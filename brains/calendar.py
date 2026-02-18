import json
import logging
import os
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from brains.config import GOOGLE_CALENDAR_CREDENTIALS

# Подавляем лишние логи от Google
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Кэш для календаря: {timestamp: (events_text, expire_at)}
_calendar_cache = {
    "events": None,
    "expire_at": None
}

def get_calendar_service():
    if not GOOGLE_CALENDAR_CREDENTIALS:
        logger.error("GOOGLE_CALENDAR_CREDENTIALS not set!")
        return None
    try:
        creds_dict = json.loads(GOOGLE_CALENDAR_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds, static_discovery=False)
    except Exception as e:
        logger.error(f"Error connecting to Google Calendar: {e}")
        return None

async def add_calendar(calendar_id):
    """Принудительно добавляет календарь в список доступных"""
    service = get_calendar_service()
    if not service: return False
    try:
        service.calendarList().insert(body={'id': calendar_id}).execute()
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
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])

        logger.info(f"🔎 Доступные календари: {[c['id'] for c in calendars]}")

        if not calendars:
            return "Я не вижу твоих календарей. Пожалуйста, напиши мне свой email, чтобы я могла 'подключиться' к твоим планам. 😊"

        all_events = []
        for entry in calendars:
            cal_id = entry['id']
            cal_name = entry.get('summary', 'Календарь')

            try:
                events_result = service.events().list(
                    calendarId=cal_id, timeMin=now_iso,
                    maxResults=5, singleEvents=True,
                    orderBy='startTime'
                ).execute()

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
        
        # Сохранение в кэш (TTL 5 минут)
        _calendar_cache["events"] = result
        _calendar_cache["expire_at"] = now + timedelta(minutes=5)
        logger.debug(f"📅 Календарь: обновлён кэш (TTL 5 мин)")
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return "Ошибка при получении событий."

async def create_event(summary, start_time, duration_minutes=30, description=None):
    service = get_calendar_service()
    if not service: return False

    try:
        # Ищем первый календарь, который не является техническим
        calendar_list = service.calendarList().list().execute()
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

        service.events().insert(calendarId=cal_id, body=event).execute()
        return True
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return False


async def check_calendar_conflicts():
    """
    Проверяет календарь на конфликты (наложения событий)
    
    Returns:
        list: Список конфликтов [{"event1": str, "event2": str, "overlap_minutes": int}]
    """
    service = get_calendar_service()
    if not service:
        return []
    
    try:
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        # Получаем события на неделю вперёд
        end_week = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace('+00:00', 'Z')
        
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        if not calendars:
            return []
        
        all_events = []
        for entry in calendars:
            cal_id = entry['id']
            cal_name = entry.get('summary', 'Календарь')
            
            try:
                events_result = service.events().list(
                    calendarId=cal_id, timeMin=now, timeMax=end_week,
                    maxResults=50, singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                for event in events_result.get('items', []):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    end = event['end'].get('dateTime', event['end'].get('date'))
                    
                    # Для全天 событий
                    if not end:
                        end = start
                    
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
        
        # Сортируем по времени начала
        all_events.sort(key=lambda x: x['start'])
        
        # Ищем конфликты
        conflicts = []
        for i in range(len(all_events) - 1):
            current = all_events[i]
            next_event = all_events[i + 1]
            
            # Если конец текущего события позже начала следующего
            if current['end'] > next_event['start']:
                overlap = (current['end'] - next_event['start']).total_seconds() / 60
                
                # Если это не одно и то же событие и наложение > 0 минут
                if overlap > 0 and current['summary'] != next_event['summary']:
                    conflicts.append({
                        'event1': f"{current['summary']} ({current['calendar']})",
                        'event2': f"{next_event['summary']} ({next_event['calendar']})",
                        'overlap_minutes': round(overlap),
                        'time1': current['start'].strftime('%d.%m %H:%M'),
                        'time2': next_event['start'].strftime('%d.%m %H:%M')
                    })
        
        if conflicts:
            logger.warning(f"⚠️ Найдено конфликтов в календаре: {len(conflicts)}")
        
        return conflicts
        
    except Exception as e:
        logger.error(f"Error checking calendar conflicts: {e}")
        return []


async def get_conflict_report() -> str:
    """
    Возвращает текстовый отчёт о конфликтах в календаре
    
    Returns:
        str: Форматированный отчёт
    """
    conflicts = await check_calendar_conflicts()
    
    if not conflicts:
        return "✅ В календаре всё чисто! Конфликтов не найдено. 😊"
    
    report = ["⚠️ **Обнаружены конфликты в расписании:**\n"]
    
    for i, conflict in enumerate(conflicts, 1):
        report.append(
            f"{i}. **{conflict['event1']}** ({conflict['time1']})\n"
            f"   ⚡ **{conflict['event2']}** ({conflict['time2']})\n"
            f"   🕐 Наложение: {conflict['overlap_minutes']} мин.\n"
        )
    
    report.append("\n💡 **Совет:** Проверь, сможешь ли ты присутствовать на обеих встречах, или перенеси одну из них.")
    
    return "\n".join(report)


async def get_upcoming_events_detailed(max_results=10):
    """Возвращает события с полными данными для напоминаний"""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace('+00:00', 'Z')
    
    service = get_calendar_service()
    if not service:
        return []
    
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        if not calendars:
            return []
        
        all_events = []
        for entry in calendars:
            cal_id = entry['id']
            
            try:
                events_result = service.events().list(
                    calendarId=cal_id, timeMin=now_iso,
                    maxResults=max_results, singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                for event in events_result.get('items', []):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    
                    all_events.append({
                        'summary': event['summary'],
                        'start_dt': start_dt,
                        'calendar': cal_id,
                        'description': event.get('description', '')
                    })
            except Exception as e:
                logger.error(f"Ошибка получения событий: {e}")
                continue
        
        return all_events[:max_results]
        
    except Exception as e:
        logger.error(f"Error getting detailed events: {e}")
        return []
