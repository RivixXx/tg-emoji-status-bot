from telethon import TelegramClient
from telethon.sessions import StringSession
from brains.config import API_ID, API_HASH, USER_SESSION, KARINA_TOKEN

# Клиент UserBot (твой аккаунт)
user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)

# Клиент Karina (Бот)
karina_client = None
if KARINA_TOKEN:
    karina_client = TelegramClient('karina_bot_session', API_ID, API_HASH)
