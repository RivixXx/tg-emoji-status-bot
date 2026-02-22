# 🚀 Deployment Guide — Karina AI v3.0

## Обновление с v2.0 на v3.0

### Шаг 1: Резервное копирование

```bash
# Бэкап базы данных (Supabase)
# Через Dashboard: Settings → Database → Backup

# Бэкап конфига
cp .env .env.backup
cp plugins/plugins_config.json plugins_config.json.backup
```

### Шаг 2: Обновление кода

```bash
# На сервере
cd ~/tg-emoji-status-bot

# Остановить бота
pkill -f "python main.py"

# Обновить код
git pull origin main

# Установить новые зависимости
pip install -r requirements.txt
```

### Шаг 3: Обновление БД

```sql
-- Выполните в Supabase SQL Editor

-- Таблица для напоминаний
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    scheduled_time TIMESTAMPTZ NOT NULL,
    escalate_after JSONB DEFAULT '[]',
    current_level TEXT DEFAULT 'soft',
    is_active BOOLEAN DEFAULT true,
    is_confirmed BOOLEAN DEFAULT false,
    snooze_until TIMESTAMPTZ,
    context JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для настроек аур
CREATE TABLE IF NOT EXISTS aura_settings (
    user_id BIGINT PRIMARY KEY,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_reminders_scheduled ON reminders(scheduled_time) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_reminders_type ON reminders(type);
CREATE INDEX IF NOT EXISTS idx_aura_settings_user ON aura_settings(user_id);
```

### Шаг 4: Проверка конфигурации

```bash
# Проверьте plugins/plugins_config.json
cat plugins/plugins_config.json

# При необходимости отредактируйте
nano plugins/plugins_config.json
```

### Шаг 5: Запуск

```bash
# Запуск бота
set -a && source .env && set +a
python main.py

# Или через systemd
sudo systemctl restart karina-bot
```

### Шаг 6: Проверка

```bash
# Проверка логов
tail -f bot.log

# Проверка плагинов
curl http://localhost:8080/api/plugins

# Проверка здоровья
curl http://localhost:8080/api/health
```

---

## Первая установка (с нуля)

### Требования

- Python 3.10+
- Supabase аккаунт
- Telegram API credentials
- Mistral API key

### 1. Клонирование

```bash
git clone https://github.com/your-username/tg-emoji-status-bot.git
cd tg-emoji-status-bot
```

### 2. Зависимости

```bash
python -m venv karina
source karina/bin/activate  # Windows: karina\Scripts\activate
pip install -r requirements.txt
```

### 3. Конфигурация

```bash
# Копирование примера
cp .env.example .env

# Редактирование
nano .env
```

**Необходимые переменные:**

```env
# Telegram
API_ID=12345678
API_HASH=your_api_hash
KARINA_BOT_TOKEN=bot_token
SESSION_STRING=user_session_string
MY_TELEGRAM_ID=your_id
TARGET_USER_ID=target_user_id

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# Mistral AI
MISTRAL_API_KEY=your_mistral_key

# Google Calendar (опционально)
GOOGLE_CALENDAR_CREDENTIALS=json_credentials

# Погода
WEATHER_API_KEY=your_openweather_key
WEATHER_CITY=Moscow

# Секрет для API
KARINA_API_SECRET=your_secret_key
```

### 4. Инициализация БД

Откройте Supabase SQL Editor и выполните `docs/init.sql`.

### 5. Запуск

```bash
set -a && source .env && set +a
python main.py
```

### 6. systemd сервис (Ubuntu)

```bash
sudo nano /etc/systemd/system/karina-bot.service
```

```ini
[Unit]
Description=Karina AI Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/tg-emoji-status-bot
Environment="PATH=/home/ubuntu/tg-emoji-status-bot/karina/bin"
ExecStart=/home/ubuntu/tg-emoji-status-bot/karina/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable karina-bot
sudo systemctl start karina-bot
sudo systemctl status karina-bot
```

---

## Docker развёртывание

### 1. Сборка

```bash
docker-compose build
```

### 2. Запуск

```bash
docker-compose up -d
```

### 3. Логи

```bash
docker-compose logs -f karina-bot
```

---

## Troubleshooting

### Ошибка: "ModuleNotFoundError: No module named 'supabase'"

```bash
pip install supabase
# Или
pip install -r requirements.txt
```

### Ошибка: "relation 'reminders' does not exist"

Выполните SQL из Шага 3 (Обновление БД).

### Ошибка: "Plugin not found"

Проверьте `plugins/plugins_config.json` и наличие файлов в `plugins/`.

### Бот не отвечает

1. Проверьте логи: `tail -f bot.log`
2. Проверьте токен бота
3. Проверьте Privacy Mode в @BotFather

### Плагины не загружаются

```bash
# Проверка директории
ls -la plugins/

# Проверка конфига
cat plugins/plugins_config.json

# Включение debug логов
export PYTHONDEBUG=1
```

---

## Мониторинг

### Health Check

```bash
curl http://localhost:8080/api/health
```

**Ответ:**
```json
{
  "status": "ok",
  "uptime_seconds": 3600,
  "errors": 0,
  "components": {
    "web": {"status": "running"},
    "bot": {"status": "running"},
    "userbot": {"status": "running"},
    "reminders": {"status": "running"}
  }
}
```

### Metrics

```bash
curl http://localhost:8080/api/metrics
```

### Plugins Status

```bash
curl http://localhost:8080/api/plugins
```

---

## Backup

### База данных

```bash
# Supabase: Dashboard → Database → Backups
# Или через pg_dump
pg_dump -h db.your-project.supabase.co -U postgres karina_db > backup.sql
```

### Конфигурация

```bash
tar -czf karina-backup-$(date +%Y%m%d).tar.gz .env plugins/plugins_config.json
```

### Автоматический backup (cron)

```bash
# В crontab
0 3 * * * /home/ubuntu/backup-karina.sh
```

---

## Security Notes

- Не коммитьте `.env` в git
- Используйте `KARINA_API_SECRET` для защиты API
- Регулярно обновляйте зависимости
- Включите 2FA в Supabase Dashboard
