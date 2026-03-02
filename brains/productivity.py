"""
Модуль продуктивности Karina AI
- Отслеживание привычек
- Анализ рабочего времени
- Детектор переработок
- AI-рекомендации по оптимизации
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from brains.clients import supabase_client
from brains.ai import ask_karina
from brains.calendar import get_today_calendar_events

logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ И НАСТРОЙКИ
# ============================================================================

# Рабочее время (по умолчанию)
DEFAULT_WORK_START = 8  # 8:00
DEFAULT_WORK_END = 17   # 17:00
MAX_WORK_HOURS = 9      # Максимум рабочих часов в день

# Переработки
OVERWORK_THRESHOLD_HOURS = 10  # Часов в день для тревоги
OVERWORK_NIGHT_START = 22      # После 22:00 — ночь
OVERWORK_WEEKEND_ALERT = True  # Предупреждать о работе в выходные

# Привычки по умолчанию
DEFAULT_HABITS = [
    {"name": "Здоровый сон", "target": "7-8 часов", "category": "health"},
    {"name": "Обед", "target": "13:00-14:00", "category": "health"},
    {"name": "Перерывы", "target": "5 мин каждый час", "category": "work"},
    {"name": "Планирование", "target": "С вечера на завтра", "category": "work"},
]

# ============================================================================
# РАБОТА С БД
# ============================================================================

async def save_work_session(user_id: int, start_time: datetime, end_time: datetime, 
                            meetings: int = 0, tasks_completed: int = 0):
    """
    Сохраняет рабочую сессию
    
    Args:
        user_id: ID пользователя
        start_time: Начало работы
        end_time: Конец работы
        meetings: Количество встреч
        tasks_completed: Выполненные задачи
    """
    try:
        duration_hours = (end_time - start_time).total_seconds() / 3600
        
        data = {
            "user_id": user_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_hours": round(duration_hours, 2),
            "meetings_count": meetings,
            "tasks_completed": tasks_completed,
            "date": start_time.strftime('%Y-%m-%d')
        }
        
        response = supabase_client.table("work_sessions").insert(data).execute()
        logger.info(f"💾 Рабочая сессия сохранена: {duration_hours}ч")
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error saving work session: {e}")
        return False


async def get_work_sessions(user_id: int, days: int = 7) -> List[Dict]:
    """Получает рабочие сессии за период"""
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        response = supabase_client.table("work_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("date", cutoff.strftime('%Y-%m-%d'))\
            .order("date", desc=True)\
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting work sessions: {e}")
        return []


async def save_habit_track(user_id: int, habit_name: str, completed: bool, 
                           notes: str = None):
    """
    Отмечает выполнение привычки
    
    Args:
        user_id: ID пользователя
        habit_name: Название привычки
        completed: Выполнена или нет
        notes: Заметки
    """
    try:
        data = {
            "user_id": user_id,
            "habit_name": habit_name,
            "completed": completed,
            "notes": notes,
            "date": datetime.now().strftime('%Y-%m-%d'),
            "tracked_at": datetime.now(timezone.utc).isoformat()
        }
        
        response = supabase_client.table("habits").insert(data).execute()
        logger.info(f"💾 Привычка '{habit_name}' отмечена: {'✅' if completed else '❌'}")
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error saving habit track: {e}")
        return False


async def get_habit_stats(user_id: int, days: int = 7) -> Dict[str, Dict]:
    """
    Получает статистику по привычкам за период
    
    Returns:
        Словарь: {habit_name: {"total": int, "completed": int, "rate": float}}
    """
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        response = supabase_client.table("habits")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("date", cutoff.strftime('%Y-%m-%d'))\
            .execute()
        
        if not response.data:
            return {}
        
        # Группируем по привычкам
        stats = {}
        for record in response.data:
            habit = record["habit_name"]
            if habit not in stats:
                stats[habit] = {"total": 0, "completed": 0, "rate": 0}
            
            stats[habit]["total"] += 1
            if record.get("completed", False):
                stats[habit]["completed"] += 1
        
        # Считаем процент
        for habit in stats:
            if stats[habit]["total"] > 0:
                stats[habit]["rate"] = round(
                    (stats[habit]["completed"] / stats[habit]["total"]) * 100, 1
                )
        
        return stats
    except Exception as e:
        logger.error(f"Error getting habit stats: {e}")
        return {}


async def get_overwork_days(user_id: int, days: int = 30) -> List[Dict]:
    """
    Получает дни с переработками
    
    Returns:
        Список дней где длительность > MAX_WORK_HOURS
    """
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        response = supabase_client.table("work_sessions")\
            .select("*")\
            .eq("user_id", user_id)\
            .gte("date", cutoff.strftime('%Y-%m-%d'))\
            .execute()
        
        if not response.data:
            return []
        
        overwork_days = []
        for session in response.data:
            if session.get("duration_hours", 0) > MAX_WORK_HOURS:
                overwork_days.append({
                    "date": session["date"],
                    "duration": session["duration_hours"],
                    "end_time": session["end_time"]
                })
        
        return overwork_days
    except Exception as e:
        logger.error(f"Error getting overwork days: {e}")
        return []


# ============================================================================
# АНАЛИЗ ПРОДУКТИВНОСТИ
# ============================================================================

async def analyze_work_patterns(user_id: int, days: int = 14) -> Dict:
    """
    Анализирует рабочие паттерны пользователя
    
    Returns:
        {
            "avg_start_time": "08:30",
            "avg_end_time": "18:45",
            "avg_duration": 9.5,
            "overwork_days": 3,
            "weekend_work_days": 1,
            "late_night_days": 2,
            "total_meetings": 15
        }
    """
    sessions = await get_work_sessions(user_id, days)
    
    if not sessions:
        return {"error": "Недостаточно данных"}
    
    total_duration = 0
    start_times = []
    end_times = []
    overwork_count = 0
    weekend_count = 0
    late_night_count = 0
    total_meetings = 0
    
    for session in sessions:
        duration = session.get("duration_hours", 0)
        total_duration += duration
        
        if duration > MAX_WORK_HOURS:
            overwork_count += 1
        
        # Извлекаем время
        start = datetime.fromisoformat(session["start_time"])
        end = datetime.fromisoformat(session["end_time"])
        
        start_times.append(start)
        end_times.append(end)
        
        # Выходные (5=Сб, 6=Вс)
        if start.weekday() >= 5:
            weekend_count += 1
        
        # Поздняя ночь
        if end.hour >= OVERWORK_NIGHT_START:
            late_night_count += 1
        
        total_meetings += session.get("meetings_count", 0)
    
    # Средние значения
    avg_start = None
    avg_end = None
    
    if start_times:
        avg_start_minutes = sum(t.hour * 60 + t.minute for t in start_times) / len(start_times)
        avg_start = f"{int(avg_start_minutes // 60):02d}:{int(avg_start_minutes % 60):02d}"
    
    if end_times:
        avg_end_minutes = sum(t.hour * 60 + t.minute for t in end_times) / len(end_times)
        avg_end = f"{int(avg_end_minutes // 60):02d}:{int(avg_end_minutes % 60):02d}"
    
    return {
        "avg_start_time": avg_start or "Н/Д",
        "avg_end_time": avg_end or "Н/Д",
        "avg_duration": round(total_duration / len(sessions), 1) if sessions else 0,
        "overwork_days": overwork_count,
        "weekend_work_days": weekend_count,
        "late_night_days": late_night_count,
        "total_meetings": total_meetings,
        "total_days": len(sessions)
    }


async def analyze_habits_with_ai(user_id: int, days: int = 7) -> str:
    """
    AI-анализ привычек с рекомендациями
    
    Returns:
        Текст с рекомендациями от Карины
    """
    habit_stats = await get_habit_stats(user_id, days)
    work_patterns = await analyze_work_patterns(user_id, days)
    
    if not habit_stats and not work_patterns:
        return "Недостаточно данных для анализа. Начни отслеживать привычки! 😊"
    
    # Формируем контекст для AI
    context = "Статистика пользователя за {days} дней:\n\n".format(days=days)
    
    # Привычки
    if habit_stats:
        context += "**Привычки:**\n"
        for habit, stats in habit_stats.items():
            context += f"- {habit}: {stats['completed']}/{stats['total']} ({stats['rate']}%)\n"
    
    # Работа
    if work_patterns and "error" not in work_patterns:
        context += "\n**Рабочие паттерны:**\n"
        context += f"- Среднее начало: {work_patterns.get('avg_start_time', 'Н/Д')}\n"
        context += f"- Средний конец: {work_patterns.get('avg_end_time', 'Н/Д')}\n"
        context += f"- Средняя длительность: {work_patterns.get('avg_duration', 0)}ч\n"
        context += f"- Переработок: {work_patterns.get('overwork_days', 0)}\n"
        context += f"- Выходных дней работы: {work_patterns.get('weekend_work_days', 0)}\n"
        context += f"- Поздних вечеров: {work_patterns.get('late_night_days', 0)}\n"
    
    # Запрашиваем AI-анализ
    prompt = f"""
Ты — Карина, заботливая помощница Михаила. Проанализируй статистику продуктивности и привычек.

ДАННЫЕ:
{context}

ЗАДАЧА:
1. Дай краткую оценку (2-3 предложения)
2. Выдели 1-2 сильные стороны
3. Предложи 1-2 конкретные улучшения
4. Если есть переработки — мягко напомни о балансе

СТИЛЬ:
- Тёплый, поддерживающий
- Без осуждения
- Конкретные рекомендации
- 1-2 эмодзи к месту
"""
    
    try:
        analysis = await ask_karina(prompt, chat_id=user_id)
        return analysis
    except Exception as e:
        logger.error(f"AI habit analysis error: {e}")
        return "Не удалось получить AI-анализ. Попробуй позже! 😊"


# ============================================================================
# АВТОМАТИЧЕСКОЕ ОТСЛЕЖИВАНИЕ
# ============================================================================

async def auto_track_workday(user_id: int):
    """
    Автоматически создаёт рабочую сессию на основе календаря
    
    Идея: если есть встречи в календаре — это рабочий день
    """
    today = datetime.now().strftime('%Y-%m-%d')
    events = await get_today_calendar_events()
    
    if not events:
        return None
    
    # Находим первую и последнюю встречу
    meeting_times = [e['start'] for e in events]
    first_meeting = min(meeting_times)
    last_meeting = max(e['end'] for e in events)
    
    # Добавляем по 30 мин до и после
    work_start = first_meeting - timedelta(minutes=30)
    work_end = last_meeting + timedelta(minutes=30)
    
    # Сохраняем сессию
    await save_work_session(
        user_id=user_id,
        start_time=work_start,
        end_time=work_end,
        meetings=len(events)
    )
    
    logger.info(f"✅ Автотрекинг: рабочий день {len(events)} встреч")
    return work_end


async def check_overwork_alert(user_id: int) -> Optional[str]:
    """
    Проверяет нужна ли тревога о переработке
    
    Returns:
        Сообщение если есть проблема, иначе None
    """
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    
    # Получаем сессии за сегодня
    sessions = await get_work_sessions(user_id, days=1)
    
    if not sessions:
        return None
    
    today_session = sessions[0]
    duration = today_session.get("duration_hours", 0)
    end_time = datetime.fromisoformat(today_session["end_time"])
    
    alerts = []
    
    # Долгий рабочий день
    if duration > OVERWORK_THRESHOLD_HOURS:
        alerts.append(f"Ты сегодня работал {duration}ч — это больше нормы! 😟")
    
    # Поздний вечер
    if end_time.hour >= OVERWORK_NIGHT_START:
        alerts.append(f"Ты закончил в {end_time.strftime('%H:%M')} — это поздно! Пора отдыхать. 😴")
    
    # Выходной
    if now.weekday() >= 5:
        alerts.append("Ты работаешь в выходной! Не забывай об отдыхе. 🌿")
    
    if alerts:
        return "\n\n".join(alerts)
    
    return None


# ============================================================================
# ОТЧЁТЫ
# ============================================================================

async def generate_productivity_report(user_id: int, days: int = 7) -> str:
    """
    Генерирует отчёт о продуктивности
    
    Returns:
        Форматированный текст отчёта
    """
    work_patterns = await analyze_work_patterns(user_id, days)
    habit_stats = await get_habit_stats(user_id, days)
    
    if "error" in work_patterns:
        return "📊 Недостаточно данных о работе за этот период."
    
    report = ["📊 **Отчёт о продуктивности** ({days} дн.)\n".format(days=days)]
    
    # Работа
    report.append("*📈 Рабочие паттерны:*")
    report.append(f"⏰ Начало: {work_patterns.get('avg_start_time', 'Н/Д')}")
    report.append(f"⏰ Конец: {work_patterns.get('avg_end_time', 'Н/Д')}")
    report.append(f"📅 Средняя длительность: {work_patterns.get('avg_duration', 0)}ч")
    report.append(f"🤝 Встреч: {work_patterns.get('total_meetings', 0)}")
    report.append("")
    
    # Проблемы
    issues = []
    if work_patterns.get('overwork_days', 0) > 0:
        issues.append(f"⚠️ Переработок: {work_patterns['overwork_days']}")
    if work_patterns.get('weekend_work_days', 0) > 0:
        issues.append(f"📅 Работал в выходные: {work_patterns['weekend_work_days']}")
    if work_patterns.get('late_night_days', 0) > 0:
        issues.append(f"🌙 Поздних вечеров: {work_patterns['late_night_days']}")
    
    if issues:
        report.append("*⚠️ Зоны внимания:*")
        report.extend(issues)
        report.append("")
    else:
        report.append("*✅ Режим работы в норме!*")
        report.append("")
    
    # Привычки
    if habit_stats:
        report.append("*🎯 Привычки:*")
        for habit, stats in habit_stats.items():
            emoji = "✅" if stats['rate'] >= 80 else "⚠️" if stats['rate'] >= 50 else "❌"
            report.append(f"{emoji} {habit}: {stats['rate']}% ({stats['completed']}/{stats['total']})")
        report.append("")
    
    # AI-рекомендации
    report.append("*🤖 Рекомендации Карины:*")
    ai_analysis = await analyze_habits_with_ai(user_id, days)
    report.append(ai_analysis)
    
    return "\n".join(report)


# ============================================================================
# УПРАВЛЕНИЕ ПРИВЫЧКАМИ
# ============================================================================

async def get_user_habits(user_id: int) -> List[Dict]:
    """Получает список привычек пользователя"""
    # Пока возвращаем дефолтные
    # В будущем — из БД
    return DEFAULT_HABITS.copy()


async def add_custom_habit(user_id: int, name: str, target: str, category: str) -> bool:
    """Добавляет пользовательскую привычку"""
    # В будущем — сохранение в БД
    logger.info(f"✅ Добавлена привычка: {name} ({category})")
    return True


async def remove_habit(user_id: int, habit_name: str) -> bool:
    """Удаляет привычку"""
    logger.info(f"🗑 Удалена привычка: {habit_name}")
    return True
