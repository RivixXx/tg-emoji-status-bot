-- ============================================================================
-- Karina AI: TTS (Text-to-Speech) настройки
-- ============================================================================
-- Дата: Февраль 2026
-- Описание: Хранение настроек TTS для пользователей
-- ============================================================================

-- Таблица для настроек TTS
CREATE TABLE IF NOT EXISTS tts_settings (
    user_id BIGINT PRIMARY KEY,
    enabled BOOLEAN DEFAULT false,
    voice TEXT DEFAULT 'ksenia',
    volume NUMERIC(3,2) DEFAULT 1.0,
    speed NUMERIC(3,2) DEFAULT 1.0,
    auto_voice_for_voice BOOLEAN DEFAULT true,  -- Отвечать голосом на голосовые
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_tts_settings_user ON tts_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_tts_settings_enabled ON tts_settings(enabled) WHERE enabled = true;

-- Комментарии
COMMENT ON TABLE tts_settings IS 'Настройки TTS (голосовые ответы) для пользователей';
COMMENT ON COLUMN tts_settings.user_id IS 'ID пользователя Telegram';
COMMENT ON COLUMN tts_settings.enabled IS 'Включён ли TTS';
COMMENT ON COLUMN tts_settings.voice IS 'Выбранный голос (ksenia, elen, irina, natasha)';
COMMENT ON COLUMN tts_settings.volume IS 'Громкость (0.0-2.0)';
COMMENT ON COLUMN tts_settings.speed IS 'Скорость речи (0.5-2.0)';
COMMENT ON COLUMN tts_settings.auto_voice_for_voice IS 'Отвечать голосом на голосовые сообщения';

-- ============================================================================
-- Триггер для обновления updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_tts_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tts_settings_updated_at
    BEFORE UPDATE ON tts_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_tts_settings_updated_at();

-- ============================================================================
-- Примеры запросов
-- ============================================================================

-- Включить TTS пользователю:
-- INSERT INTO tts_settings (user_id, enabled, voice)
-- VALUES (123456789, true, 'ksenia')
-- ON CONFLICT (user_id) DO UPDATE SET enabled = true, updated_at = NOW();

-- Выключить TTS:
-- UPDATE tts_settings SET enabled = false WHERE user_id = 123456789;

-- Сменить голос:
-- UPDATE tts_settings SET voice = 'irina' WHERE user_id = 123456789;

-- Получить настройки:
-- SELECT * FROM tts_settings WHERE user_id = 123456789;

-- Посчитать сколько пользователей с TTS:
-- SELECT COUNT(*) FROM tts_settings WHERE enabled = true;

-- Популярные голоса:
-- SELECT voice, COUNT(*) as count
-- FROM tts_settings
-- WHERE enabled = true
-- GROUP BY voice ORDER BY count DESC;
