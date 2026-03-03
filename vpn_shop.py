"""
KARINA VPN SHOP — Production Module
Полная реализация магазина VPN с логированием и заглушкой оплаты
"""
import os
import logging
import asyncio
import httpx
import qrcode
import io
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types, functions
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

# Проверка конфига
if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID]):
    logger.error("❌ ЗАПОЛНИ .env: API_ID, API_HASH, KARINA_BOT_TOKEN, MY_TELEGRAM_ID")
    exit(1)

# ========== КЛИЕНТЫ ==========
bot = TelegramClient('bot_session', API_ID, API_HASH)
http = httpx.AsyncClient(timeout=30.0)

# ========== БАЗА ДАННЫХ (in-memory для теста) ==========
# В продакшене заменить на Supabase
VPN_USERS = {}  # {user_id: {"state": str, "trial_used": bool, "balance": int, "keys": list, "joined": datetime}}
VPN_ORDERS = {}  # {order_id: {"user_id": int, "months": int, "amount": int, "status": str}}

# ========== МЕТРИКИ ==========
METRICS = {
    "total_users": 0,
    "registered_users": 0,
    "trial_activated": 0,
    "purchases": 0,
    "total_revenue": 0
}

# ========== ТАЙМИНГИ ==========
def log_timing(step_name: str, start_time: float):
    """Логгирует время выполнения шага"""
    elapsed = (time.time() - start_time) * 1000  # мс
    logger.info(f"⏱ {step_name}: {elapsed:.2f}ms")

# ========== КНОПКИ ==========
def start_button():
    return [[types.KeyboardButton('🚀 НАЧАТЬ')]]

def offer_buttons():
    return [
        [types.KeyboardButton('✅ Принимаю условия')],
        [types.KeyboardButton('❌ Отменить')]
    ]

def main_menu():
    return [
        [types.KeyboardButton('💎 Тарифы')],
        [types.KeyboardButton('🎁 Бесплатный тест')],
        [types.KeyboardButton('👤 Мой профиль')],
        [types.KeyboardButton('📖 Инструкции')],
        [types.KeyboardButton('💬 Поддержка')]
    ]

def tariffs_menu():
    return [
        [types.KeyboardButton('1 месяц — 150₽')],
        [types.KeyboardButton('3 месяца — 400₽')],
        [types.KeyboardButton('6 месяцев — 750₽')],
        [types.KeyboardButton('◀️ Назад')]
    ]

def payment_menu(amount, months):
    return [
        [types.KeyboardButton(f'💰 Оплатить {amount}₽ (Тест)')],
        [types.KeyboardButton('◀️ Отмена')]
    ]

def profile_menu(has_keys=False):
    buttons = [
        [types.KeyboardButton('🔑 Мои ключи')],
        [types.KeyboardButton('💳 Баланс')],
        [types.KeyboardButton('📜 История покупок')]
    ]
    if has_keys:
        buttons.insert(0, [types.KeyboardButton('⚡ Продлить подписку')])
    buttons.append([types.KeyboardButton('◀️ Назад')])
    return buttons

def instructions_menu():
    return [
        [types.KeyboardButton('📱 iOS')],
        [types.KeyboardButton('🤖 Android')],
        [types.KeyboardButton('💻 Windows')],
        [types.KeyboardButton('🍎 macOS')],
        [types.KeyboardButton('◀️ Назад')]
    ]

def support_menu():
    return [
        [types.KeyboardButton('✍️ Написать вопрос')],
        [types.KeyboardButton('❓ FAQ')],
        [types.KeyboardButton('◀️ Назад')]
    ]

def back_button():
    return [[types.KeyboardButton('◀️ Назад')]]

# ========== MARZBAN API ==========
async def get_marzban_token():
    """Получение токена доступа Marzban"""
    start = time.time()
    try:
        resp = await http.post(
            f"{MARZBAN_URL}/api/admin/token",
            data={"username": MARZBAN_USER, "password": MARZBAN_PASS}
        )
        log_timing("Marzban: получение токена", start)
        
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            logger.info(f"✅ Marzban токен получен")
            return token
        
        logger.error(f"❌ Marzban auth error: {resp.status_code} - {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"❌ Marzban token error: {e}")
        return None

async def create_marzban_user(username: str, days: int = 30):
    """Создание пользователя в Marzban и генерация VLESS ключа"""
    start = time.time()
    logger.info(f"🔧 Marzban: создание пользователя {username} на {days} дн.")
    
    token = await get_marzban_token()
    if not token:
        return None
    
    try:
        expire_date = datetime.now() + timedelta(days=days)
        expire_timestamp = int(expire_date.timestamp())
        
        resp = await http.post(
            f"{MARZBAN_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": username,
                "inbound_tags": ["VLESS"],
                "expire": expire_timestamp,
                "data_limit": 0  # Безлимитный трафик
            }
        )
        
        log_timing("Marzban: создание пользователя", start)
        
        if resp.status_code == 200:
            data = resp.json()
            vless_link = data.get("links", {}).get("VLESS", "")
            logger.info(f"✅ Marzban: пользователь создан, ключ сгенерирован")
            return {
                "username": data.get("username"),
                "vless": vless_link,
                "expire": expire_date
            }
        
        logger.error(f"❌ Marzban create error: {resp.status_code} - {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"❌ Marzban create error: {e}")
        return None

async def generate_vless_key(user_id: int, days: int = 1, device: str = "Телефон") -> dict:
    """Генерация VLESS ключа для пользователя"""
    start = time.time()
    username = f"vpn_{user_id}_{int(time.time())}_{device}"
    
    user_data = await create_marzban_user(username, days)
    
    if user_data:
        log_timing("Генерация ключа", start)
        return {
            "key": user_data["vless"],
            "username": user_data["username"],
            "expire": user_data["expire"],
            "device": device,
            "days": days
        }
    return None

# ========== ОТПРАВКА БАННЕРА ==========
async def send_welcome_banner(event):
    """Отправляет приветственный баннер с картинкой"""
    start = time.time()
    logger.info(f"📤 Отправка баннера пользователю {event.sender_id}")
    
    try:
        # Проверяем наличие картинки
        image_path = "image.png"
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            await event.respond(
                "🚀 **KARINA VPN**\n\n"
                "Быстрый, надёжный и недоступный для блокировок VPN нового поколения.\n\n"
                "🚀 Обход любых систем DPI и ограничений (XTLS-Reality)\n"
                "🔒 Полная невидимость для провайдера\n"
                "⚡ Высокая скорость и безлимитный трафик\n"
                "🌍 Выделенный узел в Европе (Германия)\n"
                "💰 От 150 ₽/месяц\n"
                "📱 Поддержка всех устройств: iOS, Android, PC, Mac\n\n"
                "Подключение займёт ровно 1 минуту.\n"
                "Жмите кнопку СТАРТ для инициализации соединения 👇",
                file=image_data,
                buttons=start_button()
            )
        else:
            logger.warning(f"⚠️ Баннер {image_path} не найден")
            await event.respond(
                "🚀 **KARINA VPN**\n\n"
                "Быстрый, надёжный VPN нового поколения.\n\n"
                "Жмите кнопку СТАРТ 👇",
                buttons=start_button()
            )
        
        log_timing("Отправка баннера", start)
        logger.info(f"✅ Баннер отправлен")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки баннера: {e}")
        await event.respond("🚀 **KARINA VPN**\n\nЖмите СТАРТ 👇", buttons=start_button())

# ========== ОБРАБОТЧИКИ ==========

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    """Обработчик команды /start"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info("=" * 60)
    logger.info(f"📥 /start от пользователя {user_id}")
    
    if user_id == MY_ID:
        # Владелец — отдельное приветствие
        await event.respond(f"""
👋 Привет, Михаил! Я Карина, твой персональный AI-ассистент.

💬 Пиши мне — я отвечу!
        """)
        log_timing("Ответ владельцу", start_time)
        raise events.StopPropagation
    
    # Клиент — начинаем воронку
    if user_id not in VPN_USERS:
        VPN_USERS[user_id] = {
            "state": "NEW",
            "trial_used": False,
            "balance": 0,
            "keys": [],
            "joined": datetime.now()
        }
        METRICS["total_users"] += 1
        logger.info(f"🆕 Новый пользователь: {user_id}")
    
    await send_welcome_banner(event)
    log_timing("Обработка /start", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='🚀 НАЧАТЬ'))
async def offer_handler(event):
    """Обработчик кнопки НАЧАТЬ — показ оферты"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '🚀 НАЧАТЬ' от {user_id}")
    
    await event.respond("""
📄 **ПУБЛИЧНАЯ ОФЕРТА**

Нажимая «Принимаю», вы соглашаетесь с условиями сервиса:

• Срок действия подписки: с момента активации
• Возврат средств: не предусмотрен
• Один аккаунт = 3 устройства
• Запрещено: спам, атаки, незаконный контент

Принять условия?""", buttons=offer_buttons())
    
    log_timing("Показ оферты", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='✅ Принимаю условия'))
async def accept_handler(event):
    """Принятие оферты — регистрация пользователя"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '✅ Принимаю' от {user_id}")
    
    # Обновляем состояние
    if user_id in VPN_USERS:
        VPN_USERS[user_id]["state"] = "REGISTERED"
        METRICS["registered_users"] += 1
        logger.info(f"✅ Пользователь {user_id} зарегистрирован")
    
    await event.respond("""
🎉 **ДОСТУП РАЗРЕШЁН!**

Добро пожаловать в Karina VPN!

Выберите раздел меню:""", buttons=main_menu())
    
    log_timing("Регистрация пользователя", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='❌ Отменить'))
async def cancel_handler(event):
    """Отмена оферты"""
    user_id = event.sender_id
    logger.info(f"📥 Кнопка '❌ Отменить' от {user_id}")
    
    await event.respond("❌ Доступ отменён. Если передумаете — нажмите /start")
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='💎 Тарифы'))
async def tariffs_handler(event):
    """Показ тарифов"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '💎 Тарифы' от {user_id}")
    
    await event.respond("""
╔═══════════════════════════════════════╗
║          💎  ТАРИФЫ  💎               ║
╚═══════════════════════════════════════╝

**1 месяц — 150₽**
• 3 ключа (телефон + ноутбук + планшет)
• Безлимитный трафик
• Высокая скорость
• Сервер: Германия

**3 месяца — 400₽** (выгода 50₽)
• Всё то же самое
• Экономия 17%

**6 месяцев — 750₽** (выгода 150₽)
• Всё то же самое
• Экономия 25%
• Лучшая цена!

Выберите тариф:""", buttons=tariffs_menu())
    
    log_timing("Показ тарифов", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='.*месяц.*₽'))
async def tariff_select_handler(event):
    """Выбор тарифа — переход к оплате"""
    start_time = time.time()
    user_id = event.sender_id
    text = event.text.strip()
    
    logger.info(f"📥 Выбор тарифа '{text}' от {user_id}")
    
    # Определяем тариф
    if '1' in text and 'месяц' in text:
        months, amount = 1, 150
    elif '3' in text:
        months, amount = 3, 400
    elif '6' in text:
        months, amount = 6, 750
    else:
        months, amount = 1, 150
    
    logger.info(f"💰 Тариф: {months} мес. за {amount}₽")
    
    await event.respond(f"""
✅ **Тариф выбран: {months} мес.**

💰 **К оплате: {amount}₽**

📦 **Вы получите:**
• 3 ключа VLESS
• Доступ на {months * 30} дней
• Безлимитный трафик
• Поддержка 24/7

💳 **Оплата:**
Сейчас используется тестовый режим — оплата не требуется. Ключ будет выдан сразу после нажатия кнопки "Оплатить".

Нажмите для оплаты:""", buttons=payment_menu(amount, months))
    
    log_timing("Выбор тарифа", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='💰 Оплатить.*₽'))
async def payment_handler(event):
    """Обработка оплаты (заглушка)"""
    start_time = time.time()
    user_id = event.sender_id
    text = event.text.strip()
    
    logger.info(f"📥 Оплата от {user_id}")
    
    # Извлекаем сумму из текста кнопки
    amount = int(''.join(filter(str.isdigit, text)))
    months = amount // 150 if amount >= 150 else 1
    
    logger.info(f"💳 Оплата: {amount}₽ за {months} мес. (заглушка)")
    
    # Имитация задержки оплаты
    await event.respond("⏳ **Обработка платежа...**\n\nПожалуйста, подождите...")
    await asyncio.sleep(2)  # Имитация обработки
    
    # Генерация 3 ключей
    logger.info(f"🔑 Генерация 3 ключей для {user_id}...")
    keys = []
    
    for device in ["Телефон", "Ноутбук", "Планшет"]:
        key_data = await generate_vless_key(user_id, days=months * 30, device=device)
        if key_data:
            keys.append(key_data)
            logger.info(f"✅ Ключ для '{device}' сгенерирован")
        else:
            logger.error(f"❌ Ошибка генерации ключа для '{device}'")
    
    if not keys:
        await event.respond("❌ Ошибка генерации ключей. Попробуйте позже или напишите в поддержку.")
        return
    
    # Сохраняем ключи в БД
    if user_id in VPN_USERS:
        VPN_USERS[user_id]["keys"].extend(keys)
    
    # Обновляем метрики
    METRICS["purchases"] += 1
    METRICS["total_revenue"] += amount
    
    # Отправляем ключи с QR-кодом
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(keys[0]["key"])
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    bio.name = 'vpn_qr.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    
    caption = f"""
🟢 **[ ТРАНЗАКЦИЯ ПОДТВЕРЖДЕНА ]**

✅ Оплата {amount}₽ получена

📦 **Ваш заказ:**
• Тариф: {months} мес.
• Срок: {keys[0]['expire'].strftime('%d.%m.%Y')}
• Устройств: 3

🔑 **ВАШИ КЛЮЧИ:**

**1️⃣ Телефон:**
`{keys[0]['key']}`

**2️⃣ Ноутбук:**
`{keys[1]['key']}`

**3️⃣ Планшет:**
`{keys[2]['key']}`

📥 **QR-код для быстрого подключения:**
(см. изображение выше)

📖 **Инструкция по настройке:**
Нажмите '📖 Инструкции' в главном меню

✅ **Готово!** Можете подключаться!
    """
    
    await event.respond(caption, file=bio)
    
    # Сохраняем заказ
    order_id = f"order_{user_id}_{int(time.time())}"
    VPN_ORDERS[order_id] = {
        "user_id": user_id,
        "months": months,
        "amount": amount,
        "status": "completed",
        "keys": keys,
        "created_at": datetime.now()
    }
    
    logger.info(f"✅ Заказ {order_id} завершён")
    log_timing("Оплата и выдача ключей", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='🎁 Бесплатный тест'))
async def trial_handler(event):
    """Активация бесплатного теста"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '🎁 Бесплатный тест' от {user_id}")
    
    if user_id not in VPN_USERS:
        await event.respond("❌ Сначала нажмите /start")
        return
    
    if VPN_USERS[user_id].get("trial_used"):
        await event.respond("""
❌ **Тест уже использован**

Вы уже активировали бесплатный период.
Для продолжения выберите тариф в разделе '💎 Тарифы'.
        """)
        return
    
    # Показываем подтверждение
    await event.respond("""
🎁 **БЕСПЛАТНЫЙ ТЕСТ**

Попробуйте Karina VPN бесплатно в течение 24 часов!

⚠️ **Ограничения триала:**
• 1 ключ (1 устройство)
• 1 день
• Безлимитный трафик

[ 🎁 Активировать тест ]""", buttons=[[types.KeyboardButton('🎁 Активировать тест')], [types.KeyboardButton('◀️ Назад')]])
    
    log_timing("Показ триала", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='🎁 Активировать тест'))
async def trial_activate_handler(event):
    """Активация триала"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Активация триала от {user_id}")
    
    if VPN_USERS[user_id].get("trial_used"):
        await event.respond("❌ Тест уже использован")
        return
    
    # Генерация ключа
    key_data = await generate_vless_key(user_id, days=1, device="Тест")
    
    if not key_data:
        await event.respond("❌ Ошибка генерации ключа. Попробуйте позже.")
        return
    
    # Сохраняем
    VPN_USERS[user_id]["trial_used"] = True
    VPN_USERS[user_id]["keys"].append(key_data)
    METRICS["trial_activated"] += 1
    
    await event.respond(f"""
🎉 **Тест активирован!**

⏱ **Срок:** 24 часа
📱 **Устройств:** 1

🔑 **Ваш ключ:**
`{key_data['key']}`

⚠️ **Ключ перестанет работать через 24 часа**

📖 **Инструкция:**
Нажмите '📖 Инструкции' для настройки.

💎 **Понравилось?**
Купите полную версию в разделе '💎 Тарифы'!
    """)
    
    logger.info(f"✅ Триал активирован для {user_id}")
    log_timing("Активация триала", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='👤 Мой профиль'))
async def profile_handler(event):
    """Показ профиля пользователя"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '👤 Мой профиль' от {user_id}")
    
    if user_id not in VPN_USERS:
        await event.respond("❌ Сначала нажмите /start")
        return
    
    user = VPN_USERS[user_id]
    keys_count = len(user.get("keys", []))
    
    await event.respond(f"""
╔═══════════════════════════════════════╗
║         👤  ПРОФИЛЬ  👤               ║
╚═══════════════════════════════════════╝

🆔 **ID:** `{user_id}`
💳 **Баланс:** `{user.get('balance', 0)}₽`
🎁 **Тест:** `{'Использован' if user.get('trial_used') else 'Доступен'}`
📅 **В сервисе:** `{user.get('joined', datetime.now()).strftime('%d.%m.%Y')}`

🔑 **Активные ключи:** {keys_count}
    """, buttons=profile_menu(has_keys=(keys_count > 0)))
    
    log_timing("Показ профиля", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='🔑 Мои ключи'))
async def my_keys_handler(event):
    """Показ ключей пользователя"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '🔑 Мои ключи' от {user_id}")
    
    if user_id not in VPN_USERS:
        await event.respond("❌ Сначала нажмите /start")
        return
    
    keys = VPN_USERS[user_id].get("keys", [])
    
    if not keys:
        await event.respond("📭 У вас пока нет ключей.\n\nПриобретите в разделе '💎 Тарифы'.")
        return
    
    text = "🔑 **ВАШИ КЛЮЧИ:**\n\n"
    for i, key in enumerate(keys, 1):
        device = key.get("device", f"Устройство {i}")
        expire = key.get("expire", datetime.now()).strftime('%d.%m.%Y')
        key_text = key.get("key", "N/A")[:100] + "..."
        text += f"**{i}. {device}** (до {expire})\n`{key_text}`\n\n"
    
    await event.respond(text)
    
    log_timing("Показ ключей", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='📖 Инструкции'))
async def instructions_handler(event):
    """Показ инструкций"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '📖 Инструкции' от {user_id}")
    
    await event.respond("""
📖 **ИНСТРУКЦИИ ПО НАСТРОЙКЕ**

Выберите ваше устройство:""", buttons=instructions_menu())
    
    log_timing("Показ инструкций", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='📱 iOS'))
async def ios_handler(event):
    """Инструкция для iOS"""
    logger.info(f"📥 Инструкция iOS от {event.sender_id}")
    
    await event.respond("""
📱 **НАСТРОЙКА НА iOS**

**1. Скачайте приложение:**
V2RayX из App Store
🔗 https://apps.apple.com/app/v2rayx

**2. Скопируйте ключ:**
Нажмите и удерживайте ключ → Копировать

**3. Импортируйте:**
• Откройте V2RayX
• Нажмите "+" → "Import from Clipboard"

**4. Подключитесь:**
• Выберите сервер
• Нажмите кнопку подключения
• Готово! ✅

[ 🔑 Мои ключи ] [ ◀️ Назад ]""", buttons=[[types.KeyboardButton('🔑 Мои ключи')], [types.KeyboardButton('◀️ Назад')]])
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='🤖 Android'))
async def android_handler(event):
    """Инструкция для Android"""
    logger.info(f"📥 Инструкция Android от {event.sender_id}")
    
    await event.respond("""
🤖 **НАСТРОЙКА НА ANDROID**

**1. Скачайте приложение:**
V2RayNG из Google Play
🔗 https://play.google.com/store/apps/details?id=com.v2ray.ang

**2. Скопируйте ключ:**
Нажмите на ключ → Копировать

**3. Импортируйте:**
• Откройте V2RayNG
• Нажмите "+" → "Import config from clipboard"

**4. Подключитесь:**
• Нажмите на сервер
• Нажмите круглую кнопку
• Готово! ✅

[ 🔑 Мои ключи ] [ ◀️ Назад ]""", buttons=[[types.KeyboardButton('🔑 Мои ключи')], [types.KeyboardButton('◀️ Назад')]])
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='💻 Windows'))
async def windows_handler(event):
    """Инструкция для Windows"""
    logger.info(f"📥 Инструкция Windows от {event.sender_id}")
    
    await event.respond("""
💻 **НАСТРОЙКА НА WINDOWS**

**1. Скачайте приложение:**
v2rayN с GitHub
🔗 https://github.com/2dust/v2rayN/releases

**2. Распакуйте и запустите:**
• v2rayN.zip → извлечь
• Запустите v2rayN.exe

**3. Импортируйте ключ:**
• Servers → Import servers from clipboard
• Или Ctrl+V

**4. Подключитесь:**
• Выберите сервер
• Нажмите "Enable System Proxy"
• Готово! ✅

[ 🔑 Мои ключи ] [ ◀️ Назад ]""", buttons=[[types.KeyboardButton('🔑 Мои ключи')], [types.KeyboardButton('◀️ Назад')]])
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='💬 Поддержка'))
async def support_handler(event):
    """Показ поддержки"""
    start_time = time.time()
    user_id = event.sender_id
    
    logger.info(f"📥 Кнопка '💬 Поддержка' от {user_id}")
    
    await event.respond("""
💬 **ПОДДЕРЖКА**

Возникли вопросы или проблемы?

⏱ **Время ответа:** обычно 15 минут
🕐 **Режим работы:** 24/7

**Способы связи:**""", buttons=support_menu())
    
    log_timing("Показ поддержки", start_time)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='◀️ Назад'))
async def back_handler(event):
    """Кнопка Назад"""
    user_id = event.sender_id
    logger.info(f"📥 Кнопка '◀️ Назад' от {user_id}")
    
    await event.respond("Главное меню:", buttons=main_menu())
    raise events.StopPropagation

@bot.on(events.NewMessage())
async def fallback_handler(event):
    """Обработчик неизвестных команд"""
    user_id = event.sender_id
    text = event.text.strip()
    
    # Владелец — AI Карина
    if user_id == MY_ID:
        logger.info(f"💬 Сообщение от владельца: {text[:50]}")
        await event.respond(f"✅ {text}\n\n(Карина запомнила)")
        return
    
    # Клиенты — показываем меню
    logger.info(f"📥 Неизвестная команда от {user_id}: {text[:50]}")
    await event.respond("🤔 Выберите кнопку из меню:", buttons=main_menu())
    raise events.StopPropagation

# ========== ЗАПУСК ==========

async def main():
    """Основная функция запуска"""
    await bot.start(bot_token=BOT_TOKEN)
    
    # Команды бота
    await bot(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(),
        lang_code='ru',
        commands=[
            types.BotCommand('start', 'Запустить бота'),
            types.BotCommand('ping', 'Проверить связь'),
            types.BotCommand('help', 'Справка')
        ]
    ))
    
    logger.info("=" * 60)
    logger.info("🤖 KARINA VPN SHOP ЗАПУЩЕН")
    logger.info(f"👤 Владелец: {MY_ID}")
    logger.info(f"🌐 Marzban: {MARZBAN_URL}")
    logger.info(f"💾 Пользователей в памяти: {len(VPN_USERS)}")
    logger.info("=" * 60)
    
    # Вывод метрик каждые 5 минут
    async def print_metrics():
        while True:
            await asyncio.sleep(300)
            logger.info(f"📊 МЕТРИКИ: {METRICS}")
    
    asyncio.create_task(print_metrics())
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
    finally:
        await http.aclose()
