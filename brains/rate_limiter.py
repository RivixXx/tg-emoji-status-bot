"""
Rate Limiter Utility
Декоратор для ограничения частоты вызовов функций (throttling)

Использование:
    @rate_limit(calls=10, period=60)  # 10 вызовов в минуту
    async def my_function():
        ...
"""
import asyncio
import time
import logging
from functools import wraps
from typing import Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter с скользящим окном.
    
    Атрибуты:
        calls: Максимальное количество вызовов
        period: Период времени в секундах
        key_func: Функция для получения ключа (по умолчанию None — глобальный лимит)
    """
    
    def __init__(self, calls: int, period: float, key_func: Optional[callable] = None):
        self.calls = calls
        self.period = period
        self.key_func = key_func or (lambda *args, **kwargs: "global")
        
        # Хранилище timestamps вызовов: {key: [timestamp1, timestamp2, ...]}
        self._timestamps: Dict[str, list] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    def _clean_old_timestamps(self, key: str, now: float):
        """Удаляет устаревшие timestamps"""
        cutoff = now - self.period
        self._timestamps[key] = [ts for ts in self._timestamps[key] if ts > cutoff]
    
    async def acquire(self, *args, **kwargs) -> bool:
        """
        Пытается получить разрешение на вызов.
        
        Returns:
            True если вызов разрешён, False если лимит превышен
        """
        key = self.key_func(*args, **kwargs)
        now = time.time()
        
        async with self._locks[key]:
            self._clean_old_timestamps(key, now)
            
            if len(self._timestamps[key]) < self.calls:
                self._timestamps[key].append(now)
                return True
            
            return False
    
    async def wait_if_needed(self, *args, **kwargs) -> float:
        """
        Ждёт если лимит превышен, возвращает время ожидания.
        
        Returns:
            Время ожидания в секундах (0 если не нужно ждать)
        """
        key = self.key_func(*args, **kwargs)
        now = time.time()
        
        async with self._locks[key]:
            self._clean_old_timestamps(key, now)
            
            if len(self._timestamps[key]) < self.calls:
                self._timestamps[key].append(now)
                return 0.0
            
            # Ждём пока освободится слот
            oldest = min(self._timestamps[key])
            wait_time = oldest + self.period - now
            
            if wait_time > 0:
                logger.debug(f"⏳ Rate limit: ждём {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                
                # Очищаем и добавляем новый timestamp
                self._clean_old_timestamps(key, time.time())
                self._timestamps[key].append(time.time())
            
            return max(0, wait_time)
    
    def get_remaining(self, *args, **kwargs) -> int:
        """
        Возвращает количество оставшихся вызовов.
        
        Returns:
            Количество оставшихся вызовов в текущем окне
        """
        key = self.key_func(*args, **kwargs)
        now = time.time()
        
        # Не блокируем, просто считаем
        self._clean_old_timestamps(key, now)
        return max(0, self.calls - len(self._timestamps[key]))
    
    def reset(self, key: str = "global"):
        """Сбрасывает лимит для ключа"""
        if key in self._timestamps:
            del self._timestamps[key]
            logger.info(f"🔄 Rate limit сброшен для: {key}")


def rate_limit(calls: int, period: float, key_func: Optional[callable] = None, 
               block: bool = True, error_message: str = None):
    """
    Декоратор для ограничения частоты вызовов асинхронных функций.
    
    Args:
        calls: Максимальное количество вызовов
        period: Период времени в секундах
        key_func: Функция для получения ключа rate limiting
        block: Если True — ждать, если False — возвращать ошибку
        error_message: Сообщение об ошибке при превышении лимита
    
    Returns:
        Декорированная функция
    
    Примеры:
        # Глобальный лимит
        @rate_limit(calls=10, period=60)
        async def api_call():
            ...
        
        # Лимит на пользователя
        @rate_limit(calls=5, period=60, key_func=lambda user_id, **kwargs: str(user_id))
        async def user_action(user_id):
            ...
        
        # Без блокировки (возвращает None при превышении)
        @rate_limit(calls=10, period=60, block=False)
        async def sensitive_operation():
            ...
    """
    limiter = RateLimiter(calls, period, key_func)
    error_message = error_message or f"Rate limit exceeded: {calls} calls per {period}s"
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if block:
                # Ждём если нужно
                wait_time = await limiter.wait_if_needed(*args, **kwargs)
                if wait_time > 0:
                    logger.info(f"⏳ {func.__name__}: ожидание {wait_time:.2f}s из-за rate limit")
            else:
                # Возвращаем None если лимит превышен
                if not await limiter.acquire(*args, **kwargs):
                    logger.warning(f"⚠️ {func.__name__}: rate limit превышен")
                    return None
            
            return await func(*args, **kwargs)
        
        # Добавляем атрибуты для отладки
        wrapper._rate_limiter = limiter
        wrapper._rate_limit_calls = calls
        wrapper._rate_limit_period = period
        
        return wrapper
    
    return decorator


# ============================================================================
# Предустановленные лимитеры для типичных сценариев
# ============================================================================

# API лимиты (для внешних API)
mistral_limiter = RateLimiter(calls=30, period=60)  # 30 запросов в минуту
supabase_limiter = RateLimiter(calls=100, period=60)  # 100 запросов в минуту
telegram_limiter = RateLimiter(calls=30, period=1)  # 30 сообщений в секунду

# Пользовательские лимиты (для защиты от злоупотреблений)
user_command_limiter = RateLimiter(calls=10, period=60, 
                                    key_func=lambda user_id, **kwargs: str(user_id))  # 10 команд в минуту на пользователя
vpn_key_limiter = RateLimiter(calls=5, period=3600,
                               key_func=lambda user_id, **kwargs: str(user_id))  # 5 ключей в час на пользователя


# ============================================================================
# Декораторы для типичных сценариев
# ============================================================================

def api_rate_limit(calls: int = 30, period: float = 60):
    """Декоратор для API запросов"""
    return rate_limit(calls=calls, period=period, block=True,
                      error_message=f"API rate limit: {calls} calls per {period}s")


def user_rate_limit(calls: int = 10, period: float = 60):
    """Декоратор для пользовательских команд"""
    return rate_limit(calls=calls, period=period, block=True,
                      key_func=lambda user_id, **kwargs: f"user:{user_id}",
                      error_message=f"Команд слишком много: {calls} в {period}s")


def vpn_rate_limit(calls: int = 5, period: float = 3600):
    """Декоратор для генерации VPN ключей"""
    return rate_limit(calls=calls, period=period, block=False,
                      key_func=lambda user_id, **kwargs: f"vpn:{user_id}",
                      error_message=f"Лимит VPN ключей: {calls} в час")
