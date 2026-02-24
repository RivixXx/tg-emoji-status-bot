"""
Базовые исключения Karina AI
"""


class KarinaError(Exception):
    """Базовое исключение для всех ошибок Karina"""
    pass


class AIError(KarinaError):
    """Ошибки AI модуля (Mistral)"""
    pass


class AIRateLimitError(AIError):
    """Превышение лимита запросов к AI API"""
    pass


class AITimeoutError(AIError):
    """Таймаут запроса к AI API"""
    pass


class DatabaseError(KarinaError):
    """Ошибки базы данных (Supabase)"""
    pass


class DatabaseConnectionError(DatabaseError):
    """Ошибка подключения к базе данных"""
    pass


class DatabaseNotFoundError(DatabaseError):
    """Запись не найдена в базе данных"""
    pass


class VPNError(KarinaError):
    """Ошибки VPN модуля (Marzban)"""
    pass


class VPNConnectionError(VPNError):
    """Ошибка подключения к Marzban API"""
    pass


class VPNUserExistsError(VPNError):
    """Пользователь уже существует"""
    pass


class CalendarError(KarinaError):
    """Ошибки календаря (Google)"""
    pass


class CalendarAuthError(CalendarError):
    """Ошибка авторизации Google Calendar"""
    pass


class ReminderError(KarinaError):
    """Ошибки системы напоминаний"""
    pass


class VisionError(KarinaError):
    """Ошибки компьютерного зрения"""
    pass


class VisionInvalidImageError(VisionError):
    """Некорректное изображение"""
    pass


class ConfigError(KarinaError):
    """Ошибки конфигурации"""
    pass
