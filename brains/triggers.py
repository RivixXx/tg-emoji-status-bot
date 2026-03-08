"""
Karina AI: Productivity Triggers Module
Проактивная система уведомлений и напоминаний

Триггеры активируются по расписанию и побуждают пользователя к действию:
- Утреннее планирование
- Вечерний обзор
- Напоминания о дедлайнах
- Детектор застрявших задач
- Перерывы
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Dict
from telethon import TelegramClient

from brains.tasks import (
    get_user_tasks, get_overdue_tasks, get_tasks_by_due_date,
    TaskStatus, TaskPriority, format_task_for_display
)
from brains.projects import get_active_projects, get_project_stats
from brains.sprints import (
    get_active_sprint, get_sprint_stats, get_daily_goals,
    create_daily_goals, set_evening_review, SprintStatus
)
from brains.calendar import get_upcoming_events, get_today_calendar_events

logger = logging.getLogger(__name__)


# ============================================================================
# СОСТОЯНИЕ ТРИГГЕРОВ
# ============================================================================

class TriggerState:
    """Состояние триггеров для предотвращения дублирования"""
    
    def __init__(self):
        self.last_morning_planning: Optional[date] = None
        self.last_evening_review: Optional[date] = None
        self.last_deadline_check: Optional[datetime] = None
        self.last_stuck_check: Optional[date] = None
        self.last_break_reminder: Optional[datetime] = None
        self.last_lunch_reminder: Optional[date] = None
        
    def reset(self):
        """Сброс состояния"""
        self.__init__()


trigger_state = TriggerState()


# ============================================================================
# УТРЕННЕЕ ПЛАНИРОВАНИЕ (7:00)
# ============================================================================

async def morning_planning_trigger(bot: TelegramClient, user_id: int) -> bool:
    """
    Утреннее планирование (каждый день в 7:00)
    
    Что делает:
    1. Показывает события на сегодня
    2. Предлагает сформировать цели дня
    3. Напоминает о дедлайнах
    4. Показывает активный спринт
    """
    now = datetime.now(timezone(timedelta(hours=3)))
    today = now.date()
    
    # Проверяем что уже отправляли сегодня
    if trigger_state.last_morning_planning == today:
        return False
    
    # Проверяем время (7:00 ± 1 минута)
    if not (now.hour == 7 and now.minute < 2):
        return False
    
    logger.info("🌅 Триггер: Утреннее планирование")
    
    try:
        message = "☀️ **Доброе утро, Михаил!**\n\n"
        message += "📅 **План на сегодня:**\n\n"
        
        # 1. События в календаре
        try:
            events = await get_today_calendar_events()
            if events:
                message += "📍 **Встречи:**\n"
                for event in events[:5]:
                    time_str = event['start'].strftime('%H:%M')
                    message += f"  • {time_str} — {event.get('summary', 'Без названия')}\n"
                message += "\n"
            else:
                message += "📍 Встреч на сегодня нет — отличный день для глубокой работы! 💪\n\n"
        except Exception as e:
            logger.error(f"❌ Ошибка получения календаря: {e}")
        
        # 2. Дедлайны на сегодня
        tasks_today = await get_tasks_by_due_date(user_id, days=1)
        if tasks_today:
            message += "⚠️ **Дедлайны на сегодня:**\n"
            for task in tasks_today[:5]:
                priority_emoji = "🔴" if task.priority == TaskPriority.URGENT else "🟡"
                message += f"  {priority_emoji} {task.title}\n"
            message += "\n"
        
        # 3. Просроченные задачи
        overdue = await get_overdue_tasks(user_id)
        if overdue:
            message += f"🔴 **Просрочено:** {len(overdue)} задач(и)\n"
            message += "Нужно разобраться!\n\n"
        
        # 4. Активный спринт
        active_sprint = await get_active_sprint(user_id)
        if active_sprint:
            days_left = active_sprint.days_remaining()
            stats = await get_sprint_stats(active_sprint.id)
            message += "🏃 **Активный спринт:** {active_sprint.name}\n"
            message += f"  ⏳ Осталось дней: {days_left}\n"
            message += f"  📊 Прогресс: {stats.get('completion_percent', 0)}%\n\n"
        
        # 5. Призыв к действию
        message += "💡 **Совет Карины:**\n"
        if len(tasks_today) > 3:
            message += "Сегодня плотный день! Сфокусируйся на 1-3 самых важных задачах.\n"
        elif not tasks_today:
            message += "Сегодня свободный день! Отличное время для:\n"
            message += "• Обучения новому\n"
            message += "• Долгосрочного планирования\n"
            message += "• Технического долга\n"
        else:
            message += "Сегодня хороший день! Начни с самой сложной задачи.\n"
        
        # Кнопки для быстрого действия
        from telethon import Button
        buttons = [
            [Button.inline("🎯 Цели на сегодня", b"set_daily_goals")],
            [Button.inline("📋 Показать задачи", b"show_tasks")],
            [Button.inline("🏃 Спринт", b"show_sprint")],
        ]
        
        await bot.send_message(user_id, message, buttons=buttons)
        
        trigger_state.last_morning_planning = today
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка утреннего планирования: {e}")
        return False


# ============================================================================
# ВЕЧЕРНИЙ ОБЗОР (20:00)
# ============================================================================

async def evening_review_trigger(bot: TelegramClient, user_id: int) -> bool:
    """
    Вечерний обзор (каждый день в 20:00)
    
    Что делает:
    1. Спрашивает о выполненных задачах
    2. Предлагает записать итоги дня
    3. Планирует завтрашний день
    """
    now = datetime.now(timezone(timedelta(hours=3)))
    today = now.date()
    
    # Проверяем что уже отправляли сегодня
    if trigger_state.last_evening_review == today:
        return False
    
    # Проверяем время (20:00 ± 1 минута)
    if not (now.hour == 20 and now.minute < 2):
        return False
    
    logger.info("🌙 Триггер: Вечерний обзор")
    
    try:
        # Получаем задачи которые были в работе сегодня
        tasks = await get_user_tasks(user_id, limit=50)
        completed_today = [t for t in tasks if t.status == TaskStatus.DONE and 
                          t.completed_at and t.completed_at.date() == today]
        
        message = "🌆 **Вечер на дворе!**\n\n"
        
        if completed_today:
            message += "✅ **Сегодня выполнено:**\n"
            for task in completed_today[:10]:
                message += f"  • {task.title}\n"
            message += f"\nВсего: {len(completed_today)} задач(и)\n\n"
        else:
            message += "🤔 Сегодня не было выполненных задач.\n"
            message += "Возможно ты занимался чем-то другим?\n\n"
        
        # Активный спринт
        active_sprint = await get_active_sprint(user_id)
        if active_sprint:
            days_left = active_sprint.days_remaining()
            if days_left == 0:
                message += "🔴 **Спринт заканчивается сегодня!**\n"
                message += "Нужно завершить оставшиеся задачи.\n\n"
            elif days_left == 1:
                message += "⏰ **Спринт заканчивается завтра!**\n"
                message += "Проверь что всё успеваешь.\n\n"
        
        # Призыв к вечернему обзору
        message += "📝 **Вечерний обзор:**\n\n"
        message += "Как прошёл твой день?\n"
        message += "Что получилось хорошо?\n"
        message += "Что можно улучшить завтра?\n\n"
        
        from telethon import Button
        buttons = [
            [Button.inline("📝 Записать итоги", b"evening_review_write")],
            [Button.inline("🎯 Цели на завтра", b"plan_tomorrow")],
            [Button.inline("😴 Всё, спать!", b"acknowledge_evening")],
        ]
        
        await bot.send_message(user_id, message, buttons=buttons)
        
        trigger_state.last_evening_review = today
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка вечернего обзора: {e}")
        return False


# ============================================================================
# НАПОМИНАНИЯ О ДЕДЛАЙНАХ
# ============================================================================

async def deadline_reminder_trigger(bot: TelegramClient, user_id: int) -> bool:
    """
    Напоминания о дедлайнах (каждый час)
    
    Что делает:
    1. Проверяет задачи с дедлайном через 24 часа
    2. Проверяет задачи с дедлайном через 1 час
    3. Проверяет задачи с дедлайном в текущий момент
    """
    now = datetime.now(timezone(timedelta(hours=3)))
    
    # Проверяем каждый час
    if now.minute != 0:
        return False
    
    # Не чаще раза в час
    if trigger_state.last_deadline_check:
        if (now - trigger_state.last_deadline_check).total_seconds() < 3600:
            return False
    
    logger.info("⏰ Триггер: Проверка дедлайнов")
    
    try:
        tasks = await get_user_tasks(user_id, limit=100)
        active_tasks = [t for t in tasks if t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED) 
                       and t.due_date]
        
        if not active_tasks:
            trigger_state.last_deadline_check = now
            return False
        
        # 24 часа до дедлайна
        deadline_24h = []
        # 1 час до дедлайна
        deadline_1h = []
        # Прямо сейчас
        deadline_now = []
        
        for task in active_tasks:
            delta = task.due_date - now
            hours_left = delta.total_seconds() / 3600
            
            if 23 <= hours_left <= 25:
                deadline_24h.append(task)
            elif 0.5 <= hours_left <= 1.5:
                deadline_1h.append(task)
            elif hours_left < 0.5 and hours_left > -1:
                deadline_now.append(task)
        
        # Отправляем уведомления
        if deadline_24h:
            message = "⏰ **Напоминание о дедлайнах**\n\n"
            message += "Завтра дедлайн у задач:\n\n"
            for task in deadline_24h[:5]:
                priority = "🔴" if task.priority == TaskPriority.URGENT else "🟡"
                message += f"{priority} {task.title}\n"
            message += "\nУспей сделать!"
            
            await bot.send_message(user_id, message)
        
        if deadline_1h:
            message = "🔴 **ГОРЯЧО!**\n\n"
            message += "Через час дедлайн:\n\n"
            for task in deadline_1h[:5]:
                message += f"⚠️ {task.title}\n"
            message += "\nСоберись, ты почти у цели!"
            
            await bot.send_message(user_id, message)
        
        if deadline_now:
            message = "🚨 **ДЕДЛАЙН ПРЯМО СЕЙЧАС!**\n\n"
            for task in deadline_now[:5]:
                message += f"❗️ {task.title}\n"
            message += "\nСдавай скорее!"
            
            await bot.send_message(user_id, message)
        
        trigger_state.last_deadline_check = now
        return len(deadline_24h) + len(deadline_1h) + len(deadline_now) > 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка напоминания о дедлайнах: {e}")
        return False


# ============================================================================
# ДЕТЕКТОР ЗАСТРЯВШИХ ЗАДАЧ
# ============================================================================

async def stuck_task_trigger(bot: TelegramClient, user_id: int) -> bool:
    """
    Детектор застрявших задач (каждый день в 12:00)
    
    Что делает:
    1. Ищет задачи которые 3+ дня в статусе todo
    2. Предлагает разбить на подзадачи или удалить
    """
    now = datetime.now(timezone(timedelta(hours=3)))
    today = now.date()
    
    # Проверяем что уже отправляли сегодня
    if trigger_state.last_stuck_check == today:
        return False
    
    # Проверяем время (12:00 ± 1 минута)
    if not (now.hour == 12 and now.minute < 2):
        return False
    
    logger.info("🔍 Триггер: Застрявшие задачи")
    
    try:
        tasks = await get_user_tasks(user_id, limit=100)
        
        # Ищем задачи в todo которые созданы больше 3 дней назад
        stuck_tasks = []
        for task in tasks:
            if task.status == TaskStatus.TODO and task.created_at:
                days_old = (now - task.created_at).days
                if days_old >= 3:
                    stuck_tasks.append((task, days_old))
        
        if not stuck_tasks:
            trigger_state.last_stuck_check = today
            return False
        
        # Сортируем по давности
        stuck_tasks.sort(key=lambda x: x[1], reverse=True)
        
        message = "🤔 **Застрявшие задачи**\n\n"
        message += "Эти задачи висят в todo больше 3 дней:\n\n"
        
        for task, days_old in stuck_tasks[:10]:
            message += f"⏳ {days_old} дн. — {task.title}\n"
        
        message += "\n💡 **Что делать?**\n"
        message += "1. Разбей на подзадачи\n"
        message += "2. Удали если не актуально\n"
        message += "3. Начни делать прямо сейчас!\n\n"
        
        if len(stuck_tasks) > 1:
            oldest_task = stuck_tasks[0][0]
            from telethon import Button
            buttons = [
                [Button.inline(f"🔄 Начать: {oldest_task.title[:20]}", b=f"task_start_{oldest_task.id}")],
                [Button.inline("🗑 Удалить", b"task_delete_{oldest_task.id}")],
                [Button.inline("📋 Показать все", b"show_stuck_tasks")],
            ]
            await bot.send_message(user_id, message, buttons=buttons)
        else:
            await bot.send_message(user_id, message)
        
        trigger_state.last_stuck_check = today
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка детектора застрявших задач: {e}")
        return False


# ============================================================================
# НАПОМИНАНИЯ О ПЕРЕРЫВАХ
# ============================================================================

async def break_reminder_trigger(bot: TelegramClient, user_id: int) -> bool:
    """
    Напоминания о перерывах (каждый час в 30 минут)
    
    Что делает:
    1. Напоминает сделать 5-минутный перерыв
    2. Советует размяться
    """
    now = datetime.now(timezone(timedelta(hours=3)))
    
    # Проверяем время (:30 минут)
    if now.minute != 30:
        return False
    
    # Не в рабочее время (9-18 в будни)
    if now.weekday() >= 5:  # Выходные
        return False
    if now.hour < 9 or now.hour >= 18:
        return False
    
    # Не чаще раза в час
    if trigger_state.last_break_reminder:
        if (now - trigger_state.last_break_reminder).total_seconds() < 3600:
            return False
    
    logger.info("☕ Триггер: Перерыв")
    
    try:
        # Фразы для перерывов
        break_phrases = [
            "☕ **Время перерыва!**\n\n5 минут отдыха повысят продуктивность. Разомнись!",
            "🧘 **Перерыв!**\n\nПосмотри вдаль, разомни шею. 5 минут — и снова в бой!",
            "💪 **Разминка!**\n\nВстань, пройдись, сделай пару упражнений.",
            "👀 **Отдых для глаз!**\n\nПосмотри в окно 20 секунд. Береги зрение!",
            "🚶 **Прогулка!**\n\nПройдись по офису. Движение — жизнь!",
        ]
        
        import random
        message = random.choice(break_phrases)
        
        from telethon import Button
        buttons = [
            [Button.inline("✅ Уже иду!", b"break_ack")],
            [Button.inline("⏰ Позже (15 мин)", b"break_snooze_15")],
        ]
        
        await bot.send_message(user_id, message, buttons=buttons)
        
        trigger_state.last_break_reminder = now
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка напоминания о перерыве: {e}")
        return False


# ============================================================================
# НАПОМИНАНИЕ ОБ ОБЕДЕ
# ============================================================================

async def lunch_reminder_trigger(bot: TelegramClient, user_id: int) -> bool:
    """
    Напоминание об обеде (каждый день в 13:00)
    """
    now = datetime.now(timezone(timedelta(hours=3)))
    today = now.date()
    
    # Проверяем что уже отправляли сегодня
    if trigger_state.last_lunch_reminder == today:
        return False
    
    # Проверяем время (13:00 ± 1 минута)
    if not (now.hour == 13 and now.minute < 2):
        return False
    
    # Только в будни
    if now.weekday() >= 5:
        return False
    
    logger.info("🍽️ Триггер: Обед")
    
    try:
        lunch_phrases = [
            "🍽️ **Обед!**\n\nПора подкрепиться. Здоровое питание = продуктивность!",
            "🥗 **Время обеда!**\n\nОтойди от компьютера, поешь нормально.",
            "🍕 **Обеденный перерыв!**\n\n13:00 — идеальное время для обеда.",
        ]
        
        import random
        message = random.choice(lunch_phrases)
        
        from telethon import Button
        buttons = [
            [Button.inline("✅ Иду есть!", b"lunch_ack")],
            [Button.inline("⏰ Позже", b"lunch_snooze")],
        ]
        
        await bot.send_message(user_id, message, buttons=buttons)
        
        trigger_state.last_lunch_reminder = today
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка напоминания об обеде: {e}")
        return False


# ============================================================================
# ПРОВЕРКА ПРОСРОЧЕННЫХ ЗАДАЧ (9:00)
# ============================================================================

async def overdue_tasks_trigger(bot: TelegramClient, user_id: int) -> bool:
    """
    Проверка просроченных задач (каждый день в 9:00)
    """
    now = datetime.now(timezone(timedelta(hours=3)))
    today = now.date()
    
    # Проверяем время (9:00 ± 1 минута)
    if not (now.hour == 9 and now.minute < 2):
        return False
    
    logger.info("🔴 Триггер: Просроченные задачи")
    
    try:
        overdue = await get_overdue_tasks(user_id)
        
        if not overdue:
            return False
        
        message = "🔴 **Просроченные задачи!**\n\n"
        message += f"У тебя {len(overdue)} просроченных задач(и):\n\n"
        
        for task in overdue[:10]:
            days_overdue = abs(task.days_until_due())
            message += f"  • {task.title} (просрочено на {days_overdue} дн.)\n"
        
        if len(overdue) > 10:
            message += f"\n...и ещё {len(overdue) - 10}"
        
        message += "\n\n💡 **План действий:**\n"
        message += "1. Разберись с самыми старыми\n"
        message += "2. Перенеси дедлайн если нужно\n"
        message += "3. Удали неактуальные\n"
        
        from telethon import Button
        buttons = [
            [Button.inline("📋 Показать все", b"show_overdue")],
            [Button.inline("🗑 Удалить неактуальные", b"cleanup_overdue")],
        ]
        
        await bot.send_message(user_id, message, buttons=buttons)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки просроченных задач: {e}")
        return False


# ============================================================================
# ГЛАВНЫЙ ЦИКЛ ТРИГГЕРОВ
# ============================================================================

async def start_triggers_loop(bot: TelegramClient, user_id: int):
    """
    Запускает цикл проверки триггеров
    Работает постоянно, проверяет каждый триггер по расписанию
    """
    logger.info("🎯 Запуск цикла триггеров продуктивности...")
    
    while True:
        try:
            # Проверяем все триггеры параллельно
            await asyncio.gather(
                morning_planning_trigger(bot, user_id),
                evening_review_trigger(bot, user_id),
                deadline_reminder_trigger(bot, user_id),
                stuck_task_trigger(bot, user_id),
                break_reminder_trigger(bot, user_id),
                lunch_reminder_trigger(bot, user_id),
                overdue_tasks_trigger(bot, user_id),
                return_exceptions=True
            )
            
            # Проверка каждую минуту
            await asyncio.sleep(60)
            
        except asyncio.CancelledError:
            logger.info("👋 Цикл триггеров остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле триггеров: {e}")
            await asyncio.sleep(60)


# ============================================================================
# СБРОС СОСТОЯНИЯ (при рестарте)
# ============================================================================

def reset_trigger_state():
    """Сбрасывает состояние триггеров"""
    trigger_state.reset()
    logger.info("🔄 Состояние триггеров сброшено")
