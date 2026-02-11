import os
import asyncio
from quart import Quart, request, jsonify
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon import functions, types

app = Quart(__name__)

# Переменные окружения
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session_string = os.environ['SESSION_STRING']

client = TelegramClient(StringSession(session_string), api_id, api_hash)

emoji_map = {
    'morning': '🌅',
    'day': '☀️',
    'evening': '🌆',
    'night': '🌙',
    'breakfast': '🍳',
    'transit': '🚗',
    'weekend': '🏖️'
}

emoji_cache = {}

async def get_document_id(emoji_unicode: str) -> int:
    if emoji_unicode in emoji_cache:
        return emoji_cache[emoji_unicode]
    result = await client(functions.messages.SearchCustomEmojiRequest(emojitext=emoji_unicode, hash=0))
    if result.documents:
        doc_id = result.documents[0].id
        emoji_cache[emoji_unicode] = doc_id
        return doc_id
    raise ValueError(f"Не найден emoji: {emoji_unicode}")

async def update_status(state: str):
    if state not in emoji_map:
        raise ValueError(f"Неизвестное состояние: {state}")
    emoji = emoji_map[state]
    doc_id = await get_document_id(emoji)
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
