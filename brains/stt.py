import httpx
import logging
import os
import asyncio

logger = logging.getLogger(__name__)

# Hugging Face — обновленный URL
HF_TOKEN = os.environ.get('HF_TOKEN')
MODEL_ID = "openai/whisper-large-v3"
# Используем прямой эндпоинт модели, который работает стабильно
API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"

async def transcribe_voice(file_path: str) -> str:
    """Транскрибирует голосовое сообщение через Hugging Face"""
    if not HF_TOKEN:
        logger.error("HF_TOKEN не установлен!")
        return None

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(3):
                response = await client.post(API_URL, headers=headers, content=data)
                
                if response.status_code == 200:
                    result = response.json()
                    # HF возвращает либо {'text': '...'}, либо список с одним элементом
                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get('text')
                    return result.get('text')
                
                elif response.status_code == 503:
                    wait_time = 5
                    try:
                        wait_time = response.json().get('estimated_time', 5)
                    except: pass
                    logger.info(f"Модель HF загружается, ждем {wait_time}с...")
                    await asyncio.sleep(min(wait_time, 10))
                else:
                    logger.error(f"Ошибка HF API: {response.status_code}")
                    # Если получили HTML вместо JSON (ошибка 4xx/5xx), логгируем только статус
                    break
    except Exception as e:
        logger.error(f"Ошибка при транскрибации через Hugging Face: {e}")
    
    return None
