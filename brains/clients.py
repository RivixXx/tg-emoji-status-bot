"""
Глобальные клиенты для Karina AI
- HTTP клиент (httpx)
- Supabase клиент
- Mistral API endpoints
"""
import httpx
import logging
from typing import Optional
from supabase import create_client, Client

from brains.config import SUPABASE_URL, SUPABASE_KEY, MISTRAL_API_KEY

logger = logging.getLogger(__name__)

# ============================================================================
# HTTP КЛИЕНТ
# ============================================================================

# Глобальный клиент для переиспользования соединений
# Настроен с правильными таймаутами и retry
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=10.0, read=20.0, write=10.0),
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
    follow_redirects=True
)

# ============================================================================
# SUPABASE КЛИЕНТ
# ============================================================================

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Получает Supabase клиент с ленивой инициализацией
    
    Returns:
        Client или None если не удалось подключиться
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    # Проверяем наличие ключей
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("❌ SUPABASE_URL или SUPABASE_KEY не установлены")
        return None
    
    try:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase клиент инициализирован")
        return _supabase_client
    except SupabaseException as e:
        logger.error(f"❌ Ошибка инициализации Supabase: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при инициализации Supabase: {e}")
        return None


# Свойство для совместимости со старым кодом
@property
def supabase_client() -> Client:
    """Обратная совместимость — возвращает клиент или выбрасывает ошибку"""
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase клиент не инициализирован. Проверьте SUPABASE_URL и SUPABASE_KEY")
    return client


# ============================================================================
# MISTRAL API
# ============================================================================

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_EMBED_URL = "https://api.mistral.ai/v1/embeddings"
MISTRAL_VISION_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL_NAME = "mistral-small-latest"
VISION_MODEL = "pixtral-12b-2409"
EMBED_MODEL = "mistral-embed"


# ============================================================================
# ПРОВЕРКА ПОДКЛЮЧЕНИЙ
# ============================================================================

async def check_all_connections() -> dict:
    """
    Проверяет все подключения
    
    Returns:
        dict: {"supabase": bool, "mistral": bool, "errors": list}
    """
    result = {
        "supabase": False,
        "mistral": False,
        "errors": []
    }
    
    # Проверка Supabase
    try:
        client = get_supabase_client()
        if client:
            # Пробуем сделать простой запрос
            response = client.table("health_records").select("id").limit(1).execute()
            result["supabase"] = True
            logger.info("✅ Подключение к Supabase подтверждено")
    except Exception as e:
        result["errors"].append(f"Supabase: {e}")
        logger.error(f"❌ Supabase проверка не удалась: {e}")
    
    # Проверка Mistral
    try:
        if MISTRAL_API_KEY:
            response = await http_client.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
                timeout=5.0
            )
            if response.status_code == 200:
                result["mistral"] = True
                logger.info("✅ Подключение к Mistral API подтверждено")
            else:
                result["errors"].append(f"Mistral: {response.status_code}")
    except Exception as e:
        result["errors"].append(f"Mistral: {e}")
        logger.error(f"❌ Mistral проверка не удалась: {e}")
    
    return result
