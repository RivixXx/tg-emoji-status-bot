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


# Глобальный экземпляр
tool_executor = AIToolExecutor()
