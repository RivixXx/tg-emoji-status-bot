import logging
import random
import os
import asyncio
import re
from telethon import events, types
from brains.weather import get_weather
from brains.ai import ask_karina
from brains.news import get_latest_news
from brains.memory import save_memory
from brains.calendar import get_upcoming_events, add_calendar, get_conflict_report
from brains.health import get_health_report_text, save_health_record
from brains.stt import transcribe_voice
from brains.reminders import reminder_manager, ReminderType
from brains.reminder_generator import clear_cache
from brains.smart_summary import generate_weekly_summary
from brains.aura_settings import aura_settings_manager, UserAuraSettings
from auras import confirm_health

from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ========== ЭФФЕКТ ПЕЧАТНОЙ МАШИНКИ (SMART TYPEWRITER) ==========

async def send_with_typewriter(event, text):
    """Эффект печатной машинки для Telegram. 
    Безопасно для лимитов Telegram (обновляет сообщение не чаще 2 раз в секунду)."""
    
    # Если ответ короткий (меньше 50 символов), выводим сразу, без спецэффектов
    if len(text) < 50:
        await event.respond(text)
        return

    # Разбиваем текст на слова
    words = text.split()
    
    # Вычисляем размер порции (примерно 4-5 "кадров" анимации на средний текст)
    # Чтобы не получить бан от Telegram за слишком частые изменения (FloodWait)
    frames = min(6, len(words) // 4) 
    chunk_size = max(3, len(words) // frames)
    
    # 1. Отправляем начало текста с мигающим курсором ▒
    current_text = " ".join(words[:chunk_size]) + " ▒"
    msg = await event.respond(current_text)
    
    # 2. Постепенно дописываем текст
    for i in range(chunk_size, len(words), chunk_size):
        await asyncio.sleep(0.6)  # Идеальная задержка для Telegram
        current_text = " ".join(words[:i + chunk_size]) + " ▒"
        try:
            await msg.edit(current_text)
        except Exception:
            pass # Игнорируем ошибки, если текст не изменился
            
    # 3. Финальный текст (убираем курсор)
    await asyncio.sleep(0.4)
    try:
        await msg.edit(text)
    except Exception:
        pass

def register_discovery_skills(client):
    @client.on(events.NewMessage(chats='me', pattern='(?i)id'))
    async def discovery_handler(event):
        logger.info(f"🔍 Детектор ID вызван пользователем {event.chat_id}")
        
        found = False
        if event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, types.MessageEntityCustomEmoji):
                    await event.reply(f"✅ Код кастомного эмодзи: <code>{ent.document_id}</code>\nСкопируй его и отправь мне.")
                    found = True
                    break
        
        if not found:
            await event.reply("❌ Это обычный эмодзи или текст. \nЧтобы получить ID для статуса, отправь **кастомный** эмодзи (из любого Premium-набора).")

def register_karina_base_skills(client):
    # Обработчик callback_query (ТОЛЬКО для кнопок напоминаний и здоровья)
    @client.on(events.CallbackQuery(data=re.compile(b"^(confirm_|skip_|snooze_|acknowledge)")))
    async def reminder_callback_handler(event):
        """Обработка нажатий на кнопки напоминаний"""
        data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
        logger.info(f"🔘 Callback Skills: {data} от {event.chat_id}")
        
        # Получаем объект сообщения явно, чтобы избежать AttributeError
        message = await event.get_message()
        if not message:
            logger.error("❌ Не удалось получить сообщение для callback")
            return

        # Подтверждение здоровья
        if data == "confirm_health":
            await reminder_manager.confirm_reminder(f"health_{datetime.now().strftime('%Y%m%d')}")
            await confirm_health()
            await save_health_record(True)  # Сохраняем в базу!
            await event.answer("✅ Умничка! Я горжусь тобой! ❤️", alert=True)
            await event.edit(f"{message.text}\n\n✅ Подтверждено!")
            return
        
        # Отсрочка (snooze)
        if data.startswith("snooze_"):
            minutes = int(data.split("_")[1])
            # Ищем активное напоминание
            for rid, reminder in reminder_manager.reminders.items():
                if reminder.is_active and not reminder.is_confirmed:
                    await reminder_manager.snooze_reminder(rid, minutes)
                    await event.answer(f"⏰ Напомню через {minutes} мин!", alert=True)
                    await event.edit(f"{message.text}\n\n⏰ Отложено на {minutes} мин.")
                    return
        
        # Пропуск
        if data == "skip_health":
            await event.answer("Хорошо, но я ещё напомню! 😉", alert=True)
            await event.edit(f"{message.text}\n\n⏭️ Пропущено.")
            return
        
        # Подтверждение встречи
        if data == "confirm_meeting":
            await event.answer("👍 Отлично! Ты готов! 🚀", alert=True)
            await event.edit(f"{message.text}\n\n👍 Готов!")
            return
        
        # Подтверждение обеда
        if data == "confirm_lunch":
            await event.answer("🍽 Приятного аппетита! 🥗", alert=True)
            await event.edit(f"{message.text}\n\n🍽 Приятного!")
            return
        
        # Подтверждение перерыва
        if data == "confirm_break":
            await event.answer("🧘 Отлично! Отдыхай! 😊", alert=True)
            await event.edit(f"{message.text}\n\n🧘 Отдыхай!")
            return
        
        # Просто подтверждение (acknowledge)
        if data == "acknowledge":
            await event.answer("😊 Рада что ты со мной! 💕", alert=False)
            await event.edit(f"{message.text}\n\n😊 💕")
            return
        
        # По умолчанию
        await event.answer("👌 Ок!", alert=False)

    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        logger.info(f"📩 /start от пользователя {event.chat_id}")
        await event.respond(
            "Привет! Я Карина. 😊\n\nЯ теперь не просто бот, у меня есть удобная панель управления! Нажми кнопку ниже или используй /app.",
            buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
        )
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/app'))
    async def app_command_handler(event):
        """Скилл: Открыть Mini App"""
        logger.info(f"📩 /app от пользователя {event.chat_id}")
        await event.respond(
            "Твоя персональная панель управления Кариной:",
            buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
        )
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/calendar'))
    async def calendar_handler(event):
        logger.info(f"📩 /calendar от пользователя {event.chat_id}")
        info = await get_upcoming_events()
        await event.respond(f"🗓 **Твои планы:**\n\n{info}")
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/conflicts'))
    async def conflicts_handler(event):
        """Скилл: Проверка конфликтов в календаре"""
        logger.info(f"📩 /conflicts от пользователя {event.chat_id}")
        report = await get_conflict_report()
        await event.respond(report)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/health'))
    async def health_handler(event):
        """Скилл: Статистика здоровья"""
        logger.info(f"📩 /health от пользователя {event.chat_id}")
        report = await get_health_report_text(7)
        await event.respond(report)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/remember'))
    async def remember_handler(event):
        """Скилл: Запомнить факт"""
        text_to_save = event.text.replace('/remember', '').strip()
        if not text_to_save:
            await event.respond("Напиши, что именно мне нужно запомнить. 😊\nПример: `/remember Мой любимый цвет — синий`")
            return

        logger.info(f"🧠 Сохранение в память: {text_to_save}")
        success = await save_memory(text_to_save, metadata={"source": "manual_command", "user_id": event.chat_id})

        if success:
            await event.respond("✅ Запомнила! Теперь я буду это знать. 😊")
        else:
            await event.respond("Ой, что-то пошло не так при сохранении в базу памяти. 😔")
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/weather'))
    async def weather_handler(event):
        logger.info(f"📩 /weather от пользователя {event.chat_id}")
        weather = await get_weather()
        if not weather:
            await event.respond("🌤 Ой, не смогла узнать погоду. Проверь API ключ в настройках! 😔")
        else:
            await event.respond(f"🌤 **Погода:**\n\n{weather}")
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/clearrc'))
    async def clear_cache_handler(event):
        """Очистить кэш напоминаний (для тестирования)"""
        clear_cache()
        await event.respond("🧹 Кэш напоминаний очищен! Теперь все напоминания будут уникальными! ✨")
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/agent'))
    async def agent_handler(event):
        """Скилл: ReAct агент для сложных задач"""
        logger.info(f"🤖 ReAct Agent: Запрос от {event.chat_id}")
        
        task = event.text.replace('/agent', '').strip()
        
        if not task:
            await event.respond(
                "🤖 **ReAct Агент**\n\n"
                "Я могу выполнить сложную задачу, требующую планирования и множественных шагов.\n\n"
                "**Примеры:**\n"
                "• `Создай файл test.py с функцией hello()`\n"
                "• `Установи библиотеку requests`\n"
                "• `Проверь работу бота и перезапусти если нужно`\n\n"
                "💡 Агент будет выполнять задачу пошагово, анализировать ошибки и корректировать стратегию."
            )
            raise events.StopPropagation
        
        await event.respond("🧠 Анализирую задачу и составляю план...")
        
        # Импортируем внутри функции
        from brains.ai import ask_karina_react
        
        result = await ask_karina_react(task, chat_id=event.chat_id)
        
        await event.respond(result)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/summary'))
    async def summary_handler(event):
        """Скилл: Еженедельный отчёт Smart Summary"""
        logger.info(f"📩 /summary от пользователя {event.chat_id}")
        
        # Парсим аргументы (количество дней)
        args = event.text.split()
        days = 7
        if len(args) > 1:
            try:
                days = int(args[1])
                days = max(1, min(days, 30))  # От 1 до 30 дней
            except ValueError:
                pass
        
        await event.respond(f"📊 Генерирую отчёт за {days} дн...")
        
        summary = await generate_weekly_summary(event.chat_id, days)
        
        message = f"""
📊 **Еженедельный отчёт**
{summary['period']['start']} - {summary['period']['end']}

❤️ **Здоровье:**
✅ Подтверждено: {summary['health']['confirmed']}
❌ Пропущено: {summary['health']['missed']}
📈 Успешность: {summary['health']['compliance_rate']}%
📊 Тренд: {summary['health']['trend']}

🧠 **Память:**
📝 Новых воспоминаний: {summary['memories']['new_memories']}

{summary['ai_summary']}
"""
        await event.respond(message)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/aurasettings'))
    async def aura_settings_handler(event):
        """Скилл: Управление настройками аур"""
        logger.info(f"📩 /aurasettings от пользователя {event.chat_id}")

        args = event.text.split()

        if len(args) < 2:
            # Показываем текущие настройки
            settings = await aura_settings_manager.get_settings(event.chat_id)

            message = f"""
⚙️ **Настройки аур**

🎨 Emoji-статус: {'✅' if settings.emoji_status.enabled else '❌'} {settings.emoji_status.start_time}-{settings.emoji_status.end_time}
📝 Био-статус: {'✅' if settings.bio_status.enabled else '❌'} {settings.bio_status.start_time}-{settings.bio_status.end_time}
❤️ Напоминание о здоровье: {'✅' if settings.health_reminder.enabled else '❌'} {settings.health_reminder.start_time}
☀️ Утреннее приветствие: {'✅' if settings.morning_greeting.enabled else '❌'} {settings.morning_greeting.start_time}
🌙 Вечернее напоминание: {'✅' if settings.evening_reminder.enabled else '❌'} {settings.evening_reminder.start_time}
🍽 Обед: {'✅' if settings.lunch_reminder.enabled else '❌'} {settings.lunch_reminder.start_time}
🧘 Перерыв: {'✅' if settings.break_reminder.enabled else '❌'} {settings.break_reminder.start_time}

Используйте:
/aurasettings enable <aura_name> [time]
/aurasettings disable <aura_name>
"""
            await event.respond(message)
            raise events.StopPropagation

        command = args[1].lower()

        if command == 'enable' and len(args) >= 3:
            aura_name = args[2].lower()
            time_val = args[3] if len(args) > 3 else None

            valid_auras = ['emoji_status', 'bio_status', 'health_reminder', 'morning_greeting',
                          'evening_reminder', 'lunch_reminder', 'break_reminder']

            if aura_name not in valid_auras:
                await event.respond(f"❌ Неизвестная аура. Доступные: {', '.join(valid_auras)}")
                raise events.StopPropagation

            await aura_settings_manager.update_aura(
                event.chat_id,
                aura_name,
                enabled=True,
                start_time=time_val
            )
            await event.respond(f"✅ Аура '{aura_name}' включена{' в ' + time_val if time_val else ''}")
            raise events.StopPropagation

        elif command == 'disable' and len(args) >= 3:
            aura_name = args[2].lower()

            await aura_settings_manager.update_aura(event.chat_id, aura_name, enabled=False)
            await event.respond(f"⏸️ Аура '{aura_name}' выключена")
            raise events.StopPropagation

        else:
            await event.respond("""
Используйте:
/aurasettings — показать настройки
/aurasettings enable <aura_name> [time] — включить
/aurasettings disable <aura_name> — выключить

Доступные ауры: emoji_status, bio_status, health_reminder, morning_greeting, evening_reminder, lunch_reminder, break_reminder
""")

    @client.on(events.NewMessage(pattern='/employees'))
    async def employees_handler(event):
        """Скилл: Список сотрудников по отделам"""
        logger.info(f"📩 /employees от пользователя {event.chat_id}")

        from brains.employees import get_all_employees

        employees = await get_all_employees()

        if not employees:
            await event.respond("📋 Список сотрудников пока пуст.")
            return

        # Группируем по отделам
        departments = {}
        for emp in employees:
            dept = emp.get('department', 'Без отдела')
            if dept not in departments:
                departments[dept] = []
            departments[dept].append(emp)

        message = "👥 **Сотрудники компании:**\n\n"

        for dept, emps in sorted(departments.items()):
            message += f"**{dept}:**\n"
            for emp in emps:
                bd = emp.get('birthday', '')
                bd_str = f" ({bd[5:] if bd else 'Н/Д'})" if bd else ""
                message += f"• {emp['full_name']} — {emp['position']}{bd_str}\n"
            message += "\n"

        # Telegram имеет лимит на длину сообщения (4096 символов)
        if len(message) > 4000:
            # Отправляем частями
            for i in range(0, len(message), 4000):
                await event.respond(message[i:i+4000])
        else:
            await event.respond(message)
        
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/birthdays'))
    async def birthdays_handler(event):
        """Скилл: Ближайшие дни рождения сотрудников"""
        logger.info(f"📩 /birthdays от пользователя {event.chat_id}")

        from brains.employees import get_upcoming_birthdays

        args = event.text.split()
        days = 7
        if len(args) > 1:
            try:
                days = int(args[1])
                days = max(1, min(days, 30))
            except ValueError:
                pass

        upcoming = await get_upcoming_birthdays(days)

        if not upcoming:
            await event.respond(f"🎂 В ближайшие {days} дней дней рождения нет.")
            return

        message = f"🎂 **Ближайшие дни рождения ({days} дн.):**\n\n"
        for emp in upcoming:
            bd_date = emp.get('birthday', '')[5:] if emp.get('birthday') else 'Н/Д'
            days_left = emp.get('days_until', 0)
            message += f"• {emp['full_name']} — {bd_date} (через {days_left} дн.)\n"

        await event.respond(message)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/news'))
    async def news_handler(event):
        """Скилл: Свежие новости телематики"""
        logger.info(f"📩 /news от пользователя {event.chat_id}")


        # Проверяем аргументы
        args = event.text.split()
        force_refresh = False

        if len(args) > 1 and args[1].lower() in ['force', 'fresh', 'обновить']:
            force_refresh = True
            await event.respond("🔄 Обновляю новости...")

        news = await get_latest_news(limit=5, force_refresh=force_refresh, user_id=event.chat_id)
        await event.respond(news)
        
        # Важно: возвращаем чтобы не сработал chat_handler
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/newsforce'))
    async def news_force_handler(event):
        """Скилл: Принудительное обновление новостей (очистка кэша)"""
        logger.info(f"📩 /newsforce от пользователя {event.chat_id}")

        from brains.news import clear_news_cache

        clear_news_cache()
        await event.respond("🧹 Кэш новостей очищен. Загружаю свежие данные...")

        news = await get_latest_news(limit=5, force_refresh=True, user_id=event.chat_id)
        await event.respond(news)
        
        # Важно: возвращаем чтобы не сработал chat_handler
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/newssources'))
    async def news_sources_handler(event):
        """Скилл: Управление источниками новостей"""
        logger.info(f"📩 /newssources от пользователя {event.chat_id}")

        from brains.news import get_news_sources, enable_source, disable_source

        args = event.text.split()

        if len(args) < 2:
            # Показываем список источников
            sources = await get_news_sources()

            message = "📰 **Источники новостей:**\n\n"
            for src in sources:
                status = "✅" if src.get("enabled", True) else "⏸️"
                message += f"{status} **{src['name']}** ({src['category']})\n"
                message += f"   `{src['url']}`\n\n"

            message += """**Использование:**
`/newssources enable <name>` — включить
`/newssources disable <name>` — отключить
"""
            await event.respond(message)
            raise events.StopPropagation

        # Управление источниками
        command = args[1].lower()
        source_name = " ".join(args[2:]) if len(args) > 2 else ""

        if command == 'enable':
            success = await enable_source(source_name)
            if success:
                await event.respond(f"✅ Источник '{source_name}' включен")
            else:
                await event.respond(f"❌ Источник '{source_name}' не найден")

        elif command == 'disable':
            success = await disable_source(source_name)
            if success:
                await event.respond(f"⏸️ Источник '{source_name}' отключен")
            else:
                await event.respond(f"❌ Источник '{source_name}' не найден")

        else:
            await event.respond("Неизвестная команда. Используйте /newssources для справки.")
        
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/newsclear'))
    async def news_clear_handler(event):
        """Скилл: Очистить историю новостей"""
        logger.info(f"📩 /newsclear от пользователя {event.chat_id}")

        from brains.news import clear_old_news_history

        args = event.text.split()
        days = 30

        if len(args) > 1:
            try:
                days = int(args[1])
            except ValueError:
                pass

        count = await clear_old_news_history(days)
        await event.respond(f"🧹 Удалено {count} новостей старше {days} дн.")
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/habits'))
    async def habits_handler(event):
        """Скилл: Управление привычками"""
        logger.info(f"📩 /habits от пользователя {event.chat_id}")

        from brains.productivity import get_user_habits, get_habit_stats, save_habit_track

        args = event.text.split()

        if len(args) < 2:
            # Показываем список привычек и статистику
            habits = await get_user_habits(event.chat_id)
            stats = await get_habit_stats(event.chat_id, days=7)

            message = "🎯 **Мои привычки:**\n\n"
            for habit in habits:
                habit_stats = stats.get(habit['name'], {})
                rate = habit_stats.get('rate', 0)
                bar = "█" * (rate // 10) + "░" * (10 - rate // 10)
                message += f"{habit['name']}\n"
                message += f"  Цель: {habit['target']}\n"
                message += f"  [{bar}] {rate}%\n\n"

            message += """**Использование:**
`/habits track <название>` — отметить выполненной
`/habits skip <название>` — пропустить
`/habits stats` — подробная статистика
"""
            await event.respond(message)
            raise events.StopPropagation

        command = args[1].lower()

        if command in ['track', 'complete', 'done'] and len(args) >= 3:
            habit_name = " ".join(args[2:])
            success = await save_habit_track(event.chat_id, habit_name, completed=True)
            if success:
                await event.respond(f"✅ Отлично! Привычка '{habit_name}' отмечена!")
            else:
                await event.respond("❌ Ошибка при сохранении")
            raise events.StopPropagation

        elif command == 'skip' and len(args) >= 3:
            habit_name = " ".join(args[2:])
            success = await save_habit_track(event.chat_id, habit_name, completed=False)
            if success:
                await event.respond(f"⏭️ Пропущено: {habit_name}")
            raise events.StopPropagation

        elif command == 'stats':
            from brains.productivity import generate_productivity_report
            await event.respond("📊 Генерирую отчёт...")
            report = await generate_productivity_report(event.chat_id, days=7)
            await event.respond(report)
            raise events.StopPropagation

        else:
            await event.respond("Неизвестная команда. Используйте /habits для справки.")
            raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/productivity'))
    async def productivity_handler(event):
        """Скилл: Отчёт о продуктивности"""
        logger.info(f"📩 /productivity от пользователя {event.chat_id}")

        from brains.productivity import generate_productivity_report

        args = event.text.split()
        days = 7

        if len(args) > 1:
            try:
                days = int(args[1])
                days = max(1, min(days, 30))
            except ValueError:
                pass

        await event.respond(f"📊 Генерирую отчёт за {days} дн...")
        report = await generate_productivity_report(event.chat_id, days)
        await event.respond(report)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/workstats'))
    async def workstats_handler(event):
        """Скилл: Статистика работы"""
        logger.info(f"📩 /workstats от пользователя {event.chat_id}")

        from brains.productivity import analyze_work_patterns

        args = event.text.split()
        days = 7

        if len(args) > 1:
            try:
                days = int(args[1])
            except ValueError:
                pass

        patterns = await analyze_work_patterns(event.chat_id, days)

        if "error" in patterns:
            await event.respond("📊 Недостаточно данных за этот период.")
            raise events.StopPropagation

        message = f"""📊 **Рабочая статистика** ({days} дн.)

⏰ **Режим:**
• Среднее начало: {patterns.get('avg_start_time', 'Н/Д')}
• Средний конец: {patterns.get('avg_end_time', 'Н/Д')}
• Длительность: {patterns.get('avg_duration', 0)}ч

📅 **Активность:**
• Рабочих дней: {patterns.get('total_days', 0)}
• Встреч: {patterns.get('total_meetings', 0)}

⚠️ **Зоны внимания:**
• Переработок: {patterns.get('overwork_days', 0)}
• Выходных дней: {patterns.get('weekend_work_days', 0)}
• Поздних вечеров: {patterns.get('late_night_days', 0)}
"""
        await event.respond(message)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/overwork'))
    async def overwork_handler(event):
        """Скилл: Проверка переработок"""
        logger.info(f"📩 /overwork от пользователя {event.chat_id}")

        from brains.productivity import get_overwork_days, check_overwork_alert

        args = event.text.split()
        days = 30

        if len(args) > 1:
            try:
                days = int(args[1])
            except ValueError:
                pass

        # Проверяем текущую тревогу
        alert = await check_overwork_alert(event.chat_id)

        if alert:
            await event.respond(f"⚠️ **Внимание!**\n\n{alert}")
        else:
            await event.respond("✅ Сегодня переработок нет! Так держать! 🎉")

        # Показываем статистику
        overwork_list = await get_overwork_days(event.chat_id, days)

        if overwork_list:
            message = f"\n📊 **Переработки за {days} дн.:**\n"
            for day in overwork_list[:5]:
                date = day['date']
                hours = day['duration']
                message += f"• {date}: {hours}ч\n"

            if len(overwork_list) > 5:
                message += f"... и ещё {len(overwork_list) - 5}\n"

            await event.respond(message)

        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/vision'))
    async def vision_handler(event):
        """Скилл: Анализ изображений (справка)"""
        logger.info(f"📩 /vision от пользователя {event.chat_id}")

        message = """
👁️ **Компьютерное зрение Карины**

**Отправить фото:**
Просто отправь фото в чат — Карина автоматически проанализирует его!

**Специальные команды:**
`/ocr` — Распознать текст на фото
`/analyze` — Детальный анализ изображения
`/doc` — Анализ документа (паспорт, права, справка)
`/receipt` — Анализ чека (товары, суммы)
`/vision find <текст>` — Поиск по проанализированным фото

**Что умеет Карина:**
📝 Распознавать текст (OCR)
📄 Анализировать документы
🧾 Читать чеки и счета
🖼️ Описывать фотографии
🔍 Искать по проанализированным изображениям

**Примеры:**
1. Отправь фото документа → `/doc`
2. Отправь фото чека → `/receipt`
3. Отправь скриншот → `/analyze`
"""
        await event.respond(message)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/ocr'))
    async def ocr_handler(event):
        """Скилл: Распознавание текста на фото"""
        logger.info(f"📩 /ocr от пользователя {event.chat_id}")

        # Проверяем, есть ли фото в ответе
        if not event.is_reply:
            await event.respond("❌ Отправь команду в ответ на фото или просто отправь фото с подписью /ocr")
            raise events.StopPropagation

        reply = await event.get_reply_message()
        if not (reply.photo or (reply.document and reply.document.mime_type.startswith('image/'))):
            await event.respond("❌ Это не фото! Отправь /ocr в ответ на изображение")
            raise events.StopPropagation

        # Скачиваем и анализируем
        photo_path = await reply.download_media(file="temp/vision/ocr_{}.jpg".format(datetime.now().strftime('%Y%m%d_%H%M%S')))
        
        if photo_path:
            try:
                await event.respond("🔍 Распознаю текст...")
                
                from brains.vision import ocr_image
                result = await ocr_image(photo_path, user_id=event.chat_id)
                
                if result.get("success"):
                    response = f"📝 **Распознанный текст:**\n\n```\n{result.get('text', 'Текст не найден')}\n```\n\n"
                    
                    if result.get("structured"):
                        response += f"**Структура:**\n{result['structured']}"
                    
                    await event.respond(response, parse_mode='markdown')
                else:
                    await event.respond(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            
            except Exception as e:
                logger.error(f"OCR error: {e}")
                await event.respond(f"❌ Ошибка OCR: {e}")
            finally:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/analyze'))
    async def analyze_handler(event):
        """Скилл: Детальный анализ изображения"""
        logger.info(f"📩 /analyze от пользователя {event.chat_id}")

        if not event.is_reply:
            await event.respond("❌ Отправь команду в ответ на фото")
            raise events.StopPropagation

        reply = await event.get_reply_message()
        if not (reply.photo or (reply.document and reply.document.mime_type.startswith('image/'))):
            await event.respond("❌ Это не фото!")
            raise events.StopPropagation

        photo_path = await reply.download_media(file="temp/vision/analyze_{}.jpg".format(datetime.now().strftime('%Y%m%d_%H%M%S')))
        
        if photo_path:
            try:
                await event.respond("🔍 Анализирую изображение...")
                
                from brains.vision import analyze_photo_scene
                result = await analyze_photo_scene(photo_path, user_id=event.chat_id)

                if result.get("success"):
                    await event.respond(f"🖼️ **Анализ:**\n\n{result.get('description', result.get('full_analysis', 'Анализ не удался'))}")
                else:
                    await event.respond(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            
            except Exception as e:
                logger.error(f"Analyze error: {e}")
                await event.respond(f"❌ Ошибка анализа: {e}")
            finally:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/doc'))
    async def doc_handler(event):
        """Скилл: Анализ документа"""
        logger.info(f"📩 /doc от пользователя {event.chat_id}")

        if not event.is_reply:
            await event.respond("❌ Отправь команду в ответ на фото документа")
            raise events.StopPropagation

        reply = await event.get_reply_message()
        if not (reply.photo or (reply.document and reply.document.mime_type.startswith('image/'))):
            await event.respond("❌ Это не фото!")
            raise events.StopPropagation

        photo_path = await reply.download_media(file="temp/vision/doc_{}.jpg".format(datetime.now().strftime('%Y%m%d_%H%M%S')))
        
        if photo_path:
            try:
                await event.respond("📄 Анализирую документ...")
                
                from brains.vision import analyze_document
                result = await analyze_document(photo_path, user_id=event.chat_id)
                
                if result.get("success"):
                    response = f"📄 **Тип:** {result.get('document_type', 'Не определён')}\n\n"
                    response += f"**Данные:**\n{result.get('fields', 'Не удалось извлечь данные')}"
                    
                    await event.respond(response)
                    
                    # Предлагаем запомнить
                    await event.respond("_Хочешь, я запомню важные данные из этого документа? Напиши `/remember` с нужной информацией._")
                else:
                    await event.respond(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            
            except Exception as e:
                logger.error(f"Doc analysis error: {e}")
                await event.respond(f"❌ Ошибка анализа документа: {e}")
            finally:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/receipt'))
    async def receipt_handler(event):
        """Скилл: Анализ чека"""
        logger.info(f"📩 /receipt от пользователя {event.chat_id}")

        if not event.is_reply:
            await event.respond("❌ Отправь команду в ответ на фото чека")
            raise events.StopPropagation

        reply = await event.get_reply_message()
        if not (reply.photo or (reply.document and reply.document.mime_type.startswith('image/'))):
            await event.respond("❌ Это не фото!")
            raise events.StopPropagation

        photo_path = await reply.download_media(file="temp/vision/receipt_{}.jpg".format(datetime.now().strftime('%Y%m%d_%H%M%S')))
        
        if photo_path:
            try:
                await event.respond("🧾 Анализирую чек...")
                
                from brains.vision import analyze_receipt
                result = await analyze_receipt(photo_path, user_id=event.chat_id)
                
                if result.get("success"):
                    await event.respond(f"🧾 **Анализ чека:**\n\n{result.get('full_analysis', 'Не удалось проанализировать чек')}")
                else:
                    await event.respond(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            
            except Exception as e:
                logger.error(f"Receipt analysis error: {e}")
                await event.respond(f"❌ Ошибка анализа чека: {e}")
            finally:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/vision find'))
    async def vision_find_handler(event):
        """Скилл: Поиск по проанализированным фото"""
        logger.info(f"📩 /vision find от пользователя {event.chat_id}")

        args = event.text.split(maxsplit=2)
        if len(args) < 3:
            await event.respond("❌ Использование: `/vision find <запрос>`\n\nПример: `/vision find паспорт`")
            raise events.StopPropagation

        query = args[2]

        from brains.vision import search_vision_history
        results = await search_vision_history(event.chat_id, query, limit=5)

        if not results:
            await event.respond(f"🔍 Ничего не найдено по запросу \"{query}\"")
            raise events.StopPropagation

        message = f"🔍 **Найдено {len(results)} результатов:**\n\n"
        for i, item in enumerate(results, 1):
            analyzed = datetime.fromisoformat(item['analyzed_at'].replace('+00:00', '+00:00'))
            message += f"{i}. **{analyzed.strftime('%d.%m.%Y %H:%M')}**\n"
            message += f"   Файл: {item.get('original_filename', 'Н/Д')}\n"
            message += f"   Запрос: {item.get('prompt', 'Н/Д')[:50]}...\n"
            message += f"   Анализ: {item['analysis'][:150]}...\n\n"

        if len(message) > 4000:
            message = message[:4000] + "..."

        await event.respond(message)
        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/tts'))
    async def tts_handler(event):
        """Скилл: Управление TTS (голосовыми ответами)"""
        logger.info(f"📩 /tts от пользователя {event.chat_id}")

        from brains.tts import get_tts_settings, set_tts_enabled, get_available_voices, tts_engine

        args = event.text.split()

        if len(args) < 2:
            # Показываем текущие настройки
            settings = await get_tts_settings(event.chat_id)
            voices = get_available_voices()

            status_emoji = "✅" if settings["enabled"] else "❌"
            current_voice = next((v for v in voices if v["id"] == settings["voice"]), None)

            message = f"""
🎤 **Голосовые ответы Карины**

Статус: {status_emoji} {'Включено' if settings['enabled'] else 'Выключено'}
Голос: {current_voice['name'] if current_voice else settings['voice']} ({current_voice['style'] if current_voice else ''})

**Управление:**
`/tts on` — Включить голосовые ответы
`/tts off` — Выключить голосовые ответы
`/ttsvoice` — Выбрать голос
`/ttstest` — Тестовое сообщение

**Доступные голоса:**
"""
            for v in voices:
                if v["gender"] == "female":
                    message += f"• {v['name']} — {v['style']}\n"

            await event.respond(message)
            raise events.StopPropagation

        command = args[1].lower()

        if command == 'on':
            success = await set_tts_enabled(event.chat_id, True)
            if success:
                await event.respond("✅ **Голосовые ответы включены!**\n\nТеперь Карина будет отвечать голосом! 🎤\n\nИспользуй `/ttstest` для проверки.")
            else:
                await event.respond("❌ Ошибка при включении TTS")
            raise events.StopPropagation

        elif command == 'off':
            success = await set_tts_enabled(event.chat_id, False)
            if success:
                await event.respond("⏸️ **Голосовые ответы выключены**\n\nТеперь Карина отвечает текстом.")
            else:
                await event.respond("❌ Ошибка при выключении TTS")
            raise events.StopPropagation

        elif command == 'test':
            await event.respond("🎤 Тестирую голос...")

            settings = await get_tts_settings(event.chat_id)
            voice = settings.get("voice", "ksenia")

            try:
                from brains.tts import text_to_speech

                test_text = f"Привет! Это тестовое сообщение. Мой голос — {voice}."
                audio_data = await text_to_speech(test_text, voice=voice)

                # Отправляем голосовое
                await client.send_voice(event.chat_id, audio_data)
                await event.respond("✅ Тест успешен!")

            except Exception as e:
                logger.error(f"TTS test error: {e}")
                await event.respond(f"❌ Ошибка при тестировании: {e}")

            raise events.StopPropagation

        else:
            await event.respond("❌ Неизвестная команда. Используйте `/tts` для справки.")
            raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/ttsvoice'))
    async def ttsvoice_handler(event):
        """Скилл: Выбор голоса для TTS"""
        logger.info(f"📩 /ttsvoice от пользователя {event.chat_id}")

        from brains.tts import get_tts_settings, set_tts_voice, get_available_voices, AVAILABLE_VOICES

        args = event.text.split()

        if len(args) < 2:
            # Показываем список голосов
            settings = await get_tts_settings(event.chat_id)
            voices = get_available_voices()

            message = "🎭 **Доступные голоса:**\n\n"

            for v in voices:
                current = "⭐" if v["id"] == settings["voice"] else "  "
                message += f"{current} **{v['name']}** (`/ttsvoice {v['id']}`)\n"
                message += f"   {v['style']}. {v['description']}\n\n"

            message += """**Пример:**
`/ttsvoice ksenia` — Выбрать Ксению
`/ttsvoice irina` — Выбрать Ирину
"""
            await event.respond(message)
            raise events.StopPropagation

        # Меняем голос
        new_voice = args[1].lower()

        if new_voice not in AVAILABLE_VOICES:
            await event.respond(f"❌ Неизвестный голос: {new_voice}\n\nИспользуй `/ttsvoice` для списка доступных голосов.")
            raise events.StopPropagation

        success = await set_tts_voice(event.chat_id, new_voice)

        if success:
            voice_info = AVAILABLE_VOICES[new_voice]
            await event.respond(f"✅ **Голос изменён на {voice_info['name']}!**\n\n{voice_info['style']}. {voice_info['description']}\n\nИспользуй `/ttstest` для проверки.")
        else:
            await event.respond("❌ Ошибка при смене голоса")

        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/ttstest'))
    async def ttstest_handler(event):
        """Скилл: Быстрое тестирование TTS"""
        logger.info(f"📩 /ttstest от пользователя {event.chat_id}")

        from brains.tts import get_tts_settings, text_to_speech

        await event.respond("🎤 Генерирую тестовое сообщение...")

        settings = await get_tts_settings(event.chat_id)
        voice = settings.get("voice", "ksenia")

        test_phrases = [
            "Привет! Я Карина, твой персональный помощник.",
            f"Как я звучу? Мой голос — {voice}.",
            "Надеюсь, тебе нравится мой голос!",
        ]

        import random
        test_text = random.choice(test_phrases)

        try:
            audio_data = await text_to_speech(test_text, voice=voice)

            # Отправляем голосовое
            await client.send_voice(event.chat_id, audio_data)

        except Exception as e:
            logger.error(f"TTS test error: {e}")
            await event.respond(f"❌ Ошибка: {e}")

        raise events.StopPropagation

    @client.on(events.NewMessage(pattern='/ttsstats'))
    async def ttsstats_handler(event):
        """Скилл: Статистика TTS (для админа)"""
        logger.info(f"📩 /ttsstats от пользователя {event.chat_id}")

        from brains.tts import get_tts_stats, get_available_voices

        # Проверка на админа (по ID)
        from brains.config import MY_ID
        if event.chat_id != MY_ID:
            await event.respond("❌ Эта команда доступна только администратору.")
            raise events.StopPropagation

        stats = await get_tts_stats()
        voices = get_available_voices()

        message = f"""
📊 **Статистика TTS**

👥 Пользователи:
• Всего: {stats['total_users']}
• С включенным TTS: {stats['enabled_users']}

🎭 Голоса:
"""
        for voice_id, count in stats.get('voices', {}).items():
            voice_name = next((v['name'] for v in voices if v['id'] == voice_id), voice_id)
            message += f"• {voice_name}: {count}\n"

        if not stats.get('voices'):
            message += "• Пока нет данных\n"

        await event.respond(message)
        raise events.StopPropagation

    @client.on(events.NewMessage(incoming=True))
    async def chat_handler(event):
        """Интеллектуальное общение (текст + голос + фото) + Обработка напоминаний"""
        if not event.text and not event.photo and not event.voice:
            return

        logger.info(f"📩 ВХОДЯЩЕЕ: от {event.chat_id} | Текст: {event.text[:50] if event.text else 'Медиа'}")

        # ========== ОБРАБОТКА ФОТО ==========
        if event.photo or (event.document and event.document.mime_type.startswith('image/')):
            logger.info(f"🖼️ Фото получено от {event.chat_id}")
            if not event.is_private:
                logger.info("⚠️ Пропуск (не личный чат)")
                return

            # Скачиваем фото
            photo_path = await event.download_media(file="temp/vision/photo_{}.jpg".format(datetime.now().strftime('%Y%m%d_%H%M%S')))
            
            if photo_path:
                try:
                    # Отправляем статус "думает"
                    async with client.action(event.chat_id, 'typing'):
                        # Анализируем фото
                        from brains.vision import analyze_image

                        # Определяем тип анализа по контексту
                        prompt = "Детально опиши что на этом изображении. Если есть текст — распиши его полностью."

                        result = await analyze_image(photo_path, prompt, user_id=event.chat_id)

                        if result.get("success"):
                            # Формируем ответ
                            response = f"🖼️ **Анализ изображения:**\n\n{result['description']}"

                            # Если есть текст — добавляем
                            if result.get("text_content"):
                                response += "\n\n📝 **Распознанный текст:**\n_Карина может запомнить важную информацию из этого текста. Попроси меня!_"

                            await send_with_typewriter(event, response)
                        else:
                            await event.respond(f"❌ Не удалось проанализировать фото: {result.get('error', 'Неизвестная ошибка')}")

                except Exception as e:
                    logger.error(f"Photo analysis error: {e}")
                    await event.respond("❌ Ошибка при анализе фото. Попробуй ещё раз!")
                finally:
                    # Удаляем временный файл
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                
                raise events.StopPropagation

        # ========== ОБРАБОТКА ГОЛОСА ==========
        is_voice_message = False
        
        if event.voice or event.audio:
            logger.info(f"🎤 Голосовое сообщение от {event.chat_id}")
            if not event.is_private:
                logger.info("⚠️ Пропуск (не личный чат)")
                return

            is_voice_message = True
            
            async with client.action(event.chat_id, 'record-audio'):
                path = await event.download_media(file="voice_msg.ogg")
                text = await transcribe_voice(path)
                if os.path.exists(path): os.remove(path)

                if not text:
                    await event.reply("Ой, я не смогла разобрать, что ты сказал... 🎤")
                    return

                event.text = text
                logger.info(f"🎤 Голос расшифрован: {text}")

        if not event.text:
            return

        if event.text.startswith('/'):
            logger.info(f"⚡️ Пропуск команды в чат-хендлере: {event.text.split()[0]}")
            return

        # 🔔 ПРОВЕРКА НАПОМИНАНИЙ
        
        # 1. Подтверждение здоровья (только если есть активное напоминание на сегодня)
        today_health_id = f"health_{datetime.now().strftime('%Y%m%d')}"
        is_waiting_health = False
        if today_health_id in reminder_manager.reminders:
            r = reminder_manager.reminders[today_health_id]
            if r.is_active and not r.is_confirmed:
                is_waiting_health = True

        if is_waiting_health and reminder_manager.is_health_confirmation(event.text):
            logger.info(f"✅ Подтверждение здоровья от {event.chat_id}")
            await reminder_manager.confirm_reminder(today_health_id)
            await confirm_health()
            await save_health_record(True)  # Сохраняем в базу!
            await event.respond(random.choice([
                "Умничка! 🥰",
                "Так держать! 👍",
                "Я спокойна. 😊",
                "Молодец! ❤️"
            ]))
            return
        
        # 2. Отсрочка напоминания
        if reminder_manager.is_snooze_request(event.text):
            minutes = reminder_manager.parse_snooze_command(event.text)
            if minutes:
                # Ищем активное напоминание
                for rid, reminder in reminder_manager.reminders.items():
                    if reminder.is_active and not reminder.is_confirmed:
                        await reminder_manager.snooze_reminder(rid, minutes)
                        await event.respond(f"⏰ Хорошо, напомню через {minutes} мин!")
                        return
        
        # 3. Пропуск напоминания
        if reminder_manager.is_skip_request(event.text):
            # Проверяем, есть ли что пропускать
            has_active = any(r.is_active and not r.is_confirmed for r in reminder_manager.reminders.values())
            if has_active:
                logger.info(f"⏭️ Пропуск напоминания от {event.chat_id}")
                await event.respond("Хорошо, пропускаем. Но я ещё напомню! 😉")
                return

        if event.is_private:
            logger.info(f"💬 Обработка сообщения в ЛС: {event.text[:30]}...")
            
            # Проверка что ещё не отвечали на это сообщение
            if hasattr(event, '_responded') and event._responded:
                logger.debug("⚠️ Пропуск (уже отвечали)")
                return
            
            event._responded = True

            # 1. Включаем статус "Карина печатает..." в шапке Telegram
            async with client.action(event.chat_id, 'typing'):
                # 2. ИИ думает (пока он думает, висит статус "печатает")
                response = await ask_karina(event.text, chat_id=event.chat_id)
                logger.info(f"💬 Ответ: {response[:50] if response else 'None'}...")

            # 3. Выводим текст с эффектом печатной машинки
            await send_with_typewriter(event, response)
        else:
            logger.info("⚠️ Пропуск (не личный чат)")
