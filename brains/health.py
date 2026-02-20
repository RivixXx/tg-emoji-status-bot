import httpx
import logging
import json
from datetime import datetime, timezone, timedelta
from brains.config import SUPABASE_URL, SUPABASE_KEY, MY_ID

logger = logging.getLogger(__name__)

SUPABASE_REST_URL = f"{SUPABASE_URL}/rest/v1/health_records"

async def save_health_record(confirmed: bool, timestamp: datetime = None):
    """Сохраняет запись о здоровье (укол) в Supabase"""
    if not timestamp:
        # Используем локальное время для сохранения даты/времени, 
        # но сохраняем UTC timestamp для точности
        moscow_tz = timezone(timedelta(hours=3))
        timestamp = datetime.now(moscow_tz)

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    payload = {
        "user_id": MY_ID,
        "confirmed": confirmed,
        "timestamp": timestamp.isoformat(),
        "date": timestamp.strftime('%Y-%m-%d'),
        "time": timestamp.strftime('%H:%M:%S')
    }

    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"💾 Сохранение здоровья для ID {MY_ID}: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            response = await client.post(SUPABASE_REST_URL, json=payload, headers=headers)
            if response.status_code in [201, 204, 200]:
                logger.info(f"✅ Здоровье: запись сохранена")
                return True
            else:
                logger.error(f"Supabase Save Error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Save health record failed: {e}")
        return False


async def get_health_stats(days: int = 7) -> dict:
    """Получает статистику по здоровью за последние N дней для текущего пользователя"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=none"
    }

    # Считаем дату начала (7 дней назад)
    start_date = (datetime.now(timezone(timedelta(hours=3))) - timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        async with httpx.AsyncClient() as client:
            # 🔍 Фильтруем по user_id и дате, сортируем по timestamp
            url = f"{SUPABASE_REST_URL}?user_id=eq.{MY_ID}&date=gte.{start_date}&order=timestamp.desc"
            logger.info(f"🔍 Запрос статистики для {MY_ID} с {start_date}")
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                records = response.json()
                
                if not records:
                    return {
                        "total_days": 0, "confirmed_days": 0, "missed_days": 0,
                        "success_rate": 0, "daily_stats": [],
                        "message": "Нет данных"
                    }
                
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
            else:
                logger.error(f"Supabase Stats Error: {response.status_code}")
                return {"error": f"HTTP {response.status_code}", "daily_stats": []}
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        return {"error": str(e), "daily_stats": []}


async def get_health_report_text(days: int = 7) -> str:
    """Форматирует отчет для Telegram"""
    stats = await get_health_stats(days)
    
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
