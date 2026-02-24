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
from datetime import datetime
from quart import Quart, jsonify, request
import hypercorn.asyncio
from hypercorn.config import Config
from telethon import functions, types, events, TelegramClient, Button
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
from auras import state, start_auras
from skills import register_karina_base_skills
from plugins import plugin_manager

# ========== СТРУКТУРИРОВАННОЕ ЛОГИРОВАНИЕ ==========

class JSONFormatter(logging.Formatter):
    """JSON формат для структурированных логов"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Добавляем exception если есть
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Добавляем дополнительные поля
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'chat_id'):
            log_entry["chat_id"] = record.chat_id
            
        return json.dumps(log_entry, ensure_ascii=False)


# Настройка логирования
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_format = os.environ.get('LOG_FORMAT', 'text')  # 'text' или 'json'

if log_format == 'json':
    json_handler = logging.StreamHandler(sys.stdout)
    json_handler.setFormatter(JSONFormatter())
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        handlers=[json_handler]
    )
else:
    # Текстовый формат с цветами для разработки
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        level=getattr(logging, log_level, logging.INFO),
        stream=sys.stdout
    )

logger = logging.getLogger(__name__)

# ================================================

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

# Rate limiter для API
from brains.rate_limiter import rate_limiter, create_rate_limit_headers


async def check_rate_limit(client_id: str, endpoint: str):
    """Проверяет rate limit и возвращает ответ если превышен"""
    allowed, retry_after = rate_limiter.is_allowed(client_id, endpoint)
    
    if not allowed:
        headers = create_rate_limit_headers(client_id, endpoint)
        from quart import jsonify
        return jsonify({
            "error": "Rate limit exceeded",
            "retry_after": retry_after
        }), 429, headers
    
    return None

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
    # Rate limiting
    client_ip = request.remote_addr or "unknown"
    rate_limit_response = await check_rate_limit(client_ip, "api/emotion")
    if rate_limit_response:
        return rate_limit_response
    
    auth = request.headers.get("X-Karina-Secret")
    if request.method == 'POST' and auth != os.environ.get("KARINA_API_SECRET"):
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == 'POST':
        data = await request.get_json()
        if data.get('emotion'):
            await set_emotion(data['emotion'])
        return await get_emotion_state()
    return await get_emotion_state()


# ========== API ПЛАГИНОВ ==========

@app.route('/api/plugins', methods=['GET'])
async def api_plugins_list():
    """Получить список всех плагинов"""
    return jsonify({
        "plugins": plugin_manager.list_plugins()
    })

@app.route('/api/plugins/<plugin_name>/enable', methods=['POST'])
async def api_plugin_enable(plugin_name):
    """Включить плагин"""
    auth = request.headers.get("X-Karina-Secret")
    if auth != os.environ.get("KARINA_API_SECRET"):
        return jsonify({"error": "Unauthorized"}), 401
    
    success = plugin_manager.enable_plugin(plugin_name)
    if success:
        return jsonify({"status": "ok", "message": f"Плагин {plugin_name} включен"})
    return jsonify({"error": f"Плагин {plugin_name} не найден"}), 404

@app.route('/api/plugins/<plugin_name>/disable', methods=['POST'])
async def api_plugin_disable(plugin_name):
    """Выключить плагин"""
    auth = request.headers.get("X-Karina-Secret")
    if auth != os.environ.get("KARINA_API_SECRET"):
        return jsonify({"error": "Unauthorized"}), 401
    
    success = plugin_manager.disable_plugin(plugin_name)
    if success:
        return jsonify({"status": "ok", "message": f"Плагин {plugin_name} выключен"})
    return jsonify({"error": f"Плагин {plugin_name} не найден"}), 404

@app.route('/api/plugins/<plugin_name>/settings', methods=['GET', 'POST'])
async def api_plugin_settings(plugin_name):
    """Получить или обновить настройки плагина"""
    auth = request.headers.get("X-Karina-Secret")
    if request.method == 'POST' and auth != os.environ.get("KARINA_API_SECRET"):
        return jsonify({"error": "Unauthorized"}), 401
    
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        return jsonify({"error": f"Плагин {plugin_name} не найден"}), 404
    
    if request.method == 'POST':
        data = await request.get_json()
        if data:
            plugin.update_settings(data)
            plugin_manager.save_config()
        return jsonify({"status": "ok", "settings": plugin.get_settings()})
    
    return jsonify({"settings": plugin.get_settings()})


# ========== API ДЛЯ MINI APP ==========

@app.route('/api/calendar')
async def api_calendar():
    """Получить список событий календаря (для Mini App)"""
    # Rate limiting
    client_ip = request.remote_addr or "unknown"
    rate_limit_response = await check_rate_limit(client_ip, "api/calendar")
    if rate_limit_response:
        return rate_limit_response
    
    try:
        from brains.calendar import get_upcoming_events
        events = await get_upcoming_events(max_results=10)
        # Парсим события в список
        event_list = []
        if events:
            for line in events.split('\n'):
                if line.strip():
                    event_list.append(line.strip())
        return jsonify({"events": event_list})
    except Exception as e:
        logger.error(f"API Calendar error: {e}")
        return jsonify({"events": [], "error": str(e)})

@app.route('/api/memory/search')
async def api_memory_search():
    """Поиск в памяти (для Mini App)"""
    # Rate limiting
    client_ip = request.remote_addr or "unknown"
    rate_limit_response = await check_rate_limit(client_ip, "api/memory/search")
    if rate_limit_response:
        return rate_limit_response
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({"results": ""})

    try:
        from brains.memory import search_memories
        results = await search_memories(query, limit=5)
        return jsonify({"results": results})
    except Exception as e:
        logger.error(f"API Memory Search error: {e}")
        return jsonify({"results": "", "error": str(e)})

@app.route('/api/health')
async def api_health_stats():
    """Статистика здоровья (для Mini App)"""
    # Rate limiting
    client_ip = request.remote_addr or "unknown"
    rate_limit_response = await check_rate_limit(client_ip, "api/health")
    if rate_limit_response:
        return rate_limit_response
    
    from brains.health import get_health_stats
    days = request.args.get('days', 7, type=int)
    
    try:
        # get_health_stats - синхронная функция, вызываем без await
        stats = get_health_stats(days=days)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"API Health Stats error: {e}")
        return jsonify({
            "total_days": 0,
            "confirmed_days": 0,
            "success_rate": 0,
            "error": str(e)
        })

# =======================================
# ========== КЛИЕНТЫ ==========

bot_client = TelegramClient('karina_bot_session', API_ID, API_HASH)
user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)

# ========== ЛОГИКА ЗАПУСКА И SUPERVISOR ==========

async def run_bot_main():
    """Основной цикл бота"""
    # ========== VPN SHOP LOGIC (ДВОЙНОЕ ДНО) — ПЕРВЫМ! ==========
    # Регистрируем ПЕРЕД скиллами чтобы перехватывал сообщения от чужих ID

    @bot_client.on(events.NewMessage(func=lambda e: e.is_private and e.sender_id != MY_ID))
    async def vpn_stranger_interceptor(event):
        """Перехватывает все сообщения от чужих ID и показывает витрину VPN"""

        # Инлайн-клавиатура с неоновым вайбом
        keyboard = [
            [Button.inline("🚀 Получить доступ", b"vpn_tariffs")],
            [Button.inline("❔ Как это работает", b"vpn_info")]
        ]

        # Эстетика Dark sci-fi / Space UI в тексте
        welcome_text = (
            "🌌 **[ TERMINAL ACTIVE ]**\n\n"
            "Приветствую. Я — Карина, цифровой интерфейс приватной сети.\n\n"
            "⚡️ Высокоскоростное шифрованное соединение.\n"
            "🛡 Обход любых систем DPI и блокировок (XTLS-Reality).\n"
            "🇩🇪 Выделенный узел: Frankfurt.\n\n"
            "Статус сети: `ONLINE`. Ожидание команды..."
        )

        await event.respond(welcome_text, buttons=keyboard)

        # Останавливаем распространение события, чтобы другие хендлеры не сработали
        raise events.StopPropagation

    @bot_client.on(events.CallbackQuery(func=lambda e: e.sender_id != MY_ID))
    async def vpn_callback_handler(event):
        """Обработка нажатий на кнопки от клиентов"""
        from telethon.errors import MessageNotModifiedError
        
        data = event.data.decode('utf-8')

        try:
            if data == "vpn_tariffs":
                keyboard = [
                    [Button.inline("💳 1 Месяц — 150 ₽", b"pay_1")],
                    [Button.inline("💳 3 Месяца — 400 ₽", b"pay_3")],
                    [Button.inline("◀️ Назад", b"vpn_back")]
                ]
                await event.edit(
                    "📂 **[ УРОВНИ ДОСТУПА ]**\n\n"
                    "Выберите период активации ключа. После оплаты система мгновенно сгенерирует ваш уникальный VLESS-токен.",
                    buttons=keyboard
                )

            elif data == "vpn_info":
                keyboard = [[Button.inline("◀️ Назад", b"vpn_back")]]
                await event.edit(
                    "ℹ️ **[ СПЕЦИФИКАЦИЯ ]**\n\n"
                    "Мы не используем устаревшие протоколы (OpenVPN, Wireguard). "
                    "Ваш трафик маскируется под обычные запросы к серверам Microsoft, "
                    "что делает его невидимым для провайдеров.\n\n"
                    "Поддерживаются устройства на iOS, Android, Windows и macOS.",
                    buttons=keyboard
                )

            elif data == "vpn_back":
                keyboard = [
                    [Button.inline("🚀 Получить доступ", b"vpn_tariffs")],
                    [Button.inline("❔ Как это работает", b"vpn_info")]
                ]
                await event.edit("🌌 **[ ОЖИДАНИЕ ВВОДА ]**\n\nВыберите действие:", buttons=keyboard)

            elif data.startswith("pay_"):
                # Заглушка для системы оплаты
                months = data.split("_")[1]
                keyboard = [
                    [Button.inline("✅ Я оплатил", f"checkpay_{months}".encode())],
                    [Button.inline("◀️ Отмена", b"vpn_tariffs")]
                ]
                await event.edit(
                    f"⏳ **[ ИНИЦИАЛИЗАЦИЯ ТРАНЗАКЦИИ ]**\n\n"
                    f"Переведите сумму по номеру: `+7 (999) 000-00-00` (СБП).\n"
                    f"В комментарии ничего указывать не нужно.\n\n"
                    f"После перевода нажмите кнопку ниже для генерации ключа.",
                    buttons=keyboard
                )

            elif data.startswith("checkpay_"):
                # Проверка оплаты и генерация ключа через Marzban API
                months = int(data.split("_")[1])
                sender_id = event.sender_id

                try:
                    # Отправляем сообщение о проверке
                    processing_msg = await event.get_message()
                    await event.edit(
                        "⏳ **[ ГЕНЕРАЦИЯ КЛЮЧА ]**\n\n"
                        "Соединение с сервером...\n"
                        "Генерация криптографического ключа..."
                    )

                    # Генерируем ключ через Marzban
                    from brains.vpn_api import check_payment_and_issue_key
                    from brains.exceptions import VPNError, VPNUserExistsError, VPNConnectionError

                    result = await check_payment_and_issue_key(sender_id, months)

                    if result.get("success"):
                        vless_key = result.get("vless_key")
                        expire_days = result.get("expire_days", 30)

                        # Генерируем QR-код в памяти
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=10,
                            border=2,
                        )
                        qr.add_data(vless_key)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")

                        # Сохраняем в BytesIO
                        bio = io.BytesIO()
                        bio.name = 'vpn_qr.png'
                        img.save(bio, 'PNG')
                        bio.seek(0)

                        # Формируем текст
                        caption_text = (
                            "🟢 **[ ТРАНЗАКЦИЯ ПОДТВЕРЖДЕНА ]**\n\n"
                            f"Ключ активирован на {expire_days} дней.\n\n"
                            "Ваша ссылка-подписка:\n"
                            f"```\n{vless_key}\n```\n\n"
                            "**Инструкция:**\n"
                            "1. Скачайте Hiddify или V2Box\n"
                            "2. Скопируйте ссылку выше ИЛИ отсканируйте QR-код\n"
                            "3. В приложении выберите 'Добавить из буфера обмена' или 'Сканировать QR'\n\n"
                            "🔐 Добро пожаловать в сеть!"
                        )

                        # Отправляем с QR-кодом
                        await bot_client.send_file(
                            event.chat_id,
                            file=bio,
                            caption=caption_text
                        )
                    else:
                        raise VPNError("Failed to generate key")

                except VPNUserExistsError:
                    # Пользователь уже существует — пробуем получить ключ
                    from brains.vpn_api import marzban_client
                    user_data = await marzban_client.get_user(f"vpn_{sender_id}")

                    if user_data and user_data.get("success"):
                        vless_key = user_data.get('vless_link')
                        
                        # Генерируем QR-код для продления
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=10,
                            border=2,
                        )
                        qr.add_data(vless_key)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")

                        bio = io.BytesIO()
                        bio.name = 'vpn_qr.png'
                        img.save(bio, 'PNG')
                        bio.seek(0)

                        await bot_client.send_file(
                            event.chat_id,
                            file=bio,
                            caption=(
                                "🟢 **[ КЛЮЧ АКТИВИРОВАН ]**\n\n"
                                "Ваш ключ доступа (продление):\n"
                                f"```\n{vless_key}\n```\n\n"
                                "🔐 Подключение восстановлено!"
                            )
                        )
                    else:
                        await event.edit(
                            "🔴 **[ ОШИБКА ]**\n\n"
                            "Пользователь существует, но не удалось получить ключ.\n"
                            "Обратитесь в поддержку: @support"
                        )

                except VPNConnectionError:
                    logger.error("VPN Connection error during key generation")
                    await event.edit(
                        "🔴 **[ ОШИБКА СОЕДИНЕНИЯ ]**\n\n"
                        "Не удалось подключиться к серверу генерации ключей.\n"
                        "Пожалуйста, попробуйте позже или обратитесь в поддержку: @support"
                    )

                except VPNError as e:
                    logger.error(f"VPN error: {e}")
                    await event.edit(
                        "🔴 **[ ОШИБКА ]**\n\n"
                        "Не удалось сгенерировать ключ доступа.\n"
                        f"Детали: {str(e)}\n\n"
                        "Пожалуйста, обратитесь в поддержку: @support"
                    )

                except Exception as e:
                    logger.exception(f"Unexpected error in VPN key generation: {e}")
                    await event.edit(
                        "🔴 **[ НЕИЗВЕСТНАЯ ОШИБКА ]**\n\n"
                        "Произошла непредвиденная ошибка.\n"
                        "Пожалуйста, обратитесь в поддержку: @support"
                    )
        except MessageNotModifiedError:
            # Игнорируем ошибку "сообщение не изменено"
            pass
        except Exception as e:
            logger.exception(f"Unexpected error in VPN callback: {e}")

    # Регистрируем скиллы из модуля skills (после VPN!)
    register_karina_base_skills(bot_client)

    # Запускаем бота
    await bot_client.start(bot_token=KARINA_TOKEN)
    logger.info("✅ Бот запущен")
    await report_status("bot", "running")

    # Определяем твой личный список команд
    commands = [
        types.BotCommand("start", "Перезапустить 🔄"),
        types.BotCommand("app", "Панель управления 📱"),
        types.BotCommand("calendar", "Мои планы 📅"),
        types.BotCommand("conflicts", "Конфликты ⚠️"),
        types.BotCommand("health", "Здоровье ❤️"),
        types.BotCommand("weather", "Погода 🌤"),
        types.BotCommand("news", "Новости телематики 🗞"),
        types.BotCommand("newsforce", "Обновить новости 🔄"),
        types.BotCommand("newssources", "Источники новостей 📡"),
        types.BotCommand("newsclear", "Очистить историю новостей 🧹"),
        types.BotCommand("remember", "Запомнить факт ✍️"),
        types.BotCommand("summary", "Еженедельный отчёт 📊"),
        types.BotCommand("employees", "Сотрудники 👥"),
        types.BotCommand("birthdays", "Дни рождения 🎂"),
        types.BotCommand("habits", "Мои привычки 🎯"),
        types.BotCommand("productivity", "Отчёт о продуктивности 📈"),
        types.BotCommand("workstats", "Статистика работы ⏰"),
        types.BotCommand("overwork", "Проверка переработок ⚠️"),
        types.BotCommand("vision", "Компьютерное зрение 👁️"),
        types.BotCommand("ocr", "Распознать текст на фото 📝"),
        types.BotCommand("analyze", "Анализ изображения 🔍"),
        types.BotCommand("doc", "Анализ документа 📄"),
        types.BotCommand("receipt", "Анализ чека 🧾"),
    ]

    # ========== НАСТРОЙКА ПРИВАТНОСТИ МЕНЮ ==========
    
    # 1. Стираем все команды для обычных пользователей (Default)
    await bot_client(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(),
        lang_code='',
        commands=[]
    ))
    
    # Убираем большую кнопку "Меню/Mini App" слева от поля ввода для чужих
    await bot_client(functions.bots.SetBotMenuButtonRequest(
        user_id=types.InputUserEmpty(),
        button=types.BotMenuButtonCommands()
    ))

    # 2. Устанавливаем твои роскошные команды ТОЛЬКО для тебя
    my_peer = await bot_client.get_input_entity(MY_ID)

    await bot_client(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopePeer(peer=my_peer),
        lang_code='ru',
        commands=commands
    ))
    
    # Выдаем тебе кнопку запуска Mini App (слева от поля ввода)
    await bot_client(functions.bots.SetBotMenuButtonRequest(
        user_id=my_peer,
        button=types.BotMenuButton(
            text="Карина App 📱",
            url="https://tg-emoji-status-bot-production.up.railway.app/"
        )
    ))
    # ================================================
    
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
    
    # Регистрация детектора ID эмодзи
    from skills import register_discovery_skills
    register_discovery_skills(user_client)
    
    from brains.config import MY_ID
    reminder_manager.set_client(bot_client, MY_ID)
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
        # Создаем таски для wait
        client_task = asyncio.create_task(user_client.run_until_disconnected())
        shutdown_task = asyncio.create_task(SHUTDOWN_EVENT.wait())
        
        done, pending = await asyncio.wait(
            [client_task, shutdown_task],
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

    # ========== ИНИЦИАЛИЗАЦИЯ ПЛАГИНОВ ==========
    logger.info("📦 Инициализация системы плагинов...")
    plugin_manager.load_config()
    
    # Находим и загружаем все доступные плагины
    discovered = plugin_manager.discover_plugins()
    for plugin_name in discovered:
        plugin = plugin_manager.load_plugin(plugin_name)
        if plugin:
            plugin_manager.register_plugin(plugin)
    
    # Инициализируем включенные плагины
    await plugin_manager.initialize_all()
    logger.info(f"✅ Загружено {len(plugin_manager.get_enabled_plugins())} активных плагинов")
    # ===========================================

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

        # Остановка плагинов
        await plugin_manager.shutdown_all_hooks()
        await plugin_manager.shutdown_all()

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
