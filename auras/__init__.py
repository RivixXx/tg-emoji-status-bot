import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from telethon import functions, types
from brains.config import EMOJI_MAP, MY_ID
from brains.weather import get_weather
from auras.phrases import (
    BIO_PHRASES, 
    MORNING_GREETINGS, 
    TIME_MANAGEMENT_ADVICES,
    WORK_LIFE_BALANCE_PHRASES
)

logger = logging.getLogger(__name__)

# Состояние для предотвращения повторов
_current_state = None
_last_notif_date = None
_last_notif_type = None
_is_awake = False  # Флаг пробуждения сегодня
_last_advice_hour = -1
_last_overwork_check_date = None  # Дата последней проверки на переработку

# Состояние для Био
_remaining_phrases = []
_last_bio_hour = -1

async def update_emoji_aura(user_client):
    """Аура автоматической смены эмодзи-статуса"""
    global _current_state
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour, minute, weekday = now.hour, now.minute, now.weekday()
    time_min = hour * 60 + minute
    
    if weekday < 5:  # Будни (Пн-Пт)
        if 0 <= time_min < 420: state = 'sleep'            # 00:00 - 07:00
        elif 420 <= time_min < 450: state = 'breakfast'    # 07:00 - 07:30
        elif 450 <= time_min < 480: state = 'transit'      # 07:30 - 08:00
        elif 480 <= time_min < 720: state = 'work'         # 08:00 - 12:00
        elif 720 <= time_min < 780: state = 'lunch'        # 12:00 - 13:00
        elif 780 <= time_min < 1020: state = 'work'        # 13:00 - 17:00
        elif 1020 <= time_min < 1080: state = 'transit'    # 17:00 - 18:00
        elif 1080 <= time_min < 1140: state = 'dinner'     # 18:00 - 19:00
        elif 1140 <= time_min < 1380: state = 'freetime'   # 19:00 - 23:00
        else: state = 'sleep'                              # 23:00 - 00:00
    else:  # Выходные (Сб-Вс)
        if 0 <= time_min < 540: state = 'sleep'            # 00:00 - 09:00
        elif 540 <= time_min < 720: state = 'morning'      # 09:00 - 12:00
        elif 720 <= time_min < 1080: state = 'day'         # 12:00 - 18:00
        elif 1080 <= time_min < 1380: state = 'evening'    # 18:00 - 23:00
        else: state = 'sleep'                              # 23:00 - 00:00
    
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

async def advice_aura(karina_client):
    """Аура советов по тайм-менеджменту"""
    global _last_advice_hour, _current_state
    if not karina_client or not MY_ID: return

    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour = now.hour

    # Даем совет не чаще чем раз в 4 часа и только в активное время
    if hour % 4 == 0 and hour != _last_advice_hour and 8 <= hour <= 22:
        state = _current_state
        if state in TIME_MANAGEMENT_ADVICES:
            advice = random.choice(TIME_MANAGEMENT_ADVICES[state])
            try:
                await karina_client.send_message(MY_ID, f"💡 **Совет по тайм-менеджменту:**\n\n{advice}")
                _last_advice_hour = hour
                logger.info(f"💡 Карина отправила совет для состояния: {state}")
            except Exception as e:
                logger.error(f"❌ Ошибка Ауры (Советы): {e}")

async def notifications_aura(karina_client, user_client):
    """Аура временных уведомлений Карины и детектор пробуждения"""
    global _last_notif_date, _last_notif_type, _is_awake
    if not karina_client or not MY_ID: return

    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    hour, minute, weekday = now.hour, now.minute, now.weekday()
    today_str = now.strftime('%Y-%m-%d')

    # Сброс флага пробуждения в полночь
    if hour == 0 and minute == 0:
        _is_awake = False

    # Детектор пробуждения (07:00 - 10:00)
    if 7 <= hour < 10 and not _is_awake:
        try:
            full_user = await user_client(functions.users.GetFullUserRequest(id='me'))
            status = full_user.users[0].status
            
            if isinstance(status, types.UserStatusOnline):
                _is_awake = True
                weather_info = await get_weather()
                
                category = random.choice(["energetic", "cozy"])
                base_msg = random.choice(MORNING_GREETINGS[category])
                
                weather_msg = ""
                if weather_info:
                    w_lower = weather_info.lower()
                    if any(x in w_lower for x in ["rain", "дождь", "осадки"]): w_type = "rain"
                    elif any(x in w_lower for x in ["clear", "ясно", "sun", "солн"]): w_type = "sunny"
                    elif any(x in w_lower for x in ["cloud", "облачно"]): w_type = "cloudy"
                    elif any(x in w_lower for x in ["snow", "снег", "cold", "холод", "мороз"]): w_type = "cold"
                    else: w_type = None
                    
                    if w_type:
                        weather_msg = f"\n\n{MORNING_GREETINGS['weather_dependent'][w_type]}"
                    weather_msg += f"\n\n🌤 **Погода сейчас:** {weather_info}"

                msg = f"✨ **О, ты проснулся!**\n\n{base_msg}{weather_msg}"
                await karina_client.send_message(MY_ID, msg)
                logger.info("🌞 Карина заметила пробуждение и отправила приветствие.")
                _last_notif_date, _last_notif_type = today_str, 'morning'
        except Exception as e:
            logger.error(f"❌ Ошибка в детекторе пробуждения: {e}")

    # Вечернее уведомление
    elif hour == 16 and 45 <= minute < 50:
        if _last_notif_date != today_str or _last_notif_type != 'evening':
            await karina_client.send_message(MY_ID, "🏢 **Пора домой!**\nРабочий день окончен. Не забудь **прогреть машину**! 🚗💨")
            _last_notif_date, _last_notif_type = today_str, 'evening'

    # Проверка на переработку (Пн-Пт, с 18:30 до 21:00)
    elif weekday < 5 and (hour == 18 and minute >= 30 or 19 <= hour < 21):
        global _last_overwork_check_date
        if _last_overwork_check_date != today_str:
            try:
                full_user = await user_client(functions.users.GetFullUserRequest(id='me'))
                if isinstance(full_user.users[0].status, types.UserStatusOnline):
                    msg = f"🧡 **Аура заботы:**\n\n{random.choice(WORK_LIFE_BALANCE_PHRASES)}"
                    await karina_client.send_message(MY_ID, msg)
                    _last_overwork_check_date = today_str
                    logger.info("🌙 Карина отправила напоминание об отдыхе.")
            except Exception as e:
                logger.error(f"❌ Ошибка в проверке переработки: {e}")

async def start_auras(user_client, karina_client):
    """Запуск всех фоновых процессов"""
    while True:
        try:
            await update_emoji_aura(user_client)
            await bio_aura(user_client)
            await advice_aura(karina_client)
            await notifications_aura(karina_client, user_client)
        except Exception as e:
            logger.error(f"Ошибка в основном цикле Аур: {e}")
        await asyncio.sleep(60)
