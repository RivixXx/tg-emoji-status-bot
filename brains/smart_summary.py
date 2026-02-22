"""
Smart Summary для Karina AI
Еженедельные отчёты о продуктивности, здоровье и событиях
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from brains.clients import supabase_client
from brains.ai import ask_karina

logger = logging.getLogger(__name__)


async def generate_weekly_summary(user_id: int, days: int = 7) -> Dict:
    """
    Генерирует еженедельный отчёт о деятельности пользователя
    
    Args:
        user_id: ID пользователя
        days: Период отчёта в днях (по умолчанию 7)
    
    Returns:
        Словарь с данными отчёта
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    summary = {
        "period": {
            "start": start_date.strftime("%d.%m.%Y"),
            "end": end_date.strftime("%d.%m.%Y"),
            "days": days
        },
        "health": await _get_health_summary(user_id, days),
        "calendar": await _get_calendar_summary(days),
        "memories": await _get_memories_summary(user_id, days),
        "ai_summary": None
    }
    
    # Генерируем AI-резюме
    summary["ai_summary"] = await _generate_ai_summary(summary)
    
    return summary


async def _get_health_summary(user_id: int, days: int) -> Dict:
    """Получает сводку по здоровью"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        response = supabase_client.table("health_records")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("date", start_date.strftime('%Y-%m-%d'))\
            .execute()
        
        if not response.data:
            return {
                "total_records": 0,
                "confirmed": 0,
                "missed": 0,
                "compliance_rate": 0,
                "trend": "no_data"
            }
        
        records = response.data
        total = len(records)
        confirmed = sum(1 for r in records if r.get("confirmed", True))
        missed = total - confirmed
        compliance_rate = round((confirmed / total * 100) if total > 0 else 0, 1)
        
        # Определяем тренд (сравниваем с предыдущим периодом)
        prev_start = start_date - timedelta(days=days)
        prev_response = supabase_client.table("health_records")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("date", prev_start.strftime('%Y-%m-%d'))\
            .lt("date", start_date.strftime('%Y-%m-%d'))\
            .execute()
        
        if prev_response.data:
            prev_total = len(prev_response.data)
            prev_confirmed = sum(1 for r in prev_response.data if r.get("confirmed", True))
            prev_compliance = round((prev_confirmed / prev_total * 100) if prev_total > 0 else 0, 1)
            
            if compliance_rate > prev_compliance:
                trend = "improving"
            elif compliance_rate < prev_compliance:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "no_data"
        
        return {
            "total_records": total,
            "confirmed": confirmed,
            "missed": missed,
            "compliance_rate": compliance_rate,
            "trend": trend
        }
        
    except Exception as e:
        logger.error(f"Failed to get health summary: {e}")
        return {
            "total_records": 0,
            "confirmed": 0,
            "missed": 0,
            "compliance_rate": 0,
            "trend": "error",
            "error": str(e)
        }


async def _get_calendar_summary(days: int) -> Dict:
    """Получает сводку по календарю"""
    try:
        # Пробуем импортировать функции календаря
        from brains.calendar import get_upcoming_events
        
        # Получаем события за период
        # (в реальной реализации нужно добавить метод для получения прошлых событий)
        return {
            "total_events": 0,
            "completed": 0,
            "upcoming": 0,
            "message": "Интеграция в разработке"
        }
        
    except Exception as e:
        logger.error(f"Failed to get calendar summary: {e}")
        return {
            "total_events": 0,
            "completed": 0,
            "upcoming": 0,
            "error": str(e)
        }


async def _get_memories_summary(user_id: int, days: int) -> Dict:
    """Получает сводку по новым воспоминаниям"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        response = supabase_client.table("memories")\
            .select("id, content, metadata, created_at")\
            .gte("created_at", start_date.isoformat())\
            .execute()
        
        if not response.data:
            return {
                "new_memories": 0,
                "categories": {}
            }
        
        memories = response.data
        
        # Подсчитываем по категориям
        categories = {}
        for memory in memories:
            metadata = memory.get("metadata", {})
            source = metadata.get("source", "unknown")
            categories[source] = categories.get(source, 0) + 1
        
        return {
            "new_memories": len(memories),
            "categories": categories
        }
        
    except Exception as e:
        logger.error(f"Failed to get memories summary: {e}")
        return {
            "new_memories": 0,
            "categories": {},
            "error": str(e)
        }


async def _generate_ai_summary(summary_data: Dict) -> str:
    """Генерирует текстовое резюме через AI"""
    try:
        health = summary_data.get("health", {})
        memories = summary_data.get("memories", {})
        
        prompt = f"""
Создай краткий еженедельный отчёт для Михаила на основе данных:

📊 Период: {summary_data['period']['start']} - {summary_data['period']['end']}

❤️ Здоровье:
- Всего записей: {health.get('total_records', 0)}
- Подтверждено: {health.get('confirmed', 0)}
- Пропущено: {health.get('missed', 0)}
- Успешность: {health.get('compliance_rate', 0)}%
- Тренд: {health.get('trend', 'no_data')}

🧠 Память:
- Новых воспоминаний: {memories.get('new_memories', 0)}
- Категории: {memories.get('categories', {})}

Напиши мотивирующий, дружелюбный отчёт в стиле Карины (1-2 абзаца). 
Используй эмодзи умеренно. Отметь успехи и дай рекомендации.
"""
        
        response = await ask_karina(prompt)
        return response if response else "Не удалось сгенерировать отчёт 😔"
        
    except Exception as e:
        logger.error(f"Failed to generate AI summary: {e}")
        return "Произошла ошибка при генерации отчёта 😔"


async def send_weekly_summary(user_id: int, bot_client) -> bool:
    """
    Отправляет еженедельный отчёт пользователю
    
    Args:
        user_id: ID пользователя
        bot_client: Telegram bot клиент
    
    Returns:
        True если успешно отправлено
    """
    try:
        summary = await generate_weekly_summary(user_id)
        
        # Форматируем сообщение
        message = f"""
📊 **Еженедельный отчёт**
{summary['period']['start']} - {summary['period']['end']}

❤️ **Здоровье:**
✅ Подтверждено: {summary['health']['confirmed']}
❌ Пропущено: {summary['health']['missed']}
📈 Успешность: {summary['health']['compliance_rate']}%

🧠 **Память:**
📝 Новых воспоминаний: {summary['memories']['new_memories']}

{summary['ai_summary']}
"""
        
        await bot_client.send_message(user_id, message)
        logger.info(f"📊 Weekly summary sent to user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send weekly summary: {e}")
        return False


async def start_weekly_summary_scheduler(bot_client, user_id: int):
    """
    Запускает планировщик еженедельных отчётов
    
    Args:
        bot_client: Telegram bot клиент
        user_id: ID пользователя
    """
    import asyncio
    
    while True:
        try:
            # Отправляем отчёт каждое воскресенье в 10:00
            now = datetime.now(timezone(timedelta(hours=3)))
            
            # Если воскресенье и 10:00
            if now.weekday() == 6 and now.hour == 10 and now.minute == 0:
                await send_weekly_summary(user_id, bot_client)
            
            # Проверяем каждый час
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in weekly summary scheduler: {e}")
            await asyncio.sleep(3600)
