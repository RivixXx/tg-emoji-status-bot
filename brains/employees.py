import logging
import httpx
from datetime import datetime, timezone, timedelta
from brains.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

async def get_todays_birthdays():
    """Проверяет, у кого сегодня день рождения"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Получаем текущую дату (МСК)
    moscow_tz = timezone(timedelta(hours=3))
    today = datetime.now(moscow_tz).strftime('%m-%d')
    
    try:
        async with httpx.AsyncClient() as client:
            # В Postgres можно фильтровать по месяцу и дню через to_char
            url = f"{SUPABASE_URL}/rest/v1/employees"
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                all_employees = response.json()
                celebrants = []
                for emp in all_employees:
                    # Проверяем формат даты (обычно YYYY-MM-DD)
                    emp_bd = emp['birthday'][5:] # Извлекаем MM-DD
                    if emp_bd == today:
                        celebrants.append(emp)
                return celebrants
            return []
    except Exception as e:
        logger.error(f"Error checking birthdays: {e}")
        return []

async def generate_birthday_card(employee_data: dict):
    """
    Здесь будет логика вызова DALL-E или другого сервиса генерации.
    Пока возвращаем плейсхолдер или описание промта.
    """
    characteristics = employee_data.get('characteristics', 'отличный человек')
    prompt = f"Digital art style, corporate greeting card, high quality. Theme: {characteristics}. Text: Happy Birthday {employee_data['full_name']}!"
    
    logger.info(f"🎨 Генерирую открытку для {employee_data['full_name']} с промтом: {prompt}")
    
    # TODO: Интеграция с DALL-E 3 API
    return None # Вернем URL или путь к файлу позже
