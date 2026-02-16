import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from telethon import functions, types
from brains.config import EMOJI_MAP, MY_ID
from brains.weather import get_weather
from brains.news import get_latest_news
from auras.phrases import (
    BIO_PHRASES, 
    MORNING_GREETINGS, 
    TIME_MANAGEMENT_ADVICES,
    WORK_LIFE_BALANCE_PHRASES,
    HEALTH_REMINDERS,
    HEALTH_SCOLDING
)

logger = logging.getLogger(__name__)

class AuraState:
    def __init__(self):
        self.current_emoji_state = None
        self.last_notif_date = None
        self.last_notif_type = None
        self.last_health_notif_date = None
        self.health_reminder_time = None
        self.is_health_confirmed = True
        self.is_awake = False
        self.last_advice_hour = -1
        self.last_overwork_check_date = None
        self.remaining_bio_phrases = []
        self.last_bio_hour = -1

state = AuraState()

async def update_emoji_aura(user_client):
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour, minute, weekday = now.hour, now.minute, now.weekday()
    time_min = hour * 60 + minute
    
    # Логика определения состояния (упрощена для наглядности)
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
            await user_client(functions.account.UpdateEmojiStatusRequest(
                emoji_status=types.EmojiStatus(document_id=emoji_id) if emoji_id else types.EmojiStatusEmpty()
            ))
            state.current_emoji_state = current
            logger.info(f"✨ Аура: статус изменен на {current}")
        except Exception as e:
            logger.error(f"❌ Ошибка смены статуса: {e}")

async def health_aura(karina_client):
    """Контроль здоровья (уколы)"""
    if not karina_client or not MY_ID: return
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    today = now.strftime('%Y-%m-%d')

    # Напоминание в 22:00
    if now.hour == 22 and 0 <= now.minute < 5:
        if state.last_health_notif_date != today:
            msg = random.choice(HEALTH_REMINDERS) + "\n\n*(Напиши 'сделал', когда закончишь!)*"
            await karina_client.send_message(MY_ID, msg)
            state.last_health_notif_date = today
            state.health_reminder_time = now
            state.is_health_confirmed = False

    # Ворчание через 10 минут
    if not state.is_health_confirmed and state.health_reminder_time:
        if (now - state.health_reminder_time).total_seconds() >= 600:
            await karina_client.send_message(MY_ID, random.choice(HEALTH_SCOLDING))
            state.health_reminder_time = now # Сброс таймера для следующего ворчания

async def confirm_health():
    state.is_health_confirmed = True
    logger.info("✅ Здоровье: Подтверждено пользователем.")

async def start_auras(user_client, karina_client):
    """Главный цикл фоновых задач"""
    while True:
        try:
            await update_emoji_aura(user_client)
            await health_aura(karina_client)
            # Здесь можно добавить другие ауры (bio, news, и т.д.)
        except Exception as e:
            logger.error(f" Ошибка в цикле Аур: {e}")
        await asyncio.sleep(60)
