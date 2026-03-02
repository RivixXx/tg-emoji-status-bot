"""
Модуль компьютерного зрения Karina AI
- Распознавание текста (OCR)
- Анализ изображений
- Извлечение данных
- Описание и пояснение
- Поиск по проанализированным изображениям

Используется Mistral AI (Pixtral) для мультимодального анализа
"""
import base64
import logging
import os
import httpx
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from brains.clients import http_client, supabase_client
from brains.config import MISTRAL_API_KEY

logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

MISTRAL_VISION_URL = "https://api.mistral.ai/v1/chat/completions"
VISION_MODEL = "pixtral-12b-2409"  # Мультимодальная модель Mistral

MAX_IMAGE_SIZE_MB = 10
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']

# Папка для временного хранения
TEMP_DIR = Path("temp/vision")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# УТИЛИТЫ
# ============================================================================

def encode_image_to_base64(image_path: str) -> str:
    """Кодирует изображение в base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_image_mime_type(image_path: str) -> str:
    """Определяет MIME тип изображения"""
    ext = Path(image_path).suffix.lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.gif': 'image/gif'
    }
    return mime_types.get(ext, 'image/jpeg')


def validate_image(image_path: str) -> Tuple[bool, str]:
    """
    Проверяет корректность изображения
    
    Returns:
        (успех, сообщение)
    """
    if not os.path.exists(image_path):
        return False, "Файл не найден"
    
    ext = Path(image_path).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        return False, f"Неподдерживаемый формат. Допустимы: {', '.join(SUPPORTED_FORMATS)}"
    
    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        return False, f"Файл слишком большой ({size_mb:.1f}МБ). Максимум: {MAX_IMAGE_SIZE_MB}МБ"
    
    return True, "OK"


# ============================================================================
# ОСНОВНОЙ АНАЛИЗ
# ============================================================================

async def analyze_image(
    image_path: str,
    prompt: str = "Опиши что на этом изображении",
    user_id: int = 0,
    save_to_history: bool = True
) -> Dict:
    """
    Анализирует изображение через Mistral AI
    
    Args:
        image_path: Путь к файлу изображения
        prompt: Запрос к AI
        user_id: ID пользователя
        save_to_history: Сохранить ли в историю
    
    Returns:
        {
            "success": bool,
            "description": str,
            "text_content": str,  # если есть текст
            "objects": list,  # распознанные объекты
            "analysis": str,  # развёрнутый анализ
            "error": str  # если ошибка
        }
    """
    # Проверка файла
    valid, message = validate_image(image_path)
    if not valid:
        return {"success": False, "error": message}
    
    if not MISTRAL_API_KEY:
        return {"success": False, "error": "Нет ключа Mistral API"}
    
    try:
        # Кодируем изображение
        base64_image = encode_image_to_base64(image_path)
        mime_type = get_image_mime_type(image_path)
        
        # Формируем запрос
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": f"data:{mime_type};base64,{base64_image}"
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.3
        }
        
        # Отправляем запрос
        response = await http_client.post(MISTRAL_VISION_URL, json=payload, headers=headers, timeout=60.0)
        
        if response.status_code != 200:
            logger.error(f"Vision API error: {response.status_code} - {response.text[:200]}")
            return {
                "success": False,
                "error": f"API error: {response.status_code}"
            }
        
        result = response.json()
        analysis_text = result['choices'][0]['message']['content']
        
        # Сохраняем в историю
        if save_to_history:
            await save_vision_analysis(
                user_id=user_id,
                image_path=image_path,
                prompt=prompt,
                analysis=analysis_text
            )
        
        # Извлекаем текст если есть (для OCR)
        text_content = await extract_text_from_analysis(analysis_text)
        
        return {
            "success": True,
            "description": analysis_text,
            "text_content": text_content,
            "analysis": analysis_text
        }
        
    except httpx.TimeoutException:
        logger.error("Vision API timeout")
        return {"success": False, "error": "Превышено время ожидания ответа API"}
    except Exception as e:
        logger.error(f"Vision analysis error: {e}")
        return {"success": False, "error": str(e)}


async def extract_text_from_analysis(analysis: str) -> Optional[str]:
    """
    Пытается извлечь распознанный текст из анализа
    (если AI вернул текст с изображения)
    """
    # Пока просто возвращаем анализ
    # В будущем можно парсить структурированно
    return analysis


# ============================================================================
# СПЕЦИАЛИЗИРОВАННЫЕ ФУНКЦИИ
# ============================================================================

async def ocr_image(image_path: str, user_id: int = 0) -> Dict:
    """
    Распознавание текста на изображении (OCR)
    
    Returns:
        {
            "success": bool,
            "text": str,  # распознанный текст
            "structured": dict,  # структурированные данные
            "confidence": float
        }
    """
    prompt = """
Внимательно прочитай весь текст на этом изображении.

Верни ответ в формате:
1. ПОЛНЫЙ ТЕКСТ: (дословно всё что видишь)
2. СТРУКТУРА: (если это документ, таблица, чек — разбери по полям)
3. ЯЗЫК: (определи язык текста)

Если текста нет — напиши "Текст не обнаружен".
"""
    
    result = await analyze_image(image_path, prompt, user_id)
    
    if not result["success"]:
        return result
    
    # Парсим ответ AI
    text = result.get("description", "")
    
    # Пытаемся извлечь структурированные данные
    structured = None
    if "СТРУКТУРА:" in text:
        structured_part = text.split("СТРУКТУРА:")[1].split("ЯЗЫК:")[0] if "ЯЗЫК:" in text else text.split("СТРУКТУРА:")[1]
        structured = structured_part.strip()
    
    return {
        "success": True,
        "text": text,
        "structured": structured,
        "confidence": 0.9  # Пока заглушка
    }


async def analyze_document(image_path: str, user_id: int = 0) -> Dict:
    """
    Анализ документа (паспорт, права, справка и т.д.)
    
    Returns:
        {
            "success": bool,
            "document_type": str,
            "fields": dict,
            "full_text": str
        }
    """
    prompt = """
Проанализируй этот документ. Определи:

1. ТИП ДОКУМЕНТА: (паспорт, права, справка, счёт, договор и т.д.)
2. ИЗВЛЕКИ ВСЕ ПОЛЯ: (ФИО, дата, номер, сумма и т.д.)
3. ПОЛНЫЙ ТЕКСТ: (дословно)
4. ВАЖНЫЕ ДЕТАЛИ: (сроки действия, суммы, обязательства)

Верни ответ в структурированном формате JSON если возможно.
"""
    
    result = await analyze_image(image_path, prompt, user_id)
    
    if not result["success"]:
        return result
    
    # Парсим ответ
    analysis = result.get("description", "")
    
    # Пытаемся извлечь тип документа
    doc_type = "Не определён"
    if "ТИП ДОКУМЕНТА:" in analysis:
        doc_type = analysis.split("ТИП ДОКУМЕНТА:")[1].split("\n")[0].strip()
    
    return {
        "success": True,
        "document_type": doc_type,
        "fields": analysis,  # Пока вся информация
        "full_text": analysis
    }


async def analyze_receipt(image_path: str, user_id: int = 0) -> Dict:
    """
    Анализ чека или счёта
    
    Returns:
        {
            "success": bool,
            "store": str,
            "date": str,
            "total": str,
            "items": list,
            "full_text": str
        }
    """
    prompt = """
Проанализируй этот чек/счёт. Извлеки:

1. МАГАЗИН/ОРГАНИЗАЦИЯ: название
2. ДАТА И ВРЕМЯ: когда покупка
3. СУММА: общая стоимость
4. ТОВАРЫ/УСЛУГИ: список позиций с ценами
5. ФОРМА ОПЛАТЫ: наличные/карта

Верни в структурированном виде.
"""
    
    result = await analyze_image(image_path, prompt, user_id)
    
    if not result["success"]:
        return result
    
    analysis = result.get("description", "")
    
    return {
        "success": True,
        "full_analysis": analysis
    }


async def analyze_photo_scene(image_path: str, user_id: int = 0) -> Dict:
    """
    Анализ сцены на фотографии (люди, объекты, обстановка)
    
    Returns:
        {
            "success": bool,
            "description": str,
            "objects": list,
            "people_count": int,
            "location_type": str,
            "mood": str
        }
    """
    prompt = """
Детально опиши что на фотографии:

1. ОБСТАНОВКА: где сделано фото (офис, улица, дом, природа)
2. ОБЪЕКТЫ: что видишь (мебель, техника, транспорт и т.д.)
3. ЛЮДИ: сколько человек, что делают
4. НАСТРОЕНИЕ: атмосфера (деловая, праздничная, спокойная)
5. ДЕТАЛИ: важные мелочи (вывески, знаки, надписи)

Будь максимально подробным.
"""
    
    result = await analyze_image(image_path, prompt, user_id)
    
    if not result["success"]:
        return result
    
    return {
        "success": True,
        "description": result.get("description", ""),
        "full_analysis": result.get("description", "")
    }


async def analyze_screenshot(image_path: str, user_id: int = 0) -> Dict:
    """
    Анализ скриншота (интерфейс, ошибка, переписка)
    
    Returns:
        {
            "success": bool,
            "type": str,  # сайт, приложение, ошибка, чат
            "content": str,
            "action_needed": str  # что делать
        }
    """
    prompt = """
Проанализируй этот скриншот:

1. ТИП: что это (сайт, приложение, ошибка, чат, документ)
2. СОДЕРЖИМОЕ: что показано
3. ТЕКСТ: весь видимый текст
4. ДЕЙСТВИЕ: если это ошибка — как исправить; если чат — о чём речь

Дай полезное объяснение что делать с этой информацией.
"""
    
    result = await analyze_image(image_path, prompt, user_id)
    
    if not result["success"]:
        return result
    
    return {
        "success": True,
        "full_analysis": result.get("description", "")
    }


# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================

async def save_vision_analysis(
    user_id: int,
    image_path: str,
    prompt: str,
    analysis: str,
    metadata: Dict = None
):
    """Сохраняет анализ изображения в БД"""
    try:
        # Создаём миниатюру или хэш для хранения
        import hashlib
        with open(image_path, "rb") as f:
            image_hash = hashlib.md5(f.read()).hexdigest()
        
        data = {
            "user_id": user_id,
            "image_hash": image_hash,
            "original_filename": os.path.basename(image_path),
            "prompt": prompt,
            "analysis": analysis,
            "metadata": metadata or {}
        }
        
        response = supabase_client.table("vision_history").insert(data).execute()
        logger.info(f"💾 Vision анализ сохранён: {image_hash[:8]}...")
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error saving vision analysis: {e}")
        return False


async def search_vision_history(user_id: int, query: str, limit: int = 10) -> List[Dict]:
    """
    Поиск по проанализированным изображениям
    
    Ищет по тексту анализа
    """
    try:
        # Простой поиск по тексту
        response = supabase_client.table("vision_history")\
            .select("*")\
            .eq("user_id", user_id)\
            .ilike("analysis", f"%{query}%")\
            .order("analyzed_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error searching vision history: {e}")
        return []


async def get_vision_history(user_id: int, days: int = 30, limit: int = 20) -> List[Dict]:
    """Получает историю анализа изображений"""
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        response = supabase_client.table("vision_history")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("analyzed_at", cutoff.isoformat())\
            .order("analyzed_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting vision history: {e}")
        return []