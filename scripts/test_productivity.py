#!/usr/bin/env python3
"""
Karina AI Productivity Assistant — Автоматический тест функционала

Запускает полную проверку всех компонентов:
- Задачи (CRUD)
- Проекты (CRUD)
- Спринты (CRUD)
- Ежедневные цели
- AI Function Calling (симуляция)
- Триггеры (проверка состояния)

Использование:
    python scripts/test_productivity.py

Требования:
    - Заполненный .env файл
    - Доступ к Supabase
    - Установленные зависимости
"""
import os
import sys
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_productivity.log', encoding='utf-8', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Импорты модулей
from brains.tasks import (
    create_task, get_task, get_user_tasks, update_task, complete_task, delete_task,
    get_overdue_tasks, get_productivity_stats, TaskStatus, TaskPriority
)
from brains.projects import (
    create_project, get_project, get_user_projects, archive_project,
    complete_project, delete_project, ProjectStatus, ProjectPriority
)
from brains.sprints import (
    create_sprint, get_sprint, get_user_sprints, start_sprint, complete_sprint,
    add_task_to_sprint, get_sprint_tasks, get_daily_goals, create_daily_goals,
    set_evening_review, SprintStatus
)
from brains.config import MY_ID


# ============================================================================
# ТЕСТИРОВАНИЕ ЗАДАЧ
# ============================================================================

async def test_tasks(user_id: int) -> bool:
    """Тестирует CRUD задач"""
    logger.info("=" * 60)
    logger.info("📝 ТЕСТ: Задачи (CRUD)")
    logger.info("=" * 60)
    
    try:
        # 1. Создание задачи
        logger.info("\n1️⃣ Создание задачи...")
        task = await create_task(
            user_id=user_id,
            title="Тестовая задача 1",
            description="Описание тестовой задачи",
            priority=TaskPriority.HIGH,
            due_date=datetime.now(timezone.utc) + timedelta(days=1)
        )
        
        if not task:
            logger.error("❌ Не удалось создать задачу")
            return False
        
        logger.info(f"✅ Задача создана: ID={task.id}, Title={task.title}")
        
        # 2. Получение задачи
        logger.info("\n2️⃣ Получение задачи по ID...")
        retrieved_task = await get_task(task.id, user_id)
        
        if not retrieved_task:
            logger.error("❌ Не удалось получить задачу")
            return False
        
        logger.info(f"✅ Задача получена: {retrieved_task.title}")
        
        # 3. Обновление задачи
        logger.info("\n3️⃣ Обновление задачи...")
        updated_task = await update_task(
            task_id=task.id,
            user_id=user_id,
            updates={"title": "Обновлённая тестовая задача"}
        )
        
        if not updated_task:
            logger.error("❌ Не удалось обновить задачу")
            return False
        
        logger.info(f"✅ Задача обновлена: {updated_task.title}")
        
        # 4. Получение списка задач
        logger.info("\n4️⃣ Получение списка задач...")
        tasks = await get_user_tasks(user_id, limit=10)
        
        logger.info(f"✅ Получено задач: {len(tasks)}")
        
        # 5. Начало работы над задачей
        logger.info("\n5️⃣ Начало работы над задачей...")
        started_task = await update_task(
            task_id=task.id,
            user_id=user_id,
            updates={"status": TaskStatus.IN_PROGRESS}
        )
        
        if not started_task:
            logger.error("❌ Не удалось начать задачу")
            return False
        
        logger.info(f"✅ Задача в работе: {started_task.status}")
        
        # 6. Завершение задачи
        logger.info("\n6️⃣ Завершение задачи...")
        completed_task = await complete_task(task.id, user_id)
        
        if not completed_task:
            logger.error("❌ Не удалось завершить задачу")
            return False
        
        logger.info(f"✅ Задача завершена: {completed_task.status}")
        
        # 7. Удаление задачи
        logger.info("\n7️⃣ Удаление задачи...")
        deleted = await delete_task(task.id, user_id)
        
        if not deleted:
            logger.error("❌ Не удалось удалить задачу")
            return False
        
        logger.info("✅ Задача удалена")
        
        # 8. Статистика продуктивности
        logger.info("\n8️⃣ Проверка статистики продуктивности...")
        stats = await get_productivity_stats(user_id, days=7)
        
        logger.info(f"✅ Статистика: {stats}")
        
        logger.info("\n✅ ТЕСТ ЗАДАЧ: УСПЕШНО")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Ошибка тестирования задач: {e}")
        return False


# ============================================================================
# ТЕСТИРОВАНИЕ ПРОЕКТОВ
# ============================================================================

async def test_projects(user_id: int) -> bool:
    """Тестирует CRUD проектов"""
    logger.info("=" * 60)
    logger.info("📁 ТЕСТ: Проекты (CRUD)")
    logger.info("=" * 60)
    
    try:
        # 1. Создание проекта
        logger.info("\n1️⃣ Создание проекта...")
        project = await create_project(
            user_id=user_id,
            name="Тестовый проект",
            description="Описание тестового проекта",
            priority=ProjectPriority.HIGH,
            deadline=datetime.now(timezone.utc) + timedelta(days=30)
        )
        
        if not project:
            logger.error("❌ Не удалось создать проект")
            return False
        
        logger.info(f"✅ Проект создан: ID={project.id}, Name={project.name}")
        
        # 2. Получение проекта
        logger.info("\n2️⃣ Получение проекта по ID...")
        retrieved_project = await get_project(project.id, user_id)
        
        if not retrieved_project:
            logger.error("❌ Не удалось получить проект")
            return False
        
        logger.info(f"✅ Проект получен: {retrieved_project.name}")
        
        # 3. Получение списка проектов
        logger.info("\n3️⃣ Получение списка проектов...")
        projects = await get_user_projects(user_id, limit=10)
        
        logger.info(f"✅ Получено проектов: {len(projects)}")
        
        # 4. Завершение проекта
        logger.info("\n4️⃣ Завершение проекта...")
        completed_project = await complete_project(project.id, user_id)
        
        if not completed_project:
            logger.error("❌ Не удалось завершить проект")
            return False
        
        logger.info(f"✅ Проект завершён: {completed_project.status}")
        
        # 5. Удаление проекта
        logger.info("\n5️⃣ Удаление проекта...")
        deleted = await delete_project(project.id, user_id)
        
        if not deleted:
            logger.error("❌ Не удалось удалить проект")
            return False
        
        logger.info("✅ Проект удалён")
        
        logger.info("\n✅ ТЕСТ ПРОЕКТОВ: УСПЕШНО")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Ошибка тестирования проектов: {e}")
        return False


# ============================================================================
# ТЕСТИРОВАНИЕ СПРИНТОВ
# ============================================================================

async def test_sprints(user_id: int) -> bool:
    """Тестирует CRUD спринтов"""
    logger.info("=" * 60)
    logger.info("🏃 ТЕСТ: Спринты (CRUD)")
    logger.info("=" * 60)
    
    try:
        # 1. Создание спринта
        logger.info("\n1️⃣ Создание спринта...")
        start_date = date.today()
        end_date = start_date + timedelta(days=14)
        
        sprint = await create_sprint(
            user_id=user_id,
            name="Тестовый спринт",
            start_date=start_date,
            end_date=end_date,
            goal="Тестовая цель спринта"
        )
        
        if not sprint:
            logger.error("❌ Не удалось создать спринт")
            return False
        
        logger.info(f"✅ Спринт создан: ID={sprint.id}, Name={sprint.name}")
        
        # 2. Получение спринта
        logger.info("\n2️⃣ Получение спринта...")
        retrieved_sprint = await get_sprint(sprint.id, user_id)
        
        if not retrieved_sprint:
            logger.error("❌ Не удалось получить спринт")
            return False
        
        logger.info(f"✅ Спринт получен: {retrieved_sprint.name}")
        
        # 3. Начало спринта
        logger.info("\n3️⃣ Начало спринта...")
        started_sprint = await start_sprint(sprint.id, user_id)
        
        if not started_sprint:
            logger.error("❌ Не удалось начать спринт")
            return False
        
        logger.info(f"✅ Спринт активен: {started_sprint.status}")
        
        # 4. Создание задачи для спринта
        logger.info("\n4️⃣ Создание задачи для спринта...")
        task = await create_task(
            user_id=user_id,
            title="Задача для спринта",
            priority=TaskPriority.MEDIUM
        )
        
        if not task:
            logger.error("❌ Не удалось создать задачу для спринта")
            return False
        
        # 5. Добавление задачи в спринт
        logger.info("\n5️⃣ Добавление задачи в спринт...")
        added = await add_task_to_sprint(sprint.id, task.id)
        
        logger.info(f"✅ Задача добавлена в спринт: {added}")
        
        # 6. Получение задач спринта
        logger.info("\n6️⃣ Получение задач спринта...")
        sprint_tasks = await get_sprint_tasks(sprint.id)
        
        logger.info(f"✅ Задач в спринте: {len(sprint_tasks)}")
        
        # 7. Завершение спринта
        logger.info("\n7️⃣ Завершение спринта...")
        completed_sprint = await complete_sprint(sprint.id, user_id)
        
        if not completed_sprint:
            logger.error("❌ Не удалось завершить спринт")
            return False
        
        logger.info(f"✅ Спринт завершён: {completed_sprint.status}")
        
        # Очистка: удаляем задачу
        await delete_task(task.id, user_id)
        await delete_project(sprint.id, user_id)  # Спринты удаляются через projects
        
        logger.info("\n✅ ТЕСТ СПРИНТОВ: УСПЕШНО")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Ошибка тестирования спринтов: {e}")
        return False


# ============================================================================
# ТЕСТИРОВАНИЕ ЕЖЕДНЕВНЫХ ЦЕЛЕЙ
# ============================================================================

async def test_daily_goals(user_id: int) -> bool:
    """Тестирует ежедневные цели"""
    logger.info("=" * 60)
    logger.info("🎯 ТЕСТ: Ежедневные цели")
    logger.info("=" * 60)
    
    try:
        today = date.today()
        
        # 1. Создание целей на день
        logger.info("\n1️⃣ Создание целей на день...")
        goals = await create_daily_goals(
            user_id=user_id,
            goals=["Цель 1", "Цель 2", "Цель 3"],
            goal_date=today
        )
        
        if not goals:
            logger.error("❌ Не удалось создать цели")
            return False
        
        logger.info(f"✅ Цели созданы: {len(goals.goals)} шт.")
        
        # 2. Получение целей
        logger.info("\n2️⃣ Получение целей...")
        retrieved_goals = await get_daily_goals(user_id, today)
        
        if not retrieved_goals:
            logger.error("❌ Не удалось получить цели")
            return False
        
        logger.info(f"✅ Цели получены: {retrieved_goals.goals}")
        
        # 3. Отметка выполнения
        logger.info("\n3️⃣ Отметка выполнения цели...")
        from brains.sprints import update_daily_goal_completion
        
        updated = await update_daily_goal_completion(
            user_id=user_id,
            goal_index=0,
            completed=True,
            goal_date=today
        )
        
        if not updated:
            logger.error("❌ Не удалось отметить цель")
            return False
        
        logger.info(f"✅ Цель отмечена: {updated.completed}")
        
        # 4. Вечерний обзор
        logger.info("\n4️⃣ Вечерний обзор...")
        review = await set_evening_review(
            user_id=user_id,
            review="Хороший день, много сделал",
            mood="good",
            productivity_score=8,
            goal_date=today
        )
        
        if not review:
            logger.error("❌ Не удалось сохранить обзор")
            return False
        
        logger.info(f"✅ Вечерний обзор сохранён: {review.evening_review}")
        
        logger.info("\n✅ ТЕСТ ЕЖЕДНЕВНЫХ ЦЕЛЕЙ: УСПЕШНО")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Ошибка тестирования ежедневных целей: {e}")
        return False


# ============================================================================
# СИМУЛЯЦИЯ AI FUNCTION CALLING
# ============================================================================

async def test_ai_function_calling(user_id: int) -> bool:
    """Симулирует AI Function Calling"""
    logger.info("=" * 60)
    logger.info("🤖 ТЕСТ: AI Function Calling (симуляция)")
    logger.info("=" * 60)
    
    try:
        from brains.ai_tools import tool_executor
        
        # 1. Создание задачи через AI
        logger.info("\n1️⃣ AI: Создание задачи...")
        result = await tool_executor.execute_tool(
            tool_name="create_task",
            args={
                "title": "AI тестовая задача",
                "description": "Создана через AI",
                "priority": "high",
                "due_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            },
            user_id=user_id
        )
        
        logger.info(f"✅ AI результат: {result[:100]}...")
        
        # 2. Получение задач через AI
        logger.info("\n2️⃣ AI: Получение списка задач...")
        result = await tool_executor.execute_tool(
            tool_name="get_my_tasks",
            args={"status": "todo", "limit": 5},
            user_id=user_id
        )
        
        logger.info(f"✅ AI результат: {result[:100]}...")
        
        # 3. Статистика через AI
        logger.info("\n3️⃣ AI: Статистика продуктивности...")
        result = await tool_executor.execute_tool(
            tool_name="get_productivity_stats",
            args={"days": 7},
            user_id=user_id
        )
        
        logger.info(f"✅ AI результат: {result[:100]}...")
        
        # 4. Создание проекта через AI
        logger.info("\n4️⃣ AI: Создание проекта...")
        result = await tool_executor.execute_tool(
            tool_name="create_project",
            args={
                "name": "AI тестовый проект",
                "description": "Создан через AI"
            },
            user_id=user_id
        )
        
        logger.info(f"✅ AI результат: {result[:100]}...")
        
        logger.info("\n✅ ТЕСТ AI FUNCTION CALLING: УСПЕШНО")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Ошибка тестирования AI: {e}")
        return False


# ============================================================================
# ПРОВЕРКА ТРИГГЕРОВ
# ============================================================================

async def test_triggers_state() -> bool:
    """Проверяет состояние триггеров"""
    logger.info("=" * 60)
    logger.info("🎯 ТЕСТ: Триггеры (проверка состояния)")
    logger.info("=" * 60)
    
    try:
        from brains.triggers import trigger_state
        
        logger.info("\n📊 Текущее состояние триггеров:")
        logger.info(f"  - Утреннее планирование: {trigger_state.last_morning_planning}")
        logger.info(f"  - Вечерний обзор: {trigger_state.last_evening_review}")
        logger.info(f"  - Проверка дедлайнов: {trigger_state.last_deadline_check}")
        logger.info(f"  - Застрявшие задачи: {trigger_state.last_stuck_check}")
        logger.info(f"  - Перерыв: {trigger_state.last_break_reminder}")
        logger.info(f"  - Обед: {trigger_state.last_lunch_reminder}")
        
        logger.info("\n✅ ТЕСТ ТРИГГЕРОВ: УСПЕШНО (состояние проверено)")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Ошибка проверки триггеров: {e}")
        return False


# ============================================================================
# ГЛАВНЫЙ ТЕСТ
# ============================================================================

async def run_all_tests():
    """Запускает все тесты"""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 KARINA AI PRODUCTIVITY ASSISTANT — АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ")
    logger.info("=" * 80)
    logger.info(f"\n📅 Дата: {datetime.now()}")
    logger.info(f"👤 User ID: {MY_ID}")
    logger.info(f"💾 Supabase: {'✅' if os.environ.get('SUPABASE_URL') else '❌'}")
    logger.info("")
    
    results = {
        "Задачи": False,
        "Проекты": False,
        "Спринты": False,
        "Ежедневные цели": False,
        "AI Function Calling": False,
        "Триггеры": False
    }
    
    # Тестирование
    results["Задачи"] = await test_tasks(MY_ID)
    results["Проекты"] = await test_projects(MY_ID)
    results["Спринты"] = await test_sprints(MY_ID)
    results["Ежедневные цели"] = await test_daily_goals(MY_ID)
    results["AI Function Calling"] = await test_ai_function_calling(MY_ID)
    results["Триггеры"] = await test_triggers_state()
    
    # Итоги
    logger.info("\n" + "=" * 80)
    logger.info("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    logger.info("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} — {test_name}")
    
    logger.info("")
    logger.info(f"📈 Пройдено: {passed}/{total} тестов")
    logger.info(f"📉 Провалено: {total - passed}/{total} тестов")
    
    if passed == total:
        logger.info("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к работе!")
    else:
        logger.info("\n⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ! Проверьте логи выше.")
    
    logger.info("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n👋 Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
