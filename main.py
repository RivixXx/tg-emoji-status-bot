"""
Karina AI - Telegram Bot + Web Server
Единый asyncio event loop с системой супервизора, метриками и Graceful Shutdown
"""
import os
import asyncio
import logging
import sys
import time
import signal
from datetime import datetime
from quart import Quart, jsonify, request
import hypercorn.asyncio
from hypercorn.config import Config
from telethon import functions, types, events, TelegramClient
from telethon.sessions import StringSession
from brains.config import API_ID, API_HASH, KARINA_TOKEN, USER_SESSION
from brains.memory import search_memories
from brains.calendar import get_upcoming_events, get_conflict_report
from brains.health import get_health_report_text, get_health_stats
from brains.reminders import reminder_manager, start_reminder_loop, ReminderType
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

# 🛡️ Фильтрация шумных предупреждений Telethon
logging.getLogger('telethon.network.mtproto').setLevel(logging.ERROR)
logging.getLogger('telethon.extensions.messages').setLevel(logging.ERROR)

# ========== МОНИТОРИНГ И МЕТРИКИ ==========

stats_lock = asyncio.Lock()
APP_STATS = {
    "start_time": time.time(),
    "components": {
        "web": {"status": "starting", "last_seen": 0, "restarts": 0},
        "bot": {"status": "starting", "last_seen": 0, "restarts": 0},
        "userbot": {"status": "starting", "last_seen": 0, "restarts": 0},
        "reminders": {"status": "starting", "last_seen": 0, "restarts": 0}
    },
    "errors_count": 0,
    "last_error": None
}

METRICS = {
    "requests_total": 0,
    "ai_responses_total": 0,
    "ai_latency_sum": 0,
    "ai_errors": 0,
}

# Ограничитель одновременных запросов к AI
AI_SEMAPHORE = asyncio.Semaphore(5)
SHUTDOWN_EVENT = asyncio.Event()

async def report_status(component: str, status: str):
    """Обновляет статус компонента (async-safe)"""
    async with stats_lock:
        if component in APP_STATS["components"]:
            APP_STATS["components"][component]["status"] = status
            APP_STATS["components"][component]["last_seen"] = time.time()

async def record_error(error_msg: str):
    """Фиксирует ошибку (async-safe)"""
    async with stats_lock:
        APP_STATS["errors_count"] += 1
        APP_STATS["last_error"] = {"msg": str(error_msg), "time": time.time()}

# ========== ВЕБ-СЕРВЕР ==========

app = Quart(__name__, static_folder='static', static_url_path='')

@app.route('/')
async def index():
    return await app.send_static_file('index.html')

@app.route('/api/health')
async def health_check():
    now = time.time()
    health_status = "ok"
    details = {}
    
    async with stats_lock:
        for comp, data in APP_STATS["components"].items():
            if data["status"] == "running" and (now - data["last_seen"]) > 300:
                data["status"] = "stale"
                health_status = "degraded"
            elif data["status"] in ["failed", "unauthorized"]:
                health_status = "degraded"
            details[comp] = data.copy()
        
        errors = APP_STATS["errors_count"]
        
    return jsonify({
        "status": health_status,
        "uptime_seconds": int(now - APP_STATS["start_time"]),
        "errors": errors,
        "components": details
    }), 200 if health_status == "ok" else 503

@app.route('/api/metrics')
async def metrics_endpoint():
    avg_latency = 0
    async with stats_lock:
        if METRICS["ai_responses_total"] > 0:
            avg_latency = METRICS["ai_latency_sum"] / METRICS["ai_responses_total"]
        metrics_copy = METRICS.copy()
        
    return jsonify({
        "metrics": metrics_copy,
        "ai_avg_latency_seconds": round(avg_latency, 3),
        "memory_info": "RAG active"
    })

@app.route('/api/status')
async def get_status():
    await report_status("web", "running")
    return jsonify({
        "emoji": state.current_emoji_state,
        "health_confirmed": state.is_health_confirmed,
        "next_injection": "22:00",
        "is_awake": state.is_awake
    })

@app.route('/api/emotion', methods=['GET', 'POST'])
async def api_emotion():
    auth = request.headers.get("X-Karina-Secret")
    if request.method == 'POST' and auth != os.environ.get("KARINA_API_SECRET"):
        return jsonify({"error": "Unauthorized"}), 401
        
    if request.method == 'POST':
        data = await request.get_json()
        if data.get('emotion'):
            await set_emotion(data['emotion'])
        return await get_emotion_state()
    return await get_emotion_state()

# ========== КЛИЕНТЫ ==========

bot_client = TelegramClient('karina_bot_session', API_ID, API_HASH)
user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)

# ========== ХЕНДЛЕРЫ БОТА ==========

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await report_status("bot", "running")
    async with stats_lock:
        METRICS["requests_total"] += 1
    await event.respond(
        "Привет! Я Карина. 😊\n\nНажми кнопку ниже:",
        buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
    )

@bot_client.on(events.NewMessage(incoming=True))
async def chat_handler(event):
    if not event.is_private or (event.text and event.text.startswith('/')):
        return
    
    await report_status("bot", "running")
    async with stats_lock:
        METRICS["requests_total"] += 1
    
    text_low = event.text.lower() if event.text else ''
    if any(word in text_low for word in ['сделал', 'готово', 'окей', 'уколол']):
        await event.respond("Умничка! 🥰")
        return
    
    if event.text:
        start_ts = time.time()
        async with bot_client.action(event.chat_id, 'typing'):
            try:
                # 🚦 Используем семафор для ограничения нагрузки
                async with AI_SEMAPHORE:
                    response = await asyncio.wait_for(ask_karina(event.text, chat_id=event.chat_id), timeout=20.0)
                
                async with stats_lock:
                    METRICS["ai_responses_total"] += 1
                    METRICS["ai_latency_sum"] += (time.time() - start_ts)
                await event.reply(response)
            except asyncio.TimeoutError:
                async with stats_lock:
                    METRICS["ai_errors"] += 1
                await event.reply("Ой, я что-то задумалась... попробуй еще раз? 🧠🌀")
            except Exception as e:
                async with stats_lock:
                    METRICS["ai_errors"] += 1
                logger.error(f"Chat error: {e}")

# ========== ЛОГИКА ЗАПУСКА И SUPERVISOR ==========

async def run_bot_main():
    """Основной цикл бота"""
    await bot_client.start(bot_token=KARINA_TOKEN)
    logger.info("✅ Бот запущен")
    await report_status("bot", "running")
    
    commands = [
        types.BotCommand("start", "Перезапустить 🔄"),
        types.BotCommand("calendar", "Планы 📅"),
        types.BotCommand("health", "Здоровье ❤️"),
        types.BotCommand("news", "Новости 🗞"),
    ]
    await bot_client(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(), lang_code='ru', commands=commands
    ))
    
    # Heartbeat таска для бота
    async def bot_heartbeat():
        while not SHUTDOWN_EVENT.is_set():
            await report_status("bot", "running")
            await asyncio.sleep(30)

    heartbeat_task = asyncio.create_task(bot_heartbeat())
    
    try:
        # Создаем таски для wait
        client_task = asyncio.create_task(bot_client.run_until_disconnected())
        shutdown_task = asyncio.create_task(SHUTDOWN_EVENT.wait())
        
        done, pending = await asyncio.wait(
            [client_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)

async def run_userbot_main():
    """Основной цикл UserBot"""
    await user_client.connect()
    if not await user_client.is_user_authorized():
        await report_status("userbot", "unauthorized")
        return
    
    logger.info("✅ UserBot авторизован")
    await report_status("userbot", "running")
    
    from brains.config import MY_ID
    reminder_manager.set_client(user_client, MY_ID)
    await reminder_manager.load_active_reminders()
    
    def ensure_reminder(type_enum, creator_func, *args):
        today_prefix = datetime.now().strftime('%Y%m%d')
        exists = any(r.type == type_enum and today_prefix in r.id for r in reminder_manager.reminders.values())
        if not exists:
            r = creator_func(*args)
            reminder_manager.reminders[r.id] = r
            logger.info(f"🔔 Создано напоминание: {r.id}")

    ensure_reminder(ReminderType.HEALTH, reminder_manager.create_health_reminder, "22:00")
    ensure_reminder(ReminderType.LUNCH, reminder_manager.create_lunch_reminder)
    ensure_reminder(ReminderType.MORNING, reminder_manager.create_morning_greeting)
    ensure_reminder(ReminderType.EVENING, reminder_manager.create_evening_reminder, "22:30")

    # Запуск фоновых задач
    aura_task = asyncio.create_task(start_auras(user_client, bot_client))
    
    async def monitored_reminders():
        await report_status("reminders", "running")
        try:
            await start_reminder_loop()
        except Exception as e:
            await report_status("reminders", "failed")
            await record_error(f"Reminders loop failed: {e}")

    reminders_task = asyncio.create_task(monitored_reminders())

    # Heartbeat для юзербота
    async def userbot_heartbeat():
        while not SHUTDOWN_EVENT.is_set():
            await report_status("userbot", "running")
            await asyncio.sleep(30)
    
    hb_task = asyncio.create_task(userbot_heartbeat())

    try:
        done, pending = await asyncio.wait(
            [user_client.run_until_disconnected(), SHUTDOWN_EVENT.wait()],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    finally:
        hb_task.cancel()
        aura_task.cancel()
        reminders_task.cancel()
        await asyncio.gather(hb_task, aura_task, reminders_task, return_exceptions=True)

async def component_supervisor(coro_func, name):
    """Следит за компонентом и перезапускает с экспоненциальным backoff"""
    backoff = 10
    while not SHUTDOWN_EVENT.is_set():
        try:
            logger.info(f"🔄 Supervisor: Запуск {name}...")
            await coro_func()
            if not SHUTDOWN_EVENT.is_set():
                logger.warning(f"⚠️ {name} завершился неожиданно. Перезапуск...")
        except Exception as e:
            await record_error(f"{name} crashed: {e}")
            async with stats_lock:
                APP_STATS["components"][name]["restarts"] += 1
            logger.error(f"💀 Supervisor: {name} упал: {e}. Рестарт через {backoff}с...")
            await report_status(name, "failed")
        
        if SHUTDOWN_EVENT.is_set(): break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 300)

async def run_web():
    """Запуск веб-сервера"""
    port = int(os.environ.get('PORT', 8080))
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    config.loglevel = "WARNING"
    
    async def web_heartbeat():
        while not SHUTDOWN_EVENT.is_set():
            await report_status("web", "running")
            await asyncio.sleep(60)
            
    hb_task = asyncio.create_task(web_heartbeat())
    try:
        await hypercorn.asyncio.serve(app, config, shutdown_trigger=SHUTDOWN_EVENT.wait)
    finally:
        hb_task.cancel()
        await asyncio.gather(hb_task, return_exceptions=True)

async def amain():
    """Главная асинхронная точка входа"""
    logger.info("🔧 Запуск Karina AI (Unified Loop)...")
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: SHUTDOWN_EVENT.set())

    bot_supervisor = asyncio.create_task(component_supervisor(run_bot_main, "bot"))
    user_supervisor = asyncio.create_task(component_supervisor(run_userbot_main, "userbot"))
    
    async def system_heartbeat():
        while not SHUTDOWN_EVENT.is_set():
            await asyncio.sleep(300)
            uptime = int(time.time() - APP_STATS["start_time"])
            async with stats_lock:
                errs = APP_STATS['errors_count']
            logger.info(f"💓 HEARTBEAT | Uptime: {uptime}s | Errs: {errs}")

    sh_task = asyncio.create_task(system_heartbeat())

    try:
        await run_web()
    finally:
        logger.info("🔌 Завершение работы...")
        SHUTDOWN_EVENT.set()
        
        sh_task.cancel()
        await asyncio.gather(bot_supervisor, user_supervisor, sh_task, return_exceptions=True)
        
        if bot_client.is_connected(): await bot_client.disconnect()
        if user_client.is_connected(): await user_client.disconnect()
        
        logger.info("👋 Karina AI остановлена.")

if __name__ == '__main__':
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
