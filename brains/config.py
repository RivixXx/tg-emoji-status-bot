import os

# Настройки системы
API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
USER_SESSION = os.environ['SESSION_STRING']
KARINA_TOKEN = os.environ.get('KARINA_BOT_TOKEN')
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://prucbyogggkflmxohylo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBydWNieW9nZ2drZmxteG9oeWxvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEyNjMyNzEsImV4cCI6MjA4NjgzOTI3MX0.zo9-LytryhxsI-CflDwdYH4-LmaIifP-DTwbzd5OA1U')
TARGET_USER_ID = int(os.environ.get('TARGET_USER_ID', 0))
MY_ID = int(os.environ.get('MY_TELEGRAM_ID', 0))

# Погода (OpenWeatherMap)
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
CITY = os.environ.get('WEATHER_CITY', 'Moscow')

# Эмодзи-статусы
EMOJI_MAP = {
    'morning': 4927197721900614739,
    'day': 5415717494105055663,
    'evening': 5219748856626973291,
    'night': 5247100325059370738,
    'breakfast': 5395463497783983254,
    'transit': 5244482516722655121,
    'weekend': 4906978012303458988,
    'work': 5362079447136610876,
    'lunch': 5285361500049910055,
    'dinner': 5454246314277619140,
    'freetime': 5226893221191237996,
    'sleep': 5462990652943904884
}
