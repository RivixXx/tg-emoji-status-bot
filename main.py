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
from brains.mcp_vpn_shop import (
    mcp_vpn_get_user,
    mcp_vpn_create_user,
    mcp_vpn_update_user_state,
    mcp_vpn_add_referral,
    mcp_vpn_get_referral_stats,
    mcp_vpn_create_order,
    mcp_vpn_update_order,
    mcp_vpn_update_balance,
    calculate_referral_commission
)
from brains.vpn_ui import (
    get_main_menu_text,
    get_main_menu_keyboard,
    get_profile_text,
    get_tariffs_text,
    get_tariffs_keyboard,
    get_instructions_text,
    get_instruction_platform_text,
    get_platform_keyboard,
    get_referral_text,
    get_referral_keyboard,
    get_support_text,
    get_support_keyboard,
    get_support_write_keyboard,
    get_faq_main_text,
    get_faq_main_keyboard,
    get_faq_what_text,
    get_faq_what_keyboard,
    get_faq_connect_text,
    get_faq_connect_keyboard,
    get_faq_devices_text,
    get_faq_devices_keyboard,
    get_faq_russia_text,
    get_faq_russia_keyboard,
    get_faq_speed_text,
    get_faq_speed_keyboard,
    get_faq_security_text,
    get_faq_security_keyboard,
    get_faq_tips_main_text,
    get_faq_tips_keyboard,
    get_faq_anon_text,
    get_faq_anon_keyboard,
    get_faq_leak_text,
    get_faq_leak_keyboard,
    get_faq_metadata_text,
    get_faq_metadata_keyboard,
    get_download_text,
    get_download_keyboard,
    get_balance_text,
    get_balance_keyboard,
    get_payment_keyboard,
    get_back_keyboard,
)
from auras import state, start_auras
from skills import register_karina_base_skills
from plugins import plugin_manager

# ========== FIRE-AND-FORGET (ДИСПЕТЧЕР ФОНОВЫХ ЗАДАЧ) ==========

# Безопасное хранилище для фоновых задач (чтобы Python их не удалил до завершения)
background_tasks = set()

def fire_and_forget(coro):
    """
    Запускает асинхронную функцию в фоне. 
    Бот не ждет её выполнения и мгновенно идет дальше.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # Если цикла нет, ничего не делаем

    # Создаем задачу
    task = loop.create_task(coro)
    
    # Сохраняем надежную ссылку
    background_tasks.add(task)
    
    # Как только задача выполнится (успешно или с ошибкой) - удаляем её из памяти
    task.add_done_callback(background_tasks.discard)
    
    # Если в фоне произойдет ошибка, выводим её в лог, чтобы бот не упал молча
    def log_error(t):
        if t.exception():
            err_msg = str(t.exception())
            # Игнорируем временные ошибки блокировки БД
            if "database is locked" in err_msg:
                logging.warning(f"⚠️ БД заблокирована (retry через 2с): {err_msg}")
            else:
                logging.error(f"⚠️ Ошибка в фоновой задаче: {err_msg}")
    
    task.add_done_callback(log_error)

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
    
    # ========== КЭШ ДЛЯ СКОРОСТИ (УРОВЕНЬ 1) ==========
    USER_CACHE = {}
    CACHE_TTL = 300 # Храним данные в памяти 5 минут (300 секунд)

    async def get_user_fast(user_id):
        """Мгновенно отдает юзера из памяти или запрашивает из БД"""
        now = time.time()
        # Если юзер есть в кэше и данные свежие — отдаем за миллисекунду
        if user_id in USER_CACHE and (now - USER_CACHE[user_id]['time'] < CACHE_TTL):
            return USER_CACHE[user_id]['data']
        
        # Если в кэше нет — идем в БД Supabase
        user = await mcp_vpn_get_user(user_id)
        if user:
            USER_CACHE[user_id] = {'data': user, 'time': now}
        return user

    def update_user_cache(user_id, updates):
        """Обновляет кэш локально, чтобы не ждать ответа базы"""
        if user_id in USER_CACHE:
            USER_CACHE[user_id]['data'].update(updates)
            USER_CACHE[user_id]['time'] = time.time()
    # ==================================================
    
    # ========== VPN SHOP LOGIC (ДВОЙНОЕ ДНО + ВОРОНКА ПРОДАЖ) ==========
    # Регистрируем ПЕРЕД скиллами чтобы перехватывал сообщения от чужих ID

    # Debug handler - логирует ВСЕ сообщения
    @bot_client.on(events.NewMessage())
    async def debug_all_messages(event):
        """Логирует все сообщения для отладки"""
        logger.info(f"📩 DEBUG: message from {event.sender_id} (MY_ID={MY_ID}), text='{event.text}'")
    
    # Используем Supabase через MCP вместо временного словаря
    # Состояния: NEW, WAITING_EMAIL, WAITING_CODE, REGISTERED

    def get_main_menu():
        """Возвращает клавиатуру главного меню (как на скриншоте OverSecure)"""
        return [
            [Button.text("👤 Профиль"), Button.text("💳 Баланс")],
            [Button.text("🛒 Тарифы (Магазин)"), Button.text("👥 Рефералы")],
            [Button.text("📖 Инструкция (FAQ)"), Button.text("🆘 Поддержка")]
        ]

    @bot_client.on(events.NewMessage(func=lambda e: e.is_private and e.sender_id != MY_ID))
    async def vpn_stranger_interceptor(event):
        """Перехватывает текстовые сообщения от чужих ID и ведет по воронке"""
        user_id = event.sender_id
        text = event.text.strip() if event.text else ""
        
        # Логирование для отладки
        logger.info(f"🔍 VPN Interceptor CAUGHT: user_id={user_id} (MY_ID={MY_ID}), text='{text}'")

        # Получаем или создаём пользователя
        user = await get_user_fast(user_id)
        if not user:
            # Проверяем есть ли реферер в /start
            referred_by = None
            if event.text and event.text.startswith('/start') and len(event.text.split()) > 1:
                try:
                    referred_by = int(event.text.split()[1])
                except (ValueError, IndexError):
                    pass
            
            user = await mcp_vpn_create_user(user_id, referred_by=referred_by)
            if not user:
                logger.error(f"❌ Failed to create VPN user {user_id}")
                await event.respond("⚠️ Ошибка при регистрации. Попробуйте позже.")
                raise events.StopPropagation
        
        state = user["state"]
        logger.info(f"✅ User {user_id} state: {state}")

        # ШАГ 1: Приветствие и Оферта (реагируем на /start или любое первое слово)
        if state == "NEW":
            welcome_text = (
                "📄 **Публичная оферта**\n\n"
                "Перед регистрацией ознакомьтесь с условиями использования сервиса:\n\n"
                "• Сайт — `Скоро!!!`\n"
                "• Товар — доступ к виртуальной частной сети на определённый срок\n"
                "• Все полученные данные и настройки доступа являются конфиденциальными\n"
                "• Запрещено использование сервиса в незаконных целях\n"
                "• Продавец не несёт ответственности за ненадлежащее использование товара\n"
                "• После оказания услуги надлежащего качества возврат средств не производится\n"
                "• Оператор гарантирует доступность подключения на уровне 99,0% в месяц\n\n"
                "Полный текст оферты доступен на сайте: https://твой-домен.pro/\n\n"
                "Нажимая «Принимаю условия», вы подтверждаете, что ознакомились и согласны с условиями публичной оферты."
            )
            keyboard = [
                [Button.inline("✅ Принимаю условия", b"accept_offer")],
                [Button.inline("❌ Отменить", b"decline_offer")]
            ]
            await event.respond(welcome_text, buttons=keyboard)
            raise events.StopPropagation

        # ШАГ 2: Обработка ввода Email
        elif state == "WAITING_EMAIL":
            # Простая проверка на формат почты
            if re.match(r"[^ @]+@[^ @]+\.[^ @]+", text):
                # Генерируем код (4 цифры)
                code = str(random.randint(1000, 9999))

                # Мгновенно обновляем кэш
                update_user_cache(user_id, {"state": "WAITING_CODE", "email": text, "verification_code": code})
                
                # Сохраняем в БД в фоне (Fire-and-Forget)
                fire_and_forget(mcp_vpn_update_user_state(user_id, "WAITING_CODE", email=text, code=code))

                # В будущем здесь будет реальная отправка email.
                # Пока для теста выводим код прямо в чат!
                await event.respond(
                    f"✅ **Код отправлен на вашу почту: {text}**\n\n"
                    f"*(ДЛЯ ТЕСТА - ТВОЙ КОД: {code})*\n\n"
                    f"🔑 Введите 4 цифры из письма:"
                )
            else:
                await event.respond("⚠️ Некорректный формат email. Пожалуйста, введите правильный адрес:")
            raise events.StopPropagation

        # ШАГ 3: Обработка ввода Кода
        elif state == "WAITING_CODE":
            if text == user["verification_code"]:
                # Мгновенно обновляем кэш
                update_user_cache(user_id, {"state": "REGISTERED"})
                
                # Сохраняем в БД в фоне (Fire-and-Forget)
                fire_and_forget(mcp_vpn_update_user_state(user_id, "REGISTERED"))
                
                await event.respond(
                    "🎉 **[ ДОСТУП РАЗРЕШЕН ]**\n\nАккаунт успешно создан! Можете пользоваться терминалом.",
                    buttons=get_main_menu()
                )

                # Если есть реферер — начисляем комиссию в фоне
                if user.get("referred_by"):
                    referrer_id = user["referred_by"]
                    fire_and_forget(mcp_vpn_add_referral(referrer_id, user_id, commission=0))
                    logger.info(f"✅ Referral registered: {referrer_id} -> {user_id}")
            else:
                await event.respond("❌ Неверный код. Попробуйте еще раз:")
            raise events.StopPropagation

        # ШАГ 4: Главное меню (Пользователь зарегистрирован)
        elif state == "REGISTERED":
            # Отправляем с баннером
            try:
                await event.respond(
                    file="banners/menu.jpg",
                    caption=get_main_menu_text(user),
                    buttons=get_main_menu_keyboard()
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить баннер меню: {e}")
                await event.respond(
                    get_main_menu_text(user),
                    buttons=get_main_menu_keyboard()
                )
            raise events.StopPropagation


    @bot_client.on(events.CallbackQuery(func=lambda e: e.sender_id != MY_ID))
    async def vpn_callback_handler(event):
        """Обработка нажатий на inline-кнопки (под сообщениями)"""
        user_id = event.sender_id
        data = event.data.decode('utf-8')

        # Получаем пользователя из кэша или БД
        user = await get_user_fast(user_id)
        if not user:
            # Если пользователя нет в базе — создаём
            await mcp_vpn_create_user(user_id)
            user = await get_user_fast(user_id)
            if not user:
                await event.answer("⚠️ Ошибка. Попробуйте /start", alert=True)
                return

        if data == "accept_offer":
            # Мгновенно обновляем память
            update_user_cache(user_id, {"state": "WAITING_EMAIL"}) 
            
            # Кидаем сохранение в облако в фон (Без await!)
            fire_and_forget(mcp_vpn_update_user_state(user_id, "WAITING_EMAIL"))
            
            # И в ту же миллисекунду отдаем текст юзеру!
            await event.edit("📧 **Для регистрации в системе необходим Email.**\n\nПожалуйста, введите вашу почту отправьте сообщением:")

        elif data == "decline_offer":
            # Обновляем кэш локально
            update_user_cache(user_id, {"state": "NEW"})
            # Сохраняем в БД в фоне
            fire_and_forget(mcp_vpn_update_user_state(user_id, "NEW"))
            
            await event.edit("❌ Регистрация отменена. Чтобы начать заново, отправьте любое сообщение.")
            
        elif data.startswith("pay_"):
            months = data.split("_")[1]
            keyboard = [
                [Button.inline("✅ Я оплатил", f"checkpay_{months}".encode())],
                [Button.inline("◀️ Отмена", b"cancel_pay")]
            ]
            await event.edit(
                f"⏳ **[ ИНИЦИАЛИЗАЦИЯ ТРАНЗАКЦИИ ]**\n\n"
                f"Переведите сумму по номеру: `+7 (999) 000-00-00` (СБП).\n\n"
                f"После перевода нажмите кнопку ниже для генерации ключа.",
                buttons=keyboard
            )
            
        elif data.startswith("checkpay_"):
            # Проверка оплаты и генерация ключа через Marzban API
            months = int(data.split("_")[1])
            sender_id = event.sender_id
            
            # Рассчитываем сумму
            amount = 150 if months == 1 else 400

            try:
                # Отправляем сообщение о проверке
                await event.edit(
                    "⏳ **[ ГЕНЕРАЦИЯ КЛЮЧА ]**\n\n"
                    "Соединение с сервером...\n"
                    "Генерация криптографического ключа..."
                )

                # Создаём заказ в БД (в фоне, чтобы не ждать)
                fire_and_forget(mcp_vpn_create_order(sender_id, months, amount))

                # Генерируем ключ через Marzban
                from brains.vpn_api import check_payment_and_issue_key
                from brains.exceptions import VPNError, VPNUserExistsError, VPNConnectionError

                result = await check_payment_and_issue_key(sender_id, months)

                if result.get("success"):
                    vless_key = result.get("vless_key")
                    expire_days = result.get("expire_days", 30)

                    # Начисляем комиссию рефереру (10%) в фоне
                    user = await get_user_fast(sender_id)
                    if user and user.get("referred_by"):
                        referrer_id = user["referred_by"]
                        commission = calculate_referral_commission(amount)
                        fire_and_forget(mcp_vpn_add_referral(referrer_id, sender_id, commission=commission))
                        logger.info(f"💰 Commission {commission}₽ accrued to {referrer_id}")

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
                    

                    # Обновляем заказ
                    if order:
                        await mcp_vpn_update_order(order['id'], "completed", vless_key=vless_key)

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
                
        elif data == "cancel_pay":
            await event.edit("❌ Оплата отменена. Выберите другой тариф или обратитесь в поддержку.")
            
        elif data == "refill_sbp":
            await event.edit(
                "💰 **ПОПОЛНЕНИЕ БАЛАНСА (СБП)**\n\n"
                "Переведите нужную сумму по номеру:\n"
                "`+7 (999) 000-00-00`\n\n"
                "В комментарии укажите ваш ID: `{}`\n\n"
                "После перевода нажмите '✅ Я оплатил'".format(user_id),
                buttons=[[Button.inline("✅ Я оплатил", b"refill_confirm")]]
            )
            
        elif data == "refill_crypto":
            await event.edit(
                "💰 **ПОПОЛНЕНИЕ БАЛАНСА (CRYPTO)**\n\n"
                "Отправьте USDT (TRC20) на адрес:\n"
                "`TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`\n\n"
                "Минимальная сумма: 10 USDT\n\n"
                "После отправки напишите в поддержку @support с указанием суммы и вашего ID."
            )
            
        elif data == "refill_confirm":
            await event.edit("⏳ **ПРОВЕРКА ПЛАТЕЖА**\n\nВаш запрос отправлен на проверку.")

        # ========== НОВОЕ INLINE-МЕНЮ ==========
        
        elif data == "menu_main" or data == "menu_back":
            # Отправляем с баннером
            try:
                await bot_client.send_file(
                    event.chat_id,
                    file="banners/menu.jpg",
                    caption=get_main_menu_text(user),
                    buttons=get_main_menu_keyboard()
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить баннер меню: {e}")
                await event.edit(get_main_menu_text(user), buttons=get_main_menu_keyboard())

        elif data == "menu_profile":
            await event.edit(get_profile_text(user), buttons=get_back_keyboard(main=True))

        elif data == "menu_tariffs":
            await event.edit(get_tariffs_text(), buttons=get_tariffs_keyboard())

        elif data == "menu_balance":
            await event.edit(get_balance_text(user), buttons=get_balance_keyboard())

        elif data == "menu_download":
            await event.edit(get_download_text(), buttons=get_download_keyboard())

        elif data == "menu_instructions":
            # Отправляем с баннером
            try:
                await bot_client.send_file(
                    event.chat_id,
                    file="banners/instructions.jpg",
                    caption=get_instructions_text(),
                    buttons=get_platform_keyboard()
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить баннер инструкций: {e}")
                await event.edit(get_instructions_text(), buttons=get_platform_keyboard())

        elif data == "instr_android":
            await event.edit(get_instruction_platform_text("android"), buttons=[
                [Button.inline("📥 Скачать", url="https://play.google.com/store/apps/details?id=app.hiddify.com")],
                [Button.inline("◀️ Назад", b"menu_instructions")],
                [Button.inline("🏠 Главное меню", b"menu_main")],
            ])

        elif data == "instr_ios":
            await event.edit(get_instruction_platform_text("ios"), buttons=[
                [Button.inline("📥 Скачать", url="https://apps.apple.com/app/hiddify-proxy/id6505229441")],
                [Button.inline("◀️ Назад", b"menu_instructions")],
                [Button.inline("🏠 Главное меню", b"menu_main")],
            ])

        elif data == "instr_windows":
            await event.edit(get_instruction_platform_text("windows"), buttons=[
                [Button.inline("📥 Скачать", url="https://github.com/hiddify/hiddify-next/releases")],
                [Button.inline("◀️ Назад", b"menu_instructions")],
                [Button.inline("🏠 Главное меню", b"menu_main")],
            ])

        elif data == "instr_macos":
            await event.edit(get_instruction_platform_text("macos"), buttons=[
                [Button.inline("◀️ Назад", b"menu_instructions")],
                [Button.inline("🏠 Главное меню", b"menu_main")],
            ])

        elif data == "menu_referral":
            stats = await mcp_vpn_get_referral_stats(user_id)
            await event.edit(get_referral_text(user, stats), buttons=get_referral_keyboard())

        elif data == "ref_copy":
            referral_link = f"https://t.me/your_bot?start={user_id}"
            await event.answer(f"📋 Ссылка скопирована:\n{referral_link}", alert=True)

        # ========== FAQ ==========
        
        elif data == "menu_faq":
            await event.edit(get_faq_main_text(), buttons=get_faq_main_keyboard())

        elif data == "faq_what":
            await event.edit(get_faq_what_text(), buttons=get_faq_what_keyboard())

        elif data == "faq_connect":
            await event.edit(get_faq_connect_text(), buttons=get_faq_connect_keyboard())

        elif data == "faq_devices":
            await event.edit(get_faq_devices_text(), buttons=get_faq_devices_keyboard())

        elif data == "faq_russia":
            await event.edit(get_faq_russia_text(), buttons=get_faq_russia_keyboard())

        elif data == "faq_speed":
            await event.edit(get_faq_speed_text(), buttons=get_faq_speed_keyboard())

        elif data == "faq_security":
            await event.edit(get_faq_security_text(), buttons=get_faq_security_keyboard())

        elif data == "faq_tips":
            await event.edit(get_faq_tips_main_text(), buttons=get_faq_tips_keyboard())

        elif data == "faq_anon":
            await event.edit(get_faq_anon_text(), buttons=get_faq_anon_keyboard())

        elif data == "faq_leak":
            await event.edit(get_faq_leak_text(), buttons=get_faq_leak_keyboard())

        elif data == "faq_metadata":
            await event.edit(get_faq_metadata_text(), buttons=get_faq_metadata_keyboard())

        # ========== ПОДДЕРЖКА ==========
        
        elif data == "menu_support":
            # Отправляем с баннером
            try:
                await bot_client.send_file(
                    event.chat_id,
                    file="banners/support.jpg",
                    caption=get_support_text(),
                    buttons=get_support_keyboard()
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить баннер поддержки: {e}")
                await event.edit(get_support_text(), buttons=get_support_keyboard())

        elif data == "support_write":
            await event.edit(get_support_write_text(), buttons=get_support_write_keyboard())

        else:
            await event.answer("👌 Ок!", alert=False)
    # ==================================================

    # Запускаем бота
    await bot_client.start(bot_token=KARINA_TOKEN)
    logger.info("✅ Бот запущен")
    await report_status("bot", "running")

    # Включаем мозг и базовые навыки Карины для твоего MY_ID!
    register_karina_base_skills(bot_client)
    logger.info("🧠 Скиллы Карины успешно подключены")

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
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error("🔴 Порт 8080 занят! Завершение...")
        else:
            raise
    finally:
        logger.info("🔌 Завершение работы...")
        SHUTDOWN_EVENT.set()

        # Остановка плагинов
        await plugin_manager.shutdown_all_hooks()
        await plugin_manager.shutdown_all()

        sh_task.cancel()
        await asyncio.gather(bot_supervisor, user_supervisor, sh_task, return_exceptions=True)

        # Безопасное отключение с обработкой блокировки БД
        if bot_client.is_connected():
            try:
                await bot_client.disconnect()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при отключении бота: {e}")
        
        if user_client.is_connected():
            try:
                await user_client.disconnect()
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при отключении юзербота: {e}")

        logger.info("👋 Karina AI остановлена.")

if __name__ == '__main__':

    
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
