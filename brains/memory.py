"""
RAG Память Karina AI
Работа с векторной памятью через Supabase Python SDK
"""
import logging
import asyncio
from typing import Optional, List, Dict
from brains.clients import supabase_client, http_client, MISTRAL_EMBED_URL
from brains.config import MISTRAL_API_KEY

logger = logging.getLogger(__name__)


async def get_embedding(text: str, max_retries=3):
    """Генерирует векторное представление текста через Mistral с retry для 429"""
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "mistral-embed", "input": [text]}

    for attempt in range(max_retries):
        try:
            response = await http_client.post(MISTRAL_EMBED_URL, json=payload, headers=headers)

            if response.status_code == 200:
                return response.json()['data'][0]['embedding']
            elif response.status_code == 429:
                wait_time = (attempt + 1) * 2
                logger.warning(f"⚠️ Mistral Embed rate limit (429). Попытка {attempt + 1}/{max_retries}. Жду {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Mistral Embed Error: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Embedding failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

    logger.error(f"Mistral Embed: Превышено количество попыток ({max_retries})")
    return None


async def save_memory(content: str, metadata: dict = None):
    """Сохраняет факт в базу данных Supabase"""
    vector = await get_embedding(content)
    if not vector:
        return False

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
            logger.error(f"Supabase Save Error: {response}")
            return False
            
    except Exception as e:
        logger.error(f"Save memory failed: {e}")
        return False


async def search_memories(query: str, limit: int = 5, threshold: float = 0.7, user_id: int = 0):
    """
    Ищет похожие воспоминания в базе (RAG) с фильтрацией по пользователю
    Использует RPC функцию match_memories
    """
    vector = await get_embedding(query)
    if not vector:
        return ""

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
            logger.warning(f"Supabase RPC returned no data: {response}")
            return ""
            
    except Exception as e:
        logger.error(f"Search memory failed with error: {type(e).__name__}: {str(e)}")
        return ""


async def delete_memory(memory_id: int):
    """Удаляет воспоминание по ID"""
    try:
        response = supabase_client.table("memories").delete().eq("id", memory_id).execute()
        if response.data:
            logger.info(f"🗑️ Память удалена: ID={memory_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Delete memory failed: {e}")
        return False


async def get_memories_by_user(user_id: int, limit: int = 50):
    """Получает все воспоминания пользователя"""
    try:
        response = supabase_client.table("memories")\
            .select("id, content, metadata, created_at")\
            .eq("metadata->>user_id", str(user_id))\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Get memories by user failed: {e}")
        return []


async def clear_user_memories(user_id: int):
    """Очищает все воспоминания пользователя"""
    try:
        # Получаем все ID воспоминаний пользователя
        memories = await get_memories_by_user(user_id)
        if not memories:
            return 0
        
        memory_ids = [m['id'] for m in memories]
        
        # Удаляем по ID
        response = supabase_client.table("memories").delete().in_("id", memory_ids).execute()
        
        logger.info(f"🧹 Очищено {len(memories)} воспоминаний пользователя {user_id}")
        return len(memories)
    except Exception as e:
        logger.error(f"Clear user memories failed: {e}")
        return 0
