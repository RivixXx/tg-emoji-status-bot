"""
Marzban VPN API Client
Автоматическая генерация VLESS ключей для VPN Shop
"""
import logging
import httpx
from typing import Optional, Dict
from brains.config import MARZBAN_URL, MARZBAN_ADMIN_TOKEN
from brains.exceptions import (
    VPNError,
    VPNConnectionError,
    VPNUserExistsError,
    AITimeoutError
)

logger = logging.getLogger(__name__)


class MarzbanClient:
    """Клиент для взаимодействия с Marzban API"""

    def __init__(self):
        self.base_url = MARZBAN_URL or "http://108.165.174.164:8000"
        self.admin_token = MARZBAN_ADMIN_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.admin_token}" if self.admin_token else "",
            "Content-Type": "application/json"
        }

    async def create_user(self, username: str, expire_days: int = 30) -> Optional[Dict]:
        """
        Создаёт пользователя в Marzban и возвращает VLESS ключ

        Args:
            username: Уникальное имя пользователя (обычно Telegram ID)
            expire_days: Количество дней доступа

        Returns:
            Dict с ключом доступа или None при ошибке
        """
        if not self.admin_token:
            logger.error("❌ Marzban admin token не настроен")
            return None

        url = f"{self.base_url}/api/user"

        # Вычисляем дату истечения в формате ISO
        from datetime import datetime, timedelta
        expire_date = datetime.now() + timedelta(days=expire_days)
        expire_timestamp = int(expire_date.timestamp())

        payload = {
            "username": username,
            "expire": expire_timestamp,
            "data_limit": 0,  # Без лимита трафика
            "proxies": ["vless"],
            "status": "active"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Marzban: пользователь {username} создан")

                    # Извлекаем VLESS ссылку из ответа
                    vless_link = self._extract_vless_link(data)

                    return {
                        "success": True,
                        "username": username,
                        "vless_link": vless_link,
                        "expire_date": expire_date.strftime("%Y-%m-%d"),
                        "data": data
                    }
                elif response.status_code == 409:
                    logger.warning(f"⚠️ Пользователь {username} уже существует")
                    raise VPNUserExistsError(f"User {username} already exists")
                elif response.status_code == 401:
                    logger.error("❌ Неверный токен Marzban")
                    raise VPNConnectionError("Invalid Marzban admin token")
                elif response.status_code >= 500:
                    logger.error(f"❌ Ошибка сервера Marzban: {response.status_code}")
                    raise VPNConnectionError(f"Marzban server error: {response.status_code}")
                else:
                    logger.error(f"❌ Marzban API error: {response.status_code} - {response.text[:200]}")
                    raise VPNError(f"API error: {response.status_code}")

        except httpx.TimeoutException as e:
            logger.error("⌛️ Marzban API timeout")
            raise AITimeoutError("Marzban API timeout") from e
        except httpx.ConnectError as e:
            logger.error(f"❌ Не удалось подключиться к Marzban: {e}")
            raise VPNConnectionError(f"Connection failed: {e}") from e
        except (VPNUserExistsError, VPNConnectionError, VPNError):
            raise
        except Exception as e:
            logger.error(f"❌ Marzban create user error: {e}")
            raise VPNError(f"Unexpected error: {e}") from e

    async def get_user(self, username: str) -> Optional[Dict]:
        """Получает информацию о пользователе"""
        if not self.admin_token:
            return None

        url = f"{self.base_url}/api/user/{username}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)

                if response.status_code == 200:
                    data = response.json()
                    vless_link = self._extract_vless_link(data)

                    return {
                        "success": True,
                        "username": username,
                        "vless_link": vless_link,
                        "data": data
                    }
                else:
                    logger.error(f"❌ Marzban get user error: {response.status_code}")
                    return {"success": False, "error": f"API error: {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ Marzban get user error: {e}")
            return {"success": False, "error": str(e)}

    async def remove_user(self, username: str) -> bool:
        """Удаляет пользователя"""
        if not self.admin_token:
            return False

        url = f"{self.base_url}/api/user/{username}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(url, headers=self.headers)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Marzban remove user error: {e}")
            return False

    def _extract_vless_link(self, data: Dict) -> str:
        """Извлекает VLESS ссылку из ответа Marzban"""
        try:
            # Marzban возвращает ссылки в поле links или subscription_url
            if "links" in data and data["links"]:
                # Ищем VLESS ссылку в списке
                for link in data["links"]:
                    if link.startswith("vless://"):
                        return link

            # Альтернативно: subscription_url содержит все конфиги
            if "subscription_url" in data:
                return data["subscription_url"]

            # Если ничего не найдено
            return "vless://error-link-not-found"

        except Exception as e:
            logger.error(f"❌ Error extracting VLESS link: {e}")
            return "vless://error-extracting-link"


# Глобальный экземпляр
marzban_client = MarzbanClient()


async def generate_vpn_key(telegram_id: int, months: int = 1) -> Optional[str]:
    """
    Генерирует VPN ключ для пользователя

    Args:
        telegram_id: ID пользователя в Telegram
        months: Количество месяцев доступа

    Returns:
        VLESS ссылку или None при ошибке
    """
    username = f"vpn_{telegram_id}"
    expire_days = months * 30

    result = await marzban_client.create_user(username, expire_days)

    if result and result.get("success"):
        return result.get("vless_link")

    return None


async def check_payment_and_issue_key(telegram_id: int, months: int) -> Dict:
    """
    Проверяет оплату и выдаёт ключ
    (В будущем здесь будет интеграция с платёжной системой)

    Returns:
        Dict со статусом и ключом
    """
    # Пока просто генерируем ключ
    vless_key = await generate_vpn_key(telegram_id, months)

    if vless_key:
        return {
            "success": True,
            "message": "Транзакция подтверждена",
            "vless_key": vless_key,
            "expire_days": months * 30
        }
    else:
        return {
            "success": False,
            "message": "Ошибка генерации ключа"
        }
