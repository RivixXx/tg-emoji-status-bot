# 🏗️ Архитектура Karina AI v4.0

**Версия:** 1.0  
**Дата:** 28 февраля 2026 г.

---

## 📋 Обзор

**Karina AI** — это асинхронный Telegram-бот с микросервисной архитектурой, работающий в едином event loop.

### Ключевые принципы

- ✅ **Асинхронность:** asyncio для всех I/O операций
- ✅ **Модульность:** Разделение на brains/auras/skills/plugins
- ✅ **Отказоустойчивость:** Supervisor pattern, Circuit Breaker, Retry
- ✅ **Масштабируемость:** SaaS-ready (фильтрация по user_id)

---

## 🎯 Компоненты

### 1. Main Loop (`main.py`)

**Точка входа:** `amain()`

```python
async def amain():
    """Главная асинхронная точка входа"""
    
    # 1. Инициализация плагинов
    await plugin_manager.initialize_all()
    
    # 2. Запуск супервизоров
    bot_supervisor = component_supervisor(run_bot_main, "bot")
    user_supervisor = component_supervisor(run_userbot_main, "userbot")
    
    # 3. Системный heartbeat
    system_heartbeat = asyncio.create_task(system_heartbeat())
    
    # 4. Запуск веб-сервера
    await run_web()
```

### 2. Bot Client (Telegram Bot)

**Назначение:** Обработка сообщений от пользователей

```python
bot_client = TelegramClient('karina_bot_session', API_ID, API_HASH)
await bot_client.start(bot_token=KARINA_TOKEN)
```

**Хендлеры:**

| Хендлер | Назначение |
|---------|------------|
| `debug_all_messages` | Логирование всех сообщений |
| `vpn_stranger_interceptor` | Перехват чужих ID (VPN Shop) |
| `vpn_callback_handler` | Inline-кнопки VPN Shop |
| `chat_handler` | Интеллектуальное общение (AI) |

### 3. User Client (Telegram UserBot)

**Назначение:** Смена emoji-статусов, BIO (требует Premium)

```python
user_client = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)
await user_client.connect()
```

**Хендлеры:**

| Хендлер | Назначение |
|---------|------------|
| `discovery_handler` | Детектор ID эмодзи |

### 4. Web Server (Quart + Hypercorn)

**Назначение:** API endpoints для Mini App и мониторинга

```python
app = Quart(__name__)

@app.route('/api/health')
async def health_check():
    return jsonify({"status": "ok", "components": {...}})

@app.route('/api/metrics')
async def metrics_endpoint():
    return jsonify({"ai_responses_total": 100, ...})
```

**Endpoints:**

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/health` | GET | Статус компонентов |
| `/api/metrics` | GET | Метрики AI |
| `/api/status` | GET | Статус Карины |
| `/api/emotion` | GET/POST | Эмоции |
| `/api/plugins` | GET | Список плагинов |
| `/api/calendar` | GET | Календарь |
| `/api/memory/search` | GET | Поиск в памяти |

### 5. Supervisor Pattern

**Назначение:** Автоматический перезапуск упавших компонентов

```python
async def component_supervisor(coro_func, name):
    backoff = 10
    while not SHUTDOWN_EVENT.is_set():
        try:
            await coro_func()
            # Если завершился неожиданно — рестарт
        except Exception as e:
            await record_error(f"{name} crashed: {e}")
            backoff = min(backoff * 2, 300)  # Экспоненциальный рост
            await asyncio.sleep(backoff)
```

**Backoff стратегия:**
```
10s → 20s → 40s → 80s → 160s → 300s (максимум)
```

### 6. Heartbeat System

**Назначение:** Мониторинг состояния компонентов

```python
APP_STATS = {
    "components": {
        "web": {"status": "running", "last_seen": 1234567890},
        "bot": {"status": "running", "last_seen": 1234567890},
        "userbot": {"status": "running", "last_seen": 1234567890},
        "reminders": {"status": "running", "last_seen": 1234567890}
    }
}

async def bot_heartbeat():
    while not SHUTDOWN_EVENT.is_set():
        await report_status("bot", "running")
        await asyncio.sleep(30)
```

---

## 🧠 Модули (brains/)

### AI Core (`ai.py`)

**Назначение:** Mistral AI с Function Calling

```python
async def ask_karina(prompt: str, chat_id: int) -> str:
    # 1. Получение контекста (RAG)
    context = await search_memories(prompt, user_id=chat_id)
    
    # 2. Формирование промпта
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    # 3. Запрос к Mistral (с Circuit Breaker)
    response = await mistral_chat(messages, tools=TOOLS)
    
    # 4. Сохранение в память
    await save_memory(prompt, user_id=chat_id)
    
    return response
```

**Circuit Breaker:**
```python
class CircuitBreaker:
    def __init__(self, max_failures=3, recovery_time=60):
        self.failures = 0
        self.is_open = False
    
    def record_failure(self):
        self.failures += 1
        if self.failures >= self.max_failures:
            self.is_open = True
    
    def can_proceed(self) -> bool:
        if self.is_open:
            return time.time() > self.last_failure + self.recovery_time
        return True
```

### Memory (`memory.py`)

**Назначение:** RAG память с векторным поиском

```python
async def save_memory(text: str, user_id: int):
    # Генерация эмбеддинга
    embedding = await mistral_embeddings(text)
    
    # Сохранение в Supabase
    await supabase.table("memories").insert({
        "user_id": user_id,
        "content": text,
        "embedding": embedding
    })

async def search_memories(query: str, user_id: int, limit=5):
    # Векторный поиск через RPC функцию
    result = await supabase.rpc("match_memories", {
        "query_embedding": await mistral_embeddings(query),
        "match_user_id": user_id,
        "match_count": limit
    })
    
    return result
```

### Calendar (`calendar.py`)

**Назначение:** Google Calendar интеграция

```python
async def get_upcoming_events(max_results=10):
    # Личный календарь
    events = await google_calendar.events().list(
        calendarId='primary',
        maxResults=max_results
    ).execute()
    
    # Bitrix календарь
    bitrix_events = await bitrix_calendar.get_events()
    
    # Объединение и сортировка
    return sorted(events + bitrix_events, key=lambda x: x['start'])
```

### Reminders (`reminders.py`)

**Назначение:** Умные напоминания с эскалацией

```python
class Reminder:
    def __init__(self, id, type, time, message):
        self.escalation_level = 0
        self.is_confirmed = False
    
    def get_escalation_message(self) -> str:
        messages = [
            "Пора сделать укол! 💉",
            "Ты забыл про укол! 😟",
            "Срочно сделай укол! 😠",
            "Это опасно! Сделай укол! 🚨"
        ]
        return messages[self.escalation_level]
```

**Escalation:**
```
22:00 → Напоминание
22:15 → Уровень 1 (вежливо)
22:30 → Уровень 2 (настойчиво)
22:45 → Уровень 3 (тревога)
23:00 → Уровень 4 (критично)
```

### Vision (`vision.py`)

**Назначение:** Анализ изображений (Pixtral)

```python
async def analyze_image(image_path: str, prompt: str, user_id: int):
    # Загрузка изображения
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Запрос к Mistral Pixtral
    response = await mistral_chat([
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": image_data},
                {"type": "text", "text": prompt}
            ]
        }
    ])
    
    # Сохранение в историю
    await supabase.table("vision_history").insert({
        "user_id": user_id,
        "analysis": response,
        "prompt": prompt
    })
    
    return response
```

### Productivity (`productivity.py`)

**Назначение:** Трекер привычек, учёт времени

```python
async def track_habit(user_id: int, habit_name: str, completed: bool):
    await supabase.table("habits").upsert({
        "user_id": user_id,
        "name": habit_name,
        "completed": completed,
        "date": datetime.now().date()
    })

async def analyze_work_patterns(user_id: int, days=7):
    sessions = await supabase.table("work_sessions")\
        .select("*")\
        .eq("user_id", user_id)\
        .gte("start_time", datetime.now() - timedelta(days=days))\
        .execute()
    
    # Анализ паттернов
    return {
        "avg_start_time": "...",
        "avg_end_time": "...",
        "overwork_days": 5
    }
```

### News (`news.py`)

**Назначение:** RSS новости с историей

```python
async def get_latest_news(limit=5, force_refresh=False):
    # Проверка кэша (1 час)
    if not force_refresh and cache_valid():
        return cached_news
    
    # Парсинг RSS
    feeds = [
        "https://habr.com/ru/rss/articles/telecom/",
        "https://www.osp.ru/news/rss/"
    ]
    
    news = []
    for feed in feeds:
        async with aiohttp.ClientSession() as session:
            async with session.get(feed) as response:
                rss = await response.text()
                news.extend(parse_rss(rss))
    
    # Фильтрация дублей
    unique_news = filter_duplicates(news)
    
    # Сохранение в историю
    for item in unique_news[:limit]:
        await supabase.table("news_history").insert(item)
    
    return format_news(unique_news[:limit])
```

### Employees (`employees.py`)

**Назначение:** База сотрудников, авто-поздравления

```python
async def get_upcoming_birthdays(days=7):
    today = datetime.now()
    
    result = await supabase.rpc("get_upcoming_birthdays", {
        "start_date": today.date(),
        "end_date": (today + timedelta(days=days)).date()
    })
    
    return result

async def birthday_reminder(employee):
    message = f"""
🎂 **Сегодня день рождения!**

{employee['full_name']} — {employee['position']}

Поздравь его в чате! 🎉
"""
    return message
```

---

## 🌅 Auras

### Aura Engine (`auras/__init__.py`)

**Назначение:** Фоновые задачи (emoji-статусы, BIO)

```python
async def start_auras(user_client, bot_client):
    while True:
        now = datetime.now()
        
        # Утренний брифинг (7:00)
        if now.hour == 7 and now.minute == 0:
            await send_morning_briefing()
        
        # Смена статуса (по расписанию)
        if now.hour == 22 and now.minute == 0:
            await set_emoji_status("sleep")
        
        # Проверка переработок (21:00)
        if now.hour == 21 and now.minute == 0:
            await check_overwork()
        
        await asyncio.sleep(60)
```

### Aura Settings (`auras/aura_settings.py`)

**Назначение:** Настройки аур через БД

```python
class AuraSettingsManager:
    async def get_settings(self, user_id: int):
        result = await supabase.table("aura_settings")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    async def update_aura(self, user_id: int, aura_name: str, enabled: bool):
        await supabase.table("aura_settings")\
            .upsert({"user_id": user_id, aura_name: {"enabled": enabled}})
```

---

## 🎯 Skills

### Commands (`skills/__init__.py`)

**Назначение:** Telegram команды (24 штуки)

```python
def register_karina_base_skills(client):
    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond("Привет! Я Карина. 😊")
    
    @client.on(events.NewMessage(pattern='/calendar'))
    async def calendar_handler(event):
        info = await get_upcoming_events()
        await event.respond(f"🗓 **Твои планы:**\n\n{info}")
    
    @client.on(events.NewMessage(pattern='/health'))
    async def health_handler(event):
        report = await get_health_report_text(7)
        await event.respond(report)
```

---

## 🔌 Plugins

### Plugin Manager (`plugins/__init__.py`)

**Назначение:** Система плагинов

```python
class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.config = {}
    
    def discover_plugins(self) -> list:
        """Находит все плагины в папке plugins/"""
        return [f.stem for f in Path("plugins").glob("*.py")]
    
    def load_plugin(self, name: str):
        """Загружает плагин"""
        spec = importlib.util.spec_from_file_location(name, f"plugins/{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    async def initialize_all(self):
        """Инициализирует все включенные плагины"""
        for name in self.get_enabled_plugins():
            plugin = self.get_plugin(name)
            if hasattr(plugin, 'initialize'):
                await plugin.initialize()
```

---

## 🗄️ Database (Supabase)

### Connection

```python
from supabase import create_client

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)
```

### Tables

| Таблица | Поля | Индексы |
|---------|------|---------|
| `health_records` | id, user_id, confirmed, timestamp | user_id |
| `memories` | id, user_id, content, embedding (vector) | embedding (ivfflat) |
| `reminders` | id, user_id, type, is_active, is_confirmed | user_id, is_active |
| `aura_settings` | user_id, emoji_status, bio_status, ... | user_id |
| `employees` | id, full_name, position, department, birthday | birthday (month, day) |
| `news_history` | id, user_id, title, url, published_at | user_id, published_at |
| `habits` | id, user_id, name, target, streak | user_id |
| `work_sessions` | id, user_id, start_time, end_time, source | user_id, start_time |
| `vision_history` | id, user_id, file_path, analysis, prompt | user_id |

### RPC Functions

```sql
-- Векторный поиск
CREATE FUNCTION match_memories(
  query_embedding vector(1024),
  match_user_id bigint,
  match_count int
)
RETURNS TABLE(id bigint, content text, similarity float)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT id, content, 1 - (embedding <=> query_embedding) as similarity
  FROM memories
  WHERE user_id = match_user_id
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

---

## 📊 Event Flow

### 1. Пользователь пишет сообщение

```
Пользователь → NewMessage
  ↓
vpn_stranger_interceptor (если sender_id != MY_ID)
  ↓
  ├─ NEW → Оферта
  ├─ WAITING_EMAIL → Запрос Email
  ├─ WAITING_CODE → Запрос кода
  └─ REGISTERED → Главное меню
  ↓
raise events.StopPropagation (блокировка AI)
```

### 2. Пользователь нажимает кнопку

```
Пользователь → CallbackQuery
  ↓
vpn_callback_handler
  ↓
  ├─ accept_offer → WAITING_EMAIL
  ├─ pay_1 → Оплата (1 месяц)
  ├─ checkpay_1 → Проверка → Генерация ключа
  └─ menu_profile → Профиль
  ↓
await event.edit(...)
```

### 3. Пользователь общается с AI

```
Пользователь → chat_handler
  ↓
  ├─ Фото → analyze_image()
  ├─ Голос → transcribe_voice() → AI
  └─ Текст → AI
  ↓
async with client.action('typing')
  ↓
ask_karina() → Mistral AI
  ↓
send_with_typewriter() → Постепенный вывод
```

---

## 🛡️ Отказоустойчивость

### Graceful Shutdown

```python
SHUTDOWN_EVENT = asyncio.Event()

for sig in (signal.SIGINT, signal.SIGTERM):
    loop.add_signal_handler(sig, lambda: SHUTDOWN_EVENT.set())

try:
    await run_web()
finally:
    SHUTDOWN_EVENT.set()
    await plugin_manager.shutdown_all()
    await bot_client.disconnect()
    await user_client.disconnect()
```

### Error Handling

```python
try:
    result = await mistral_chat(messages)
except RateLimitError:
    await asyncio.sleep(retry_after)
    result = await mistral_chat(messages)  # Retry
except CircuitBreakerOpen:
    return "Извините, AI временно недоступен. Попробуйте позже."
except Exception as e:
    logger.error(f"AI error: {e}")
    return "Произошла ошибка. Попробуйте еще раз."
```

---

## 📈 Метрики

### Производительность

| Метрика | Значение |
|---------|----------|
| **Время ответа AI** | 2-5 сек |
| **Время ответа (кэш)** | 0.01 сек |
| **RAG поиск** | 0.1-0.3 сек |
| **Генерация ключа** | 2-5 сек |

### Надёжность

| Метрика | Значение |
|---------|----------|
| **Uptime** | 99.5% |
| **Circuit Breaker срабатываний** | 0-2 в день |
| **Supervisor рестартов** | 0-1 в неделю |

---

## 📞 Поддержка

- **Документация:** `docs/ARCHITECTURE.md`
- **Логи:** `tail -f bot.log`
- **Метрики:** `/api/metrics`

---

**Последнее обновление:** 28 февраля 2026 г.
