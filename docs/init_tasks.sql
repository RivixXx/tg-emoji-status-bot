-- ============================================================================
-- Karina AI: Tasks & Projects Module
-- Миграция для системы управления задачами и проектами
-- ============================================================================
-- Дата: Март 2026
-- Версия: 1.0
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. ПРОЕКТЫ
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    deadline TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}', -- Дополнительные данные (цвет, теги, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для проектов
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_priority ON projects(priority);
CREATE INDEX IF NOT EXISTS idx_projects_deadline ON projects(deadline);

-- ----------------------------------------------------------------------------
-- 2. ЗАДАЧИ
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'review', 'done', 'cancelled')),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    due_date TIMESTAMPTZ,
    estimated_hours NUMERIC(5,2),
    actual_hours NUMERIC(5,2),
    parent_task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE, -- Подзадачи
    tags TEXT[] DEFAULT '{}', -- Теги задачи
    metadata JSONB DEFAULT '{}', -- Дополнительные данные
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ
);

-- Индексы для задач
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_tags ON tasks USING GIN(tags);

-- ----------------------------------------------------------------------------
-- 3. СПРИНТЫ
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sprints (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    goal TEXT,
    status TEXT DEFAULT 'planning' CHECK (status IN ('planning', 'active', 'completed', 'archived')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для спринтов
CREATE INDEX IF NOT EXISTS idx_sprints_user_id ON sprints(user_id);
CREATE INDEX IF NOT EXISTS idx_sprints_status ON sprints(status);
CREATE INDEX IF NOT EXISTS idx_sprints_dates ON sprints(start_date, end_date);

-- ----------------------------------------------------------------------------
-- 4. СВЯЗЬ СПРИНТ-ЗАДАЧИ (многие-ко-многим)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sprint_tasks (
    sprint_id BIGINT REFERENCES sprints(id) ON DELETE CASCADE,
    task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (sprint_id, task_id)
);

-- Индексы для связи
CREATE INDEX IF NOT EXISTS idx_sprint_tasks_sprint ON sprint_tasks(sprint_id);
CREATE INDEX IF NOT EXISTS idx_sprint_tasks_task ON sprint_tasks(task_id);

-- ----------------------------------------------------------------------------
-- 5. КОММЕНТАРИИ К ЗАДАЧАМ
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_comments (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    comment TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для комментариев
CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_user ON task_comments(user_id);

-- ----------------------------------------------------------------------------
-- 6. ЕЖЕДНЕВНЫЕ ЦЕЛИ
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_goals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    goals TEXT[] NOT NULL, -- Массив целей (до 10)
    completed BOOLEAN[] DEFAULT '{}', -- Статус выполнения каждой цели
    evening_review TEXT, -- Вечерний обзор
    mood TEXT, -- Настроение дня
    productivity_score INTEGER CHECK (productivity_score >= 1 AND productivity_score <= 10),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Уникальность на пользователя + дату
    CONSTRAINT unique_user_date UNIQUE (user_id, date)
);

-- Индексы для ежедневных целей
CREATE INDEX IF NOT EXISTS idx_daily_goals_user ON daily_goals(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_goals_date ON daily_goals(date);
CREATE INDEX IF NOT EXISTS idx_daily_goals_user_date ON daily_goals(user_id, date);

-- ----------------------------------------------------------------------------
-- 7. ИСТОРИЯ ИЗМЕНЕНИЙ (для аудита)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_history (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    action TEXT NOT NULL, -- created, updated, status_changed, deleted
    old_value JSONB,
    new_value JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для истории
CREATE INDEX IF NOT EXISTS idx_task_history_task ON task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_task_history_user ON task_history(user_id);
CREATE INDEX IF NOT EXISTS idx_task_history_action ON task_history(action);

-- ----------------------------------------------------------------------------
-- 8. ФУНКЦИИ И ТРИГГЕРЫ
-- ----------------------------------------------------------------------------

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для updated_at
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sprints_updated_at
    BEFORE UPDATE ON sprints
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_comments_updated_at
    BEFORE UPDATE ON task_comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_goals_updated_at
    BEFORE UPDATE ON daily_goals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 9. ФУНКЦИЯ: Автозавершение задачи при 100% подзадач
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION check_subtasks_completion()
RETURNS TRIGGER AS $$
BEGIN
    -- Если все подзадачи выполнены, завершаем родительскую задачу
    IF NEW.status = 'done' THEN
        UPDATE tasks
        SET status = 'done',
            completed_at = NOW()
        WHERE id = NEW.parent_task_id
        AND NOT EXISTS (
            SELECT 1 FROM tasks
            WHERE parent_task_id = NEW.parent_task_id
            AND status != 'done'
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автозавершения
CREATE TRIGGER auto_complete_parent_task
    AFTER UPDATE ON tasks
    FOR EACH ROW
    WHEN (NEW.status = 'done')
    EXECUTE FUNCTION check_subtasks_completion();

-- ----------------------------------------------------------------------------
-- 10. ФУНКЦИЯ: Логирование изменений задач
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION log_task_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO task_history (task_id, user_id, action, new_value)
        VALUES (NEW.id, NEW.user_id, 'created', to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO task_history (task_id, user_id, action, old_value, new_value)
        VALUES (NEW.id, NEW.user_id, 'updated', to_jsonb(OLD), to_jsonb(NEW));
        
        -- Отдельно логируем смену статуса
        IF OLD.status != NEW.status THEN
            INSERT INTO task_history (task_id, user_id, action, old_value, new_value)
            VALUES (NEW.id, NEW.user_id, 'status_changed', 
                    jsonb_build_object('status', OLD.status),
                    jsonb_build_object('status', NEW.status));
        END IF;
        
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO task_history (task_id, user_id, action, old_value)
        VALUES (OLD.id, OLD.user_id, 'deleted', to_jsonb(OLD));
        RETURN OLD;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Триггер для логирования
CREATE TRIGGER task_change_log
    AFTER INSERT OR UPDATE OR DELETE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION log_task_changes();

-- ----------------------------------------------------------------------------
-- 11. ПРЕДСТАВЛЕНИЯ (VIEWS) для удобных запросов
-- ----------------------------------------------------------------------------

-- Представление: Активные задачи с проектами
CREATE OR REPLACE VIEW active_tasks_with_projects AS
SELECT 
    t.id,
    t.user_id,
    t.title,
    t.description,
    t.status,
    t.priority,
    t.due_date,
    t.estimated_hours,
    t.actual_hours,
    t.created_at,
    p.id as project_id,
    p.name as project_name,
    p.status as project_status
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
WHERE t.status NOT IN ('done', 'cancelled')
ORDER BY t.priority DESC, t.due_date ASC;

-- Представление: Прогресс спринта
CREATE OR REPLACE VIEW sprint_progress AS
SELECT 
    s.id as sprint_id,
    s.name as sprint_name,
    s.start_date,
    s.end_date,
    s.status as sprint_status,
    COUNT(st.task_id) as total_tasks,
    COUNT(CASE WHEN t.status = 'done' THEN 1 END) as completed_tasks,
    ROUND(
        COUNT(CASE WHEN t.status = 'done' THEN 1 END)::NUMERIC * 100 / 
        NULLIF(COUNT(st.task_id), 0),
        2
    ) as completion_percent
FROM sprints s
LEFT JOIN sprint_tasks st ON s.id = st.sprint_id
LEFT JOIN tasks t ON st.task_id = t.id
GROUP BY s.id, s.name, s.start_date, s.end_date, s.status;

-- Представление: Задачи на сегодня
CREATE OR REPLACE VIEW today_tasks AS
SELECT 
    id,
    user_id,
    title,
    description,
    status,
    priority,
    due_date,
    project_id,
    tags
FROM tasks
WHERE DATE(due_date) = CURRENT_DATE
OR (status IN ('todo', 'in_progress') AND due_date IS NULL)
ORDER BY priority DESC, due_date ASC;

-- Представление: Просроченные задачи
CREATE OR REPLACE VIEW overdue_tasks AS
SELECT 
    id,
    user_id,
    title,
    description,
    status,
    priority,
    due_date,
    project_id,
    CURRENT_DATE - DATE(due_date) as days_overdue
FROM tasks
WHERE due_date < NOW()
AND status NOT IN ('done', 'cancelled')
ORDER BY due_date ASC;

-- ----------------------------------------------------------------------------
-- 12. RPC ФУНКЦИИ для удобного доступа из Python
-- ----------------------------------------------------------------------------

-- Получить задачи пользователя с фильтрами
CREATE OR REPLACE FUNCTION get_user_tasks(
    p_user_id BIGINT,
    p_status TEXT DEFAULT NULL,
    p_project_id BIGINT DEFAULT NULL,
    p_limit INTEGER DEFAULT 50
)
RETURNS TABLE (
    id BIGINT,
    title TEXT,
    description TEXT,
    status TEXT,
    priority TEXT,
    due_date TIMESTAMPTZ,
    project_id BIGINT,
    project_name TEXT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        t.title,
        t.description,
        t.status,
        t.priority,
        t.due_date,
        t.project_id,
        p.name as project_name,
        t.created_at
    FROM tasks t
    LEFT JOIN projects p ON t.project_id = p.id
    WHERE t.user_id = p_user_id
    AND (p_status IS NULL OR t.status = p_status)
    AND (p_project_id IS NULL OR t.project_id = p_project_id)
    ORDER BY t.priority DESC, t.due_date ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Получить статистику пользователя
CREATE OR REPLACE FUNCTION get_user_productivity_stats(
    p_user_id BIGINT,
    p_days INTEGER DEFAULT 7
)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_tasks', COUNT(*),
        'completed_tasks', COUNT(*) FILTER (WHERE status = 'done'),
        'in_progress_tasks', COUNT(*) FILTER (WHERE status = 'in_progress'),
        'overdue_tasks', COUNT(*) FILTER (WHERE due_date < NOW() AND status NOT IN ('done', 'cancelled')),
        'completion_rate', ROUND(
            COUNT(*) FILTER (WHERE status = 'done')::NUMERIC * 100 / NULLIF(COUNT(*), 0),
            2
        ),
        'total_projects', (SELECT COUNT(*) FROM projects WHERE user_id = p_user_id AND status = 'active'),
        'active_sprints', (SELECT COUNT(*) FROM sprints WHERE user_id = p_user_id AND status = 'active')
    ) INTO result
    FROM tasks
    WHERE user_id = p_user_id
    AND created_at >= NOW() - INTERVAL '1 day' * p_days;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 13. ПРИМЕРЫ ДАННЫХ (для тестирования)
-- ----------------------------------------------------------------------------

-- Пример проекта
-- INSERT INTO projects (user_id, name, description, status, priority, deadline)
-- VALUES (582792393, 'Telegram Bot', 'Разработка Karina AI бота', 'active', 'high', '2026-04-01');

-- Пример задачи
-- INSERT INTO tasks (user_id, project_id, title, description, status, priority, due_date, estimated_hours)
-- VALUES (582792393, 1, 'Система задач', 'Реализовать CRUD для задач', 'in_progress', 'high', '2026-03-15', 4.0);

-- ----------------------------------------------------------------------------
-- 14. РАЗРЕШЕНИЯ (если используется RLS)
-- ----------------------------------------------------------------------------
-- ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE sprints ENABLE ROW LEVEL SECURITY;
-- 
-- CREATE POLICY user_projects ON projects
--     FOR ALL USING (user_id = current_setting('app.current_user_id')::BIGINT);
-- 
-- CREATE POLICY user_tasks ON tasks
--     FOR ALL USING (user_id = current_setting('app.current_user_id')::BIGINT);

-- ----------------------------------------------------------------------------
-- КОНЕЦ МИГРАЦИИ
-- ----------------------------------------------------------------------------
