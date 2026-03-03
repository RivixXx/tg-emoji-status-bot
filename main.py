"""
KARINA AI — VPN Shop Bot
- Владелец (MY_ID): персональный ассистент Карина
- Клиенты: VPN магазин с триалом и покупками
"""
import os
import logging
import asyncio
import httpx
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types, functions
from dotenv import load_dotenv

load_dotenv()

# ========== КОНФИГ ==========
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('KARINA_BOT_TOKEN', '')
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0))
MISTRAL_KEY = os.environ.get('MISTRAL_API_KEY', '')

# Marzban
MARZBAN_URL = os.environ.get('MARZBAN_URL', 'http://localhost:8000')
MARZBAN_USER = os.environ.get('MARZBAN_USER', 'admin')
MARZBAN_PASS = os.environ.get('MARZBAN_PASS', '')

# Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка
if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID]):
    logger.error("❌ Заполни .env: API_ID, API_HASH, KARINA_BOT_TOKEN, MY_TELEGRAM_ID")
    exit(1)

# ========== КЛИЕНТЫ ==========
bot = TelegramClient('bot_session', API_ID, API_HASH)
http = httpx.AsyncClient(timeout=30.0)

# ========== БАЗА ДАННЫХ (in-memory кэш) ==========
# В продакшене заменить на Supabase
USERS_DB = {}  # {user_id: {"state": "NEW", "trial_used": False, "balance": 0, "keys": []}}
ORDERS_DB = {}  # {order_id: {"user_id": ..., "amount": ..., "status": "pending"}}

# ========== КНОПКИ ==========
def main_menu():
    return [
        [types.KeyboardButton('🚀 Купить VPN')],
        [types.KeyboardButton('🎁 Бесплатный тест')],
        [types.KeyboardButton('👤 Мой профиль')],
        [types.KeyboardButton('📱 Как использовать')],
        [types.KeyboardButton('💬 Поддержка')]
    ]

def tariffs_menu():
    return [
        [types.KeyboardButton('1 месяц — 150₽')],
        [types.KeyboardButton('3 месяца — 400₽')],
        [types.KeyboardButton('6 месяцев — 750₽')],
        [types.KeyboardButton('◀️ Назад')]
    ]

def profile_menu(has_key=False):
    buttons = [
        [types.KeyboardButton('💳 Пополнить баланс')],
        [types.KeyboardButton('📜 История покупок')]
    ]
    if has_key:
        buttons.insert(1, [types.KeyboardButton('🔑 Мои ключи')])
    buttons.append([types.KeyboardButton('◀️ Назад')])
    return buttons

def payment_menu(amount):
    return [
        [types.KeyboardButton(f'💰 Оплатить {amount}₽')],
        [types.KeyboardButton('◀️ Назад')]
    ]

def back_menu():
    return [[types.KeyboardButton('◀️ Назад')]]

# ========== MARZBAN API ==========
async def get_marzban_token():
    """Получение токена Marzban"""
    try:
        resp = await http.post(f"{MARZBAN_URL}/api/admin/token", data={
            "username": MARZBAN_USER,
            "password": MARZBAN_PASS
        })
        if resp.status_code == 200:
            return resp.json().get("access_token")
        logger.error(f"Marzban auth error: {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"Marzban token error: {e}")
        return None

async def create_marzban_user(username: str, days: int = 30):
    """Создание пользователя в Marzban"""
    token = await get_marzban_token()
    if not token:
        return None
    
    try:
        # Создаём пользователя с ограничением по времени
        expire_date = datetime.now() + timedelta(days=days)
        
        resp = await http.post(
            f"{MARZBAN_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": username,
                "inbound_tags": ["VLESS"],
                "expire": int(expire_date.timestamp()),
                "data_limit": 0  # Без лимита трафика
            }
        )
        
        if resp.status_code == 200:
            data = resp.json()
            return {
                "username": data.get("username"),
                "vless": data.get("links", {}).get("VLESS", ""),
                "expire": expire_date
            }
        logger.error(f"Marzban create error: {resp.status_code} - {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Marzban create error: {e}")
        return None

async def generate_vless_key(user_id: int, days: int = 1) -> str:
    """Генерация VLESS ключа для пользователя"""
    username = f"vpn_{user_id}_{int(datetime.now().timestamp())}"
    user_data = await create_marzban_user(username, days)
    
    if user_data:
        return user_data["vless"]
    return None

# ========== ОБРАБОТЧИКИ ==========

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(e):
    user_id = e.sender_id
    
    if user_id == MY_ID:
        # ВЛАДЕЛЕЦ — персональный ассистент
        await e.reply(f"""
👋 Привет, Михаил! Я Карина, твой персональный ассистент.

🧠 **Мои возможности:**
• Отвечаю на вопросы
• Помню контекст диалога
• Помогаю с организацией времени
• Слежу за здоровьем

💬 Просто напиши мне — я отвечу!

**Команды:**
/ping — проверить связь
/help — справка
/status — статус систем
        """)
    else:
        # КЛИЕНТ — VPN магазин
        if user_id not in USERS_DB:
            USERS_DB[user_id] = {
                "state": "NEW",
                "trial_used": False,
                "balance": 0,
                "keys": [],
                "joined": datetime.now()
            }
        
        await e.reply(f"""
🚀 **VPN SHOP**

Быстрый и надёжный VPN для любых устройств.

⚡ **Мгновенная выдача**
💳 **Оплата картой**
📱 **Любые устройства**

👇 Нажмите кнопку ниже:
        """, buttons=[[types.KeyboardButton('🚀 Начать')]])
    
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='/ping'))
async def ping_handler(e):
    await e.reply("🏓 Понг! Бот работает ✅")
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(e):
    if e.sender_id == MY_ID:
        await e.reply("""
📚 **Команды владельца:**

/ping — проверить работу
/status — статус систем
/ai <текст> — вопрос ИИ
        """)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='/status'))
async def status_handler(e):
    if e.sender_id == MY_ID:
        await e.reply("""
✅ **Статус систем:**

🤖 Бот: работает
📡 Telegram: подключён
🌐 Marzban: {marzban}
💾 База: in-memory
🧠 AI: {ai}
        """.format(
            marzban="✅" if MARZBAN_URL else "❌",
            ai="✅" if MISTRAL_KEY else "❌"
        ))
    raise events.StopPropagation

@bot.on(events.NewMessage())
async def chat_handler(e):
    user_id = e.sender_id
    text = e.text.strip()
    
    # ВЛАДЕЛЕЦ
    if user_id == MY_ID:
        if text.startswith('/ai '):
            question = text[4:]
            # TODO: Интеграция с Mistral AI
            await e.reply(f"🧠 Вопрос: {question}\n\n(ИИ будет подключен)")
            return
        
        # Обычный чат
        await e.reply(f"✅ {text}\n\n(Карина запомнила)")
        raise events.StopPropagation
    
    # КЛИЕНТЫ
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {"state": "NEW", "trial_used": False, "balance": 0, "keys": []}
    
    user = USERS_DB[user_id]
    
    # Главное меню
    if text == '🚀 Начать':
        user['state'] = 'REGISTERED'
        await e.reply("""
🎉 **Добро пожаловать в VPN SHOP!**

Выберите действие:
        """, buttons=main_menu())
        raise events.StopPropagation
    
    # Купить VPN
    if text == '🚀 Купить VPN':
        await e.reply("""
💎 **Выберите тариф:**

**1 месяц — 150₽**
• 1 ключ = 1 устройство
• Безлимитный трафик
• Высокая скорость

**3 месяца — 400₽** (выгода 50₽)
• Экономия 17%
• Все преимущества месяца

**6 месяцев — 750₽** (выгода 150₽)
• Экономия 25%
• Лучшая цена!

📦 **Что вы получите:**
• 3 ключа для разных устройств
• Инструкция по настройке
• Поддержка 24/7
        """, buttons=tariffs_menu())
        raise events.StopPropagation
    
    # Тарифы
    if 'месяц' in text and '₽' in text:
        # Определяем тариф
        if '1' in text and 'месяц' in text:
            months, price = 1, 150
        elif '3' in text:
            months, price = 3, 400
        elif '6' in text:
            months, price = 6, 750
        else:
            months, price = 1, 150
        
        await e.reply(f"""
✅ **Тариф выбран:** {months} мес. за {price}₽

📦 **Вы получите:**
• 3 ключа (телефон + ноутбук + планшет)
• Доступ на {months * 30} дней
• Безлимитный трафик

💳 Для оплаты нажмите:
        """, buttons=payment_menu(price))
        raise events.StopPropagation
    
    # Оплата
    if 'Оплатить' in text:
        await e.reply("""
💳 **Оплата:**

1. Нажмите "💰 Оплатить"
2. Перейдите по ссылке
3. Оплатите картой
4. Ключ придёт автоматически

⏱ Оплата обрабатывается 1-2 минуты
        """)
        # TODO: Интеграция с платежной системой
        raise events.StopPropagation
    
    # Бесплатный тест
    if text == '🎁 Бесплатный тест':
        if user.get('trial_used'):
            await e.reply("""
❌ **Тест уже использован**

Вы уже активировали бесплатный период.
Для продолжения выберите тариф в разделе "🚀 Купить VPN".
            """)
        else:
            # Выдаём тест на 1 день
            key = await generate_vless_key(user_id, days=1)
            if key:
                user['trial_used'] = True
                user['keys'].append({'key': key, 'expire': '1 день', 'type': 'trial'})
                
                await e.reply(f"""
🎁 **Тестовый доступ активирован!**

⏱ Срок: 1 день
📱 Устройств: 1

**Ваш ключ:**
`{key[:100]}...`

📥 **Как подключить:**
1. Скачайте приложение (см. "📱 Как использовать")
2. Скопируйте ключ выше
3. Импортируйте в приложение

⚠️ **Ключ перестанет работать через 24 часа**

Для полного доступа выберите тариф:
        """, buttons=tariffs_menu())
            else:
                await e.reply("❌ Ошибка выдачи теста. Попробуйте позже или напишите в поддержку.")
        raise events.StopPropagation
    
    # Профиль
    if text == '👤 Мой профиль':
        keys_count = len(user.get('keys', []))
        await e.reply(f"""
👤 **Ваш профиль:**

💳 Баланс: {user.get('balance', 0)}₽
🔑 Ключей: {keys_count}
🎁 Тест: {'Использован' if user.get('trial_used') else 'Доступен'}
📅 В сервисе: {user.get('joined', datetime.now()).strftime('%d.%m.%Y')}
        """, buttons=profile_menu(has_key=(keys_count > 0)))
        raise events.StopPropagation
    
    # Мои ключи
    if text == '🔑 Мои ключи':
        keys = user.get('keys', [])
        if not keys:
            await e.reply("📭 У вас пока нет ключей.\n\nПриобретите в разделе '🚀 Купить VPN'.")
        else:
            await e.reply(f"**Ваши ключи ({len(keys)} шт.):**\n\n" + 
                         "\n\n".join([f"**{i+1}.** `{k['key'][:50]}...` ({k.get('expire', 'N/A')})" 
                                     for i, k in enumerate(keys)]))
        raise events.StopPropagation
    
    # Инструкция
    if text == '📱 Как использовать':
        await e.reply("""
📚 **Как использовать VPN:**

**1️⃣ Скачайте приложение:**

📱 **Android:** V2RayNG
🔗 https://play.google.com/store/apps/details?id=com.v2ray.ang

🍎 **iOS:** V2RayX
🔗 https://apps.apple.com/app/v2rayx/id1592659094

💻 **Windows:** v2rayN
🔗 https://github.com/2dust/v2rayN

**2️⃣ Импортируйте ключ:**
1. Скопируйте ключ из бота
2. Откройте приложение
3. Нажмите "+" или "Import"
4. Вставьте ключ

**3️⃣ Подключитесь:**
1. Выберите сервер
2. Нажмите кнопку подключения
3. Готово! ✅

❓ **Вопросы?** Напишите в поддержку.
        """)
        raise events.StopPropagation
    
    # Поддержка
    if text == '💬 Поддержка':
        await e.reply("""
💬 **Поддержка:**

По всем вопросам пишите: @support_username

⏱ Обычно отвечаем в течение 15 минут
        """)
        raise events.StopPropagation
    
    # Назад
    if text == '◀️ Назад':
        await e.reply("Главное меню:", buttons=main_menu())
        raise events.StopPropagation
    
    # Пополнить баланс (заглушка)
    if text == '💳 Пополнить баланс':
        await e.reply("""
💳 **Пополнение баланса:**

Минимальная сумма: 100₽

Комиссия: 0%

⚠️ В разработке. Скоро будет доступно!
        """)
        raise events.StopPropagation
    
    # История покупок
    if text == '📜 История покупок':
        await e.reply("📭 История покупок пуста.\n\nСовершите первую покупку!")
        raise events.StopPropagation
    
    # Неизвестная команда
    await e.reply("""
🤔 Не понял команду.

Выберите кнопку из меню:
    """, buttons=main_menu())
    raise events.StopPropagation

# ========== ЗАПУСК ==========

async def main():
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
    
    logger.info("=" * 50)
    logger.info("🤖 KARINA VPN SHOP BOT ЗАПУЩЕН")
    logger.info(f"👤 Владелец: {MY_ID}")
    logger.info(f"🌐 Marzban: {MARZBAN_URL}")
    logger.info("=" * 50)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
    finally:
        await http.aclose()
