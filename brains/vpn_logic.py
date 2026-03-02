import asyncio
import logging
import time
import io
import qrcode
from telethon import events, Button, TelegramClient
from brains.config import MY_ID
from brains.media import media_manager
from brains.payment import payment_manager
from brains.alerts import notify_new_user, notify_sale, notify_trial, notify_system_error
from brains.mcp_vpn_shop import (
    mcp_vpn_get_user,
    mcp_vpn_create_user,
    mcp_vpn_update_user_state
)
from brains.vpn_ui import (
    BANNER_FILES,
    get_main_menu_text,
    get_main_menu_keyboard,
    get_profile_text,
    get_tariffs_text,
    get_tariffs_keyboard,
    get_instructions_text,
    get_platform_keyboard,
    get_back_keyboard,
    get_payment_methods_keyboard,
    get_after_purchase_keyboard,
    get_trial_success_text
)

logger = logging.getLogger(__name__)

# ========== КЭШ ДЛЯ СКОРОСТИ (УРОВЕНЬ 1) ==========
USER_CACHE = {}
CACHE_TTL = 300 # 5 минут

async def get_user_fast(user_id):
    """Мгновенно отдает юзера из памяти или запрашивает из БД"""
    now = time.time()
    if user_id in USER_CACHE and (now - USER_CACHE[user_id]['time'] < CACHE_TTL):
        return USER_CACHE[user_id]['data']
    
    user = await mcp_vpn_get_user(user_id)
    if user:
        USER_CACHE[user_id] = {'data': user, 'time': now}
    return user

def update_user_cache(user_id, updates):
    """Обновляет кэш локально"""
    if user_id in USER_CACHE:
        USER_CACHE[user_id]['data'].update(updates)
        USER_CACHE[user_id]['time'] = time.time()

# Ссылка на функцию fire_and_forget
_fire_and_forget_ref = None

def set_fire_and_forget(func):
    global _fire_and_forget_ref
    _fire_and_forget_ref = func

def fire_and_forget(coro):
    if _fire_and_forget_ref:
        _fire_and_forget_ref(coro)
    else:
        asyncio.create_task(coro)

async def issue_vpn_key(bot_client, user_id, months=1, is_trial=False, amount=0):
    """Единая логика генерации и выдачи ключа с Onboarding-элементами"""
    from brains.vpn_api import check_payment_and_issue_key
    
    try:
        # Для триала передаем 0 месяцев
        result = await check_payment_and_issue_key(user_id, 0 if is_trial else months)
        
        if result.get("success"):
            vless_key = result.get("vless_key")
            expire_days = result.get("expire_days", 1 if is_trial else 30 * months)

            # Генерация QR
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(vless_key)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            bio.name = 'vpn_qr.png'
            img.save(bio, 'PNG')
            bio.seek(0)

            if is_trial:
                caption = f"{get_trial_success_text()}\n`{vless_key}`"
                fire_and_forget(notify_trial(bot_client, user_id))
            else:
                caption = f"🚀 **ПОДПИСКА АКТИВИРОВАНА!**\n\nДоступ открыт на **{expire_days} дней**.\n\nТвой ключ:\n`{vless_key}`\n\n*Нажми на ключ выше, чтобы скопировать.*"
                fire_and_forget(notify_sale(bot_client, user_id, amount, months))

            await bot_client.send_file(
                user_id, file=bio,
                caption=caption,
                buttons=get_after_purchase_keyboard()
            )
            return True
    except Exception as e:
        logger.error(f"Failed to issue key: {e}")
        fire_and_forget(notify_system_error(bot_client, "VPN_API", str(e)))
    return False

def register_vpn_handlers(bot_client: TelegramClient):
    """Регистрирует все обработчики VPN в боте"""

    @bot_client.on(events.NewMessage(func=lambda e: e.is_private and e.sender_id != MY_ID))
    async def vpn_stranger_interceptor(event):
        user_id = event.sender_id
        text = event.text.strip() if event.text else ""
        
        # ЕСЛИ ЭТО НЕ КОМАНДА /start И НЕ ДРУГАЯ VPN КОМАНДА - ПРОПУСКАЕМ К ИИ
        if not text.startswith('/start') and not text.startswith('/vpn'):
            return

        user = await get_user_fast(user_id)
        if not user:
            referred_by = None
            if text.startswith('/start') and len(text.split()) > 1:
                try: referred_by = int(text.split()[1])
                except: pass
            user = await mcp_vpn_create_user(user_id, referred_by=referred_by)
            # Алерт о новом юзере
            sender = await event.get_sender()
            first_name = sender.first_name if sender and sender.first_name else "Unknown"
            fire_and_forget(notify_new_user(bot_client, user_id, first_name))
        
        state = user["state"]

        if state == "NEW":
            welcome_text = "📄 **Публичная оферта**\n\nДля использования VPN необходимо принять условия сервиса."
            keyboard = [[Button.inline("✅ Принимаю условия", b"accept_offer")], [Button.inline("❌ Отменить", b"decline_offer")]]
            await event.respond(welcome_text, buttons=keyboard)
            raise events.StopPropagation

        elif state == "REGISTERED":
            await event.respond(get_main_menu_text(user), buttons=get_main_menu_keyboard())
            raise events.StopPropagation

    @bot_client.on(events.CallbackQuery(func=lambda e: e.sender_id != MY_ID))
    async def vpn_callback_handler(event):
        user_id = event.sender_id
        data = event.data.decode('utf-8')
        user = await get_user_fast(user_id)

        if data == "accept_offer":
            update_user_cache(user_id, {"state": "REGISTERED"})
            fire_and_forget(mcp_vpn_update_user_state(user_id, "REGISTERED"))
            await event.delete()
            await media_manager.send_banner(bot_client, user_id, "MENU", BANNER_FILES["MENU"], get_main_menu_text(user), get_main_menu_keyboard())
            raise events.StopPropagation()

        elif data == "menu_main" or data == "menu_back":
            await event.delete()
            await media_manager.send_banner(bot_client, user_id, "MENU", BANNER_FILES["MENU"], get_main_menu_text(user), get_main_menu_keyboard())
            raise events.StopPropagation()

        elif data == "menu_tariffs":
            await event.edit(get_tariffs_text(), buttons=get_tariffs_keyboard())
            raise events.StopPropagation()

        elif data == "buy_trial":
            if user.get("trial_used"):
                await event.answer("⚠️ Вы уже использовали тестовый период!", alert=True)
                raise events.StopPropagation()
            
            await event.edit("⏳ **Генерирую тестовый доступ...**")
            success = await issue_vpn_key(bot_client, user_id, is_trial=True)
            if success:
                update_user_cache(user_id, {"trial_used": True})
                fire_and_forget(mcp_vpn_update_user_state(user_id, "REGISTERED", trial_used=True))
                logger.info(f"🎁 Trial activated for {user_id}")
            else:
                await event.edit("❌ Не удалось выдать тест. Попробуйте позже.")
            raise events.StopPropagation()

        elif data.startswith("pay_"):
            months = int(data.split("_")[1])
            amount = 150 if months == 1 else (400 if months == 3 else 750)
            await event.edit(f"💳 **Выбор метода оплаты: {amount} ₽**", buttons=get_payment_methods_keyboard(amount, months))
            raise events.StopPropagation()

        elif data.startswith("pay_crypto_"):
            parts = data.split("_")
            months, amount = int(parts[2]), int(parts[3])
            
            await event.edit("⏳ **Связываюсь с CryptoBot...**")
            invoice = await payment_manager.create_invoice(amount, user_id=user_id)
            
            if invoice:
                keyboard = [
                    [Button.url("🔗 Оплатить в CryptoBot", invoice["pay_url"])],
                    [Button.inline("✅ Я оплатил (Проверить)", f"check_inv_{invoice['invoice_id']}_{months}_{amount}".encode())],
                    [Button.inline("◀️ Отмена", b"menu_tariffs")]
                ]
                await event.edit(f"✅ **Счет готов!**\n\nСумма: `{invoice['amount']} {invoice['asset']}`\n\nНажми на кнопку ниже, чтобы перейти к оплате. Ключ придет сразу после подтверждения.", buttons=keyboard)
            else:
                await event.edit("❌ Ошибка платежного шлюза. Попробуйте другой метод.")
            raise events.StopPropagation()

        elif data.startswith("check_inv_"):
            parts = data.split("_")
            inv_id, months, amount = int(parts[2]), int(parts[3]), int(parts[4])
            
            is_paid = await payment_manager.check_invoice(inv_id)
            if is_paid:
                await event.edit("🎉 **Оплата подтверждена!** Подготавливаю ключ...")
                await issue_vpn_key(bot_client, user_id, months=months, amount=amount)
            else:
                await event.answer("⌛️ Транзакция еще в обработке. Подождите немного...", alert=True)
            raise events.StopPropagation()

        elif data == "menu_profile":
            await event.edit(get_profile_text(user), buttons=get_back_keyboard(main=True))
            raise events.StopPropagation()

        elif data == "menu_instructions":
            await event.delete()
            await media_manager.send_banner(bot_client, user_id, "INSTRUCTIONS", BANNER_FILES["INSTRUCTIONS"], get_instructions_text(), get_platform_keyboard())
            raise events.StopPropagation()

        elif data == "get_my_key":
            await event.answer("🔍 Проверяю подписку...", alert=False)
            await issue_vpn_key(bot_client, user_id)
            raise events.StopPropagation()

        else:
            await event.answer("👌", alert=False)
            raise events.StopPropagation()
