"""
Скрипт для получения SESSION_STRING (Telethon String Session)

Использование:
    python scripts/get_session.py

Вам понадобится:
    - API_ID и API_HASH из https://my.telegram.org
    - Номер телефона для входа в Telegram
    - Код подтверждения из Telegram
"""
import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')


async def main():
    """Генерация session string"""
    if not API_ID or not API_HASH:
        print("❌ API_ID и API_HASH не установлены!")
        print("   Заполните .env файл или установите переменные окружения")
        return

    print("=" * 60)
    print("📱 TELETHON SESSION STRING GENERATOR")
    print("=" * 60)
    print()
    print("Этот скрипт создаст SESSION_STRING для подключения к Telegram")
    print("как пользователь (userbot).")
    print()
    print("Вам потребуется:")
    print("  1. Ввести номер телефона (с +7...)")
    print("  2. Ввести код из Telegram (придет в приложение)")
    print("  3. Ввести пароль двухфакторной аутентификации (если включен)")
    print()
    print("=" * 60)
    print()

    async with TelegramClient(
        StringSession(),
        API_ID,
        API_HASH
    ) as client:
        print("✅ Сессия создана!")
        print()
        print("📋 SESSION_STRING (скопируйте в .env):")
        print("-" * 60)
        print(client.session.save())
        print("-" * 60)
        print()
        print("Добавьте эту строку в .env файл:")
        print(f"SESSION_STRING={client.session.save()}")
        print()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Отменено пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
