"""
MCP Tools для VPN Shop
Работа с пользователями, рефералами и заказами через Supabase
Версия 2.0 (Production Ready)
"""
import logging
from typing import Optional, Dict, List
from brains.clients import supabase_client
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ========== USERS ==========

async def mcp_vpn_get_user(user_id: int) -> Optional[Dict]:
    """Получает пользователя VPN Shop со всеми полями"""
    try:
        response = supabase_client.table("vpn_shop_users").select("*").eq("user_id", user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error getting VPN user: {e}")
        return None


async def mcp_vpn_create_user(user_id: int, email: str = None, referred_by: int = None) -> Dict:
    """Создаёт пользователя (начальное состояние)"""
    try:
        data = {
            "user_id": user_id,
            "email": email,
            "state": "NEW",
            "referred_by": referred_by,
            "balance": 0,
            "trial_used": False
        }
        
        response = supabase_client.table("vpn_shop_users").upsert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error creating VPN user: {e}")
        return None


async def mcp_vpn_update_user_state(user_id: int, state: str, **kwargs) -> bool:
    """Универсальное обновление полей пользователя (state, trial_used, sub_end)"""
    try:
        data = {"state": state, "updated_at": datetime.now().isoformat()}
        data.update(kwargs)
            
        response = supabase_client.table("vpn_shop_users").update(data).eq("user_id", user_id).execute()
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error updating VPN user: {e}")
        return False


# ========== SUBSCRIPTIONS ==========

async def mcp_vpn_activate_sub(user_id: int, months: int) -> bool:
    """Продлевает или активирует подписку"""
    try:
        user = await mcp_vpn_get_user(user_id)
        if not user: return False
        
        # Рассчитываем новую дату окончания
        now = datetime.now()
        current_end = user.get("sub_end")
        
        if current_end:
            start_from = max(now, datetime.fromisoformat(current_end.replace('Z', '+00:00')))
        else:
            start_from = now
            
        new_end = start_from + timedelta(days=30 * months if months > 0 else 1) # 1 день для триала
        
        return await mcp_vpn_update_user_state(user_id, "REGISTERED", sub_end=new_end.isoformat())
    except Exception as e:
        logger.error(f"Failed to activate sub: {e}")
        return False


async def mcp_vpn_get_users_with_expiring_sub(days: int = 3) -> List[Dict]:
    """Находит пользователей, у которых подписка кончается через X дней"""
    try:
        target_date = (datetime.now() + timedelta(days=days)).isoformat()
        now = datetime.now().isoformat()
        
        # Ищем тех, у кого sub_end меньше target_date, но больше сейчас
        response = supabase_client.table("vpn_shop_users") \
            .select("user_id, sub_end") \
            .lt("sub_end", target_date) \
            .gt("sub_end", now) \
            .execute()
            
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting expiring subs: {e}")
        return []


# ========== ORDERS ==========

async def mcp_vpn_create_order(user_id: int, months: int, amount: float, invoice_id: int = None) -> Optional[Dict]:
    """Создаёт заказ с привязкой к инвойсу"""
    try:
        data = {
            "user_id": user_id,
            "months": months,
            "amount": amount,
            "status": "pending",
            "invoice_id": invoice_id
        }
        response = supabase_client.table("vpn_shop_orders").insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return None


async def mcp_vpn_update_order(order_id: int, status: str, **kwargs) -> bool:
    """Обновляет статус и данные заказа"""
    try:
        data = {"status": status, "updated_at": datetime.now().isoformat()}
        data.update(kwargs)
            
        response = supabase_client.table("vpn_shop_orders").update(data).eq("id", order_id).execute()
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error updating order: {e}")
        return False


# ========== REFERRALS & BALANCE ==========

async def mcp_vpn_get_referral_stats(user_id: int) -> Dict:
    """Получает статистику (упрощенная версия через RPC или агрегацию)"""
    try:
        # Пытаемся вызвать RPC функцию get_referral_stats из SQL
        try:
            rpc_resp = supabase_client.rpc("get_referral_stats", {"user_id_param": user_id}).execute()
            if rpc_resp.data:
                return rpc_resp.data[0]
        except:
            pass
            
        # Фолбэк на ручной расчет если RPC нет
        ref_resp = supabase_client.table("vpn_shop_referrals").select("commission").eq("referrer_id", user_id).execute()
        total_commission = sum(r.get("commission", 0) for r in ref_resp.data) if ref_resp.data else 0
        return {"total_referrals": len(ref_resp.data or []), "total_commission": total_commission}
    except Exception as e:
        logger.error(f"Error getting referral stats: {e}")
        return {"total_referrals": 0, "total_commission": 0}

def calculate_referral_commission(amount: float) -> float:
    return amount * 0.10
