-- ============================================================================
-- KARINA AI — SUPABASE DATABASE INIT SCRIPT
-- ============================================================================
-- Этот скрипт создаёт все необходимые таблицы для работы бота
-- Выполните в SQL Editor Supabase или через psql
-- ============================================================================

-- Включаем расширение pgvector для RAG памяти
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 1. HEALTH RECORDS — История здоровья (уколы, замеры)
-- ============================================================================
CREATE TABLE IF NOT EXISTS health_records (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    confirmed BOOLEAN DEFAULT TRUE,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    date DATE NOT NULL,
    time TIME,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_user_date ON health_records(user_id, date);
CREATE INDEX IF NOT EXISTS idx_health_timestamp ON health_records(timestamp);

COMMENT ON TABLE health_records IS 'История подтверждений здоровья (уколы, замеры)';

-- ============================================================================
-- 2. MEMORIES — RAG память (векторный поиск)
-- ============================================================================
CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT DEFAULT 0,
    content TEXT NOT NULL,
    embedding vector(1024),  -- Mistral embed размер
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);

-- Векторный индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_memories_embedding 
ON memories USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

COMMENT ON TABLE memories IS 'Долговременная память с векторным поиском (RAG)';

-- ============================================================================
-- 3. REMINDERS — Умные напоминания
-- ============================================================================
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    user_id BIGINT DEFAULT 0,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    scheduled_time TIMESTAMPTZ NOT NULL,
    escalate_after JSONB DEFAULT '[10, 30, 60]',
    current_level TEXT DEFAULT 'soft',
    is_active BOOLEAN DEFAULT TRUE,
    is_confirmed BOOLEAN DEFAULT FALSE,
    snooze_until TIMESTAMPTZ,
    context JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(is_active);
CREATE INDEX IF NOT EXISTS idx_reminders_scheduled ON reminders(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id);

COMMENT ON TABLE reminders IS 'Активные и архивные напоминания с эскалацией';

-- ============================================================================
-- 4. AURA SETTINGS — Настройки аур
-- ============================================================================
CREATE TABLE IF NOT EXISTS aura_settings (
    user_id BIGINT PRIMARY KEY,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aura_user ON aura_settings(user_id);

COMMENT ON TABLE aura_settings IS 'Настройки аур пользователей (emoji, bio, напоминания)';

-- ============================================================================
-- 5. EMPLOYEES — База сотрудников
-- ============================================================================
CREATE TABLE IF NOT EXISTS employees (
    id BIGSERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    position TEXT,
    department TEXT,
    birthday DATE,
    characteristics TEXT,
    email TEXT,
    phone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department);
CREATE INDEX IF NOT EXISTS idx_employees_birthday ON employees(birthday);

COMMENT ON TABLE employees IS 'База сотрудников компании с днями рождения';

-- ============================================================================
-- 6. NEWS HISTORY — История показанных новостей
-- ============================================================================
CREATE TABLE IF NOT EXISTS news_history (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    link TEXT UNIQUE NOT NULL,
    source TEXT,
    category TEXT,
    published_at TIMESTAMPTZ,
    shown_at TIMESTAMPTZ DEFAULT NOW(),
    user_id BIGINT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_news_link ON news_history(link);
CREATE INDEX IF NOT EXISTS idx_news_shown ON news_history(shown_at);
CREATE INDEX IF NOT EXISTS idx_news_user ON news_history(user_id);

COMMENT ON TABLE news_history IS 'История показанных новостей для фильтрации дублей';

-- ============================================================================
-- 7. HABITS — Трекер привычек
-- ============================================================================
CREATE TABLE IF NOT EXISTS habits (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    habit_name TEXT NOT NULL,
    completed BOOLEAN DEFAULT TRUE,
    notes TEXT,
    date DATE NOT NULL,
    tracked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_habits_user_date ON habits(user_id, date);
CREATE INDEX IF NOT EXISTS idx_habits_name ON habits(habit_name);

COMMENT ON TABLE habits IS 'Отслеживание выполнения привычек';

-- ============================================================================
-- 8. WORK SESSIONS — Рабочие сессии
-- ============================================================================
CREATE TABLE IF NOT EXISTS work_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    duration_hours NUMERIC(5,2),
    meetings_count INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_work_user_date ON work_sessions(user_id, date);
CREATE INDEX IF NOT EXISTS idx_work_duration ON work_sessions(duration_hours);

COMMENT ON TABLE work_sessions IS 'Автотрекинг рабочих сессий по календарю';

-- ============================================================================
-- 9. VISION HISTORY — История анализа изображений
-- ============================================================================
CREATE TABLE IF NOT EXISTS vision_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    image_hash TEXT NOT NULL,
    original_filename TEXT,
    prompt TEXT,
    analysis TEXT,
    metadata JSONB DEFAULT '{}',
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vision_user ON vision_history(user_id);
CREATE INDEX IF NOT EXISTS idx_vision_hash ON vision_history(image_hash);
CREATE INDEX IF NOT EXISTS idx_vision_analysis ON vision_history USING gin(to_tsvector('russian', analysis));

COMMENT ON TABLE vision_history IS 'История анализа изображений (OCR, документы, чеки)';

-- ============================================================================
-- 10. TTS SETTINGS — Настройки синтеза речи
-- ============================================================================
CREATE TABLE IF NOT EXISTS tts_settings (
    user_id BIGINT PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    voice TEXT DEFAULT 'v3_1_ru',
    volume REAL DEFAULT 1.0,
    speed REAL DEFAULT 1.0,
    auto_voice_for_voice BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tts_user ON tts_settings(user_id);

COMMENT ON TABLE tts_settings IS 'Настройки TTS (текст-в-речь) для пользователей';

-- ============================================================================
-- 11. VPN USERS — Пользователи VPN (для Marzban интеграции)
-- ============================================================================
CREATE TABLE IF NOT EXISTS vpn_users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    state TEXT DEFAULT 'NEW',
    trial_used BOOLEAN DEFAULT FALSE,
    referred_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_state ON vpn_users(state);
CREATE INDEX IF NOT EXISTS idx_vpn_referred ON vpn_users(referred_by);

COMMENT ON TABLE vpn_users IS 'Пользователи VPN магазина';

-- ============================================================================
-- 12. PAYMENTS — Платежи
-- ============================================================================
CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount NUMERIC(10,2),
    currency TEXT,
    status TEXT DEFAULT 'pending',
    invoice_id TEXT UNIQUE,
    payment_method TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

COMMENT ON TABLE payments IS 'История платежей за VPN';

-- ============================================================================
-- RPC ФУНКЦИЯ ДЛЯ ПОИСКА ПАМЯТИ (RAG)
-- ============================================================================
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding vector(1024),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_user_id BIGINT DEFAULT 0
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.content,
        m.metadata,
        m.created_at,
        1 - (m.embedding <=> query_embedding) AS similarity
    FROM memories m
    WHERE 1 - (m.embedding <=> query_embedding) > match_threshold
      AND (filter_user_id = 0 OR m.user_id = filter_user_id)
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION match_memories IS 'Поиск похожих воспоминаний по вектору (RAG)';

-- ============================================================================
-- TRIGGERS ДЛЯ АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применяем триггеры к таблицам с updated_at
CREATE TRIGGER update_aura_settings_updated_at
    BEFORE UPDATE ON aura_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_employees_updated_at
    BEFORE UPDATE ON employees
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reminders_updated_at
    BEFORE UPDATE ON reminders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tts_settings_updated_at
    BEFORE UPDATE ON tts_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vpn_users_updated_at
    BEFORE UPDATE ON vpn_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) — ОПЦИОНАЛЬНО
-- ============================================================================
-- Включаем RLS для безопасности (если нужно)
-- ALTER TABLE health_records ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
-- и т.д.

-- ============================================================================
-- ПРИМЕРЫ ДАННЫХ (SEED) — ОПЦИОНАЛЬНО
-- ============================================================================

-- Пример сотрудника
INSERT INTO employees (full_name, position, department, birthday, characteristics)
VALUES 
    ('Иванов Иван', 'Разработчик', 'IT', '1990-05-15', 'Любит кофе и код'),
    ('Петрова Анна', 'Менеджер', 'Продажи', '1988-08-20', 'Душа компании')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- ГОТОВО!
-- ============================================================================
