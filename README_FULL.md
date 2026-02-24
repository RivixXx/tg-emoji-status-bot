# 🤖 Karina AI v1.1 — Полная документация

**Версия:** 1.1 (VPN Shop Release)  
**Дата:** 24 февраля 2026 г.  
**Статус:** ✅ Production Ready

---

## 📋 Содержание

1. [Быстрый старт](#-быстрый-старт)
2. [Архитектура](#-архитектура)
3. [Модули](#-модули)
4. [VPN Shop](#-vpn-shop)
5. [Команды бота](#-команды-бота)
6. [База данных](#-база-данных)
7. [Развёртывание](#-развёртывание)
8. [Мониторинг](#-мониторинг)
9. [Безопасность](#-безопасность)
10. [Тесты](#-тесты)

---

## 🚀 Быстрый старт

### 1. Клонирование
```bash
git clone <repo>
cd tg-emoji-status-bot
```

### 2. База данных (Supabase)
```sql
-- Основные таблицы
docs/init.sql

-- Сотрудники
docs/seed_employees.sql

-- Продуктивность
docs/init_productivity.sql

-- Новости
docs/init_news_history.sql

-- Зрение
docs/init_vision.sql
```

### 3. Переменные окружения
```bash
cp .env.example .env
nano .env  # Заполни своими ключами
```

### 4. Запуск
```bash
python -m venv karina
source karina/bin/activate
pip install -r requirements.txt
python main.py
```

---

## 🏗 Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    Karina AI v1.1                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Bot Client │  │  User Client │  │  Web Server  │ │
│  │  (Telethon)  │  │  (Telethon)  │  │   (Quart)    │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │         │
│  ┌──────▼─────────────────▼─────────────────▼──────┐ │
│  │              Supervisor Pattern                  │ │
│  │  • Graceful Shutdown  • Health Checks           │ │
│  │  • Auto Restart       • Metrics                 │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │              Brains (Интеллект)                  │ │
│  │  • AI (Mistral)  • Calendar  • Reminders        │ │
│  │  • Vision          • Health    • News           │ │
│  │  • Productivity    • Employees • Weather        │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │              Auras (Фоновые задачи)              │ │
│  │  • Emoji статусы  • BIO  • Напоминания          │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │              VPN Shop (Двойное дно)              │ │
│  │  • Marzban API  • QR-коды  • VLESS ключи        │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🧩 Модули

### 1. 🧠 AI (Mistral)
- Function Calling с 11 инструментами
- RAG память (векторный поиск)
- Контекст диалога (10 сообщений)
- Circuit Breaker для отказоустойчивости

**Файлы:** `brains/ai.py`, `brains/memory.py`, `brains/ai_tools.py`

### 2. 📅 Calendar
- Google Calendar (личный + Bitrix)
- Авто-напоминания за 15 минут
- Утренняя проверка в 7:00
- Детектор конфликтов

**Файлы:** `brains/calendar.py`, `auras/__init__.py`

### 3. 🔔 Reminders
- Умные напоминания с эскалацией
- Интерактивные кнопки
- Персистентность в БД
- AI-генерация текстов

**Файлы:** `brains/reminders.py`, `brains/reminder_generator.py`

### 4. 👁️ Vision
- Анализ изображений (Pixtral)
- OCR (распознавание текста)
- Документы, чеки, скриншоты
- Поиск по проанализированным фото

**Файлы:** `brains/vision.py`

### 5. 📊 Productivity
- Трекер привычек
- Учёт рабочего времени
- AI-анализ с рекомендациями
- Детектор переработок (21:00)

**Файлы:** `brains/productivity.py`

### 6. 📰 News
- 4 RSS источника
- История просмотров
- Фильтрация дублей
- Кэширование (1 час)

**Файлы:** `brains/news.py`

### 7. 👥 Employees
- База сотрудников (30 чел.)
- Авто-поздравления (8:15)
- AI-генерация открыток

**Файлы:** `brains/employees.py`

### 8. 🌅 Auras
- Emoji-статусы (авто-смена)
- Динамическое BIO
- Утренний брифинг
- Переработки (21:00)

**Файлы:** `auras/__init__.py`, `auras/phrases.py`

### 9. 🔐 VPN Shop
- Автоматическая генерация VLESS ключей
- QR-коды для быстрой активации
- Интеграция с Marzban API
- SSH туннель между серверами

**Файлы:** `brains/vpn_api.py`, `main.py` (VPN Interceptor)

---

## 🔐 VPN Shop

### Настройка Marzban

**1. `/opt/marzban/.env`:**
```bash
XRAY_SUBSCRIPTION_URL_PREFIX=http://108.165.174.164:8000
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
```

**2. SSH туннель (Autossh):**
```bash
# Сервис: /etc/systemd/system/karina-tunnel.service
[Unit]
Description=Secure AutoSSH Tunnel to Marzban
After=network-online.target

[Service]
User=ai
ExecStart=/usr/bin/autossh -M 0 -N -i /home/ai/.ssh/marzban_key -L 8000:127.0.0.1:8000 root@108.165.174.164
Restart=always

[Install]
WantedBy=multi-user.target
```

**3. Запуск:**
```bash
sudo systemctl enable karina-tunnel
sudo systemctl start karina-tunnel
```

### Как работает

```
Пользователь → Бот (VPN меню) → Marzban API → VLESS ключ + QR
                ↓
            SSH туннель (8000:127.0.0.1:8000)
                ↓
         Немецкий сервер (Marzban)
```

---

## 📱 Команды бота

### 👤 Личные команды (только для владельца)
| Команда | Описание |
|---------|----------|
| `/start` | Перезапустить 🔄 |
| `/app` | Открыть Mini App 📱 |
| `/calendar` | Мои планы 📅 |
| `/conflicts` | Проверить накладки ⚠️ |
| `/health` | Статистика здоровья ❤️ |
| `/weather` | Погода 🌤 |
| `/remember` | Запомнить факт ✍️ |
| `/summary [days]` | Еженедельный отчёт 📊 |

### 📰 Новости
| Команда | Описание |
|---------|----------|
| `/news` | Новости телематики 🗞 |
| `/newsforce` | Обновить новости 🔄 |
| `/newssources` | Источники новостей 📡 |
| `/newsclear` | Очистить историю 🧹 |

### 👥 Сотрудники
| Команда | Описание |
|---------|----------|
| `/employees` | Список сотрудников 👥 |
| `/birthdays [days]` | Дни рождения 🎂 |

### 🎯 Продуктивность
| Команда | Описание |
|---------|----------|
| `/habits` | Мои привычки 🎯 |
| `/productivity [days]` | Отчёт о продуктивности 📈 |
| `/workstats [days]` | Статистика работы ⏰ |
| `/overwork [days]` | Проверка переработок ⚠️ |

### 👁️ Зрение
| Команда | Описание |
|---------|----------|
| `/vision` | Справка по зрению 👁️ |
| `/ocr` | Распознать текст 📝 |
| `/analyze` | Анализ изображения 🔍 |
| `/doc` | Анализ документа 📄 |
| `/receipt` | Анализ чека 🧾 |

### 🎤 Голосовые ответы (TTS)
| Команда | Описание |
|---------|----------|
| `/tts` | Включить/выключить голос 🎤 |
| `/ttsvoice` | Выбрать голос 🎭 |
| `/ttstest` | Тест голоса 🎤 |

### ⚙️ Настройки
| Команда | Описание |
|---------|----------|
| `/aurasettings` | Настройки аур ⚙️ |
| `/clearrc` | Очистить кэш напоминаний 🧹 |

### 🔐 VPN Shop (для всех)
| Кнопка | Описание |
|--------|----------|
| `🚀 Получить доступ` | Меню тарифов |
| `💳 1 Месяц — 150 ₽` | Тариф 1 месяц |
| `💳 3 Месяца — 400 ₽` | Тариф 3 месяца |
| `❔ Как это работает` | Информация |

---

## 🗄 База данных

### Таблицы

| Таблица | Назначение |
|---------|------------|
| `health_records` | История здоровья |
| `memories` | RAG память (векторы) |
| `reminders` | Умные напоминания |
| `aura_settings` | Настройки аур |
| `employees` | Сотрудники + ДР |
| `news_history` | История новостей |
| `habits` | Привычки |
| `work_sessions` | Рабочие сессии |
| `vision_history` | Анализ изображений |

### Миграции

```bash
docs/init.sql              # Основные таблицы
docs/init_employees.sql    # Сотрудники
docs/init_productivity.sql # Продуктивность
docs/init_news_history.sql # Новости
docs/init_vision.sql       # Зрение
```

---

## 🚀 Развёртывание

### Вариант 1: Домашний сервер (Ubuntu)

```bash
# Клонирование
git clone <repo>
cd tg-emoji-status-bot

# Виртуальное окружение
python3 -m venv karina
source karina/bin/activate

# Зависимости
pip install -r requirements.txt

# Переменные окружения
cp .env.example .env
nano .env

# Запуск
set -a && source .env && set +a
python main.py
```

### Вариант 2: Docker

```bash
docker-compose up -d
```

### Вариант 3: Railway

1. Deploy from GitHub
2. Добавить переменные окружения
3. Дождаться сборки

---

## 📊 Мониторинг

### API метрики

**Health check:**
```bash
curl http://localhost:8080/api/health
```

**Metrics:**
```bash
curl http://localhost:8080/api/metrics
```

### Логирование

**Текстовый формат (разработка):**
```bash
LOG_FORMAT=text LOG_LEVEL=INFO python main.py
```

**JSON формат (продакшен):**
```bash
LOG_FORMAT=json LOG_LEVEL=INFO python main.py
```

**Анализ логов:**
```bash
# Последние 100 строк
tail -f bot.log -n 100

# Ошибки
grep "ERROR" bot.log

# VPN продажи
grep "💰 Продажа" bot.log
```

---

## 🛡 Безопасность

### SSH туннель

**Без паролей:**
```bash
# Генерация ключа
ssh-keygen -t ed25519 -f ~/.ssh/marzban_key -N ""

# Копирование
ssh-copy-id -i ~/.ssh/marzban_key root@108.165.174.164
```

**Отключение паролей (на немецком сервере):**
```bash
sudo nano /etc/ssh/sshd_config
# PasswordAuthentication no
sudo systemctl restart ssh
```

### Rate Limiting

| Endpoint | Лимит |
|----------|-------|
| global | 100/мин |
| api/calendar | 10/мин |
| api/memory/search | 20/мин |
| api/health | 30/мин |
| api/emotion | 10/мин |

---

## 🧪 Тесты

### Запуск
```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск всех тестов
pytest tests/ -v

# Запуск с coverage
pytest tests/ -v --cov=brains --cov-report=html
```

### Покрытие

| Модуль | Тестов | Статус |
|--------|--------|--------|
| CircuitBreaker | 6 | ✅ |
| VPN API | 11 | ✅ |
| Reminders | 18 | ✅ |

---

## 📈 История версий

### v1.1 (Февраль 2026)
- ✅ VPN Shop (Marzban API)
- ✅ QR-коды для ключей
- ✅ Приватность меню команд
- ✅ SSH туннель (Autossh)
- ✅ 35 unit-тестов

### v1.0 (Ноябрь 2025)
- ✅ MVP: AI, Calendar, Health, Reminders

---

## 📞 Поддержка

- **Документация:** `docs/`
- **Логи:** `tail -f bot.log`
- **Статус:** `/api/health`
- **Release Notes:** `RELEASE_NOTES.md`

---

**Последнее обновление:** 24 февраля 2026 г.  
**Версия:** 1.1
