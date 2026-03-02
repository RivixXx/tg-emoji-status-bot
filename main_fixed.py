"""
Karina AI — Telegram Bot + Web Server
Единый asyncio event loop с системой супервизора, метриками и Graceful Shutdown

Версия: 4.1 (Исправленная)
"""
import os
import asyncio
import logging
import sys
import time
import signal
import sqlite3
from typing import Optional, Set

# Импорты веб-сервера
from quart import Quart, jsonify
import hypercorn.asyncio
from hypercorn.config import Config

# Импорты Telegram
from telethon import functions, types, TelegramClient, events
from telethon.sessions import StringSession

# Импорты конфигурации
from brains.config import API_ID, API_HASH, KARINA_TOKEN, USER_SESSION, MY_ID
from brains.validate_config import validate_and_start

# Импорты модулей
from brains.reminders import reminder_manager, start_reminder_loop
from brains.vpn_logic import register_vpn_handlers, set_fire_and_forget
from brains.subscription_monitor import start_sub_monitor_loop
from brains.clients import check_all_connections, get_supabase_client
from auras import start_auras
from skills import register_karina_base_skills
from plugins import plugin_manager

# ============================================================================
# FIRE-AND-FORGET (ДИСПЕТЧЕР ФОНОВЫХ ЗАДАЧ)
# ============================================================================

background_tasks: Set[asyncio.Task] = set()


def fire_and_forget(coro):
    """
    Запускает асинхронную функцию в фоне с обработкой ошибок
    
    Args:
        coro: Coroutine для запуска
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("⚠️ fire_and_forget вызван вне event loop")
        return

    task = loop.create_task(coro)
    background_tasks.add(task)

    def cleanup(t):
        background_tasks.discard(t)
        if t.exception():
            err_msg = str(t.exception())
            if "database is locked" in err_msg.lower():
                logger.warning(f"⚠️ БД заблокирована (временная проблема): {err_msg}")
            elif "connection reset" in err_msg.lower():
                logger.warning(f"⚠️ Соединение сброшено (повторная попытка): {err_msg}")
            else:
                logger.error(f"⚠️ Ошибка в фоновой задаче: {err_msg}")

    task.add_done_callback(cleanup)


# Передаем функцию fire_and_forget в логику VPN
set_fire_and_forget(fire_and_forget)

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# 🛡️ Фильтрация шумных предупреждений Telethon
logging.getLogger('telethon.network.mtproto').setLevel(logging.ERROR)
logging.getLogger('telethon.extensions.messages').setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('googleapiclient').setLevel(logging.WARNING)

# ============================================================================
# МОНИТОРИНГ И МЕТРИКИ
# ============================================================================

stats_lock = asyncio.Lock()
APP_STATS = {
    "start_time": 0,
    "components": {
        "web": {"status": "starting", "last_seen": 0, "restarts": 0},
        "bot": {"status": "starting", "last_seen": 0, "restarts": 0},
        "userbot": {"status": "starting", "last_seen": 0, "restarts": 0},
        "reminders": {"status": "starting", "last_seen": 0, "restarts": 0}
    },
    "errors_count": 0,
    "last_error": None,
    "connections": {
        "supabase": False,
        "mistral": False
    }
}

SHUTDOWN_EVENT = asyncio.Event()


async def report_status(component: str, status: str):
    """Обновляет статус компонента"""
    async with stats_lock:
        if component in APP_STATS["components"]:
            APP_STATS["components"][component]["status"] = status
            APP_STATS["components"][component]["last_seen"] = time.time()


async def record_error(error_msg: str):
    """Записывает ошибку"""
    async with stats_lock:
        APP_STATS["errors_count"] += 1
        APP_STATS["last_error"] = {"msg": str(error_msg), "time": time.time()}

# ============================================================================
# ВЕБ-СЕРВЕР
# ============================================================================

app = Quart(__name__, static_folder='static', static_url_path='')


@app.route('/')
async def index():
    """Главная страница Mini App"""
    return await app.send_static_file('index.html')


@app.route('/api/health')
async def health_check():
    """Health check endpoint для мониторинга"""
    now = time.time()
    async with stats_lock:
        return jsonify({
            "status": "ok",
            "uptime": int(now - APP_STATS["start_time"]),
            "errors": APP_STATS["errors_count"],
            "components": APP_STATS["components"],
            "connections": APP_STATS["connections"]
        }), 200

# ============================================================================
# ЛОГИКА ЗАПУСКА КОМПОНЕНТОВ
# ============================================================================

async def run_bot_main(client: TelegramClient):
    """Запуск бота"""
    logger.info("✅ Бот запущен")
    await report_status("bot", "running")

    # Регистрация команд (отправляем в API)
    commands = [
        types.BotCommand("start", "Меню VPN 🚀"),
        types.BotCommand("app", "Панель управления 📱")
    ]
    try:
        # Очищаем глобальные команды
        await client(functions.bots.SetBotCommandsRequest(
            scope=types.BotCommandScopeDefault(),
            lang_code='',
            commands=[]
        ))
        # Устанавливаем персональные команды для пользователя
        my_peer = await client.get_input_entity(MY_ID)
        await client(functions.bots.SetBotCommandsRequest(
            scope=types.BotCommandScopePeer(peer=my_peer),
            lang_code='ru',
            commands=commands
        ))
        logger.info("✅ Команды бота установлены")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить команды бота: {e}")

    await client.run_until_disconnected()


async def run_userbot_main(u_client: TelegramClient, b_client: TelegramClient):
    """Запуск userbot (для аур и emoji статусов)"""
    try:
        await u_client.connect()
        
        if not await u_client.is_user_authorized():
            logger.error("❌ UserBot не авторизован. Проверьте SESSION_STRING")
            await report_status("userbot", "unauthorized")
            return

        logger.info("✅ UserBot авторизован")
        await report_status("userbot", "running")

        # Запуск аур и напоминаний
        reminder_manager.set_client(b_client, MY_ID)

        # Создаем задачи
        aura_task = asyncio.create_task(start_auras(u_client, b_client))
        reminders_task = asyncio.create_task(start_reminder_loop())

        try:
            await u_client.run_until_disconnected()
        finally:
            # Отменяем задачи при остановке
            aura_task.cancel()
            reminders_task.cancel()
            try:
                await asyncio.gather(aura_task, reminders_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"❌ Ошибка в userbot: {e}")
        await report_status("userbot", "failed")
        raise


async def component_supervisor(coro_func, name: str, *args):
    """
    Супервизор для компонентов с экспоненциальным backoff
    
    Args:
        coro_func: Функция для запуска
        name: Имя компонента
        *args: Аргументы для функции
    """
    backoff = 10  # Начальная задержка
    max_backoff = 300  # Максимум 5 минут

    while not SHUTDOWN_EVENT.is_set():
        try:
            logger.info(f"🔄 Supervisor: Запуск {name}...")
            await coro_func(*args)
        except asyncio.CancelledError:
            logger.info(f"🛑 Компонент {name} остановлен")
            break
        except Exception as e:
            err_text = str(e)
            await record_error(f"{name} crashed: {err_text}")

            logger.error(f"💀 Supervisor: {name} упал: {err_text}. Рестарт через {backoff}с...")
            await report_status(name, "failed")

        if SHUTDOWN_EVENT.is_set():
            break
            
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ============================================================================

async def amain():
    """Основная функция запуска"""
    loop = asyncio.get_running_loop()
    
    # Обработчики сигналов
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: SHUTDOWN_EVENT.set())

    # ========================================================================
    # 1. ВАЛИДАЦИЯ КОНФИГУРАЦИИ
    # ========================================================================
    logger.info("🔍 Проверка конфигурации...")
    
    if not await validate_and_start():
        logger.error("❌ ЗАПУСК ОТМЕНЁН: Ошибки в конфигурации")
        return

    # ========================================================================
    # 2. ПРОВЕРКА ПОДКЛЮЧЕНИЙ
    # ========================================================================
    logger.info("🔍 Проверка подключений к внешним сервисам...")
    connections = await check_all_connections()
    
    async with stats_lock:
        APP_STATS["connections"] = {
            "supabase": connections.get("supabase", False),
            "mistral": connections.get("mistral", False)
        }
    
    if connections["errors"]:
        logger.warning(f"⚠️ Проблемы с подключениями: {connections['errors']}")

    # ========================================================================
    # 3. ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ TELEGRAM
    # ========================================================================
    logger.info("🔧 Инициализация Telegram клиентов...")
    
    # Бот клиент
    bot_client = TelegramClient('karina_bot_session', API_ID, API_HASH)
    
    # Регистрируем хендлеры ДО подключения
    register_vpn_handlers(bot_client)
    register_karina_base_skills(bot_client)

    # Подключаемся с защитой от блокировки БД
    logger.info("🔌 Подключение бота к Telegram...")
    for i in range(15):
        try:
            await bot_client.connect()
            if not await bot_client.is_user_authorized():
                await bot_client.start(bot_token=KARINA_TOKEN)
            logger.info("✅ Бот подключен и авторизован")
            break
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                wait_time = 2 ** i
                logger.warning(f"⏳ БД сессии заблокирована, жду {wait_time}с... (попытка {i+1}/15)")
                await asyncio.sleep(wait_time)
            else:
                raise
        except Exception as e:
            logger.error(f"❌ Ошибка подключения бота: {e}")
            await asyncio.sleep(5)

    if not bot_client.is_connected():
        logger.error("🔴 Не удалось открыть сессию бота. Запуск отменён.")
        return

    # Userbot клиент (для аур)
    user_client: Optional[TelegramClient] = None
    
    if USER_SESSION and len(USER_SESSION) > 50:
        try:
            user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)
            logger.info("✅ UserBot сессия загружена")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации UserBot: {e}")
    else:
        logger.warning("⚠️ SESSION_STRING пуст — ауры и emoji-статусы не будут работать")

    # ========================================================================
    # 4. ИНИЦИАЛИЗАЦИЯ ПЛАГИНОВ
    # ========================================================================
    logger.info("🧩 Загрузка плагинов...")
    plugin_manager.load_config()
    discovered = plugin_manager.discover_plugins()
    
    for plugin_name in discovered:
        if plugin_name in ["base", "__init__", "base.py"]:
            continue
        plugin = plugin_manager.load_plugin(plugin_name)
        if plugin:
            plugin_manager.register_plugin(plugin)
            logger.info(f"✅ Плагин загружен: {plugin_name}")
    
    await plugin_manager.initialize_all()

    # ========================================================================
    # 5. ЗАПУСК ЗАДАЧ
    # ========================================================================
    logger.info("🚀 Запуск компонентов...")
    
    # Супервизоры для бота и userbot
    bot_supervisor = asyncio.create_task(
        component_supervisor(run_bot_main, "bot", bot_client)
    )
    
    user_supervisor: Optional[asyncio.Task] = None
    if user_client:
        user_supervisor = asyncio.create_task(
            component_supervisor(run_userbot_main, "userbot", user_client, bot_client)
        )

    # Даем боту время инициализироваться
    await asyncio.sleep(3)
    
    # Монитор подписок
    sub_monitor = asyncio.create_task(start_sub_monitor_loop(bot_client))

    # ========================================================================
    # 6. ЗАПУСК ВЕБ-СЕРВЕРА
    # ========================================================================
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🌐 Веб-сервер запускается на порту {port}...")
    
    APP_STATS["start_time"] = time.time()
    
    try:
        config = Config()
        config.bind = [f"0.0.0.0:{port}"]
        config.accesslog = None  # Отключаем access log для тишины
        
        await hypercorn.asyncio.serve(
            app, 
            config, 
            shutdown_trigger=SHUTDOWN_EVENT.wait
        )
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")
    finally:
        # ====================================================================
        # 7. CORRECT SHUTDOWN
        # ====================================================================
        logger.info("🛑 Завершение работы...")
        
        SHUTDOWN_EVENT.set()
        
        # Отменяем фоновые задачи
        sub_monitor.cancel()
        bot_supervisor.cancel()
        if user_supervisor:
            user_supervisor.cancel()
        
        # Ждем завершения
        await asyncio.gather(
            bot_supervisor, 
            user_supervisor if user_supervisor else asyncio.sleep(0),
            return_exceptions=True
        )
        
        # Отключаем клиентов
        if bot_client.is_connected():
            await bot_client.disconnect()
        if user_client and user_client.is_connected():
            await user_client.disconnect()
        
        # Закрываем HTTP клиент
        from brains.clients import http_client
        await http_client.aclose()
        
        # Shutdown плагинов
        await plugin_manager.shutdown_all()
        
        logger.info("✅ Работа завершена корректно")


if __name__ == '__main__':
    try:
        logger.info("=" * 60)
        logger.info("🤖 KARINA AI v4.1 — Запуск")
        logger.info("=" * 60)
        
        asyncio.run(amain())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по сигналу пользователя")
    except Exception as e:
        logger.error(f"💀 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
