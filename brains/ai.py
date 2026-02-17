import httpx
import logging
import json
import asyncio
from datetime import datetime
from brains.config import MISTRAL_API_KEY
from brains.memory import search_memories, save_memory
from brains.calendar import create_event, get_upcoming_events
from brains.weather import get_weather

logger = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_EMBED_URL = "https://api.mistral.ai/v1/embeddings"
MODEL_NAME = "mistral-small-latest"

async def mistral_request_with_retry(client, url, headers, payload, max_retries=3):
    """Запрос к Mistral API с retry для 429 ошибок"""
    for attempt in range(max_retries):
        try:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                logger.warning(f"⚠️ Mistral API rate limit (429). Попытка {attempt + 1}/{max_retries}. Жду {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Mistral API Error: {response.status_code} - {response.text[:200]}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Request error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
    
    logger.error(f"Mistral API: Превышено количество попыток ({max_retries})")
    return None

# Хранилище истории: {chat_id: [messages]}
CHATS_HISTORY = {}

SYSTEM_PROMPT = """
Ты — Карина, заботливая и умная цифровая помощница. 
Твой стиль общения: живой, дружелюбный, слегка игривый, с эмодзи.

ГЛАВНОЕ ПРАВИЛО ПАМЯТИ:
Если предоставлен блок "КОНТЕКСТ ПАМЯТИ", всегда используй эти факты как приоритетные.

ПРАВИЛА ИНСТРУМЕНТОВ:
1. Если пользователь хочет что-то ЗАПЛАНИРОВАТЬ или НАПОМНИТЬ — используй `create_calendar_event`.
2. Если пользователь спрашивает о планах или календаре — используй `get_upcoming_calendar_events`.
3. Если пользователь спрашивает про ПОГОДУ — используй `get_weather_info`.
Сегодняшняя дата и время: {now}
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Создает событие в календаре Google",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Заголовок события"},
                    "start_time": {"type": "string", "description": "Дата и время в формате ISO"},
                    "duration": {"type": "integer", "description": "Длительность в минутах", "default": 30}
                },
                "required": ["summary", "start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_calendar_events",
            "description": "Получает список ближайших событий из календаря",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Количество событий", "default": 5}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_info",
            "description": "Получает текущую погоду",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

async def ask_karina(prompt: str, chat_id: int = 0) -> str:
    """Запрос к Mistral AI с памятью на 10 сообщений и RAG"""
    if not MISTRAL_API_KEY:
        return "У меня нет ключа от моих новых мозгов... 😔"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    context_memory = await search_memories(prompt)
    
    # Инициализация истории для чата
    if chat_id not in CHATS_HISTORY:
        CHATS_HISTORY[chat_id] = []

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    # Формируем сообщение пользователя с RAG
    user_content = prompt
    if context_memory:
        user_content = f"КОНТЕКСТ ПАМЯТИ:\n{context_memory}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {prompt}"

    # Добавляем в историю
    CHATS_HISTORY[chat_id].append({"role": "user", "content": user_content})
    
    # Ограничиваем историю 10 сообщениями
    if len(CHATS_HISTORY[chat_id]) > 10:
        CHATS_HISTORY[chat_id] = CHATS_HISTORY[chat_id][-10:]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(now=now_str)}
    ] + CHATS_HISTORY[chat_id]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await mistral_request_with_retry(
                client, MISTRAL_URL, headers,
                {
                    "model": MODEL_NAME,
                    "messages": messages,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.3
                }
            )
            
            if not result:
                return "Мои мысли спутались... попробуй еще раз? 🧠"
            
            message = result['choices'][0]['message']

            # Обработка функций
            if message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    args = json.loads(tool_call["function"]["arguments"])
                    
                    if func_name == "create_calendar_event":
                        try:
                            start_dt = datetime.fromisoformat(args["start_time"].replace('Z', ''))
                            success = await create_event(args["summary"], start_dt, args.get("duration", 30))
                            if success:
                                res = f"Сделано! ✅ Записала в календарь: **{args['summary']}** на {start_dt.strftime('%d.%m в %H:%M')}."
                                CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                                return res
                        except:
                            return "Не смогла записать в календарь... 🗓"
                    
                    elif func_name == "get_upcoming_calendar_events":
                        events_list = await get_upcoming_events(max_results=args.get("count", 5))
                        res = f"Вот твои ближайшие планы: 😊\n\n{events_list}"
                        CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                        return res
                    
                    elif func_name == "get_weather_info":
                        weather_data = await get_weather()
                        res = f"Я узнала! 🌤 Сейчас за окном {weather_data}. Одевайся по погоде! 😊"
                        CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                        return res

            response_text = message['content'].strip()
            CHATS_HISTORY[chat_id].append({"role": "assistant", "content": response_text})
            return response_text
            
    except Exception as e:
        logger.error(f"Mistral connection error: {e}")
        return "Кажется, я потеряла связь со своим облачным разумом... 🔌"
