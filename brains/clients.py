import httpx

# Глобальный клиент для переиспользования соединений во всем приложении
http_client = httpx.AsyncClient(timeout=30.0)

# Общие URL для Mistral
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_EMBED_URL = "https://api.mistral.ai/v1/embeddings"
MODEL_NAME = "mistral-small-latest"
