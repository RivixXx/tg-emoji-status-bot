import httpx
import logging
import json
from datetime import datetime
from brains.config import MISTRAL_API_KEY
from brains.memory import search_memories, save_memory
from brains.calendar import create_event

logger = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL_NAME = "mistral-small-latest"

SYSTEM_PROMPT = """
Ты — Карина, заботливая и умная цифровая помощница. 
Твой стиль общения: живой, дружелюбный, слегка игривый, с эмодзи.

ГЛАВНОЕ ПРАВИЛО ПАМЯТИ:
Если предоставлен блок "КОНТЕКСТ ПАМЯТИ", всегда используй эти факты как приоритетные.

ПРАВИЛО КАЛЕНДАРЯ:
Если пользователь просит что-то запланировать или напомнить, используй функцию `create_calendar_event`.
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
                    "start_time": {"type": "string", "description": "Дата и время в формате ISO (например, 2024-05-15T10:00:00)"},
                    "duration": {"type": "integer", "description": "Длительность в минутах", "default": 30}
                },
                "required": ["summary", "start_time"]
            }
        }
    }
]

async def ask_karina(prompt: str) -> str:
    """Запрос к Mistral AI API с поддержкой RAG и Function Calling"""
    if not MISTRAL_API_KEY:
        return "У меня нет ключа от моих новых мозгов (MISTRAL_API_KEY не задан)... 😔"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    context_memory = await search_memories(prompt)
    
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    user_message_with_context = prompt
    if context_memory:
        user_message_with_context = f"КОНТЕКСТ ПАМЯТИ:\n{context_memory}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {prompt}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(now=now_str)},
        {"role": "user", "content": user_message_with_context}
    ]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MISTRAL_URL, json={
                "model": MODEL_NAME,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0.3
            }, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Mistral API Error: {response.status_code} - {response.text}")
                return "Мои мысли спутались... попробуй еще раз? 🧠"

            result = response.json()
            message = result['choices'][0]['message']

            # Если модель хочет вызвать функцию
            if message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    if tool_call["function"]["name"] == "create_calendar_event":
                        args = json.loads(tool_call["function"]["arguments"])
                        try:
                            # Парсим ISO строку из LLM
                            start_dt = datetime.fromisoformat(args["start_time"].replace('Z', ''))
                            success = await create_event(args["summary"], start_dt, args.get("duration", 30))
                            if success:
                                return f"Сделано! ✅ Записала в календарь: **{args['summary']}** на {start_dt.strftime('%d.%m в %H:%M')}."
                            else:
                                return "Ой, не удалось достучаться до календаря. Проверь настройки доступа. 📅"
                        except Exception as e:
                            logger.error(f"Error parsing date or calling calendar: {e}")
                            return "Что-то не так с датой, я запуталась в календаре... 🗓"

            return message['content'].strip()
            
    except Exception as e:
        logger.error(f"Mistral connection error: {e}")
        return "Кажется, я потеряла связь со своим облачным разумом... 🔌"
