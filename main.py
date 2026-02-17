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
