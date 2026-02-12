import os
import asyncio
import logging
import sys
from quart import Quart
from telethon import TelegramClient, functions, types, events
from telethon.sessions import StringSession
from datetime import datetime, timezone, timedelta

# Настройка логирования: выводим в stdout, чтобы Railway не считал это ошибками
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Приглушаем шум от самой библиотеки Telethon
logging.getLogger('telethon').setLevel(logging.WARNING)

app = Quart(__name__)

# Ключи из переменных окружения
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session_string = os.environ['SESSION_STRING']
target_user_id = int(os.environ.get('TARGET_USER_ID', 0))
# ID чата для уведомлений (твой ID или ID чата с Кариной)
notification_chat_id = int(os.environ.get('NOTIFICATION_CHAT_ID', 0))

client = TelegramClient(StringSession(session_string), api_id, api_hash)

# Кеш сообщений для лога удалений {msg_id: text}
message_cache = {}
# Храним состояние, чтобы не дублировать действия
current_state = None
last_notification_date = None # 'YYYY-MM-DD'
last_notification_type = None # 'morning' или 'evening'

# Твои document_id (Убедись, что это Custom Emoji ID)
emoji_map = {
    'morning': 5395463497783983254,
    'day': 4927197721900614739,
    'evening': 5377535110289576661,
    'night': 5247100325059370738,
    'breakfast': 5913264639025615311,
    'transit': 5246743378917334735,
    'weekend': 4906978012303458988
}

@client.on(events.NewMessage(from_users=target_user_id))
async def cache_handler(event):
    if event.message.text:
        message_cache[event.message.id] = event.message.text
        if len(message_cache) > 500:
            oldest_key = next(iter(message_cache))
            del message_cache[oldest_key]

@client.on(events.MessageDeleted())
async def delete_handler(event):
    for msg_id in event.deleted_ids:
        if msg_id in message_cache:
            original_text = message_cache[msg_id]
            try:
                await client.send_message(
                    'me',
                    f"🗑 **Удалено сообщение от {target_user_id}:**\n\n{original_text}"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления об удалении: {e}")
            finally:
                del message_cache[msg_id]

async def update_status(state: str):
    global current_state
    
    if state == current_state:
        return

    if state not in emoji_map:
        logger.error(f"Неизвестное состояние: {state}")
        return
    
    doc_id = emoji_map[state]
    
    try:
        await client(functions.account.UpdateEmojiStatusRequest(
            emoji_status=types.EmojiStatus(document_id=doc_id)
        ))
        logger.info(f"✅ Статус успешно изменён на {state} (ID: {doc_id})")
        current_state = state
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении статуса ({state}, ID: {doc_id}): {e}")

async def periodic_update():
    global last_notification_date, last_notification_type
    moscow_tz = timezone(timedelta(hours=3))
    
    while True:
        try:
            now = datetime.now(moscow_tz)
            hour = now.hour
            minute = now.minute
            weekday = now.weekday()
            today_str = now.strftime('%Y-%m-%d')

            # --- Логика эмодзи-статуса ---
            if weekday >= 5:
                state = 'weekend'
            else:
                time_min = hour * 60 + minute
                if 420 <= time_min < 430: # 07:00–07:10
                    state = 'breakfast'
                elif (430 <= time_min < 480) or (1020 <= time_min < 1080): # 07:10–08:00 или 17:00–18:00
                    state = 'transit'
                elif 6 <= hour < 12:
                    state = 'morning'
                elif 12 <= hour < 18:
                    state = 'day'
                elif 18 <= hour < 22:
                    state = 'evening'
                else:
                    state = 'night'

            await update_status(state)

            # --- Логика уведомлений ассистента ---
            if notification_chat_id != 0:
                # Утреннее приветствие (08:10)
                if hour == 8 and 10 <= minute < 15:
                    if last_notification_date != today_str or last_notification_type != 'morning':
                        try:
                            await client.send_message(
                                notification_chat_id,
                                "☀️ **Доброе утро!**\nПора начинать рабочий день. Желаю продуктивности и отличного настроения! 🚀"
                            )
                            last_notification_date = today_str
                            last_notification_type = 'morning'
                            logger.info("📢 Отправлено утреннее приветствие")
                        except Exception as e:
                            logger.error(f"Ошибка при отправке утреннего уведомления: {e}")

                # Конец дня + прогрев (16:45)
                elif hour == 16 and 45 <= minute < 50:
                    if last_notification_date != today_str or last_notification_type != 'evening':
                        try:
                            await client.send_message(
                                notification_chat_id,
                                "🏢 **Рабочий день подходит к концу!**\nПора закругляться и уходить домой. Не забудь **завести и прогреть машину**! 🚗💨"
                            )
                            last_notification_date = today_str
                            last_notification_type = 'evening'
                            logger.info("📢 Отправлено вечернее уведомление")
                        except Exception as e:
                            logger.error(f"Ошибка при отправке вечернего уведомления: {e}")

        except Exception as e:
            logger.error(f"Ошибка в цикле обновления: {e}")

        await asyncio.sleep(60) # Уменьшил интервал до 1 минуты для точности уведомлений

async def get_current_emoji_id():
    try:
        me = await client.get_me()
        if me.emoji_status:
            logger.info(f"🔍 Текущий ID вашего эмодзи-статуса: {me.emoji_status.document_id}")
        else:
            logger.info("🔍 У вас сейчас не установлен эмодзи-статус.")
    except Exception:
        pass

@app.before_serving
async def startup():
    await client.connect()
    if not await client.is_user_authorized():
        logger.error("Сессия не авторизована!")
        raise RuntimeError("Сессия не авторизована! Проверь SESSION_STRING")
    
    logger.info("🚀 Telethon клиент успешно подключён и авторизован")
    await get_current_emoji_id()
    asyncio.create_task(periodic_update())

@client.on(events.NewMessage(chats='me'))
async def discovery_handler(event):
    if event.message.text and event.message.text.lower().startswith('id'):
        if event.message.entities:
            found = False
            for ent in event.message.entities:
                if isinstance(ent, types.MessageEntityCustomEmoji):
                    await event.reply(f"Код для emoji_map:\n<code>{ent.document_id}</code>")
                    found = True
            if not found:
                await event.reply("В этом сообщении не найдено кастомных эмодзи.")

@app.after_serving
async def shutdown():
    await client.disconnect()
    logger.info("👋 Telethon клиент отключён")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
