# 🚀 KARINA AI — ЗАПУСК ПОСЛЕ ИСПРАВЛЕНИЙ

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Пошаговая инструкция](#пошаговая-инструкция)
3. [Проверка работы](#проверка-работы)
4. [Частые проблемы](#частые-проблемы)

---

## ⚡ Быстрый старт

```bash
# 1. Клонирование и переход в директорию
cd tg-emoji-status-bot

# 2. Создание виртуального окружения
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 3. Установка зависимостей
pip install -r requirements.txt

# 4. Копирование конфига
cp .env.example .env

# 5. Заполнение .env (обязательные поля!)
nano .env  # или любой редактор

# 6. Запуск валидации
python -m brains.validate_config

# 7. Запуск бота
python main_fixed.py
```

---

## 📖 Пошаговая инструкция

### Шаг 1: Telegram credentials

1. Перейдите на https://my.telegram.org/apps
2. Войдите по номеру телефона
3. Создайте новое приложение:
   - **App title**: Karina Bot
   - **Short name**: karina_bot
   - **Platform**: Desktop
4. Скопируйте `API_ID` и `API_HASH` в `.env`

### Шаг 2: Bot Token

1. Откройте @BotFather в Telegram
2. Отправьте `/newbot`
3. Введите имя и username бота (должен заканчиваться на `bot`)
4. Скопируйте токен в `.env` как `KARINA_BOT_TOKEN`

### Шаг 3: My Telegram ID

1. Откройте @userinfobot в Telegram
2. Отправьте любое сообщение
3. Скопируйте ваш ID в `.env` как `MY_TELEGRAM_ID`

### Шаг 4: Mistral AI Key

1. Перейдите на https://console.mistral.ai/api-keys
2. Создайте новый API key
3. Скопируйте в `.env` как `MISTRAL_API_KEY`

### Шаг 5: Supabase

1. Перейдите на https://supabase.com
2. Создайте новый проект
3. Settings → API:
   - **Project URL** → `SUPABASE_URL`
   - **service_role key** → `SUPABASE_KEY`
4. SQL Editor → выполните скрипт из `docs/init_supabase.sql`

### Шаг 6: Session String (для аур)

```bash
# Запуск скрипта генерации
python scripts/get_session.py

# Введите номер телефона и код из Telegram
# Скопируйте SESSION_STRING в .env
```

### Шаг 7: Запуск валидации

```bash
python -m brains.validate_config
```

Если все проверки пройдены — запускаем бота:

```bash
python main_fixed.py
```

---

## ✅ Проверка работы

### Health Check

Откройте в браузере:
```
http://localhost:8080/api/health
```

Должно вернуться:
```json
{
  "status": "ok",
  "uptime": 123,
  "errors": 0,
  "components": {...},
  "connections": {
    "supabase": true,
    "mistral": true
  }
}
```

### Telegram команды

1. `/start` — меню бота
2. `/app` — Mini App панель
3. `/health` — статистика здоровья

---

## 🔧 Частые проблемы

### ❌ "API_ID должен быть числом"

**Решение:** Проверьте `.env` — API_ID должен быть без кавычек:
```env
API_ID=12345678  # ✅ Правильно
API_ID="12345678"  # ❌ Неправильно
```

### ❌ "Supabase клиент не инициализирован"

**Причины:**
1. Неверный `SUPABASE_URL` (должен заканчиваться на `.supabase.co`)
2. Неверный `SUPABASE_KEY` (должен быть service_role, не anon)
3. Таблицы не созданы

**Решение:**
```bash
# Выполните SQL скрипт в Supabase SQL Editor
# docs/init_supabase.sql
```

### ❌ "Mistral API вернул ошибку: 401"

**Решение:** Проверьте `MISTRAL_API_KEY` в `.env`

### ❌ "database is locked"

**Причина:** SQLite сессия заблокирована другим процессом

**Решение:**
1. Закройте все экземпляры бота
2. Удалите файлы сессий:
   ```bash
   rm karina_bot_session*
   ```
3. Перезапустите бота

### ❌ "SESSION_STRING пуст — ауры не будут работать"

**Решение:** Сгенерируйте session string:
```bash
python scripts/get_session.py
```

### ❌ Бот не отвечает на команды

**Проверьте:**
1. Бот запущен? (смотрите логи)
2. Ваш `MY_TELEGRAM_ID` совпадает с вашим ID?
3. Бот добавлен в админы (если работает в группе)?

---

## 📊 Логи

Бот выводит логи в консоль. Для сохранения в файл:

```bash
python main_fixed.py 2>&1 | tee bot.log
```

Для просмотра в реальном времени:
```bash
tail -f bot.log
```

---

## 🐳 Docker (опционально)

```bash
docker-compose up -d
```

Проверка логов:
```bash
docker-compose logs -f karina-bot
```

---

## 🆘 Поддержка

Если ничего не помогает:

1. Включите debug логирование в `main_fixed.py`:
   ```python
   logging.basicConfig(level=logging.DEBUG, ...)
   ```

2. Проверьте все подключения:
   ```bash
   python -c "from brains.clients import check_all_connections; import asyncio; print(asyncio.run(check_all_connections()))"
   ```

3. Откройте issue на GitHub с логами
