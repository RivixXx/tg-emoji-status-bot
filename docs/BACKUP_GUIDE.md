# 🗄️ Бэкап базы данных

## 📋 Описание

Скрипт `scripts/backup_db.py` предназначен для создания и восстановления бэкапов базы данных Supabase.

---

## 🚀 Быстрый старт

### Создание бэкапа

```bash
# Перейти в директорию проекта
cd ~/tg-emoji-status-bot

# Активировать виртуальное окружение
source karina/bin/activate  # Linux/Mac
# или
karina\Scripts\activate  # Windows

# Создать бэкап
python scripts/backup_db.py
```

**Результат:**
```
2026-03-08 12:00:00 - INFO - 🚀 Начало бэкапа базы данных Supabase
2026-03-08 12:00:01 - INFO - ✅ Подключение к Supabase установлено
2026-03-08 12:00:02 - INFO - 💾 Бэкап таблицы: memories
2026-03-08 12:00:03 - INFO - ✅ memories: 150 записей
...
============================================================
✅ Бэкап завершён успешно!
📁 Файл: backup/db_backup_2026-03-08_12-00-00.json
📊 Записей всего: 500
💾 Размер: 2.45 MB
============================================================
```

---

## 📖 Команды

### Создание бэкапа

```bash
# Базовая команда
python scripts/backup_db.py

# С указанием директории
python scripts/backup_db.py --backup --output /path/to/backups
```

### Восстановление из бэкапа

```bash
# Тестовое восстановление (без записи)
python scripts/backup_db.py --restore backup/db_backup_2026-03-08_12-00-00.json --dry-run

# Полное восстановление
python scripts/backup_db.py --restore backup/db_backup_2026-03-08_12-00-00.json
```

### Просмотр помощи

```bash
python scripts/backup_db.py --help
```

---

## ⚙️ Настройка автоматического бэкапа (cron)

### 1. Откройте crontab

```bash
crontab -e
```

### 2. Добавьте задачу

```bash
# Ежедневный бэкап в 3:00 ночи
0 3 * * * cd /home/user/tg-emoji-status-bot && /home/user/tg-emoji-status-bot/karina/bin/python scripts/backup_db.py >> logs/backup.log 2>&1

# Еженедельный бэкап (воскресенье в 2:00)
0 2 * * 0 cd /home/user/tg-emoji-status-bot && /home/user/tg-emoji-status-bot/karina/bin/python scripts/backup_db.py >> logs/backup.log 2>&1
```

### 3. Проверьте cron

```bash
# Просмотр задач
crontab -l

# Просмотр логов cron
grep CRON /var/log/syslog
```

---

## 📁 Структура бэкапа

Файл бэкапа имеет следующую структуру:

```json
{
  "backup_version": "1.0",
  "supabase_url": "https://xxx.supabase.co",
  "backed_up_at": "2026-03-08T12:00:00.000000",
  "tables": {
    "memories": {
      "table_name": "memories",
      "record_count": 150,
      "data": [...],
      "backed_up_at": "2026-03-08T12:00:00.000000"
    },
    "reminders": {
      "table_name": "reminders",
      "record_count": 25,
      "data": [...],
      "backed_up_at": "2026-03-08T12:00:00.000000"
    }
  }
}
```

---

## 🔄 Восстановление данных

### Полное восстановление

```bash
python scripts/backup_db.py --restore backup/db_backup_2026-03-08_12-00-00.json
```

⚠️ **Внимание:** Это создаст дубликаты записей! Для полного восстановления сначала очистите таблицы.

### Частичное восстановление

Отредактируйте файл бэкапа, удалив ненужные таблицы или записи, затем выполните:

```bash
python scripts/backup_db.py --restore backup/db_backup_2026-03-08_12-00-00.json
```

---

## 🛡️ Лучшие практики

### 1. Регулярность

- **Ежедневные бэкапы** — для критичных данных
- **Еженедельные бэкапы** — для обычных данных
- **Ежемесячные бэкапы** — для архивных целей

### 2. Хранение

- Храните **минимум 3 последние версии** бэкапов
- Копируйте бэкапы на **другой сервер** или в облако
- Используйте **сжатие** для экономии места:

```bash
# Сжатие после бэкапа
gzip backup/db_backup_*.json
```

### 3. Мониторинг

Добавьте проверку последнего бэкапа:

```bash
# Проверка возраста последнего бэкапа
find backup -name "db_backup_*.json" -mtime +7 -print
```

### 4. Автоматизация

Создайте скрипт `scripts/rotate_backups.sh`:

```bash
#!/bin/bash
# Удаляет бэкапы старше 30 дней
find backup -name "db_backup_*.json" -mtime +30 -delete
echo "Старые бэкапы удалены"
```

Добавьте в crontab:
```bash
0 4 * * * /home/user/tg-emoji-status-bot/scripts/rotate_backups.sh >> logs/rotate.log 2>&1
```

---

## 🔧 Интеграция с Supabase Dashboard

### Ручной бэкап через Dashboard

1. Откройте [Supabase Dashboard](https://supabase.com/dashboard)
2. Выберите ваш проект
3. Перейдите в **Table Editor**
4. Нажмите **⋮** → **Backup**

### Автоматические бэкапы Supabase

На бесплатном тарифе автоматические бэкапы **не доступны**. Рассмотрите:

- Переход на Pro тариф ($25/мес)
- Использование нашего скрипта `backup_db.py`

---

## 📊 Мониторинг бэкапов

### Проверка последнего бэкапа

```bash
# Последний бэкап
ls -lt backup/ | head -n 2

# Размер последнего бэкапа
du -h backup/db_backup_*.json | tail -n 1

# Количество записей в последнем бэкапе
python -c "import json; d=json.load(open('backup/db_backup_latest.json')); print(sum(t['record_count'] for t in d['tables'].values()))"
```

### Создание симлинка на последний бэкап

```bash
ln -sf backup/db_backup_*.json backup/db_backup_latest.json
```

---

## ❓ Troubleshooting

### Ошибка: "SUPABASE_URL не установлен"

**Решение:**
```bash
# Проверьте .env файл
cat .env | grep SUPABASE

# Или экспортируйте переменные
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_KEY=your_key
```

### Ошибка: "Connection timeout"

**Решение:**
- Проверьте подключение к интернету
- Увеличьте таймаут в скрипте (параметр `timeout`)

### Ошибка: "Table not found"

**Решение:**
- Убедитесь, что таблицы существуют в Supabase
- Проверьте права доступа service_role ключа

---

## 📝 Логи

Логи бэкапа сохраняются в:

```bash
# При ручном запуске
logs/backup.log

# При запуске через cron
/var/log/syslog | grep backup_db
```

---

## 🔐 Безопасность

- Файлы бэкапа содержат **чувствительные данные**
- Установите права доступа:
  ```bash
  chmod 600 backup/*.json
  ```
- Не коммитьте бэкапы в Git (добавьте в `.gitignore`)

---

**Последнее обновление:** Март 2026
