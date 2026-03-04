"""
KARINA AI — Dual Mode Bot
- Владелец (MY_ID): Персональный AI-ассистент (календарь, здоровье, напоминания, новости)
- Клиенты: VPN Shop (inline, кэш баннеров, QR-коды)
"""
import os
import asyncio
import logging
import signal
import time
import httpx
import qrcode
import io
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, functions, types, errors
from dotenv import load_dotenv

load_dotenv()

# ========== КОНФИГ ==========
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('KARINA_BOT_TOKEN', '')
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0))
MISTRAL_KEY = os.environ.get('MISTRAL_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
MARZBAN_URL = os.environ.get('MARZBAN_URL', 'http://127.0.0.1:8000')
MARZBAN_USER = os.environ.get('MARZBAN_USER', 'admin')
MARZBAN_PASS = os.environ.get('MARZBAN_PASS', '')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID]):
    logger.error("❌ ЗАПОЛНИ .env")
    exit(1)

# ========== КЛИЕНТЫ ==========
bot = TelegramClient('bot_session', API_ID, API_HASH)
http = httpx.AsyncClient(timeout=30.0)

# ========== КЭШ БАННЕРОВ ==========
CACHED_BANNERS = {}
BANNER_PATHS = {
    "menu": "banners/menu.jpg",
    "support": "banners/support.jpg",
    "instructions": "banners/instructions.jpg",
    "profile": "banners/menu.jpg",
    "shop": "banners/menu.jpg"
}

# ========== VPN USERS ==========
VPN_USERS = {}

# ========== УТИЛИТЫ ==========
def log_timing(step_name: str, start_time: float):
    elapsed = (time.time() - start_time) * 1000
    logger.info(f"⏱ {step_name}: {elapsed:.2f}ms")

# ========== VPN SHOP — ФУНКЦИИ ==========
# Inline кнопки
def inline_main_menu():
    return [
        [Button.inline("💎 Тарифы", b"shop_tariffs"), Button.inline("🎁 Тест", b"trial_activate")],
        [Button.inline("👤 Профиль", b"profile_menu"), Button.inline("📖 Инструкции", b"instructions_menu")],
        [Button.inline("💬 Поддержка", b"support_menu"), Button.inline("❓ FAQ", b"faq_menu")]
    ]

def inline_back():
    return [[Button.inline("◀️ Назад", b"main_menu")]]

def inline_tariffs():
    return [
        [Button.inline("1 мес — 150₽", b"tariff_1"), Button.inline("3 мес — 400₽", b"tariff_3")],
        [Button.inline("6 мес — 750₽", b"tariff_6")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]

def inline_profile(has_keys=False):
    buttons = [
        [Button.inline("🔑 Ключи", b"my_keys"), Button.inline("💳 Баланс", b"balance")],
        [Button.inline("📜 История", b"history")]
    ]
    if has_keys:
        buttons.insert(0, [Button.inline("⚡ Продлить", b"shop_tariffs")])
    buttons.append([Button.inline("◀️ Назад", b"main_menu")])
    return buttons

def inline_instructions():
    return [
        [Button.inline("📱 iOS", b"instr_ios"), Button.inline("🤖 Android", b"instr_android")],
        [Button.inline("💻 Windows", b"instr_windows"), Button.inline("🍎 macOS", b"instr_macos")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]

def inline_support():
    return [
        [Button.inline("✍️ Задать вопрос", b"support_ask")],
        [Button.inline("❓ FAQ", b"faq_menu")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]

# Тексты
def text_welcome(user_id):
    return f"╔═══════════════════════╗\n║     🌌  **KARINA VPN**  🌌     ║\n╚═══════════════════════╝\n\n👤 **Абонент:** `{user_id}`\n🔐 **Статус:** `Активен`\n\nДобро пожаловать в Karina VPN Shop.\n\nВыберите раздел:"

def text_profile(user_id, user_data):
    keys_count = len(user_data.get("keys", []))
    return f"╔═══════════════════════╗\n║       👤  **ПРОФИЛЬ**  👤      ║\n╚═══════════════════════╝\n\n🆔 **ID:** `{user_id}`\n💳 **Баланс:** `{user_data.get('balance', 0)}₽`\n🎁 **Тест:** `{'Использован' if user_data.get('trial_used') else 'Доступен'}`\n📅 **В сервисе:** `{user_data.get('joined', datetime.now()).strftime('%d.%m.%Y')}`\n\n🔑 **Ключи:** `{keys_count}`"

def text_tariffs():
    return f"╔═══════════════════════╗\n║        💎  **ТАРИФЫ**  💎      ║\n╚═══════════════════════╝\n\n**1 месяц — 150₽**\n• 3 ключа\n• Безлимитный трафик\n\n**3 месяца — 400₽** (выгода 50₽)\n\n**6 месяцев — 750₽** (выгода 150₽)"

def text_payment(amount, months):
    return f"╔═══════════════════════╗\n║      💳  **ОПЛАТА**  💳        ║\n╚═══════════════════════╝\n\n💰 **Сумма:** `{amount}₽`\n📅 **Период:** `{months} мес.`\n\n💳 **Тестовый режим:**\nКлюч будет выдан сразу."

def text_keys(keys):
    if not keys:
        return "📭 У вас пока нет ключей."
    text = "╔═══════════════════════╗\n║     🔑  **ВАШИ КЛЮЧИ**  🔑     ║\n╚═══════════════════════╝\n\n"
    for i, key in enumerate(keys, 1):
        device = key.get("device", "Устройство")
        expire = key.get("expire", datetime.now()).strftime('%d.%m.%Y')
        key_short = key.get("key", "N/A")[:50] + "..."
        text += f"**{i}. {device}** (до {expire})\n`{key_short}`\n\n"
    return text

# Баннеры
async def get_cached_banner(banner_name: str):
    if banner_name in CACHED_BANNERS:
        logger.info(f"⚡ Баннер '{banner_name}' из кэша")
        return CACHED_BANNERS[banner_name]
    
    file_path = BANNER_PATHS.get(banner_name)
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"⚠️ Баннер '{banner_name}' не найден")
        return None
    
    try:
        logger.warning(f"⚠️ Первая загрузка баннера '{banner_name}'...")
        start = time.time()
        msg = await bot.send_file(MY_ID, file=file_path)
        CACHED_BANNERS[banner_name] = msg.media
        elapsed = time.time() - start
        logger.info(f"✅ Баннер '{banner_name}' загружен за {elapsed:.2f}с")
        return msg.media
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки баннера: {e}")
        return None

async def send_banner(event, banner_name: str, caption: str, buttons, user_id):
    banner_media = await get_cached_banner(banner_name)
    try:
        if isinstance(event, events.CallbackQuery.Event):
            if banner_media:
                await event.edit(caption, buttons=buttons, file=banner_media, parse_mode='md')
            else:
                await event.edit(caption, buttons=buttons, parse_mode='md')
        else:
            if banner_media:
                await bot.send_file(event.chat_id, file=banner_media, caption=caption, buttons=buttons, parse_mode='md')
            else:
                await event.respond(caption, buttons=buttons, parse_mode='md')
    except errors.MessageNotModifiedError:
        pass
    except Exception as e:
        logger.error(f"❌ Ошибка баннера: {e}")
        await event.respond(caption, buttons=buttons, parse_mode='md')

# Marzban
async def get_marzban_token():
    start = time.time()
    try:
        resp = await http.post(f"{MARZBAN_URL}/api/admin/token", data={"username": MARZBAN_USER, "password": MARZBAN_PASS})
        log_timing("Marzban: токен", start)
        if resp.status_code == 200:
            return resp.json().get("access_token")
        return None
    except Exception as e:
        logger.error(f"❌ Marzban token: {e}")
        return None

async def create_marzban_user(username: str, days: int = 30):
    start = time.time()
    logger.info(f"🔧 Marzban: создание {username} на {days} дн.")
    token = await get_marzban_token()
    if not token:
        return None
    try:
        expire = int((datetime.now() + timedelta(days=days)).timestamp())
        resp = await http.post(f"{MARZBAN_URL}/api/user", headers={"Authorization": f"Bearer {token}"}, json={"username": username, "inbound_tags": ["VLESS"], "expire": expire, "data_limit": 0})
        log_timing("Marzban: создание", start)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"✅ Marzban: пользователь создан")
            return {"username": data.get("username"), "vless": data.get("links", {}).get("VLESS", ""), "expire": datetime.fromtimestamp(expire)}
        logger.error(f"❌ Marzban: {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"❌ Marzban error: {e}")
        return None

async def generate_vless_key(user_id: int, days: int = 1, device: str = "phone"):
    start = time.time()
    device_map = {"Телефон": "phone", "Ноутбук": "laptop", "Планшет": "tablet", "Тест": "trial"}
    device_en = device_map.get(device, device.lower().replace(" ", "_"))
    username = f"vpn_{user_id}_{int(time.time())}_{device_en}"[:32]
    user_data = await create_marzban_user(username, days)
    if user_data:
        log_timing("Генерация ключа", start)
        return {"key": user_data["vless"], "username": user_data["username"], "expire": user_data["expire"], "device": device, "days": days}
    return None

# ========== ИМПОРТЫ МОДУЛЕЙ ==========
# AI и память
from brains.ai import ask_karina

# Календарь
from brains.calendar import get_upcoming_events

# Здоровье
from brains.health import get_health_report_text

# Напоминания
from brains.reminders import reminder_manager, start_reminder_loop, ReminderType, Reminder

# Новости
from brains.news import get_latest_news

# Сотрудники
from brains.employees import get_todays_birthdays, get_upcoming_birthdays

# ========== ГЛОБАЛЬНЫЕ СОСТОЯНИЯ ==========
SHUTDOWN_EVENT = asyncio.Event()

# ========== ХЭНДЛЕРЫ ВЛАДЕЛЬЦА (AI) ==========

@bot.on(events.NewMessage(chats=MY_ID))
async def owner_chat_handler(event):
    """Обработка сообщений от владельца (AI Карина)"""
    text = event.text.strip()
    
    # Игнорируем команды (они обрабатываются отдельно)
    if text.startswith('/'):
        return
    
    start = time.time()
    logger.info(f"💬 Сообщение от владельца: {text[:50]}")
    
    # Запрос к AI
    async with bot.action(MY_ID, 'typing'):
        response = await ask_karina(text, chat_id=MY_ID)
    
    await event.respond(response)
    elapsed = (time.time() - start) * 1000
    logger.info(f"⏱ AI ответ за {elapsed:.2f}ms")

# ========== ХЭНДЛЕРЫ КЛИЕНТОВ (VPN SHOP) ==========

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info("=" * 60)
    logger.info(f"📥 /start от {user_id}")
    
    if user_id == MY_ID:
        await event.respond("👋 Привет, Михаил! Я Карина, твой AI-ассистент.\n\n💬 Пиши — отвечу!\n⚙️ Команды: /help")
        return
    
    # Клиент — VPN магазин
    if user_id not in VPN_USERS:
        VPN_USERS[user_id] = {"state": "NEW", "trial_used": False, "balance": 0, "keys": [], "joined": datetime.now()}
    
    await send_banner(event, "menu", text_welcome(user_id), inline_main_menu(), user_id)
    log_timing("Обработка /start", start_time)

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    start_time = time.time()
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    logger.info(f"📥 Кнопка '{data}' от {user_id}")
    
    # Владелец — игнорируем (у него свои команды)
    if user_id == MY_ID:
        await event.answer("⚙️ Это для клиентов", alert=True)
        return
    
    if user_id not in VPN_USERS:
        VPN_USERS[user_id] = {"state": "NEW", "trial_used": False, "balance": 0, "keys": [], "joined": datetime.now()}
    
    user = VPN_USERS[user_id]
    
    # Навигация
    if data == "main_menu":
        await send_banner(event, "menu", text_welcome(user_id), inline_main_menu(), user_id)
    
    elif data == "profile_menu":
        await send_banner(event, "profile", text_profile(user_id, user), inline_profile(len(user.get("keys", [])) > 0), user_id)
    
    elif data == "shop_tariffs":
        await send_banner(event, "shop", text_tariffs(), inline_tariffs(), user_id)
    
    elif data == "trial_activate":
        if user.get("trial_used"):
            await event.answer("❌ Тест уже использован", alert=True)
        else:
            await event.answer("🎁 Активация...", alert=False)
            key_data = await generate_vless_key(user_id, days=1, device="trial")
            if key_data:
                user["trial_used"] = True
                user["keys"].append(key_data)
                await event.edit(f"🎉 **Тест активирован!**\n\n🔑 Ключ:\n`{key_data['key']}`\n\n⏱ Срок: 24 часа", buttons=inline_back())
            else:
                await event.answer("❌ Ошибка", alert=True)
    
    elif data.startswith("tariff_"):
        months_map = {"tariff_1": (1, 150), "tariff_3": (3, 400), "tariff_6": (6, 750)}
        months, amount = months_map.get(data, (1, 150))
        await send_banner(event, "shop", text_payment(amount, months), [[Button.inline(f"💰 Оплатить {amount}₽", b"pay_confirm")], [Button.inline("◀️ Назад", b"shop_tariffs")]], user_id)
    
    elif data == "pay_confirm":
        await event.answer("⏳ Обработка...", alert=False)
        await asyncio.sleep(2)
        
        months = 1
        keys = []
        for device in ["Телефон", "Ноутбук", "Планшет"]:
            key_data = await generate_vless_key(user_id, days=months * 30, device=device)
            if key_data:
                keys.append(key_data)
        
        if keys:
            user["keys"].extend(keys)
            
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(keys[0]["key"])
            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            bio.name = 'vpn_qr.png'
            img.save(bio, 'PNG')
            bio.seek(0)
            
            caption = f"🟢 **ОПЛАТА ПОДТВЕРЖДЕНА**\n\n🔑 **Ключи:**\n"
            for i, key in enumerate(keys, 1):
                caption += f"\n**{i}. {key['device']}:**\n`{key['key']}`"
            
            await bot.send_file(user_id, file=bio, caption=caption, buttons=inline_profile(True))
        else:
            await event.answer("❌ Ошибка", alert=True)
    
    elif data == "my_keys":
        await send_banner(event, "profile", text_keys(user.get("keys", [])), inline_back(), user_id)
    
    elif data == "balance":
        await event.answer(f"💳 Баланс: {user.get('balance', 0)}₽", alert=True)
    
    elif data == "history":
        await event.answer("📜 История пуста", alert=True)
    
    elif data.startswith("instr_"):
        instr_map = {
            "instr_ios": "📱 iOS: V2RayX → + → Import",
            "instr_android": "🤖 Android: V2RayNG → + → Import",
            "instr_windows": "💻 Windows: v2rayN → Import",
            "instr_macos": "🍎 macOS: Скоро"
        }
        await event.answer(instr_map.get(data, "Гайка..."), alert=True)
    
    else:
        await event.answer("🤔 В разработке", alert=True)
    
    log_timing(f"Обработка '{data}'", start_time)

def log_timing(step_name: str, start_time: float):
    elapsed = (time.time() - start_time) * 1000
    logger.info(f"⏱ {step_name}: {elapsed:.2f}ms")

# ========== ФОНОВЫЕ ЗАДАЧИ ВЛАДЕЛЬЦА ==========

async def owner_background_tasks():
    """Фоновые задачи для владельца"""
    logger.info("🔄 Запуск фоновых задач владельца...")
    
    while not SHUTDOWN_EVENT.is_set():
        try:
            now = datetime.now()
            
            # Утреннее приветствие (7:00)
            if now.hour == 7 and now.minute == 0:
                await bot.send_message(MY_ID, f"☀️ Доброе утро, Михаил!\n\n{await get_latest_news(limit=3, user_id=MY_ID)}")
            
            # Проверка здоровья (22:00)
            if now.hour == 22 and now.minute == 0:
                await bot.send_message(MY_ID, "💉 Михаил, пора сделать укол!\n\nНапиши 'сделал' когда выполнишь.")
            
            # Проверка дней рождения (8:00)
            if now.hour == 8 and now.minute == 0:
                celebrants = await get_todays_birthdays()
                for emp in celebrants:
                    await bot.send_message(MY_ID, f"🎂 Сегодня день рождения у {emp['full_name']}!")
            
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"❌ Ошибка фоновой задачи: {e}")
            await asyncio.sleep(60)

# ========== ЗАПУСК ==========

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    
    # Инициализация напоминаний
    reminder_manager.set_client(bot, MY_ID)
    
    # Запуск цикла напоминаний
    reminders_task = asyncio.create_task(start_reminder_loop())
    
    # Фоновые задачи владельца
    background_task = asyncio.create_task(owner_background_tasks())
    
    logger.info("=" * 60)
    logger.info("🤖 KARINA AI — Dual Mode ЗАПУЩЕН")
    logger.info(f"👤 Владелец: {MY_ID}")
    logger.info(f"🧠 AI: {'✅' if MISTRAL_KEY else '❌'}")
    logger.info(f"🌐 Marzban: {'✅' if MARZBAN_URL else '❌'}")
    logger.info(f"💾 Supabase: {'✅' if SUPABASE_URL else '❌'}")
    logger.info("=" * 60)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
        SHUTDOWN_EVENT.set()
