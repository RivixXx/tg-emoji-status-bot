import os
import asyncio
from quart import Quart
from telethon import TelegramClient, functions, types, events
from telethon.sessions import StringSession
from datetime import datetime, timezone, timedelta

app = Quart(__name__)

# Ключи из переменных окружения Railway
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session_string = os.environ['SESSION_STRING']
target_user_id = int(os.environ.get('TARGET_USER_ID', 0))

client = TelegramClient(StringSession(session_string), api_id, api_hash)

# Кеш сообщений для лога удалений {msg_id: text}
message_cache = {}

# Твои document_id (оставил как есть)
# ... (остальные переменные)

@client.on(events.NewMessage(from_users=target_user_id))
async def cache_handler(event):
    if event.message.text:
        message_cache[event.message.id] = event.message.text
        # Ограничиваем кеш 500 сообщениями
        if len(message_cache) > 500:
            oldest_key = next(iter(message_cache))
            del message_cache[oldest_key]

@client.on(events.MessageDeleted())
async def delete_handler(event):
    for msg_id in event.deleted_ids:
        if msg_id in message_cache:
            original_text = message_cache[msg_id]
            await client.send_message(
                'me',
                f"🗑 **Удалено сообщение от {target_user_id}:**\n\n{original_text}"
            )
            del message_cache[msg_id]

async def update_status(state: str):
    if state not in emoji_map:
        raise ValueError(f"Неизвестное состояние: {state}")
    
    doc_id = emoji_map[state]
    
    await client(functions.account.UpdateEmojiStatusRequest(
        emoji_status=types.EmojiStatus(document_id=doc_id)
    ))
    print(f"Статус изменён на {state} (doc_id={doc_id})")

async def periodic_update():
    moscow_tz = timezone(timedelta(hours=3))
    while True:
        now = datetime.now(moscow_tz)               # время МСК (UTC+3)
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()               # 0 = понедельник, 6 = воскресенье

        if weekday >= 5:                      # суббота + воскресенье
            state = 'weekend'
        else:
            time_min = hour * 60 + minute
            if 420 <= time_min < 430:         # 07:00–07:10
                state = 'breakfast'
            elif (430 <= time_min < 480) or (1020 <= time_min < 1080):  # 07:10–08:00 или 17:00–18:00
                state = 'transit'
            elif 6 <= hour < 12:
                state = 'morning'
            elif 12 <= hour < 18:
                state = 'day'
            elif 18 <= hour < 22:
                state = 'evening'
            else:
                state = 'night'

        try:
            await update_status(state)
        except Exception as e:
            print(f"Ошибка при обновлении статуса: {e}")

        await asyncio.sleep(600)              # 10 минут

@app.before_serving
async def startup():
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Сессия не авторизована! Проверь SESSION_STRING в переменных Railway")
    print("Telethon клиент успешно подключён и авторизован")
    
    # Запускаем фоновую задачу один раз при старте
    asyncio.create_task(periodic_update())

@app.after_serving
async def shutdown():
    await client.disconnect()
    print("Telethon клиент отключён")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
