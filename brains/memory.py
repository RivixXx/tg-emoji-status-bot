"""
RAG Память Karina AI
Работа с векторной памятью через Supabase Python SDK
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from brains.clients import supabase_client, http_client, MISTRAL_EMBED_URL
from brains.config import MISTRAL_API_KEY

logger = logging.getLogger(__name__)


async def get_embedding(text: str, max_retries: int = 3) -> Optional[List[float]]:
    """
    Генерирует векторное представление текста через Mistral с retry для 429.
    
    Args:
        text: Текст для эмбеддинга
        max_retries: Максимальное количество попыток
    
    Returns:
        Вектор эмбеддинга или None при ошибке
    """
    if not MISTRAL_API_KEY:
        logger.error("❌ MISTRAL_API_KEY не установлен")
        return None

    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "mistral-embed", "input": [text]}

    for attempt in range(max_retries):
        try:
            response = await http_client.post(MISTRAL_EMBED_URL, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    return data['data'][0]['embedding']
                else:
                    logger.error(f"❌ Mistral Embed: пустой ответ")
                    return None

            elif response.status_code == 429:
                # Rate limit — экспоненциальная задержка
                wait_time = (attempt + 1) * 2
                logger.warning(f"⚠️ Mistral Embed rate limit (429). Попытка {attempt + 1}/{max_retries}. Жду {wait_time}s...")
                await asyncio.sleep(wait_time)
                # Не считаем за failure, продолжаем retry

            elif response.status_code == 401:
                logger.error("🔐 Mistral Embed Authentication Error (401). Проверьте API ключ.")
                return None

            elif response.status_code == 400:
                logger.error(f"❌ Mistral Embed Bad Request (400): {response.text[:200]}")
                return None

            else:
                logger.error(f"❌ Mistral Embed Error: {response.status_code} - {response.text[:200]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

        except httpx.TimeoutException as e:
            logger.error(f"⌛️ Mistral Embed Timeout (attempt {attempt + 1}/{max_retries}): {type(e).__name__}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

        except httpx.ConnectError as e:
            logger.error(f"🔌 Mistral Embed Connect Error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)

        except httpx.RequestError as e:
            logger.error(f"❌ Mistral Embed Request Error (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

        except Exception as e:
            logger.exception(f"💥 Mistral Embed Unexpected Error (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
            return None

    logger.error(f"❌ Mistral Embed: Превышено количество попыток ({max_retries})")
    return None


async def save_memory(content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Сохраняет факт в базу данных Supabase с retry logic.
    
    Args:
        content: Текст воспоминания
        metadata: Дополнительные метаданные
    
    Returns:
        True если успешно, False иначе
    """
    if not supabase_client:
        logger.error("❌ Supabase клиент не инициализирован")
        return False

    vector = await get_embedding(content)
    if not vector:
        logger.warning(f"⚠️ Не удалось получить эмбеддинг для: {content[:50]}...")
        return False

    # Retry logic для Supabase запроса
    max_retries = 3
    for attempt in range(max_retries):
        try:
            data = {
                "content": content,
                "embedding": vector,
                "metadata": metadata or {}
            }

            response = supabase_client.table("memories").insert(data).execute()

            if response.data:
                logger.info(f"💾 Память сохранена: {content[:50]}...")
                return True
            else:
                logger.error(f"❌ Supabase Save Error: {response}")
                # Пробуем снова при пустом ответе
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

        except asyncio.TimeoutError:
            logger.error(f"⌛️ Supabase Save Timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)

        except Exception as e:
            # Логгируем конкретную ошибку
            logger.error(f"❌ Save memory failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

    logger.error(f"❌ Save memory: Превышено количество попыток ({max_retries})")
    return False


async def search_memories(query: str, limit: int = 5, threshold: float = 0.7, user_id: int = 0) -> str:
    """
    Ищет похожие воспоминания в базе (RAG) с фильтрацией по пользователю.
    Использует RPC функцию match_memories.
    
    Args:
        query: Текст запроса для поиска
        limit: Максимальное количество результатов
        threshold: Порог схожести (0.0-1.0)
        user_id: ID пользователя для фильтрации
    
    Returns:
        Строка с найденными воспоминаниями или пустая строка
    """
    if not supabase_client:
        logger.debug("⚠️ Supabase клиент не инициализирован")
        return ""

    vector = await get_embedding(query)
    if not vector:
        logger.warning(f"⚠️ Не удалось получить эмбеддинг для запроса: {query[:30]}...")
        return ""

    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Вызов RPC функции с параметрами
            response = supabase_client.rpc(
                "match_memories",
                {
                    "query_embedding": vector,
                    "match_threshold": threshold,
                    "match_count": limit,
                    "filter_user_id": user_id
                }
            ).execute()

            if response.data:
                results = response.data
                if not results:
                    logger.info(f"🔍 Память: Ничего не найдено (порог {threshold}) для '{query[:30]}'")
                    return ""

                logger.info(f"🧠 Память: Найдено {len(results)} фактов (порог {threshold})")
                return "\n".join([f"- {r['content']}" for r in results])
            else:
                logger.warning(f"⚠️ Supabase RPC returned no data (attempt {attempt + 1}/{max_retries}): {response}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return ""

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Память: Таймаут запроса к Supabase (attempt {attempt + 1}/{max_retries}, >60с)")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
            else:
                return ""

        except Exception as e:
            logger.error(f"❌ Search memory failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return ""

    return ""


async def delete_memory(memory_id: int) -> bool:
    """
    Удаляет воспоминание по ID.
    
    Args:
        memory_id: ID воспоминания для удаления
    
    Returns:
        True если успешно, False иначе
    """
    if not supabase_client:
        logger.error("❌ Supabase клиент не инициализирован")
        return False

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = supabase_client.table("memories").delete().eq("id", memory_id).execute()

            if response.data:
                logger.info(f"🗑️ Память удалена: ID={memory_id}")
                return True
            else:
                logger.warning(f"⚠️ Память не найдена или не удалена: ID={memory_id}")
                return False

        except asyncio.TimeoutError:
            logger.error(f"⌛️ Delete memory timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"❌ Delete memory failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

    return False


async def get_memories_by_user(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Получает все воспоминания пользователя.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество результатов
    
    Returns:
        Список воспоминаний или пустой список при ошибке
    """
    if not supabase_client:
        logger.error("❌ Supabase клиент не инициализирован")
        return []

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = supabase_client.table("memories")\
                .select("id, content, metadata, created_at")\
                .eq("metadata->>user_id", str(user_id))\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()

            if response.data:
                return response.data
            else:
                logger.info(f"ℹ️ У пользователя {user_id} нет воспоминаний")
                return []

        except asyncio.TimeoutError:
            logger.error(f"⌛️ Get memories by user timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"❌ Get memories by user failed (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

    return []


async def clear_user_memories(user_id: int) -> int:
    """
    Очищает все воспоминания пользователя.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Количество удалённых воспоминаний или 0 при ошибке
    """
    if not supabase_client:
        logger.error("❌ Supabase клиент не инициализирован")
        return 0

    try:
        # Получаем все ID воспоминаний пользователя
        memories = await get_memories_by_user(user_id)
        if not memories:
            logger.info(f"ℹ️ Нет воспоминаний для очистки у пользователя {user_id}")
            return 0

        memory_ids = [m['id'] for m in memories]

        # Удаляем по ID
        response = supabase_client.table("memories").delete().in_("id", memory_ids).execute()

        logger.info(f"🧹 Очищено {len(memories)} воспоминаний пользователя {user_id}")
        return len(memories)

    except asyncio.TimeoutError:
        logger.error(f"⌛️ Clear user memories timeout")
        return 0

    except Exception as e:
        logger.error(f"❌ Clear user memories failed: {type(e).__name__} - {e}")
        return 0
