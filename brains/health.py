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
        timestamp = datetime.now(timezone.utc)

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
            logger.info(f"💾 Сохранение записи: {payload}")
            response = await client.post(SUPABASE_REST_URL, json=payload, headers=headers)
            logger.info(f"📊 Supabase ответ: {response.status_code}")
            if response.status_code in [201, 204, 200]:
                logger.info(f"✅ Здоровье: запись сохранена ({confirmed})")
                return True
            else:
                logger.error(f"Supabase Health Error: {response.status_code} - {response.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"Save health record failed: {e}")
        return False


async def get_health_stats(days: int = 7) -> dict:
    """
    Получает статистику по здоровью за последние N дней

    Returns:
        dict: {
            "total_days": int,
            "confirmed_days": int,
            "missed_days": int,
            "success_rate": float,
            "daily_stats": [{"date": str, "confirmed": bool, "time": str}]
        }
    """
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=none"  # Важно для Supabase REST API
    }

    # Получаем записи за последние N дней
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        async with httpx.AsyncClient() as client:
            # Запрос с фильтрацией по дате (Supabase REST API syntax)
            url = f"{SUPABASE_REST_URL}?date=gte.{start_date}&order=date.desc"
            logger.info(f"🔍 Запрос к Supabase: {url}")
            response = await client.get(url, headers=headers)
            
            logger.info(f"📊 Supabase ответ: {response.status_code}")
            logger.info(f"📄 Тело ответа: {response.text[:500]}")

            if response.status_code == 200:
                records = response.json()
                
                if not records:
                    return {
                        "total_days": 0,
                        "confirmed_days": 0,
                        "missed_days": 0,
                        "success_rate": 0,
                        "daily_stats": [],
                        "message": "Нет данных за указанный период"
                    }
                
                # Группируем по датам
                daily_data = {}
                for record in records:
                    date = record.get('date', 'unknown')
                    if date not in daily_data:
                        daily_data[date] = {
                            "date": date,
                            "confirmed": record.get('confirmed', False),
                            "time": record.get('time', 'N/A')
                        }
                
                # Преобразуем в список
                daily_stats = list(daily_data.values())
                daily_stats.sort(key=lambda x: x['date'], reverse=True)
                
                # Считаем статистику
                total_days = len(daily_stats)
                confirmed_days = sum(1 for d in daily_stats if d['confirmed'])
                missed_days = total_days - confirmed_days
                success_rate = round((confirmed_days / total_days * 100) if total_days > 0 else 0, 1)
                
                return {
                    "total_days": total_days,
                    "confirmed_days": confirmed_days,
                    "missed_days": missed_days,
                    "success_rate": success_rate,
                    "daily_stats": daily_stats
                }
            else:
                logger.error(f"Supabase Health Stats Error: {response.status_code}")
                return {
                    "total_days": 0,
                    "confirmed_days": 0,
                    "missed_days": 0,
                    "success_rate": 0,
                    "daily_stats": [],
                    "error": f"HTTP {response.status_code}"
                }
    except Exception as e:
        logger.error(f"Get health stats failed: {e}")
        return {
            "total_days": 0,
            "confirmed_days": 0,
            "missed_days": 0,
            "success_rate": 0,
            "daily_stats": [],
            "error": str(e)
        }


async def get_health_report_text(days: int = 7) -> str:
    """
    Возвращает текстовый отчёт о здоровье
    
    Returns:
        str: Форматированный отчёт
    """
    stats = await get_health_stats(days)
    
    if stats.get("error"):
        return f"❌ Ошибка получения статистики: {stats['error']}"
    
    if stats["total_days"] == 0:
        return "📊 Нет данных о здоровье за этот период. Начни отмечать уколы!"
    
    # Формируем отчёт
    lines = [
        "📊 **Статистика здоровья**\n",
        f"📅 Период: {stats['total_days']} дн.",
        f"✅ Подтверждено: {stats['confirmed_days']}",
        f"❌ Пропущено: {stats['missed_days']}",
        f"📈 Успешность: {stats['success_rate']}%\n"
    ]
    
    # Добавляем последние записи
    if stats['daily_stats']:
        lines.append("**Последние записи:**")
        for day in stats['daily_stats'][:5]:
            status = "✅" if day['confirmed'] else "❌"
            lines.append(f"{status} {day['date']} в {day['time']}")
    
    # Мотивация
    if stats['success_rate'] >= 90:
        lines.append("\n🏆 Отличный результат! Так держать! 💪")
    elif stats['success_rate'] >= 70:
        lines.append("\n👍 Хороший результат, но можно лучше! 😊")
    else:
        lines.append("\n💡 Нужно быть внимательнее к здоровью! ❤️")
    
    return "\n".join(lines)
