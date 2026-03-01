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
import json
import io
import re
import random
from datetime import datetime
from quart import Quart, jsonify, request
import hypercorn.asyncio
from hypercorn.config import Config
from telethon import functions, types, events, TelegramClient, Button
from telethon.tl.custom import Button as CustomButton
from telethon.sessions import StringSession
from telethon.tl.types import BotCommandScopeDefault, BotCommandScopePeer, InputUserEmpty
from brains.config import API_ID, API_HASH, KARINA_TOKEN, USER_SESSION, MY_ID
from brains.memory import search_memories
from brains.calendar import get_upcoming_events, get_conflict_report
import qrcode
from brains.health import get_health_report_text, get_health_stats
from brains.reminders import reminder_manager, start_reminder_loop, ReminderType
from brains.emotions import get_emotion_state, set_emotion
from brains.news import get_latest_news
from brains.ai import ask_karina
from brains.media import media_manager
from brains.vpn_logic import register_vpn_handlers, set_fire_and_forget
from brains.alerts import notify_system_error
from brains.subscription_monitor import start_sub_monitor_loop
from auras import state, start_auras
from skills import register_karina_base_skills
from plugins import plugin_manager

# ========== FIRE-AND-FORGET (ДИСПЕТЧЕР ФОНОВЫХ ЗАДАЧ) ==========

background_tasks = set()

def fire_and_forget(coro):
    """Запускает асинхронную функцию в фоне."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    task = loop.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    
    def log_error(t):
        if t.exception():
            err_msg = str(t.exception())
            if "database is locked" in err_msg:
                logging.warning(f"⚠️ БД заблокирована: {err_msg}")
            else:
                logging.error(f"⚠️ Ошибка в фоновой задаче: {err_msg}")
    
    task.add_done_callback(log_error)

# Передаем функцию fire_and_forget в логику VPN
set_fire_and_forget(fire_and_forget)

# ========== ЛОГИРОВАНИЕ ==========

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
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

SHUTDOWN_EVENT = asyncio.Event()

async def report_status(component: str, status: str):
    async with stats_lock:
        if component in APP_STATS["components"]:
            APP_STATS["components"][component]["status"] = status
            APP_STATS["components"][component]["last_seen"] = time.time()

async def record_error(error_msg: str):
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
    async with stats_lock:
        return jsonify({"status": "ok", "uptime": int(now - APP_STATS["start_time"]), "errors": APP_STATS["errors_count"]}), 200

# ========== КЛИЕНТЫ ==========

bot_client = TelegramClient('karina_bot_session', API_ID, API_HASH)
user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)

# ========== ЛОГИКА ЗАПУСКА ==========

async def run_bot_main():
    await bot_client.start(bot_token=KARINA_TOKEN)
    logger.info("✅ Бот запущен")
    await report_status("bot", "running")

    # Регистрация команд
    commands = [types.BotCommand("start", "Меню VPN 🚀"), types.BotCommand("app", "Панель управления 📱")]
    await bot_client(functions.bots.SetBotCommandsRequest(scope=types.BotCommandScopeDefault(), lang_code='', commands=[]))
    
    my_peer = await bot_client.get_input_entity(MY_ID)
    await bot_client(functions.bots.SetBotCommandsRequest(scope=types.BotCommandScopePeer(peer=my_peer), lang_code='ru', commands=commands))

    # Регистрация логики VPN
    register_vpn_handlers(bot_client)
    
    # Регистрация скиллов
    register_karina_base_skills(bot_client)
    
    await bot_client.run_until_disconnected()

async def run_userbot_main():
    await user_client.connect()
    if not await user_client.is_user_authorized():
        await report_status("userbot", "unauthorized")
        return
    
    logger.info("✅ UserBot авторизован")
    await report_status("userbot", "running")
    
    # Запуск аур и напоминаний
    from brains.health import get_health_stats
    reminder_manager.set_client(bot_client, MY_ID)
    await reminder_manager.load_active_reminders()
    
    aura_task = asyncio.create_task(start_auras(user_client, bot_client))
    reminders_task = asyncio.create_task(start_reminder_loop())

    try:
        await user_client.run_until_disconnected()
    finally:
        aura_task.cancel()
        reminders_task.cancel()

async def component_supervisor(coro_func, name):
    backoff = 10
    while not SHUTDOWN_EVENT.is_set():
        try:
            logger.info(f"🔄 Supervisor: Запуск {name}...")
            await coro_func()
        except Exception as e:
            err_text = str(e)
            await record_error(f"{name} crashed: {err_text}")
            fire_and_forget(notify_system_error(bot_client, name, err_text))
            logger.error(f"💀 Supervisor: {name} упал: {err_text}. Рестарт через {backoff}с...")
            await report_status(name, "failed")
        
        if SHUTDOWN_EVENT.is_set(): break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 300)

async def amain():
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: SHUTDOWN_EVENT.set())

    # Плагины
    plugin_manager.load_config()
    discovered = plugin_manager.discover_plugins()
    for plugin_name in discovered:
        plugin = plugin_manager.load_plugin(plugin_name)
        if plugin: plugin_manager.register_plugin(plugin)
    await plugin_manager.initialize_all()

    bot_supervisor = asyncio.create_task(component_supervisor(run_bot_main, "bot"))
    user_supervisor = asyncio.create_task(component_supervisor(run_userbot_main, "userbot"))
    sub_monitor = asyncio.create_task(start_sub_monitor_loop(bot_client))

    try:
        port = int(os.environ.get('PORT', 8080))
        config = Config()
        config.bind = [f"0.0.0.0:{port}"]
        await hypercorn.asyncio.serve(app, config, shutdown_trigger=SHUTDOWN_EVENT.wait)
    finally:
        SHUTDOWN_EVENT.set()
        await plugin_manager.shutdown_all()
        sub_monitor.cancel()
        await asyncio.gather(bot_supervisor, user_supervisor, return_exceptions=True)
        if bot_client.is_connected(): await bot_client.disconnect()
        if user_client.is_connected(): await user_client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
