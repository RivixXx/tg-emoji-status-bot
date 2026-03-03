"""
KARINA AI — Главный файл запуска
Запускает VPN магазин
"""
import os
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Проверка конфига
API_ID = os.environ.get('API_ID')
BOT_TOKEN = os.environ.get('KARINA_BOT_TOKEN')

if not API_ID or not BOT_TOKEN:
    print("❌ ЗАПОЛНИ .env: API_ID, KARINA_BOT_TOKEN")
    exit(1)

# Импортируем и запускаем VPN магазин
from vpn_shop import main

if __name__ == '__main__':
    logging.info("🚀 KARINA VPN SHOP — ЗАПУСК")
    asyncio.run(main())
