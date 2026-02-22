"""
Aura Settings для Karina AI
Конфигурация и управление аурами (emoji-статусы, био, напоминания)
"""
import logging
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from brains.clients import supabase_client

logger = logging.getLogger(__name__)


@dataclass
class AuraConfig:
    """Конфигурация одной ауры"""
    enabled: bool = True
    start_time: str = "09:00"
    end_time: str = "18:00"
    custom_settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_settings is None:
            self.custom_settings = {}


@dataclass
class UserAuraSettings:
    """Полные настройки аур пользователя"""
    user_id: int
    emoji_status: AuraConfig = None
    bio_status: AuraConfig = None
    health_reminder: AuraConfig = None
    morning_greeting: AuraConfig = None
    evening_reminder: AuraConfig = None
    lunch_reminder: AuraConfig = None
    break_reminder: AuraConfig = None
    
    def __post_init__(self):
        if self.emoji_status is None:
            self.emoji_status = AuraConfig()
        if self.bio_status is None:
            self.bio_status = AuraConfig()
        if self.health_reminder is None:
            self.health_reminder = AuraConfig(enabled=True, start_time="22:00", end_time="22:00")
        if self.morning_greeting is None:
            self.morning_greeting = AuraConfig(enabled=True, start_time="07:00", end_time="07:00")
        if self.evening_reminder is None:
            self.evening_reminder = AuraConfig(enabled=True, start_time="22:30", end_time="22:30")
        if self.lunch_reminder is None:
            self.lunch_reminder = AuraConfig(enabled=True, start_time="13:00", end_time="13:00")
        if self.break_reminder is None:
            self.break_reminder = AuraConfig(enabled=False, start_time="15:00", end_time="15:00")
    
    def to_dict(self) -> Dict:
        """Преобразует в словарь для JSON сериализации"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserAuraSettings':
        """Создаёт объект из словаря"""
        settings = cls(user_id=data['user_id'])
        
        if 'emoji_status' in data:
            settings.emoji_status = AuraConfig(**data['emoji_status'])
        if 'bio_status' in data:
            settings.bio_status = AuraConfig(**data['bio_status'])
        if 'health_reminder' in data:
            settings.health_reminder = AuraConfig(**data['health_reminder'])
        if 'morning_greeting' in data:
            settings.morning_greeting = AuraConfig(**data['morning_greeting'])
        if 'evening_reminder' in data:
            settings.evening_reminder = AuraConfig(**data['evening_reminder'])
        if 'lunch_reminder' in data:
            settings.lunch_reminder = AuraConfig(**data['lunch_reminder'])
        if 'break_reminder' in data:
            settings.break_reminder = AuraConfig(**data['break_reminder'])
        
        return settings


class AuraSettingsManager:
    """Менеджер настроек аур"""
    
    TABLE_NAME = "aura_settings"
    
    def __init__(self):
        self._cache: Dict[int, UserAuraSettings] = {}
    
    async def get_settings(self, user_id: int) -> UserAuraSettings:
        """Получает настройки аур пользователя"""
        # Проверяем кэш
        if user_id in self._cache:
            return self._cache[user_id]
        
        # Загружаем из базы
        try:
            response = supabase_client.table(self.TABLE_NAME)\
                .select("*")\
                .eq("user_id", user_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                data = response.data[0]
                settings = UserAuraSettings.from_dict(data['settings'])
                self._cache[user_id] = settings
                return settings
        except Exception as e:
            logger.error(f"Failed to get aura settings: {e}")
        
        # Возвращаем настройки по умолчанию
        settings = UserAuraSettings(user_id=user_id)
        self._cache[user_id] = settings
        return settings
    
    async def save_settings(self, settings: UserAuraSettings) -> bool:
        """Сохраняет настройки аур пользователя"""
        try:
            data = {
                "user_id": settings.user_id,
                "settings": settings.to_dict(),
                "updated_at": "now()"
            }
            
            # Upsert: вставляем или обновляем
            response = supabase_client.table(self.TABLE_NAME)\
                .upsert(data, on_conflict="user_id")\
                .execute()
            
            if response.data:
                self._cache[settings.user_id] = settings
                logger.info(f"💾 Aura settings saved for user {settings.user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to save aura settings: {e}")
            return False
    
    async def update_aura(self, user_id: int, aura_name: str, enabled: bool = None, 
                          start_time: str = None, end_time: str = None,
                          custom_settings: Dict = None) -> bool:
        """Обновляет настройки конкретной ауры"""
        settings = await self.get_settings(user_id)
        
        aura_config = getattr(settings, aura_name, None)
        if not aura_config:
            logger.error(f"Unknown aura: {aura_name}")
            return False
        
        if enabled is not None:
            aura_config.enabled = enabled
        if start_time is not None:
            aura_config.start_time = start_time
        if end_time is not None:
            aura_config.end_time = end_time
        if custom_settings is not None:
            aura_config.custom_settings.update(custom_settings)
        
        return await self.save_settings(settings)
    
    def clear_cache(self, user_id: int = None):
        """Очищает кэш настроек"""
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()


# Глобальный экземпляр
aura_settings_manager = AuraSettingsManager()


# Инициализация таблицы в БД
async def init_aura_settings_table():
    """Создаёт таблицу настроек аур если не существует"""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS aura_settings (
        user_id BIGINT PRIMARY KEY,
        settings JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_aura_settings_user ON aura_settings(user_id);
    
    COMMENT ON TABLE aura_settings IS 'Настройки аур пользователей';
    """
    
    try:
        # Выполняем SQL через Supabase
        # В реальной реализации нужно использовать execute_sql или аналог
        logger.info("📦 Aura settings table initialization skipped (use init.sql)")
    except Exception as e:
        logger.error(f"Failed to init aura settings table: {e}")
