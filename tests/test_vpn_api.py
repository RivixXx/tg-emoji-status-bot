"""
Tests for VPN API (Marzban Client) - JWT Authentication
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brains.vpn_api import MarzbanClient, generate_vpn_key
from brains.exceptions import VPNError, VPNUserExistsError, VPNAuthorizationError, VPNConnectionError


class TestMarzbanClient:
    """Тесты для MarzbanClient"""

    def test_init_default_values(self):
        """Проверка инициализации по умолчанию"""
        client = MarzbanClient()
        
        assert client.base_url == "http://108.165.174.164:8000"
        assert client.username == "root"
        assert client.password is None  # Если не задан в env

    def test_init_with_env(self):
        """Проверка инициализации из env"""
        client = MarzbanClient()
        
        # Проверяем что URL установлен (из env или дефолтный)
        assert "http://" in client.base_url or "https://" in client.base_url
        assert client.username == "root"

    @pytest.mark.asyncio
    async def test_get_token_success(self):
        """Проверка получения токена"""
        client = MarzbanClient()
        client.password = "test_password"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test_token_123"}
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            token = await client.get_token()
            
            assert token == "test_token_123"

    @pytest.mark.asyncio
    async def test_get_token_auth_error(self):
        """Проверка ошибки авторизации"""
        client = MarzbanClient()
        client.password = "wrong_password"
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            with pytest.raises(VPNAuthorizationError):
                await client.get_token()

    @pytest.mark.asyncio
    async def test_get_token_no_password(self):
        """Проверка без пароля"""
        client = MarzbanClient()
        client.password = None
        
        token = await client.get_token()
        
        assert token is None

    @pytest.mark.asyncio
    async def test_create_user_success(self):
        """Проверка успешного создания пользователя"""
        client = MarzbanClient()
        client.password = "test_password"
        
        # Mock для получения токена
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "test_token"}
        
        # Mock для создания пользователя
        user_response = MagicMock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "username": "vpn_123",
            "links": ["vless://test-key-123"]
        }
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.side_effect = [token_response, user_response]
            
            result = await client.create_user("vpn_123", expire_days=30)
            
            assert result["success"] == True
            assert result["username"] == "vpn_123"
            assert "vless://" in result["vless_link"]

    @pytest.mark.asyncio
    async def test_create_user_conflict(self):
        """Проверка обработки конфликта (пользователь существует)"""
        client = MarzbanClient()
        client.password = "test_password"
        
        # Mock для получения токена
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "test_token"}
        
        # Mock для создания пользователя (конфликт)
        user_response = MagicMock()
        user_response.status_code = 409
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.side_effect = [token_response, user_response]
            
            with pytest.raises(VPNUserExistsError):
                await client.create_user("vpn_123")

    @pytest.mark.asyncio
    async def test_create_user_no_password(self):
        """Проверка без пароля"""
        client = MarzbanClient()
        client.password = None
        
        result = await client.create_user("vpn_123")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_create_user_timeout(self):
        """Проверка обработки таймаута"""
        client = MarzbanClient()
        client.password = "test_password"
        
        with patch('httpx.AsyncClient.post', side_effect=Exception("Timeout")):
            with pytest.raises(VPNError):
                await client.create_user("vpn_123")

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
