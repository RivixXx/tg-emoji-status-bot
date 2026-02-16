import os
import asyncio
import logging
import sys
from quart import Quart
from telethon import functions, types
from brains.clients import user_client, karina_client
from brains.config import KARINA_TOKEN
from skills import register_discovery_skills, register_karina_base_skills
from auras import start_auras

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Quart(__name__)

async def setup_bot_commands(client):
    """Установка актуальных команд в меню бота"""
    try:
        commands = [
            types.BotCommand(command="start", description="Перезапустить Карину 🔄"),
            types.BotCommand(command="calendar", description="Показать мои планы 📅"),
            types.BotCommand(command="news", description="Свежие новости транспорта 🗞"),
            types.BotCommand(command="weather", description="Прогноз погоды 🌤"),
            types.BotCommand(command="remember", description="Запомнить факт (после команды) ✍️"),
            types.BotCommand(command="link_email", description="Привязать Google Календарь 📧"),
        ]
        await client(functions.bots.SetBotCommandsRequest(
            scope=types.BotCommandScopeDefault(),
            lang_code='ru',
            commands=commands
        ))
        logger.info("✅ Команды меню бота обновлены.")
    except Exception as e:
        logger.error(f"❌ Ошибка обновления меню команд: {e}")

@app.before_serving
async def startup():
    # 1. Подключаем UserBot
    await user_client.connect()
    if not await user_client.is_user_authorized():
        logger.error("UserBot не авторизован!")
        return
    
    # Регистрация скиллов для UserBot
    register_discovery_skills(user_client)

    # 2. Подключаем Карину
    if karina_client:
        await karina_client.start(bot_token=KARINA_TOKEN)
        # Установка команд в меню
        await setup_bot_commands(karina_client)
        # Регистрация скиллов для Карины
        register_karina_base_skills(karina_client)
        logger.info("🤖 Карина готова к работе!")

    logger.info("🚀 Вся система (Мозги, Скиллы, Ауры) запущена")
    
    # 3. Запускаем Ауры (фоновые задачи)
    asyncio.create_task(start_auras(user_client, karina_client))

@app.after_serving
async def shutdown():
    await user_client.disconnect()
    if karina_client:
        await karina_client.disconnect()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
