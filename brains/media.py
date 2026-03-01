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
    Обеспечивает кэширование file_id в Supabase для мгновенной отправки.
    """
    
    _instance = None
    _supabase: Client = None
    _cache: Dict[str, str] = {}  # Локальный кэш для текущей сессии

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MediaManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._supabase:
            try:
                self._supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("MediaManager: Supabase client initialized")
            except Exception as e:
                logger.error(f"MediaManager: Failed to init Supabase: {e}")

    async def get_file_id(self, key: str) -> Optional[str]:
        """Получает file_id из кэша или БД"""
        if key in self._cache:
            return self._cache[key]

        try:
            response = self._supabase.table("media_cache").select("file_id").eq("key", key).execute()
            if response.data:
                file_id = response.data[0]["file_id"]
                self._cache[key] = file_id
                return file_id
        except Exception as e:
            logger.warning(f"MediaManager: Error fetching file_id for {key}: {e}")
        
        return None

    async def save_file_id(self, key: str, file_id: str):
        """Сохраняет file_id в БД и кэш"""
        self._cache[key] = file_id
        try:
            self._supabase.table("media_cache").upsert({
                "key": key,
                "file_id": file_id
            }).execute()
            logger.info(f"MediaManager: Cached file_id for {key}")
        except Exception as e:
            logger.error(f"MediaManager: Error saving file_id for {key}: {e}")

    async def send_banner(self, client: TelegramClient, chat_id: int, key: str, 
                          path: str, caption: str, buttons: any = None) -> Optional[types.Message]:
        """
        Отправляет баннер. Если есть file_id - по нему, если нет - загружает и кэширует.
        """
        file_id = await self.get_file_id(key)
        
        try:
            if file_id:
                # Отправка по file_id (мгновенно)
                return await client.send_file(chat_id, file_id, caption=caption, buttons=buttons)
            else:
                # Первая загрузка файла
                if not os.path.exists(path):
                    logger.error(f"MediaManager: File not found at {path}")
                    # Фолбэк на текстовое сообщение, если файла нет
                    return await client.send_message(chat_id, caption, buttons=buttons)
                
                message = await client.send_file(chat_id, path, caption=caption, buttons=buttons)
                
                # Сохраняем file_id для будущего использования
                # В Telethon file_id можно достать из media.photo.id или media.document.id
                new_file_id = None
                if hasattr(message.media, 'photo'):
                    new_file_id = message.media.photo
                elif hasattr(message.media, 'document'):
                    new_file_id = message.media.document
                
                if new_file_id:
                    await self.save_file_id(key, new_file_id)
                
                return message
        except Exception as e:
            logger.error(f"MediaManager: Failed to send banner {key}: {e}")
            return await client.send_message(chat_id, caption, buttons=buttons)

# Экземпляр синглтона
media_manager = MediaManager()
