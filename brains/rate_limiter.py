"""
Rate Limiter для Karina AI API
Ограничение количества запросов от одного клиента
"""
import time
from collections import defaultdict
from typing import Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class RateLimitConfig:
    """Конфигурация rate limiter"""
    requests: int  # Максимальное количество запросов
    window: int  # Временное окно в секундах


# Конфигурации по умолчанию
DEFAULT_LIMITS = {
    "global": RateLimitConfig(requests=100, window=60),  # 100 запросов в минуту
    "api/calendar": RateLimitConfig(requests=10, window=60),  # 10 в минуту
    "api/memory/search": RateLimitConfig(requests=20, window=60),  # 20 в минуту
    "api/health": RateLimitConfig(requests=30, window=60),  # 30 в минуту
    "api/health/stats": RateLimitConfig(requests=30, window=60),  # 30 в минуту
    "api/emotion": RateLimitConfig(requests=10, window=60),  # 10 в минуту
    "api/plugins": RateLimitConfig(requests=20, window=60),  # 20 в минуту
}


class RateLimiter:
    """
    Rate limiter с скользящим окном
    
    Использование:
        limiter = RateLimiter()
        allowed, retry_after = limiter.is_allowed("client_id", "endpoint")
    """
    
    def __init__(self, configs: Dict[str, RateLimitConfig] = None):
        self.configs = configs or DEFAULT_LIMITS
        # Хранилище: {client_id: {endpoint: [timestamps]}}
        self._requests: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    
    def is_allowed(self, client_id: str, endpoint: str = "global") -> Tuple[bool, int]:
        """
        Проверяет может ли клиент сделать запрос
        
        Args:
            client_id: Уникальный идентификатор клиента (IP, user_id, etc.)
            endpoint: Название эндпоинта для специфичного лимита
        
        Returns:
            (allowed, retry_after): (разрешено ли, секунд до следующего запроса)
        """
        now = time.time()
        config = self.configs.get(endpoint, self.configs["global"])
        
        # Получаем timestamps запросов клиента
        timestamps = self._requests[client_id][endpoint]
        
        # Удаляем старые запросы за пределами окна
        window_start = now - config.window
        timestamps = [ts for ts in timestamps if ts > window_start]
        
        # Проверяем лимит
        if len(timestamps) >= config.requests:
            # Вычисляем сколько ждать до следующего запроса
            oldest_in_window = min(timestamps)
            retry_after = int(oldest_in_window + config.window - now) + 1
            self._requests[client_id][endpoint] = timestamps
            return False, retry_after
        
        # Добавляем текущий запрос
        timestamps.append(now)
        self._requests[client_id][endpoint] = timestamps
        
        return True, 0
    
    def get_remaining(self, client_id: str, endpoint: str = "global") -> int:
        """Получает количество оставшихся запросов"""
        now = time.time()
        config = self.configs.get(endpoint, self.configs["global"])
        timestamps = self._requests[client_id][endpoint]
        
        # Удаляем старые
        window_start = now - config.window
        timestamps = [ts for ts in timestamps if ts > window_start]
        
        return max(0, config.requests - len(timestamps))
    
    def reset(self, client_id: str, endpoint: str = None):
        """Сбрасывает лимиты для клиента"""
        if endpoint:
            self._requests[client_id][endpoint] = []
        else:
            self._requests[client_id] = defaultdict(list)
    
    def cleanup(self):
        """Очищает старые записи (рекомендуется запускать периодически)"""
        now = time.time()
        max_window = max(config.window for config in self.configs.values())
        cutoff = now - max_window
        
        # Находим клиентов для удаления
        empty_clients = []
        
        for client_id, endpoints in self._requests.items():
            for endpoint in list(endpoints.keys()):
                endpoints[endpoint] = [ts for ts in endpoints[endpoint] if ts > cutoff]
                if not endpoints[endpoint]:
                    del endpoints[endpoint]
            
            if not endpoints:
                empty_clients.append(client_id)
        
        # Удаляем пустых клиентов
        for client_id in empty_clients:
            del self._requests[client_id]


# Глобальный экземпляр
rate_limiter = RateLimiter()


def create_rate_limit_headers(client_id: str, endpoint: str = "global") -> Dict[str, str]:
    """
    Создаёт заголовки для rate limiting
    
    Returns:
        Заголовки X-RateLimit-*
    """
    remaining = rate_limiter.get_remaining(client_id, endpoint)
    config = rate_limiter.configs.get(endpoint, rate_limiter.configs["global"])
    
    return {
        "X-RateLimit-Limit": str(config.requests),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(int(time.time()) + config.window)
    }
