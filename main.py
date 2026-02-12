import os
import asyncio
from quart import Quart
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from datetime import datetime, timezone, timedelta

app = Quart(__name__)

# Ключи из переменных окружения Railway
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session_string = os.environ['SESSION_STRING']

client = TelegramClient(StringSession(session_string), api_id, api_hash)

# Твои document_id (оставил как есть)
emoji_map = {
    'morning': 5395463497783983254,
    'day': 5362079447136610876,
    'evening': 5375447270852407733,
    'night': 5247100325059370738,
    'breakfast': 5913264639025615311,
    'transit': 5246743378917334735,
    'weekend': 4906978012303458988
}

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
