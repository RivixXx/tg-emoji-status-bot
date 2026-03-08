"""
Karina AI: Projects Module
Управление проектами
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from brains.clients import supabase_client
from brains.supabase_retry import safe_supabase_insert, safe_supabase_select, safe_supabase_update

logger = logging.getLogger(__name__)


class ProjectStatus(Enum):
    """Статусы проекта"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectPriority(Enum):
    """Приоритеты проекта"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Project:
    """Модель проекта"""
    id: Optional[int] = None
    user_id: int = 0
    name: str = ""
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    priority: ProjectPriority = ProjectPriority.MEDIUM
    deadline: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Преобразует проект в словарь для Supabase"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Project":
        """Создаёт проект из словаря"""
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=ProjectStatus(data.get("status", "active")),
            priority=ProjectPriority(data.get("priority", "medium")),
            deadline=datetime.fromisoformat(data["deadline"].replace('+00:00', '+00:00')) if data.get("deadline") else None,
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"].replace('+00:00', '+00:00')) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace('+00:00', '+00:00')) if data.get("updated_at") else None,
        )

    def is_overdue(self) -> bool:
        """Проверяет, просрочен ли проект"""
        if not self.deadline or self.status == ProjectStatus.COMPLETED:
            return False
        return datetime.now(timezone.utc) > self.deadline

    def days_until_deadline(self) -> Optional[int]:
        """Возвращает количество дней до дедлайна"""
        if not self.deadline:
            return None
        delta = self.deadline - datetime.now(timezone.utc)
        return delta.days


# ============================================================================
# CRUD ОПЕРАЦИИ
# ============================================================================

async def create_project(
    user_id: int,
    name: str,
    description: str = "",
    priority: ProjectPriority = ProjectPriority.MEDIUM,
    deadline: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Project]:
    """
    Создаёт новый проект
    
    Args:
        user_id: ID пользователя
        name: Название проекта
        description: Описание
        priority: Приоритет
        deadline: Дедлайн
        metadata: Дополнительные данные
    
    Returns:
        Созданный проект или None
    """
    if not supabase_client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None

    project = Project(
        user_id=user_id,
        name=name,
        description=description,
        priority=priority,
        deadline=deadline,
        metadata=metadata or {}
    )

    result = await safe_supabase_insert(
        supabase_client,
        "projects",
        project.to_dict(),
        max_retries=3
    )

    if result and result.data:
        logger.info(f"✅ Проект создан: {name[:50]}...")
        return Project.from_dict(result.data[0])
    
    logger.error(f"❌ Не удалось создать проект: {name}")
    return None


async def get_project(project_id: int, user_id: int) -> Optional[Project]:
    """
    Получает проект по ID
    
    Args:
        project_id: ID проекта
        user_id: ID пользователя
    
    Returns:
        Проект или None
    """
    if not supabase_client:
        return None

    result = await safe_supabase_select(
        supabase_client,
        "projects",
        filters={"id": project_id, "user_id": user_id},
        max_retries=2
    )

    if result and len(result) > 0:
        return Project.from_dict(result[0])
    
    return None


async def get_user_projects(
    user_id: int,
    status: Optional[ProjectStatus] = None,
    limit: int = 50
) -> List[Project]:
    """
    Получает проекты пользователя
    
    Args:
        user_id: ID пользователя
        status: Фильтр по статусу
        limit: Максимальное количество
    
    Returns:
        Список проектов
    """
    if not supabase_client:
        return []

    filters = {"user_id": user_id}
    if status:
        filters["status"] = status.value

    result = await safe_supabase_select(
        supabase_client,
        "projects",
        filters=filters,
        limit=limit,
        max_retries=2
    )

    return [Project.from_dict(row) for row in result] if result else []


async def update_project(
    project_id: int,
    user_id: int,
    updates: Dict[str, Any]
) -> Optional[Project]:
    """
    Обновляет проект
    
    Args:
        project_id: ID проекта
        user_id: ID пользователя
        updates: Поля для обновления
    
    Returns:
        Обновлённый проект или None
    """
    if not supabase_client:
        return None

    # Преобразуем enum в строки
    if "status" in updates and isinstance(updates["status"], ProjectStatus):
        updates["status"] = updates["status"].value
    if "priority" in updates and isinstance(updates["priority"], ProjectPriority):
        updates["priority"] = updates["priority"].value

    result = await safe_supabase_update(
        supabase_client,
        "projects",
        updates,
        eq_column="id",
        eq_value=project_id,
        max_retries=3
    )

    if result and result.data:
        logger.info(f"✅ Проект обновлён: {project_id}")
        return Project.from_dict(result.data[0])
    
    logger.error(f"❌ Не удалось обновить проект: {project_id}")
    return None


async def archive_project(project_id: int, user_id: int) -> Optional[Project]:
    """
    Архивирует проект
    
    Args:
        project_id: ID проекта
        user_id: ID пользователя
    
    Returns:
        Архивированный проект или None
    """
    return await update_project(project_id, user_id, {"status": ProjectStatus.ARCHIVED})


async def complete_project(project_id: int, user_id: int) -> Optional[Project]:
    """
    Завершает проект
    
    Args:
        project_id: ID проекта
        user_id: ID пользователя
    
    Returns:
        Завершённый проект или None
    """
    return await update_project(project_id, user_id, {"status": ProjectStatus.COMPLETED})


async def delete_project(project_id: int, user_id: int) -> bool:
    """
    Удаляет проект
    
    Args:
        project_id: ID проекта
        user_id: ID пользователя
    
    Returns:
        True если успешно
    """
    if not supabase_client:
        return False

    from brains.supabase_retry import safe_supabase_delete
    
    result = await safe_supabase_delete(
        supabase_client,
        "projects",
        eq_column="id",
        eq_value=project_id,
        max_retries=2
    )

    if result:
        logger.info(f"🗑️ Проект удалён: {project_id}")
        return True
    
    return False


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

async def get_project_tasks(project_id: int, user_id: int) -> List[Dict]:
    """
    Получает задачи проекта
    
    Args:
        project_id: ID проекта
        user_id: ID пользователя
    
    Returns:
        Список задач
    """
    if not supabase_client:
        return []

    try:
        from brains import tasks as tasks_module
        
        all_tasks = await tasks_module.get_user_tasks(user_id, limit=200)
        project_tasks = [t for t in all_tasks if t.project_id == project_id]
        
        return [t.to_dict() for t in project_tasks]
    except Exception as e:
        logger.error(f"❌ Ошибка получения задач проекта: {e}")
        return []


async def get_project_stats(project_id: int, user_id: int) -> Dict:
    """
    Получает статистику проекта
    
    Args:
        project_id: ID проекта
        user_id: ID пользователя
    
    Returns:
        Словарь со статистикой
    """
    tasks = await get_project_tasks(project_id, user_id)
    
    if not tasks:
        return {
            "total_tasks": 0,
            "completed_tasks": 0,
            "in_progress_tasks": 0,
            "todo_tasks": 0,
            "completion_percent": 0
        }

    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == "done")
    in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
    todo = sum(1 for t in tasks if t.get("status") == "todo")

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "in_progress_tasks": in_progress,
        "todo_tasks": todo,
        "completion_percent": round(completed * 100 / total, 2) if total > 0 else 0
    }


async def get_active_projects(user_id: int) -> List[Project]:
    """
    Получает активные проекты
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Список активных проектов
    """
    return await get_user_projects(user_id, status=ProjectStatus.ACTIVE)


async def get_overdue_projects(user_id: int) -> List[Project]:
    """
    Получает просроченные проекты
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Список просроченных проектов
    """
    projects = await get_user_projects(user_id, limit=100)
    return [p for p in projects if p.is_overdue()]


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def format_project_for_display(project: Project, show_stats: bool = False) -> str:
    """
    Форматирует проект для отображения
    
    Args:
        project: Проект
        show_stats: Показывать статистику
    
    Returns:
        Форматированная строка
    """
    status_emoji = {
        ProjectStatus.ACTIVE: "🟢",
        ProjectStatus.PAUSED: "⏸️",
        ProjectStatus.COMPLETED: "✅",
        ProjectStatus.ARCHIVED: "🗄️"
    }

    priority_emoji = {
        ProjectPriority.LOW: "🟢",
        ProjectPriority.MEDIUM: "🟡",
        ProjectPriority.HIGH: "🟠",
        ProjectPriority.URGENT: "🔴"
    }

    lines = [
        f"{status_emoji.get(project.status, '🟢')} {priority_emoji.get(project.priority, '🟡')} **{project.name}**",
    ]

    if project.description:
        lines.append(f"📝 {project.description[:100]}...")

    if project.deadline:
        if project.is_overdue():
            days = abs(project.days_until_deadline())
            lines.append(f"🔴 Просрочено на {days} дн.")
        else:
            days = project.days_until_deadline()
            if days == 0:
                lines.append("⚠️ Дедлайн сегодня!")
            elif days == 1:
                lines.append("⏰ Дедлайн завтра")
            else:
                lines.append(f"📅 Дедлайн: {project.deadline.strftime('%d.%m.%Y')} (через {days} дн.)")

    if show_stats:
        # Статистика будет добавлена из отдельного вызова
        pass

    return "\n".join(lines)
