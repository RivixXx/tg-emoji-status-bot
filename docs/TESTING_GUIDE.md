# 🧪 Автоматическое тестирование Karina AI

**Скрипт:** `scripts/test_productivity.py`
**Версия:** 1.0
**Дата:** Март 2026

---

## 📋 Описание

Автоматический скрипт для полного тестирования системы управления задачами и проектами Karina AI.

**Время выполнения:** 30-60 секунд

---

## 🚀 Быстрый старт

### 1. Запуск теста

```bash
# Перейти в директорию проекта
cd ~/tg-emoji-status-bot

# Активировать виртуальное окружение
source karina/bin/activate  # Linux/Mac
# или
karina\Scripts\activate  # Windows

# Запустить тест
python scripts/test_productivity.py
```

### 2. Просмотр результатов

```bash
# Результаты в реальном времени
python scripts/test_productivity.py

# Логи теста
cat test_productivity.log

# Только ошибки
grep "ERROR" test_productivity.log
```

---

## 📊 Что тестирует скрипт

### ✅ 6 основных тестов:

| № | Тест | Описание | Время |
|---|------|----------|-------|
| 1 | **Задачи (CRUD)** | Создание, чтение, обновление, удаление задач | ~10 сек |
| 2 | **Проекты (CRUD)** | Создание, завершение, удаление проектов | ~5 сек |
| 3 | **Спринты (CRUD)** | Создание спринта, задачи спринта, завершение | ~10 сек |
| 4 | **Ежедневные цели** | Создание, выполнение, вечерний обзор | ~5 сек |
| 5 | **AI Function Calling** | Симуляция вызова AI инструментов | ~10 сек |
| 6 | **Триггеры** | Проверка состояния триггеров | ~1 сек |

---

## 📝 Пример вывода

```
================================================================================
🚀 KARINA AI PRODUCTIVITY ASSISTANT — АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ
================================================================================

📅 Дата: 2026-03-08 15:30:00.000000
👤 User ID: 582792393
💾 Supabase: ✅

============================================================
📝 ТЕСТ: Задачи (CRUD)
============================================================

1️⃣ Создание задачи...
✅ Задача создана: ID=123, Title=Тестовая задача 1

2️⃣ Получение задачи по ID...
✅ Задача получена: Тестовая задача 1

3️⃣ Обновление задачи...
✅ Задача обновлена: Обновлённая тестовая задача

4️⃣ Получение списка задач...
✅ Получено задач: 5

5️⃣ Начало работы над задачей...
✅ Задача в работе: TaskStatus.IN_PROGRESS

6️⃣ Завершение задачи...
✅ Задача завершена: TaskStatus.DONE

7️⃣ Удаление задачи...
✅ Задача удалена

8️⃣ Проверка статистики продуктивности...
✅ Статистика: {'total_tasks': 5, 'completed_tasks': 3, ...}

✅ ТЕСТ ЗАДАЧ: УСПЕШНО

... (аналогично для других тестов)

================================================================================
📊 ИТОГИ ТЕСТИРОВАНИЯ
================================================================================
✅ PASS — Задачи
✅ PASS — Проекты
✅ PASS — Спринты
✅ PASS — Ежедневные цели
✅ PASS — AI Function Calling
✅ PASS — Триггеры

📈 Пройдено: 6/6 тестов
📉 Провалено: 0/6 тестов

🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к работе!
================================================================================
```

---

## 🔧 Настройки

### Переменные окружения

Скрипт использует переменные из `.env`:

```bash
# Обязательно
MY_TELEGRAM_ID=582792393      # ID пользователя для тестов
SUPABASE_URL=https://...      # URL Supabase
SUPABASE_KEY=...              # Ключ Supabase

# Опционально
MISTRAL_API_KEY=...           # Для AI тестов (не обязательно)
```

### Логирование

**Формат логов:**
```
2026-03-08 15:30:00,000 - INFO - Сообщение
2026-03-08 15:30:01,000 - ERROR - Ошибка
```

**Файл логов:**
- `test_productivity.log` — создаётся при запуске
- Перезаписывается при каждом запуске

---

## 🐛 Troubleshooting

### Ошибка: "Supabase клиент не инициализирован"

**Причина:** Не заполнен `.env` файл

**Решение:**
```bash
# Проверить .env
cat .env | grep SUPABASE

# Если пусто — скопировать .env.example
cp .env.example .env
nano .env  # Заполнить значениями
```

### Ошибка: "ModuleNotFoundError: No module named 'brains'"

**Причина:** Не добавлен корень проекта в PATH

**Решение:**
```bash
# Запускать из корня проекта
cd ~/tg-emoji-status-bot
python scripts/test_productivity.py
```

### Ошибка: "Task not found"

**Причина:** Задача была удалена в предыдущем тесте

**Решение:** Нормальное поведение, тесты изолированы

### Тесты выполняются слишком долго

**Причина:** Медленное соединение с Supabase

**Решение:**
- Проверить интернет-соединение
- Увеличить таймауты в коде (по умолчанию 60 сек)

---

## 📊 Интерпретация результатов

### ✅ Все тесты пройдены (6/6)

```
📈 Пройдено: 6/6 тестов
🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!
```

**Статус:** ✅ Система готова к продакшену

### ⚠️ Часть тестов провалена

```
📈 Пройдено: 4/6 тестов
⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ!
```

**Действия:**
1. Проверить логи выше
2. Исправить ошибки
3. Перезапустить тесты

### ❌ Все тесты провалены

```
📈 Пройдено: 0/6 тестов
```

**Возможные причины:**
- Не заполнен `.env`
- Нет подключения к Supabase
- Ошибка импорта модулей

**Решение:**
```bash
# Проверить подключение
python -c "from brains.clients import supabase_client; print(supabase_client)"

# Проверить импорты
python -c "from brains import tasks, projects, sprints; print('OK')"
```

---

## 🔄 Интеграция с CI/CD

### GitHub Actions

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      env:
        MY_TELEGRAM_ID: ${{ secrets.MY_TELEGRAM_ID }}
        SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
        SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
      run: |
        python scripts/test_productivity.py
```

### Локальный CI

```bash
#!/bin/bash
# scripts/run_tests.sh

echo "🚀 Запуск тестов..."

python scripts/test_productivity.py

if [ $? -eq 0 ]; then
    echo "✅ Все тесты пройдены!"
    exit 0
else
    echo "❌ Тесты провалены!"
    exit 1
fi
```

---

## 📈 Метрики тестов

### Время выполнения

| Тест | Ожидаемое время |
|------|-----------------|
| Задачи | ~10 сек |
| Проекты | ~5 сек |
| Спринты | ~10 сек |
| Ежедневные цели | ~5 сек |
| AI Function Calling | ~10 сек |
| Триггеры | ~1 сек |
| **ИТОГО** | **~41 сек** |

### Использование памяти

```bash
# Запуск с профилированием памяти
python -m memory_profiler scripts/test_productivity.py
```

### Покрытие кода

```bash
# Запуск с coverage
coverage run scripts/test_productivity.py
coverage report
coverage html
```

---

## 🎯 Рекомендации

### 1. Запускать перед деплоем

```bash
# Перед обновлением на сервере
python scripts/test_productivity.py

# Если все тесты пройдены
git push && ssh server "cd project && git pull && sudo systemctl restart bot"
```

### 2. Запускать после изменений

```bash
# После изменения кода
python scripts/test_productivity.py

# Убедиться что все тесты пройдены
```

### 3. Автоматизировать

```bash
# Добавить в pre-commit hook
cat >> .git/hooks/pre-commit << 'EOF'
#!/bin/bash
python scripts/test_productivity.py || exit 1
EOF

chmod +x .git/hooks/pre-commit
```

---

## 📝 Логи тестов

### Структура логов

```
test_productivity.log

2026-03-08 15:30:00 - INFO - ================================
2026-03-08 15:30:00 - INFO - 🚀 KARINA AI PRODUCTIVITY ASSISTANT
2026-03-08 15:30:01 - INFO - 📝 ТЕСТ: Задачи (CRUD)
2026-03-08 15:30:02 - INFO - 1️⃣ Создание задачи...
2026-03-08 15:30:03 - INFO - ✅ Задача создана: ID=123
...
```

### Поиск ошибок

```bash
# Все ошибки
grep "ERROR" test_productivity.log

# Ошибки с контекстом
grep -B 2 -A 2 "ERROR" test_productivity.log

# Только критичные
grep "💥" test_productivity.log
```

### Статистика

```bash
# Количество тестов
grep "TEST:" test_productivity.log | wc -l

# Количество ошибок
grep "ERROR" test_productivity.log | wc -l

# Количество успешных тестов
grep "✅ ТЕСТ" test_productivity.log | wc -l
```

---

## 🎯 Примеры использования

### Быстрая проверка

```bash
# Запустить и проверить статус
python scripts/test_productivity.py && echo "✅ OK" || echo "❌ FAIL"
```

### Полная проверка с логами

```bash
# Запустить с сохранением логов
python scripts/test_productivity.py 2>&1 | tee test_output.log

# Проверить результат
tail -20 test_output.log
```

### Проверка конкретного теста

```bash
# Запустить только тест задач (модификация скрипта)
python -c "
import asyncio
from scripts.test_productivity import test_tasks
asyncio.run(test_tasks(582792393))
"
```

---

**Последнее обновление:** Март 2026
**Автор:** Karina AI Team
