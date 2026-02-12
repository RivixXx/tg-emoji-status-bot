import os

# Настройки системы
API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
USER_SESSION = os.environ['SESSION_STRING']
KARINA_TOKEN = os.environ.get('KARINA_BOT_TOKEN')
TARGET_USER_ID = int(os.environ.get('TARGET_USER_ID', 0))
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0))

# Погода (OpenWeatherMap)
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
CITY = os.environ.get('WEATHER_CITY', 'Moscow')

# Эмодзи-статусы
EMOJI_MAP = {
    'morning': 5395463497783983254,
    'day': 4927197721900614739,
    'evening': 5219748856626973291,
    'night': 5247100325059370738,
    'breakfast': 5913264639025615311,
    'transit': 5246743378917334735,
    'weekend': 4906978012303458988
}
