import logging
from datetime import datetime, timezone, timedelta
from brains.clients import supabase_client
from brains.config import MY_ID

logger = logging.getLogger(__name__)


async def save_health_record(confirmed: bool, timestamp: datetime = None):
    """Сохраняет запись о здоровье (укол) в Supabase"""
    if not timestamp:
        moscow_tz = timezone(timedelta(hours=3))
        timestamp = datetime.now(moscow_tz)

    try:
        data = {
            "user_id": MY_ID,
            "confirmed": confirmed,
            "timestamp": timestamp.isoformat(),
            "date": timestamp.strftime('%Y-%m-%d'),
            "time": timestamp.strftime('%H:%M:%S')
        }
        
        response = supabase_client.table("health_records").insert(data).execute()
        
        if response.data:
            logger.info("✅ Здоровье: запись сохранена")
            return True
        else:
            logger.error(f"Supabase Save Error: {response}")
            return False
    except Exception as e:
        logger.error(f"Save health record failed: {e}")
        return False


def get_health_stats(days: int = 7) -> dict:
    """Получает статистику по здоровью за последние N дней"""
    start_date = (datetime.now(timezone(timedelta(hours=3))) - timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        # Фильтруем по user_id и дате, сортируем по timestamp
        response = supabase_client.table("health_records")\
            .select("*")\
            .eq("user_id", MY_ID)\
            .gte("date", start_date)\
            .order("timestamp", desc=True)\
            .execute()

        if not response.data:
            return {
                "total_days": 0, "confirmed_days": 0, "missed_days": 0,
                "success_rate": 0, "daily_stats": [],
                "message": "Нет данных"
            }

        records = response.data

        # Группируем по датам (берем самую свежую запись за день)
        daily_data = {}
        for record in records:
            date = record.get('date')
            if date and date not in daily_data:
                daily_data[date] = {
                    "date": date,
                    "confirmed": record.get('confirmed', False),
                    "time": record.get('time', 'N/A')
                }

        # Сортируем результат по дате
        daily_stats = sorted(daily_data.values(), key=lambda x: x['date'], reverse=True)

        confirmed_days = sum(1 for d in daily_stats if d['confirmed'])
        total_days = len(daily_stats)

        return {
            "total_days": total_days,
            "confirmed_days": confirmed_days,
            "missed_days": total_days - confirmed_days,
            "success_rate": round((confirmed_days / total_days * 100) if total_days > 0 else 0, 1),
            "daily_stats": daily_stats
        }
        
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        return {"error": str(e), "daily_stats": []}


async def get_health_report_text(days: int = 7) -> str:
    """Форматирует отчет для Telegram"""
    # get_health_stats - синхронная функция
    stats = get_health_stats(days)

    if "error" in stats:
        return f"❌ Ошибка получения статистики: {stats['error']}"

    if not stats.get("daily_stats"):
        return "📊 Нет данных за последние 7 дней. Напиши 'сделал', когда уколешься! ❤️"

    lines = [
        "📊 **Статистика здоровья**\n",
        f"📅 Период: {stats['total_days']} дн.",
        f"✅ Подтверждено: {stats['confirmed_days']}",
        f"❌ Пропущено: {stats['missed_days']}",
        f"📈 Успешность: {stats['success_rate']}%\n",
        "**Последние записи:**"
    ]

    for day in stats['daily_stats'][:5]:
        status = "✅" if day['confirmed'] else "❌"
        lines.append(f"{status} {day['date']} в {day['time']}")

    if stats['success_rate'] >= 90:
        lines.append("\n🏆 Результат супер! Так держать! 💪")
    else:
        lines.append("\n💡 Помни, здоровье — это главное! ❤️")

    return "\n".join(lines)
