"""
KARINA VPN SHOP — Production Inline Version
- Кэширование file_id баннеров (мгновенная отправка)
- Inline кнопки (стильно, под сообщением)
- CallbackQuery обработка (вместо текстовых команд)
- Markdown разметка
- Полное логирование
"""
import os
import time
import logging
import asyncio
import httpx
import qrcode
import io
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, errors
from telethon.tl.types import InputMediaDice
from dotenv import load_dotenv

load_dotenv()

# ========== КОНФИГ ==========
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('KARINA_BOT_TOKEN', '')
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0))

# Marzban
MARZBAN_URL = os.environ.get('MARZBAN_URL', 'http://127.0.0.1:8000')
MARZBAN_USER = os.environ.get('MARZBAN_USER', 'admin')
MARZBAN_PASS = os.environ.get('MARZBAN_PASS', '')

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('vpn_shop.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID]):
    logger.error("❌ ЗАПОЛНИ .env: API_ID, API_HASH, KARINA_BOT_TOKEN, MY_TELEGRAM_ID")
    exit(1)

# ========== КЛИЕНТЫ ==========
bot = TelegramClient('bot_session', API_ID, API_HASH)
http = httpx.AsyncClient(timeout=30.0)

# ========== КЭШ БАННЕРОВ (file_id) ==========
# Ключ: имя баннера, Значение: media объект Telegram
CACHED_BANNERS = {}

# Пути к баннерам
BANNER_PATHS = {
    "menu": "banners/menu.jpg",
    "support": "banners/support.jpg",
    "instructions": "banners/instructions.jpg",
    "profile": "banners/menu.jpg",  # Используем menu для профиля
    "shop": "banners/menu.jpg",      # Используем menu для магазина
    "faq": "banners/support.jpg"     # Используем support для FAQ
}

# ========== МЕТРИКИ ==========
METRICS = {
    "total_users": 0,
    "registered_users": 0,
    "trial_activated": 0,
    "purchases": 0,
    "total_revenue": 0
}

# База пользователей (in-memory)
VPN_USERS = {}

# ========== УТИЛИТЫ ==========
def log_timing(step_name: str, start_time: float):
    """Логгирует время выполнения шага"""
    elapsed = (time.time() - start_time) * 1000
    logger.info(f"⏱ {step_name}: {elapsed:.2f}ms")

# ========== INLINE КНОПКИ ==========
def inline_main_menu(is_admin=False):
    """Главное меню inline"""
    keyboard = [
        [Button.inline("💎 Тарифы", b"shop_tariffs"), Button.inline("🎁 Тест", b"trial_activate")],
        [Button.inline("👤 Профиль", b"profile_menu"), Button.inline("📖 Инструкции", b"instructions_menu")],
        [Button.inline("💬 Поддержка", b"support_menu"), Button.inline("❓ FAQ", b"faq_menu")]
    ]
    if is_admin:
        keyboard.append([Button.inline("📊 Админ", b"admin_panel")])
    return keyboard

def inline_back():
    """Кнопка Назад"""
    return [[Button.inline("◀️ Назад", b"main_menu")]]

def inline_tariffs():
    """Меню тарифов"""
    return [
        [Button.inline("1 мес — 150₽", b"tariff_1"), Button.inline("3 мес — 400₽", b"tariff_3")],
        [Button.inline("6 мес — 750₽", b"tariff_6")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]

def inline_profile(has_keys=False):
    """Меню профиля"""
    buttons = [
        [Button.inline("🔑 Ключи", b"my_keys"), Button.inline("💳 Баланс", b"balance")],
        [Button.inline("📜 История", b"history")]
    ]
    if has_keys:
        buttons.insert(0, [Button.inline("⚡ Продлить", b"shop_tariffs")])
    buttons.append([Button.inline("◀️ Назад", b"main_menu")])
    return buttons

def inline_instructions():
    """Меню инструкций"""
    return [
        [Button.inline("📱 iOS", b"instr_ios"), Button.inline("🤖 Android", b"instr_android")],
        [Button.inline("💻 Windows", b"instr_windows"), Button.inline("🍎 macOS", b"instr_macos")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]

def inline_support():
    """Меню поддержки"""
    return [
        [Button.inline("✍️ Задать вопрос", b"support_ask")],
        [Button.inline("❓ FAQ", b"faq_menu")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]

# ========== ТЕКСТЫ (Markdown) ==========
def text_welcome(user_id):
    return (
        f"╔═══════════════════════════════╗\n"
        f"║     🌌  **KARINA VPN**  🌌     ║\n"
        f"╚═══════════════════════════════╝\n\n"
        f"👤 **Абонент:** `{user_id}`\n"
        f"🔐 **Статус:** `Активен`\n\n"
        f"Добро пожаловать в **Karina VPN Shop**.\n"
        f"Ваш узел связи готов к работе.\n\n"
        f"Выберите раздел:"
    )

def text_profile(user_id, user_data):
    keys_count = len(user_data.get("keys", []))
    return (
        f"╔═══════════════════════════════╗\n"
        f"║       👤  **ПРОФИЛЬ**  👤      ║\n"
        f"╚═══════════════════════════════╝\n\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"💳 **Баланс:** `{user_data.get('balance', 0)}₽`\n"
        f"🎁 **Тест:** `{'Использован' if user_data.get('trial_used') else 'Доступен'}`\n"
        f"📅 **В сервисе:** `{user_data.get('joined', datetime.now()).strftime('%d.%m.%Y')}`\n\n"
        f"🔑 **Ключи:** `{keys_count}`"
    )

def text_tariffs():
    return (
        f"╔═══════════════════════════════╗\n"
        f"║        💎  **ТАРИФЫ**  💎      ║\n"
        f"╚═══════════════════════════════╝\n\n"
        f"**1 месяц — 150₽**\n"
        f"• 3 ключа (телефон + ноутбук + планшет)\n"
        f"• Безлимитный трафик\n"
        f"• Сервер: Германия\n\n"
        f"**3 месяца — 400₽** (выгода 50₽)\n"
        f"• Экономия 17%\n\n"
        f"**6 месяцев — 750₽** (выгода 150₽)\n"
        f"• Экономия 25%\n"
        f"• Лучшая цена!"
    )

def text_instructions():
    return (
        f"╔═══════════════════════════════╗\n"
        f"║    📖  **ИНСТРУКЦИИ**  📖      ║\n"
        f"╚═══════════════════════════════╝\n\n"
        f"Выберите ваше устройство:\n"
        f"Пошаговые гайки для настройки."
    )

def text_support():
    return (
        f"╔═══════════════════════════════╗\n"
        f"║   💬  **ПОДДЕРЖКА**  💬        ║\n"
        f"╚═══════════════════════════════╝\n\n"
        f"⏱ **Время ответа:** 15 минут\n"
        f"🕐 **Режим:** 24/7\n\n"
        f"Возникли вопросы? Напишите нам!"
    )

def text_payment(amount, months):
    return (
        f"╔═══════════════════════════════╗\n"
        f"║      💳  **ОПЛАТА**  💳        ║\n"
        f"╚═══════════════════════════════╝\n\n"
        f"💰 **Сумма:** `{amount}₽`\n"
        f"📅 **Период:** `{months} мес.`\n\n"
        f"📦 **Вы получите:**\n"
        f"• 3 ключа VLESS\n"
        f"• Доступ на {months * 30} дней\n"
        f"• Безлимитный трафик\n\n"
        f"💳 **Тестовый режим:**\n"
        f"Оплата не требуется. Ключ будет выдан сразу."
    )

def text_keys(keys):
    if not keys:
        return "📭 У вас пока нет ключей.\n\nПриобретите в разделе '💎 Тарифы'."
    
    text = "╔═══════════════════════════════╗\n║     🔑  **ВАШИ КЛЮЧИ**  🔑     ║\n╚═══════════════════════════════╝\n\n"
    for i, key in enumerate(keys, 1):
        device = key.get("device", "Устройство")
        expire = key.get("expire", datetime.now()).strftime('%d.%m.%Y')
        key_short = key.get("key", "N/A")[:50] + "..."
        text += f"**{i}. {device}** (до {expire})\n`{key_short}`\n\n"
    return text

# ========== БАННЕРЫ (КЭШИРОВАНИЕ) ==========
async def get_cached_banner(banner_name: str):
    """Получает баннер из кэша или загружает первый раз"""
    if banner_name in CACHED_BANNERS:
        logger.info(f"⚡ Баннер '{banner_name}' из кэша")
        return CACHED_BANNERS[banner_name]
    
    # Загружаем первый раз
    file_path = BANNER_PATHS.get(banner_name)
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"⚠️ Баннер '{banner_name}' не найден: {file_path}")
        return None
    
    try:
        logger.warning(f"⚠️ Первая загрузка баннера '{banner_name}'...")
        start = time.time()
        
        # Отправляем боту (себе) для получения media
        msg = await bot.send_file(MY_ID, file=file_path)
        CACHED_BANNERS[banner_name] = msg.media
        
        elapsed = time.time() - start
        logger.info(f"✅ Баннер '{banner_name}' загружен за {elapsed:.2f}с и закэширован")
        
        return msg.media
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки баннера '{banner_name}': {e}")
        return None

async def send_banner(event, banner_name: str, caption: str, buttons, user_id):
    """
    Отправляет или редактирует сообщение с баннером
    - CallbackQuery: редактирует (мгновенно)
    - NewMessage: отправляет новое
    """
    banner_media = await get_cached_banner(banner_name)
    
    try:
        if isinstance(event, events.CallbackQuery.Event):
            # РЕДАКТИРОВАНИЕ (мгновенно, красиво)
            if banner_media:
                await event.edit(caption, buttons=buttons, file=banner_media, parse_mode='md')
            else:
                await event.edit(caption, buttons=buttons, parse_mode='md')
        else:
            # ОТПРАВКА НОВОГО
            if banner_media:
                await bot.send_file(event.chat_id, file=banner_media, caption=caption, buttons=buttons, parse_mode='md')
            else:
                await event.respond(caption, buttons=buttons, parse_mode='md')
    except errors.MessageNotModifiedError:
        pass  # Игнорируем
    except Exception as e:
        logger.error(f"❌ Ошибка отправки баннера '{banner_name}': {e}")
        await event.respond(caption, buttons=buttons, parse_mode='md')

# ========== MARZBAN ==========
async def get_marzban_token():
    start = time.time()
    try:
        resp = await http.post(f"{MARZBAN_URL}/api/admin/token", data={"username": MARZBAN_USER, "password": MARZBAN_PASS})
        log_timing("Marzban: токен", start)
        if resp.status_code == 200:
            return resp.json().get("access_token")
        logger.error(f"❌ Marzban auth: {resp.status_code}")
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
        resp = await http.post(
            f"{MARZBAN_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": username, "inbound_tags": ["VLESS"], "expire": expire, "data_limit": 0}
        )
        log_timing("Marzban: создание", start)
        
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"✅ Marzban: пользователь создан")
            return {"username": data.get("username"), "vless": data.get("links", {}).get("VLESS", ""), "expire": datetime.fromtimestamp(expire)}
        
        logger.error(f"❌ Marzban: {resp.status_code} - {resp.text[:200]}")
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

# ========== ХЭНДЛЕРЫ ==========

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info("=" * 60)
    logger.info(f"📥 /start от {user_id}")
    
    if user_id == MY_ID:
        await event.respond("👋 Привет, Михаил!")
        return
    
    if user_id not in VPN_USERS:
        VPN_USERS[user_id] = {"state": "NEW", "trial_used": False, "balance": 0, "keys": [], "joined": datetime.now()}
        METRICS["total_users"] += 1
        logger.info(f"🆕 Новый пользователь: {user_id}")
    
    await send_banner(event, "menu", text_welcome(user_id), inline_main_menu(user_id == MY_ID), user_id)
    log_timing("Обработка /start", start_time)

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    start_time = time.time()
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    logger.info(f"📥 Кнопка '{data}' от {user_id}")
    
    if user_id not in VPN_USERS:
        VPN_USERS[user_id] = {"state": "NEW", "trial_used": False, "balance": 0, "keys": [], "joined": datetime.now()}
    
    user = VPN_USERS[user_id]
    
    # Навигация
    if data == "main_menu":
        await send_banner(event, "menu", text_welcome(user_id), inline_main_menu(user_id == MY_ID), user_id)
    
    elif data == "profile_menu":
        await send_banner(event, "profile", text_profile(user_id, user), inline_profile(len(user.get("keys", [])) > 0), user_id)
    
    elif data == "shop_tariffs":
        await send_banner(event, "shop", text_tariffs(), inline_tariffs(), user_id)
    
    elif data == "instructions_menu":
        await send_banner(event, "instructions", text_instructions(), inline_instructions(), user_id)
    
    elif data == "support_menu":
        await send_banner(event, "support", text_support(), inline_support(), user_id)
    
    elif data == "trial_activate":
        if user.get("trial_used"):
            await event.answer("❌ Тест уже использован", alert=True)
        else:
            await event.answer("🎁 Активация...", alert=False)
            key_data = await generate_vless_key(user_id, days=1, device="trial")
            if key_data:
                user["trial_used"] = True
                user["keys"].append(key_data)
                METRICS["trial_activated"] += 1
                await event.edit(f"🎉 **Тест активирован!**\n\n🔑 Ключ:\n`{key_data['key']}`\n\n⏱ Срок: 24 часа", buttons=inline_back())
                logger.info(f"✅ Триал активирован для {user_id}")
            else:
                await event.answer("❌ Ошибка генерации", alert=True)
    
    elif data.startswith("tariff_"):
        months_map = {"tariff_1": (1, 150), "tariff_3": (3, 400), "tariff_6": (6, 750)}
        months, amount = months_map.get(data, (1, 150))
        await send_banner(event, "shop", text_payment(amount, months), [[Button.inline(f"💰 Оплатить {amount}₽", b"pay_confirm")], [Button.inline("◀️ Назад", b"shop_tariffs")]], user_id)
    
    elif data == "pay_confirm":
        await event.answer("⏳ Обработка...", alert=False)
        await asyncio.sleep(2)  # Имитация оплаты
        
        # Определяем тариф из предыдущего сообщения (упрощённо 1 месяц)
        months = 1
        keys = []
        for device in ["Телефон", "Ноутбук", "Планшет"]:
            key_data = await generate_vless_key(user_id, days=months * 30, device=device)
            if key_data:
                keys.append(key_data)
        
        if keys:
            user["keys"].extend(keys)
            METRICS["purchases"] += 1
            METRICS["total_revenue"] += 150
            
            # QR-код
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
            logger.info(f"✅ Заказ оплачен, ключи выданы {user_id}")
        else:
            await event.answer("❌ Ошибка генерации ключей", alert=True)
    
    elif data == "my_keys":
        await send_banner(event, "profile", text_keys(user.get("keys", [])), inline_back(), user_id)
    
    elif data == "balance":
        await event.answer(f"💳 Баланс: {user.get('balance', 0)}₽", alert=True)
    
    elif data == "history":
        await event.answer("📜 История пуста", alert=True)
    
    elif data.startswith("instr_"):
        instr_map = {
            "instr_ios": "📱 **iOS:**\n1. V2RayX из App Store\n2. Копировать ключ\n3. + → Import from Clipboard\n4. Подключиться",
            "instr_android": "🤖 **Android:**\n1. V2RayNG из Play Market\n2. Копировать ключ\n3. + → Import config\n4. Подключиться",
            "instr_windows": "💻 **Windows:**\n1. v2rayN с GitHub\n2. Распаковать\n3. Servers → Import\n4. Enable Proxy",
            "instr_macos": "🍎 **macOS:**\nV2RayX из App Store\nСкоро..."
        }
        await event.answer(instr_map.get(data, "Гайка..."), alert=True)
    
    elif data == "faq_menu":
        await event.answer("❓ FAQ в разработке", alert=True)
    
    elif data == "support_ask":
        await event.answer("✍️ Напишите вопрос в чат", alert=True)
    
    elif data == "admin_panel":
        await event.answer(f"📊 Метрики: {METRICS}", alert=True)
    
    else:
        logger.warning(f"⚠️ Неизвестная кнопка: {data}")
        await event.answer("🤔 В разработке", alert=True)
    
    log_timing(f"Обработка '{data}'", start_time)

# ========== ЗАПУСК ==========
async def main():
    await bot.start(bot_token=BOT_TOKEN)
    
    logger.info("=" * 60)
    logger.info("🤖 KARINA VPN SHOP INLINE ЗАПУЩЕН")
    logger.info(f"👤 Владелец: {MY_ID}")
    logger.info(f"🌐 Marzban: {MARZBAN_URL}")
    logger.info("=" * 60)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
    finally:
        await http.aclose()
