import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# Цветовые темы для разных эмоций
EMOTION_THEMES = {
    "neutral": {
        "primary": "#38bdf8",      # sky blue
        "secondary": "#94a3b8",    # slate gray
        "bg_gradient": "linear-gradient(to bottom, rgba(2, 6, 23, 0.4), rgba(2, 6, 23, 0.9))"
    },
    "positive": {
        "primary": "#4ade80",      # green
        "secondary": "#2dd4bf",    # teal
        "bg_gradient": "linear-gradient(to bottom, rgba(2, 6, 23, 0.4), rgba(20, 83, 45, 0.9))"
    },
    "excited": {
        "primary": "#facc15",      # yellow
        "secondary": "#fb923c",    # orange
        "bg_gradient": "linear-gradient(to bottom, rgba(2, 6, 23, 0.4), rgba(113, 63, 18, 0.9))"
    },
    "sad": {
        "primary": "#60a5fa",      # blue
        "secondary": "#818cf8",    # indigo
        "bg_gradient": "linear-gradient(to bottom, rgba(2, 6, 23, 0.4), rgba(30, 58, 138, 0.9))"
    },
    "angry": {
        "primary": "#f87171",      # red
        "secondary": "#dc2626",    # dark red
        "bg_gradient": "linear-gradient(to bottom, rgba(2, 6, 23, 0.4), rgba(127, 29, 29, 0.9))"
    },
    "romantic": {
        "primary": "#fb7185",      # rose
        "secondary": "#e879f9",    # fuchsia
        "bg_gradient": "linear-gradient(to bottom, rgba(2, 6, 23, 0.4), rgba(131, 24, 67, 0.9))"
    },
    "work": {
        "primary": "#a78bfa",      # purple
        "secondary": "#6366f1",    # indigo
        "bg_gradient": "linear-gradient(to bottom, rgba(2, 6, 23, 0.4), rgba(49, 46, 129, 0.9))"
    }
}

# Ключевые слова для определения эмоций (русский + английский)
EMOTION_KEYWORDS = {
    "positive": [
        "отлично", "хорошо", "прекрасно", "замечательно", "супер", "класс",
        "рад", "радост", "счастлив", "доволен", "круто", "awesome", "great",
        "wonderful", "happy", "good", "nice", "perfect", "love", "лучше",
        "ура", "победа", "успех", "молодец", "восхищ", "восторг"
    ],
    "excited": [
        "вау", "ого", "классно", "здорово", "обалдеть", "невероятно",
        "потрясающе", "восхитительно", "fire", "amazing", "wow", "excited",
        "нетерпением", "жду", "предвкуш", "энергия", "драйв", "огонь"
    ],
    "sad": [
        "плохо", "грустно", "тоска", "печаль", "расстроен", "обижен",
        "больно", "тяжело", "трудно", "устал", "депресс", "sad", "bad",
        "upset", "tired", "disappointed", "miss", "скучаю", "жаль",
        "к сожалению", "увы", "неудач", "провал", "ошибка"
    ],
    "angry": [
        "злой", "бешен", "ярость", "раздраж", "достал", "надоел",
        "ненавижу", "ужас", "кошмар", "отвратительно", "angry", "mad",
        "hate", "annoyed", "frustrated", "позор", "безобразие", "какого",
        "чёрт", "блин", "сколько можно", "опять"
    ],
    "romantic": [
        "люблю", "любовь", "нежный", "ласковый", "милый", "дорогой",
        "сердце", "поцелуй", "обним", "скучаю", "хочу тебя", "love",
        "kiss", "hug", "miss you", "дорогая", "дорогой", "солнце",
        "зайка", "котёнок", "милашка"
    ],
    "work": [
        "работа", "задача", "проект", "дедлайн", "встреча", "совещание",
        "отчёт", "план", "срок", "бизнес", "клиент", "заказчик", "коллег",
        "work", "task", "project", "deadline", "meeting", "report",
        "дел", "надо", "нужно", "сделать", "работ", "труд"
    ]
}

# Позитивные усилители
POSITIVE_INTENSIFIERS = ["очень", "крайне", "чрезвычайно", "невероятно", "безумно", "super", "very", "extremely"]

# Негативные усилители
NEGATIVE_INTENSIFIERS = ["совсем", "абсолютно", "полностью", "совершенно", "totally", "absolutely", "completely"]

# Отрицания
NEGATIONS = ["не", "ни", "нет", "нельзя", "нельзя", "not", "no", "never", "without"]


class EmotionAnalyzer:
    """Анализатор тональности текста для эмоционального движка Карины"""
    
    def __init__(self):
        self.current_emotion = "neutral"
        self.emotion_history: List[Dict] = []
        self.intensity = 1.0
    
    def analyze(self, text: str) -> Dict:
        """
        Анализирует текст и возвращает эмоцию и цветовую тему
        
        Returns:
            dict: {"emotion": str, "theme": dict, "intensity": float}
        """
        if not text:
            return self._get_result("neutral")
        
        text_lower = text.lower()
        words = set(re.findall(r'\w+', text_lower))
        
        # Подсчёт очков для каждой эмоции
        emotion_scores = {
            "positive": 0,
            "excited": 0,
            "sad": 0,
            "angry": 0,
            "romantic": 0,
            "work": 0
        }
        
        # Проверка ключевых слов
        for emotion, keywords in EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    emotion_scores[emotion] += 1
        
        # Проверка усилителей
        intensifier_count = 0
        for word in POSITIVE_INTENSIFIERS + NEGATIVE_INTENSIFIERS:
            if word in text_lower:
                intensifier_count += 1
        
        self.intensity = min(1.0 + (intensifier_count * 0.3), 2.0)
        
        # Проверка отрицаний (упрощённая)
        has_negation = any(neg in text_lower for neg in NEGATIONS)
        if has_negation:
            # Если есть отрицание с позитивным словом, уменьшаем позитив
            if emotion_scores["positive"] > 0:
                emotion_scores["positive"] *= 0.5
            if emotion_scores["excited"] > 0:
                emotion_scores["excited"] *= 0.5
        
        # Определение доминирующей эмоции
        max_score = max(emotion_scores.values())
        
        if max_score == 0:
            # Если нет явных эмоций, проверяем на рабочую тематику
            if emotion_scores["work"] > 0:
                self.current_emotion = "work"
            else:
                self.current_emotion = "neutral"
        else:
            # Находим эмоцию с максимальным score
            self.current_emotion = max(emotion_scores, key=emotion_scores.get)
        
        # Сохраняем в историю
        self.emotion_history.append({
            "emotion": self.current_emotion,
            "text_preview": text[:50] + "..." if len(text) > 50 else text,
            "score": emotion_scores.get(self.current_emotion, 0)
        })
        
        # Ограничиваем историю
        if len(self.emotion_history) > 20:
            self.emotion_history = self.emotion_history[-20:]
        
        return self._get_result(self.current_emotion)
    
    def _get_result(self, emotion: str) -> Dict:
        """Возвращает результат с темой"""
        theme = EMOTION_THEMES.get(emotion, EMOTION_THEMES["neutral"])
        return {
            "emotion": emotion,
            "theme": theme,
            "intensity": self.intensity
        }
    
    def get_current_emotion(self) -> str:
        """Возвращает текущую эмоцию"""
        return self.current_emotion
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """Возвращает историю эмоций"""
        return self.emotion_history[-limit:]
    
    def reset(self):
        """Сбрасывает состояние"""
        self.current_emotion = "neutral"
        self.intensity = 1.0


# Глобальный экземпляр для использования в приложении
emotion_analyzer = EmotionAnalyzer()


async def get_emotion_state(text: str = None) -> Dict:
    """
    Анализирует текст и возвращает текущее эмоциональное состояние
    
    Args:
        text: Текст для анализа (опционально)
    
    Returns:
        dict: {"emotion": str, "theme": dict, "intensity": float}
    """
    if text:
        return emotion_analyzer.analyze(text)
    return emotion_analyzer._get_result(emotion_analyzer.current_emotion)


async def set_emotion(emotion: str):
    """Принудительно устанавливает эмоцию"""
    if emotion in EMOTION_THEMES:
        emotion_analyzer.current_emotion = emotion
        logger.info(f"🎭 Эмоция установлена: {emotion}")
    else:
        logger.warning(f"⚠️ Неизвестная эмоция: {emotion}")
