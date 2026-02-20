# 🏠 Karina AI — Развёртывание на домашнем сервере (Ubuntu 22.04)

## 📋 Требования

- **CPU**: 4+ ядра (лучше 8)
- **RAM**: 16GB+ (для LLM 7B)
- **GPU**: Опционально (NVIDIA для ускорения)
- **Диск**: 50GB+ (LLM + данные)
- **OS**: Ubuntu 22.04 LTS

---

## 🚀 Быстрый старт

### 1. Обновление системы
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Установка Docker
```bash
sudo apt install docker.io docker-compose -y
sudo usermod -aG docker $USER
# Перелогинься для применения
```

### 3. Установка Ollama (локальная LLM)
```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull mistral:7b  # 4.1GB модель
```

### 4. Установка PostgreSQL + pgvector
```bash
sudo apt install postgresql postgresql-contrib -y

# pgvector для RAG
sudo apt install postgresql-server-dev-all -y
cd /tmp
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### 5. Клонирование проекта
```bash
cd ~
git clone https://github.com/your-username/tg-emoji-status-bot.git
cd tg-emoji-status-bot
```

### 6. Создание .env файла
```bash
cp .env.example .env
nano .env  # Отредактируй переменные
```

### 7. Запуск
```bash
# Установка зависимостей
pip3 install -r requirements.txt

# Запуск бота
python3 main.py
```

---

## 🔧 Детальная настройка

### PostgreSQL

```sql
-- Создание пользователя и базы
sudo -u postgres psql

CREATE DATABASE karina_db;
CREATE USER karina_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE karina_db TO karina_user;
\q

# Создание таблицы health_records
sudo -u postgres psql karina_db

CREATE TABLE IF NOT EXISTS health_records (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    confirmed BOOLEAN DEFAULT true,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    date DATE DEFAULT CURRENT_DATE,
    time TIME DEFAULT CURRENT_TIME,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_health_date ON health_records(date DESC);
CREATE INDEX idx_health_user ON health_records(user_id);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);

\q
```

### Ollama API

Создай файл `brains/ollama_client.py`:

```python
import httpx
import logging

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral:7b"

async def generate_text(prompt: str, system: str = None) -> str:
    """Генерация текста через локальную Ollama"""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "top_p": 0.9
        }
    }
    
    if system:
        payload["system"] = system
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OLLAMA_URL, json=payload)
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        return None
```

---

## 📝 .env файл

```bash
# Telegram
API_ID=12345678
API_HASH=your_api_hash
SESSION_STRING=your_session_string
KARINA_BOT_TOKEN=your_bot_token

# AI (локальный)
USE_LOCAL_AI=true
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b

# Если хочешь оставить Mistral (резерв)
MISTRAL_API_KEY=your_key

# Database (локальный PostgreSQL)
DATABASE_URL=postgresql://karina_user:your_password@localhost:5432/karina_db
SUPABASE_URL=http://localhost:5432
SUPABASE_KEY=your_password

# Google Calendar
GOOGLE_CALENDAR_CREDENTIALS={"type":"service_account",...}

# Voice (Hugging Face)
HF_TOKEN=your_token

# Weather
WEATHER_API_KEY=your_key
WEATHER_CITY=Moscow

# User IDs
MY_TELEGRAM_ID=your_id
TARGET_USER_ID=target_id
```

---

## 🐳 Docker Compose (опционально)

Создай `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: karina_db
      POSTGRES_USER: karina_user
      POSTGRES_PASSWORD: your_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    restart: unless-stopped
    # Для GPU:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  karina-bot:
    build: .
    environment:
      - DATABASE_URL=postgresql://karina_user:your_password@postgres:5432/karina_db
      - OLLAMA_URL=http://ollama:11434
    volumes:
      - ./data:/app/data
    depends_on:
      - postgres
      - ollama
    restart: unless-stopped

volumes:
  postgres_data:
  ollama_data:
```

Запуск:
```bash
docker-compose up -d
```

---

## 🔍 Мониторинг

### Логи
```bash
# Бот
journalctl -u karina-bot -f

# Ollama
journalctl -u ollama -f

# PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-*.log
```

### Ресурсы
```bash
# CPU/RAM
htop

# GPU (если NVIDIA)
nvidia-smi

# Диск
df -h
```

---

## 🛡 Безопасность

### Firewall
```bash
sudo ufw enable
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 5432/tcp  # PostgreSQL (только локально!)
# Не открывай 11434 наружу!
```

### Автоматический старт
```bash
# Создай systemd сервис
sudo nano /etc/systemd/system/karina-bot.service
```

```ini
[Unit]
Description=Karina AI Bot
After=network.target postgresql.service ollama.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/tg-emoji-status-bot
ExecStart=/usr/bin/python3 /home/your_user/tg-emoji-status-bot/main.py
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

## 📊 Сравнение: Railway vs Домашний сервер

| Параметр | Railway | Домашний сервер |
|----------|---------|-----------------|
| **Стоимость** | $5-20/мес | ~$2-5/мес (электричество) |
| **CPU** | Ограничено | Полный доступ |
| **RAM** | Ограничено | Полный доступ |
| **LLM** | Только API | Любая локальная |
| **Безопасность** | Облако | Полный контроль |
| **Надёжность** | 99.9% | Зависит от тебя |
| **Масштаб** | Легко | Нужно самому |

---

## 🎯 Рекомендации

### Для начала:
1. **Ollama + mistral:7b** — достаточно для напоминаний
2. **PostgreSQL локально** — вместо Supabase
3. **Docker** — для простоты развёртывания

### Для продакшена:
1. **vLLM** — быстрее Ollama
2. **GPU** — NVIDIA RTX 3060+ (12GB VRAM)
3. **Reserve proxy** — для доступа извне

---

## 🆘 Troubleshooting

### Ollama не запускается
```bash
ollama serve  # Вручную
journalctl -u ollama -f  # Логи
```

### PostgreSQL не подключается
```bash
sudo systemctl status postgresql
sudo tail -f /var/log/postgresql/postgresql-*.log
```

### Бот не отвечает
```bash
sudo systemctl status karina-bot
sudo journalctl -u karina-bot -f
```

### Нехватка RAM
```bash
# Используй меньшую модель
ollama pull mistral:7b-instruct-q4_K_M  # 2.5GB вместо 4.1GB
```

---

**Готово!** 🎉 Теперь Karina работает на твоём сервере без лимитов!

(karina) ai@ai-node:~/tg-emoji-status-bot$ git pull origin main
remote: Enumerating objects: 426, done.
remote: Counting objects: 100% (426/426), done.
remote: Compressing objects: 100% (182/182), done.
remote: Total 426 (delta 230), reused 416 (delta 220), pack-reused 0 (from 0)
Receiving objects: 100% (426/426), 1.38 MiB | 55.00 KiB/s, done.
Resolving deltas: 100% (230/230), done.
From https://github.com/RivixXx/tg-emoji-status-bot
 * branch            main       -> FETCH_HEAD
 + 7925fd1...7775ea7 main       -> origin/main  (forced update)
hint: You have divergent branches and need to specify how to reconcile them.
hint: You can do so by running one of the following commands sometime before
hint: your next pull:
hint:
hint:   git config pull.rebase false  # merge (the default strategy)
hint:   git config pull.rebase true   # rebase
hint:   git config pull.ff only       # fast-forward only
hint:
hint: You can replace "git config" with "git config --global" to set a default
hint: preference for all repositories. You can also pass --rebase, --no-rebase,
hint: or --ff-only on the command line to override the configured default per
hint: invocation.
fatal: Need to specify how to reconcile divergent branches.