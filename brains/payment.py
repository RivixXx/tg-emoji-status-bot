import aiohttp
import logging
import os
from typing import Optional, Dict, Any

# Рекомендуется добавить CRYPTO_PAY_TOKEN в .env
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN", "YOUR_TOKEN_HERE")
IS_TESTNET = True # Поменяйте на False для продакшна

class CryptoPayManager:
    """Интеграция с CryptoPay API (CryptoBot)"""
    
    BASE_URL = "https://testnet-pay.cryptomus.com/api/v1" if IS_TESTNET else "https://pay.cryptomus.com/api/v1"
    # Для CryptoBot API (более простой вариант):
    API_URL = "https://testnet-pay.crypt.bot/api" if IS_TESTNET else "https://pay.crypt.bot/api"

    def __init__(self, token: str = CRYPTO_PAY_TOKEN):
        self.token = token
        self.headers = {"Crypto-Pay-API-Token": self.token}

    async def create_invoice(self, amount: float, currency: str = "USDT", 
                             description: str = "Оплата VPN", user_id: int = 0) -> Optional[Dict[str, Any]]:
        """Создает счет на оплату"""
        url = f"{self.API_URL}/createInvoice"
        # Конвертация фиата в крипто (упрощенно или через фиксированные суммы)
        # В идеале здесь должен быть запрос курса, но для начала можно фиксировать USDT
        
        payload = {
            "asset": "USDT",
            "amount": str(round(amount / 95, 2)), # Примерный курс 95р за USDT
            "description": f"{description} (ID: {user_id})",
            "payload": str(user_id)
        }
        
        try:
            async with aiohttp.ClientClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        return result["result"]
                    else:
                        logging.error(f"CryptoPay error: {result}")
        except Exception as e:
            logging.error(f"Failed to create invoice: {e}")
        return None

    async def check_invoice(self, invoice_id: int) -> bool:
        """Проверяет статус оплаты счета"""
        url = f"{self.API_URL}/getInvoices"
        params = {"invoice_ids": str(invoice_id)}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as resp:
                    result = await resp.json()
                    if result.get("ok") and result["result"]["items"]:
                        status = result["result"]["items"][0]["status"]
                        return status == "paid"
        except Exception as e:
            logging.error(f"Failed to check invoice: {e}")
        return False

payment_manager = CryptoPayManager()
