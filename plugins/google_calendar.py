"""
Google Calendar Plugin for Karina AI
Отключаемый модуль для работы с Google Calendar
"""
import logging
from datetime import datetime
from plugins.base import Plugin, PluginConfig

logger = logging.getLogger(__name__)


class GoogleCalendarPlugin(Plugin):
    """Плагин Google Calendar"""
    
    name = "google_calendar"
    version = "1.0.0"
    description = "Интеграция с Google Calendar (личный + Bitrix24)"
    author = "Karina AI Team"
    
    def __init__(self, config: PluginConfig = None):
        super().__init__(config)
        self._calendar_service = None
        self._credentials = None
    
    async def initialize(self):
        """Инициализация плагина"""
        if not self.enabled:
            logger.info(f"⏸️ Плагин {self.name} отключен")
            return
        
        try:
            # Импортируем только если плагин включен
            from brains.calendar import get_calendar_service
            
            self._calendar_service = get_calendar_service()
            self._initialized = True
            
            logger.info(f"✅ Плагин {self.name} инициализирован")
        except ImportError as e:
            logger.warning(f"⚠️ Плагин {self.name}: зависимости не установлены. {e}")
            self.disable()
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации плагина {self.name}: {e}")
            self.disable()
    
    async def shutdown(self):
        """Завершение работы плагина"""
        self._calendar_service = None
        self._credentials = None
        logger.info(f"🛑 Плагин {self.name} остановлен")
    
    async def get_upcoming_events(self, max_results: int = 5) -> str:
        """
        Получает список ближайших событий
        
        Args:
            max_results: Максимальное количество событий
        
        Returns:
            Форматированная строка со списком событий
        """
        if not self.enabled or not self._initialized:
            return "📅 Календарь временно недоступен"
        
        try:
            from brains.calendar import get_upcoming_events as core_get_events
            return await core_get_events(max_results)
        except Exception as e:
            logger.error(f"❌ Ошибка получения событий: {e}")
            return "⚠️ Не удалось получить события из календаря"
    
    async def create_event(
        self,
        summary: str,
        start_time: datetime,
        duration: int = 30,
        description: str = ""
    ) -> bool:
        """
        Создает событие в календаре
        
        Args:
            summary: Заголовок события
            start_time: Время начала
            duration: Длительность в минутах
            description: Описание
        
        Returns:
            True если успешно
        """
        if not self.enabled or not self._initialized:
            logger.warning(f"⚠️ Попытка создания события при отключенном плагине {self.name}")
            return False
        
        try:
            from brains.calendar import create_event as core_create_event
            return await core_create_event(summary, start_time, duration, description)
        except Exception as e:
            logger.error(f"❌ Ошибка создания события: {e}")
            return False
    
    async def get_conflict_report(self) -> str:
        """
        Проверяет календарь на конфликты
        
        Returns:
            Отчет о конфликтах
        """
        if not self.enabled or not self._initialized:
            return "📅 Проверка конфликтов недоступна"
        
        try:
            from brains.calendar import get_conflict_report as core_get_conflicts
            return await core_get_conflicts()
        except Exception as e:
            logger.error(f"❌ Ошибка проверки конфликтов: {e}")
            return "⚠️ Не удалось проверить конфликты"
    
    def is_available(self) -> bool:
        """Проверяет доступность плагина"""
        return self.enabled and self._initialized


# Экземпляр плагина для регистрации
plugin_instance = GoogleCalendarPlugin()
