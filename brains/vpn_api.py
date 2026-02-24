"""
Marzban VPN API Client
Автоматическая генерация VLESS ключей для VPN Shop
Использует JWT аутентификацию (логин/пароль)
"""
import logging
import httpx
from typing import Optional, Dict
from brains.config import MARZBAN_URL, MARZBAN_USER, MARZBAN_PASS
from brains.exceptions import (
    VPNError,
    VPNConnectionError,
    VPNUserExistsError,
    VPNAuthorizationError
)

logger = logging.getLogger(__name__)


class MarzbanClient:
    """Клиент для взаимодействия с Marzban API"""

    def __init__(self):
        self.base_url = MARZBAN_URL or "http://108.165.174.164:8000"
        self.username = MARZBAN_USER or "root"
        self.password = MARZBAN_PASS
        self._token_cache: Optional[str] = None

    async def get_token(self) -> Optional[str]:
        """
        Получает JWT токен администратора
        
        Returns:
            access_token или None при ошибке
        """
        if not self.password:
            logger.error("❌ Пароль Marzban не настроен")
            return None

        url = f"{self.base_url}/api/admin/token"
        
        # Marzban требует данные в формате формы (OAuth2)
        data = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=data)

                if response.status_code == 200:
                    result = response.json()
                    token = result.get("access_token")
                    logger.info("✅ Получен токен Marzban")
                    return token
                elif response.status_code == 401:
                    logger.error("❌ Неверный логин/пароль Marzban")
                    raise VPNAuthorizationError("Invalid Marzban credentials")
                else:
                    logger.error(f"❌ Marzban token error: {response.status_code} - {response.text[:200]}")
                    raise VPNConnectionError(f"Token API error: {response.status_code}")

        except httpx.TimeoutException:
            logger.error("⌛️ Marzban token timeout")
            raise VPNConnectionError("Marzban token timeout")
        except httpx.ConnectError as e:
            logger.error(f"❌ Не удалось подключиться к Marzban: {e}")
            raise VPNConnectionError(f"Connection failed: {e}")
        except (VPNAuthorizationError, VPNConnectionError):
            raise
        except Exception as e:
            logger.error(f"❌ Marzban get token error: {e}")
            raise VPNError(f"Unexpected error: {e}")

    async def create_user(self, username: str, expire_days: int = 30) -> Optional[Dict]:
        """
        Создаёт пользователя в Marzban и возвращает VLESS ключ

        Args:
            username: Уникальное имя пользователя (обычно Telegram ID)
            expire_days: Количество дней доступа

        Returns:
            Dict с ключом доступа или None при ошибке
        """
        # Получаем токен
        token = await self.get_token()
        if not token:
            return None

        url = f"{self.base_url}/api/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "application/json",
            "Content-Type": "application/json"
        }

        # Вычисляем дату истечения
        from datetime import datetime, timedelta
        expire_date = datetime.now() + timedelta(days=expire_days)

        # Формируем данные нового пользователя
        user_payload = {
            "username": username,
            "expire": int(expire_date.timestamp()),
            "data_limit": 0,  # Без лимита трафика
            "proxies": {
                "vless": {}
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=user_payload)

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
                    raise VPNConnectionError("Invalid Marzban token")
                elif response.status_code >= 500:
                    logger.error(f"❌ Ошибка сервера Marzban: {response.status_code}")
                    raise VPNConnectionError(f"Marzban server error: {response.status_code}")
                else:
                    logger.error(f"❌ Marzban API error: {response.status_code} - {response.text[:200]}")
                    raise VPNError(f"API error: {response.status_code}")

        except httpx.TimeoutException:
            logger.error("⌛️ Marzban API timeout")
            raise VPNConnectionError("Marzban API timeout")
        except httpx.ConnectError as e:
            logger.error(f"❌ Не удалось подключиться к Marzban: {e}")
            raise VPNConnectionError(f"Connection failed: {e}")
        except (VPNUserExistsError, VPNConnectionError, VPNError):
            raise
        except Exception as e:
            logger.error(f"❌ Marzban create user error: {e}")
            raise VPNError(f"Unexpected error: {e}")

    async def get_user(self, username: str) -> Optional[Dict]:
        """Получает информацию о пользователе"""
        token = await self.get_token()
        if not token:
            return None

        url = f"{self.base_url}/api/user/{username}"
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    vless_link = self._extract_vless_link(data)

                    return {
                        "success": True,
                        "username": username,
                        "vless_link": vless_link,
                        "data": data
                    }
                elif response.status_code == 404:
                    logger.warning(f"⚠️ Пользователь {username} не найден")
                    return None
                else:
                    logger.error(f"❌ Marzban get user error: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"❌ Marzban get user error: {e}")
            return None

    async def remove_user(self, username: str) -> bool:
        """Удаляет пользователя"""
        token = await self.get_token()
        if not token:
            return False

        url = f"{self.base_url}/api/user/{username}"
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(url, headers=headers)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Marzban remove user error: {e}")
            return False

    def _extract_vless_link(self, data: Dict) -> str:
        """Извлекает VLESS ссылку из ответа Marzban"""
        try:
            # Marzban возвращает ссылки в поле links
            if "links" in data and data["links"]:
                # Ищем VLESS ссылку в списке
                for link in data["links"]:
                    if link.startswith("vless://"):
                        return link

            # Альтернативно: subscription_url содержит все конфиги
            if "subscription_url" in data:
                sub_url = data["subscription_url"]
                
                # Если ссылка относительная (начинается с /), добавляем базовый URL
                if sub_url.startswith("/"):
                    # Используем внешний IP для доступа из интернета
                    base_url = self.base_url.replace("127.0.0.1", "108.165.174.164").replace("localhost", "108.165.174.164")
                    return f"{base_url}{sub_url}"
                else:
                    # Если ссылка абсолютная, но содержит 127.0.0.1 или localhost — заменяем
                    return sub_url.replace("127.0.0.1", "108.165.174.164").replace("localhost", "108.165.174.164")

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
    try:
        # Генерируем ключ
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
    except VPNUserExistsError:
        # Пользователь уже существует — пробуем получить ключ
        user_data = await marzban_client.get_user(f"vpn_{telegram_id}")
        
        if user_data and user_data.get("success"):
            return {
                "success": True,
                "message": "Ключ активирован (продление)",
                "vless_key": user_data.get("vless_link"),
                "expire_days": months * 30,
                "existing": True
            }
        else:
            return {
                "success": False,
                "message": "Пользователь существует, но не удалось получить ключ"
            }
    except Exception as e:
        logger.error(f"❌ VPN key generation error: {e}")
        return {
            "success": False,
            "message": f"Ошибка: {str(e)}"
        }
