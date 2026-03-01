from brains.config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client, Client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # SQL для создания таблицы media_cache
    # К сожалению, через python-клиент supabase нельзя выполнять произвольный SQL (только через RPC или Dashboard)
    # Поэтому мы просто проверим доступность
    
    logger.info("Пожалуйста, выполните следующий SQL в Dashboard Supabase (SQL Editor):")
    print("""
CREATE TABLE IF NOT EXISTS public.media_cache (
    key text NOT NULL,
    file_id text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT media_cache_pkey PRIMARY KEY (key)
);

ALTER TABLE public.media_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read" ON public.media_cache FOR SELECT USING (true);
CREATE POLICY "Allow service role all" ON public.media_cache USING (true) WITH CHECK (true);
    """)

if __name__ == "__main__":
    init_db()
