import json
import logging
import os
import ast
import asyncio
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from brains.config import GOOGLE_CALENDAR_CREDENTIALS

# Подавляем лишние логи от Google
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Кэш для календаря
_calendar_cache = {
    "events": None,
    "expire_at": None
}

def get_calendar_service():
    if not GOOGLE_CALENDAR_CREDENTIALS:
        logger.error("GOOGLE_CALENDAR_CREDENTIALS not set!")
        return None
    
    try:
        creds_raw = GOOGLE_CALENDAR_CREDENTIALS.strip()
        
        if (creds_raw.startswith("'") and creds_raw.endswith("'")) or \
           (creds_raw.startswith('"') and creds_raw.endswith('"')):
            creds_raw = creds_raw[1:-1]

        try:
            creds_dict = json.loads(creds_raw)
        except json.JSONDecodeError:
            creds_dict = ast.literal_eval(creds_raw)

        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds, static_discovery=False)
    except Exception as e:
        logger.error(f"❌ Error connecting to Google Calendar: {e}")
        return None

async def add_calendar(calendar_id):
    """Принудительно добавляет календарь в список доступных"""
    service = get_calendar_service()
    if not service: return False
    try:
        # Исправлено: выполняем блокирующий вызов в отдельном потоке
        await asyncio.to_thread(service.calendarList().insert(body={'id': calendar_id}).execute)
        logger.info(f"✅ Календарь {calendar_id} успешно добавлен в список.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении календаря {calendar_id}: {e}")
        return False

async def get_upcoming_events(max_results=10, force_refresh=False):
    """Получает список предстоящих событий с кэшированием (TTL 5 минут)"""
    now = datetime.now(timezone.utc)
    
    # Проверка кэша
    if not force_refresh and _calendar_cache["events"] and _calendar_cache["expire_at"]:
        if now < _calendar_cache["expire_at"]:
            logger.debug("📅 Календарь: используем кэш")
            return _calendar_cache["events"]
    
    service = get_calendar_service()
    if not service: return "Не удалось подключиться к календарю."

    try:
        now_iso = now.isoformat().replace('+00:00', 'Z')
        
        # Исправлено: выполняем блокирующий вызов в отдельном потоке
        calendar_list = await asyncio.to_thread(service.calendarList().list().execute)
        calendars = calendar_list.get('items', [])

        if not calendars:
            return "Я не вижу твоих календарей. Пожалуйста, напиши мне свой email, чтобы я могла 'подключиться' к твоим планам. 😊"

        all_events = []
        for entry in calendars:
            cal_id = entry['id']
            cal_name = entry.get('summary', 'Календарь')

            try:
                # Исправлено: выполняем блокирующий вызов в отдельном потоке
                events_result = await asyncio.to_thread(
                    service.events().list(
                        calendarId=cal_id, timeMin=now_iso,
                        maxResults=5, singleEvents=True,
                        orderBy='startTime'
                    ).execute
                )

                for event in events_result.get('items', []):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    dt_msk = dt.astimezone(timezone(timedelta(hours=3)))
                    formatted_start = dt_msk.strftime('%d.%m %H:%M')
                    all_events.append((dt_msk, f"📅 {formatted_start} — {event['summary']} (в: {cal_name})"))
            except:
                continue

        if not all_events:
            result = "На ближайшее время планов нет."
        else:
            all_events.sort(key=lambda x: x[0])
            result = "\n".join([e[1] for e in all_events[:max_results]])
        
        # Сохранение в кэш
        _calendar_cache["events"] = result
        _calendar_cache["expire_at"] = now + timedelta(minutes=5)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return "Ошибка при получении событий."

async def create_event(summary, start_time, duration_minutes=30, description=None, create_reminder=True):
    """
    Создает событие в календаре
    
    Args:
        summary: Заголовок события
        start_time: Время начала
        duration_minutes: Длительность в минутах
        description: Описание
        create_reminder: Автоматически создать напоминание за 15 минут (по умолчанию True)
    
    Returns:
        True если успешно
    """
    service = get_calendar_service()
    if not service:
        logger.error("❌ Calendar service unavailable")
        return False

    try:
        # Исправлено: выполняем блокирующий вызов в отдельном потоке
        calendar_list = await asyncio.to_thread(service.calendarList().list().execute)
        calendars = calendar_list.get('items', [])
        cal_id = 'primary'
        for cal in calendars:
            if 'iam.gserviceaccount.com' not in cal['id']:
                cal_id = cal['id']
                break

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone(timedelta(hours=3)))

        event = {
            'summary': summary,
            'description': description or "Создано Кариной 🤖",
            'start': {'dateTime': start_time.isoformat()},
            'end': {'dateTime': (start_time + timedelta(minutes=duration_minutes)).isoformat()},
        }

        # Исправлено: выполняем блокирующий вызов в отдельном потоке
        await asyncio.to_thread(service.events().insert(calendarId=cal_id, body=event).execute)
        
        logger.info(f"✅ Событие '{summary}' создано в календаре")
        
        # Автоматическое создание напоминания
        if create_reminder:
            try:
                from brains.reminders import reminder_manager, ReminderType
                
                reminder_time = start_time - timedelta(minutes=15)
                now = datetime.now(timezone(timedelta(hours=3)))
                
                # Создаём напоминание только если время ещё не прошло
                if reminder_time > now:
                    reminder_id = f"meeting_{int(start_time.timestamp())}"
                    
                    # Проверяем, нет ли уже такого напоминания
                    if reminder_id not in reminder_manager.reminders:
                        reminder = Reminder(
                            id=reminder_id,
                            type=ReminderType.MEETING,
                            message=f"Встреча: {summary}",
                            scheduled_time=reminder_time,
                            escalate_after=[5, 10],  # Более короткая эскалация для встреч
                            context={
                                "title": summary,
                                "minutes": 15,
                                "source": "auto_create",
                                "event_start": start_time.isoformat()
                            }
                        )
                        await reminder_manager.add_reminder(reminder)
                        logger.info(f"🔔 Напоминание о встрече '{summary}' создано на {reminder_time.strftime('%H:%M')}")
                    else:
                        logger.debug(f"⚠️ Напоминание {reminder_id} уже существует")
                else:
                    logger.warning(f"⏰ Пропущено создание напоминания для '{summary}' — время уже прошло")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка создания напоминания о встрече: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return False

async def check_calendar_conflicts():
    service = get_calendar_service()
    if not service: return []
    
    try:
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        end_week = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace('+00:00', 'Z')
        
        # Исправлено: выполняем блокирующий вызов в отдельном потоке
        calendar_list = await asyncio.to_thread(service.calendarList().list().execute)
        calendars = calendar_list.get('items', [])
        
        if not calendars: return []
        
        all_events = []
        for entry in calendars:
            cal_id = entry['id']
            cal_name = entry.get('summary', 'Календарь')
            
            try:
                # Исправлено: выполняем блокирующий вызов в отдельном потоке
                events_result = await asyncio.to_thread(
                    service.events().list(
                        calendarId=cal_id, timeMin=now, timeMax=end_week,
                        maxResults=50, singleEvents=True,
                        orderBy='startTime'
                    ).execute
                )
                
                for event in events_result.get('items', []):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    end = event['end'].get('dateTime', event['end'].get('date'))
                    if not end: end = start
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    
                    all_events.append({
                        'summary': event['summary'],
                        'calendar': cal_name,
                        'start': start_dt,
                        'end': end_dt
                    })
            except Exception as e:
                logger.error(f"Ошибка получения событий из {cal_id}: {e}")
                continue
        
        all_events.sort(key=lambda x: x['start'])
        conflicts = []
        for i in range(len(all_events) - 1):
            current = all_events[i]
            next_event = all_events[i + 1]
            if current['end'] > next_event['start']:
                overlap = (current['end'] - next_event['start']).total_seconds() / 60
                if overlap > 0 and current['summary'] != next_event['summary']:
                    conflicts.append({
                        'event1': f"{current['summary']} ({current['calendar']})",
                        'event2': f"{next_event['summary']} ({next_event['calendar']})",
                        'overlap_minutes': round(overlap),
                        'time1': current['start'].strftime('%d.%m %H:%M'),
                        'time2': next_event['start'].strftime('%d.%m %H:%M')
                    })
        return conflicts
    except Exception as e:
        logger.error(f"Error checking calendar conflicts: {e}")
        return []

async def get_conflict_report() -> str:
    conflicts = await check_calendar_conflicts()
    if not conflicts: return "✅ В календаре всё чисто! Конфликтов не найдено. 😊"
    report = ["⚠️ **Обнаружены конфликты в расписании:**\n"]
    for i, conflict in enumerate(conflicts, 1):
        report.append(f"{i}. **{conflict['event1']}** ({conflict['time1']})\n   ⚡ **{conflict['event2']}** ({conflict['time2']})\n   🕐 Наложение: {conflict['overlap_minutes']} мин.\n")
    report.append("\n💡 **Совет:** Проверь, сможешь ли ты присутствовать на обеих встречах, или перенеси одну из них.")
    return "\n".join(report)


async def get_today_calendar_events() -> list:
    """
    Получает список событий на сегодня (с 00:00 до 23:59 по МСК)
    Возвращает список словарей: [{'summary': str, 'start': datetime, 'end': datetime, 'calendar': str}]
    """
    service = get_calendar_service()
    if not service:
        logger.error("❌ Calendar service unavailable")
        return []

    try:
        moscow_tz = timezone(timedelta(hours=3))
        now = datetime.now(moscow_tz)
        
        # Начало и конец текущего дня по МСК
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Конвертируем в UTC для API
        day_start_utc = day_start.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        day_end_utc = day_end.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Исправлено: выполняем блокирующий вызов в отдельном потоке
        calendar_list = await asyncio.to_thread(service.calendarList().list().execute)
        calendars = calendar_list.get('items', [])

        if not calendars:
            return []

        all_events = []
        for entry in calendars:
            cal_id = entry['id']
            cal_name = entry.get('summary', 'Календарь')
            
            # Пропускаем календари сервисных аккаунтов
            if 'iam.gserviceaccount.com' in cal_id:
                continue

            try:
                # Исправлено: выполняем блокирующий вызов в отдельном потоке
                events_result = await asyncio.to_thread(
                    service.events().list(
                        calendarId=cal_id,
                        timeMin=day_start_utc,
                        timeMax=day_end_utc,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute
                )

                for event in events_result.get('items', []):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    end = event['end'].get('dateTime', event['end'].get('date'))
                    
                    # Для全天 событий (без времени) используем начало дня
                    if 'T' not in start:
                        continue  # Пропускаем全天 события
                    
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00')) if end else start_dt + timedelta(hours=1)
                    
                    # Конвертируем в МСК для удобства
                    start_msk = start_dt.astimezone(moscow_tz)
                    end_msk = end_dt.astimezone(moscow_tz)
                    
                    all_events.append({
                        'summary': event['summary'],
                        'calendar': cal_name,
                        'start': start_msk,
                        'end': end_msk,
                        'id': event.get('id', ''),
                        'description': event.get('description', '')
                    })
                    
            except Exception as e:
                logger.error(f"Ошибка получения событий из {cal_id}: {e}")
                continue

        # Сортируем по времени начала
        all_events.sort(key=lambda x: x['start'])
        return all_events

    except Exception as e:
        logger.error(f"Error getting today's events: {e}")
        return []
