import logging
from telethon import TelegramClient
from brains.config import MY_ID

logger = logging.getLogger(__name__)

async def send_admin_alert(client: TelegramClient, message: str):
    """Отправляет уведомление администратору (владельцу)"""
    try:
        await client.send_message(MY_ID, f"🔔 **[ADMIN ALERT]**\n\n{message}")
    except Exception as e:
        logger.error(f"Failed to send admin alert: {e}")

async def notify_new_user(client: TelegramClient, user_id: int, name: str):
    msg = f"""🆕 **Новый пользователь!**
👤 Имя: {name}
🆔 ID: `{user_id}`"""
    await send_admin_alert(client, msg)

async def notify_sale(client: TelegramClient, user_id: int, amount: float, months: int):
    msg = f"""💰 **УСПЕШНАЯ ПРОДАЖА!**

👤 Юзер: `{user_id}`
💵 Сумма: `{amount} ₽`
📅 Срок: `{months} мес.`

🚀 Работаем!"""
    await send_admin_alert(client, msg)

async def notify_trial(client: TelegramClient, user_id: int):
    msg = f"""🎁 **Активирован Триал**
👤 Юзер: `{user_id}`
⏱ Срок: 24 часа"""
    await send_admin_alert(client, msg)

async def notify_system_error(client: TelegramClient, component: str, error: str):
    msg = f"""⚠️ **КРИТИЧЕСКАЯ ОШИБКА!**

🧱 Компонент: `{component}`
❌ Текст: `{error}`"""
    await send_admin_alert(client, msg)
