# 🔌 Plugin System Guide

## Обзор

Система плагинов Karina AI позволяет расширять функционал бота через подключаемые модули.

## Архитектура

```
plugins/
├── base.py              # Базовый класс Plugin и PluginManager
├── __init__.py          # Экспорт системы
├── plugins_config.json  # Конфигурация плагинов
└── google_calendar.py   # Пример плагина
```

## Создание плагина

### 1. Базовый класс

```python
from plugins.base import Plugin, PluginConfig

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    description = "Мой плагин"
    author = "Author Name"
    
    def __init__(self, config: PluginConfig = None):
        super().__init__(config)
    
    async def initialize(self):
        """Инициализация плагина"""
        if not self.enabled:
            return
        # Код инициализации
    
    async def shutdown(self):
        """Завершение работы"""
        # Очистка ресурсов
```

### 2. Конфигурация

Добавьте в `plugins/plugins_config.json`:

```json
{
  "my_plugin": {
    "enabled": true,
    "settings": {
      "option1": "value1",
      "option2": 42
    }
  }
}
```

### 3. Регистрация

Плагин автоматически загружается через `PluginManager`:

```python
# В main.py
from plugins import plugin_manager

# Загрузка при старте
plugin_manager.load_config()
discovered = plugin_manager.discover_plugins()

for plugin_name in discovered:
    plugin = plugin_manager.load_plugin(plugin_name)
    if plugin:
        plugin_manager.register_plugin(plugin)

await plugin_manager.initialize_all()
```

## Управление плагинами

### API Endpoints

```bash
# Список плагинов
GET /api/plugins

# Включить плагин
POST /api/plugins/<name>/enable
Headers: X-Karina-Secret: <secret>

# Выключить плагин
POST /api/plugins/<name>/disable
Headers: X-Karina-Secret: <secret>

# Настройки плагина
GET /api/plugins/<name>/settings
POST /api/plugins/<name>/settings
Headers: X-Karina-Secret: <secret>
```

### Программное управление

```python
from plugins import plugin_manager

# Получить плагин
plugin = plugin_manager.get_plugin("google_calendar")

# Включить/выключить
plugin_manager.enable_plugin("google_calendar")
plugin_manager.disable_plugin("google_calendar")

# Получить настройки
settings = plugin.get_settings()

# Обновить настройки
plugin.update_settings({"new_option": "value"})
```

## Жизненный цикл плагина

1. **Discovery** — `discover_plugins()` находит `.py` файлы в `plugins/`
2. **Loading** — `load_plugin()` загружает модуль динамически
3. **Registration** — `register_plugin()` добавляет в реестр
4. **Initialization** — `initialize_all()` вызывает `initialize()` у включенных
5. **Startup** — `startup_all()` вызывает `on_startup()` при запуске бота
6. **Shutdown** — `shutdown_all()` и `shutdown_all_hooks()` при остановке

## Best Practices

### ✅ Делайте

- Проверяйте `self.enabled` перед выполнением
- Обрабатывайте ImportError для опциональных зависимостей
- Освобождайте ресурсы в `shutdown()`
- Используйте логирование через `logger`

### ❌ Не делайте

- Не полагайтесь на другие плагины напрямую
- Не блокируйте event loop
- Не храните чувствительные данные в конфиге

## Пример: Плагин погоды

```python
from plugins.base import Plugin, PluginConfig
import asyncio

class WeatherPlugin(Plugin):
    name = "weather"
    version = "1.0.0"
    description = "Погода через OpenWeatherMap"
    
    def __init__(self, config: PluginConfig = None):
        super().__init__(config)
        self._cache = {}
    
    async def initialize(self):
        if not self.enabled:
            return
        
        # Проверка зависимостей
        try:
            from brains.weather import get_weather
            self._initialized = True
        except ImportError:
            self.disable()
    
    async def shutdown(self):
        self._cache.clear()
    
    async def get_current_weather(self, city: str = None):
        if not self.enabled or not self._initialized:
            return None
        
        settings = self.get_settings()
        city = city or settings.get('default_city', 'Moscow')
        
        # Кэширование
        if city in self._cache:
            return self._cache[city]
        
        from brains.weather import get_weather
        weather = await get_weather(city)
        self._cache[city] = weather
        
        return weather
```

## Отладка

### Включение логов

```python
import logging
logging.getLogger('plugins').setLevel(logging.DEBUG)
```

### Проверка статуса

```python
# В Python консоли
from plugins import plugin_manager

print(plugin_manager.list_plugins())
# [{'name': 'google_calendar', 'enabled': True, ...}]
```

## Миграция существующих модулей

### Из модуля в плагин

**До:**
```python
# brains/calendar.py
async def get_upcoming_events():
    ...
```

**После:**
```python
# plugins/google_calendar.py
class GoogleCalendarPlugin(Plugin):
    async def get_upcoming_events(self):
        ...

# brains/calendar.py
async def get_upcoming_events():
    from plugins import plugin_manager
    plugin = plugin_manager.get_plugin('google_calendar')
    if plugin and plugin.is_available():
        return await plugin.get_upcoming_events()
    return "Calendar plugin unavailable"
```

## FAQ

### Q: Как отключить плагин?
A: Через API или измените `plugins_config.json` и перезапустите бота.

### Q: Можно ли загружать плагины на лету?
A: Да, но требуется вызов `initialize()` вручную.

### Q: Где хранить данные плагина?
A: В Supabase через отдельные таблицы или в `settings`.

### Q: Как тестировать плагин?
A: Создайте тестовый конфиг и используйте `plugin_manager` в тестах.
