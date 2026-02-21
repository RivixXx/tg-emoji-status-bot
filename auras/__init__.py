import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from telethon import functions, types
from telethon.errors import PersistentTimestampOutdatedError
from brains.config import EMOJI_MAP, MY_ID
from brains.weather import get_weather
from brains.news import get_latest_news
from brains.employees import get_todays_birthdays, generate_birthday_card
from brains.ai import ask_karina
from brains.reminder_generator import generate_aura_phrase
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
            logger.info(f"🔄 Попытка смены эмодзи-статуса на {current} (ID: {emoji_id})")
            await user_client(functions.account.UpdateEmojiStatusRequest(
                emoji_status=types.EmojiStatus(document_id=emoji_id) if emoji_id else types.EmojiStatusEmpty()
            ))
            logger.info(f"✨ Аура: статус изменен на {current}")
        except Exception as e:
            logger.error(f"❌ Ошибка смены статуса ({current}): {e}")
        finally:
            # Помечаем состояние как установленное (даже если была ошибка), 
            # чтобы не спамить попытками каждую минуту
            state.current_emoji_state = current

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
            new_bio = await generate_aura_phrase("bio")
            if not new_bio:
                new_bio = random.choice(BIO_PHRASES)
            
            try:
                await user_client(functions.account.UpdateProfileRequest(about=new_bio))
                state.last_bio_date = today
                logger.info(f"✅ Аура: БИО обновлено: {new_bio}")
            except Exception as e:
                logger.error(f"❌ Ошибка обновления БИО: {e}")

async def confirm_health():
    state.is_health_confirmed = True
    logger.info("✅ Здоровье: Подтверждено пользователем.")

async def check_birthdays_task(karina_client):
    """Ежедневная проверка дней рождения сотрудников"""
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    
    # Запускаем один раз в день, например в 9:05 утра
    if now.hour == 9 and now.minute == 5:
        logger.info("🎂 Проверка дней рождения сотрудников...")
        celebrants = await get_todays_birthdays()
        
        for emp in celebrants:
            logger.info(f"🥳 Сегодня день рождения у {emp['full_name']}!")
            
            # 1. Генерируем поздравление через AI
            prompt = f"Напиши теплое, оригинальное корпоративное поздравление для сотрудника по имени {emp['full_name']}. Учти его качества: {emp['characteristics']}. Стиль: дружелюбная Карина AI."
            greeting_text = await ask_karina(prompt)
            
            # 2. Генерируем открытку (пока логируем)
            await generate_birthday_card(emp)
            
            # 3. Отправляем в группу (здесь нужен ID вашей группы)
            GROUP_ID = os.environ.get('TEAM_GROUP_ID')
            if GROUP_ID:
                try:
                    await karina_client.send_message(int(GROUP_ID), f"🥳 **С ДНЁМ РОЖДЕНИЯ!** 🎂\n\n{greeting_text}")
                    logger.info(f"✅ Поздравление для {emp['full_name']} отправлено в группу.")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки поздравления: {e}")

async def start_auras(user_client, karina_client):
    """Главный цикл фоновых задач"""
    reconnect_attempts = 0
    max_reconnect_attempts = 5
    
    while True:
        try:
            await update_emoji_aura(user_client)
            await update_bio_aura(user_client)
            await check_birthdays_task(karina_client)
            
            reconnect_attempts = 0  # Сброс счётчика ошибок при успешной итерации
            
        except PersistentTimestampOutdatedError as e:
            logger.warning(f"⚠️ Telegram: рассинхронизация timestamp (попытка {reconnect_attempts + 1}/{max_reconnect_attempts})")
            reconnect_attempts += 1
            
            if reconnect_attempts >= max_reconnect_attempts:
                logger.error("❌ Превышено количество попыток переподключения. Требуется рестарт.")
                await asyncio.sleep(300)
                reconnect_attempts = 0
            else:
                try:
                    logger.info("🔄 Переподключение к Telegram...")
                    if user_client.is_connected():
                        await user_client.disconnect()
                    await asyncio.sleep(5)
                    await user_client.connect()
                    logger.info("✅ Переподключение успешно.")
                except Exception as reconnect_err:
                    logger.error(f"❌ Ошибка переподключения: {reconnect_err}")
                    await asyncio.sleep(30)
                    
        except Exception as e:
            logger.error(f" Ошибка в цикле Аур: {e}")
            await asyncio.sleep(60)
            
        await asyncio.sleep(60)
