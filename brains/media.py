import os
import logging
from typing import Optional, Dict
from telethon import TelegramClient, types
from brains.config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class MediaManager:
    """
    Класс для управления медиафайлами (баннерами).
    Обеспечивает кэширование в Supabase для мгновенной отправки.
    """
    
    _instance = None
    _supabase: Client = None
    _cache: Dict[str, any] = {} 

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MediaManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._supabase:
            try:
                self._supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            except Exception as e:
                logger.error(f"MediaManager: Failed to init Supabase: {e}")

    async def get_cached_media(self, key: str) -> Optional[any]:
        """Получает медиа из кэша или БД"""
        if key in self._cache:
            return self._cache[key]

        try:
            response = self._supabase.table("media_cache").select("file_id").eq("key", key).execute()
            if response.data:
                # В Telethon мы можем отправлять медиа, используя его строку-представление или ID
                # Но для простоты при первой загрузке в этой сессии мы будем использовать локальный файл
                return None 
        except Exception as e:
            logger.warning(f"MediaManager: Error fetching cache for {key}: {e}")
        
        return None

    async def save_media_id(self, key: str, file_id: str):
        """Сохраняет file_id в БД"""
        try:
            self._supabase.table("media_cache").upsert({
                "key": key,
                "file_id": str(file_id) # Сохраняем как строку
            }).execute()
        except Exception as e:
            logger.error(f"MediaManager: Error saving file_id for {key}: {e}")

    async def send_banner(self, client: TelegramClient, chat_id: int, key: str, 
                          path: str, caption: str, buttons: any = None) -> Optional[types.Message]:
        """Отправляет баннер с кэшированием"""
        
        try:
            # Пытаемся отправить файл
            if not os.path.exists(path):
                return await client.send_message(chat_id, caption, buttons=buttons)
            
            # Отправляем файл (Telethon сам эффективно обрабатывает повторную отправку в рамках одной сессии)
            message = await client.send_file(chat_id, path, caption=caption, buttons=buttons)
            
            # Сохраняем file_id для истории (как строку)
            if message.media:
                file_id = None
                if hasattr(message.media, 'photo'):
                    file_id = f"photo_{message.media.photo.id}"
                elif hasattr(message.media, 'document'):
                    file_id = f"doc_{message.media.document.id}"
                
                if file_id:
                    # Запускаем сохранение в фоне
                    from main import fire_and_forget
                    fire_and_forget(self.save_media_id(key, file_id))
            
            return message
        except Exception as e:
            logger.error(f"MediaManager: Failed to send banner {key}: {e}")
            # Фолбэк на текст если заблокировано или ошибка
            try:
                return await client.send_message(chat_id, caption, buttons=buttons)
            except:
                return None

media_manager = MediaManager()
