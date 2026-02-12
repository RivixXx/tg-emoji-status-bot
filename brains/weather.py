import aiohttp
import logging
from brains.config import WEATHER_API_KEY, CITY

logger = logging.getLogger(__name__)

async def get_weather():
    if not WEATHER_API_KEY:
        return None
    
    url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    temp = round(data['main']['temp'])
                    desc = data['weather'][0]['description']
                    return f"{temp}°C, {desc}"
                else:
                    logger.error(f"Ошибка погоды: статус {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Ошибка при запросе погоды: {e}")
        return None
