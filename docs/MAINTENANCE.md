# 🔧 Обслуживание Karina AI v4.0

**Версия:** 1.0  
**Дата:** 28 февраля 2026 г.

---

## 📋 Чек-листы обслуживания

### Ежедневно

```bash
# 1. Проверка статуса бота
systemctl status karina-bot  # Если через systemd
# или
ps aux | grep "python.*main.py"

# 2. Проверка логов
tail -100 ~/tg-emoji-status-bot/bot.log | grep -E "ERROR|WARNING"

# 3. Проверка места на диске
df -h

# 4. Проверка памяти
free -h

# 5. Проверка активных подключений
netstat -tuln | grep :8080
```

### Еженедельно

```bash
# 1. Очистка старых логов
sudo journalctl --vacuum-time=7d

# 2. Проверка обновлений зависимостей
pip list --outdated

# 3. Проверка БД (Supabase Dashboard)
# https://prucbyogggkflmxohylo.supabase.co

# 4. Резервное копирование конфигурации
cp ~/tg-emoji-status-bot/.env ~/backups/.env.$(date +%Y%m%d)
```

### Ежемесячно

```bash
# 1. Обновление зависимостей
cd ~/tg-emoji-status-bot
pip install -r requirements.txt --upgrade

# 2. Проверка метрик
curl http://localhost:8080/api/metrics | jq

# 3. Аудит безопасности
# - Проверка .env на утечки
# - Обновление токенов если нужно

# 4. Анализ производительности
# - Время ответа AI
# - Hit rate кэша
# - Количество ошибок
```

---

## 📊 Мониторинг

### Health Check

```bash
curl http://localhost:8080/api/health
```

**Ответ:**
```json
{
  "status": "ok",
  "uptime_seconds": 123456,
  "errors": 0,
  "components": {
    "web": {"status": "running", "last_seen": 1234567890},
    "bot": {"status": "running", "last_seen": 1234567890},
    "userbot": {"status": "running", "last_seen": 1234567890},
    "reminders": {"status": "running", "last_seen": 1234567890}
  }
}
```

### Metrics

```bash
curl http://localhost:8080/api/metrics
```

**Ответ:**
```json
{
  "metrics": {
    "requests_total": 1000,
    "ai_responses_total": 500,
    "ai_latency_sum": 1500,
    "ai_errors": 5
  },
  "ai_avg_latency_seconds": 3.0,
  "memory_info": "RAG active"
}
```

---

## 🗄️ База данных

### Проверка размера таблиц

```sql
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Очистка старых данных

```sql
-- Удаление старых напоминаний (старше 30 дней)
DELETE FROM reminders 
WHERE created_at < NOW() - INTERVAL '30 days'
AND is_active = false;

-- Удаление старой истории vision (старше 90 дней)
DELETE FROM vision_history 
WHERE analyzed_at < NOW() - INTERVAL '90 days';

-- Удаление старых сессий работы (старше 60 дней)
DELETE FROM work_sessions 
WHERE start_time < NOW() - INTERVAL '60 days';
```

### Оптимизация индексов

```sql
-- Пересборка индексов
REINDEX TABLE memories;
REINDEX TABLE reminders;
REINDEX TABLE employees;

-- Анализ таблиц
ANALYZE memories;
ANALYZE reminders;
ANALYZE vpn_shop_users;
```

---

## 🚨 Обработка ошибок

### Бот не отвечает

```bash
# 1. Проверка процесса
ps aux | grep "python.*main.py"

# 2. Если процесс есть — перезапуск
pkill -f "python.*main.py"
sleep 2
~/deploy.sh

# 3. Проверка логов
tail -100 ~/tg-emoji-status-bot/bot.log

# 4. Если ошибка "database is locked"
# — Ждать 2 минуты или перезапустить
```

### Ошибка "Address already in use"

```bash
# 1. Найти процесс на порту 8080
lsof -i :8080

# 2. Убить процесс
kill -9 <PID>

# 3. Запустить бота
~/deploy.sh
```

### Ошибка "No space left on device"

```bash
# 1. Проверить место
df -h

# 2. Найти большие файлы
sudo find / -type f -size +500M -exec ls -lh {} \;

# 3. Очистить логи
sudo truncate -s 0 /var/log/auth.log
sudo journalctl --vacuum-time=3d

# 4. Проверить
df -h
```

### Circuit Breaker сработал

```bash
# 1. Проверить логи
tail -100 bot.log | grep "Circuit"

# 2. Подождать 60 секунд (recovery time)

# 3. Если не восстановился — перезапуск
pkill -f "python.*main.py"
~/deploy.sh
```

---

## 📈 Логи

### Просмотр логов

```bash
# Последние 100 строк
tail -100 ~/tg-emoji-status-bot/bot.log

# В реальном времени
tail -f ~/tg-emoji-status-bot/bot.log

# Только ошибки
tail -f bot.log | grep ERROR

# Только VPN
tail -f bot.log | grep VPN

# Поиск по дате
grep "2026-02-28" bot.log
```

### Ротация логов

```bash
# Создать файл ротации
sudo nano /etc/logrotate.d/karina-bot

# Содержимое:
/home/ai/tg-emoji-status-bot/bot.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ai ai
}
```

---

## 🔐 Безопасность

### Проверка .env

```bash
# Убедиться что .env не в git
git ls-files | grep .env  # Должно быть пусто

# Проверить права доступа
ls -la ~/tg-emoji-status-bot/.env
# Должно быть: -rw------- (600)

# Исправить если нужно
chmod 600 ~/tg-emoji-status-bot/.env
```

### Обновление токенов

```bash
# 1. Сгенерировать новый токен бота
# https://t.me/BotFather

# 2. Обновить .env
nano ~/tg-emoji-status-bot/.env

# 3. Перезапустить бота
pkill -f "python.*main.py"
~/deploy.sh
```

### Аудит зависимостей

```bash
# Проверка на уязвимости
pip install safety
safety check -r requirements.txt

# Обновление критичных зависимостей
pip install --upgrade mistralai supabase
```

---

## 📦 Бэкапы

### Конфигурация

```bash
# Создать бэкап
tar -czf karina-config-$(date +%Y%m%d).tar.gz \
    ~/tg-emoji-status-bot/.env \
    ~/tg-emoji-status-bot/main.py \
    ~/tg-emoji-status-bot/brains/ \
    ~/tg-emoji-status-bot/auras/ \
    ~/tg-emoji-status-bot/skills/

# Сохранить в безопасное место
cp karina-config-*.tar.gz ~/backups/
```

### База данных (Supabase)

```sql
-- Экспорт через Supabase Dashboard
-- https://prucbyogggkflmxohylo.supabase.co
-- Project Settings → Database → Backup

-- Или через pg_dump
pg_dump -h db.prucbyogggkflmxohylo.supabase.co \
  -U postgres \
  -d postgres \
  -F c \
  -f backup-$(date +%Y%m%d).dump
```

### Восстановление

```bash
# 1. Распаковать конфигурацию
tar -xzf karina-config-20260228.tar.gz -C ~/

# 2. Восстановить БД
pg_restore -h db.prucbyogggkflmxohylo.supabase.co \
  -U postgres \
  -d postgres \
  backup-20260228.dump

# 3. Перезапустить бота
~/deploy.sh
```

---

## 🎯 Производительность

### Оптимизация кэша

```python
# Проверка hit rate
# main.py: USER_CACHE

# Если hit rate < 90%:
# - Увеличить CACHE_TTL (сейчас 300s)
# - Проверить частоту запросов
```

### Оптимизация БД

```sql
-- Проверка медленных запросов
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Добавление индексов
CREATE INDEX IF NOT EXISTS idx_vpn_users_state 
ON vpn_shop_users(state);

CREATE INDEX IF NOT EXISTS idx_orders_status 
ON vpn_shop_orders(status);
```

---

## 📞 Поддержка

- **Документация:** `docs/MAINTENANCE.md`
- **Логи:** `tail -f bot.log`
- **Статус:** `/api/health`
- **Метрики:** `/api/metrics`

---

**Последнее обновление:** 28 февраля 2026 г.
