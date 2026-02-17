"""
Бот Карина - отдельный процесс для обработки сообщений Telegram
"""
import os
import asyncio
import logging
import sys
from telethon import functions, types, events
from telethon.sessions import StringSession
from telethon import TelegramClient
from brains.config import API_ID, API_HASH, KARINA_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Создаём клиента бота
bot_client = None
if KARINA_TOKEN:
    bot_client = TelegramClient('karina_bot', API_ID, API_HASH)

# --- Хендлеры ---

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    logger.info(f"📩 /start от {event.chat_id}")
    await event.respond(
        "Привет! Я Карина. 😊\n\nЯ теперь не просто бот, у меня есть удобная панель управления! Нажми кнопку ниже или используй /app.",
        buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
    )

@bot_client.on(events.NewMessage(pattern='/app'))
async def app_handler(event):
    logger.info(f"📩 /app от {event.chat_id}")
    await event.respond(
        "Твоя персональная панель управления Кариной:",
        buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
    )

@bot_client.on(events.NewMessage(pattern='/calendar'))
async def calendar_handler(event):
    logger.info(f"📩 /calendar от {event.chat_id}")
    from brains.calendar import get_upcoming_events
    info = await get_upcoming_events()
    await event.respond(f"🗓 **Твои планы:**\n\n{info}")

@bot_client.on(events.NewMessage(pattern='/conflicts'))
async def conflicts_handler(event):
    logger.info(f"📩 /conflicts от {event.chat_id}")
    from brains.calendar import get_conflict_report
    report = await get_conflict_report()
    await event.respond(report)

@bot_client.on(events.NewMessage(pattern='/health'))
async def health_handler(event):
    logger.info(f"📩 /health от {event.chat_id}")
    from brains.health import get_health_report_text
    report = await get_health_report_text(7)
    await event.respond(report)

@bot_client.on(events.NewMessage(pattern='/news'))
async def news_handler(event):
    logger.info(f"📩 /news от {event.chat_id}")
    from brains.news import get_latest_news
    news = await get_latest_news()
    await event.respond(f"🗞 **Новости:**\n\n{news}")

@bot_client.on(events.NewMessage(incoming=True))
async def chat_handler(event):
    logger.info(f"💬 Сообщение от {event.chat_id}: {event.text[:50] if event.text else 'no text'}")
    
    # Пропускаем команды
    if event.text and event.text.startswith('/'):
        return
    
    # Пропускаем не личные сообщения
    if not event.is_private:
        return
    
    # Детектор здоровья
    text_low = event.text.lower() if event.text else ''
    if any(word in text_low for word in ['сделал', 'готово', 'окей', 'уколол']):
        await event.respond("Умничка! 🥰")
        return
    
    # Отвечаем через AI
    from brains.ai import ask_karina
    async with bot_client.action(event.chat_id, 'typing'):
        response = await ask_karina(event.text, chat_id=event.chat_id)
        await event.reply(response)


async def main():
    """Запуск бота"""
    if not bot_client:
        logger.error("❌ Бот не создан!")
        return
    
    logger.info("🤖 Запуск бота Karina...")
    await bot_client.start(bot_token=KARINA_TOKEN)
    logger.info("✅ Бот запущен")
    
    # Установка команд
    commands = [
        types.BotCommand(command="start", description="Перезапустить Карину 🔄"),
        types.BotCommand(command="calendar", description="Показать мои планы 📅"),
        types.BotCommand(command="conflicts", description="Проверить накладки ⚠️"),
        types.BotCommand(command="health", description="Статистика здоровья ❤️"),
        types.BotCommand(command="news", description="Свежие новости транспорта 🗞"),
        types.BotCommand(command="weather", description="Прогноз погоды 🌤"),
        types.BotCommand(command="remember", description="Запомнить факт ✍️"),
        types.BotCommand(command="link_email", description="Привязать Google Календарь 📧"),
    ]
    await bot_client(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(),
        lang_code='ru',
        commands=commands
    ))
    logger.info("✅ Команды установлены")
    
    logger.info("📡 Бот слушает сообщения...")
    await bot_client.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка...")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
