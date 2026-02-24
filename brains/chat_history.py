"""
LRU Cache для истории чатов Karina AI
Ограничивает размер истории и предотвращает утечку памяти
"""
import asyncio
from collections import OrderedDict
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class ChatHistoryEntry:
    """Запись истории чата"""
    messages: List[Dict[str, Any]]
    last_access: float  # timestamp последнего доступа


class ChatHistoryCache:
    """
    LRU кэш для истории чатов
    
    Использование:
        cache = ChatHistoryCache(max_size=100, max_messages=10)
        messages = await cache.get(chat_id)
        await cache.set(chat_id, messages)
    """
    
    def __init__(self, max_size: int = 100, max_messages: int = 10):
        """
        Args:
            max_size: Максимальное количество чатов в кэше
            max_messages: Максимальное количество сообщений в одном чате
        """
        self._cache: OrderedDict[int, ChatHistoryEntry] = OrderedDict()
        self._max_size = max_size
        self._max_messages = max_messages
        self._lock = asyncio.Lock()
    
    async def get(self, chat_id: int) -> List[Dict[str, Any]]:
        """
        Получает историю чата
        
        Args:
            chat_id: ID чата
        
        Returns:
            Список сообщений
        """
        async with self._lock:
            if chat_id not in self._cache:
                return []
            
            # Перемещаем в конец (самый свежий)
            self._cache.move_to_end(chat_id)
            return self._cache[chat_id].messages.copy()
    
    async def set(self, chat_id: int, messages: List[Dict[str, Any]]):
        """
        Сохраняет историю чата
        
        Args:
            chat_id: ID чата
            messages: Список сообщений
        """
        import time
        
        async with self._lock:
            # Ограничиваем количество сообщений
            trimmed_messages = messages[-self._max_messages:] if len(messages) > self._max_messages else messages
            
            if chat_id in self._cache:
                # Обновляем существующий
                self._cache[chat_id].messages = trimmed_messages
                self._cache[chat_id].last_access = time.time()
                self._cache.move_to_end(chat_id)
            else:
                # Создаём новый
                self._cache[chat_id] = ChatHistoryEntry(
                    messages=trimmed_messages,
                    last_access=time.time()
                )
                
                # Удаляем самый старый если превышен размер
                if len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)
    
    async def append(self, chat_id: int, message: Dict[str, Any]):
        """
        Добавляет одно сообщение в историю
        
        Args:
            chat_id: ID чата
            message: Сообщение для добавления
        """
        async with self._lock:
            if chat_id in self._cache:
                self._cache[chat_id].messages.append(message)
                # Обрезаем если нужно
                if len(self._cache[chat_id].messages) > self._max_messages:
                    self._cache[chat_id].messages = self._cache[chat_id].messages[-self._max_messages:]
                self._cache.move_to_end(chat_id)
            else:
                import time
                self._cache[chat_id] = ChatHistoryEntry(
                    messages=[message],
                    last_access=time.time()
                )
    
    async def delete(self, chat_id: int) -> bool:
        """
        Удаляет историю чата
        
        Args:
            chat_id: ID чата
        
        Returns:
            True если удалено, False если не существовало
        """
        async with self._lock:
            if chat_id in self._cache:
                del self._cache[chat_id]
                return True
            return False
    
    async def clear(self):
        """Очищает весь кэш"""
        async with self._lock:
            self._cache.clear()
    
    async def contains(self, chat_id: int) -> bool:
        """Проверяет существует ли чат в кэше"""
        async with self._lock:
            return chat_id in self._cache
    
    async def size(self) -> int:
        """Получает количество чатов в кэше"""
        async with self._lock:
            return len(self._cache)
    
    async def cleanup_old(self, max_age_seconds: int = 3600):
        """
        Удаляет чаты старше указанного времени
        
        Args:
            max_age_seconds: Максимальный возраст в секундах
        """
        import time
        
        async with self._lock:
            now = time.time()
            to_delete = [
                chat_id for chat_id, entry in self._cache.items()
                if now - entry.last_access > max_age_seconds
            ]
            
            for chat_id in to_delete:
                del self._cache[chat_id]
            
            return len(to_delete)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получает статистику кэша"""
        async with self._lock:
            import time
            
            now = time.time()
            ages = [now - entry.last_access for entry in self._cache.values()]
            
            return {
                "total_chats": len(self._cache),
                "max_size": self._max_size,
                "max_messages_per_chat": self._max_messages,
                "avg_age_seconds": sum(ages) / len(ages) if ages else 0,
                "oldest_chat_age": max(ages) if ages else 0,
                "newest_chat_age": min(ages) if ages else 0
            }


# Глобальный экземпляр
chat_history_cache = ChatHistoryCache(max_size=100, max_messages=10)
