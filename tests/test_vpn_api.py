"""
Tests for VPN API (Marzban Client)
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brains.vpn_api import MarzbanClient, generate_vpn_key


class TestMarzbanClient:
    """Тесты для MarzbanClient"""

    def test_init_default_values(self):
        """Проверка инициализации по умолчанию"""
        client = MarzbanClient()
        
        assert client.base_url == "http://108.165.174.164:8000"
        assert "Authorization" in client.headers

    def test_init_with_env(self):
        """Проверка инициализации из env"""
        with patch.dict(os.environ, {
            "MARZBAN_URL": "http://test:8000",
            "MARZBAN_ADMIN_TOKEN": "test_token"
        }):
            # Пересоздаём чтобы подхватил env
            client = MarzbanClient()
            
            assert client.base_url == "http://test:8000"
            assert client.headers["Authorization"] == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_create_user_success(self):
        """Проверка успешного создания пользователя"""
        client = MarzbanClient()
        client.admin_token = "test_token"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "username": "vpn_123",
            "links": ["vless://test-key-123"],
            "subscription_url": "https://sub.url"
        }
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            result = await client.create_user("vpn_123", expire_days=30)
            
            assert result["success"] == True
            assert result["username"] == "vpn_123"
            assert "vless://" in result["vless_link"]

    @pytest.mark.asyncio
    async def test_create_user_conflict(self):
        """Проверка обработки конфликта (пользователь существует)"""
        client = MarzbanClient()
        client.admin_token = "test_token"
        
        mock_response = MagicMock()
        mock_response.status_code = 409
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            with patch.object(client, 'get_user', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {"success": True, "vless_link": "vless://existing"}
                
                result = await client.create_user("vpn_123")
                
                assert result is not None
                mock_get.assert_called_once_with("vpn_123")

    @pytest.mark.asyncio
    async def test_create_user_no_token(self):
        """Проверка без токена"""
        client = MarzbanClient()
        client.admin_token = None
        
        result = await client.create_user("vpn_123")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_create_user_timeout(self):
        """Проверка обработки таймаута"""
        client = MarzbanClient()
        client.admin_token = "test_token"
        
        with patch('httpx.AsyncClient.post', side_effect=Exception("Timeout")):
            result = await client.create_user("vpn_123")
            
            assert result["success"] == False
            assert "error" in result

    def test_extract_vless_link_from_links(self):
        """Проверка извлечения VLESS из links"""
        client = MarzbanClient()
        
        data = {
            "links": [
                "vmess://abc",
                "vless://test-key-123",
                "trojan://xyz"
            ]
        }
        
        link = client._extract_vless_link(data)
        assert link == "vless://test-key-123"

    def test_extract_vless_link_from_subscription(self):
        """Проверка извлечения VLESS из subscription_url"""
        client = MarzbanClient()
        
        data = {
            "subscription_url": "https://sub.url/vless-key"
        }
        
        link = client._extract_vless_link(data)
        assert link == "https://sub.url/vless-key"

    def test_extract_vless_link_not_found(self):
        """Проверка когда ссылка не найдена"""
        client = MarzbanClient()
        
        data = {}
        
        link = client._extract_vless_link(data)
        assert link == "vless://error-link-not-found"


class TestGenerateVPNKey:
    """Тесты для функции generate_vpn_key"""

    @pytest.mark.asyncio
    async def test_generate_key_success(self):
        """Проверка успешной генерации ключа"""
        with patch('brains.vpn_api.marzban_client') as mock_client:
            mock_client.create_user = AsyncMock(return_value={
                "success": True,
                "vless_link": "vless://test-key"
            })
            
            key = await generate_vpn_key(123456, months=1)
            
            assert key == "vless://test-key"
            mock_client.create_user.assert_called_once_with("vpn_123456", 30)

    @pytest.mark.asyncio
    async def test_generate_key_failure(self):
        """Проверка неудачной генерации ключа"""
        with patch('brains.vpn_api.marzban_client') as mock_client:
            mock_client.create_user = AsyncMock(return_value=None)
            
            key = await generate_vpn_key(123456, months=1)
            
            assert key is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
