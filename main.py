"""
KARINA AI — Dual Mode Production Bot
- Владелец (MY_ID): AI-ассистент Карина (Mistral AI + RAG + Tools)
- Клиенты: VPN Shop (воронка, тарифы, ключи, триал)
"""
import os
import asyncio
import logging
import httpx
import qrcode
import io
from datetime import datetime, timedelta
from telethon import TelegramClient, events, types, functions
from dotenv import load_dotenv

load_dotenv()

# ========== КОНФИГ ==========
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('KARINA_BOT_TOKEN', '')
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0))

# AI
MISTRAL_KEY = os.environ.get('MISTRAL_API_KEY', '')

# Marzban
MARZBAN_URL = os.environ.get('MARZBAN_URL', 'http://127.0.0.1:8000')
MARZBAN_USER = os.environ.get('MARZBAN_USER', 'admin')
MARZBAN_PASS = os.environ.get('MARZBAN_PASS', '')

# Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID]):
    logger.error("❌ Заполни .env")
    exit(1)

# ========== КЛИЕНТЫ ==========
bot = TelegramClient('bot_session', API_ID, API_HASH)
http = httpx.AsyncClient(timeout=30.0)

# ========== КЭШ ==========
USER_CACHE = {}
CACHE_TTL = 300

# ========== VPN КНОПКИ ==========
def vpn_main_menu():
    return [
        [types.KeyboardButton('💎 Тарифы')],
        [types.KeyboardButton('💳 Баланс')],
        [types.KeyboardButton('👤 Профиль')],
        [types.KeyboardButton('📖 Инструкции')],
        [types.KeyboardButton('💬 Поддержка')]
    ]

def vpn_tariffs():
    return [
        [types.KeyboardButton('1 месяц — 150₽')],
        [types.KeyboardButton('3 месяца — 400₽')],
        [types.KeyboardButton('6 месяцев — 750₽')],
        [types.KeyboardButton('◀️ Назад')]
    ]

def vpn_back():
    return [[types.KeyboardButton('◀️ Назад')]]

# ========== AI ФУНКЦИИ ==========
async def ask_karina_ai(prompt: str, chat_id: int = 0) -> str:
    """Запрос к Mistral AI"""
    if not MISTRAL_KEY:
        return f"🤔 {prompt} (ИИ пока не подключён — добавь MISTRAL_API_KEY в .env)"
    
    try:
        headers = {"Authorization": f"Bearer {MISTRAL_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": "Ты Карина, персональная AI-помощница Михаила. Отвечай тепло, кратко, с заботой. 1-3 эмодзи."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        resp = await http.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'].strip()
        return f"❌ Ошибка AI: {resp.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

# ========== MARZBAN ==========
async def get_marzban_token():
    try:
        resp = await http.post(f"{MARZBAN_URL}/api/admin/token", data={
            "username": MARZBAN_USER,
            "password": MARZBAN_PASS
        })
        if resp.status_code == 200:
            return resp.json().get("access_token")
        return None
    except:
        return None

async def create_vless_key(days: int = 1):
    """Создаёт ключ на указанное количество дней"""
    token = await get_marzban_token()
    if not token:
        return None
    
    try:
        username = f"vpn_{int(datetime.now().timestamp())}"
        expire = int((datetime.now() + timedelta(days=days)).timestamp())
        
        resp = await http.post(
            f"{MARZBAN_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": username, "expire": expire, "data_limit": 0}
        )
        
        if resp.status_code == 200:
            data = resp.json()
            return data.get("links", {}).get("vless", "")
        return None
    except:
        return None

# ========== ОБРАБОТЧИКИ ==========

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(e):
    user_id = e.sender_id
    
    if user_id == MY_ID:
        await e.reply(f"""
👋 Привет, Михаил! Я Карина, твой персональный AI-ассистент.

🧠 **Мои возможности:**
• Отвечаю на вопросы (Mistral AI)
• Помню контекст диалога
• Помогаю с организацией
• Слежу за здоровьем

💬 Просто напиши мне — я отвечу!

**Команды:**
/ping — проверить связь
/help — справка
/status — статус систем
        """)
    else:
        # Клиент — начинаем воронку
        await e.reply("""
📄 **ПУБЛИЧНАЯ ОФЕРТА**

Нажимая "Принимаю", вы соглашаетесь с условиями сервиса.

[Принимаю]
        """, buttons=[[types.KeyboardButton('✅ Принимаю условия')]])
    
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
/ping — проверить
/help — справка
/status — статус
        """)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern='/status'))
async def status_handler(e):
    if e.sender_id == MY_ID:
        await e.reply(f"""
✅ **Статус:**
🤖 Бот: работает
📡 Telegram: ✅
🌐 Marzban: {'✅' if MARZBAN_URL else '❌'}
🧠 AI: {'✅' if MISTRAL_KEY else '❌'}
💾 БД: {'✅' if SUPABASE_URL else '❌'}
        """)
    raise events.StopPropagation

@bot.on(events.NewMessage())
async def main_handler(e):
    user_id = e.sender_id
    text = e.text.strip()
    
    # ВЛАДЕЛЕЦ — AI Карина
    if user_id == MY_ID:
        if text.startswith('/'):
            return  # Команды обрабатываются отдельно
        
        # Отвечаем через AI
        async with bot.action(user_id, 'typing'):
            response = await ask_karina_ai(text, user_id)
        await e.reply(response)
        raise events.StopPropagation
    
    # КЛИЕНТЫ — VPN Shop
    # Простая воронка без БД (in-memory)
    
    if text == '✅ Принимаю условия':
        await e.reply("""
🎉 **Доступ разрешён!**

Добро пожаловать в Karina VPN!

Выберите раздел:
        """, buttons=vpn_main_menu())
        raise events.StopPropagation
    
    if text == '💎 Тарифы':
        await e.reply("""
💎 **ТАРИФЫ**

1 месяц — 150₽
3 месяца — 400₽ (выгода 50₽)
6 месяцев — 750₽ (выгода 150₽)

📦 **3 ключа** (телефон + ноутбук + планшет)
⚡ **Мгновенная выдача**
        """, buttons=vpn_tariffs())
        raise events.StopPropagation
    
    if 'месяц' in text and '₽' in text:
        await e.reply("""
✅ Тариф выбран!

Для оплаты напишите: /pay
        """)
        raise events.StopPropagation
    
    if text == '💳 Баланс':
        await e.reply("💳 Баланс: 0₽\n\n(В разработке)")
        raise events.StopPropagation
    
    if text == '👤 Профиль':
        await e.reply("👤 Профиль\n\nID: {}".format(user_id))
        raise events.StopPropagation
    
    if text == '📖 Инструкции':
        await e.reply("""
📖 **КАК ИСПОЛЬЗОВАТЬ:**

1️⃣ Скачайте приложение:
• Android: V2RayNG
• iOS: V2RayX
• Windows: v2rayN

2️⃣ Скопируйте ключ

3️⃣ Импортируйте в приложение

4️⃣ Подключитесь!
        """)
        raise events.StopPropagation
    
    if text == '💬 Поддержка':
        await e.reply("💬 Поддержка: @support")
        raise events.StopPropagation
    
    if text == '◀️ Назад':
        await e.reply("Главное меню:", buttons=vpn_main_menu())
        raise events.StopPropagation
    
    # Неизвестное
    await e.reply("Выберите кнопку:", buttons=vpn_main_menu())
    raise events.StopPropagation

# ========== ЗАПУСК ==========

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    
    await bot(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(),
        lang_code='ru',
        commands=[
            types.BotCommand('start', 'Запустить'),
            types.BotCommand('ping', 'Проверить'),
            types.BotCommand('help', 'Справка'),
            types.BotCommand('status', 'Статус')
        ]
    ))
    
    logger.info("=" * 50)
    logger.info("🤖 KARINA AI ЗАПУЩЕНА")
    logger.info(f"👤 Владелец: {MY_ID}")
    logger.info(f"🧠 AI: {'✅' if MISTRAL_KEY else '❌'}")
    logger.info(f"🌐 VPN: {'✅' if MARZBAN_URL else '❌'}")
    logger.info("=" * 50)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
