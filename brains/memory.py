import httpx
import logging
import json
import asyncio
from typing import Optional, List, Dict
from brains.config import MISTRAL_API_KEY, SUPABASE_URL, SUPABASE_KEY
# Импортируем из общего модуля clients
from brains.clients import http_client, MISTRAL_EMBED_URL

logger = logging.getLogger(__name__)

SUPABASE_RPC_URL = f"{SUPABASE_URL}/rest/v1/rpc/match_memories"
SUPABASE_REST_URL = f"{SUPABASE_URL}/rest/v1/memories"

async def get_embedding(text: str, max_retries=3):
    """Генерирует векторное представление текста через Mistral с retry для 429"""
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "mistral-embed", "input": [text]}

    for attempt in range(max_retries):
        try:
            # Используем глобальный http_client
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
    if not vector: return False
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    payload = {
        "content": content,
        "embedding": vector,
        "metadata": metadata or {}
    }
    
    try:
        response = await http_client.post(SUPABASE_REST_URL, json=payload, headers=headers)
        if response.status_code not in [201, 204, 200]:
            logger.error(f"Supabase Save Error: {response.status_code} - {response.text}")
        return response.status_code in [201, 204, 200]
    except Exception as e:
        logger.error(f"Save memory failed: {e}")
    return False

async def search_memories(query: str, limit: int = 5, threshold: float = 0.7, user_id: int = 0):
    """
    Ищет похожие воспоминания в базе (RAG) с фильтрацией по пользователю
    """
    vector = await get_embedding(query)
    if not vector: return ""
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query_embedding": vector,
        "match_threshold": threshold,
        "match_count": limit,
        "filter_user_id": user_id  # Передаем ID для фильтрации в RPC
    }
    
    try:
        response = await http_client.post(SUPABASE_RPC_URL, json=payload, headers=headers)
        if response.status_code == 200:
            results = response.json()
            if not results: 
                logger.info(f"🔍 Память: Ничего не найдено (порог {threshold}) для '{query}'")
                return ""
            
            logger.info(f"🧠 Память: Найдено {len(results)} фактов (порог {threshold})")
            return "\n".join([f"- {r['content']}" for r in results])
        else:
            logger.error(f"Supabase RPC Error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Search memory failed: {e}")
    return ""
