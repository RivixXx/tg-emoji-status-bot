"""
MCP Tools для VPN Shop
Работа с пользователями, рефералами и заказами через Supabase
"""
import logging
from typing import Optional, Dict, List
from brains.clients import supabase_client
from datetime import datetime

logger = logging.getLogger(__name__)


# ========== USERS ==========

async def mcp_vpn_get_user(user_id: int) -> Optional[Dict]:
    """Получает пользователя VPN Shop"""
    try:
        response = supabase_client.table("vpn_shop_users").select("*").eq("user_id", user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error getting VPN user: {e}")
        return None


async def mcp_vpn_create_user(user_id: int, email: str = None, referred_by: int = None) -> Dict:
    """Создаёт или обновляет пользователя"""
    try:
        data = {
            "user_id": user_id,
            "email": email,
            "state": "NEW",
            "referred_by": referred_by,
            "balance": 0,
            "updated_at": datetime.now().isoformat()
        }
        
        response = supabase_client.table("vpn_shop_users").upsert(data).execute()
        logger.info(f"✅ VPN user created/updated: {user_id}")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error creating VPN user: {e}")
        return None


async def mcp_vpn_update_user_state(user_id: int, state: str, email: str = None, code: str = None) -> bool:
    """Обновляет состояние пользователя"""
    try:
        data = {
            "state": state,
            "updated_at": datetime.now().isoformat()
        }
        if email:
            data["email"] = email
        if code:
            data["verification_code"] = code
            
        response = supabase_client.table("vpn_shop_users").update(data).eq("user_id", user_id).execute()
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error updating VPN user state: {e}")
        return False


async def mcp_vpn_update_balance(user_id: int, amount: float) -> bool:
    """Обновляет баланс пользователя"""
    try:
        response = supabase_client.table("vpn_shop_users").update({
            "balance": amount,
            "updated_at": datetime.now().isoformat()
        }).eq("user_id", user_id).execute()
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error updating balance: {e}")
        return False


# ========== REFERRALS ==========

async def mcp_vpn_add_referral(referrer_id: int, referred_id: int, commission: float = 0) -> bool:
    """Добавляет реферальную связь"""
    try:
        data = {
            "referrer_id": referrer_id,
            "referred_id": referred_id,
            "commission": commission
        }
        response = supabase_client.table("vpn_shop_referrals").insert(data).execute()
        logger.info(f"✅ Referral added: {referrer_id} -> {referred_id}")
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error adding referral: {e}")
        return False


async def mcp_vpn_get_referrals(user_id: int) -> List[Dict]:
    """Получает список рефералов пользователя"""
    try:
        response = supabase_client.table("vpn_shop_referrals").select("*").eq("referrer_id", user_id).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting referrals: {e}")
        return []


async def mcp_vpn_get_referral_stats(user_id: int) -> Dict:
    """Получает статистику по рефералам"""
    try:
        # Количество рефералов
        referrals_response = supabase_client.table("vpn_shop_referrals").select("id", count="exact").eq("referrer_id", user_id).execute()
        total_referrals = referrals_response.count if hasattr(referrals_response, 'count') else 0
        
        # Общая комиссия
        commission_response = supabase_client.table("vpn_shop_referrals").select("commission").eq("referrer_id", user_id).execute()
        total_commission = sum(r.get("commission", 0) for r in commission_response.data) if commission_response.data else 0
        
        return {
            "total_referrals": total_referrals,
            "total_commission": total_commission
        }
    except Exception as e:
        logger.error(f"Error getting referral stats: {e}")
        return {"total_referrals": 0, "total_commission": 0}


# ========== ORDERS ==========

async def mcp_vpn_create_order(user_id: int, months: int, amount: float) -> Optional[Dict]:
    """Создаёт заказ"""
    try:
        data = {
            "user_id": user_id,
            "months": months,
            "amount": amount,
            "status": "pending"
        }
        response = supabase_client.table("vpn_shop_orders").insert(data).execute()
        logger.info(f"✅ Order created: {user_id}, {months} months")
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return None


async def mcp_vpn_update_order(order_id: int, status: str, vless_key: str = None) -> bool:
    """Обновляет статус заказа"""
    try:
        data = {
            "status": status,
            "updated_at": datetime.now().isoformat()
        }
        if vless_key:
            data["vless_key"] = vless_key
            
        response = supabase_client.table("vpn_shop_orders").update(data).eq("id", order_id).execute()
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error updating order: {e}")
        return False


async def mcp_vpn_get_user_orders(user_id: int, limit: int = 10) -> List[Dict]:
    """Получает заказы пользователя"""
    try:
        response = supabase_client.table("vpn_shop_orders").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting user orders: {e}")
        return []


# ========== COMMISSION CALCULATION ==========

def calculate_referral_commission(amount: float) -> float:
    """Рассчитывает комиссию для реферера (10%)"""
    return amount * 0.10
