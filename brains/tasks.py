"""
Karina AI: Tasks Module
CRUD операции для управления задачами
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from brains.clients import supabase_client
from brains.supabase_retry import safe_supabase_insert, safe_supabase_select, safe_supabase_update

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Статусы задачи"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Приоритеты задачи"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    """Модель задачи"""
    id: Optional[int] = None
    user_id: int = 0
    project_id: Optional[int] = None
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    parent_task_id: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Преобразует задачу в словарь для Supabase"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
            "parent_task_id": self.parent_task_id,
            "tags": self.tags,
            "metadata": self.metadata,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        """Создаёт задачу из словаря"""
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id", 0),
            project_id=data.get("project_id"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "todo")),
            priority=TaskPriority(data.get("priority", "medium")),
            due_date=datetime.fromisoformat(data["due_date"].replace('+00:00', '+00:00')) if data.get("due_date") else None,
            estimated_hours=data.get("estimated_hours"),
            actual_hours=data.get("actual_hours"),
            parent_task_id=data.get("parent_task_id"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"].replace('+00:00', '+00:00')) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace('+00:00', '+00:00')) if data.get("updated_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"].replace('+00:00', '+00:00')) if data.get("completed_at") else None,
            started_at=datetime.fromisoformat(data["started_at"].replace('+00:00', '+00:00')) if data.get("started_at") else None,
        )

    def is_overdue(self) -> bool:
        """Проверяет, просрочена ли задача"""
        if not self.due_date or self.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
            return False
        return datetime.now(timezone.utc) > self.due_date

    def days_until_due(self) -> Optional[int]:
        """Возвращает количество дней до дедлайна"""
        if not self.due_date:
            return None
        delta = self.due_date - datetime.now(timezone.utc)
        return delta.days


# ============================================================================
# CRUD ОПЕРАЦИИ
# ============================================================================

async def create_task(
    user_id: int,
    title: str,
    description: str = "",
    project_id: Optional[int] = None,
    priority: TaskPriority = TaskPriority.MEDIUM,
    due_date: Optional[datetime] = None,
    estimated_hours: Optional[float] = None,
    parent_task_id: Optional[int] = None,
    tags: Optional[List[str]] = None
) -> Optional[Task]:
    """
    Создаёт новую задачу
    
    Args:
        user_id: ID пользователя
        title: Заголовок задачи
        description: Описание
        project_id: ID проекта (опционально)
        priority: Приоритет
        due_date: Дедлайн
        estimated_hours: Оценка времени в часах
        parent_task_id: ID родительской задачи (для подзадач)
        tags: Теги
    
    Returns:
        Созданную задачу или None
    """
    if not supabase_client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None

    task = Task(
        user_id=user_id,
        title=title,
        description=description,
        project_id=project_id,
        priority=priority,
        due_date=due_date,
        estimated_hours=estimated_hours,
        parent_task_id=parent_task_id,
        tags=tags or []
    )

    result = await safe_supabase_insert(
        supabase_client,
        "tasks",
        task.to_dict(),
        max_retries=3
    )

    if result and result.data:
        logger.info(f"✅ Задача создана: {title[:50]}...")
        return Task.from_dict(result.data[0])
    
    logger.error(f"❌ Не удалось создать задачу: {title}")
    return None


async def get_task(task_id: int, user_id: int) -> Optional[Task]:
    """
    Получает задачу по ID
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя (для проверки прав)
    
    Returns:
        Задачу или None
    """
    if not supabase_client:
        return None

    result = await safe_supabase_select(
        supabase_client,
        "tasks",
        filters={"id": task_id, "user_id": user_id},
        max_retries=2
    )

    if result and len(result) > 0:
        return Task.from_dict(result[0])
    
    return None


async def get_user_tasks(
    user_id: int,
    status: Optional[TaskStatus] = None,
    project_id: Optional[int] = None,
    limit: int = 50,
    include_completed: bool = False
) -> List[Task]:
    """
    Получает задачи пользователя с фильтрами
    
    Args:
        user_id: ID пользователя
        status: Фильтр по статусу
        project_id: Фильтр по проекту
        limit: Максимальное количество задач
        include_completed: Включать выполненные задачи
    
    Returns:
        Список задач
    """
    if not supabase_client:
        return []

    filters = {"user_id": user_id}
    
    if status:
        filters["status"] = status.value
    elif not include_completed:
        # По умолчанию скрываем выполненные и отменённые
        pass
    
    # Используем RPC функцию для эффективного запроса
    try:
        response = supabase_client.rpc(
            "get_user_tasks",
            {
                "p_user_id": user_id,
                "p_status": status.value if status else None,
                "p_project_id": project_id,
                "p_limit": limit
            }
        ).execute()

        if response.data:
            return [Task.from_dict(row) for row in response.data]
    except Exception as e:
        logger.error(f"❌ Ошибка получения задач через RPC: {e}")
    
    # Fallback: прямой запрос к таблице
    result = await safe_supabase_select(
        supabase_client,
        "tasks",
        filters=filters,
        limit=limit,
        max_retries=2
    )

    return [Task.from_dict(row) for row in result] if result else []


async def update_task(
    task_id: int,
    user_id: int,
    updates: Dict[str, Any]
) -> Optional[Task]:
    """
    Обновляет задачу
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя
        updates: Словарь с полями для обновления
    
    Returns:
        Обновлённую задачу или None
    """
    if not supabase_client:
        return None

    # Преобразуем enum в строки
    if "status" in updates and isinstance(updates["status"], TaskStatus):
        updates["status"] = updates["status"].value
    if "priority" in updates and isinstance(updates["priority"], TaskPriority):
        updates["priority"] = updates["priority"].value

    # Авто-установка completed_at
    if "status" in updates and updates["status"] == "done":
        updates["completed_at"] = datetime.now(timezone.utc).isoformat()
    elif "status" in updates and updates["status"] == "in_progress":
        updates["started_at"] = datetime.now(timezone.utc).isoformat()

    result = await safe_supabase_update(
        supabase_client,
        "tasks",
        updates,
        eq_column="id",
        eq_value=task_id,
        max_retries=3
    )

    if result and result.data:
        logger.info(f"✅ Задача обновлена: {task_id}")
        return Task.from_dict(result.data[0])
    
    logger.error(f"❌ Не удалось обновить задачу: {task_id}")
    return None


async def complete_task(task_id: int, user_id: int) -> Optional[Task]:
    """
    Завершает задачу
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя
    
    Returns:
        Завершённую задачу или None
    """
    return await update_task(task_id, user_id, {"status": TaskStatus.DONE})


async def delete_task(task_id: int, user_id: int) -> bool:
    """
    Удаляет задачу
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя
    
    Returns:
        True если успешно
    """
    if not supabase_client:
        return False

    from brains.supabase_retry import safe_supabase_delete
    
    result = await safe_supabase_delete(
        supabase_client,
        "tasks",
        eq_column="id",
        eq_value=task_id,
        max_retries=2
    )

    if result:
        logger.info(f"🗑️ Задача удалена: {task_id}")
        return True
    
    return False


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

async def get_overdue_tasks(user_id: int, days: int = 30) -> List[Task]:
    """
    Получает просроченные задачи
    
    Args:
        user_id: ID пользователя
        days: Период для поиска
    
    Returns:
        Список просроченных задач
    """
    if not supabase_client:
        return []

    try:
        response = supabase_client.rpc(
            "get_user_tasks",
            {
                "p_user_id": user_id,
                "p_status": None,
                "p_project_id": None,
                "p_limit": 100
            }
        ).execute()

        if response.data:
            tasks = [Task.from_dict(row) for row in response.data]
            overdue = [t for t in tasks if t.is_overdue()]
            return overdue
    except Exception as e:
        logger.error(f"❌ Ошибка получения просроченных задач: {e}")
    
    return []


async def get_tasks_by_due_date(
    user_id: int,
    days: int = 7
) -> List[Task]:
    """
    Получает задачи с дедлайном в ближайшие N дней
    
    Args:
        user_id: ID пользователя
        days: Количество дней
    
    Returns:
        Список задач
    """
    tasks = await get_user_tasks(user_id, limit=100)
    
    cutoff = datetime.now(timezone.utc) + timedelta(days=days)
    return [
        t for t in tasks 
        if t.due_date and t.due_date <= cutoff 
        and t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)
    ]


async def get_subtasks(parent_task_id: int, user_id: int) -> List[Task]:
    """
    Получает подзадачи
    
    Args:
        parent_task_id: ID родительской задачи
        user_id: ID пользователя
    
    Returns:
        Список подзадач
    """
    return await get_user_tasks(
        user_id,
        project_id=None,
        limit=100
    )


async def add_task_comment(
    task_id: int,
    user_id: int,
    comment: str
) -> bool:
    """
    Добавляет комментарий к задаче
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя
        comment: Текст комментария
    
    Returns:
        True если успешно
    """
    if not supabase_client:
        return False

    data = {
        "task_id": task_id,
        "user_id": user_id,
        "comment": comment
    }

    result = await safe_supabase_insert(
        supabase_client,
        "task_comments",
        data,
        max_retries=2
    )

    if result and result.data:
        logger.info(f"💬 Комментарий добавлен к задаче {task_id}")
        return True
    
    return False


async def get_task_comments(task_id: int) -> List[Dict]:
    """
    Получает комментарии задачи
    
    Args:
        task_id: ID задачи
    
    Returns:
        Список комментариев
    """
    if not supabase_client:
        return []

    result = await safe_supabase_select(
        supabase_client,
        "task_comments",
        filters={"task_id": task_id},
        max_retries=2
    )

    return result if result else []


async def get_productivity_stats(user_id: int, days: int = 7) -> Dict:
    """
    Получает статистику продуктивности
    
    Args:
        user_id: ID пользователя
        days: Период в днях
    
    Returns:
        Словарь со статистикой
    """
    if not supabase_client:
        return {}

    try:
        # Используем RPC функцию
        response = supabase_client.rpc(
            "get_user_productivity_stats",
            {
                "p_user_id": user_id,
                "p_days": days
            }
        ).execute()

        if response.data:
            return response.data
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")

    # Fallback: ручной подсчёт
    tasks = await get_user_tasks(user_id, limit=200)
    
    completed = sum(1 for t in tasks if t.status == TaskStatus.DONE)
    in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
    overdue = sum(1 for t in tasks if t.is_overdue())
    total = len(tasks)

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "in_progress_tasks": in_progress,
        "overdue_tasks": overdue,
        "completion_rate": round(completed * 100 / total, 2) if total > 0 else 0
    }


async def start_work_on_task(task_id: int, user_id: int) -> Optional[Task]:
    """
    Начинает работу над задачей (статус = in_progress)
    
    Args:
        task_id: ID задачи
        user_id: ID пользователя
    
    Returns:
        Обновлённую задачу
    """
    task = await get_task(task_id, user_id)
    if not task:
        return None

    if task.status == TaskStatus.TODO:
        return await update_task(task_id, user_id, {"status": TaskStatus.IN_PROGRESS})
    
    return task


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def format_task_for_display(task: Task, show_description: bool = False) -> str:
    """
    Форматирует задачу для отображения
    
    Args:
        task: Задача
        show_description: Показывать описание
    
    Returns:
        Форматированная строка
    """
    status_emoji = {
        TaskStatus.TODO: "⏳",
        TaskStatus.IN_PROGRESS: "🔄",
        TaskStatus.REVIEW: "👀",
        TaskStatus.DONE: "✅",
        TaskStatus.CANCELLED: "❌"
    }

    priority_emoji = {
        TaskPriority.LOW: "🟢",
        TaskPriority.MEDIUM: "🟡",
        TaskPriority.HIGH: "🟠",
        TaskPriority.URGENT: "🔴"
    }

    lines = [
        f"{status_emoji.get(task.status, '⏳')} {priority_emoji.get(task.priority, '🟡')} **{task.title}**",
    ]

    if task.due_date:
        if task.is_overdue():
            days = abs(task.days_until_due())
            lines.append(f"🔴 Просрочено на {days} дн.")
        else:
            days = task.days_until_due()
            if days == 0:
                lines.append("⚠️ Дедлайн сегодня!")
            elif days == 1:
                lines.append("⏰ Дедлайн завтра")
            else:
                lines.append(f"📅 Дедлайн: {task.due_date.strftime('%d.%m.%Y')} (через {days} дн.)")

    if task.estimated_hours:
        lines.append(f"⏱ Оценка: {task.estimated_hours}ч")

    if task.tags:
        lines.append(f"🏷 Теги: {', '.join(task.tags)}")

    if show_description and task.description:
        lines.append(f"\n📝 {task.description}")

    return "\n".join(lines)
