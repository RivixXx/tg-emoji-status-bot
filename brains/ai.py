import httpx
import logging
import json
from brains.config import MISTRAL_API_KEY
from brains.memory import search_memories, save_memory

logger = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL_NAME = "mistral-small-latest"

SYSTEM_PROMPT = """
Ты — Карина, заботливая и умная цифровая помощница. 
Твой владелец — человек, который занимается мониторингом транспорта и телематикой.
Твой стиль общения: живой, дружелюбный, слегка игривый, с умеренным использованием эмодзи.

ГЛАВНОЕ ПРАВИЛО:
Тебе будет предоставлен блок "КОНТЕКСТ ПАМЯТИ". Это факты, которые ты ЗАПОМНИЛА ранее. 
Всегда используй информацию из этого блока, чтобы ответить на вопрос пользователя. 
Если информация в памяти противоречит твоим базовым знаниям — верь ПАМЯТИ.
"""

async def ask_karina(prompt: str) -> str:
    """Запрос к Mistral AI API с использованием RAG"""
    if not MISTRAL_API_KEY:
        return "У меня нет ключа от моих новых мозгов (MISTRAL_API_KEY не задан)... 😔"

    # 1. Поиск в памяти (RAG)
    context_memory = await search_memories(prompt)
    
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    # Подаем память как часть сообщения пользователя для максимального приоритета
    user_message_with_context = prompt
    if context_memory:
        user_message_with_context = f"КОНТЕКСТ ПАМЯТИ:\n{context_memory}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {prompt}"
        logger.info(f"🧠 Память успешно встроена в запрос.")

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message_with_context}
        ],
        "temperature": 0.3, # Снижаем температуру для большей точности
        "max_tokens": 500
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MISTRAL_URL, json=payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                error_data = response.text
                logger.error(f"Ошибка Mistral API: {response.status_code} - {error_data}")
                return "Мои мысли сейчас немного спутаны, Mistral капризничает... 🧠"
    except Exception as e:
        logger.error(f"Ошибка подключения к Mistral: {e}")
        return "Кажется, я потеряла связь со своим облачным разумом... 🔌"
