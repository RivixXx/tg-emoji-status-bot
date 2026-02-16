import json
import logging
from datetime import datetime, timedelta, timezone
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
        return build('calendar', 'v3', credentials=creds, static_discovery=False)
    except Exception as e:
        logger.error(f"Error connecting to Google Calendar: {e}")
        return None

async def get_target_calendar_id(service):
    """Находит ID календаря пользователя (пропуская технический календарь сервис-аккаунта)"""
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        # Ищем календарь, который НЕ является техническим адресом сервис-аккаунта
        for cal in calendars:
            if 'iam.gserviceaccount.com' not in cal['id']:
                return cal['id']
        
        return 'primary'
    except:
        return 'primary'

async def get_upcoming_events(max_results=10):
    service = get_calendar_service()
    if not service: return "Не удалось подключиться к календарю."

    try:
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        if not calendars:
            return "Я не вижу ни одного доступного календаря. Пожалуйста, поделись своим календарем с моим email: rivix-830@karina-487619.iam.gserviceaccount.com"

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
                
                for event in events_result.get('items', []):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    # Переводим в МСК для отображения
                    dt_msk = dt.astimezone(timezone(timedelta(hours=3)))
                    formatted_start = dt_msk.strftime('%d.%m %H:%M')
                    all_events.append((dt_msk, f"📅 {formatted_start} — {event['summary']} (в: {cal_name})"))
            except:
                continue

        if not all_events:
            return "На ближайшее время планов нет."
        
        # Сортируем по дате
        all_events.sort(key=lambda x: x[0])
        return "\n".join([e[1] for e in all_events[:max_results]])
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return "Ошибка при получении событий."

async def create_event(summary, start_time, duration_minutes=30, description=None):
    service = get_calendar_service()
    if not service: return False

    try:
        cal_id = await get_target_calendar_id(service)
        
        # Устанавливаем таймзону МСК, если её нет
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone(timedelta(hours=3)))

        start = start_time.isoformat()
        end = (start_time + timedelta(minutes=duration_minutes)).isoformat()

        event = {
            'summary': summary,
            'description': description or "Создано Кариной 🤖",
            'start': {'dateTime': start},
            'end': {'dateTime': end},
        }

        service.events().insert(calendarId=cal_id, body=event).execute()
        logger.info(f"Событие '{summary}' создано в календаре {cal_id}")
        return True
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return False
