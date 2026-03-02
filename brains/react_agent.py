"""
ReAct Agent — Karina AI v5.0
Автономный агент с архитектурой Reason + Act
"""
import json
import asyncio
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

from brains.config import MISTRAL_API_KEY

logger = logging.getLogger(__name__)

# Глобальный HTTP клиент
http_client = httpx.AsyncClient(timeout=60.0)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_EMBED_URL = "https://api.mistral.ai/v1/embeddings"
MODEL_NAME = "mistral-small-latest"


async def mistral_chat(prompt: str) -> str:
    """Запрос к Mistral AI"""
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    try:
        result = await http_client.post(MISTRAL_URL, headers=headers, json=payload)
        result.raise_for_status()
        data = result.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Mistral chat error: {e}")
        return ""


@dataclass
class Step:
    """Шаг плана"""
    id: int
    description: str
    tool: str
    parameters: Dict[str, Any]
    expected_result: str


@dataclass
class TaskResult:
    """Результат выполнения задачи"""
    task: str
    success: bool
    steps: List[Dict]
    errors: List[str]
    lessons_learned: List[str]


class LLMEngine:
    """
    LLM движок для принятия решений
    """
    
    async def reason(self, context: str, task: str) -> dict:
        """
        Анализирует задачу и принимает решение
        """
        prompt = f"""
Контекст: {context}

Задача: {task}

Проанализируй задачу и выбери следующее действие.

Доступные инструменты:
1. write_file — Создать файл
2. read_file — Прочитать файл  
3. run_command — Выполнить команду
4. api_call — Вызвать API
5. database_query — SQL запрос

Ответь в формате JSON:
{{
  "reasoning": "Твои размышления...",
  "action": "название инструмента",
  "parameters": {{...}},
  "expected_result": "Описание ожидаемого результата"
}}
"""
        
        try:
            response = await mistral_chat(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"LLM reasoning error: {e}")
            return {
                "reasoning": "Ошибка анализа",
                "action": None,
                "parameters": {},
                "expected_result": ""
            }


class TaskPlanner:
    """
    Планировщик задач — разбивает на подзадачи
    """
    
    async def create_plan(self, task: str, context: dict = None) -> List[Step]:
        """
        Создаёт план выполнения задачи
        """
        prompt = f"""
Задача: {task}

Контекст: {context or 'Нет дополнительного контекста'}

Разбей задачу на последовательные выполнимые шаги.

ДОСТУПНЫЕ ИНСТРУМЕНТЫ (использовать ТОЛЬКО эти названия):
- write_file (параметры: path, content) — Создать/записать файл
- read_file (параметры: path) — Прочитать файл
- run_command (параметры: command, timeout) — Выполнить команду shell
- api_call (параметры: url, method) — HTTP запрос (ТОЛЬКО реальные URL!)
- database_query (параметры: query, params) — SQL запрос к Supabase
- get_calendar (параметры: date) — Проверить календарь на дату (формат: YYYY-MM-DD)

Важно:
- Для get_calendar используй ТОЛЬКО реальные даты
- Для api_call используй ТОЛЬКО существующие URL
- Не выдумывай несуществующие API

Ответь ТОЛЬКО JSON массивом шагов в формате:
[
  {{
    "id": 1,
    "description": "Описание шага",
    "tool": "get_calendar",
    "parameters": {{"date": "2026-02-28"}},
    "expected_result": "События календаря"
  }}
]

Никакого дополнительного текста, только JSON!
"""
        
        try:
            response = await mistral_chat(prompt)
            
            # Очищаем ответ от markdown и лишнего текста
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # Пытаемся распарсить как массив
            try:
                steps_data = json.loads(response)
            except:
                # Если не массив, ищем JSON в тексте
                import re
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    steps_data = json.loads(json_match.group())
                else:
                    logger.error(f"Failed to parse plan: {response[:200]}")
                    return []
            
            # Фильтруем только допустимые инструменты
            valid_tools = {"write_file", "read_file", "run_command", "api_call", "database_query", "get_calendar"}
            
            return [
                Step(
                    id=step["id"],
                    description=step["description"],
                    tool=step["tool"],
                    parameters=step["parameters"],
                    expected_result=step["expected_result"]
                )
                for step in steps_data
                if step.get("tool") in valid_tools
            ]
        except Exception as e:
            logger.error(f"Planner error: {e}")
            return []
    
    async def adjust_plan(self, plan: List[Step], error: str) -> List[Step]:
        """
        Корректирует план при ошибке
        """
        prompt = f"""
Текущий план:
{[asdict(step) for step in plan]}

Произошла ошибка: {error}

Скорректируй план чтобы обойти ошибку. Верни новый план в том же формате JSON.
"""
        
        try:
            response = await mistral_chat(prompt)
            plan_data = json.loads(response)
            
            return [
                Step(
                    id=step["id"],
                    description=step["description"],
                    tool=step["tool"],
                    parameters=step["parameters"],
                    expected_result=step["expected_result"]
                )
                for step in plan_data.get("steps", [])
            ]
        except Exception as e:
            logger.error(f"Plan adjustment error: {e}")
            return plan


class ToolRegistry:
    """
    Реестр инструментов
    """
    
    def __init__(self):
        self.tools = {
            "write_file": self.write_file,
            "read_file": self.read_file,
            "run_command": self.run_command,
            "api_call": self.api_call,
            "database_query": self.database_query,
            "get_calendar": self.get_calendar,
        }
    
    async def execute(self, tool_name: str, **kwargs) -> dict:
        """Выполняет инструмент"""
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"Неизвестный инструмент: {tool_name}"
            }
        
        try:
            return await self.tools[tool_name](**kwargs)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def write_file(self, path: str, content: str) -> dict:
        """Создаёт файл"""
        try:
            import os
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"✅ Файл создан: {path}")
            return {
                "success": True,
                "message": f"Файл создан: {path}"
            }
        except Exception as e:
            logger.error(f"write_file error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def read_file(self, path: str) -> dict:
        """Читает файл"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content
            }
        except Exception as e:
            logger.error(f"read_file error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def run_command(self, command: str, timeout: int = 60) -> dict:
        """Выполняет команду в shell"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode('utf-8'),
                "stderr": stderr.decode('utf-8'),
                "returncode": process.returncode
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {timeout}s"
            }
        except Exception as e:
            logger.error(f"run_command error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def api_call(self, url: str, method: str = "GET", **kwargs) -> dict:
        """Вызывает HTTP API"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, **kwargs) as response:
                    data = await response.json()
                    
                    return {
                        "success": response.status == 200,
                        "data": data,
                        "status_code": response.status
                    }
        except Exception as e:
            logger.error(f"api_call error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def database_query(self, query: str, params: dict = None) -> dict:
        """SQL запрос к базе данных Supabase"""
        try:
            from brains.mcp_vpn_shop import supabase
            
            if params:
                result = await supabase.execute(query, params)
            else:
                result = await supabase.execute(query)
            
            return {
                "success": True,
                "data": result
            }
        except Exception as e:
            logger.error(f"database_query error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_calendar(self, date: str) -> dict:
        """Проверка календаря на дату"""
        try:
            from brains.calendar import get_upcoming_events
            
            # Получаем события
            events = await get_upcoming_events(max_results=10)
            
            # Фильтруем по дате если указано
            if date:
                # Простая фильтрация по строке
                filtered = [e for e in events.split('\n') if date in e] if events else []
                events = '\n'.join(filtered)
            
            return {
                "success": True,
                "data": events or "Событий нет"
            }
        except Exception as e:
            logger.error(f"get_calendar error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class FeedbackLoop:
    """
    Анализ результатов и самоисправление
    """
    
    async def analyze_result(self, expected: str, actual: dict) -> dict:
        """
        Оценивает результат выполнения
        """
        if not actual:
            return {
                "success": False,
                "issues": ["Нет результата"],
                "recommendations": ["Повторить попытку"],
                "needs_retry": True,
                "alternative_approach": ""
            }
        
        if actual.get("success"):
            return {
                "success": True,
                "issues": [],
                "recommendations": [],
                "needs_retry": False,
                "alternative_approach": ""
            }
        
        # Если ошибка — пытаемся получить JSON от LLM
        error_msg = actual.get("error", "Неизвестная ошибка")
        
        prompt = f"""
Произошла ошибка при выполнении: {error_msg}

Ожидалось: {expected}

Нужно ли повторить попытку или скорректировать стратегию?

Ответь ТОЛЬКО JSON:
{{
  "success": false,
  "issues": ["{error_msg}"],
  "recommendations": ["Попробовать другой подход"],
  "needs_retry": true,
  "alternative_approach": "Описание"
}}
"""
        
        try:
            response = await mistral_chat(prompt)
            
            # Очищаем от markdown
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            return json.loads(response)
        except Exception as e:
            logger.error(f"Feedback analysis error: {e}")
            # Fallback — возвращаем безопасный ответ
            return {
                "success": False,
                "issues": [error_msg],
                "recommendations": ["Повторить"],
                "needs_retry": True,
                "alternative_approach": ""
            }
    
    async def decide_retry(self, error: str, attempts: int) -> bool:
        """
        Решает стоит ли повторять попытку
        """
        # Обработка None
        if not error:
            return True  # Если ошибка неясна, пробуем снова
        
        if attempts >= 3:  # Максимум 3 попытки
            return False
        
        # Анализ типа ошибки
        retryable_errors = [
            "timeout",
            "connection",
            "rate limit",
            "temporary",
            "locked"
        ]
        
        error_lower = error.lower()
        for retryable in retryable_errors:
            if retryable in error_lower:
                return True
        
        return False
    
    async def adjust_strategy(self, issue: str, context: dict) -> str:
        """
        Предлагает альтернативный подход
        """
        if not issue:
            issue = "Неизвестная ошибка"
        
        prompt = f"""
Произошла проблема: {issue}

Контекст: {context}

Предложи альтернативный подход используя ТОЛЬКО эти инструменты:
- write_file (параметры: path, content)
- read_file (параметры: path)
- run_command (параметры: command, timeout)
- api_call (параметры: url, method)
- database_query (параметры: query, params)
- get_calendar (параметры: date)

Ответь ТОЛЬКО JSON:
{{
  "tool": "write_file",
  "parameters": {{"path": "/tmp/test.txt", "content": "Hello"}}
}}
"""
        
        try:
            response = await mistral_chat(prompt)
            
            # Очищаем от markdown
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # Проверяем что инструмент допустимый
            valid_tools = {"write_file", "read_file", "run_command", "api_call", "database_query", "get_calendar"}
            
            try:
                data = json.loads(response)
                if data.get("tool") not in valid_tools:
                    logger.warning(f"Invalid tool in adjustment: {data.get('tool')}")
                    return ""
                return response
            except:
                return ""
        except Exception as e:
            logger.error(f"Strategy adjustment error: {e}")
            return ""


class ReActAgent:
    """
    Автономный агент с ReAct архитектурой
    """
    
    def __init__(self):
        self.llm = LLMEngine()
        self.planner = TaskPlanner()
        self.tools = ToolRegistry()
        self.feedback = FeedbackLoop()
        self.short_term_memory = []
    
    async def execute_task(self, task: str, user_id: int = None) -> TaskResult:
        """
        Выполняет задачу используя ReAct подход
        """
        logger.info(f"🚀 ReAct Agent: Начинаю выполнение задачи: {task}")
        
        # 1. Загрузить контекст из памяти (если есть)
        context = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # 2. Создать план
        logger.info("📋 Создаю план...")
        plan = await self.planner.create_plan(task, context)
        
        if not plan:
            return TaskResult(
                task=task,
                success=False,
                steps=[],
                errors=["Не удалось создать план"],
                lessons_learned=[]
            )
        
        logger.info(f"✅ План создан: {len(plan)} шагов")
        
        # 3. Выполнить план по шагам
        results = []
        errors = []
        strategy_adjustments = 0  # Счётчик корректировок стратегии
        max_adjustments = 5  # Максимум 5 корректировок
        
        for step in plan:
            logger.info(f"🔧 Выполняю шаг {step.id}: {step.description}")

            success = False
            attempts = 0
            max_attempts = 3

            while not success and attempts < max_attempts and strategy_adjustments < max_adjustments:
                # 4. Выполнить действие
                try:
                    result = await self.tools.execute(
                        step.tool,
                        **step.parameters
                    )
                except Exception as e:
                    logger.error(f"Step execution error: {e}")
                    result = {"success": False, "error": str(e)}
                
                # 5. Оценить результат
                feedback = await self.feedback.analyze_result(
                    step.expected_result,
                    result
                )
                
                # Конвертируем "true"/"false" в bool
                success_result = feedback.get("success", False)
                if isinstance(success_result, str):
                    success_result = success_result.lower() == "true"
                
                if success_result:
                    success = True
                    results.append({
                        "step_id": step.id,
                        "success": True,
                        "result": result,
                        "attempts": attempts + 1
                    })
                    logger.info(f"✅ Шаг {step.id} выполнен успешно")
                else:
                    attempts += 1  # Увеличиваем только при ошибке
                    error_msg = result.get("error") if result else "Неизвестная ошибка"
                    logger.warning(f"❌ Шаг {step.id} не выполнен: {error_msg}")
                    
                    # 6. Самоисправление
                    if await self.feedback.decide_retry(error_msg, attempts):
                        logger.info(f"🔄 Попытка {attempts}/{max_attempts}")
                        continue
                    else:
                        # Корректировка стратегии
                        strategy_adjustments += 1
                        if strategy_adjustments >= max_adjustments:
                            logger.error("🚨 Превышено количество корректировок стратегии")
                            errors.append(f"Превышено количество корректировок ({max_adjustments})")
                            break
                        
                        new_strategy = await self.feedback.adjust_strategy(
                            error_msg,
                            context
                        )
                        
                        if new_strategy:
                            logger.info(f"🔄 Стратегия скорректирована (попытка {strategy_adjustments}/{max_adjustments})")
                            # Обновляем шаг
                            try:
                                strategy_data = json.loads(new_strategy)
                                step.tool = strategy_data.get("tool", step.tool)
                                step.parameters = strategy_data.get("parameters", step.parameters)
                            except:
                                pass
                        
                        attempts = 0  # Сброс попыток для нового подхода
            
            if not success:
                errors.append(f"Шаг {step.id} не выполнен после {max_attempts} попыток")
                logger.error(f"❌ Шаг {step.id} провален")
                break
        
        # 7. Сохранить урок в память
        lessons = []
        if errors:
            lessons.append(f"Избегать: {', '.join(errors)}")
        if success:
            lessons.append("Успешная стратегия выполнения")
        
        # 8. Добавить в краткосрочную память
        self.short_term_memory.append({
            "task": task,
            "result": "success" if not errors else "failed",
            "timestamp": datetime.now()
        })
        
        # Ограничиваем размер памяти
        if len(self.short_term_memory) > 50:
            self.short_term_memory = self.short_term_memory[-50:]
        
        return TaskResult(
            task=task,
            success=len(errors) == 0,
            steps=results,
            errors=errors,
            lessons_learned=lessons
        )
    
    def get_memory_context(self) -> str:
        """Возвращает контекст из краткосрочной памяти"""
        if not self.short_term_memory:
            return "Нет предыдущего контекста"
        
        context = "История сессии:\n"
        for entry in self.short_term_memory[-10:]:
            context += f"- {entry['task']}: {entry['result']}\n"
        
        return context
    
    def clear_memory(self):
        """Очищает краткосрочную память"""
        self.short_term_memory = []


# ========== ИНТЕГРАЦИЯ В ASK_KARINA ==========

async def ask_karina_react(prompt: str, chat_id: int = None) -> str:
    """
    Запрос к ReAct агенту
    """
    agent = ReActAgent()
    
    result = await agent.execute_task(prompt, user_id=chat_id)
    
    # Форматирование результата
    if result.success:
        response = "✅ Задача выполнена!\n\n"
        response += f"Выполнено шагов: {len(result.steps)}\n"
        
        for step in result.steps:
            response += f"• Шаг {step['step_id']}: OK"
            if step.get('attempts', 1) > 1:
                response += f" (с попытки {step['attempts']})"
            response += "\n"
    else:
        response = "❌ Задача не выполнена\n\n"
        response += "Ошибки:\n"
        for error in result.errors:
            response += f"• {error}\n"
    
    if result.lessons_learned:
        response += "\n📚 Уроки:\n"
        for lesson in result.lessons_learned:
            response += f"• {lesson}\n"
    
    return response
