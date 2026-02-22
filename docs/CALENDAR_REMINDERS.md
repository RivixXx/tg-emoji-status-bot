# 🔔 Напоминания о встречах из календаря

## 📋 Обзор

Karina AI автоматически напоминает о встречах из Google Calendar за **15 минут** до начала события.

---

## 🔄 Как это работает

### Гибридная система создания напоминаний

```
┌─────────────────────────────────────────────────────────────┐
│                    СОБЫТИЕ ДОБАВЛЕНО                        │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
    ┌───────────────┐               ┌───────────────┐
    │ Через бота    │               │ Напрямую в    │
    │ (чат/Mini App)│               │ Google Calendar│
    └───────────────┘               └───────────────┘
            │                               │
            ▼                               ▼
    ┌───────────────────┐           ┌───────────────────┐
    │ АВТО при создании │           │ Ждём 7:00 утра    │
    │ напоминание       │           │ следующего дня    │
    └───────────────────┘           └───────────────────┘
                                            │
                                            ▼
                                    ┌───────────────────┐
                                    │ УТРЕННЯЯ ПРОВЕРКА │
                                    │ (каждый день 7:00)│
                                    └───────────────────┘
                                            │
                                            ▼
                                    ┌───────────────────┐
                                    │ Создание напомин. │
                                    │ для всех событий  │
                                    └───────────────────┘
```

---

## ⏰ Расписание автоматических задач

| Время | Задача | Описание |
|-------|--------|----------|
| **7:00** | `check_calendar_reminders_task` | Проверка календаря на сегодня, создание напоминаний |
| **8:15** | `check_birthdays_task` | Проверка дней рождения сотрудников |

---

## 🛠️ Реализация

### 1. Утренняя проверка (7:00)

**Файл:** `auras/__init__.py`

```python
async def check_calendar_reminders_task(karina_client):
    """
    Утренняя проверка календаря на сегодня
    Создаёт напоминания за 15 минут до каждого события
    """
    # Запускаем в 7:00 утра
    if now.hour == 7 and now.minute == 0:
        events = await get_today_calendar_events()
        
        for event in events:
            reminder_time = event['start'] - timedelta(minutes=15)
            
            # Пропускаем если время прошло
            if reminder_time <= now:
                continue
            
            # Создаём напоминание если нет дубля
            reminder = Reminder(
                id=f"meeting_{int(event_time.timestamp())}",
                type=ReminderType.MEETING,
                message=f"Встреча: {event['summary']}",
                scheduled_time=reminder_time,
                ...
            )
            await reminder_manager.add_reminder(reminder)
```

### 2. Авто-создание при добавлении через бота

**Файл:** `brains/calendar.py`

```python
async def create_event(summary, start_time, duration_minutes=30, 
                       description=None, create_reminder=True):
    # ... создание события в Google Calendar ...
    
    # Автоматическое создание напоминания
    if create_reminder:
        reminder_time = start_time - timedelta(minutes=15)
        
        if reminder_time > now:  # Если время ещё не прошло
            reminder = Reminder(
                id=f"meeting_{int(start_time.timestamp())}",
                type=ReminderType.MEETING,
                message=f"Встреча: {summary}",
                scheduled_time=reminder_time,
                ...
            )
            await reminder_manager.add_reminder(reminder)
```

### 3. Получение событий на сегодня

**Файл:** `brains/calendar.py`

```python
async def get_today_calendar_events() -> list:
    """
    Получает список событий на сегодня (с 00:00 до 23:59 по МСК)
    Возвращает: [{'summary': str, 'start': datetime, 'end': datetime, ...}]
    """
    # Запрос к Google Calendar API с фильтрацией по дате
    ...
```

---

## 📊 Типы напоминаний

### Встречи (MEETING)

| Параметр | Значение |
|----------|----------|
| **Время отправки** | За 15 минут до встречи |
| **Эскалация** | 5 мин → 10 мин |
| **Кнопки** | "👍 Готов!", "⏰ 5 мин" |
| **Источник** | `auto_create` или `auto_morning_check` |

### Пример сообщения

```
🔔 Встреча: Совещание по проекту
⏰ Начало в 14:00

[👍 Готов!] [⏰ 5 мин]
```

---

## 🔍 Логирование

### Успешное создание

```
📅 Утренняя проверка календаря на сегодня...
🔔 Создано напоминание: Совещание по проекту на 13:45
✅ Проверка завершена. Создано напоминаний: 3
```

### Пропуск события

```
⏭️ Пропущено событие 'Обед' — время напоминания прошло
⚠️ Напоминание для 'Планёрка' уже существует
```

---

## 🧪 Тестирование

### 1. Проверка утренней задачи

```python
# В main.py или консоли
from auras import check_calendar_reminders_task
from brains.clients import karina_client

# Принудительный запуск (не дожидаясь 7:00)
await check_calendar_reminders_task(karina_client)
```

### 2. Проверка авто-создания

```python
# Создаём событие через бота
from brains.calendar import create_event
from datetime import datetime, timedelta

future_time = datetime.now() + timedelta(hours=2)
await create_event(
    summary="Тестовая встреча",
    start_time=future_time,
    duration_minutes=30
)

# Проверяем напоминание
from brains.reminders import reminder_manager
print(reminder_manager.reminders)
```

### 3. Просмотр напоминаний

```
/clearrc  → Очистить кэш и протестировать заново
```

---

## 📝 Структура напоминания

```python
Reminder(
    id="meeting_1740312000",           # Уникальный ID
    type=ReminderType.MEETING,         # Тип: встреча
    message="Встреча: Совещание",      # Текст сообщения
    scheduled_time=datetime(...),      # Время отправки
    escalate_after=[5, 10],            # Эскалация (мин)
    current_level=EscalationLevel.SOFT,
    is_active=True,
    is_confirmed=False,
    context={
        "title": "Совещание",
        "minutes": 15,
        "source": "auto_morning_check",  # или "auto_create"
        "event_start": "2026-02-22T14:00:00+03:00",
        "calendar": "Личный"
    }
)
```

---

## 🛡️ Защита от дублей

```python
reminder_id = f"meeting_{int(event_time.timestamp())}"

# Проверка перед созданием
if reminder_id not in reminder_manager.reminders:
    # Создаём напоминание
    ...
else:
    logger.debug(f"⚠️ Напоминание {reminder_id} уже существует")
```

---

## ⚠️ Известные ограничения

| Проблема | Решение |
|----------|---------|
| Событие добавлено после 7:00 | Напоминание создастся при добавлении через бота |
| Бот перезапустили после 7:00 | Напоминания сохраняются в БД и загружаются при старте |
| Время напоминания прошло | Пропускаем событие (лог: `⏭️ Пропущено событие`) |
| Google Calendar недоступен | Лог: `❌ Calendar service unavailable` |

---

## 🔧 Настройки

### Изменить время напоминания

**Файл:** `auras/__init__.py` и `brains/calendar.py`

```python
# Было: за 15 минут
reminder_time = event_time - timedelta(minutes=15)

# Стало: за 30 минут
reminder_time = event_time - timedelta(minutes=30)
```

### Изменить время утренней проверки

**Файл:** `auras/__init__.py`

```python
# Было: 7:00
if now.hour == 7 and now.minute == 0:

# Стало: 6:30
if now.hour == 6 and now.minute == 30:
```

### Отключить авто-создание

**Файл:** `brains/calendar.py`

```python
# При вызове create_event
await create_event(
    summary="...",
    start_time=...,
    create_reminder=False  # Отключить авто-напоминание
)
```

---

## 📚 Связанные файлы

| Файл | Функция |
|------|---------|
| `auras/__init__.py` | `check_calendar_reminders_task()` |
| `brains/calendar.py` | `get_today_calendar_events()`, `create_event()` |
| `brains/reminders.py` | `ReminderManager`, `Reminder` |
| `brains/reminder_generator.py` | AI-генерация текста напоминаний |
| `skills/__init__.py` | Обработчик callback-кнопок |

---

## 🎯 Сценарии использования

### Сценарий 1: Добавление через бота

```
Пользователь: "Запиши меня к стоматологу на завтра 15:00"
Карина: [создаёт событие в Google Calendar]
        [автоматически создаёт напоминание на 14:45]
        ✅ Записала! Напомню за 15 минут.
```

### Сценарий 2: Добавление через Google Calendar

```
1. Пользователь добавляет событие в приложении Google Calendar
2. В 7:00 Карина проверяет календарь
3. Создаёт напоминание за 15 минут до встречи
4. В назначенное время отправляет напоминание
```

### Сценарий 3: Конфликт напоминаний

```
1. Событие добавлено в Google Calendar
2. В 7:00 Карина создаёт напоминание
3. Пользователь просит бота: "Перенеси встречу на 16:00"
4. Бот создаёт НОВОЕ событие (новый ID)
5. Старое напоминание остаётся, но не сработает (время прошло)
6. Новое напоминание создаётся автоматически
```

---

**Последнее обновление:** Февраль 2026
