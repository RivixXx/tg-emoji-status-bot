"""
Karina AI - Telegram Bot + Web Server
Запускает Telethon клиентов в отдельных потоках
"""
import os
import asyncio
import logging
import sys
import threading
from quart import Quart, jsonify, request
import hypercorn.asyncio
from hypercorn.config import Config
from telethon import functions, types, events, TelegramClient
from telethon.sessions import StringSession
from brains.config import API_ID, API_HASH, KARINA_TOKEN, USER_SESSION
from brains.memory import search_memories
from brains.calendar import get_upcoming_events, get_conflict_report
from brains.health import get_health_report_text, get_health_stats
from brains.emotions import get_emotion_state, set_emotion
from brains.news import get_latest_news
from brains.ai import ask_karina
from auras import state, start_auras

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# ========== ВЕБ-СЕРВЕР ==========

app = Quart(__name__, static_folder='static', static_url_path='')

@app.route('/')
async def index():
    return await app.send_static_file('index.html')

@app.route('/api/status')
async def get_status():
    return jsonify({
        "emoji": state.current_emoji_state,
        "health_confirmed": state.is_health_confirmed,
        "next_injection": "22:00",
        "is_awake": state.is_awake
    })

@app.route('/api/calendar')
async def get_api_calendar():
    events = await get_upcoming_events(max_results=10)
    return jsonify({"events": events.split('\n') if events else []})

@app.route('/api/memory/search')
async def api_search_memory():
    query = request.args.get('q', '')
    results = await search_memories(query)
    return jsonify({"results": results})

@app.route('/api/emotion', methods=['GET', 'POST'])
async def api_emotion():
    if request.method == 'POST':
        data = await request.get_json()
        if data.get('emotion'):
            await set_emotion(data['emotion'])
        return await get_emotion_state()
    return await get_emotion_state()

@app.route('/api/health')
async def api_health():
    days = int(request.args.get('days', 7))
    return jsonify(await get_health_stats(days))

# ========== КЛИЕНТЫ ==========

bot_client = TelegramClient('karina_bot_session', API_ID, API_HASH)
user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)

# ========== ХЕНДЛЕРЫ БОТА ==========

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    logger.info(f"📩 /start от {event.chat_id}")
    await event.respond(
        "Привет! Я Карина. 😊\n\nНажми кнопку ниже:",
        buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
    )

@bot_client.on(events.NewMessage(pattern='/app'))
async def app_handler(event):
    logger.info(f"📩 /app от {event.chat_id}")
    await event.respond(
        "Твоя панель:",
        buttons=[types.KeyboardButtonWebView("Открыть 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
    )

@bot_client.on(events.NewMessage(pattern='/calendar'))
async def calendar_handler(event):
    logger.info(f"📩 /calendar от {event.chat_id}")
    info = await get_upcoming_events()
    await event.respond(f"🗓 **Планы:**\n\n{info}")

@bot_client.on(events.NewMessage(pattern='/conflicts'))
async def conflicts_handler(event):
    logger.info(f"📩 /conflicts от {event.chat_id}")
    report = await get_conflict_report()
    await event.respond(report)

@bot_client.on(events.NewMessage(pattern='/health'))
async def health_handler(event):
    logger.info(f"📩 /health от {event.chat_id}")
    report = await get_health_report_text(7)
    await event.respond(report)

@bot_client.on(events.NewMessage(pattern='/news'))
async def news_handler(event):
    logger.info(f"📩 /news от {event.chat_id}")
    news = await get_latest_news()
    await event.respond(f"🗞 **Новости:**\n\n{news}")

@bot_client.on(events.NewMessage(incoming=True))
async def chat_handler(event):
    if event.text and event.text.startswith('/'):
        return
    if not event.is_private:
        return
    
    text_low = event.text.lower() if event.text else ''
    if any(word in text_low for word in ['сделал', 'готово', 'окей', 'уколол']):
        await event.respond("Умничка! 🥰")
        return
    
    if event.text:
        logger.info(f"💬 Сообщение от {event.chat_id}: {event.text[:30]}")
        async with bot_client.action(event.chat_id, 'typing'):
            response = await ask_karina(event.text, chat_id=event.chat_id)
            await event.reply(response)

# ========== ЗАПУСК В ПОТОКАХ ==========

def run_bot_thread():
    """Запуск бота в отдельном потоке"""
    logger.info("🤖 Запуск бота (поток)...")
    
    async def bot_main():
        await bot_client.start(bot_token=KARINA_TOKEN)
        logger.info("✅ Бот запущен")
        
        # Команды
        commands = [
            types.BotCommand("start", "Перезапустить 🔄"),
            types.BotCommand("calendar", "Планы 📅"),
            types.BotCommand("conflicts", "Конфликты ⚠️"),
            types.BotCommand("health", "Здоровье ❤️"),
            types.BotCommand("news", "Новости 🗞"),
        ]
        await bot_client(functions.bots.SetBotCommandsRequest(
            scope=types.BotCommandScopeDefault(),
            lang_code='ru',
            commands=commands
        ))
        logger.info("📡 Бот слушает сообщения...")
        
        await bot_client.run_until_disconnected()
    
    # Создаём новый event loop для потока
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bot_main())

def run_userbot_thread():
    """Запуск UserBot в отдельном потоке"""
    logger.info("👤 Запуск UserBot (поток)...")
    
    async def userbot_main():
        await user_client.connect()
        if not await user_client.is_user_authorized():
            logger.error("❌ UserBot не авторизован!")
            return
        logger.info("✅ UserBot авторизован")
        await user_client.run_until_disconnected()
    
    # Создаём новый event loop для потока
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(userbot_main())

async def run_auras():
    """Запуск аур"""
    await asyncio.sleep(3)
    logger.info("🌀 Запуск аур...")
    await start_auras(user_client, bot_client)

async def run_web():
    """Запуск веб-сервера"""
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🌐 Запуск веб-сервера на порту {port}...")
    
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    config.loglevel = "WARNING"
    
    await hypercorn.asyncio.serve(app, config)

def main():
    """Главная функция"""
    logger.info("🔧 Запуск Karina AI...")
    
    # Запускаем бота и UserBot в отдельных потоках
    bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
    userbot_thread = threading.Thread(target=run_userbot_thread, daemon=True)
    
    bot_thread.start()
    userbot_thread.start()
    
    # Ждём пока клиенты запустятся
    import time
    time.sleep(2)
    
    # Запускаем веб-сервер и ауры в главном потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(asyncio.gather(
        run_web(),
        run_auras(),
        return_exceptions=True
    ))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Остановка...")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
