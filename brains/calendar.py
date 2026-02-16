import json
import logging
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from brains.config import GOOGLE_CALENDAR_CREDENTIALS

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    if not GOOGLE_CALENDAR_CREDENTIALS:
        logger.error("GOOGLE_CALENDAR_CREDENTIALS not set!")
        return None
    try:
        creds_dict = json.loads(GOOGLE_CALENDAR_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        # static_discovery=False убирает варнинг про file_cache
        return build('calendar', 'v3', credentials=creds, static_discovery=False)
    except Exception as e:
        logger.error(f"Error connecting to Google Calendar: {e}")
        return None

async def get_upcoming_events(max_results=10):
    """Получает ближайшие события из всех доступных календарей"""
    service = get_calendar_service()
    if not service: return "Не удалось подключиться к календарю."

    try:
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Получаем список календарей
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        # Если список пуст, попробуем хотя бы 'primary' (это сам сервис-аккаунт)
        if not calendars:
            calendars = [{'id': 'primary', 'summary': 'Основной'}]

        all_events = []
        for entry in calendars:
            cal_id = entry['id']
            cal_name = entry.get('summary', 'Календарь')
            
            try:
                events_result = service.events().list(
                    calendarId=cal_id, timeMin=now,
                    maxResults=5, singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    formatted_start = dt.strftime('%d.%m %H:%M')
                    all_events.append(f"📅 {formatted_start} — {event['summary']} (в: {cal_name})")
            except Exception as e:
                logger.warning(f"Не удалось прочитать календарь {cal_id}: {e}")
                continue

        if not all_events:
            return "На ближайшее время планов не найдено. Проверь, что ты поделился нужным календарем с моим email: rivix-830@karina-487619.iam.gserviceaccount.com"
        
        # Сортируем все события по времени, так как они из разных календарей
        all_events.sort()
        return "\n".join(all_events[:max_results])
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return "Ошибка при получении событий."

async def create_event(summary, start_time, duration_minutes=30, description=None):
    """Создает событие в основном календаре"""
    service = get_calendar_service()
    if not service: return False

    try:
        # Убеждаемся, что время в правильном формате с таймзоной
        if start_time.tzinfo is None:
            # Если зоны нет, считаем что это МСК (UTC+3)
            from datetime import timezone, timedelta
            start_time = start_time.replace(tzinfo=timezone(timedelta(hours=3)))

        start = start_time.isoformat()
        end = (start_time + timedelta(minutes=duration_minutes)).isoformat()

        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start},
            'end': {'dateTime': end},
        }

        # Пытаемся записать в 'primary'. 
        # ВАЖНО: Событие создастся в календаре самого СЕРВИС-АККАУНТА.
        # Чтобы оно появилось у тебя, ты должен быть подписан на этот аккаунт 
        # или мы должны указать твой email как calendarId, если есть права.
        service.events().insert(calendarId='primary', body=event).execute()
        return True
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return False
