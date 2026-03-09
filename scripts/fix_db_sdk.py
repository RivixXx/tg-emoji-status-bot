#!/usr/bin/env python3
"""
Скрипт для исправления БД через Supabase SDK
Выполняет миграцию таблиц в Supabase

Использование:
    python scripts/fix_db_sdk.py
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brains.clients import supabase_client

print("=" * 60)
print("🔧 Исправление БД — BIGSERIAL для ID")
print("=" * 60)

if not supabase_client:
    print("\n❌ Supabase клиент не инициализирован!")
    print("\nПроверьте:")
    print("  1. SUPABASE_URL в .env")
    print("  2. SUPABASE_KEY в .env")
    sys.exit(1)

print(f"\n✅ Supabase клиент инициализирован")
print(f"📊 URL: {supabase_client.supabase_url}")
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
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_sprints_user_id ON sprints(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_goals_user_date ON daily_goals(user_id, date);
"""

async def fix_database():
    try:
        print("📝 Выполнение миграции...")
        print("⏳ Это может занять несколько секунд...")
        print("")
        
        # Выполняем SQL через Supabase SDK
        result = supabase_client.postgrest.session.execute(MIGRATION_SQL)
        
        print("✅ Миграция выполнена успешно!")
        print("")
        
        # Проверяем что таблицы созданы
        print("📊 Проверка таблиц...")
        
        tables = ['projects', 'tasks', 'sprints', 'daily_goals', 
                  'task_comments', 'task_history', 'sprint_tasks']
        
        for table in tables:
            try:
                response = supabase_client.table(table).select("*").limit(1).execute()
                print(f"  ✅ {table}")
            except Exception as e:
                print(f"  ❌ {table}: {e}")
        
        print("")
        print("=" * 60)
        print("✅ БД успешно исправлена!")
        print("=" * 60)
        print("")
        print("🚀 Теперь запусти тесты:")
        print("   python scripts/test_productivity.py")
        print("")
        
    except Exception as e:
        print(f"\n❌ Ошибка выполнения миграции: {e}")
        print("\nПопробуйте выполнить SQL вручную через Supabase Dashboard:")
        print("  1. Откройте https://supabase.com/dashboard")
        print("  2. Перейдите в SQL Editor")
        print("  3. Скопируйте и выполните SQL из scripts/fix_db_migration.sql")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(fix_database())
    except KeyboardInterrupt:
        print("\n\n👋 Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
