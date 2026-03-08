"""
VPN Shop Logic — Обработчики событий VPN-магазина
"""
import os
import io
import time
import json
import logging
import asyncio
import qrcode
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, errors
import httpx

from brains.vpn_ui import (
    inline_main_menu, inline_back, inline_tariffs, inline_profile,
    inline_instructions, inline_support,
    text_welcome, text_profile, text_tariffs, text_payment, text_keys,
    text_instruction
)

logger = logging.getLogger(__name__)

# ========== КОНФИГ ==========
MARZBAN_URL = os.environ.get('MARZBAN_URL', 'http://127.0.0.1:8000')
MARZBAN_USER = os.environ.get('MARZBAN_USER', 'admin')
MARZBAN_PASS = os.environ.get('MARZBAN_PASS', '')

# ========== КЭШ БАННЕРОВ (СОХРАНЕНИЕ НА ДИСК) ==========
CACHE_FILE = "banners_cache.json"
FILE_ID_CACHE = {}

# Пытаемся прочитать сохраненные ID при запуске
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r") as f:
            FILE_ID_CACHE = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения кэша с диска: {e}")

BANNER_PATHS = {
    "menu": "banners/menu.jpg",
    "support": "banners/support.jpg",
    "instructions": "banners/instructions.jpg",
    "profile": "banners/menu.jpg",
    "shop": "banners/menu.jpg"
}

# ========== VPN USERS (хранилище в памяти) ==========
VPN_USERS = {}

# ========== HTTP КЛИЕНТ ==========
http = httpx.AsyncClient(timeout=30.0)


# ========== УТИЛИТЫ ==========
def log_timing(step_name: str, start_time: float):
    elapsed = (time.time() - start_time) * 1000
    logger.info(f"⏱ {step_name}: {elapsed:.2f}ms")


# ========== БАННЕРЫ ==========
async def preload_banners(bot: TelegramClient, my_id: int):
    """
    Загружает баннеры 1 раз в жизни бота и навсегда сохраняет их file_id в json.
    """
    logger.info("🖼 Проверка кэша баннеров на диске...")
    changed = False
    uploaded_paths = {}  # Чтобы не грузить одну и ту же картинку (например, menu.jpg) дважды

    for banner_name, file_path in BANNER_PATHS.items():
        if banner_name not in FILE_ID_CACHE:
            if os.path.exists(file_path):
                # Если этот файл уже загрузили для другой кнопки
                if file_path in uploaded_paths:
                    FILE_ID_CACHE[banner_name] = uploaded_paths[file_path]
                    changed = True
                    continue

                logger.info(f"⏳ ЗАГРУЖАЮ '{banner_name}' ОДИН РАЗ НАВСЕГДА (займет ~45 сек)...")
                try:
                    msg = await bot.send_file(my_id, file=file_path)
                    FILE_ID_CACHE[banner_name] = msg.file.id  # Сохраняем текстовый ID
                    uploaded_paths[file_path] = msg.file.id
                    changed = True
                    logger.info(f"✅ Баннер '{banner_name}' успешно загружен!")
                except Exception as e:
                    logger.error(f"❌ Ошибка предзагрузки баннера '{banner_name}': {e}")
            else:
                logger.warning(f"⚠️ Файл для баннера не найден: {file_path}")

    if changed:
        with open(CACHE_FILE, "w") as f:
            json.dump(FILE_ID_CACHE, f)
        logger.info("💾 Кэш баннеров сохранен в banners_cache.json! Больше загрузок не будет.")
    else:
        logger.info("⚡ Все баннеры найдены на диске! Загрузка мгновенная.")


async def get_cached_banner(bot: TelegramClient, banner_name: str, my_id: int):
    # Мгновенно отдаем сохраненный текстовый ID из памяти
    return FILE_ID_CACHE.get(banner_name)


async def send_banner(bot, event, banner_name: str, caption: str, buttons, user_id, my_id: int):
    banner_file_id = await get_cached_banner(bot, banner_name, my_id)
    try:
        if isinstance(event, events.CallbackQuery.Event):
            if banner_file_id:
                await event.edit(caption, buttons=buttons, file=banner_file_id, parse_mode='md')
            else:
                await event.edit(caption, buttons=buttons, parse_mode='md')
        else:
            if banner_file_id:
                await bot.send_file(event.chat_id, file=banner_file_id, caption=caption, buttons=buttons, parse_mode='md')
            else:
                await event.respond(caption, buttons=buttons, parse_mode='md')
    except errors.MessageNotModifiedError:
        pass
    except Exception as e:
        logger.error(f"❌ Ошибка баннера: {e}")
        await event.respond(caption, buttons=buttons, parse_mode='md')


# ========== MARZBAN ==========
async def get_marzban_token():
    start = time.time()
    try:
        resp = await http.post(
            f"{MARZBAN_URL}/api/admin/token",
            data={"username": MARZBAN_USER, "password": MARZBAN_PASS}
        )
        log_timing("Marzban: токен", start)
        if resp.status_code == 200:
            return resp.json().get("access_token")
        return None
    except Exception as e:
        logger.error(f"❌ Marzban token: {e}")
        return None


async def create_marzban_user(username: str, days: int = 30):
    start = time.time()
    logger.info(f"🔧 Marzban: создание {username} на {days} дн.")
    
    token = await get_marzban_token()
    if not token:
        return None
    
    try:
        expire = int((datetime.now() + timedelta(days=days)).timestamp())
        resp = await http.post(
            f"{MARZBAN_URL}/api/user",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": username, "inbound_tags": ["VLESS"], "expire": expire, "data_limit": 0}
        )
        log_timing("Marzban: создание", start)
        
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"✅ Marzban: пользователь создан")
            return {
                "username": data.get("username"),
                "vless": data.get("links", {}).get("VLESS", ""),
                "expire": datetime.fromtimestamp(expire)
            }
        logger.error(f"❌ Marzban: {resp.status_code}")
        return None
    except Exception as e:
        logger.error(f"❌ Marzban error: {e}")
        return None


async def generate_vless_key(user_id: int, days: int = 1, device: str = "phone"):
    start = time.time()
    
    device_map = {"Телефон": "phone", "Ноутбук": "laptop", "Планшет": "tablet", "Тест": "trial"}
    device_en = device_map.get(device, device.lower().replace(" ", "_"))
    username = f"vpn_{user_id}_{int(time.time())}_{device_en}"[:32]
    
    user_data = await create_marzban_user(username, days)
    if user_data:
        log_timing("Генерация ключа", start)
        return {
            "key": user_data["vless"],
            "username": user_data["username"],
            "expire": user_data["expire"],
            "device": device,
            "days": days
        }
    return None


# ========== РЕГИСТРАЦИЯ ХЭНДЛЕРОВ ==========
def register_vpn_handlers(bot: TelegramClient, my_id: int):
    """Регистрирует все обработчики VPN-магазина"""
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        start_time = time.time()
        user_id = event.sender_id

        logger.info("=" * 60)
        logger.info(f"📥 /start от {user_id}")

        if user_id == my_id:
            await event.respond("👋 Привет, Михаил! Я Карина, твой AI-ассистент.\n\n💬 Пиши — отвечу!\n⚙️ Команды: /help")
            return

        # Клиент — VPN магазин
        if user_id not in VPN_USERS:
            VPN_USERS[user_id] = {
                "state": "NEW",
                "trial_used": False,
                "balance": 0,
                "keys": [],
                "joined": datetime.now()
            }

        await send_banner(bot, event, "menu", text_welcome(user_id), inline_main_menu(), user_id, my_id)
        log_timing("Обработка /start", start_time)

    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        start_time = time.time()
        user_id = event.sender_id
        data = event.data.decode('utf-8')

        logger.info(f"📥 Кнопка '{data}' от {user_id}")

        # Игнорируем кнопки VPN-магазина от владельца
        # (у владельца свои AI-кнопки с префиксом ai_)
        if user_id == my_id and data.startswith("vpn_"):
            await event.answer("⚙️ Это для клиентов", alert=True)
            return

        if user_id not in VPN_USERS:
            VPN_USERS[user_id] = {
                "state": "NEW",
                "trial_used": False,
                "balance": 0,
                "keys": [],
                "joined": datetime.now()
            }

        user = VPN_USERS[user_id]

        # ⚡ СРАЗУ отвечаем на callback query, чтобы ID не истёк во время загрузки баннера
        await event.answer()

        # Навигация
        if data == "main_menu":
            await send_banner(bot, event, "menu", text_welcome(user_id), inline_main_menu(), user_id, my_id)

        elif data == "profile_menu":
            await send_banner(
                bot, event, "profile", text_profile(user_id, user),
                inline_profile(len(user.get("keys", [])) > 0), user_id, my_id
            )

        elif data == "shop_tariffs":
            await send_banner(bot, event, "shop", text_tariffs(), inline_tariffs(), user_id, my_id)

        elif data == "trial_activate":
            if user.get("trial_used"):
                await event.answer("❌ Тест уже использован", alert=True)
            else:
                await event.answer("🎁 Активация...", alert=False)
                key_data = await generate_vless_key(user_id, days=1, device="trial")
                if key_data:
                    user["trial_used"] = True
                    user["keys"].append(key_data)
                    await event.edit(
                        f"🎉 **Тест активирован!**\n\n🔑 Ключ:\n`{key_data['key']}`\n\n⏱ Срок: 24 часа",
                        buttons=inline_back()
                    )
                else:
                    await event.answer("❌ Ошибка", alert=True)

        elif data.startswith("tariff_"):
            months_map = {"tariff_1": (1, 150), "tariff_3": (3, 400), "tariff_6": (6, 750)}
            months, amount = months_map.get(data, (1, 150))
            await send_banner(
                bot, event, "shop", text_payment(amount, months),
                [[Button.inline(f"💰 Оплатить {amount}₽", b"pay_confirm")], [Button.inline("◀️ Назад", b"shop_tariffs")]],
                user_id, my_id
            )

        elif data == "pay_confirm":
            await event.answer("⏳ Обработка...", alert=False)
            await asyncio.sleep(2)

            months = 1
            keys = []
            for device in ["Телефон", "Ноутбук", "Планшет"]:
                key_data = await generate_vless_key(user_id, days=months * 30, device=device)
                if key_data:
                    keys.append(key_data)

            if keys:
                user["keys"].extend(keys)

                qr = qrcode.QRCode(version=1, box_size=10, border=2)
                qr.add_data(keys[0]["key"])
                img = qr.make_image(fill_color="black", back_color="white")
                bio = io.BytesIO()
                bio.name = 'vpn_qr.png'
                img.save(bio, 'PNG')
                bio.seek(0)

                caption = f"🟢 **ОПЛАТА ПОДТВЕРЖДЕНА**\n\n🔑 **Ключи:**\n"
                for i, key in enumerate(keys, 1):
                    caption += f"\n**{i}. {key['device']}:**\n`{key['key']}`"

                await bot.send_file(user_id, file=bio, caption=caption, buttons=inline_profile(True))
            else:
                await event.answer("❌ Ошибка", alert=True)

        elif data == "my_keys":
            await send_banner(bot, event, "profile", text_keys(user.get("keys", [])), inline_back(), user_id, my_id)

        elif data == "balance":
            await event.answer(f"💳 Баланс: {user.get('balance', 0)}₽", alert=True)

        elif data == "history":
            await event.answer("📜 История пуста", alert=True)

        elif data.startswith("instr_"):
            platform_map = {
                "instr_ios": "ios",
                "instr_android": "android",
                "instr_windows": "windows",
                "instr_macos": "macos"
            }
            platform = platform_map.get(data, "ios")
            await event.answer(text_instruction(platform), alert=True)

        elif data == "support_ask":
            await event.answer("✍️ Напишите ваш вопрос в чат", alert=True)

        elif data == "support_menu":
            await send_banner(bot, event, "support", "💬 **Поддержка**\n\nНапишите ваш вопрос.", inline_support(), user_id, my_id)

        elif data == "faq_menu":
            await event.answer("❓ FAQ: В разработке", alert=True)

        elif data == "instructions_menu":
            await send_banner(bot, event, "instructions", "📖 **Инструкции**\n\nВыберите устройство:", inline_instructions(), user_id, my_id)

        else:
            await event.answer("🤔 В разработке", alert=True)

        log_timing(f"Обработка '{data}'", start_time)
