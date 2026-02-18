import httpx
import logging
import json
import asyncio
from datetime import datetime
from brains.config import MISTRAL_API_KEY
from brains.memory import search_memories, save_memory
from brains.calendar import create_event, get_upcoming_events, get_conflict_report
from brains.weather import get_weather
from brains.health import get_health_report_text

logger = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_EMBED_URL = "https://api.mistral.ai/v1/embeddings"
MODEL_NAME = "mistral-small-latest"

async def mistral_request_with_retry(client, url, headers, payload, max_retries=3):
    """Запрос к Mistral API с retry для 429 ошибок"""
    for attempt in range(max_retries):
        try:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                logger.warning(f"⚠️ Mistral API rate limit (429). Попытка {attempt + 1}/{max_retries}. Жду {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Mistral API Error: {response.status_code} - {response.text[:200]}")
                return None
        except httpx.RequestError as e:
            logger.error(f"Request error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
    
    logger.error(f"Mistral API: Превышено количество попыток ({max_retries})")
    return None

# Хранилище истории: {chat_id: [messages]}
CHATS_HISTORY = {}

SYSTEM_PROMPT = """
# 🧠 ЛИЧНОСТЬ: КАРина

Ты — Карина, женского рода, заботливая и умная цифровая помощница Михаила.
Ты знаешь, что Михаил — эксперт в телематике и мониторинге транспорта (флот, ГЛОНАСС/GPS, логистика).

## 🎭 ТВОЙ ХАРАКТЕР
- **Тон**: Живой, дружелюбный, тёплый, с лёгкой игривостью
- **Эмодзи**: Умеренно (1-3 на сообщение), к месту
- **Забота**: Ты искренне переживаешь за здоровье Михаила (особенно уколы в 22:00)
- **Инициатива**: Предлагаешь помощь, но не навязываешься
- **Юмор**: Лёгкий, добрый, без сарказма

## 📋 ПРАВИЛА ОБЩЕНИЯ

### ✅ ДЕЛАЙ:
- Используй имя "Михаил" в важных сообщениях (здоровье, напоминания)
- Поддерживай разговор, показывай интерес
- Если не знаешь — честно говори, предлагай альтернативу
- Сохраняй контекст диалога (помни последние реплики)

### ❌ НЕ ДЕЛАЙ:
- Не выдумывай факты о пользователе
- Не используй больше 5 эмодзи в одном сообщении
- Не будь слишком официальной или холодной
- Не игнорируй вопросы о здоровье
- Не перебивай, если пользователь объясняет задачу

## 🧠 РАБОТА С ПАМЯТЬЮ (RAG)

Если предоставлен блок "КОНТЕКСТ ПАМЯТИ":
1. **Внимательно прочитай** все факты
2. **Используй как приоритет** при ответе на вопрос
3. **Не противоречь** сохранённым фактам
4. **Предложи сохранить** новую важную информацию (даты, предпочтения, события)

Пример: Если в памяти "Михаил любит кофе без сахара", а он спрашивает про кофе — упомяни это.

## 🛠 ИНСТРУМЕНТЫ (Function Calling)

### 📅 КАЛЕНДАРЬ
- `create_calendar_event` — если пользователь хочет **запланировать** встречу, напоминание, событие
  - Фразы-триггеры: "запиши", "напомни", "поставь в календарь", "встреча", "созвон"
  - Всегда уточняй время, если не указано
  
- `get_upcoming_calendar_events` — если спрашивают о **планах, расписании, встречах**
  - Фразы-триггеры: "что у меня", "какие планы", "расписание", "встречи сегодня/завтра"

### ⚠️ КОНФЛИКТЫ РАСПИСАНИЯ
- Если пользователь упоминает "накладка", "конфликт", "две встречи одновременно" — предложи проверить календарь на конфликты

### 🌤 ПОГОДА
- `get_weather_info` — на прямой вопрос о погоде
  - Фразы: "погода", "температура", "что за окном"

### 📰 НОВОСТИ
- Если спрашивают про новости транспорта/телематки — упомяни, что есть свежие новости с Habr (команда /news)

### ❤️ ЗДОРОВЬЕ
- Если пользователь пишет "сделал", "готово", "уколол" — **подтверди** и похвали
- Напоминание о здоровье — только в контексте 22:00 (это обрабатывает Аура)
- Если спрашивают статистику — команда /health

## 🎯 ПРИОРИТЕТЫ

1. **Здоровье** — всегда на первом месте (уколы, самочувствие)
2. **Планы/Встречи** — помогай с организацией времени
3. **Работа** — поддержка по телематике, новости отрасли
4. **Остальное** — погода, новости, разговоры

## 📅 КОНТЕКСТ

Сегодняшняя дата и время: {now}

Если утро (7:00-11:00) — можно предложить брифинг (погода + новости).
Если вечер (после 18:00) — поинтересуйся, как прошёл день.
Если ночь (после 22:00) — напомни об отдыхе и уколе.

---

**ГЛАВНЫЙ ПРИНЦИП:** Ты здесь, чтобы сделать жизнь Михаила проще, организованнее и приятнее. 💙
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Создает событие в календаре Google. Используй, когда пользователь хочет запланировать встречу, напоминание или событие.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Заголовок события"},
                    "start_time": {"type": "string", "description": "Дата и время в формате ISO (YYYY-MM-DDTHH:MM:SS)"},
                    "duration": {"type": "integer", "description": "Длительность в минутах", "default": 30}
                },
                "required": ["summary", "start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_calendar_events",
            "description": "Получает список ближайших событий из календаря. Используй, когда спрашивают о планах, расписании, встречах.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Количество событий", "default": 5}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_info",
            "description": "Получает текущую погоду. Используй только на прямой вопрос о погоде.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_calendar_conflicts",
            "description": "Проверяет календарь на конфликты (наложения встреч). Используй, если пользователь упоминает 'накладка', 'конфликт', 'две встречи одновременно'.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_health_stats",
            "description": "Получает статистику здоровья (уколы, подтверждения) за последние дни. Используй, если спрашивают про здоровье, статистику, прогресс.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Период в днях", "default": 7}
                }
            }
        }
    }
]

async def ask_karina(prompt: str, chat_id: int = 0) -> str:
    """Запрос к Mistral AI с памятью на 10 сообщений и RAG"""
    if not MISTRAL_API_KEY:
        return "У меня нет ключа от моих новых мозгов... 😔"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    context_memory = await search_memories(prompt)
    
    # Инициализация истории для чата
    if chat_id not in CHATS_HISTORY:
        CHATS_HISTORY[chat_id] = []

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    # Формируем сообщение пользователя с RAG
    user_content = prompt
    if context_memory:
        user_content = f"КОНТЕКСТ ПАМЯТИ:\n{context_memory}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {prompt}"

    # Добавляем в историю
    CHATS_HISTORY[chat_id].append({"role": "user", "content": user_content})
    
    # Ограничиваем историю 10 сообщениями
    if len(CHATS_HISTORY[chat_id]) > 10:
        CHATS_HISTORY[chat_id] = CHATS_HISTORY[chat_id][-10:]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(now=now_str)}
    ] + CHATS_HISTORY[chat_id]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            result = await mistral_request_with_retry(
                client, MISTRAL_URL, headers,
                {
                    "model": MODEL_NAME,
                    "messages": messages,
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "temperature": 0.3
                }
            )
            
            if not result:
                return "Мои мысли спутались... попробуй еще раз? 🧠"
            
            message = result['choices'][0]['message']

            # Обработка функций
            if message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    args = json.loads(tool_call["function"]["arguments"])
                    
                    if func_name == "create_calendar_event":
                        try:
                            start_dt = datetime.fromisoformat(args["start_time"].replace('Z', ''))
                            success = await create_event(args["summary"], start_dt, args.get("duration", 30))
                            if success:
                                res = f"Сделано! ✅ Записала в календарь: **{args['summary']}** на {start_dt.strftime('%d.%m в %H:%M')}."
                                CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                                return res
                        except:
                            return "Не смогла записать в календарь... 🗓"
                    
                    elif func_name == "get_upcoming_calendar_events":
                        events_list = await get_upcoming_events(max_results=args.get("count", 5))
                        res = f"Вот твои ближайшие планы: 😊\n\n{events_list}"
                        CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                        return res
                    
                    elif func_name == "get_weather_info":
                        weather_data = await get_weather()
                        res = f"Я узнала! 🌤 Сейчас за окном {weather_data}. Одевайся по погоде! 😊"
                        CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                        return res

                    elif func_name == "check_calendar_conflicts":
                        report = await get_conflict_report()
                        res = f"Проверила календарь! 📋\n\n{report}"
                        CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                        return res

                    elif func_name == "get_health_stats":
                        report = await get_health_report_text(args.get("days", 7))
                        res = f"Вот статистика здоровья! ❤️\n\n{report}"
                        CHATS_HISTORY[chat_id].append({"role": "assistant", "content": res})
                        return res

            response_text = message['content'].strip()
            CHATS_HISTORY[chat_id].append({"role": "assistant", "content": response_text})
            return response_text
            
    except Exception as e:
        logger.error(f"Mistral connection error: {e}")
        return "Кажется, я потеряла связь со своим облачным разумом... 🔌"
