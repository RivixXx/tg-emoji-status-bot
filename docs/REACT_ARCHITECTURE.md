# 🧠 ReAct Agent Architecture — Karina AI v5.0

**Версия:** 5.0.0  
**Дата:** 28 февраля 2026 г.  
**Статус:** 🚀 В разработке

---

## 📋 Обзор

**ReAct (Reason + Act)** — это архитектура автономных агентов, которая комбинирует:

- **Reasoning** (Логическое рассуждение)
- **Acting** (Выполнение действий)

В отличие от традиционного подхода, ReAct агент **не следует жёсткой логике**, а:
1. Анализирует задачу
2. Составляет план
3. Выбирает инструменты динамически
4. Выполняет действия
5. Оценивает результат
6. Корректирует стратегию при ошибках
7. Повторяет пока задача не решена

---

## 🔄 Базовый цикл работы (Agent Loop)

```
┌─────────────────────────────────────────────────────────┐
│                   1. Получить задачу                    │
│         "Создай Telegram-бота для продажи VPN"          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              2. Проанализировать (Reason)               │
│  LLM анализирует задачу, определяет контекст и цели    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              3. Составить план (Planner)                │
│  Разбивка на подзадачи:                                │
│  1. Создать структуру проекта                          │
│  2. Написать основной файл                             │
│  3. Подключить API                                     │
│  4. Протестировать                                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│           4. Выбрать инструмент (Tool Selector)         │
│  LLM выбирает: write_file, run_command, api_call...    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              5. Выполнить действие (Act)                │
│  Python функция: open(), subprocess, requests...       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              6. Получить результат                      │
│  Успех → Данные / Ошибка → Исключение                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│           7. Оценить результат (Feedback)               │
│  ✅ Успех → Следующий шаг                               │
│  ❌ Ошибка → Анализ → Корректировка → Retry            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │  8. Повторить  │◄────────────────┐
            │  или Завершить │                 │
            └────────────────┘                 │
                     │                         │
                     ▼                         │
            [Задача решена]                    │
                     │                         │
                     └─────────────────────────┘
```

---

## ⚙️ Архитектурные блоки

### 1️⃣ LLM (Мозг)

**Назначение:** Reasoning, планирование, принятие решений

```python
# brains/llm_engine.py

class LLMEngine:
    """
    LLM выполняет ТОЛЬКО принятие решений.
    НЕ выполняет действия напрямую.
    """
    
    async def reason(self, context: str, task: str) -> dict:
        """
        Анализирует задачу и принимает решение
        """
        prompt = f"""
Контекст: {context}

Задача: {task}

Проанализируй задачу и выбери следующее действие:

Доступные инструменты:
1. write_file — Создать файл
2. read_file — Прочитать файл
3. run_command — Выполнить команду
4. api_call — Вызвать API
5. search_web — Поиск в интернете

Ответь в формате JSON:
{{
  "reasoning": "Твои размышления...",
  "action": "название инструмента",
  "parameters": {{...}}
}}
"""
        
        response = await mistral_chat(prompt)
        return json.loads(response)
```

**Что делает LLM:**
- ✅ Анализирует контекст
- ✅ Выбирает инструмент
- ✅ Формирует параметры
- ✅ Оценивает результат

**Что НЕ делает LLM:**
- ❌ Не выполняет действия напрямую
- ❌ Не имеет доступа к файловой системе
- ❌ Не вызывает API напрямую

---

### 2️⃣ Planner (Планировщик)

**Назначение:** Разбивка сложных задач на подзадачи

```python
# brains/planner.py

class TaskPlanner:
    """
    Разбивает сложные задачи на последовательные шаги
    """
    
    async def create_plan(self, task: str, context: dict = None) -> list:
        """
        Создаёт план выполнения задачи
        """
        prompt = f"""
Задача: {task}

Контекст: {context or 'Нет дополнительного контекста'}

Разбей задачу на последовательные выполнимые шаги.

Каждый шаг должен:
- Быть атомарным (одно действие)
- Иметь чёткий критерий успеха
- Использовать доступные инструменты

Доступные инструменты:
- write_file, read_file, run_command, api_call, search_web

Формат ответа (JSON):
{{
  "steps": [
    {{
      "id": 1,
      "description": "Создать структуру проекта",
      "tool": "write_file",
      "expected_result": "Файлы созданы"
    }},
    {{
      "id": 2,
      "description": "Написать основной файл",
      "tool": "write_file",
      "expected_result": "Код написан"
    }}
  ]
}}
"""
        
        response = await mistral_chat(prompt)
        plan_data = json.loads(response)
        
        return [Step(**step) for step in plan_data['steps']]
    
    async def adjust_plan(self, plan: list, error: str) -> list:
        """
        Корректирует план при ошибке
        """
        prompt = f"""
Текущий план: {plan}

Произошла ошибка: {error}

Скорректируй план чтобы обойти ошибку:
"""
        
        response = await mistral_chat(prompt)
        return self.parse_plan(response)
```

**Пример плана:**

Задача: *"Создай Telegram-бота"*

```json
{
  "steps": [
    {
      "id": 1,
      "description": "Создать структуру проекта",
      "tool": "write_file",
      "parameters": {
        "path": "bot/__init__.py",
        "content": ""
      }
    },
    {
      "id": 2,
      "description": "Написать основной файл",
      "tool": "write_file",
      "parameters": {
        "path": "bot/main.py",
        "content": "..."
      }
    },
    {
      "id": 3,
      "description": "Установить зависимости",
      "tool": "run_command",
      "parameters": {
        "command": "pip install telethon"
      }
    },
    {
      "id": 4,
      "description": "Протестировать запуск",
      "tool": "run_command",
      "parameters": {
        "command": "python bot/main.py"
      }
    }
  ]
}
```

---

### 3️⃣ Tools (Инструменты)

**Назначение:** Реальные действия в окружающем мире

```python
# brains/tools/__init__.py

class ToolRegistry:
    """Реестр доступных инструментов"""
    
    def __init__(self):
        self.tools = {
            "write_file": self.write_file,
            "read_file": self.read_file,
            "run_command": self.run_command,
            "api_call": self.api_call,
            "search_web": self.search_web,
            "database_query": self.database_query,
        }
    
    async def execute(self, tool_name: str, **kwargs):
        """Выполняет инструмент"""
        if tool_name not in self.tools:
            raise ValueError(f"Неизвестный инструмент: {tool_name}")
        
        return await self.tools[tool_name](**kwargs)
    
    async def write_file(self, path: str, content: str) -> dict:
        """Создаёт файл"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Файл создан: {path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def read_file(self, path: str) -> dict:
        """Читает файл"""
        try:
            with open(path, 'r') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content
            }
        except Exception as e:
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
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "returncode": process.returncode
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def api_call(self, url: str, method: str = "GET", **kwargs) -> dict:
        """Вызывает HTTP API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, **kwargs) as response:
                    data = await response.json()
                    
                    return {
                        "success": response.status == 200,
                        "data": data,
                        "status_code": response.status
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_web(self, query: str) -> dict:
        """Поиск в интернете"""
        # Реализация через поисковый API
        pass
    
    async def database_query(self, query: str, params: dict = None) -> dict:
        """SQL запрос к базе данных"""
        try:
            result = await supabase.execute(query, params)
            
            return {
                "success": True,
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
```

**Доступные инструменты:**

| Инструмент | Описание | Пример |
|------------|----------|--------|
| `write_file` | Создать файл | `write_file("test.py", "print('Hi')")` |
| `read_file` | Прочитать файл | `read_file("config.json")` |
| `run_command` | Выполнить команду | `run_command("pip install requests")` |
| `api_call` | HTTP запрос | `api_call("https://api.example.com/data")` |
| `search_web` | Поиск в интернете | `search_web("Python async tutorial")` |
| `database_query` | SQL запрос | `database_query("SELECT * FROM users")` |

---

### 4️⃣ Memory (Память)

**Назначение:** Хранение контекста и опыта

```python
# brains/memory.py

class AgentMemory:
    """
    Двухуровневая память агента
    """
    
    def __init__(self):
        self.short_term = []  # Контекст текущей сессии
        self.long_term_db = "agent_experiences"  # Таблица в Supabase
    
    # ========== SHORT-TERM MEMORY ==========
    
    def add_to_short_term(self, entry: dict):
        """Добавляет запись в краткосрочную память"""
        self.short_term.append({
            "timestamp": datetime.now(),
            **entry
        })
        
        # Ограничиваем размер (последние 50 записей)
        if len(self.short_term) > 50:
            self.short_term = self.short_term[-50:]
    
    def get_short_term_context(self) -> str:
        """Возвращает контекст текущей сессии"""
        if not self.short_term:
            return "Нет предыдущего контекста"
        
        context = "История сессии:\n"
        for entry in self.short_term[-10:]:  # Последние 10 записей
            context += f"- {entry['action']}: {entry.get('result', 'Нет результата')}\n"
        
        return context
    
    def clear_short_term(self):
        """Очищает краткосрочную память"""
        self.short_term = []
    
    # ========== LONG-TERM MEMORY ==========
    
    async def store_experience(self, task: str, plan: list, result: dict):
        """Сохраняет опыт выполнения задачи"""
        
        experience = {
            "task": task,
            "plan": plan,
            "success": result.get("success"),
            "errors": result.get("errors", []),
            "lessons_learned": result.get("recommendations", []),
            "timestamp": datetime.now().isoformat()
        }
        
        # Генерация эмбеддинга для поиска
        embedding = await mistral_embeddings(task)
        experience["embedding"] = embedding
        
        # Сохранение в Supabase
        await supabase.table(self.long_term_db).insert(experience)
    
    async def retrieve_similar_tasks(self, task: str, limit: int = 5) -> list:
        """Ищет похожие задачи в прошлом (векторный поиск)"""
        
        embedding = await mistral_embeddings(task)
        
        results = await supabase.rpc("match_agent_experiences", {
            "query_embedding": embedding,
            "match_count": limit
        })
        
        return results
    
    async def get_lessons_learned(self, task: str) -> list:
        """Извлекает уроки из похожих задач"""
        similar = await self.retrieve_similar_tasks(task)
        
        lessons = []
        for exp in similar:
            if exp.get("lessons_learned"):
                lessons.extend(exp["lessons_learned"])
        
        return list(set(lessons))  # Уникальные уроки
    
    async def store_error_pattern(self, error: str, solution: str):
        """Сохраняет паттерн ошибки и решения"""
        
        pattern = {
            "error_pattern": error,
            "solution": solution,
            "timestamp": datetime.now().isoformat()
        }
        
        await supabase.table("agent_error_patterns").insert(pattern)
    
    async def get_solution_for_error(self, error: str) -> str:
        """Ищет решение для известной ошибки"""
        
        # Поиск по подобию ошибок
        results = await supabase.table("agent_error_patterns")\
            .select("solution")\
            .eq("error_pattern", error)\
            .execute()
        
        if results.data:
            return results.data[0]["solution"]
        
        return None
```

**Типы памяти:**

| Тип | Хранение | Размер | Время жизни |
|-----|----------|--------|-------------|
| **Short-term** | В памяти (list) | 50 записей | До перезапуска |
| **Long-term** | Supabase (БД) | Неограничен | Постоянно |

---

### 5️⃣ Feedback Loop (Самоисправление)

**Назначение:** Анализ результатов и корректировка стратегии

```python
# brains/feedback.py

class FeedbackLoop:
    """
    Анализирует результаты и корректирует стратегию
    """
    
    async def analyze_result(self, expected: str, actual: dict) -> dict:
        """
        Оценивает результат выполнения
        """
        prompt = f"""
Оцени результат выполнения:

Ожидалось: {expected}
Получено: {actual}

Вопросы:
1. Результат соответствует ожиданиям?
2. Есть ли ошибки?
3. Нужно ли скорректировать стратегию?

Ответь в формате JSON:
{{
  "success": true/false,
  "issues": ["Проблема 1", "Проблема 2"],
  "recommendations": ["Рекомендация 1", "Рекомендация 2"],
  "needs_retry": true/false,
  "alternative_approach": "Описание альтернативного подхода"
}}
"""
        
        response = await mistral_chat(prompt)
        return json.loads(response)
    
    async def adjust_strategy(self, issue: str, context: dict) -> str:
        """
        Предлагает альтернативный подход при ошибке
        """
        prompt = f"""
Произошла проблема: {issue}

Контекст: {context}

Предложи альтернативный подход для решения задачи:
"""
        
        return await mistral_chat(prompt)
    
    async def decide_retry(self, error: str, attempts: int) -> bool:
        """
        Решает стоит ли повторять попытку
        """
        if attempts >= 3:  # Максимум 3 попытки
            return False
        
        # Анализ типа ошибки
        retryable_errors = [
            "timeout",
            "connection",
            "rate limit",
            "temporary"
        ]
        
        for retryable in retryable_errors:
            if retryable in error.lower():
                return True
        
        return False
    
    async def learn_from_feedback(self, feedback: dict):
        """
        Сохраняет уроки для будущего использования
        """
        if feedback.get("success"):
            # Успех — запомнить успешную стратегию
            await memory.store_success_pattern(feedback)
        else:
            # Ошибка — запомнить проблему и решение
            await memory.store_error_pattern(
                feedback.get("issues"),
                feedback.get("recommendations")
            )
```

**Цикл самоисправления:**

```
1. Выполнить действие
   ↓
2. Получить результат (Успех/Ошибка)
   ↓
3. Анализ через LLM
   ↓
4. Если ошибка:
   ├─ Определить тип ошибки
   ├─ Решить: Retry или Adjust
   ├─ Если Retry → Повторить (макс. 3 раза)
   └─ Если Adjust → Новый план
   ↓
5. Сохранить урок в память
```

---

## 🎯 Полный цикл ReAct агента

```python
# brains/react_agent.py

class ReActAgent:
    """
    Автономный агент с ReAct архитектурой
    """
    
    def __init__(self):
        self.llm = LLMEngine()
        self.planner = TaskPlanner()
        self.tools = ToolRegistry()
        self.memory = AgentMemory()
        self.feedback = FeedbackLoop()
    
    async def execute_task(self, task: str, user_id: int = None):
        """
        Выполняет задачу используя ReAct подход
        """
        # 1. Загрузить контекст из памяти
        similar_tasks = await self.memory.retrieve_similar_tasks(task)
        lessons = await self.memory.get_lessons_learned(task)
        
        context = {
            "user_id": user_id,
            "similar_tasks": similar_tasks,
            "lessons_learned": lessons
        }
        
        # 2. Создать план
        plan = await self.planner.create_plan(task, context)
        
        # 3. Выполнить план по шагам
        results = []
        attempts = 0
        max_attempts = 3
        
        for step in plan:
            success = False
            
            while not success and attempts < max_attempts:
                attempts += 1
                
                # 4. Выбрать инструмент
                tool_name = step.tool
                parameters = step.parameters
                
                # 5. Выполнить действие
                result = await self.tools.execute(tool_name, **parameters)
                
                # 6. Оценить результат
                feedback = await self.feedback.analyze_result(
                    step.expected_result,
                    result
                )
                
                if feedback["success"]:
                    success = True
                    results.append({
                        "step": step.id,
                        "success": True,
                        "result": result
                    })
                else:
                    # 7. Самоисправление
                    if await self.feedback.decide_retry(result.get("error"), attempts):
                        # Попытка повторить
                        continue
                    else:
                        # Корректировка стратегии
                        new_strategy = await self.feedback.adjust_strategy(
                            result.get("error"),
                            context
                        )
                        
                        # Обновить шаг
                        step = self.parse_step(new_strategy)
                        attempts = 0  # Сброс попыток для нового подхода
            
            if not success:
                # Задача не может быть выполнена
                results.append({
                    "step": step.id,
                    "success": False,
                    "error": "Превышено количество попыток"
                })
                break
        
        # 8. Сохранить опыт
        await self.memory.store_experience(
            task,
            plan,
            {"success": all(r.get("success") for r in results), "results": results}
        )
        
        return results
```

---

## 📊 Сравнение архитектур

### Традиционный подход (Karina AI v4.0)

```
Пользователь → Handler → Brains Module → API → Результат
                                      ↓
                                  Ошибка → Возврат пользователю
```

**Проблемы:**
- ❌ Одна попытка
- ❌ Нет самоисправления
- ❌ Жёсткая логика
- ❌ Нет обучения

### ReAct подход (Karina AI v5.0)

```
Пользователь → ReAct Agent → Plan → Execute → Feedback
                                   ↓           │
                                   │           ↓
                                   └─────── Adjust/Retry
                                           ↓
                                       Сохранить опыт
```

**Преимущества:**
- ✅ Множественные попытки
- ✅ Самоисправление
- ✅ Динамическое планирование
- ✅ Обучение на опыте

---

## 🚀 Примеры использования

### Пример 1: Создание файла

**Задача:** *"Создай файл test.py с функцией hello()"*

```python
agent = ReActAgent()
result = await agent.execute_task("Создай файл test.py с функцией hello()")

# План:
# 1. write_file("test.py", "def hello():\n    print('Hello')")

# Результат:
[{"step": 1, "success": True, "result": {"message": "Файл создан"}}]
```

### Пример 2: Установка зависимости

**Задача:** *"Установи библиотеку requests"*

```python
result = await agent.execute_task("Установи requests")

# План:
# 1. run_command("pip install requests")

# Если ошибка (нет прав):
# 2. run_command("sudo pip install requests")

# Если ошибка (нет pip):
# 3. run_command("apt-get install python3-pip")
# 4. run_command("pip install requests")
```

### Пример 3: Создание VPN магазина

**Задача:** *"Создай VPN-магазин для монетизации бота"*

```python
result = await agent.execute_task("""
Создай VPN-магазин для монетизации Telegram-бота:
1. Создай таблицы БД
2. Напиши UI для магазина
3. Интегрируй Marzban API
4. Протестируй
""")

# План (автоматически сгенерированный):
# 1. write_file("docs/init_vpn_shop.sql", "...")
# 2. database_query("CREATE TABLE ...")
# 3. write_file("brains/vpn_ui.py", "...")
# 4. write_file("main.py", "...")  # Обновить main.py
# 5. run_command("git add . && git commit -m '...'")
# 6. api_call("https://marzban/api/user", method="POST", ...)
# 7. run_command("python -m py_compile main.py")
```

---

## 📋 Миграция с v4.0 на v5.0

### Шаг 1: Добавить новые модули

```
brains/
├── react_agent.py         # Новый: ReAct агент
├── llm_engine.py          # Новый: LLM движок
├── planner.py             # Новый: Планировщик
├── feedback.py            # Новый: Feedback loop
├── memory.py              # Обновить: AgentMemory
└── tools/
    ├── __init__.py        # Новый: Реестр инструментов
    ├── file_tools.py      # write_file, read_file
    ├── shell_tools.py     # run_command
    ├── api_tools.py       # api_call
    └── web_tools.py       # search_web
```

### Шаг 2: Обновить ask_karina

```python
# brains/ai.py

async def ask_karina(prompt: str, chat_id: int) -> str:
    # Старый подход (сохранить для обратной совместимости)
    ...
    
    # Новый ReAct подход (для сложных задач)
    if is_complex_task(prompt):
        agent = ReActAgent()
        result = await agent.execute_task(prompt, user_id=chat_id)
        return format_agent_result(result)
    
    # Простой запрос к AI
    return await mistral_chat(prompt)
```

### Шаг 3: Интегрировать в skills/

```python
# skills/__init__.py

@client.on(events.NewMessage(pattern='/agent'))
async def agent_handler(event):
    """Выполнить задачу через ReAct агента"""
    task = event.text.replace('/agent', '').strip()
    
    await event.respond("🤖 Анализирую задачу...")
    
    agent = ReActAgent()
    result = await agent.execute_task(task, user_id=event.chat_id)
    
    await event.respond(format_agent_result(result))
```

---

## 📈 Метрики и мониторинг

### Метрики агента

```python
AGENT_METRICS = {
    "tasks_completed": 0,
    "tasks_failed": 0,
    "average_steps_per_task": 0,
    "average_attempts_per_step": 0,
    "success_rate": 0.0,
    "tools_usage": {
        "write_file": 0,
        "read_file": 0,
        "run_command": 0,
        "api_call": 0
    }
}
```

### API endpoints

```python
@app.route('/api/agent/status')
async def agent_status():
    """Статус ReAct агента"""
    return jsonify({
        "tasks_completed": AGENT_METRICS["tasks_completed"],
        "success_rate": AGENT_METRICS["success_rate"],
        "average_steps": AGENT_METRICS["average_steps_per_task"]
    })

@app.route('/api/agent/memory')
async def agent_memory():
    """Просмотр памяти агента"""
    return jsonify({
        "short_term_size": len(agent.memory.short_term),
        "long_term_size": await count_db_records("agent_experiences")
    })
```

---

## 🎯 Roadmap внедрения

### P0 (Критичные)

- [ ] Создать `brains/react_agent.py`
- [ ] Создать `brains/llm_engine.py`
- [ ] Создать `brains/planner.py`
- [ ] Создать `brains/feedback.py`
- [ ] Создать `brains/memory.py` (обновить)
- [ ] Создать `brains/tools/`

### P1 (Важные)

- [ ] Обновить `ask_karina()` для поддержки ReAct
- [ ] Добавить команду `/agent`
- [ ] Интеграция с VPN Shop
- [ ] Тесты для ReAct агента

### P2 (Долгосрочные)

- [ ] Multi-agent система
- [ ] Human-in-the-loop
- [ ] Auto-documentation
- [ ] Web UI для мониторинга

---

## 📞 Поддержка

- **Документация:** `docs/REACT_ARCHITECTURE.md`
- **Примеры:** `examples/react_*.py`
- **Тесты:** `tests/test_react_agent.py`

---

**Последнее обновление:** 28 февраля 2026 г.
