import httpx
import logging
import json
from brains.config import MISTRAL_API_KEY, SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

MISTRAL_EMBED_URL = "https://api.mistral.ai/v1/embeddings"
SUPABASE_RPC_URL = f"{SUPABASE_URL}/rest/v1/rpc/match_memories"
SUPABASE_REST_URL = f"{SUPABASE_URL}/rest/v1/memories"

async def get_embedding(text: str):
    """Генерирует векторное представление текста через Mistral"""
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "mistral-embed", "input": [text]}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(MISTRAL_EMBED_URL, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()['data'][0]['embedding']
            logger.error(f"Mistral Embed Error: {response.status_code}")
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
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
        async with httpx.AsyncClient() as client:
            response = await client.post(SUPABASE_REST_URL, json=payload, headers=headers)
            if response.status_code not in [201, 204, 200]:
                logger.error(f"Supabase Save Error: {response.status_code} - {response.text}")
            return response.status_code in [201, 204, 200]
    except Exception as e:
        logger.error(f"Save memory failed: {e}")
    return False

async def search_memories(query: str, limit: int = 3):
    """Ищет похожие воспоминания в базе"""
    vector = await get_embedding(query)
    if not vector: return ""
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query_embedding": vector,
        "match_threshold": 0.1,
        "match_count": limit
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(SUPABASE_RPC_URL, json=payload, headers=headers)
            if response.status_code == 200:
                results = response.json()
                if not results: 
                    logger.info(f"🔍 Память: Ничего не найдено (порог 0.1) для '{query}'")
                    return ""
                
                logger.info(f"🧠 Память: Найдено {len(results)} фактов.")
                return "\n".join([f"- {r['content']}" for r in results])
            else:
                logger.error(f"Supabase RPC Error: {response.status_code} - {response.text}")
    except Exception as e:
    except Exception as e:
        logger.error(f"Search memory failed: {e}")
    return ""
