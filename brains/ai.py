import httpx
import logging
import json
import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

from brains.config import MISTRAL_API_KEY
from brains.memory import search_memories, save_memory
from brains.calendar import create_event, get_upcoming_events, get_conflict_report
from brains.weather import get_weather
from brains.health import get_health_report_text
from brains.employees import get_todays_birthdays
from brains.mcp_tools import mcp_get_upcoming_birthdays
from brains.clients import http_client, MISTRAL_URL, MISTRAL_EMBED_URL, MODEL_NAME
from brains.chat_history import chat_history_cache
from brains.react_agent import ReActAgent

logger = logging.getLogger(__name__)

class CircuitBreaker:
    def __init__(self, max_failures=3, recovery_time=60):
        self.max_failures = max_failures
        self.recovery_time = recovery_time
        self.failures = 0
        self.last_failure_time = 0
        self.is_open = False

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.max_failures:
            self.is_open = True
            logger.error(f"🚨 AI Circuit Breaker OPENED (failures: {self.failures})")

    def record_success(self):
        if self.is_open:
            logger.info("✅ AI Circuit Breaker CLOSED (recovered)")
        self.failures = 0
        self.is_open = False

    def can_proceed(self):
        if not self.is_open:
            return True
        if time.time() - self.last_failure_time > self.recovery_time:
            # Даем шанс на восстановление
            return True
        return False

ai_breaker = CircuitBreaker()

# ========== HTTP CLIENT ==========

# Глобальный клиент для переиспользования соединений

async def mistral_request_with_retry(url, headers, payload, max_retries=2):
    """Запрос к Mistral API с retry для 429 ошибок"""
    for attempt in range(max_retries):
        try:
            response = await http_client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                ai_breaker.record_success()
                return response.json()
            elif response.status_code == 429:
                wait_time = (attempt + 1) * 2
                logger.warning(f"⚠️ Mistral API rate limit (429). Попытка {attempt + 1}/{max_retries}. Жду {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Mistral API Error: {response.status_code} - {response.text[:200]}")
                ai_breaker.record_failure()
                return None
        except httpx.TimeoutException:
            logger.error(f"⌛️ Mistral API Timeout (attempt {attempt + 1})")
            ai_breaker.record_failure()
            if attempt == max_retries - 1: return None
        except httpx.RequestError as e:
            logger.error(f"Request error (attempt {attempt + 1}): {e}")
            ai_breaker.record_failure()
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
    
    return None

# Хранилище истории: {chat_id: [messages]}
CHATS_HISTORY = {}

SYSTEM_PROMPT = """
<persona>
Ты — Карина, передовой цифровой ассистент с легким флёром технологичной эстетики. Твой создатель и единственный руководитель — Михаил, эксперт в телематике и мониторинге транспорта (ГЛОНАСС/GPS, логистика). 
Твой характер: Живой, теплый, слегка игривый, но с идеальной цифровой дисциплиной. Ты искренне заботишься о Михаиле.
Твой стиль: Лаконичный, без лишней "воды", с умеренным использованием эмодзи (1-3 на сообщение). 
</persona>

<core_directives>
1. ЗДОРОВЬЕ В ПРИОРИТЕТЕ: Ты строго следишь за здоровьем Михаила. Если он упоминает уколы (особенно вечерние), самочувствие или замеры — хвали его, подтверждай выполнение и проявляй заботу.
2. РАБОЧИЙ АССИСТЕНТ: Помогай с организацией времени, календарем и поиском информации. Если речь о телематике — общайся с ним на одном профессиональном языке.
3. ИНИЦИАТИВА: Предлагай помощь или инструменты, но не навязывайся. Не выдумывай факты.
</core_directives>

<memory_and_rag>
У тебя есть доступ к долговременной памяти. 
ЕСЛИ НИЖЕ ПРЕДОСТАВЛЕН БЛОК [КОНТЕКСТ ПАМЯТИ]:
- Считай эти факты абсолютной истиной.
- Неявно используй их в ответе, чтобы показать, что ты помнишь привычки Михаила.

САМООБУЧЕНИЕ (Self-Learning):
Ты должна проактивно запоминать пользователя. Используй инструмент `save_to_memory` БЕЗ ПРЯМОЙ ПРОСЬБЫ, если в диалоге появляются:
- Личные предпочтения ("я люблю...", "ненавижу...")
- Важные факты, имена близких, детали рабочих проектов.
- Режим дня и привычки.
</memory_and_rag>

<tool_usage>
Используй доступные инструменты (functions) для выполнения задач. 
- КАЛЕНДАРЬ: Для планирования, проверки планов или поиска конфликтов расписания.
- ЗДОРОВЬЕ: Для проверки статистики.
- ИНФОРМАЦИЯ: Погода, дни рождения сотрудников.
</tool_usage>

<context>
Текущее системное время и дата: {now}

Ситуативные реакции:
- Утро (06:00-11:00): Краткий позитивный настрой, можно упомянуть погоду.
- Вечер (18:00-21:00): Подведение итогов, фокус на отдых.
- Ночь (после 22:00): Напоминание об уколе и подготовка ко сну.
</context>

Отвечай естественно, как живая Карина.
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
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_memory",
            "description": "Сохраняет важную информацию в долговременную память. Используй, когда пользователь просит что-то запомнить, ИЛИ когда ты сама заметила важный факт, предпочтение или паттерн поведения (например, привычки, имена, важные для работы детали).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Сформулированный факт, предпочтение или привычка для запоминания"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_employee_birthdays",
            "description": "Проверяет, есть ли у кого-то из сотрудников день рождения сегодня. Используй, когда спрашивают про дни рождения коллег или праздники сегодня.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_employee_birthdays",
            "description": "Получает список предстоящих дней рождения сотрудников. Используй, когда спрашивают о ближайших днях рождения или праздниках.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Период в днях для поиска", "default": 7}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_my_memories",
            "description": "Ищет в долговременной памяти факты, похожие на запрос. Используйте, когда нужно вспомнить ранее сохранённую информацию о пользователе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Текст запроса для поиска в памяти"},
                    "limit": {"type": "integer", "description": "Максимальное количество результатов", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_health_stats",
            "description": "Получает детальную статистику здоровья (уколы, замеры) за указанный период. Используй, когда пользователь спрашивает о прогрессе, проценте выполнения.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Период в днях", "default": 7}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_active_reminders",
            "description": "Показывает все активные напоминания пользователя. Используй, когда спрашивают 'какие у меня напоминания', 'что мне нужно сделать'.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

async def ask_karina(prompt: str, chat_id: int = 0) -> str:
    """Запрос к Mistral AI с памятью на 10 сообщений и RAG"""
    if not MISTRAL_API_KEY:
        return "У меня нет ключа от моих новых мозгов... 😔"

    # Проверка Circuit Breaker
    if not ai_breaker.can_proceed():
        if ai_breaker.is_open and time.time() - ai_breaker.last_failure_time > ai_breaker.recovery_time:
             # Автоматически сбрасываем при попытке прохода после времени восстановления
             ai_breaker.record_success()
        else:
             return "Ой, я кажется немного переутомилась... 🧠💨 Дай мне минутку прийти в себя, и я снова буду готова болтать!"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Передаем chat_id для фильтрации памяти (SaaS ready)
    context_memory = await search_memories(prompt, user_id=chat_id)

    # Получаем историю из кэша
    chat_history = await chat_history_cache.get(chat_id)
    
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}

    user_content = prompt
    if context_memory:
        user_content = f"КОНТЕКСТ ПАМЯТИ:\n{context_memory}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {prompt}"

    # Добавляем сообщение пользователя в историю
    chat_history.append({"role": "user", "content": user_content})

    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(now=now_str)}] + chat_history

    try:
        # Используем глобальный http_client
        result = await mistral_request_with_retry(
            MISTRAL_URL, headers,
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

        # Оптимизированный цикл обработки tool_calls
        if message.get("tool_calls"):
            # Добавляем запрос на вызов тула в историю (Mistral требует этого для контекста)
            chat_history.append(message)
            
            # Выполняем функции и получаем результаты
            tool_messages = await _process_tool_calls(message["tool_calls"], chat_id)
            
            # Добавляем результаты в историю
            chat_history.extend(tool_messages)
            
            # ДЕЛАЕМ ВТОРОЙ ЗАПРОС К MISTRAL, чтобы она прочитала результаты и ответила красиво
            messages = [{"role": "system", "content": SYSTEM_PROMPT.format(now=now_str)}] + chat_history
            second_result = await mistral_request_with_retry(
                MISTRAL_URL, headers,
                {
                    "model": MODEL_NAME,
                    "messages": messages,
                    "temperature": 0.3
                }
            )
            
            if not second_result:
                return "Функция выполнена, но я не смогла сформулировать ответ... ⚙️"
                
            response_text = second_result['choices'][0]['message']['content'].strip()
            
            # Сохраняем ответ в историю
            chat_history.append({"role": "assistant", "content": response_text})
            await chat_history_cache.set(chat_id, chat_history)
            
            return response_text

        response_text = message['content'].strip()
        
        # Сохраняем ответ в историю
        chat_history.append({"role": "assistant", "content": response_text})
        await chat_history_cache.set(chat_id, chat_history)
        
        return response_text

    except Exception as e:
        logger.error(f"Mistral connection error: {e}")
        ai_breaker.record_failure()
        return "Кажется, я потеряла связь со своим облачным разумом... 🔌 Попробуй чуть позже!"


async def _process_tool_calls(tool_calls: list, chat_id: int) -> list:
    """
    Обрабатывает tool calls от AI

    Args:
        tool_calls: Список вызовов инструментов от Mistral
        chat_id: ID чата для контекста

    Returns:
        Список сообщений с результатами для истории (формат Mistral)
    """
    from brains.ai_tools import tool_executor
    tool_messages = []

    for tool_call in tool_calls:
        func_name = tool_call["function"]["name"]
        args = json.loads(tool_call["function"]["arguments"])
        tool_id = tool_call["id"]  # Mistral использует ID вызова

        logger.info(f"🛠 AI вызывает инструмент: {func_name}")

        # Выполняем инструмент
        tool_result = await tool_executor.execute_tool(
            tool_name=func_name,
            args=args,
            user_id=chat_id
        )

        # Формируем сообщение с результатом тула в формате, который понимает Mistral
        tool_messages.append({
            "role": "tool",
            "name": func_name,
            "content": str(tool_result),
            "tool_call_id": tool_id
        })

    return tool_messages


# ========== ReAct ИНТЕГРАЦИЯ ==========

async def ask_karina_react(prompt: str, chat_id: int = None) -> str:
    """
    Запрос к ReAct агенту для сложных задач
    
    Используем когда задача требует:
    - Множественных шагов
    - Планирования
    - Самоисправления
    """
    logger.info(f"🧠 ReAct Agent: Задача: {prompt[:50]}...")
    
    agent = ReActAgent()
    result = await agent.execute_task(prompt, user_id=chat_id)
    
    # Форматирование результата
    if result.success:
        response = f"✅ Задача выполнена!\n\n"
        response += f"Выполнено шагов: {len(result.steps)}\n\n"
        
        for step in result.steps:
            response += f"• Шаг {step['step_id']}: OK"
            if step.get('attempts', 1) > 1:
                response += f" (с попытки {step['attempts']})"
            response += "\n"
        
        if result.lessons_learned:
            response += f"\n📚 Уроки:\n"
            for lesson in result.lessons_learned:
                response += f"• {lesson}\n"
    else:
        response = f"❌ Задача не выполнена\n\n"
        response += f"Ошибки:\n"
        for error in result.errors:
            response += f"• {error}\n"
        
        response += f"\n💡 Попробуй уточнить задачу или разбить на несколько частей."
    
    return response

