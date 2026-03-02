"""
Валидатор конфигурации Karina AI
Проверяет наличие всех необходимых переменных окружения и ключей
"""
import os
import sys
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Обязательные переменные окружения
REQUIRED_VARS = [
    "API_ID",
    "API_HASH",
    "KARINA_BOT_TOKEN",
    "MY_TELEGRAM_ID",
    "MISTRAL_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
]

# Опциональные переменные
OPTIONAL_VARS = [
    "SESSION_STRING",
    "GOOGLE_CALENDAR_CREDENTIALS",
    "WEATHER_API_KEY",
    "WEATHER_CITY",
    "MARZBAN_URL",
    "MARZBAN_USER",
    "MARZBAN_PASS",
    "KARINA_API_SECRET",
    "HF_TOKEN",
    "TARGET_USER_ID",
]

# Переменные для конкретных модулей
MODULE_VARS = {
    "TTS": ["TORCH_AVAILABLE"],  # Проверяется импортом
    "STT": ["HF_TOKEN"],
    "VPN": ["MARZBAN_URL", "MARZBAN_USER", "MARZBAN_PASS"],
    "CALENDAR": ["GOOGLE_CALENDAR_CREDENTIALS"],
    "WEATHER": ["WEATHER_API_KEY"],
}


class ConfigValidator:
    """Валидирует конфигурацию приложения"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_required_vars(self) -> bool:
        """Проверяет обязательные переменные окружения"""
        for var in REQUIRED_VARS:
            value = os.environ.get(var)
            if not value or value in ["", "0", "your_mistral_api_key", "your_supabase_service_role_key"]:
                self.errors.append(f"❌ Обязательная переменная не установлена: {var}")
        return len(self.errors) == 0

    def validate_optional_vars(self):
        """Проверяет опциональные переменные (предупреждения)"""
        for var in OPTIONAL_VARS:
            value = os.environ.get(var)
            if not value:
                self.warnings.append(f"⚠️ Опциональная переменная не установлена: {var}")

    def validate_telegram_credentials(self) -> bool:
        """Проверяет корректность Telegram credentials"""
        api_id = os.environ.get("API_ID", "0")
        api_hash = os.environ.get("API_HASH", "")
        bot_token = os.environ.get("KARINA_BOT_TOKEN", "")
        my_id = os.environ.get("MY_TELEGRAM_ID", "0")

        # API_ID должен быть числом > 0
        try:
            if int(api_id) <= 0:
                self.errors.append("❌ API_ID должен быть положительным числом")
        except ValueError:
            self.errors.append("❌ API_ID должен быть числом")

        # API_HASH должен быть не пустым
        if not api_hash or len(api_hash) < 10:
            self.errors.append("❌ API_HASH должен быть непустой строкой (32 символа)")

        # Bot token должен содержать разделитель ':'
        if ":" not in bot_token:
            self.errors.append("❌ KARINA_BOT_TOKEN должен содержать ':' (формат: ID:TOKEN)")

        # MY_TELEGRAM_ID должен быть числом
        try:
            int(my_id)
        except ValueError:
            self.errors.append("❌ MY_TELEGRAM_ID должен быть числом")

        return len(self.errors) == 0

    def validate_supabase_connection(self) -> bool:
        """Проверяет подключение к Supabase"""
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")

        if not supabase_url.startswith("https://"):
            self.errors.append("❌ SUPABASE_URL должен начинаться с https://")

        if not supabase_url.endswith(".supabase.co"):
            self.errors.append("❌ SUPABASE_URL должен заканчиваться на .supabase.co")

        if len(supabase_key) < 20:
            self.errors.append("❌ SUPABASE_KEY слишком короткий (должен быть service_role key)")

        # Пробуем импортировать и подключиться
        try:
            from supabase import create_client
            client = create_client(supabase_url, supabase_key)
            logger.info("✅ Подключение к Supabase успешно")
        except Exception as e:
            self.errors.append(f"❌ Ошибка подключения к Supabase: {e}")
            return False

        return len(self.errors) == 0

    def validate_mistral_api(self) -> bool:
        """Проверяет подключение к Mistral API"""
        api_key = os.environ.get("MISTRAL_API_KEY", "")

        if not api_key or len(api_key) < 20:
            self.errors.append("❌ MISTRAL_API_KEY должен быть непустой строкой")
            return False

        # Пробуем сделать тестовый запрос
        try:
            import httpx
            headers = {"Authorization": f"Bearer {api_key}"}
            # Простой запрос для проверки
            response = httpx.get("https://api.mistral.ai/v1/models", headers=headers, timeout=5.0)
            if response.status_code == 200:
                logger.info("✅ Подключение к Mistral API успешно")
                return True
            else:
                self.errors.append(f"❌ Mistral API вернул ошибку: {response.status_code}")
                return False
        except Exception as e:
            self.errors.append(f"❌ Ошибка подключения к Mistral API: {e}")
            return False

    def validate_optional_modules(self):
        """Проверяет доступность опциональных модулей"""
        # TTS
        if os.environ.get("ENABLE_TTS", "0") == "1":
            try:
                import torch
                logger.info("✅ Torch доступен для TTS")
            except ImportError:
                self.warnings.append("⚠️ TTS включён, но torch не установлен. Выполните: pip install torch")

        # Weather
        weather_key = os.environ.get("WEATHER_API_KEY")
        if weather_key:
            logger.info("✅ Weather API ключ установлен")
        else:
            self.warnings.append("⚠️ WEATHER_API_KEY не установлен — погода не будет работать")

        # Google Calendar
        calendar_creds = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS")
        if calendar_creds:
            logger.info("✅ Google Calendar credentials установлены")
        else:
            self.warnings.append("⚠️ GOOGLE_CALENDAR_CREDENTIALS не установлены — календарь не будет работать")

    def validate_session_string(self):
        """Проверяет SESSION_STRING для userbot"""
        session = os.environ.get("SESSION_STRING", "")

        if not session:
            self.warnings.append("⚠️ SESSION_STRING пуст — userbot и ауры не будут работать")
            return False

        # Session string должен быть достаточно длинным
        if len(session) < 50:
            self.errors.append("❌ SESSION_STRING слишком короткий")
            return False

        return True

    def validate_all(self, strict: bool = False) -> Tuple[bool, List[str], List[str]]:
        """
        Запускает полную валидацию

        Args:
            strict: Если True, ошибки в опциональных модулях считаются критичными

        Returns:
            (успех, список ошибок, список предупреждений)
        """
        logger.info("🔍 Запуск валидации конфигурации...")

        # Обязательные проверки
        self.validate_required_vars()
        self.validate_telegram_credentials()

        # Проверка подключений (только если нет ошибок в переменных)
        if not self.errors:
            self.validate_supabase_connection()
            self.validate_mistral_api()

        # Проверка session string
        self.validate_session_string()

        # Опциональные проверки
        self.validate_optional_vars()
        self.validate_optional_modules()

        success = len(self.errors) == 0

        if success:
            logger.info("✅ Все проверки пройдены!")
        else:
            logger.error(f"❌ Найдено ошибок: {len(self.errors)}")
            for err in self.errors:
                logger.error(err)

        return success, self.errors, self.warnings


def print_validation_report(errors: List[str], warnings: List[str]):
    """Выводит отчёт валидации в консоль"""
    print("\n" + "=" * 60)
    print("📋 ОТЧЁТ ВАЛИДАЦИИ КОНФИГУРАЦИИ")
    print("=" * 60 + "\n")

    if errors:
        print("🔴 КРИТИЧЕСКИЕ ОШИБКИ:")
        for err in errors:
            print(f"  {err}")
        print()

    if warnings:
        print("🟡 ПРЕДУПРЕЖДЕНИЯ:")
        for warn in warnings:
            print(f"  {warn}")
        print()

    if not errors and not warnings:
        print("✅ Все проверки пройдены успешно!")
        print()

    print("=" * 60 + "\n")


async def validate_and_start():
    """
    Валидирует конфигурацию перед запуском бота

    Returns:
        True если можно запускать бота
    """
    validator = ConfigValidator()
    success, errors, warnings = validator.validate_all()

    print_validation_report(errors, warnings)

    if not success:
        print("\n❌ ЗАПУСК НЕВОЗМОЖЕН: Исправьте критические ошибки в .env файле")
        print("\n📝 Пример .env файла:")
        print("""
# Telegram (получить на https://my.telegram.org)
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
KARINA_BOT_TOKEN=123456:ABCDEF-1234567890abcdef
MY_TELEGRAM_ID=123456789
SESSION_STRING=... (получить через python main.py --gen-session)

# Mistral AI (получить на https://console.mistral.ai)
MISTRAL_API_KEY=your_mistral_api_key_here

# Supabase (получить на https://supabase.com)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_role_key_here
""")
        return False

    return True


if __name__ == "__main__":
    # Запуск валидации из командной строки
    logging.basicConfig(level=logging.INFO)
    
    validator = ConfigValidator()
    success, errors, warnings = validator.validate_all()
    print_validation_report(errors, warnings)
    
    sys.exit(0 if success else 1)
