import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from brains.clients import supabase_client

logger = logging.getLogger(__name__)


async def get_todays_birthdays() -> List[Dict]:
    """Проверяет, у кого сегодня день рождения (по московскому времени)"""
    moscow_tz = timezone(timedelta(hours=3))
    today = datetime.now(moscow_tz)
    today_str = today.strftime('%m-%d')  # MM-DD формат

    try:
        # Получаем всех сотрудников из таблицы
        response = supabase_client.table("employees").select("*").execute()

        if response.data:
            celebrants = []
            for emp in response.data:
                if emp.get('birthday'):
                    # Извлекаем месяц и день из даты рождения
                    emp_bd = emp['birthday'][5:]  # MM-DD из YYYY-MM-DD
                    if emp_bd == today_str:
                        celebrants.append(emp)
            return celebrants
        return []
    except Exception as e:
        logger.error(f"Error checking birthdays: {e}")
        return []


async def get_all_employees() -> List[Dict]:
    """Получает список всех сотрудников"""
    try:
        response = supabase_client.table("employees").select("*").order("department").execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting employees: {e}")
        return []


async def get_employee_by_id(employee_id: int) -> Optional[Dict]:
    """Получает сотрудника по ID"""
    try:
        response = supabase_client.table("employees").select("*").eq("id", employee_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error getting employee: {e}")
        return None


async def add_employee(employee_data: dict) -> bool:
    """Добавляет нового сотрудника в базу"""
    try:
        response = supabase_client.table("employees").insert(employee_data).execute()
        if response.data:
            logger.info(f"✅ Сотрудник {employee_data['full_name']} добавлен")
            return True
        return False
    except Exception as e:
        logger.error(f"Error adding employee: {e}")
        return False


async def update_employee(employee_id: int, update_data: dict) -> bool:
    """Обновляет данные сотрудника"""
    try:
        response = supabase_client.table("employees").update(update_data).eq("id", employee_id).execute()
        if response.data:
            logger.info(f"✅ Сотрудник {employee_id} обновлен")
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating employee: {e}")
        return False


async def delete_employee(employee_id: int) -> bool:
    """Удаляет сотрудника по ID"""
    try:
        response = supabase_client.table("employees").delete().eq("id", employee_id).execute()
        if response.data:
            logger.info(f"🗑️ Сотрудник {employee_id} удален")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting employee: {e}")
        return False


async def get_upcoming_birthdays(days: int = 7) -> List[Dict]:
    """Получает список предстоящих дней рождения"""
    moscow_tz = timezone(timedelta(hours=3))
    today = datetime.now(moscow_tz)
    
    try:
        response = supabase_client.table("employees").select("*").execute()
        
        if not response.data:
            return []
        
        upcoming = []
        for emp in response.data:
            if not emp.get('birthday'):
                continue
            
            # Создаем дату ДР в текущем году
            bd_month = int(emp['birthday'][5:7])
            bd_day = int(emp['birthday'][8:10])
            
            try:
                bd_this_year = today.replace(month=bd_month, day=bd_day)
            except ValueError:
                # Для 29 февраля используем 28 февраля
                bd_this_year = today.replace(month=2, day=28)
            
            # Вычисляем разницу в днях
            days_until = (bd_this_year - today).days
            
            # Если в этом году уже прошел, берем следующий год
            if days_until < 0:
                try:
                    bd_next_year = today.replace(year=today.year + 1, month=bd_month, day=bd_day)
                except ValueError:
                    bd_next_year = today.replace(year=today.year + 1, month=2, day=28)
                days_until = (bd_next_year - today).days
            
            if 0 <= days_until <= days:
                emp_copy = emp.copy()
                emp_copy['days_until'] = days_until
                upcoming.append(emp_copy)
        
        # Сортируем по возрастанию дней
        upcoming.sort(key=lambda x: x['days_until'])
        return upcoming
    
    except Exception as e:
        logger.error(f"Error getting upcoming birthdays: {e}")
        return []


async def generate_birthday_card(employee_data: dict):
    """
    Генерирует описание промта для создания открытки DALL-E
    """
    characteristics = employee_data.get('characteristics', 'отличный человек')
    full_name = employee_data.get('full_name', 'Сотрудник')
    
    prompt = f"""
Digital art style, corporate greeting card, high quality.
Theme: {characteristics}.
Text: Happy Birthday {full_name}!
Color scheme: warm, celebratory tones.
Style: modern, professional, friendly.
"""
    
    logger.info(f"🎨 Генерирую открытку для {full_name}")
    logger.info(f"📝 Промт: {prompt.strip()}")
    
    # TODO: Интеграция с DALL-E 3 API
    return prompt.strip()
