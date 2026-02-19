-- Инициализация базы данных Karina AI

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

-- Комментарии
COMMENT ON TABLE health_records IS 'История напоминаний о здоровье (уколы, замеры)';
COMMENT ON TABLE memories IS 'Векторная память для RAG (долговременная память Карины)';
