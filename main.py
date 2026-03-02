"""
KARINA AI — Dual Mode Bot
- Для владельца (MY_ID): персональный ассистент
- Для клиентов: VPN магазин
"""
import os
import logging
import asyncio
from telethon import TelegramClient, events, types, functions
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

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Проверка
if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID]):
    logger.error("❌ Заполни .env: API_ID, API_HASH, KARINA_BOT_TOKEN, MY_TELEGRAM_ID")
    exit(1)

# ========== КЛИЕНТ ==========
bot = TelegramClient('bot_session', API_ID, API_HASH)

# ========== VPN ДАННЫЕ (кэш) ==========
VPN_USERS = {}  # {user_id: {"state": "NEW", "trial_used": False}}

# ========== КНОПКИ ==========
def vpn_menu_keyboard():
    return [
        [types.KeyboardButton('🚀 Купить VPN')],
        [types.KeyboardButton('👤 Мой профиль')],
        [types.KeyboardButton('📱 Инструкция')],
        [types.KeyboardButton('💬 Поддержка')]
    ]

def tariff_keyboard():
    return [
        [types.KeyboardButton('1 месяц — 150₽')],
        [types.KeyboardButton('3 месяца — 400₽')],
        [types.KeyboardButton('6 месяцев — 750₽')],
        [types.KeyboardButton('◀️ Назад')]
    ]

def back_keyboard():
    return [[types.KeyboardButton('◀️ Назад')]]

# ========== ОБРАБОТЧИКИ ==========

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(e):
    user_id = e.sender_id
    
    if user_id == MY_ID:
        # Владелец — персональный ответ
        await e.reply("""
👋 Привет! Я Карина, твой персональный ассистент.

🧠 Сейчас я работаю в базовом режиме.
💬 Пиши мне — я отвечу!

Команды:
/ping — проверить связь
/help — справка
        """)
    else:
        # Клиент — VPN витрина
        if user_id not in VPN_USERS:
            VPN_USERS[user_id] = {"state": "NEW", "trial_used": False}
        
        await e.reply("""
🚀 **VPN SHOP**

Быстрый и надёжный VPN для любых устройств.

📱 Нажмите кнопку ниже для начала:
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
/ai <текст> — задать вопрос ИИ
/status — статус систем
        """)
    raise events.StopPropagation

@bot.on(events.NewMessage())
async def chat_handler(e):
    user_id = e.sender_id
    text = e.text.strip()
    
    # Владелец — отвечаем как ассистент
    if user_id == MY_ID:
        # Команды владельца
        if text.startswith('/ai '):
            question = text[4:]
            # TODO: Интеграция с Mistral AI
            await e.reply(f"🧠 Вопрос: {question}\n\n(ИИ будет подключен)")
            return
        
        if text == '/status':
            await e.reply("""
✅ Бот работает
📡 Telegram: подключён
🧠 AI: готов к работе
📊 БД: Supabase
            """)
            return
        
        # Обычный чат
        await e.reply(f"✅ {text}\n\n(Карина запомнила)")
    
    # Клиенты — VPN магазин
    else:
        if text == '🚀 Начать':
            VPN_USERS[user_id]['state'] = 'REGISTERED'
            await e.reply("""
🎉 **Добро пожаловать!**

Выберите действие:
            """, buttons=vpn_menu_keyboard())
            return
        
        if text == '🚀 Купить VPN':
            await e.reply("""
💎 **Тарифы VPN:**

• 1 месяц — 150₽
• 3 месяца — 400₽ (выгода 50₽)
• 6 месяцев — 750₽ (выгода 150₽)

🎁 **Бесплатный тест:** 1 день
            """, buttons=tariff_keyboard())
            return
        
        if text == '👤 Мой профиль':
            user_data = VPN_USERS.get(user_id, {})
            await e.reply(f"""
👤 **Профиль:**

ID: `{user_id}`
Статус: {user_data.get('state', 'NEW')}
Тест использован: {user_data.get('trial_used', 'Нет')}
            """, buttons=back_keyboard())
            return
        
        if text == '📱 Инструкция':
            await e.reply("""
📚 **Как использовать VPN:**

1️⃣ После оплаты вы получите ключ
2️⃣ Скачайте приложение (V2RayX, V2RayNG)
3️⃣ Импортируйте ключ
4️⃣ Подключитесь

📱 Приложения:
• iOS: V2RayX
• Android: V2RayNG
• Windows: v2rayN
            """, buttons=back_keyboard())
            return
        
        if text == '💬 Поддержка':
            await e.reply("💬 По вопросам: @support_username")
            return
        
        if 'месяц' in text and '₽' in text:
            await e.reply("""
✅ **Выбран тариф**

Для активации напишите /pay
            """)
            return
        
        if text == '◀️ Назад':
            await e.reply("Главное меню:", buttons=vpn_menu_keyboard())
            return
        
        # Неизвестная команда
        await e.reply("""
🤔 Не понял команду.

Выберите кнопку из меню:
        """, buttons=vpn_menu_keyboard())
    
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
    
    logger.info("=" * 40)
    logger.info("🤖 KARINA BOT ЗАПУЩЕН")
    logger.info(f"👤 Владелец: {MY_ID}")
    logger.info("=" * 40)
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
