"""
KARINA AI — Dual Mode Bot

- Владелец (MY_ID): Персональный AI-ассистент (календарь, здоровье, напоминания, новости)
- Клиенты: VPN Shop (inline, кэш баннеров, QR-коды)
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, events
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

if not all([API_ID, API_HASH, BOT_TOKEN, MY_ID]):
    logger.error("❌ ЗАПОЛНИ .env")
    exit(1)

# ========== КЛИЕНТ (создается в main()) ==========
bot: TelegramClient = None  # Инициализируется в main()

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

# VPN магазин
from brains.vpn_logic import register_vpn_handlers, preload_banners

# Задачи и проекты
from skills.task_commands import register_task_commands

# Триггеры продуктивности
from brains.triggers import start_triggers_loop

# ========== ГЛОБАЛЬНЫЕ СОСТОЯНИЯ ==========
SHUTDOWN_EVENT = asyncio.Event()


# ========== ФОНОВЫЕ ЗАДАЧИ ВЛАДЕЛЬЦА ==========
async def owner_background_tasks():
    """Фоновые задачи для владельца"""
    logger.info("🔄 Запуск фоновых задач владельца...")
    
    last_greeting_date = None
    last_health_check_date = None
    last_birthday_check_date = None

    while not SHUTDOWN_EVENT.is_set():
        try:
            now = datetime.now()
            today = now.date()

            # Утреннее приветствие (7:00) — с защитой от повторной отправки
            if now.hour == 7 and now.minute == 0 and today != last_greeting_date:
                await bot.send_message(
                    MY_ID,
                    f"☀️ Доброе утро, Михаил!\n\n{await get_latest_news(limit=3, user_id=MY_ID)}"
                )
                last_greeting_date = today

            # Проверка здоровья (22:00) — с защитой от повторной отправки
            if now.hour == 22 and now.minute == 0 and today != last_health_check_date:
                await bot.send_message(
                    MY_ID,
                    "💉 Михаил, пора сделать укол!\n\nНапиши 'сделал' когда выполнишь."
                )
                last_health_check_date = today

            # Проверка дней рождения (8:00) — с защитой от повторной отправки
            if now.hour == 8 and now.minute == 0 and today != last_birthday_check_date:
                celebrants = await get_todays_birthdays()
                for emp in celebrants:
                    await bot.send_message(
                        MY_ID,
                        f"🎂 Сегодня день рождения у {emp['full_name']}!"
                    )
                last_birthday_check_date = today

            # Сон 30 секунд вместо 60 для более точного попадания
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"❌ Ошибка фоновой задачи: {e}")
            await asyncio.sleep(30)


# ========== ЗАПУСК ==========
async def main():
    global bot
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)

    # ---> ПРЕДЗАГРУЗКА БАННЕРОВ <---
    # Бот загрузит все картинки до того, как начнет отвечать пользователям
    await preload_banners(bot, MY_ID)

    # 1. ПОДКЛЮЧАЕМ ЛОГИКУ МАГАЗИНА
    register_vpn_handlers(bot, MY_ID)

    # 2. ПОДКЛЮЧАЕМ ЗАДАЧИ И ПРОЕКТЫ
    register_task_commands(bot, MY_ID)

    # 3. ПОДКЛЮЧАЕМ AI-АССИСТЕНТА ДЛЯ ВЛАДЕЛЬЦА
    @bot.on(events.NewMessage(chats=MY_ID))
    async def owner_chat_handler(event):
        """Обработка сообщений от владельца (AI Карина)"""
        text = event.text.strip()

        # Игнорируем команды (они обрабатываются отдельно)
        if text.startswith('/'):
            return

        logger.info(f"💬 Сообщение от владельца: {text[:50]}")

        # Запрос к AI
        async with bot.action(MY_ID, 'typing'):
            response = await ask_karina(text, chat_id=MY_ID)

        await event.respond(response)

    # 4. ОБРАБОТКА CALLBACK ОТ ТРИГГЕРОВ
    @bot.on(events.CallbackQuery(chats=MY_ID))
    async def trigger_callback_handler(event):
        """Обработка кнопок от триггеров продуктивности"""
        data = event.data.decode('utf-8')
        
        # Перерывы
        if data == 'break_ack':
            await event.answer("✅ Отлично! 5 минут — и снова в бой! 💪", alert=True)
        elif data == 'break_snooze_15':
            await event.answer("⏰ Напомню через 15 минут", alert=True)
        
        # Обед
        elif data == 'lunch_ack':
            await event.answer("✅ Приятного аппетита! 🍽️", alert=True)
        elif data == 'lunch_snooze':
            await event.answer("⏰ Напомню позже", alert=True)
        
        # Вечерний обзор
        elif data == 'evening_review_write':
            await event.answer("✍️ Напиши итоги дня в чат", alert=True)
        elif data == 'plan_tomorrow':
            await event.answer("🎯 Цели на завтра: используй /goals", alert=True)
        elif data == 'acknowledge_evening':
            await event.answer("😴 Спокойной ночи! 💙", alert=True)
        
        # Просроченные задачи
        elif data == 'show_overdue':
            await event.edit("🔴 **Просроченные задачи:**\n\nИспользуй /tasks для просмотра")
        
        # Застрявшие задачи
        elif data == 'show_stuck_tasks':
            await event.edit("📋 **Застрявшие задачи:**\n\nИспользуй /tasks todo")
        
        # Утреннее планирование
        elif data == 'set_daily_goals':
            await event.answer("🎯 Используй /goals plan <цель1>, <цель2>", alert=True)
        elif data == 'show_tasks':
            await event.answer("📋 Используй /tasks", alert=True)
        elif data == 'show_sprint':
            await event.answer("🏃 Используй /sprints", alert=True)
        
        else:
            return  # Пропускаем, это не наша кнопка
        
        await event.answer()

    # 3. ИНИЦИАЛИЗАЦИЯ НАПОМИНАНИЙ
    reminder_manager.set_client(bot, MY_ID)
    reminders_task = asyncio.create_task(start_reminder_loop())

    # 4. ТРИГГЕРЫ ПРОДУКТИВНОСТИ
    triggers_task = asyncio.create_task(start_triggers_loop(bot, MY_ID))

    # 5. ФОНОВЫЕ ЗАДАЧИ ВЛАДЕЛЬЦА
    background_task = asyncio.create_task(owner_background_tasks())

    logger.info("=" * 60)
    logger.info("🤖 KARINA AI — Dual Mode ЗАПУЩЕН")
    logger.info(f"👤 Владелец: {MY_ID}")
    logger.info(f"🧠 AI: {'✅' if MISTRAL_KEY else '❌'}")
    logger.info(f"💾 Supabase: {'✅' if SUPABASE_URL else '❌'}")
    logger.info(f"🎯 Триггеры продуктивности: ✅")
    logger.info("=" * 60)

    await bot.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановлено")
        SHUTDOWN_EVENT.set()
