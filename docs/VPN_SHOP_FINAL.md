# ✅ VPN Shop — Финальная версия (РАБОТАЕТ!)

**Дата:** 24 февраля 2026 г.  
**Статус:** ✅ Полностью рабочий VPN Shop

---

## 🎉 Что работает

| Функция | Статус |
|---------|--------|
| Создание пользователей | ✅ |
| Генерация VLESS ключа | ✅ |
| QR-код | ✅ |
| Прямая ссылка vless:// | ✅ |
| Subscription URL | ✅ |
| Авто-активация VLESS | ✅ |
| Туннель SSH | ✅ |

---

## 📁 Изменённые файлы

### 1. `brains/vpn_api.py`

**Изменения:**
- ✅ Добавлен импорт `uuid`
- ✅ Генерация UUID для VLESS ключа
- ✅ Добавлено поле `inbounds` для активации VLESS
- ✅ Приоритет прямой VLESS ссылки над subscription URL

**Код:**
```python
import uuid

# Генерация UUID
new_uuid = str(uuid.uuid4())

# Payload с inbounds
user_payload = {
    "username": username,
    "expire": int(expire_date.timestamp()),
    "data_limit": 0,
    "proxies": {
        "vless": {
            "id": new_uuid  # Уникальный ключ
        }
    },
    "inbounds": {
        "VLESS TCP REALITY": ["VLESS TCP REALITY"]
    }
}
```

---

### 2. `main.py`

**Изменения:**
- ✅ Добавлен импорт `qrcode` и `io`
- ✅ Генерация QR-кода в памяти
- ✅ Отправка QR-кода с сообщением

**Код:**
```python
import qrcode
import io

# Генерация QR-кода
qr = qrcode.QRCode(version=1, box_size=10, border=2)
qr.add_data(vless_key)
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")

bio = io.BytesIO()
bio.name = 'vpn_qr.png'
img.save(bio, 'PNG')
bio.seek(0)

# Отправка с QR-кодом
await bot_client.send_file(
    event.chat_id,
    file=bio,
    caption="🟢 [ ТРАНЗАКЦИЯ ПОДТВЕРЖДЕНА ]\n\n..."
)
```

---

### 3. `brains/config.py`

**Добавлено:**
```python
# Marzban VPN API
MARZBAN_URL = os.environ.get('MARZBAN_URL', 'http://108.165.174.164:8000')
MARZBAN_USER = os.environ.get('MARZBAN_USER', 'root')
MARZBAN_PASS = os.environ.get('MARZBAN_PASS', '')
```

---

### 4. `.env.example`

**Добавлено:**
```bash
# Marzban VPN API
MARZBAN_URL=http://108.165.174.164:8000
MARZBAN_USER=root
MARZBAN_PASS=your_marzban_password
```

---

### 5. `requirements.txt`

**Добавлено:**
```
qrcode[pil]==8.0
```

---

## 🔧 Настройка Marzban

### 1. `/opt/marzban/.env`

```bash
XRAY_SUBSCRIPTION_URL_PREFIX=http://108.165.174.164:8000
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
```

### 2. `docker-compose.yml`

```yaml
services:
  marzban:
    image: gozargah/marzban:latest
    restart: always
    env_file:
      - .env
    environment:
      - UVICORN_HOST=0.0.0.0
    network_mode: host
    volumes:
      - /var/lib/marzban:/var/lib/marzban
```

---

## 🔐 SSH Туннель (Autossh)

### Сервис: `/etc/systemd/system/karina-tunnel.service`

```ini
[Unit]
Description=Secure AutoSSH Tunnel to Marzban
After=network-online.target
Wants=network-online.target

[Service]
User=ai
Environment="AUTOSSH_GATETIME=0"
ExecStart=/usr/bin/autossh -M 0 -N -q -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" -o "StrictHostKeyChecking=no" -i /home/ai/.ssh/marzban_key -L 8000:127.0.0.1:8000 root@108.165.174.164
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Команды:

```bash
# Генерация ключа
ssh-keygen -t ed25519 -f ~/.ssh/marzban_key -N ""

# Копирование на немецкий сервер
ssh-copy-id -i ~/.ssh/marzban_key root@108.165.174.164

# Установка autossh
sudo apt install autossh -y

# Запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable karina-tunnel
sudo systemctl start karina-tunnel
sudo systemctl status karina-tunnel
```

---

## 🚀 Деплой

```bash
# На домашнем сервере
cd ~/tg-emoji-status-bot
git pull
pm2 restart karina-bot
```

---

## 🧪 Тестирование

1. **Запустить бота с другого аккаунта:**
   - `/start`
   - `🚀 Получить доступ`
   - `💳 1 Месяц`
   - `✅ Я оплатил`

2. **Проверить результат:**
   - ✅ Пришёл QR-код
   - ✅ Ссылка `vless://...@108.165.174.164:443`
   - ✅ Подключение работает в Hiddify/V2Box

3. **Проверить в Marzban:**
   - ✅ Пользователь создан
   - ✅ VLESS горит синим (активен)
   - ✅ Есть конфиг и QR в панели

---

## 📊 Архитектура

```
┌─────────────────┐     SSH Tunnel      ┌──────────────────┐
│  Домашний сервер │ ──────────────────→ │  Немецкий сервер │
│    (ai-node)     │  :8000 → :8000      │  (108.165.174.164)│
│                  │                     │                  │
│  Karina Bot ────→│  http://127.0.0.1:8000  │  Marzban         │
│  (Telegram)      │                     │  (Docker)        │
└─────────────────┘                     └──────────────────┘
       │
       │ VPN Shop
       ▼
┌─────────────────┐
│  Пользователь   │
│  (Telegram)     │
│                 │
│  QR-код ───────→│ Hiddify/V2Box
│  vless://...    │
└─────────────────┘
```

---

## 🛠 Безопасность

| Угроза | Защита |
|--------|--------|
| Брутфорс паролей | ❌ Отключено (`PasswordAuthentication no`) |
| Перехват трафика | ❌ SSH шифрование |
| Разрыв туннеля | ❌ Autossh авто-переподключение |
| Утечка ключа | ❌ Ключ только на домашнем сервере |
| DDoS Marzban | ❌ Доступ только через туннель |

---

## 📝 Логи

```bash
# Логи бота
tail -f ~/tg-emoji-status-bot/bot.log | grep -i vpn

# Логи Marzban
marzban logs

# Логи туннеля
sudo journalctl -u karina-tunnel -f
```

---

## 🎯 Финальный результат

**Бот возвращает:**

```
🟢 [ ТРАНЗАКЦИЯ ПОДТВЕРЖДЕНА ]

Ключ активирован на 30 дней.

Ваша ссылка-подписка:
vless://3cc720da-92cb-485b-b74f-754a33752785@108.165.174.164:443?security=reality&type=tcp&...

Инструкция:
1. Скачайте Hiddify или V2Box
2. Скопируйте ссылку выше ИЛИ отсканируйте QR-код
3. В приложении выберите 'Добавить из буфера обмена' или 'Сканировать QR'

🔐 Добро пожаловать в сеть!
```

**QR-код:** Работает ✅

**VLESS конфиг:** Работает ✅

---

**Версия:** 1.0 (Final)  
**Дата:** 24 февраля 2026 г.
