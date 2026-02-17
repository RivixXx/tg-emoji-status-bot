"""
Веб-сервер для Mini App Карины
"""
import os
import asyncio
import logging
import sys
from quart import Quart, jsonify, request
from brains.memory import search_memories
from brains.calendar import get_upcoming_events
from brains.emotions import get_emotion_state, set_emotion
from brains.health import get_health_stats, get_health_report_text
from auras import state

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


if __name__ == '__main__':
    import hypercorn.asyncio
    from hypercorn.config import Config
    
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🌐 Запуск веб-сервера на порту {port}...")
    
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    config.loglevel = "WARNING"
    
    asyncio.run(hypercorn.asyncio.serve(app, config))
