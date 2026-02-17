import os
import asyncio
import logging
import sys
from quart import Quart, jsonify, request
from telethon import functions, types
from brains.clients import user_client, karina_client
from brains.config import KARINA_TOKEN
from brains.memory import search_memories
from brains.calendar import get_upcoming_events
from brains.emotions import get_emotion_state, set_emotion
from brains.health import get_health_stats, get_health_report_text
from skills import register_discovery_skills, register_karina_base_skills
from auras import start_auras, state

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Quart(__name__, static_folder='static', static_url_path='')

@app.route('/')
async def index():
    """Отдача Mini App"""
    return await app.send_static_file('index.html')

# --- API для Mini App ---

@app.route('/api/status')
async def get_status():
    """Текущее состояние Карины"""
    return jsonify({
        "emoji": state.current_emoji_state,
        "health_confirmed": state.is_health_confirmed,
        "next_injection": "22:00",
        "is_awake": state.is_awake
    })

@app.route('/api/calendar')
async def get_api_calendar():
    """События для Mini App"""
    events = await get_upcoming_events(max_results=10)
    return jsonify({"events": events.split('\n') if events else []})

@app.route('/api/memory/search')
async def api_search_memory():
    """Поиск по памяти для админки"""
    query = request.args.get('q', '')
    results = await search_memories(query)
    return jsonify({"results": results})

@app.route('/api/emotion', methods=['GET', 'POST'])
async def api_emotion():
    """Эмоциональное состояние Карины"""
    if request.method == 'POST':
        data = await request.get_json()
        text = data.get('text', '')
        emotion = data.get('emotion', '')

        if emotion:
            await set_emotion(emotion)
            state_data = await get_emotion_state()
            return jsonify(state_data)
        elif text:
            state_data = await get_emotion_state(text)
            return jsonify(state_data)

    # GET - текущее состояние
    state_data = await get_emotion_state()
    return jsonify(state_data)

@app.route('/api/health')
async def api_health():
    """Статистика здоровья"""
    days = int(request.args.get('days', 7))
    stats = await get_health_stats(days)
    return jsonify(stats)

@app.route('/api/health/report')
async def api_health_report():
    """Текстовый отчёт о здоровье"""
    days = int(request.args.get('days', 7))
    report = await get_health_report_text(days)
    return jsonify({"report": report, "days": days})

# --- Конец API ---

async def setup_bot_commands(client):
    """Установка актуальных команд в меню бота"""
    try:
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
        await client(functions.bots.SetBotCommandsRequest(
            scope=types.BotCommandScopeDefault(),
            lang_code='ru',
            commands=commands
        ))
        logger.info("✅ Команды меню бота обновлены.")
    except Exception as e:
        logger.error(f"❌ Ошибка обновления меню команд: {e}")


async def run_bot():
    """Запуск бота с обработкой сообщений"""
    logger.info("🤖 Запуск бота Karina...")
    
    if not KARINA_TOKEN:
        logger.error("❌ KARINA_TOKEN не установлен!")
        return
    
    # Запускаем бота
    await karina_client.start(bot_token=KARINA_TOKEN)
    logger.info("✅ Бот Karina запущен")
    
    # Установка команд
    await setup_bot_commands(karina_client)
    
    # Регистрация скиллов (хендлеров)
    register_karina_base_skills(karina_client)
    logger.info("✅ Скиллы зарегистрированы")
    logger.info("🤖 Карина готова к работе!")
    
    # Бесконечный цикл для обработки событий
    await karina_client.run_until_disconnected()


async def run_web_server():
    """Запуск веб-сервера"""
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🌐 Запуск веб-сервера на порту {port}...")
    
    # Используем Hypercorn для ASGI
    import hypercorn.asyncio
    from hypercorn.config import Config
    
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    config.loglevel = "WARNING"
    
    await hypercorn.asyncio.serve(app, config)


async def run_userbot():
    """Запуск UserBot"""
    logger.info("📱 Запуск UserBot...")
    await user_client.connect()
    
    if not await user_client.is_user_authorized():
        logger.error("❌ UserBot не авторизован!")
        return
    
    logger.info("✅ UserBot авторизован")
    register_discovery_skills(user_client)
    logger.info("✅ Скиллы UserBot зарегистрированы")
    
    # Держим соединение
    await user_client.run_until_disconnected()


async def run_auras():
    """Запуск аур"""
    # Ждём пока бот запустится
    await asyncio.sleep(2)
    logger.info("🌀 Запуск аур...")
    await start_auras(user_client, karina_client)


async def main():
    """Главная функция - запускает всё вместе"""
    logger.info("🔧 Запуск системы Karina AI...")
    
    # Запускаем всё параллельно
    await asyncio.gather(
        run_bot(),           # Бот (основной)
        run_web_server(),    # Веб-сервер
        run_auras(),         # Ауры
        return_exceptions=True
    )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка по сигналу...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
