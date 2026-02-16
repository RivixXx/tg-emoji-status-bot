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
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Error connecting to Google Calendar: {e}")
        return None

async def get_upcoming_events(max_results=5):
    """Получает ближайшие события из всех доступных календарей"""
    service = get_calendar_service()
    if not service: return "Не удалось подключиться к календарю."

    try:
        now = datetime.utcnow().isoformat() + 'Z'
        # Сначала получаем список всех календарей
        calendar_list = service.calendarList().list().execute()
        all_events = []

        for entry in calendar_list.get('items', []):
            cal_id = entry['id']
            cal_name = entry.get('summary', 'Без названия')
            
            events_result = service.events().list(
                calendarId=cal_id, timeMin=now,
                maxResults=max_results, singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Превращаем в читаемый формат
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted_start = dt.strftime('%d.%m %H:%M')
                all_events.append(f"📅 {formatted_start} — {event['summary']} (в: {cal_name})")

        if not all_events:
            return "На ближайшее время планов нет."
        
        return "
".join(all_events[:max_results])
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return "Ошибка при получении событий."

async def create_event(summary, start_time, duration_minutes=30, description=None):
    """Создает событие в основном календаре"""
    service = get_calendar_service()
    if not service: return False

    try:
        start = start_time.isoformat()
        end = (start_time + timedelta(minutes=duration_minutes)).isoformat()

        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start, 'timeZone': 'Europe/Moscow'},
            'end': {'dateTime': end, 'timeZone': 'Europe/Moscow'},
        }

        service.events().insert(calendarId='primary', body=event).execute()
        return True
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return False
