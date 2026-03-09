#!/usr/bin/env python3
"""
Скрипт для исправления БД — добавляет BIGSERIAL для ID таблиц
Выполняет миграцию таблиц в Supabase

Использование:
    python scripts/fix_db.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
except ImportError:
    print("❌ Установите psycopg2: pip install psycopg2-binary")
    sys.exit(1)

from brains.config import SUPABASE_URL, SUPABASE_KEY

# Парсим URL для подключения
# Формат: https://xxx.supabase.co → xxx.supabase.co
db_host = SUPABASE_URL.replace('https://', '').replace('/rest/v1', '')
db_name = 'postgres'
db_user = 'postgres'
db_password = SUPABASE_KEY

print("=" * 60)
print("🔧 Исправление БД — BIGSERIAL для ID")
print("=" * 60)
print(f"\n📊 Подключение к: {db_host}")
print(f"👤 Пользователь: {db_user}")
print("")

# SQL миграция
MIGRATION_SQL = """
-- 1. Удаляем старые таблицы
DROP TABLE IF EXISTS task_history CASCADE;
DROP TABLE IF EXISTS task_comments CASCADE;
DROP TABLE IF EXISTS daily_goals CASCADE;
DROP TABLE IF EXISTS sprint_tasks CASCADE;
DROP TABLE IF EXISTS sprints CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS projects CASCADE;

-- 2. Создаём заново с BIGSERIAL
CREATE TABLE projects (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    priority TEXT DEFAULT 'medium',
    deadline TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    project_id BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium',
    due_date TIMESTAMPTZ,
    estimated_hours NUMERIC(5,2),
    actual_hours NUMERIC(5,2),
    parent_task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ
);

CREATE TABLE sprints (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    goal TEXT,
    status TEXT DEFAULT 'planning',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE daily_goals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    goals TEXT[] NOT NULL,
    completed BOOLEAN[] DEFAULT '{}',
    evening_review TEXT,
    mood TEXT,
    productivity_score INTEGER CHECK (productivity_score >= 1 AND productivity_score <= 10),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_user_date UNIQUE (user_id, date)
);

CREATE TABLE task_comments (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    comment TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE task_history (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sprint_tasks (
    sprint_id BIGINT REFERENCES sprints(id) ON DELETE CASCADE,
    task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (sprint_id, task_id)
);

-- 3. Индексы
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_project_id ON tasks(project_id);
CREATE INDEX idx_sprints_user_id ON sprints(user_id);
CREATE INDEX idx_daily_goals_user_date ON daily_goals(user_id, date);
"""

try:
    # Подключение к БД
    print("🔌 Подключение к Supabase...")
    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,
        port=5432,
        sslmode='require'
    )
    print("✅ Подключение установлено")
    
    # Создаём курсор
    cursor = conn.cursor()
    
    # Выполняем миграцию
    print("\n📝 Выполнение миграции...")
    print("⏳ Это может занять несколько секунд...")
    print("")
    
    cursor.execute(MIGRATION_SQL)
    conn.commit()
    
    print("✅ Миграция выполнена успешно!")
    print("")
    
    # Проверяем что таблицы созданы
    print("📊 Проверка таблиц...")
    cursor.execute("""
        SELECT table_name, 
               (SELECT COUNT(*) FROM information_schema.columns c 
                WHERE c.table_name = t.table_name) as columns
        FROM information_schema.tables t
        WHERE t.table_schema = 'public'
        AND t.table_type = 'BASE TABLE'
        AND t.table_name IN ('projects', 'tasks', 'sprints', 'daily_goals', 
                             'task_comments', 'task_history', 'sprint_tasks')
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    
    print("\n✅ Созданные таблицы:")
    for table_name, columns in tables:
        print(f"  • {table_name} ({columns} колонок)")
    
    print("")
    print("=" * 60)
    print("✅ БД успешно исправлена!")
    print("=" * 60)
    print("")
    print("🚀 Теперь запусти тесты:")
    print("   python scripts/test_productivity.py")
    print("")
    
    cursor.close()
    conn.close()
    
except psycopg2.Error as e:
    print(f"\n❌ Ошибка подключения к БД: {e}")
    print("\nПроверьте:")
    print("  1. SUPABASE_URL в .env")
    print("  2. SUPABASE_KEY в .env")
    print("  3. Подключение к интернету")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    sys.exit(1)
