import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from telethon import functions, types
from brains.config import EMOJI_MAP, MY_ID
from brains.weather import get_weather
from auras.phrases import BIO_PHRASES

logger = logging.getLogger(__name__)

# Состояние для предотвращения повторов
_current_state = None
_last_notif_date = None
_last_notif_type = None

# Состояние для Био
_remaining_phrases = []
_last_bio_hour = -1

async def update_emoji_aura(user_client):
    """Аура автоматической смены эмодзи-статуса"""
    global _current_state
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour, minute, weekday = now.hour, now.minute, now.weekday()
    
    if weekday >= 5: 
        state = 'weekend'
    else:
        time_min = hour * 60 + minute
        if 420 <= time_min < 430: state = 'breakfast'
        elif (430 <= time_min < 480) or (1020 <= time_min < 1080): state = 'transit'
        elif 6 <= hour < 12: state = 'morning'
        elif 12 <= hour < 18: state = 'day'
        elif 18 <= hour < 22: state = 'evening'
        else: state = 'night'
    
    if state != _current_state and user_client.is_connected():
        emoji_id = EMOJI_MAP.get(state)
        try:
            if emoji_id:
                await user_client(functions.account.UpdateEmojiStatusRequest(
                    emoji_status=types.EmojiStatus(document_id=emoji_id)
                ))
                logger.info(f"✨ Аура: статус аккаунта изменен на {state} (ID: {emoji_id})")
            else:
                # Если ID нет в мапе, сбрасываем статус
                await user_client(functions.account.UpdateEmojiStatusRequest(
                    emoji_status=types.EmojiStatusEmpty()
                ))
                logger.info(f"✨ Аура: статус сброшен (состояние {state})")
            _current_state = state
        except Exception as e:
            logger.error(f"❌ Ошибка Ауры (статус {state}, ID {emoji_id}): {e}")
            # Чтобы не пытаться каждую минуту, если ID битый
            _current_state = state 

async def bio_aura(user_client):
    """Аура динамического БИО (Пн-Пт, 08:00-17:00)"""
    global _remaining_phrases, _last_bio_hour
    
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour, weekday = now.hour, now.weekday()

    if weekday < 5 and 8 <= hour <= 17:
        if hour != _last_bio_hour:
            if not _remaining_phrases:
                _remaining_phrases = BIO_PHRASES.copy()
                random.shuffle(_remaining_phrases)
                logger.info("🔄 Аура Био: Список фраз обновлен и перемешан.")

            new_bio = _remaining_phrases.pop()
            
            try:
                if user_client.is_connected():
                    await user_client(functions.account.UpdateProfileRequest(about=new_bio))
                    logger.info(f"📝 Аура Био: описание обновлено на: {new_bio}")
                    _last_bio_hour = hour
            except Exception as e:
                logger.error(f"❌ Ошибка Ауры (Био): {e}")

async def notifications_aura(karina_client):
    """Аура временных уведомлений Карины"""
    global _last_notif_date, _last_notif_type
    if not karina_client or not MY_ID: return

    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour, minute = now.hour, now.minute
    today_str = now.strftime('%Y-%m-%d')

    if hour == 8 and 10 <= minute < 15:
        if _last_notif_date != today_str or _last_notif_type != 'morning':
            weather_info = await get_weather()
            msg = "☀️ **Доброе утро!**\nПора начинать рабочий день. Желаю успехов! 🚀"
            if weather_info:
                msg += f"\n\n🌤 **Погода сегодня:** {weather_info}"
            
            await karina_client.send_message(MY_ID, msg)
            _last_notif_date, _last_notif_type = today_str, 'morning'

    elif hour == 16 and 45 <= minute < 50:
        if _last_notif_date != today_str or _last_notif_type != 'evening':
            await karina_client.send_message(MY_ID, "🏢 **Пора домой!**\nРабочий день окончен. Не забудь **прогреть машину**! 🚗💨")
            _last_notif_date, _last_notif_type = today_str, 'evening'

async def start_auras(user_client, karina_client):
    """Запуск всех фоновых процессов"""
    while True:
        try:
            await update_emoji_aura(user_client)
            await bio_aura(user_client)
            await notifications_aura(karina_client)
        except Exception as e:
            logger.error(f"Ошибка в основном цикле Аур: {e}")
        await asyncio.sleep(60)
