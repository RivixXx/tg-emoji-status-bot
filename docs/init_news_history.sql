-- ============================================================================
-- Karina AI: Таблица для истории новостей
-- ============================================================================
-- Дата: Февраль 2026
-- Описание: Отслеживание показанных новостей для предотвращения дублей
-- ============================================================================

-- Таблица для истории новостей (отслеживание просмотренных)
CREATE TABLE IF NOT EXISTS news_history (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    link TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    category TEXT,
    published_at TIMESTAMPTZ,
    shown_at TIMESTAMPTZ DEFAULT NOW(),
    user_id BIGINT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_news_shown_at ON news_history(shown_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_category ON news_history(category);
CREATE INDEX IF NOT EXISTS idx_news_user ON news_history(user_id);
CREATE INDEX IF NOT EXISTS idx_news_link ON news_history(link);

-- Комментарии
COMMENT ON TABLE news_history IS 'История показанных новостей для отслеживания прочитанного';
COMMENT ON COLUMN news_history.title IS 'Заголовок новости';
COMMENT ON COLUMN news_history.link IS 'Уникальная ссылка на новость (защита от дублей)';
COMMENT ON COLUMN news_history.source IS 'Источник новости (название RSS)';
COMMENT ON COLUMN news_history.category IS 'Категория: telematics, tachography, innovations, logistics';
COMMENT ON COLUMN news_history.published_at IS 'Дата публикации в источнике';
COMMENT ON COLUMN news_history.shown_at IS 'Когда показали пользователю';
COMMENT ON COLUMN news_history.user_id IS 'ID пользователя (для мультипользовательского режима)';

-- ============================================================================
-- Примеры запросов
-- ============================================================================

-- Посмотреть последние показанные новости:
-- SELECT title, source, shown_at FROM news_history ORDER BY shown_at DESC LIMIT 10;

-- Посчитать количество новостей за неделю:
-- SELECT COUNT(*) FROM news_history WHERE shown_at > NOW() - INTERVAL '7 days';

-- Очистить старые новости (старше 30 дней):
-- DELETE FROM news_history WHERE shown_at < NOW() - INTERVAL '30 days';

-- Найти дубликаты по URL:
-- SELECT link, COUNT(*) FROM news_history GROUP BY link HAVING COUNT(*) > 1;
