"""
Karina AI: Sprints Module
Управление спринтами и ежедневными целями
"""
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from brains.clients import supabase_client
from brains.supabase_retry import safe_supabase_insert, safe_supabase_select, safe_supabase_update

logger = logging.getLogger(__name__)


class SprintStatus(Enum):
    """Статусы спринта"""
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Sprint:
    """Модель спринта"""
    id: Optional[int] = None
    user_id: int = 0
    name: str = ""
    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=lambda: date.today() + timedelta(days=14))
    goal: str = ""
    status: SprintStatus = SprintStatus.PLANNING
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Преобразует спринт в словарь для Supabase"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "goal": self.goal,
            "status": self.status.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Sprint":
        """Создаёт спринт из словаря"""
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id", 0),
            name=data.get("name", ""),
            start_date=date.fromisoformat(data["start_date"]) if data.get("start_date") else date.today(),
            end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else date.today() + timedelta(days=14),
            goal=data.get("goal", ""),
            status=SprintStatus(data.get("status", "planning")),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"].replace('+00:00', '+00:00')) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace('+00:00', '+00:00')) if data.get("updated_at") else None,
        )

    def days_remaining(self) -> int:
        """Возвращает количество дней до конца спринта"""
        delta = self.end_date - date.today()
        return max(0, delta.days)

    def days_elapsed(self) -> int:
        """Возвращает количество дней с начала спринта"""
        delta = date.today() - self.start_date
        return max(0, delta.days)

    def is_active(self) -> bool:
        """Проверяет, активен ли спринт"""
        return self.status == SprintStatus.ACTIVE and self.start_date <= date.today() <= self.end_date


@dataclass
class DailyGoals:
    """Модель ежедневных целей"""
    id: Optional[int] = None
    user_id: int = 0
    date: date = field(default_factory=date.today)
    goals: List[str] = field(default_factory=list)
    completed: List[bool] = field(default_factory=list)
    evening_review: str = ""
    mood: str = ""
    productivity_score: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Преобразует в словарь для Supabase"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat(),
            "goals": self.goals,
            "completed": self.completed,
            "evening_review": self.evening_review,
            "mood": self.mood,
            "productivity_score": self.productivity_score,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DailyGoals":
        """Создаёт из словаря"""
        return cls(
            id=data.get("id"),
            user_id=data.get("user_id", 0),
            date=date.fromisoformat(data["date"]) if data.get("date") else date.today(),
            goals=data.get("goals", []),
            completed=data.get("completed", []),
            evening_review=data.get("evening_review", ""),
            mood=data.get("mood", ""),
            productivity_score=data.get("productivity_score", 5),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"].replace('+00:00', '+00:00')) if data.get("created_at") else None,
        )

    def completion_percent(self) -> float:
        """Процент выполнения целей"""
        if not self.goals:
            return 0.0
        completed_count = sum(1 for c in self.completed if c)
        return round(completed_count * 100 / len(self.goals), 2)


# ============================================================================
# СПРИНТЫ - CRUD
# ============================================================================

async def create_sprint(
    user_id: int,
    name: str,
    start_date: date,
    end_date: date,
    goal: str = "",
    status: SprintStatus = SprintStatus.PLANNING
) -> Optional[Sprint]:
    """
    Создаёт новый спринт
    
    Args:
        user_id: ID пользователя
        name: Название спринта
        start_date: Дата начала
        end_date: Дата окончания
        goal: Цель спринта
        status: Статус
    
    Returns:
        Созданный спринт или None
    """
    if not supabase_client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None

    sprint = Sprint(
        user_id=user_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        goal=goal,
        status=status
    )

    result = await safe_supabase_insert(
        supabase_client,
        "sprints",
        sprint.to_dict(),
        max_retries=3
    )

    if result and result.data:
        logger.info(f"✅ Спринт создан: {name}")
        return Sprint.from_dict(result.data[0])
    
    return None


async def get_sprint(sprint_id: int, user_id: int) -> Optional[Sprint]:
    """Получает спринт по ID"""
    if not supabase_client:
        return None

    result = await safe_supabase_select(
        supabase_client,
        "sprints",
        filters={"id": sprint_id, "user_id": user_id},
        max_retries=2
    )

    if result and len(result) > 0:
        return Sprint.from_dict(result[0])
    
    return None


async def get_user_sprints(
    user_id: int,
    status: Optional[SprintStatus] = None,
    limit: int = 20
) -> List[Sprint]:
    """Получает спринты пользователя"""
    if not supabase_client:
        return []

    filters = {"user_id": user_id}
    if status:
        filters["status"] = status.value

    result = await safe_supabase_select(
        supabase_client,
        "sprints",
        filters=filters,
        limit=limit,
        max_retries=2
    )

    return [Sprint.from_dict(row) for row in result] if result else []


async def update_sprint(
    sprint_id: int,
    user_id: int,
    updates: Dict[str, Any]
) -> Optional[Sprint]:
    """Обновляет спринт"""
    if not supabase_client:
        return None

    # Преобразуем enum и date
    if "status" in updates and isinstance(updates["status"], SprintStatus):
        updates["status"] = updates["status"].value
    if "start_date" in updates and isinstance(updates["start_date"], date):
        updates["start_date"] = updates["start_date"].isoformat()
    if "end_date" in updates and isinstance(updates["end_date"], date):
        updates["end_date"] = updates["end_date"].isoformat()

    result = await safe_supabase_update(
        supabase_client,
        "sprints",
        updates,
        eq_column="id",
        eq_value=sprint_id,
        max_retries=3
    )

    if result and result.data:
        logger.info(f"✅ Спринт обновлён: {sprint_id}")
        return Sprint.from_dict(result.data[0])
    
    return None


async def start_sprint(sprint_id: int, user_id: int) -> Optional[Sprint]:
    """Начинает спринт"""
    return await update_sprint(
        sprint_id, user_id,
        {"status": SprintStatus.ACTIVE}
    )


async def complete_sprint(sprint_id: int, user_id: int) -> Optional[Sprint]:
    """Завершает спринт"""
    return await update_sprint(
        sprint_id, user_id,
        {"status": SprintStatus.COMPLETED}
    )


async def delete_sprint(sprint_id: int, user_id: int) -> bool:
    """Удаляет спринт"""
    if not supabase_client:
        return False

    from brains.supabase_retry import safe_supabase_delete
    
    result = await safe_supabase_delete(
        supabase_client,
        "sprints",
        eq_column="id",
        eq_value=sprint_id,
        max_retries=2
    )

    if result:
        logger.info(f"🗑️ Спринт удалён: {sprint_id}")
        return True
    return False


# ============================================================================
# СВЯЗЬ СПРИНТ-ЗАДАЧИ
# ============================================================================

async def add_task_to_sprint(sprint_id: int, task_id: int) -> bool:
    """Добавляет задачу в спринт"""
    if not supabase_client:
        return False

    data = {"sprint_id": sprint_id, "task_id": task_id}

    try:
        response = supabase_client.table("sprint_tasks").insert(data).execute()
        if response.data:
            logger.info(f"✅ Задача {task_id} добавлена в спринт {sprint_id}")
            return True
    except Exception as e:
        if "duplicate key" not in str(e).lower():
            logger.error(f"❌ Ошибка добавления задачи в спринт: {e}")
    
    return False


async def remove_task_from_sprint(sprint_id: int, task_id: int) -> bool:
    """Удаляет задачу из спринта"""
    if not supabase_client:
        return False

    try:
        response = supabase_client.table("sprint_tasks")\
            .delete()\
            .eq("sprint_id", sprint_id)\
            .eq("task_id", task_id)\
            .execute()
        
        if response.data is not None:
            logger.info(f"🗑️ Задача {task_id} удалена из спринта {sprint_id}")
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка удаления задачи из спринта: {e}")
    
    return False


async def get_sprint_tasks(sprint_id: int) -> List[Dict]:
    """Получает задачи спринта"""
    if not supabase_client:
        return []

    try:
        response = supabase_client.table("sprint_tasks")\
            .select("task_id, tasks(*)")\
            .eq("sprint_id", sprint_id)\
            .execute()

        if response.data:
            return [row.get("tasks", {}) for row in response.data if row.get("tasks")]
    except Exception as e:
        logger.error(f"❌ Ошибка получения задач спринта: {e}")
    
    return []


# ============================================================================
# ЕЖЕДНЕВНЫЕ ЦЕЛИ
# ============================================================================

async def get_daily_goals(user_id: int, goal_date: date = None) -> Optional[DailyGoals]:
    """Получает цели на день"""
    if not supabase_client:
        return None

    goal_date = goal_date or date.today()

    result = await safe_supabase_select(
        supabase_client,
        "daily_goals",
        filters={"user_id": user_id, "date": goal_date.isoformat()},
        max_retries=2
    )

    if result and len(result) > 0:
        return DailyGoals.from_dict(result[0])
    
    return None


async def create_daily_goals(
    user_id: int,
    goals: List[str],
    goal_date: date = None
) -> Optional[DailyGoals]:
    """
    Создаёт ежедневные цели
    
    Args:
        user_id: ID пользователя
        goals: Список целей (до 10)
        goal_date: Дата (по умолчанию сегодня)
    
    Returns:
        DailyGoals или None
    """
    if not supabase_client:
        return None

    goal_date = goal_date or date.today()
    
    # Ограничиваем количество целей
    goals = goals[:10]
    completed = [False] * len(goals)

    daily = DailyGoals(
        user_id=user_id,
        date=goal_date,
        goals=goals,
        completed=completed
    )

    # Используем upsert для обновления если уже существует
    try:
        response = supabase_client.table("daily_goals").upsert(
            daily.to_dict(),
            on_conflict="user_id,date"
        ).execute()

        if response.data:
            logger.info(f"✅ Цели на {goal_date} созданы/обновлены")
            return DailyGoals.from_dict(response.data[0])
    except Exception as e:
        logger.error(f"❌ Ошибка создания ежедневных целей: {e}")
    
    return None


async def update_daily_goal_completion(
    user_id: int,
    goal_index: int,
    completed: bool,
    goal_date: date = None
) -> Optional[DailyGoals]:
    """Обновляет выполнение цели"""
    if not supabase_client:
        return None

    goal_date = goal_date or date.today()
    daily = await get_daily_goals(user_id, goal_date)
    
    if not daily:
        return None

    if goal_index < 0 or goal_index >= len(daily.completed):
        logger.error(f"❌ Неверный индекс цели: {goal_index}")
        return None

    daily.completed[goal_index] = completed

    result = await safe_supabase_update(
        supabase_client,
        "daily_goals",
        {"completed": daily.completed},
        eq_column="id",
        eq_value=daily.id,
        max_retries=2
    )

    if result and result.data:
        logger.info(f"✅ Цель {goal_index + 1} отмечена как {'выполненная' if completed else 'невыполненная'}")
        return DailyGoals.from_dict(result.data[0])
    
    return None


async def set_evening_review(
    user_id: int,
    review: str,
    mood: str = "",
    productivity_score: int = 5,
    goal_date: date = None
) -> Optional[DailyGoals]:
    """Устанавливает вечерний обзор дня"""
    if not supabase_client:
        return None

    goal_date = goal_date or date.today()
    daily = await get_daily_goals(user_id, goal_date)
    
    if not daily:
        # Создаём новую запись если нет
        daily = DailyGoals(
            user_id=user_id,
            date=goal_date,
            goals=[],
            completed=[]
        )

    updates = {
        "evening_review": review,
        "mood": mood,
        "productivity_score": min(10, max(1, productivity_score))
    }

    result = await safe_supabase_update(
        supabase_client,
        "daily_goals",
        updates,
        eq_column="user_id",
        eq_value=user_id,
        max_retries=2
    )

    # Если не нашли по user_id, создаём новую
    if not result or not result.data:
        try:
            daily.evening_review = review
            daily.mood = mood
            daily.productivity_score = min(10, max(1, productivity_score))
            
            response = supabase_client.table("daily_goals").insert(daily.to_dict()).execute()
            if response.data:
                return DailyGoals.from_dict(response.data[0])
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения вечернего обзора: {e}")
        return None

    return DailyGoals.from_dict(result.data[0])


# ============================================================================
# СТАТИСТИКА
# ============================================================================

async def get_sprint_stats(sprint_id: int) -> Dict:
    """Получает статистику спринта"""
    tasks = await get_sprint_tasks(sprint_id)
    
    if not tasks:
        return {
            "total_tasks": 0,
            "completed_tasks": 0,
            "in_progress_tasks": 0,
            "completion_percent": 0
        }

    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == "done")
    in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "in_progress_tasks": in_progress,
        "completion_percent": round(completed * 100 / total, 2) if total > 0 else 0
    }


async def get_active_sprint(user_id: int) -> Optional[Sprint]:
    """Получает активный спринт пользователя"""
    sprints = await get_user_sprints(user_id, status=SprintStatus.ACTIVE, limit=1)
    return sprints[0] if sprints else None


async def get_weekly_completion(user_id: int, days: int = 7) -> float:
    """Получает процент выполнения целей за неделю"""
    if not supabase_client:
        return 0.0

    try:
        cutoff = date.today() - timedelta(days=days)
        
        response = supabase_client.table("daily_goals")\
            .select("goals, completed")\
            .eq("user_id", user_id)\
            .gte("date", cutoff.isoformat())\
            .execute()

        if response.data:
            total_goals = 0
            total_completed = 0
            
            for row in response.data:
                goals = row.get("goals", [])
                completed = row.get("completed", [])
                total_goals += len(goals)
                total_completed += sum(1 for c in completed if c)
            
            if total_goals > 0:
                return round(total_completed * 100 / total_goals, 2)
    except Exception as e:
        logger.error(f"❌ Ошибка получения недельной статистики: {e}")
    
    return 0.0


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def format_sprint_for_display(sprint: Sprint, show_stats: bool = False) -> str:
    """
    Форматирует спринт для отображения
    
    Args:
        sprint: Спринт
        show_stats: Показывать статистику
    
    Returns:
        Форматированная строка
    """
    status_emoji = {
        SprintStatus.PLANNING: "📋",
        SprintStatus.ACTIVE: "🏃",
        SprintStatus.COMPLETED: "✅",
        SprintStatus.ARCHIVED: "🗄️"
    }

    emoji = status_emoji.get(sprint.status, "📋")
    days_left = sprint.days_remaining()
    days_elapsed = sprint.days_elapsed()

    lines = [
        f"{emoji} **{sprint.name}**",
        f"📅 {sprint.start_date} — {sprint.end_date}",
    ]

    if sprint.status == SprintStatus.ACTIVE:
        if days_left == 0:
            lines.append("🔴 Заканчивается сегодня!")
        elif days_left == 1:
            lines.append("⏰ Заканчивается завтра!")
        else:
            lines.append(f"⏳ Осталось дней: {days_left}")
    elif sprint.status == SprintStatus.PLANNING:
        lines.append(f"📅 До начала: {max(0, (sprint.start_date - date.today()).days)} дн.")

    if sprint.goal:
        lines.append(f"🎯 {sprint.goal[:100]}")

    if show_stats:
        lines.append(f"📊 Прошло дней: {days_elapsed} из {(sprint.end_date - sprint.start_date).days}")

    return "\n".join(lines)
