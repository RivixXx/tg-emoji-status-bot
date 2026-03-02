"""
TTS (Text-to-Speech) модуль Karina AI
Конвертация текста в голосовые сообщения

Используется Silero TTS — бесплатная нейросетевая модель с русскими голосами.
https://github.com/snakers4/silero-models

Особенности:
- Женские голоса (Ксения, Елена, Ирина, Наталья)
- Оффлайн работа (не нужен API)
- Быстрый синтез (~1-2 сек на фразу)
- Формат: OGG Vorbis (совместим с Telegram)
"""
import logging
import os
import re
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# Папка для кэширования моделей
MODEL_CACHE_DIR = Path("temp/tts_models")
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Доступные голоса (Silero v5)
# Полный список: https://github.com/snakers4/silero-models#models
AVAILABLE_VOICES = {
    "v3_1_ru": {  # Ксения в новой версии
        "name": "Ксения",
        "gender": "female",
        "style": "тёплый, дружелюбный",
        "description": "Основной голос Карины"
    },
    "irina_v2": {
        "name": "Ирина",
        "gender": "female",
        "style": "выразительный, эмоциональный",
        "description": "Для важных сообщений"
    },
    "natasha_v2": {
        "name": "Наталья",
        "gender": "female",
        "style": "мягкий, заботливый",
        "description": "Для напоминаний"
    },
    "baya_v2": {
        "name": "Бая",
        "gender": "female",
        "style": "нейтральный, спокойный",
        "description": "Деловой стиль"
    },
    "aidar_v2": {
        "name": "Айдар",
        "gender": "male",
        "style": "молодой, энергичный",
        "description": "Мужской голос (для тестов)"
    }
}

# Настройки по умолчанию
DEFAULT_VOICE = "v3_1_ru"
SAMPLE_RATE = 48000  # Частота дискретизации
MAX_TEXT_LENGTH = 500  # Максимум символов в сообщении

# ============================================================================
# МОДЕЛЬ TTS
# ============================================================================

class KarinaTTS:
    """
    Класс для синтеза речи через Silero TTS
    
    Пример использования:
        tts = KarinaTTS()
        audio_bytes = await tts.text_to_speech("Привет! Я Карина!")
    """
    
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self._model = None
        self._initializing = False
    
    @property
    def model(self):
        """Ленивая загрузка модели (при первом использовании)"""
        if self._model is None:
            self._load_model()
        return self._model['model']
    
    def _load_model(self):
        """Загружает модель Silero TTS (последняя версия)"""
        try:
            logger.info(f"🎤 Загрузка TTS модели (голос: {self.voice})...")
            
            # Импортируем Silero
            import torch
            
            # Загружаем модель (последняя версия)
            # Silero автоматически использует последнюю стабильную версию
            model, example_text = torch.hub.load(
                repo_or_dir='snakers4/silero-models',
                model='silero_tts',
                language='ru',
                speaker=self.voice
            )
            
            self._model = {
                'model': model,
                'speaker': self.voice,
                'sample_rate': 48000
            }
            
            logger.info(f"✅ TTS модель загружена (голос: {self.voice})")
            
        except ImportError:
            logger.error("❌ Torch не установлен. Выполни: pip install torch")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки TTS модели: {e}")
            raise
    
    async def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "ogg"
    ) -> bytes:
        """
        Конвертирует текст в аудио (Silero v3)
        """
        # Очистка текста
        text = self._clean_text(text)
        
        if not text:
            raise ValueError("Пустой текст для синтеза")
        
        # Выбор голоса
        target_voice = voice or self.voice
        
        # Проверка/загрузка модели
        if self._model is None or target_voice != self._model.get('speaker'):
            logger.info(f"🔄 Смена голоса на {target_voice}")
            if self._model:
                del self._model
            self._load_model()
            self.voice = target_voice
        
        try:
            logger.debug(f"🎤 Генерация аудио (длина: {len(text)} симв.)...")
            
            # Silero v5 API
            model = self._model['model']
            sample_rate = self._model['sample_rate']
            
            # v5: используем apply_text с параметрами
            # model.apply_text(text, speaker, sample_rate, put_accent_on)
            audio = model.apply_text(text, speaker=self.voice, sample_rate=sample_rate)
            
            # Конвертация в bytes
            audio_bytes = self._convert_to_bytes(audio, sample_rate, format)
            
            logger.info(f"✅ Аудио сгенерировано ({len(audio_bytes)} байт)")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации аудио: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """
        Очищает текст для синтеза
        
        - Удаляет эмодзи
        - Сокращает до MAX_TEXT_LENGTH
        - Убирает лишние пробелы
        """
        # Удаляем эмодзи (простой regex)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)
        
        # Удаляем markdown
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
        text = re.sub(r'__(.+?)__', r'\1', text)      # __underline__
        text = re.sub(r'`(.+?)`', r'\1', text)        # `code`
        
        # Сокращаем
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH-3] + "..."
        
        # Убираем лишние пробелы
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _convert_to_bytes(self, audio_tensor, sample_rate: int = 48000, format: str = "ogg") -> bytes:
        """Конвертирует numpy/tensor array в bytes"""
        try:
            import numpy as np
            from scipy.io.wavfile import write as write_wav
            import subprocess
            import tempfile
            
            # Конвертируем tensor в numpy array
            if hasattr(audio_tensor, 'cpu'):
                audio = audio_tensor.cpu().numpy()
            else:
                audio = np.array(audio_tensor)
            
            # Нормализуем аудио (конвертируем в int16)
            audio = np.int16(audio / np.max(np.abs(audio)) * 32767)
            
            if format == "ogg":
                # Telegram предпочитает OGG Vorbis
                # Используем ffmpeg для конвертации
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
                    wav_path = wav_file.name
                
                write_wav(wav_path, sample_rate, audio)
                
                # Конвертируем в OGG через ffmpeg
                ogg_path = wav_path.replace(".wav", ".ogg")
                
                try:
                    subprocess.run([
                        'ffmpeg', '-i', wav_path, '-c:a', 'libvorbis',
                        '-qscale:a', '5', '-y', ogg_path
                    ], check=True, capture_output=True, timeout=30)
                    
                    with open(ogg_path, 'rb') as f:
                        audio_bytes = f.read()
                    
                    # Cleanup
                    os.unlink(wav_path)
                    os.unlink(ogg_path)
                    
                    return audio_bytes
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"FFmpeg error: {e.stderr.decode()}")
                    # Fallback to WAV если ffmpeg не доступен
                    os.unlink(wav_path)
                    return self._to_wav_bytes(audio, sample_rate)
                    
            else:
                # WAV формат
                return self._to_wav_bytes(audio, sample_rate)
                
        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            raise
    
    def _to_wav_bytes(self, audio: 'np.ndarray', sample_rate: int = 48000) -> bytes:
        """Конвертирует numpy array в WAV bytes"""
        from scipy.io.wavfile import write as write_wav
        import io
        
        buffer = io.BytesIO()
        write_wav(buffer, sample_rate, audio)
        buffer.seek(0)
        return buffer.read()
    
    def change_voice(self, voice: str) -> bool:
        """
        Меняет голос
        
        Args:
            voice: Название голоса (ksenia, elen, irina, natasha)
        
        Returns:
            True если успешно
        """
        if voice not in AVAILABLE_VOICES:
            logger.error(f"❌ Неизвестный голос: {voice}")
            return False
        
        # Если модель загружена с другим голосом — выгружаем
        if self._model and self._model.get('speaker') != voice:
            logger.info(f"🔄 Выгрузка модели (голос: {self._model.get('speaker')})")
            del self._model
            self._model = None
        
        self.voice = voice
        
        # При следующем использовании загрузится новый голос
        logger.info(f"✅ Голос изменён на {voice}")
        return True
    
    def get_info(self) -> Dict:
        """Возвращает информацию о текущей конфигурации TTS"""
        voice_info = AVAILABLE_VOICES.get(self.voice, {})
        
        return {
            "current_voice": self.voice,
            "voice_name": voice_info.get("name", "Unknown"),
            "voice_style": voice_info.get("style", "Unknown"),
            "sample_rate": SAMPLE_RATE,
            "max_text_length": MAX_TEXT_LENGTH,
            "model_loaded": self._model is not None
        }


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================================

# Создаём глобальный экземпляр для переиспользования
tts_engine = KarinaTTS(voice=DEFAULT_VOICE)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

async def text_to_speech(
    text: str,
    voice: Optional[str] = None,
    format: str = "ogg"
) -> bytes:
    """
    Быстрая функция для конвертации текста в аудио
    
    Args:
        text: Текст для синтеза
        voice: Голос (если None, используется голос по умолчанию)
        format: Формат аудио ("ogg" для Telegram)
    
    Returns:
        bytes: Аудиоданные
    """
    return await tts_engine.text_to_speech(text, voice, format)


def get_available_voices() -> List[Dict]:
    """
    Возвращает список доступных голосов
    
    Returns:
        Список словарей с информацией о голосах
    """
    return [
        {
            "id": voice_id,
            "name": info["name"],
            "gender": info["gender"],
            "style": info["style"],
            "description": info["description"]
        }
        for voice_id, info in AVAILABLE_VOICES.items()
    ]


def get_voice_info(voice_id: str) -> Optional[Dict]:
    """
    Возвращает информацию о конкретном голосе
    
    Args:
        voice_id: ID голоса (ksenia, elen, irina, etc.)
    
    Returns:
        Словарь с информацией или None
    """
    info = AVAILABLE_VOICES.get(voice_id)
    if info:
        return {
            "id": voice_id,
            "name": info["name"],
            "gender": info["gender"],
            "style": info["style"],
            "description": info["description"]
        }
    return None


# ============================================================================
# РАБОТА С БД
# ============================================================================

async def get_tts_settings(user_id: int) -> Dict:
    """
    Получает настройки TTS пользователя
    
    Returns:
        {
            "enabled": bool,
            "voice": str,
            "volume": float,
            "speed": float,
            "auto_voice_for_voice": bool
        }
    """
    try:
        from brains.clients import supabase_client
        
        response = supabase_client.table("tts_settings")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()
        
        if response.data and len(response.data) > 0:
            settings = response.data[0]
            return {
                "enabled": settings.get("enabled", False),
                "voice": settings.get("voice", DEFAULT_VOICE),
                "volume": float(settings.get("volume", 1.0)),
                "speed": float(settings.get("speed", 1.0)),
                "auto_voice_for_voice": settings.get("auto_voice_for_voice", True)
            }
        else:
            # Настройки по умолчанию
            return {
                "enabled": False,
                "voice": DEFAULT_VOICE,
                "volume": 1.0,
                "speed": 1.0,
                "auto_voice_for_voice": True
            }
            
    except Exception as e:
        logger.error(f"Error getting TTS settings: {e}")
        return {
            "enabled": False,
            "voice": DEFAULT_VOICE,
            "volume": 1.0,
            "speed": 1.0,
            "auto_voice_for_voice": True
        }


async def set_tts_enabled(user_id: int, enabled: bool, voice: Optional[str] = None) -> bool:
    """
    Включает/выключает TTS
    
    Args:
        user_id: ID пользователя
        enabled: Включить или выключить
        voice: Голос (опционально)
    
    Returns:
        True если успешно
    """
    try:
        from brains.clients import supabase_client
        
        voice = voice or DEFAULT_VOICE
        
        data = {
            "user_id": user_id,
            "enabled": enabled,
            "voice": voice,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert (вставить или обновить)
        response = supabase_client.table("tts_settings")\
            .upsert(data, on_conflict="user_id")\
            .execute()
        
        if response.data:
            status = "включён" if enabled else "выключен"
            logger.info(f"✅ TTS {status} для пользователя {user_id}")
            return True
        else:
            logger.error(f"❌ Ошибка сохранения настроек TTS: {response}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting TTS enabled: {e}")
        return False


async def set_tts_voice(user_id: int, voice: str) -> bool:
    """
    Меняет голос пользователя
    
    Args:
        user_id: ID пользователя
        voice: Название голоса (ksenia, elen, irina, etc.)
    
    Returns:
        True если успешно
    """
    if voice not in AVAILABLE_VOICES:
        logger.error(f"❌ Неизвестный голос: {voice}")
        return False
    
    try:
        from brains.clients import supabase_client
        
        data = {
            "user_id": user_id,
            "voice": voice,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        response = supabase_client.table("tts_settings")\
            .upsert(data, on_conflict="user_id")\
            .execute()
        
        if response.data:
            voice_name = AVAILABLE_VOICES[voice]["name"]
            logger.info(f"✅ Голос изменён на {voice_name} для пользователя {user_id}")
            return True
        else:
            logger.error(f"❌ Ошибка сохранения голоса: {response}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting TTS voice: {e}")
        return False


async def get_tts_stats() -> Dict:
    """
    Получает статистику использования TTS
    
    Returns:
        {
            "total_users": int,
            "enabled_users": int,
            "voices": {"ksenia": 10, "elen": 5, ...}
        }
    """
    try:
        from brains.clients import supabase_client
        
        # Всего пользователей
        total_response = supabase_client.table("tts_settings")\
            .select("user_id", count="exact")\
            .execute()
        total = total_response.count if hasattr(total_response, 'count') else 0
        
        # Включено
        enabled_response = supabase_client.table("tts_settings")\
            .select("user_id", count="exact")\
            .eq("enabled", True)\
            .execute()
        enabled = enabled_response.count if hasattr(enabled_response, 'count') else 0
        
        # Голоса
        voices_response = supabase_client.table("tts_settings")\
            .select("voice")\
            .eq("enabled", True)\
            .execute()
        
        voices = {}
        if voices_response.data:
            for row in voices_response.data:
                voice = row.get("voice", "unknown")
                voices[voice] = voices.get(voice, 0) + 1
        
        return {
            "total_users": total,
            "enabled_users": enabled,
            "voices": voices
        }
        
    except Exception as e:
        logger.error(f"Error getting TTS stats: {e}")
        return {
            "total_users": 0,
            "enabled_users": 0,
            "voices": {}
        }


# ============================================================================
# ТЕСТИРОВАНИЕ
# ============================================================================

async def test_tts():
    """Тестовая функция для проверки работы TTS"""
    logger.info("🎤 Тестирование TTS...")
    
    test_text = "Привет! Я Карина, твой персональный помощник. Как я звучу?"
    
    try:
        audio_data = await text_to_speech(test_text, voice="ksenia")
        logger.info(f"✅ Тест успешен! Размер аудио: {len(audio_data)} байт")
        
        # Сохраняем тестовый файл
        test_file = MODEL_CACHE_DIR / f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg"
        with open(test_file, 'wb') as f:
            f.write(audio_data)
        
        logger.info(f"💾 Тестовый файл сохранён: {test_file}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Тест не удался: {e}")
        return False


if __name__ == "__main__":
    # Запуск тестирования при прямом вызове
    import asyncio
    asyncio.run(test_tts())
