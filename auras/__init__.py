import asyncio
import logging
import random
import os
from datetime import datetime, timezone, timedelta
from telethon import functions, types
from telethon.errors import PersistentTimestampOutdatedError
from brains.config import EMOJI_MAP, MY_ID
from brains.weather import get_weather
from brains.news import get_latest_news
from brains.employees import get_todays_birthdays, generate_birthday_card
from brains.ai import ask_karina
from brains.reminder_generator import generate_aura_phrase
from brains.reminders import reminder_manager, ReminderType, Reminder
from auras.phrases import (
    BIO_PHRASES,
    MORNING_GREETINGS,
    TIME_MANAGEMENT_ADVICES,
    WORK_LIFE_BALANCE_PHRASES
)

logger = logging.getLogger(__name__)

class AuraState:
    def __init__(self):
        self.current_emoji_state = None
        self.last_notif_date = None
        self.last_notif_type = None
        self.is_health_confirmed = True
        self.is_awake = False
        self.last_advice_hour = -1
        self.last_overwork_check_date = None
        self.remaining_bio_phrases = []
        self.last_bio_date = None

state = AuraState()

async def update_emoji_aura(user_client):
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour, minute, weekday = now.hour, now.minute, now.weekday()
    time_min = hour * 60 + minute
    
    # Логика определения состояния
    if weekday < 5:
        if time_min < 420: current = 'sleep'
        elif time_min < 1020: current = 'work'
        elif time_min < 1380: current = 'freetime'
        else: current = 'sleep'
    else:
        current = 'weekend' if 540 < time_min < 1380 else 'sleep'
    
    if current != state.current_emoji_state and user_client.is_connected():
        emoji_id = EMOJI_MAP.get(current)
        try:
            logger.info(f"🔄 Попытка смены эмодзи-статуса на {current} (ID: {emoji_id})")
            # Добавляем таймаут, чтобы не вешать цикл
            await asyncio.wait_for(
                user_client(functions.account.UpdateEmojiStatusRequest(
                    emoji_status=types.EmojiStatus(document_id=emoji_id) if emoji_id else types.EmojiStatusEmpty()
                )),
                timeout=15
            )
            logger.info(f"✨ Аура: статус изменен на {current}")
            state.current_emoji_state = current
        except asyncio.TimeoutError:
            logger.warning(f"⏳ Тайм-аут при смене статуса на {current}. Telegram не отвечает.")
        except Exception as e:
            logger.error(f"❌ Ошибка смены статуса ({current}): {e}")

async def update_bio_aura(user_client):
    """Динамическое БИО в рабочее время"""
    if not user_client.is_connected(): return
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    today = now.strftime('%Y-%m-%d')
    
    # Только в будни с 9 до 18
    if now.weekday() < 5 and 9 <= now.hour < 18:
        if state.last_bio_date != today:
            logger.info("🎨 Аура: Генерация нового БИО...")
            try:
                # Генерация фразы через ИИ тоже с таймаутом
                new_bio = await asyncio.wait_for(generate_aura_phrase("bio"), timeout=20)
                if not new_bio:
                    new_bio = random.choice(BIO_PHRASES)
                
                await asyncio.wait_for(
                    user_client(functions.account.UpdateProfileRequest(about=new_bio)),
                    timeout=15
                )
                state.last_bio_date = today
                logger.info(f"✅ Аура: БИО обновлено: {new_bio}")
            except asyncio.TimeoutError:
                logger.warning("⏳ Тайм-аут при обновлении БИО")
            except Exception as e:
                logger.error(f"❌ Ошибка обновления БИО: {e}")

async def confirm_health():
    state.is_health_confirmed = True
    logger.info("✅ Здоровье: Подтверждено пользователем.")

async def check_birthdays_task(karina_client):
    """Ежедневная проверка дней рождения сотрудников (8:15)"""
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)

    if now.hour == 8 and now.minute == 15:
        logger.info("🎂 Проверка дней рождения сотрудников...")
        try:
            celebrants = await get_todays_birthdays()
            for emp in celebrants:
                logger.info(f"🥳 Сегодня день рождения у {emp['full_name']}!")
                prompt = f"Напиши поздравление для {emp['full_name']}. Учти: {emp['characteristics']}. Стиль: Карина AI."
                greeting_text = await asyncio.wait_for(ask_karina(prompt), timeout=30)
                
                GROUP_ID = os.environ.get('TEAM_GROUP_ID')
                if GROUP_ID and greeting_text:
                    await karina_client.send_message(int(GROUP_ID), f"🥳 **С ДНЁМ РОЖДЕНИЯ!** 🎂\n\n{greeting_text}")
        except Exception as e:
            logger.error(f"❌ Ошибка в задаче дней рождения: {e}")


async def check_calendar_reminders_task(karina_client):
    """
    Утренняя проверка календаря на сегодня (7:00)
    Создаёт напоминания за 15 минут до каждого события
    """
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)

    # Запускаем в 7:00 утра
    if now.hour == 7 and now.minute == 0:
        logger.info("📅 Утренняя проверка календаря на сегодня...")
        
        from brains.calendar import get_today_calendar_events
        
        # Получаем события на сегодня
        try:
            events = await asyncio.wait_for(get_today_calendar_events(), timeout=30)
            
            if not events:
                logger.info("📅 На сегодня событий нет")
                return
            
            created_count = 0
            for event in events:
                event_time = event['start']
                reminder_time = event_time - timedelta(minutes=15)
                
                if reminder_time <= now: continue
                
                reminder_id = f"meeting_{int(event_time.timestamp())}"
                if reminder_id in reminder_manager.reminders: continue
                
                reminder = Reminder(
                    id=reminder_id,
                    type=ReminderType.MEETING,
                    message=f"Встреча: {event['summary']}",
                    scheduled_time=reminder_time,
                    escalate_after=[5, 10],
                    context={
                        "title": event['summary'],
                        "minutes": 15,
                        "source": "auto_morning_check",
                        "event_start": event_time.isoformat(),
                        "calendar": event.get('calendar', '')
                    }
                )
                
                await reminder_manager.add_reminder(reminder)
                created_count += 1
                logger.info(f"🔔 Создано напоминание: {event['summary']} на {reminder_time.strftime('%H:%M')}")
            
            logger.info(f"✅ Проверка завершена. Создано напоминаний: {created_count}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки календаря: {e}")


async def check_overwork_task(karina_client, user_id: int):
    """
    Вечерняя проверка на переработки (21:00)
    """
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)

    if now.hour == 21 and now.minute == 0:
        from brains.productivity import check_overwork_alert, get_overwork_days
        try:
            alert = await asyncio.wait_for(check_overwork_alert(user_id), timeout=20)
            if alert:
                await karina_client.send_message(user_id, f"😟 **Карина беспокоится...**\n\n{alert}\n\nПожалуйста, позаботься об отдыхе! 💙")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки переработок: {e}")


async def start_auras(user_client, karina_client):
    """Главный цикл фоновых задач (безопасный)"""
    while True:
        try:
            # Запускаем задачи параллельно, чтобы они не ждали друг друга
            await asyncio.gather(
                update_emoji_aura(user_client),
                update_bio_aura(user_client),
                check_birthdays_task(karina_client),
                check_calendar_reminders_task(karina_client),
                check_overwork_task(karina_client, MY_ID),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"⚠️ Критическая ошибка в главном цикле аур: {e}")
        
        await asyncio.sleep(60)
