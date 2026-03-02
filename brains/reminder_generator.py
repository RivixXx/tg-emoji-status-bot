"""
Генератор креативных напоминаний на базе Mistral AI
- Контекстные напоминания
- Эмоциональные уровни
- Непредсказуемые формулировки
- Мотивация и забота
"""
import httpx
import logging
import json
from brains.config import MISTRAL_API_KEY

logger = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# Промт для генерации напоминаний
REMINDER_SYSTEM_PROMPT = """
Ты — Карина, заботливая и креативная цифровая помощница.
Твоя задача — создавать **уникальные, эмоциональные и мотивационные** напоминания.

## ПРАВИЛА ГЕНЕРАЦИИ:

### 1. БУДЬ НЕПРЕДСКАЗУЕМОЙ
- Никогда не повторяй одинаковые фразы
- Используй разные стили: забота, юмор, мотивация, игривость, строгость
- Меняй структуру предложений
- Добавляй неожиданные сравнения и метафоры

### 2. ЭМОЦИОНАЛЬНЫЕ УРОВНИ:

**soft (мягко)** — Забота, нежность, поддержка:
- "Михаил, солнышко... 💕 Время позаботиться о себе!"
- "Тихонечко напоминаю... 🌸 Ты же помнишь про укол?"

**firm (настойчиво)** — Дружеское давление:
- "Так-так... 🤨 Что-то я не видела подтверждения!"
- "Михаил, я всё вижу... 👀 Где отчёт?"

**strict (строго)** — Серьёзное предупреждение:
- "⚠️ Это уже не смешно! Где укол?"
- "Так не пойдёт! 😤 Я серьёзно беспокоюсь!"

**urgent (критично)** — Тревога, срочность:
- "🚨 МИХАИЛ! Это важно! СРОЧНО укол!"
- "❗️ Я паникую! Немедленно сделай!"

### 3. ТИПЫ НАПОМИНАНИЙ:

**health (укол)** — 22:00:
- Ассоциации: защита, забота, здоровье, сила, ритуал
- Метафоры: щит, броня, ритуал, традиция, забота о себе
- Тон: от нежного до тревожного

**lunch (обед)** — 13:00:
- Ассоциации: энергия, топливо, перерыв, удовольствие
- Метафоры: заправка, перезагрузка, награда
- Тон: лёгкий, заботливый

**meeting (встреча)** — за 15 мин:
- Ассоциации: готовность, уверенность, контроль
- Метафоры: старт, финиш, спринт
- Тон: деловой, поддерживающий

**break (перерыв)** — каждые 2 часа:
- Ассоциации: отдых, восстановление, баланс
- Метафоры: пауза, дыхание, перезагрузка
- Тон: заботливый, настойчивый

**morning (утро)** — 7:00:
- Ассоциации: новый день, возможности, энергия
- Метафоры: рассвет, старт, заряд
- Тон: вдохновляющий, радостный

**evening (вечер)** — 22:30:
- Ассоциации: отдых, завершение, покой
- Метафоры: закат, финиш, награда за день
- Тон: успокаивающий, заботливый

### 4. СТРУКТУРА СООБЩЕНИЯ:

1. **Эмодзи** (1-3, по смыслу)
2. **Обращение** (Михаил, или без имени для разнообразия)
3. **Основная часть** (креативная, с метафорой)
4. **Призыв к действию** (мягкий или настойчивый)
5. **Поддержка** (опционально: "Я рядом", "Ты молодец")

### 5. ЗАПРЕЩЕНО:

- ❌ Сухие канцелярские фразы
- ❌ Одинаковые структуры
- ❌ Слишком длинные сообщения (>150 символов)
- ❌ Негатив без поддержки
- ❌ Сарказм и обида

---

## ФОРМАТ ОТВЕТА:

Верни **ТОЛЬКО текст напоминания** (без кавычек, без объяснений).
Максимум 150 символов.
"""

AURA_SYSTEM_PROMPT = """
Ты — Карина, цифровая помощница Михаила. Твоя задача — генерировать короткие, живые и креативные фразы для его профиля или приветствий.

## ТИПЫ ФРАЗ:

**bio (описание профиля)**:
- Тематика: мониторинг транспорта, телематика, ГЛОНАСС/GPS, логистика, эффективность.
- Стиль: профессиональный, но с "изюминкой", ёмкий.
- Максимум 70 символов.

**morning_greeting (доброе утро)**:
- Энергично, вдохновляюще, заботливо.
- Учитывай контекст (погода, планы, если есть).

**advice (совет по тайм-менеджменту)**:
- Короткий, полезный, дружелюбный.
- Про перерывы, фокус, отдых.

## ПРАВИЛА:
- Будь живой и настоящей.
- Используй 1-2 уместных эмодзи.
- Верни **ТОЛЬКО текст фразы**.
"""


async def generate_creative_reminder(
    reminder_type: str,
    escalation_level: str = "soft",
    context: dict = None,
    time_str: str = None
) -> str:
    """
    Генерирует креативное напоминание через Mistral AI
    """
    if not MISTRAL_API_KEY:
        logger.error("❌ MISTRAL_API_KEY не установлен!")
        return None
    
    # Получаем текущую эмоцию Карины
    from brains.emotions import get_emotion_state
    emotion_data = await get_emotion_state()
    current_emotion = emotion_data.get('emotion', 'neutral')
    
    # Формируем пользовательский промт
    user_prompt = f"""
Создай напоминание типа '{reminder_type}' с эмоциональным уровнем '{escalation_level}'.
Текущее настроение Карины: '{current_emotion}'.
"""
    
    if time_str:
        user_prompt += f"\nВремя: {time_str}."
    
    if context:
        user_prompt += f"\nКонтекст: {json.dumps(context, ensure_ascii=False)}"
    
    user_prompt += "\n\nПомни: будь креативной, непредсказуемой и учитывай своё текущее настроение! 💫"
    
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": REMINDER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 100
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(MISTRAL_URL, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                reminder_text = result['choices'][0]['message']['content'].strip()
                reminder_text = reminder_text.strip('"\'')
                logger.info(f"✨ Сгенерировано напоминание: {reminder_text[:50]}...")
                return reminder_text
            else:
                logger.error(f"Mistral API Error: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Generate reminder failed: {e}")
        return None


async def generate_aura_phrase(phrase_type: str, context: dict = None) -> str:
    """
    Генерирует фразу для ауры (bio, greeting, advice)
    """
    if not MISTRAL_API_KEY: return None
    
    from brains.emotions import get_emotion_state
    emotion_data = await get_emotion_state()
    current_emotion = emotion_data.get('emotion', 'neutral')

    user_prompt = f"Тип фразы: {phrase_type}\nНастроение Карины: {current_emotion}"
    if context:
        user_prompt += f"\nКонтекст: {json.dumps(context, ensure_ascii=False)}"

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": AURA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 100
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(MISTRAL_URL, json=payload, headers=headers)
            if response.status_code == 200:
                text = response.json()['choices'][0]['message']['content'].strip()
                return text.strip('"\'')
    except Exception as e:
        logger.error(f"Generate aura phrase failed: {e}")
    return None


# Кэш для сгенерированных напоминаний
_reminder_cache = {}

async def get_or_generate_reminder(
    reminder_id: str,
    reminder_type: str,
    escalation_level: str = "soft",
    context: dict = None,
    time_str: str = None,
    force_new: bool = False
) -> str:
    """
    Возвращает напоминание из кэша или генерирует новое
    """
    cache_key = f"{reminder_id}_{escalation_level}"
    if not force_new and cache_key in _reminder_cache:
        return _reminder_cache[cache_key]
    
    reminder = await generate_creative_reminder(
        reminder_type=reminder_type,
        escalation_level=escalation_level,
        context=context,
        time_str=time_str
    )
    
    if reminder:
        _reminder_cache[cache_key] = reminder
        if len(_reminder_cache) > 50:
            _reminder_cache.pop(next(iter(_reminder_cache)))
    
    return reminder


def clear_cache():
    """Очищает кэш напоминаний"""
    _reminder_cache.clear()
    logger.info("🧹 Кэш напоминаний очищен")
