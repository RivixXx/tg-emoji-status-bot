import httpx
from supabase import create_client, Client
from brains.config import SUPABASE_URL, SUPABASE_KEY

# Глобальный клиент для переиспользования соединений во всем приложении
http_client = httpx.AsyncClient(timeout=30.0)

# Supabase клиент для работы с базой данных
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Общие URL для Mistral
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_EMBED_URL = "https://api.mistral.ai/v1/embeddings"
MODEL_NAME = "mistral-small-latest"
