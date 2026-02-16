import httpx
import logging
import os
import asyncio

logger = logging.getLogger(__name__)

# Hugging Face — Переход на новый Router API
HF_TOKEN = os.environ.get('HF_TOKEN')
MODEL_ID = "openai/whisper-large-v3"
# Hugging Face теперь рекомендует использовать router.huggingface.co
API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_ID}"

async def transcribe_voice(file_path: str) -> str:
    """Транскрибирует голосовое сообщение через Hugging Face Router API"""
    if not HF_TOKEN:
        logger.error("HF_TOKEN не установлен!")
        return None

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(3):
                # Некоторые модели требуют отправки данных как бинарный поток
                response = await client.post(API_URL, headers=headers, content=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get('text')
                    return result.get('text')
                
                elif response.status_code == 503:
                    logger.info("Модель HF загружается, ждем 10с...")
                    await asyncio.sleep(10)
                else:
                    logger.error(f"Ошибка HF API: {response.status_code} - {response.text[:100]}")
                    break
    except Exception as e:
        logger.error(f"Ошибка при транскрибации через Hugging Face: {e}")
    
    return None
