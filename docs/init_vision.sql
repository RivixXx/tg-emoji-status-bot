-- ============================================================================
-- Karina AI: Модуль компьютерного зрения (Vision)
-- ============================================================================
-- Дата: Февраль 2026
-- Описание: Хранение анализа изображений, OCR, распознанные документы
-- ============================================================================

-- Таблица для истории анализа изображений
CREATE TABLE IF NOT EXISTS vision_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL DEFAULT 0,
    image_hash TEXT NOT NULL,
    original_filename TEXT,
    file_path TEXT,
    prompt TEXT,
    analysis TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для vision_history
CREATE INDEX IF NOT EXISTS idx_vision_history_user ON vision_history(user_id);
CREATE INDEX IF NOT EXISTS idx_vision_history_hash ON vision_history(image_hash);
CREATE INDEX IF NOT EXISTS idx_vision_history_analyzed_at ON vision_history(analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_vision_history_analysis ON vision_history USING gin(to_tsvector('russian', analysis));

-- Комментарии
COMMENT ON TABLE vision_history IS 'История анализа изображений через Vision AI';
COMMENT ON COLUMN vision_history.image_hash IS 'MD5 хэш изображения для поиска дублей';
COMMENT ON COLUMN vision_history.original_filename IS 'Исходное имя файла';
COMMENT ON COLUMN vision_history.prompt IS 'Запрос пользователя к AI';
COMMENT ON COLUMN vision_history.analysis IS 'Текстовый анализ изображения от AI';
COMMENT ON COLUMN vision_history.metadata IS 'Дополнительные данные (тип анализа, теги и т.д.)';

-- ============================================================================
-- Примеры запросов
-- ============================================================================

-- Найти все анализы за неделю:
-- SELECT * FROM vision_history 
-- WHERE user_id = 123 AND analyzed_at > NOW() - INTERVAL '7 days'
-- ORDER BY analyzed_at DESC;

-- Поиск по содержимому (полнотекстовый):
-- SELECT * FROM vision_history 
-- WHERE user_id = 123 AND analysis @@ to_tsquery('russian', 'документ & паспорт')
-- ORDER BY analyzed_at DESC;

-- Посчитать количество анализов по типам:
-- SELECT metadata->>'analysis_type' as type, COUNT(*) 
-- FROM vision_history 
-- WHERE user_id = 123
-- GROUP BY type ORDER BY COUNT DESC;

-- Найти дубликаты изображений:
-- SELECT image_hash, COUNT(*) FROM vision_history 
-- GROUP BY image_hash HAVING COUNT(*) > 1;
