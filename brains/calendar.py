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

async def get_all_calendars(service):
    """Возвращает список всех ID календарей, к которым есть доступ"""
    try:
        calendar_list = service.calendarList().list().execute()
        items = calendar_list.get('items', [])
        ids = [cal['id'] for cal in items]
        logger.info(f"🔎 Доступные календари: {ids}")
        return items
    except Exception as e:
        logger.error(f"Error listing calendars: {e}")
        return []

async def get_upcoming_events(max_results=10):
    service = get_calendar_service()
    if not service: return "Не удалось подключиться к календарю."

    try:
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        calendars = await get_all_calendars(service)
        
        if not calendars:
            # Если список пуст, это часто значит, что Google еще не обновил кеш прав.
            # Попробуем проверить основной календарь сервис-аккаунта (там пусто, но это тест)
            calendars = [{'id': 'primary', 'summary': 'Очередь (пусто)'}]

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
                    dt_msk = dt.astimezone(timezone(timedelta(hours=3)))
                    formatted_start = dt_msk.strftime('%d.%m %H:%M')
                    all_events.append((dt_msk, f"📅 {formatted_start} — {event['summary']} (в: {cal_name})"))
            except Exception as e:
                logger.warning(f"Ошибка доступа к {cal_id}: {e}")
                continue

        if not all_events:
            return "Я пока не вижу твоих планов. Убедись, что ты поделился календарем с rivix-830@karina-487619.iam.gserviceaccount.com и нажал 'Сохранить' в настройках Google."
        
        all_events.sort(key=lambda x: x[0])
        return "\n".join([e[1] for e in all_events[:max_results]])
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return "Ошибка при получении событий."

async def create_event(summary, start_time, duration_minutes=30, description=None):
    service = get_calendar_service()
    if not service: return False

    try:
        # Пытаемся найти первый не-технический календарь для записи
        calendars = await get_all_calendars(service)
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
