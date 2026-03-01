import asyncio
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient, Button
from brains.mcp_vpn_shop import mcp_vpn_get_users_with_expiring_sub
from brains.vpn_ui import get_tariffs_keyboard

logger = logging.getLogger(__name__)

async def check_expiring_subscriptions(bot_client: TelegramClient):
    """
    Проверяет пользователей, у которых скоро кончается подписка,
    и отправляет им уведомления.
    """
    logger.info("🕵️ Monitoring subscriptions...")
    
    # Интервалы для уведомлений
    check_points = [
        {"days": 3, "msg": "У тебя осталось 3 дня подписки! Не забудь продлить, чтобы оставаться на связи. 🚀"},
        {"days": 1, "msg": "Твоя подписка истекает завтра! ⏳"},
        {"hours": 1, "msg": "Внимание! Подписка закончится через 1 час. ⚠️"}
    ]

    try:
        expiring_users = await mcp_vpn_get_users_with_expiring_sub(days=3)
        
        for user in expiring_users:
            user_id = user["user_id"]
            
            try:
                await bot_client.send_message(
                    user_id,
                    f"""👋 **ПРИВЕТ!**

{check_points[0]['msg']}""",
                    buttons=[[Button.inline("💎 Продлить сейчас", b"menu_tariffs")]]
                )
                logger.info(f"📩 Notification sent to {user_id}")
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
                
    except Exception as e:
        logger.error(f"Subscription monitor error: {e}")

async def start_sub_monitor_loop(bot_client: TelegramClient):
    """Бесконечный цикл проверки подписок (раз в 6 часов)"""
    while True:
        await check_expiring_subscriptions(bot_client)
        await asyncio.sleep(21600) # 6 часов
