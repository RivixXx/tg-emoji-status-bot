import os
import asyncio
import asyncio
from quart import Quart, request, jsonify
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon import functions, types
from datetime import datetime

app = Quart(__name__)

# Переменные окружения
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session_string = os.environ['SESSION_STRING']

client = TelegramClient(StringSession(session_string), api_id, api_hash)

emoji_map = {
    'morning': 5395463497783983254,
    'day': 5362079447136610876,
    'evening': 5375447270852407733,
    'night': 5247100325059370738,
    'breakfast': 5913264639025615311,
    'transit': 5246743378917334735,
    'weekend': 4906978012303458988
    # 'morning': '☕️',
    # 'day': '👨‍💼',
    # 'evening': '👨‍💻',
    # 'night': '💤',
    # 'breakfast': '🫠',
    # 'transit': '👣',
    # 'weekend': '🏖️'
}

emoji_cache = {}

async def get_document_id(emoji_unicode: str) -> int:
    if emoji_unicode in emoji_cache:
        return emoji_cache[emoji_unicode]
    
    result = await client(functions.messages.SearchCustomEmojiRequest(
        emoticon=emoji_unicode,
        hash=0
    ))
    
    if result.document_id:
        doc_id = result.document_id[0]
        emoji_cache[emoji_unicode] = doc_id
        return doc_id
    else:
        raise ValueError(f"Custom emoji не найден для '{emoji_unicode}'. Возможно, эмодзи не поддерживается или требуется Premium.")

async def update_status(state: str):
    if state not in emoji_map:
        raise ValueError(f"Неизвестное состояние: {state}")
    
    doc_id = emoji_map[state]
    
    await client(functions.account.UpdateEmojiStatusRequest(
        emoji_status=types.EmojiStatus(document_id=doc_id)
    ))

@app.before_serving
async def startup():
    # Запускаем клиент без asyncio.run()
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Сессия не авторизована! Проверь SESSION_STRING")
    print("Telethon клиент подключён и авторизован")

@app.after_serving
async def shutdown():
    await client.disconnect()
    print("Telethon отключён")

@app.route('/update', methods=['POST'])
async def handle_update():
    data = await request.get_json()
    state = data.get('state')
    if not state:
        return jsonify({'error': 'Требуется поле "state"'}), 400
    try:
        await update_status(state)
        return jsonify({'status': 'updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

async def periodic_update():
    while True:
        now = datetime.utcnow()  # или .now() с timezone, если нужно
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()  # 0=понедельник ... 6=воскресенье

        if weekday >= 5:  # сб + вс
            state = 'weekend'
        else:
            time_min = hour * 60 + minute
            if 420 <= time_min < 430:     # 07:00-07:10
                state = 'breakfast'
            elif (430 <= time_min < 480) or (1020 <= time_min < 1080):  # 07:10-08:00 или 17:00-18:00
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
            print(f"Обновлён статус: {state}")
        except Exception as e:
            print(f"Ошибка обновления: {e}")

        await asyncio.sleep(600)  # 10 минут

@app.before_serving
async def startup():
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Сессия не авторизована!")
    print("Telethon клиент подключён и авторизован")
    
    # Запускаем фоновую задачу
    asyncio.create_task(periodic_update())
