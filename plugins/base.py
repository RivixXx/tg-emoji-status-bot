"""
Plugin System for Karina AI
Базовый класс плагина и менеджер плагинов
"""
import logging
import importlib
import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class PluginConfig:
    """Конфигурация плагина"""
    name: str
    enabled: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """Базовый класс для всех плагинов"""
    
    # Метаданные плагина (переопределяются в наследниках)
    name: str = "base_plugin"
    version: str = "1.0.0"
    description: str = "Base plugin class"
    author: str = "Unknown"
    
    def __init__(self, config: PluginConfig = None):
        self.config = config or PluginConfig(name=self.name)
        self.enabled = self.config.enabled
        self._initialized = False
    
    @abstractmethod
    async def initialize(self):
        """Инициализация плагина (загружает конфигурацию, подключает ресурсы)"""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Завершение работы плагина (освобождает ресурсы)"""
        pass
    
    async def on_startup(self):
        """Вызывается при запуске приложения"""
        pass
    
    async def on_shutdown(self):
        """Вызывается при остановке приложения"""
        pass
    
    def get_settings(self) -> Dict[str, Any]:
        """Получить настройки плагина"""
        return self.config.settings
    
    def update_settings(self, settings: Dict[str, Any]):
        """Обновить настройки плагина"""
        self.config.settings.update(settings)
    
    def is_enabled(self) -> bool:
        """Проверить, включен ли плагин"""
        return self.enabled
    
    def enable(self):
        """Включить плагин"""
        self.enabled = True
        logger.info(f"✅ Плагин '{self.name}' включен")
    
    def disable(self):
        """Выключить плагин"""
        self.enabled = False
        logger.info(f"⏸️ Плагин '{self.name}' выключен")
    
    def __repr__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"<Plugin {self.name} v{self.version} [{status}]>"


class PluginManager:
    """Менеджер плагинов - загрузка, регистрация, управление"""
    
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_configs: Dict[str, PluginConfig] = {}
        self.config_file = self.plugins_dir / "plugins_config.json"
        
    def load_config(self):
        """Загружает конфигурацию плагинов из файла"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, config_data in data.items():
                        self.plugin_configs[name] = PluginConfig(
                            name=name,
                            enabled=config_data.get('enabled', True),
                            settings=config_data.get('settings', {})
                        )
                logger.info(f"📦 Загружена конфигурация {len(self.plugin_configs)} плагинов")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки конфигурации плагинов: {e}")
        else:
            logger.info("📦 Файл конфигурации плагинов не найден, используем значения по умолчанию")
    
    def save_config(self):
        """Сохраняет конфигурацию плагинов в файл"""
        try:
            data = {}
            for name, config in self.plugin_configs.items():
                data[name] = {
                    'enabled': config.enabled,
                    'settings': config.settings
                }
            
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Конфигурация плагинов сохранена")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения конфигурации плагинов: {e}")
    
    def discover_plugins(self) -> List[str]:
        """Находит все доступные плагины в директории"""
        plugin_files = []
        
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            return plugin_files
        
        for file in self.plugins_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            plugin_files.append(file.stem)
        
        logger.info(f"🔍 Найдено {len(plugin_files)} потенциальных плагинов")
        return plugin_files
    
    def load_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Загружает плагин по имени"""
        try:
            module_path = self.plugins_dir / f"{plugin_name}.py"
            if not module_path.exists():
                logger.error(f"❌ Плагин {plugin_name} не найден")
                return None
            
            # Загружаем модуль динамически
            spec = importlib.util.spec_from_file_location(f"plugins.{plugin_name}", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Ищем класс плагина (первый подкласс Plugin)
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, Plugin) and 
                    attr is not Plugin):
                    plugin_class = attr
                    break
            
            if not plugin_class:
                logger.error(f"❌ В плагине {plugin_name} не найден класс Plugin")
                return None
            
            # Получаем конфиг или создаём дефолтный
            config = self.plugin_configs.get(plugin_name, PluginConfig(name=plugin_name))
            if plugin_name not in self.plugin_configs:
                self.plugin_configs[plugin_name] = config
            
            # Создаём экземпляр плагина
            plugin = plugin_class(config)
            logger.info(f"✅ Плагин {plugin_name} v{plugin.version} загружен")
            
            return plugin
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки плагина {plugin_name}: {e}")
            return None
    
    def register_plugin(self, plugin: Plugin):
        """Регистрирует плагин в менеджере"""
        self.plugins[plugin.name] = plugin
        logger.info(f"📦 Плагин {plugin.name} зарегистрирован")
    
    async def initialize_all(self):
        """Инициализирует все включенные плагины"""
        for name, plugin in self.plugins.items():
            if plugin.is_enabled():
                try:
                    await plugin.initialize()
                    logger.info(f"✅ Плагин {name} инициализирован")
                except Exception as e:
                    logger.error(f"❌ Ошибка инициализации плагина {name}: {e}")
                    plugin.disable()
    
    async def shutdown_all(self):
        """Завершает работу всех плагинов"""
        for name, plugin in self.plugins.items():
            try:
                await plugin.shutdown()
                logger.info(f"🛑 Плагин {name} остановлен")
            except Exception as e:
                logger.error(f"❌ Ошибка остановки плагина {name}: {e}")
    
    async def startup_all(self):
        """Вызывает on_startup для всех включенных плагинов"""
        for name, plugin in self.plugins.items():
            if plugin.is_enabled():
                try:
                    await plugin.on_startup()
                except Exception as e:
                    logger.error(f"❌ Ошибка startup плагина {name}: {e}")
    
    async def shutdown_all_hooks(self):
        """Вызывает on_shutdown для всех плагинов"""
        for name, plugin in self.plugins.items():
            if plugin.is_enabled():
                try:
                    await plugin.on_shutdown()
                except Exception as e:
                    logger.error(f"❌ Ошибка shutdown плагина {name}: {e}")
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Получает плагин по имени"""
        return self.plugins.get(name)
    
    def get_enabled_plugins(self) -> List[Plugin]:
        """Получает список всех включенных плагинов"""
        return [p for p in self.plugins.values() if p.is_enabled()]
    
    def enable_plugin(self, name: str) -> bool:
        """Включает плагин"""
        if name in self.plugins:
            self.plugins[name].enable()
            if name in self.plugin_configs:
                self.plugin_configs[name].enabled = True
            self.save_config()
            return True
        return False
    
    def disable_plugin(self, name: str) -> bool:
        """Выключает плагин"""
        if name in self.plugins:
            self.plugins[name].disable()
            if name in self.plugin_configs:
                self.plugin_configs[name].enabled = False
            self.save_config()
            return True
        return False
    
    def list_plugins(self) -> List[Dict]:
        """Возвращает список всех плагинов с информацией"""
        result = []
        for name, plugin in self.plugins.items():
            result.append({
                'name': plugin.name,
                'version': plugin.version,
                'description': plugin.description,
                'author': plugin.author,
                'enabled': plugin.is_enabled(),
                'settings': plugin.get_settings()
            })
        return result


# Глобальный экземпляр менеджера плагинов
plugin_manager = PluginManager()
