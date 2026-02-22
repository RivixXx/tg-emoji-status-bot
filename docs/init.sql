-- Инициализация базы данных Karina AI (v2.0 - SaaS Ready)

-- Расширение для векторного поиска
CREATE EXTENSION IF NOT EXISTS vector;

-- Таблица для истории здоровья (уколы, замеры)
CREATE TABLE IF NOT EXISTS health_records (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    confirmed BOOLEAN DEFAULT true,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    date DATE DEFAULT CURRENT_DATE,
    time TIME DEFAULT CURRENT_TIME,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для RAG памяти (векторный поиск)
CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_health_date ON health_records(date DESC);
CREATE INDEX IF NOT EXISTS idx_health_user ON health_records(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memories_metadata_user ON memories USING gin (metadata);

-- Функция для поиска в памяти с фильтрацией по user_id
CREATE OR REPLACE FUNCTION match_memories (
  query_embedding vector(1024),
  match_threshold float,
  match_count int,
  filter_user_id bigint DEFAULT 0
)
RETURNS TABLE (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    memories.id,
    memories.content,
    memories.metadata,
    1 - (memories.embedding <=> query_embedding) AS similarity
  FROM memories
  WHERE 
    (filter_user_id = 0 OR (memories.metadata->>'user_id')::bigint = filter_user_id)
    AND 1 - (memories.embedding <=> query_embedding) > match_threshold
  ORDER BY memories.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Таблица для умных напоминаний
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    scheduled_time TIMESTAMPTZ NOT NULL,
    escalate_after JSONB DEFAULT '[]',
    current_level TEXT DEFAULT 'soft',
    is_active BOOLEAN DEFAULT true,
    is_confirmed BOOLEAN DEFAULT false,
    snooze_until TIMESTAMPTZ,
    context JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для настроек аур
CREATE TABLE IF NOT EXISTS aura_settings (
    user_id BIGINT PRIMARY KEY,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для напоминаний
CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_reminders_scheduled ON reminders(scheduled_time) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_reminders_type ON reminders(type);

-- Индексы для настроек аур
CREATE INDEX IF NOT EXISTS idx_aura_settings_user ON aura_settings(user_id);

-- Комментарии
COMMENT ON TABLE health_records IS 'История напоминаний о здоровье (уколы, замеры)';
COMMENT ON TABLE memories IS 'Векторная память для RAG (долговременная память Карины)';
COMMENT ON TABLE reminders IS 'Умные напоминания с эскалацией и персистентностью';
