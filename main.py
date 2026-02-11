from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from flask import Flask, request
import asyncio
import os

app = Flask(__name__)

# Эти значения возьмём из переменных окружения Railway
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
session_string = os.environ['SESSION_STRING']

client = TelegramClient(StringSession(session_string), api_id, api_hash)

# Emoji для разных состояний (можно потом поменять)
emoji_map = {
    'morning': '☕',
    'day': '☀️',
    'evening': '🌆',
    'night': '🌙',
    'breakfast': '🍳',
    'transit': '🚗',
    'weekend': '🏖️'
}

emoji_cache = {}

async def get_document_id(emoji):
    if emoji in emoji_cache:
        return emoji_cache[emoji]
    result = await client(functions.messages.SearchCustomEmojiRequest(emojitext=emoji, hash=0))
    if result.documents:
        doc_id = result.documents[0].id
        emoji_cache[emoji] = doc_id
        return doc_id
    raise ValueError(f"Emoji {emoji} не найден")

async def set_status(state):
    emoji = emoji_map.get(state)
    if not emoji:
        return
    doc_id = await get_document_id(emoji)
    await client(functions.account.UpdateEmojiStatusRequest(
        emoji_status=types.EmojiStatus(document_id=doc_id)
    ))

@app.route('/update', methods=['POST'])
def update():
    data = request.get_json()
    state = data.get('state')
    if not state:
        return {'error': 'Нет state'}, 400
    try:
        asyncio.run(set_status(state))
        return {'ok': True}
    except Exception as e:
        return {'error': str(e)}, 500

if __name__ == '__main__':
    asyncio.run(client.start())
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
