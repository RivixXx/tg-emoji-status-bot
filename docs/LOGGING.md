# 📝 Логирование и мониторинг Karina AI

## 🎯 Настройка логирования

### Форматы логов

**Текстовый (по умолчанию):**
```
2026-02-24 10:30:15,123 - INFO - brains.ai - 🧠 AI ответил за 1.2s
```

**JSON (для продакшена):**
```json
{
  "timestamp": "2026-02-24T10:30:15.123456",
  "level": "INFO",
  "logger": "brains.ai",
  "message": "🧠 AI ответил за 1.2s",
  "module": "ai",
  "function": "ask_karina",
  "line": 123
}
```

### Переменные окружения

```bash
# Уровень логирования: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Формат: text или json
LOG_FORMAT=text
```

## 📊 Типы логов

### Обычные события
```python
logger.info("✅ Бот запущен")
logger.warning("⚠️ Mistral API rate limit")
logger.error("❌ Ошибка подключения к БД")
```

### С контекстом (user_id, chat_id)
```python
extra = {'user_id': 123456, 'chat_id': 987654}
logger.info("Пользователь отправил команду", extra=extra)
```

### С исключениями
```python
try:
    # код
except Exception as e:
    logger.exception("Ошибка выполнения")  # автоматически добавит traceback
```

## 🔍 Анализ логов

### JSON логи (продакшен)

**Просмотр:**
```bash
# Красивый вывод
docker logs karina-bot | jq .

# Фильтрация по уровню
docker logs karina-bot | jq 'select(.level == "ERROR")'

# Поиск по пользователю
docker logs karina-bot | jq 'select(.user_id == 123456)'
```

**Агрегация:**
```bash
# Количество ошибок
docker logs karina-bot | jq -r 'select(.level == "ERROR")' | wc -l

# Топ модулей по ошибкам
docker logs karina-bot | jq -r 'select(.level == "ERROR") | .logger' | sort | uniq -c | sort -rn
```

### Текстовые логи (разработка)

**Просмотр в реальном времени:**
```bash
# Последние 100 строк + follow
tail -f bot.log -n 100

# С цветом (если поддерживается)
tail -f bot.log | ccze -A
```

**Поиск:**
```bash
# Ошибки
grep "ERROR" bot.log

# Конкретный модуль
grep "brains.vision" bot.log

# Пользователь
grep "user_id=123456" bot.log
```

## 📈 Метрики и мониторинг

### API метрики

**Health check:**
```bash
curl http://localhost:8080/api/health
```

**Ответ:**
```json
{
  "status": "ok",
  "uptime_seconds": 3600,
  "errors": 2,
  "components": {
    "web": {"status": "running", "last_seen": 1234567890},
    "bot": {"status": "running", "last_seen": 1234567890},
    "userbot": {"status": "running", "last_seen": 1234567890},
    "reminders": {"status": "running", "last_seen": 1234567890}
  }
}
```

**Metrics:**
```bash
curl http://localhost:8080/api/metrics
```

### Логирование VPN Shop

**Продажи:**
```python
logger.info(
    "💰 Продажа VPN",
    extra={
        'user_id': telegram_id,
        'months': months,
        'amount': amount
    }
)
```

**Анализ:**
```bash
# Количество продаж за день
docker logs karina-bot | jq 'select(.message | contains("💰 Продажа"))' | wc -l

# Выручка за день
docker logs karina-bot | jq 'select(.message | contains("💰 Продажа")) | .amount' | paste -sd+ | bc
```

## 🚨 Alerting

### Telegram уведомления об ошибках

```python
async def notify_admin(message: str):
    """Отправляет уведомление админу"""
    try:
        await bot_client.send_message(
            MY_ID,
            f"🚨 **ALERT**\n\n{message}"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить alert: {e}")

# Использование
if error_count > threshold:
    await notify_admin(f"Много ошибок: {error_count} за 5 мин")
```

### Prometheus + Grafana (план)

**Экспорт метрик:**
```python
from prometheus_client import Counter, Histogram

AI_REQUESTS = Counter('ai_requests_total', 'Total AI requests')
AI_LATENCY = Histogram('ai_latency_seconds', 'AI response latency')
```

**Дашборды:**
- Запросы к AI (RPS, latency)
- Ошибки по компонентам
- Активные напоминания
- VPN продажи

## 📁 Ротация логов

### Для Docker

```yaml
# docker-compose.yml
services:
  karina-bot:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Для systemd

```ini
# /etc/systemd/system/karina.service
[Service]
StandardOutput=journal
StandardError=journal
```

```bash
# Просмотр через journalctl
journalctl -u karina -f

# Очистка старых логов
journalctl --vacuum-time=7d
```

## 🐛 Отладка

### Включение DEBUG режима

```bash
# В .env
LOG_LEVEL=DEBUG
```

**Что логируется:**
- Все запросы к API
- SQL запросы
- Состояния напоминаний
- Callback кнопки

### Временное логирование

```python
# В любом месте кода
logger.setLevel(logging.DEBUG)
logger.debug("Отладочная информация")
logger.setLevel(logging.INFO)  # Вернуть обратно
```

## 📊 Best Practices

1. **Не логируйте секреты:**
   ```python
   # ❌ ПЛОХО
   logger.info(f"Token: {api_key}")
   
   # ✅ ХОРОШО
   logger.info(f"Token: {api_key[:4]}...{api_key[-4:]}")
   ```

2. **Используйте уровни правильно:**
   - `DEBUG` — отладочная информация
   - `INFO` — обычные события
   - `WARNING` — что-то необычное, но не критично
   - `ERROR` — ошибка, требующая внимания
   - `CRITICAL` — критическая ошибка, бот не работает

3. **Контекст в логах:**
   ```python
   # ✅ Добавьте user_id, chat_id
   logger.info("Обработка команды", extra={'user_id': event.chat_id})
   ```

4. **Структурированные логи для продакшена:**
   ```bash
   LOG_FORMAT=json
   ```

---

**Версия:** 1.0  
**Дата:** 24 февраля 2026
