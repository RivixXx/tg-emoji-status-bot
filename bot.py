"""
KARINA AI — Telegram Bot
Минимальная рабочая версия
"""
import os
import logging
import sys
from telethon import TelegramClient, events, types, functions
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Загружаем конфиг
load_dotenv()

# Настройки
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('KARINA_BOT_TOKEN', '')
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0))
SESSION = os.environ.get('SESSION_STRING', '')
MISTRAL_KEY = os.environ.get('MISTRAL_API_KEY', '')

# Логирование
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка конфига
if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID, MISTRAL_KEY]):
    print("❌ ЗАПОЛНИТЕ .env ФАЙЛ!")
    print("Обязательно: API_ID, API_HASH, KARINA_BOT_TOKEN, MY_TELEGRAM_ID, MISTRAL_API_KEY")
    sys.exit(1)

# Клиенты
bot = TelegramClient('bot_session', API_ID, API_HASH)
user = TelegramClient(StringSession(SESSION), API_ID, API_HASH) if SESSION else None

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(e):
    await e.reply("👋 Привет! Я Карина.\n\nРаботаю нормально ✅")
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='/ping'))
async def ping_handler(e):
    await e.reply("🏓 Понг! Бот работает!")
    raise events.StopPropagation

@bot.on(events.NewMessage())
async def chat_handler(e):
    """Простой чат без ИИ для теста"""
    if e.sender_id == MY_ID:
        await e.reply(f"✅ Получила сообщение: {e.text[:50]}")
    raise events.StopPropagation

async def main():
    # Бот
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("✅ Бот запущен")
    
    # Команды
    await bot(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(),
        lang_code='ru',
        commands=[
            types.BotCommand('start', 'Запустить бота'),
            types.BotCommand('ping', 'Проверить связь')
        ]
    ))
    
    # Userbot (если есть сессия)
    if user:
        await user.start()
        logger.info("✅ UserBot запущен")
    
    logger.info("=" * 40)
    logger.info("🤖 KARINA BOT ГОТОВ К РАБОТЕ")
    logger.info("=" * 40)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
