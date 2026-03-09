"""
AI Tool Executor для Karina AI
Выполнение инструментов (function calling) отдельно от основного запроса
"""
import logging
from datetime import datetime
from typing import Any, Dict
import asyncio

logger = logging.getLogger(__name__)


class AIToolExecutor:
    """Исполнитель AI инструментов"""
    
    def __init__(self):
        # Кэш для импортов
        self._imports_cache = {}
    
    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: int = 0
    ) -> str:
        """
        Выполняет инструмент и возвращает результат
        
        Args:
            tool_name: Название инструмента
            args: Аргументы инструмента
            user_id: ID пользователя для фильтрации
        
        Returns:
            Результат выполнения в виде строки
        """
        logger.info(f"🛠 AI вызывает инструмент: {tool_name}")
        
        try:
            if tool_name == "create_calendar_event":
                return await self._create_calendar_event(args)
            
            elif tool_name == "get_upcoming_calendar_events":
                return await self._get_calendar_events(args)
            
            elif tool_name == "get_weather_info":
                return await self._get_weather()
            
            elif tool_name == "check_calendar_conflicts":
                return await self._check_conflicts()
            
            elif tool_name == "get_health_stats":
                return await self._get_health_stats(args)
            
            elif tool_name == "save_to_memory":
                return await self._save_memory(args, user_id)
            
            elif tool_name == "check_employee_birthdays":
                return await self._check_birthdays()
            
            elif tool_name == "get_upcoming_employee_birthdays":
                return await self._get_upcoming_birthdays(args)
            
            elif tool_name == "search_my_memories":
                return await self._search_memories(args, user_id)
            
            elif tool_name == "get_my_health_stats":
                return await self._get_detailed_health_stats(args, user_id)
            
            elif tool_name == "list_my_active_reminders":
                return await self._get_active_reminders()

            # Задачи и проекты
            elif tool_name == "create_task":
                return await self._create_task(args, user_id)

            elif tool_name == "get_my_tasks":
                return await self._get_tasks(args, user_id)

            elif tool_name == "complete_task":
                return await self._complete_task(args, user_id)

            elif tool_name == "create_project":
                return await self._create_project(args, user_id)

            elif tool_name == "get_sprint_info":
                return await self._get_sprint_info(user_id)

            elif tool_name == "get_productivity_stats":
                return await self._get_productivity_stats(args, user_id)

            else:
                return f"❌ Неизвестный инструмент: {tool_name}"
                
        except asyncio.TimeoutError:
            logger.error(f"⌛️ Таймаут выполнения инструмента: {tool_name}")
            return f"⌛️ Таймаут выполнения инструмента {tool_name}"
        except Exception as e:
            logger.exception(f"❌ Ошибка выполнения {tool_name}: {e}")
            return f"❌ Ошибка выполнения {tool_name}: {str(e)}"
    
    async def _create_calendar_event(self, args: Dict) -> str:
        """Создаёт событие в календаре"""
        from brains.calendar import create_event
        
        start_dt = datetime.fromisoformat(args["start_time"].replace('Z', ''))
        summary = args["summary"]
        duration = args.get("duration", 30)
        
        success = await asyncio.wait_for(
            create_event(summary, start_dt, duration),
            timeout=15.0
        )
        
        if success:
            return (
                f"✅ Сделала! Записала в календарь: {summary} "
                f"на {start_dt.strftime('%d.%m в %H:%M')}."
            )
        return "❌ Ошибка при создании события."
    
    async def _get_calendar_events(self, args: Dict) -> str:
        """Получает события календаря"""
        from brains.calendar import get_upcoming_events
        
        count = args.get("count", 5)
        events_list = await asyncio.wait_for(
            get_upcoming_events(max_results=count),
            timeout=10.0
        )
        return f"Список ближайших планов:\n{events_list}"
    
    async def _get_weather(self) -> str:
        """Получает погоду"""
        from brains.weather import get_weather
        
        weather_data = await asyncio.wait_for(get_weather(), timeout=5.0)
        return f"Погода: {weather_data}"
    
    async def _check_conflicts(self) -> str:
        """Проверяет конфликты календаря"""
        from brains.calendar import get_conflict_report
        
        report = await asyncio.wait_for(get_conflict_report(), timeout=10.0)
        return f"Отчет по конфликтам:\n{report}"
    
    async def _get_health_stats(self, args: Dict) -> str:
        """Получает статистику здоровья"""
        from brains.health import get_health_report_text
        
        days = args.get("days", 7)
        report = await asyncio.wait_for(
            get_health_report_text(days),
            timeout=10.0
        )
        return f"Статистика здоровья:\n{report}"
    
    async def _save_memory(self, args: Dict, user_id: int) -> str:
        """Сохраняет в память"""
        from brains.memory import save_memory
        
        fact = args["text"]
        success = await asyncio.wait_for(
            save_memory(fact, metadata={"source": "ai_chat", "user_id": user_id}),
            timeout=10.0
        )
        
        if success:
            return f"✅ Я всё запомнила! Теперь я буду знать, что: {fact}"
        return "❌ Ошибка при сохранении в память."
    
    async def _check_birthdays(self) -> str:
        """Проверяет дни рождения сегодня"""
        from brains.employees import get_todays_birthdays
        
        celebrants = await asyncio.wait_for(get_todays_birthdays(), timeout=10.0)
        
        if not celebrants:
            return "Сегодня дней рождения нет. 😊"
        
        names = ", ".join([emp['full_name'] for emp in celebrants])
        return f"Да! Сегодня день рождения празднуют: {names}. 🥳"
    
    async def _get_upcoming_birthdays(self, args: Dict) -> str:
        """Получает предстоящие дни рождения"""
        from brains.mcp_tools import mcp_get_upcoming_birthdays
        
        days_period = args.get("days", 7)
        upcoming = await asyncio.wait_for(
            mcp_get_upcoming_birthdays(days_period),
            timeout=10.0
        )
        
        if not upcoming:
            return f"В ближайшие {days_period} дней дней рождения нет. 😊"
        
        lines = []
        for emp in upcoming:
            bd_date = emp.get('birthday', '')[5:]  # MM-DD
            days_left = emp.get('days_until', 0)
            lines.append(f"• {emp['full_name']} — {bd_date} (через {days_left} дн.)")
        
        return "🎂 Ближайшие дни рождения:\n" + "\n".join(lines)
    
    async def _search_memories(self, args: Dict, user_id: int) -> str:
        """Ищет в памяти"""
        from brains.mcp_tools import mcp_search_memories
        
        query = args["query"]
        limit = args.get("limit", 5)
        
        memories = await asyncio.wait_for(
            mcp_search_memories(query, limit=limit, user_id=user_id),
            timeout=10.0
        )
        
        if memories:
            return f"📚 Я вспомнила:\n{memories}"
        return "К сожалению, я не нашла ничего похожего в памяти. 🤔"
    
    async def _get_detailed_health_stats(self, args: Dict, user_id: int) -> str:
        """Получает детальную статистику здоровья"""
        from brains.mcp_tools import mcp_get_health_stats
        
        days = args.get("days", 7)
        stats = await asyncio.wait_for(
            mcp_get_health_stats(user_id=user_id, days=days),
            timeout=10.0
        )
        
        compliance = stats.get("compliance_rate", 0)
        return (
            f"📊 Статистика здоровья за {stats.get('period_days', 7)} дней:\n"
            f"✅ Подтверждено: {stats.get('confirmed', 0)}\n"
            f"❌ Пропущено: {stats.get('missed', 0)}\n"
            f"📈 Успешность: {compliance}%"
        )
    
    async def _get_active_reminders(self) -> str:
        """Получает активные напоминания"""
        from brains.mcp_tools import mcp_get_active_reminders

        reminders = await asyncio.wait_for(mcp_get_active_reminders(), timeout=10.0)

        if not reminders:
            return "📋 У тебя сейчас нет активных напоминаний. Отлично! 😊"

        lines = []
        for r in reminders:
            time_str = r.get("scheduled_time", "")[:16].replace("T", " ")
            lines.append(f"• {r.get('message', 'Напоминание')} ({time_str})")

        return "🔔 Активные напоминания:\n" + "\n".join(lines)

    # ========== ЗАДАЧИ И ПРОЕКТЫ ==========

    async def _create_task(self, args: Dict, user_id: int) -> str:
        """Создаёт задачу"""
        from brains.tasks import create_task, TaskPriority
        from datetime import datetime

        title = args.get("title", "")
        description = args.get("description", "")
        due_date_str = args.get("due_date")
        priority_str = args.get("priority", "medium")

        if not title:
            return "❌ Не указано название задачи"

        # Парсим дедлайн
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            except:
                pass

        # Парсим приоритет
        priority_map = {
            "low": TaskPriority.LOW,
            "medium": TaskPriority.MEDIUM,
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT
        }
        priority = priority_map.get(priority_str, TaskPriority.MEDIUM)

        task = await create_task(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date
        )

        if task:
            response = f"✅ **Задача создана!**\n\n"
            response += f"📝 {task.title}\n"
            if task.due_date:
                response += f"📅 Дедлайн: {task.due_date.strftime('%d.%m.%Y %H:%M')}\n"
            response += f"🔴 Приоритет: {task.priority.value}"
            return response
        
        return "❌ Не удалось создать задачу"

    async def _get_tasks(self, args: Dict, user_id: int) -> str:
        """Получает задачи"""
        from brains.tasks import get_user_tasks, TaskStatus, format_task_for_display

        status_str = args.get("status", "todo")
        limit = args.get("limit", 10)

        status_map = {
            "todo": TaskStatus.TODO,
            "in_progress": TaskStatus.IN_PROGRESS,
            "done": TaskStatus.DONE,
            "all": None
        }
        status = status_map.get(status_str, TaskStatus.TODO)

        tasks = await get_user_tasks(
            user_id=user_id,
            status=status,
            limit=limit,
            include_completed=(status_str == "all")
        )

        if not tasks:
            return f"📋 Задач не найдено (статус: {status_str})"

        response = f"📋 **Задачи** ({len(tasks)}):\n\n"
        for task in tasks[:limit]:
            response += f"• {task.title}\n"
            if task.due_date:
                if task.is_overdue():
                    response += f"  🔴 Просрочено\n"
                else:
                    response += f"  📅 {task.due_date.strftime('%d.%m')}\n"

        return response

    async def _complete_task(self, args: Dict, user_id: int) -> str:
        """Завершает задачу"""
        from brains.tasks import complete_task

        task_id = args.get("task_id")
        if not task_id:
            return "❌ Не указан ID задачи"

        task = await complete_task(task_id, user_id)

        if task:
            return f"✅ **Задача завершена!**\n\n{task.title}"
        return "❌ Не удалось завершить задачу (проверь ID)"

    async def _create_project(self, args: Dict, user_id: int) -> str:
        """Создаёт проект"""
        from brains.projects import create_project, ProjectPriority
        from datetime import datetime

        name = args.get("name", "")
        description = args.get("description", "")
        deadline_str = args.get("deadline")

        if not name:
            return "❌ Не указано название проекта"

        # Парсим дедлайн
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            except:
                pass

        project = await create_project(
            user_id=user_id,
            name=name,
            description=description,
            deadline=deadline
        )

        if project:
            response = f"✅ **Проект создан!**\n\n"
            response += f"📁 {project.name}\n"
            if project.description:
                response += f"📝 {project.description[:100]}\n"
            if project.deadline:
                response += f"📅 Дедлайн: {project.deadline.strftime('%d.%m.%Y')}"
            return response
        
        return "❌ Не удалось создать проект"

    async def _get_sprint_info(self, user_id: int) -> str:
        """Получает информацию о спринте"""
        from brains.sprints import get_active_sprint, get_sprint_stats, format_sprint_for_display

        sprint = await get_active_sprint(user_id)

        if not sprint:
            return "🏃 У тебя нет активного спринта"

        stats = await get_sprint_stats(sprint.id)
        days_left = sprint.days_remaining()

        response = f"🏃 **Активный спринт:**\n\n"
        response += f"📛 {sprint.name}\n"
        response += f"📅 {sprint.start_date} — {sprint.end_date}\n"
        response += f"⏳ Осталось дней: {days_left}\n"
        response += f"📊 Прогресс: {stats.get('completion_percent', 0)}%\n"
        
        if sprint.goal:
            response += f"\n🎯 Цель: {sprint.goal}"

        return response

    async def _get_productivity_stats(self, args: Dict, user_id: int) -> str:
        """Получает статистику продуктивности"""
        from brains.tasks import get_productivity_stats

        days = args.get("days", 7)
        stats = await get_productivity_stats(user_id, days)

        response = f"📊 **Продуктивность** ({days} дн.):\n\n"
        response += f"📋 Задач: {stats.get('total_tasks', 0)}\n"
        response += f"✅ Выполнено: {stats.get('completed_tasks', 0)}\n"
        response += f"🔄 В работе: {stats.get('in_progress_tasks', 0)}\n"
        response += f"🔴 Просрочено: {stats.get('overdue_tasks', 0)}\n"
        response += f"\n📈 Процент выполнения: {stats.get('completion_rate', 0)}%"

        return response


# Глобальный экземпляр
tool_executor = AIToolExecutor()
