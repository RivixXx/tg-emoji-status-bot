import httpx
import logging
import os
import asyncio

logger = logging.getLogger(__name__)

# Hugging Face — отличная бесплатная альтернатива
HF_TOKEN = os.environ.get('HF_TOKEN')
MODEL_ID = "openai/whisper-large-v3"
API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"

async def transcribe_voice(file_path: str) -> str:
    """Транскрибирует голосовое сообщение через Hugging Face Inference API"""
    if not HF_TOKEN:
        logger.error("HF_TOKEN не установлен!")
        return None

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Иногда модели на HF нужно время, чтобы "проснуться"
            for attempt in range(3):
                response = await client.post(API_URL, headers=headers, content=data)
                
                if response.status_code == 200:
                    return response.json().get('text')
                elif response.status_code == 503:
                    # Модель загружается, подождем немного
                    wait_time = response.json().get('estimated_time', 20)
                    logger.info(f"Модель HF загружается, ждем {wait_time}с...")
                    await asyncio.sleep(min(wait_time, 5))
                else:
                    logger.error(f"Ошибка HF API: {response.status_code} - {response.text}")
                    break
    except Exception as e:
        logger.error(f"Ошибка при транскрибации через Hugging Face: {e}")
    
    return None
