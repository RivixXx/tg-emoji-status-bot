"""
MCP Tools для Karina AI
Инструменты для работы с Supabase через MCP
"""
import logging
from typing import Optional, List, Dict
from brains.clients import supabase_client

logger = logging.getLogger(__name__)


# ========== MEMORY TOOLS ==========

async def mcp_search_memories(query: str, limit: int = 5, threshold: float = 0.7, user_id: int = 0) -> str:
    """
    Поиск воспоминаний в RAG памяти
    
    Args:
        query: Текст запроса для поиска
        limit: Максимальное количество результатов
        threshold: Порог схожести (0-1)
        user_id: ID пользователя для фильтрации
    
    Returns:
        Строка с найденными воспоминаниями
    """
    from brains.memory import search_memories
    return await search_memories(query, limit, threshold, user_id)


async def mcp_save_memory(content: str, metadata: dict = None) -> bool:
    """
    Сохранение факта в долговременную память
    
    Args:
        content: Текст для запоминания
        metadata: Дополнительные метаданные (user_id, source, etc.)
    
    Returns:
        True если успешно
    """
    from brains.memory import save_memory
    return await save_memory(content, metadata)


async def mcp_delete_memory(memory_id: int) -> bool:
    """
    Удаление воспоминания по ID
    
    Args:
        memory_id: ID воспоминания для удаления
    
    Returns:
        True если успешно
    """
    from brains.memory import delete_memory
    return await delete_memory(memory_id)


async def mcp_get_user_memories(user_id: int, limit: int = 50) -> List[Dict]:
    """
    Получение всех воспоминаний пользователя
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество результатов
    
    Returns:
        Список воспоминаний
    """
    from brains.memory import get_memories_by_user
    return await get_memories_by_user(user_id, limit)


async def mcp_clear_user_memories(user_id: int) -> int:
    """
    Очистка всех воспоминаний пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Количество удалённых воспоминаний
    """
    from brains.memory import clear_user_memories
    return await clear_user_memories(user_id)


# ========== HEALTH TOOLS ==========

async def mcp_save_health_record(user_id: int, confirmed: bool = True) -> bool:
    """
    Сохранение записи о здоровье (укол, замер)
    
    Args:
        user_id: ID пользователя
        confirmed: Подтверждено ли действие
    
    Returns:
        True если успешно
    """
    try:
        data = {
            "user_id": user_id,
            "confirmed": confirmed
        }
        response = supabase_client.table("health_records").insert(data).execute()
        return bool(response.data)
    except Exception as e:
        logger.error(f"Failed to save health record: {e}")
        return False


async def mcp_get_health_stats(user_id: int, days: int = 7) -> Dict:
    """
    Получение статистики здоровья за период
    
    Args:
        user_id: ID пользователя
        days: Количество дней для статистики
    
    Returns:
        Словарь со статистикой
    """
    try:
        from datetime import datetime, timedelta
        
        start_date = datetime.now() - timedelta(days=days)
        
        # Получаем все записи
        response = supabase_client.table("health_records")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("date", start_date.strftime('%Y-%m-%d'))\
            .order("date", desc=True)\
            .execute()
        
        if not response.data:
            return {
                "total": 0,
                "confirmed": 0,
                "missed": 0,
                "compliance_rate": 0
            }
        
        records = response.data
        total = len(records)
        confirmed = sum(1 for r in records if r.get("confirmed", True))
        missed = total - confirmed
        compliance_rate = round((confirmed / total * 100) if total > 0 else 0, 1)
        
        return {
            "total": total,
            "confirmed": confirmed,
            "missed": missed,
            "compliance_rate": compliance_rate,
            "period_days": days
        }
    except Exception as e:
        logger.error(f"Failed to get health stats: {e}")
        return {
            "total": 0,
            "confirmed": 0,
            "missed": 0,
            "compliance_rate": 0,
            "error": str(e)
        }


# ========== REMINDER TOOLS ==========

async def mcp_get_active_reminders() -> List[Dict]:
    """
    Получение активных напоминаний
    
    Returns:
        Список активных напоминаний
    """
    try:
        response = supabase_client.table("reminders")\
            .select("*")\
            .eq("is_active", True)\
            .order("scheduled_time", desc=False)\
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Failed to get active reminders: {e}")
        return []


async def mcp_cancel_reminder(reminder_id: str) -> bool:
    """
    Отмена напоминания
    
    Args:
        reminder_id: ID напоминания для отмены
    
    Returns:
        True если успешно
    """
    try:
        response = supabase_client.table("reminders")\
            .update({"is_active": False, "is_confirmed": False})\
            .eq("id", reminder_id)\
            .execute()
        
        return bool(response.data)
    except Exception as e:
        logger.error(f"Failed to cancel reminder: {e}")
        return False


# ========== QUERY TOOLS (универсальный SQL инструмент) ==========

async def mcp_execute_query(table: str, operation: str, filters: Dict = None, data: Dict = None) -> Dict:
    """
    Универсальный инструмент для выполнения запросов к таблице
    
    Args:
        table: Имя таблицы
        operation: Операция (select, insert, update, delete)
        filters: Фильтры для запроса (например {"user_id": 123})
        data: Данные для insert/update
    
    Returns:
        Результат запроса
    """
    try:
        query = supabase_client.table(table)
        
        if operation == "select":
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.select("*").execute()
            
        elif operation == "insert":
            if not data:
                return {"error": "Data required for insert"}
            response = query.insert(data).execute()
            
        elif operation == "update":
            if not data or not filters:
                return {"error": "Data and filters required for update"}
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.update(data).execute()
            
        elif operation == "delete":
            if not filters:
                return {"error": "Filters required for delete"}
            for key, value in filters.items():
                query = query.eq(key, value)
            response = query.delete().execute()
        else:
            return {"error": f"Unknown operation: {operation}"}
        
        return {
            "success": True,
            "data": response.data,
            "count": len(response.data) if response.data else 0
        }
    except Exception as e:
        logger.error(f"Failed to execute query: {e}")
        return {"success": False, "error": str(e)}


# ========== EMPLOYEES TOOLS ==========

async def mcp_get_todays_birthdays() -> List[Dict]:
    """
    Получение сотрудников с днем рождения сегодня

    Returns:
        Список сотрудников-именинников
    """
    from brains.employees import get_todays_birthdays
    return await get_todays_birthdays()


async def mcp_get_upcoming_birthdays(days: int = 7) -> List[Dict]:
    """
    Получение предстоящих дней рождения

    Args:
        days: Период в днях для поиска

    Returns:
        Список сотрудников с предстоящими ДР
    """
    from brains.employees import get_upcoming_birthdays
    return await get_upcoming_birthdays(days)


async def mcp_get_all_employees() -> List[Dict]:
    """
    Получение всех сотрудников

    Returns:
        Список всех сотрудников
    """
    from brains.employees import get_all_employees
    return await get_all_employees()


async def mcp_get_employee_by_id(employee_id: int) -> Optional[Dict]:
    """
    Получение сотрудника по ID

    Args:
        employee_id: ID сотрудника

    Returns:
        Данные сотрудника или None
    """
    from brains.employees import get_employee_by_id
    return await get_employee_by_id(employee_id)


async def mcp_add_employee(employee_data: dict) -> bool:
    """
    Добавление нового сотрудника

    Args:
        employee_data: Данные сотрудника {
            full_name: str,
            first_name: str,
            last_name: str,
            position: str,
            department: str,
            characteristics: str (опционально),
            birthday: str (YYYY-MM-DD, опционально)
        }

    Returns:
        True если успешно
    """
    from brains.employees import add_employee
    return await add_employee(employee_data)


async def mcp_update_employee(employee_id: int, update_data: dict) -> bool:
    """
    Обновление данных сотрудника

    Args:
        employee_id: ID сотрудника
        update_data: Данные для обновления

    Returns:
        True если успешно
    """
    from brains.employees import update_employee
    return await update_employee(employee_id, update_data)


async def mcp_delete_employee(employee_id: int) -> bool:
    """
    Удаление сотрудника

    Args:
        employee_id: ID сотрудника для удаления

    Returns:
        True если успешно
    """
    from brains.employees import delete_employee
    return await delete_employee(employee_id)


async def mcp_generate_birthday_card(employee_data: dict) -> str:
    """
    Генерация промта для открытки на день рождения

    Args:
        employee_data: Данные сотрудника

    Returns:
        Промт для генерации открытки
    """
    from brains.employees import generate_birthday_card
    return await generate_birthday_card(employee_data)
