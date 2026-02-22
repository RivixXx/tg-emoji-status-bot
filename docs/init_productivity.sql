-- ============================================================================
-- Karina AI: Модуль продуктивности
-- ============================================================================
-- Дата: Февраль 2026
-- Описание: Отслеживание привычек, рабочего времени, переработок
-- ============================================================================

-- Таблица для отслеживания привычек
CREATE TABLE IF NOT EXISTS habits (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL DEFAULT 0,
    habit_name TEXT NOT NULL,
    completed BOOLEAN DEFAULT true,
    notes TEXT,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    tracked_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для учёта рабочего времени
CREATE TABLE IF NOT EXISTS work_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL DEFAULT 0,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    duration_hours NUMERIC(5,2),
    meetings_count INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для привычек
CREATE INDEX IF NOT EXISTS idx_habits_user ON habits(user_id);
CREATE INDEX IF NOT EXISTS idx_habits_date ON habits(date DESC);
CREATE INDEX IF NOT EXISTS idx_habits_user_date ON habits(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_habits_name ON habits(habit_name);

-- Индексы для рабочих сессий
CREATE INDEX IF NOT EXISTS idx_work_sessions_user ON work_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_work_sessions_date ON work_sessions(date DESC);
CREATE INDEX IF NOT EXISTS idx_work_sessions_user_date ON work_sessions(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_work_sessions_duration ON work_sessions(duration_hours);

-- Комментарии
COMMENT ON TABLE habits IS 'Отслеживание выполнения привычек пользователя';
COMMENT ON COLUMN habits.habit_name IS 'Название привычки (например: "Здоровый сон", "Обед")';
COMMENT ON COLUMN habits.completed IS 'Выполнена ли привычка';
COMMENT ON COLUMN habits.notes IS 'Заметки о выполнении';

COMMENT ON TABLE work_sessions IS 'Учёт рабочего времени и сессий';
COMMENT ON COLUMN work_sessions.start_time IS 'Начало рабочей сессии';
COMMENT ON COLUMN work_sessions.end_time IS 'Конец рабочей сессии';
COMMENT ON COLUMN work_sessions.duration_hours IS 'Длительность в часах';
COMMENT ON COLUMN work_sessions.meetings_count IS 'Количество встреч за сессию';
COMMENT ON COLUMN work_sessions.tasks_completed IS 'Выполненные задачи';

-- ============================================================================
-- Примеры запросов
-- ============================================================================

-- Посмотреть привычки за неделю:
-- SELECT habit_name, COUNT(*) as total, SUM(CASE WHEN completed THEN 1 ELSE 0 END) as completed
-- FROM habits WHERE date > NOW() - INTERVAL '7 days'
-- GROUP BY habit_name ORDER BY habit_name;

-- Посчитать среднее рабочее время:
-- SELECT AVG(duration_hours), DATE_TRUNC('week', date) as week
-- FROM work_sessions GROUP BY week ORDER BY week DESC;

-- Найти дни с переработками (>9 часов):
-- SELECT date, duration_hours FROM work_sessions 
-- WHERE duration_hours > 9 ORDER BY date DESC;

-- Посчитать работу по дням недели:
-- SELECT EXTRACT(DOW FROM date) as day_of_week, AVG(duration_hours)
-- FROM work_sessions GROUP BY day_of_week ORDER BY day_of_week;
