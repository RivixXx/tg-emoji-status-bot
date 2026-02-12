import os
import asyncio
import logging
import sys
from quart import Quart
from telethon import TelegramClient, functions, types, events
from telethon.sessions import StringSession
from datetime import datetime, timezone, timedelta

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)
logging.getLogger('telethon').setLevel(logging.WARNING)

app = Quart(__name__)

# --- Конфигурация ---
API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
USER_SESSION = os.environ['SESSION_STRING']
KARINA_TOKEN = os.environ.get('KARINA_BOT_TOKEN') # Токен от BotFather
TARGET_USER_ID = int(os.environ.get('TARGET_USER_ID', 0))
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0)) # Твой личный ID для уведомлений

# Инициализируем клиентов (без подключения)
user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)
karina_client = None
if KARINA_TOKEN:
    karina_client = TelegramClient('karina_bot', API_ID, API_HASH)

# --- Состояние ---
message_cache = {}
current_emoji_state = None
last_notif_date = None
last_notif_type = None

# Эмодзи-статусы
emoji_map = {
    'morning': 5395463497783983254,
    'day': 4927197721900614739,
    'evening': 5219748856626973291,
    'night': 5247100325059370738,
    'breakfast': 5913264639025615311,
    'transit': 5246743378917334735,
    'weekend': 4906978012303458988
}

# --- Логика UserBot (Твой аккаунт) ---

@user_client.on(events.NewMessage(from_users=TARGET_USER_ID))
async def cache_handler(event):
    if event.message.text:
        message_cache[event.message.id] = event.message.text
        if len(message_cache) > 500:
            del message_cache[next(iter(message_cache))]

@user_client.on(events.MessageDeleted())
async def delete_handler(event):
    for msg_id in event.deleted_ids:
        if msg_id in message_cache:
            original_text = message_cache[msg_id]
            try:
                await user_client.send_message('me', f"🗑 **Удалено сообщение от {TARGET_USER_ID}:**\n\n{original_text}")
            except Exception as e:
                logger.error(f"Ошибка лога удаления: {e}")
            finally:
                del message_cache[msg_id]

async def update_emoji_status(state: str):
    global current_emoji_state
    if state == current_emoji_state or state not in emoji_map:
        return
    
    try:
        await user_client(functions.account.UpdateEmojiStatusRequest(
            emoji_status=types.EmojiStatus(document_id=emoji_map[state])
        ))
        logger.info(f"✅ Статус аккаунта: {state}")
        current_emoji_state = state
    except Exception as e:
        logger.error(f"❌ Ошибка статуса: {e}")

# --- Логика Карины (Бот-ассистент) ---

async def send_karina_notification(text: str):
    if karina_client and MY_ID:
        try:
            await karina_client.send_message(MY_ID, text)
            logger.info("📢 Карина отправила уведомление")
        except Exception as e:
            logger.error(f"Карина не смогла написать: {e}")

# --- Общий цикл управления ---

async def brain_loop():
    global last_notif_date, last_notif_type
    moscow_tz = timezone(timedelta(hours=3))
    
    while True:
        try:
            now = datetime.now(moscow_tz)
            hour, minute, weekday = now.hour, now.minute, now.weekday()
            today_str = now.strftime('%Y-%m-%d')

            # 1. Обновление статуса (UserBot)
            if weekday >= 5: state = 'weekend'
            else:
                time_min = hour * 60 + minute
                if 420 <= time_min < 430: state = 'breakfast'
                elif (430 <= time_min < 480) or (1020 <= time_min < 1080): state = 'transit'
                elif 6 <= hour < 12: state = 'morning'
                elif 12 <= hour < 18: state = 'day'
                elif 18 <= hour < 22: state = 'evening'
                else: state = 'night'
            
            if user_client.is_connected():
                await update_emoji_status(state)

            # 2. Уведомления от Карины
            if karina_client and karina_client.is_connected():
                if hour == 8 and 10 <= minute < 15:
                    if last_notif_date != today_str or last_notif_type != 'morning':
                        await send_karina_notification("☀️ **Доброе утро!**\nПора начинать рабочий день. Желаю успехов! 🚀")
                        last_notif_date, last_notif_type = today_str, 'morning'

                elif hour == 16 and 45 <= minute < 50:
                    if last_notif_date != today_str or last_notif_type != 'evening':
                        await send_karina_notification("🏢 **Пора домой!**\nРабочий день окончен. Не забудь **прогреть машину**! 🚗💨")
                        last_notif_date, last_notif_type = today_str, 'evening'

        except Exception as e:
            logger.error(f"Ошибка в Brain Loop: {e}")
        await asyncio.sleep(60)

# --- Запуск ---

@app.before_serving
async def startup():
    # 1. Запускаем UserBot
    await user_client.connect()
    if not await user_client.is_user_authorized():
        logger.error("UserBot не авторизован! Проверь SESSION_STRING.")
        return
    
    # 2. Запускаем Карину
    if karina_client:
        await karina_client.start(bot_token=KARINA_TOKEN)
        
        # Регистрация обработчиков Карины после старта
        @karina_client.on(events.NewMessage(pattern='/start'))
        async def start_karina(event):
            await event.respond("Привет! Я Карина, твой личный ассистент. 😊")
            
        logger.info("🤖 Карина готова к работе!")

    logger.info("🚀 Вся система запущена")
    asyncio.create_task(brain_loop())

@app.after_serving
async def shutdown():
    if user_client:
        await user_client.disconnect()
    if karina_client:
        await karina_client.disconnect()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
