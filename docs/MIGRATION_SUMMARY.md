# 📋 Migration Summary — Karina AI v3.0

## Быстрые команды для обновления

### 1. Обновление кода и зависимостей

```bash
cd ~/tg-emoji-status-bot

# Остановить бота
pkill -f "python main.py"

# Обновить код
git pull origin main

# Установить зависимости
pip install -r requirements.txt
```

### 2. Обновление БД

Выполните в **Supabase SQL Editor**:

```sql
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

-- Комментарии
COMMENT ON TABLE reminders IS 'Умные напоминания с эскалацией и персистентностью';
COMMENT ON TABLE aura_settings IS 'Настройки аур пользователей';
```

### 3. Запуск

```bash
# Запуск
set -a && source .env && set +a
python main.py

# Или через systemd
sudo systemctl restart karina-bot
```

---

## Проверка работы

### 1. Проверка плагинов

```bash
curl http://localhost:8080/api/plugins
```

**Ожидаемый ответ:**
```json
{
  "plugins": [
    {
      "name": "google_calendar",
      "version": "1.0.0",
      "enabled": true,
      ...
    }
  ]
}
```

### 2. Проверка новых команд

В Telegram:

```
/summary 7          # Еженедельный отчёт за 7 дней
/aurasettings       # Показать настройки аур
```

### 3. Проверка логов

```bash
tail -f bot.log
```

**Ожидаемые сообщения:**
```
📦 Инициализация системы плагинов...
✅ Плагин google_calendar v1.0.0 загружен
✅ Загружено 1 активных плагинов
```

---

## Новые файлы

```
tg-emoji-status-bot/
├── brains/
│   ├── mcp_tools.py          # NEW: MCP инструменты
│   ├── smart_summary.py      # NEW: Еженедельные отчёты
│   └── aura_settings.py      # NEW: Настройки аур
├── plugins/
│   ├── base.py               # NEW: Базовый класс плагина
│   ├── __init__.py           # NEW: Экспорт системы
│   ├── google_calendar.py    # NEW: Плагин календаря
│   └── plugins_config.json   # NEW: Конфигурация
└── docs/
    ├── CHANGELOG.md          # NEW: История изменений
    ├── PLUGINS.md            # NEW: Документация плагинов
    ├── DEPLOY.md             # NEW: Полная инструкция деплоя
    └── MIGRATION_SUMMARY.md  # NEW: Этот файл
```

---

## Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `requirements.txt` | + `supabase` |
| `brains/clients.py` | + `supabase_client` |
| `brains/memory.py` | Полная переработка |
| `brains/reminders.py` | Переработка |
| `brains/ai.py` | + 3 MCP инструмента |
| `brains/calendar.py` | Без изменений (теперь плагин) |
| `skills/__init__.py` | + `/summary`, `/aurasettings` |
| `main.py` | + Plugin Manager, API endpoints |
| `docs/init.sql` | + 2 таблицы |
| `README.md` | Обновлён |

---

## API Endpoints

### Плагины

```bash
# Список
GET /api/plugins

# Включить
POST /api/plugins/google_calendar/enable
Headers: X-Karina-Secret: <your_secret>

# Выключить
POST /api/plugins/google_calendar/disable
Headers: X-Karina-Secret: <your_secret>

# Настройки
GET /api/plugins/google_calendar/settings
POST /api/plugins/google_calendar/settings
Headers: X-Karina-Secret: <your_secret>
```

---

## Troubleshooting

### Ошибка: `ModuleNotFoundError: No module named 'supabase'`

```bash
pip install supabase
# или
pip install -r requirements.txt
```

### Ошибка: `relation "reminders" does not exist`

Выполните SQL из раздела "Обновление БД" выше.

### Ошибка: `Plugin google_calendar not found`

Проверьте:
```bash
ls -la plugins/
cat plugins/plugins_config.json
```

### Бот не запускается

1. Проверьте логи: `tail -f bot.log`
2. Проверьте `.env` файл
3. Убедитесь, что все зависимости установлены

---

## Откат к предыдущей версии

```bash
# Вернуть код
git checkout <previous_commit>

# Вернуть зависимости
pip uninstall supabase
pip install -r requirements.txt

# Перезапустить бота
sudo systemctl restart karina-bot
```

**Внимание:** Таблицы `reminders` и `aura_settings` останутся в БД, но не будут использоваться.

---

## Контакты и поддержка

- 📁 GitHub Issues: https://github.com/your-username/tg-emoji-status-bot/issues
- 📖 Документация: `docs/` папка
- 🧠 Wiki: https://github.com/your-username/tg-emoji-status-bot/wiki

---

**Последнее обновление:** Февраль 2026  
**Версия:** v3.0.0
