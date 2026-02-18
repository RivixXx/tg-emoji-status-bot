"""
Система умных напоминаний Karina
- Здоровье (уколы, замеры)
- Встречи (календарь)
- Перерывы/обед
- Утренние/вечерние ритуалы
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import random

logger = logging.getLogger(__name__)


class ReminderType(Enum):
    HEALTH = "health"
    MEETING = "meeting"
    BREAK = "break"
    LUNCH = "lunch"
    MORNING = "morning"
    EVENING = "evening"
    CUSTOM = "custom"


class EscalationLevel(Enum):
    SOFT = "soft"       # Мягкое напоминание
    FIRM = "firm"       # Настойчивое
    STRICT = "strict"   # Строгое
    URGENT = "urgent"   # Критичное


@dataclass
class Reminder:
    """Модель напоминания"""
    id: str
    type: ReminderType
    message: str
    scheduled_time: datetime
    escalate_after: List[int] = field(default_factory=lambda: [10, 30, 60])  # минуты
    current_level: EscalationLevel = EscalationLevel.SOFT
    is_active: bool = True
    is_confirmed: bool = False
    snooze_until: Optional[datetime] = None
    context: Dict = field(default_factory=dict)
    
    def get_escalation_message(self, level: EscalationLevel) -> str:
        """Возвращает сообщение с учётом уровня эскалации"""
        prefixes = {
            EscalationLevel.SOFT: "",
            EscalationLevel.FIRM: "⚠️ ",
            EscalationLevel.STRICT: "🚨 ",
            EscalationLevel.URGENT: "❗️ "
        }
        return f"{prefixes.get(level, '')}{self.message}"


class ReminderManager:
    """Менеджер напоминаний"""
    
    def __init__(self):
        self.reminders: Dict[str, Reminder] = {}
        self.active_escalations: Dict[str, asyncio.Task] = {}
        self.my_id: int = 0
        self.client = None
        
        # Конфигурация по умолчанию
        self.config = {
            "health_time": "22:00",
            "lunch_window": (13, 14),  # 13:00–14:00
            "break_interval": 120,  # каждые 2 часа
            "meeting_reminder": 15,  # за 15 минут до встречи
            "morning_greeting": True,
            "evening_reminder": True,
        }
        
        # Фразы для эскалации
        self.health_phrases = {
            EscalationLevel.SOFT: [
                "💉 Михаил, время {time}! Пора сделать укол. Я забочусь о тебе! ❤️",
                "🩺 Напоминание: время укола! Твоё здоровье важно! 😊",
            ],
            EscalationLevel.FIRM: [
                "⚠️ Михаил, я жду подтверждения! Ты сделал укол? 🤨",
                "🤔 Что-то ты не отвечаешь... Всё в порядке с уколом?",
            ],
            EscalationLevel.STRICT: [
                "🚨 Михаил, я начинаю волноваться! Где подтверждение укола? 😤",
                "😠 Так не пойдёт! Я же просила подтвердить укол!",
            ],
            EscalationLevel.URGENT: [
                "❗️ МИХАИЛ! Это критично! Немедленно сделай укол и подтверди! 💉",
                "🆘 Я серьёзно! Здоровье не шутка! Срочно укол! 😡",
            ]
        }
        
        self.meeting_phrases = {
            EscalationLevel.SOFT: [
                "📅 Через {minutes} мин. встреча: \"{title}\"",
                "⏰ Напоминаю: \"{title}\" через {minutes} мин.",
            ],
            EscalationLevel.FIRM: [
                "⚠️ Встреча \"{title}\" начинается через {minutes} мин. Ты готов?",
            ],
            EscalationLevel.STRICT: [
                "🚨 \"{title}\" СЕЙЧАС! Ты опаздываешь! 🏃",
            ]
        }
        
        self.break_phrases = {
            EscalationLevel.SOFT: [
                "☕️ Ты работаешь уже {hours} ч. Пора сделать перерыв!",
                "🧘 Михаил, пора отдохнуть! Поработай глазами и потянись!",
            ],
            EscalationLevel.FIRM: [
                "⚠️ {hours} ч. без перерыва — это много! Встань, пройдись!",
            ]
        }
        
        self.lunch_phrases = {
            EscalationLevel.SOFT: [
                "🍽 Пора пообедать! Приятного аппетита! 😊",
                "🥗 Обеденное время! Отвлекись от работы!",
            ],
            EscalationLevel.FIRM: [
                "⚠️ Ты пропустил обед! Это вредно! 🤨",
            ]
        }
        
        self.morning_phrases = [
            "☀️ Доброе утро, Михаил! 🌅 Как спал? Готов к новому дню?",
            "🌞 Просыпайся! Сегодня великий день! 💪",
            "☕️ Утро доброе! Кофе уже ждёт? 😊",
        ]
        
        self.evening_phrases = [
            "🌙 Михаил, пора отдыхать! Завтра новый день! 😴",
            "🌃 День заканчивается. Время расслабиться! 🛋",
            "🌌 Пора на боковую! Здоровый сон важен! 💤",
        ]
    
    def set_client(self, client, my_id: int):
        """Устанавливает клиент и ID пользователя"""
        self.client = client
        self.my_id = my_id
    
    async def send_reminder(self, reminder: Reminder):
        """Отправляет напоминание пользователю"""
        if not self.client or not self.my_id:
            logger.error("❌ Клиент или my_id не установлен!")
            return
        
        message = reminder.get_escalation_message(reminder.current_level)
        
        # Подставляем контекст в сообщение
        if reminder.context:
            for key, value in reminder.context.items():
                message = message.replace(f"{{{key}}}", str(value))
        
        try:
            await self.client.send_message(self.my_id, message)
            logger.info(f"🔔 Напоминание отправлено: {reminder.id} ({reminder.current_level.value})")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания: {e}")
    
    async def start_escalation(self, reminder: Reminder):
        """Запускает эскалацию напоминания"""
        if reminder.id in self.active_escalations:
            self.active_escalations[reminder.id].cancel()
        
        async def escalation_loop():
            levels = [
                (EscalationLevel.FIRM, reminder.escalate_after[0] if len(reminder.escalate_after) > 0 else 10),
                (EscalationLevel.STRICT, reminder.escalate_after[1] if len(reminder.escalate_after) > 1 else 30),
                (EscalationLevel.URGENT, reminder.escalate_after[2] if len(reminder.escalate_after) > 2 else 60),
            ]
            
            for level, delay_minutes in levels:
                if not reminder.is_active or reminder.is_confirmed:
                    return
                
                await asyncio.sleep(delay_minutes * 60)
                
                if not reminder.is_active or reminder.is_confirmed:
                    return
                
                reminder.current_level = level
                await self.send_reminder(reminder)
        
        self.active_escalations[reminder.id] = asyncio.create_task(escalation_loop())
    
    def create_health_reminder(self, time_str: str = "22:00") -> Reminder:
        """Создаёт напоминание о здоровье"""
        now = datetime.now(timezone(timedelta(hours=3)))
        hour, minute = map(int, time_str.split(':'))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if scheduled < now:
            scheduled += timedelta(days=1)
        
        return Reminder(
            id=f"health_{scheduled.strftime('%Y%m%d')}",
            type=ReminderType.HEALTH,
            message=random.choice(self.health_phrases[EscalationLevel.SOFT]),
            scheduled_time=scheduled,
            escalate_after=[10, 30, 60],
            context={"time": time_str}
        )
    
    def create_meeting_reminder(self, title: str, start_time: datetime, minutes_before: int = 15) -> Reminder:
        """Создаёт напоминание о встрече"""
        scheduled = start_time - timedelta(minutes=minutes_before)
        
        return Reminder(
            id=f"meeting_{int(start_time.timestamp())}",
            type=ReminderType.MEETING,
            message=random.choice(self.meeting_phrases[EscalationLevel.SOFT]),
            scheduled_time=scheduled,
            escalate_after=[5, 15],
            context={"title": title, "minutes": minutes_before}
        )
    
    def create_break_reminder(self, work_hours: float) -> Reminder:
        """Создаёт напоминание о перерыве"""
        return Reminder(
            id=f"break_{int(datetime.now().timestamp())}",
            type=ReminderType.BREAK,
            message=random.choice(self.break_phrases[EscalationLevel.SOFT]),
            scheduled_time=datetime.now(timezone(timedelta(hours=3))),
            escalate_after=[30],
            context={"hours": work_hours}
        )
    
    def create_lunch_reminder(self) -> Reminder:
        """Создаёт напоминание об обеде"""
        now = datetime.now(timezone(timedelta(hours=3)))
        scheduled = now.replace(hour=13, minute=0, second=0, microsecond=0)
        
        if scheduled < now:
            scheduled += timedelta(days=1)
        
        return Reminder(
            id=f"lunch_{scheduled.strftime('%Y%m%d')}",
            type=ReminderType.LUNCH,
            message=random.choice(self.lunch_phrases[EscalationLevel.SOFT]),
            scheduled_time=scheduled,
            escalate_after=[60],
        )
    
    def create_morning_greeting(self) -> Reminder:
        """Создаёт утреннее приветствие"""
        now = datetime.now(timezone(timedelta(hours=3)))
        scheduled = now.replace(hour=7, minute=0, second=0, microsecond=0)
        
        if scheduled < now:
            scheduled += timedelta(days=1)
        
        return Reminder(
            id=f"morning_{scheduled.strftime('%Y%m%d')}",
            type=ReminderType.MORNING,
            message=random.choice(self.morning_phrases),
            scheduled_time=scheduled,
            escalate_after=[],
        )
    
    def create_evening_reminder(self, time_str: str = "22:30") -> Reminder:
        """Создаёт вечернее напоминание"""
        now = datetime.now(timezone(timedelta(hours=3)))
        hour, minute = map(int, time_str.split(':'))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if scheduled < now:
            scheduled += timedelta(days=1)
        
        return Reminder(
            id=f"evening_{scheduled.strftime('%Y%m%d')}",
            type=ReminderType.EVENING,
            message=random.choice(self.evening_phrases),
            scheduled_time=scheduled,
            escalate_after=[],
        )
    
    def confirm_reminder(self, reminder_id: str):
        """Подтверждает напоминание"""
        if reminder_id in self.reminders:
            self.reminders[reminder_id].is_confirmed = True
            self.reminders[reminder_id].is_active = False
            
            if reminder_id in self.active_escalations:
                self.active_escalations[reminder_id].cancel()
                del self.active_escalations[reminder_id]
            
            logger.info(f"✅ Напоминание подтверждено: {reminder_id}")
    
    def snooze_reminder(self, reminder_id: str, minutes: int):
        """Откладывает напоминание"""
        if reminder_id in self.reminders:
            reminder = self.reminders[reminder_id]
            reminder.snooze_until = datetime.now(timezone(timedelta(hours=3))) + timedelta(minutes=minutes)
            reminder.is_active = False
            
            if reminder_id in self.active_escalations:
                self.active_escalations[reminder_id].cancel()
                del self.active_escalations[reminder_id]
            
            # Создаём новое напоминание
            new_reminder = Reminder(
                id=f"{reminder_id}_snoozed",
                type=reminder.type,
                message=reminder.message,
                scheduled_time=reminder.snooze_until,
                escalate_after=reminder.escalate_after,
                context=reminder.context
            )
            self.reminders[new_reminder.id] = new_reminder
            
            logger.info(f"⏰ Напоминание отложено на {minutes} мин: {reminder_id}")
    
    def parse_snooze_command(self, text: str) -> Optional[int]:
        """Парсит команду отсрочки из текста"""
        text_lower = text.lower()
        
        # "напомни через 30 минут", "отложи на час", "через 20 мин"
        import re
        
        # Минуты
        match = re.search(r'через\s+(\d+)\s*(мин|минут|минуты|м)', text_lower)
        if match:
            return int(match.group(1))
        
        # Часы
        match = re.search(r'через\s+(\d+)\s*(час|часа|часов|ч|ч.)', text_lower)
        if match:
            return int(match.group(1)) * 60
        
        # "на час", "на 30 минут"
        match = re.search(r'на\s+(\d+)\s*(мин|минут|час|часа|часов|ч|ч.)', text_lower)
        if match:
            value = int(match.group(1))
            if 'час' in match.group(2):
                return value * 60
            return value
        
        return None
    
    def is_health_confirmation(self, text: str) -> bool:
        """Проверяет, является ли текст подтверждением здоровья"""
        text_lower = text.lower()
        confirm_words = ['сделал', 'готово', 'окей', 'уколол', 'подтверждаю', 'да', 'ок', 'yes', 'done']
        return any(word in text_lower for word in confirm_words)
    
    def is_snooze_request(self, text: str) -> bool:
        """Проверяет, просит ли пользователь отложить напоминание"""
        text_lower = text.lower()
        snooze_words = ['напомни', 'отложи', 'позже', 'потом', 'через', 'snooze']
        return any(word in text_lower for word in snooze_words) and self.parse_snooze_command(text) is not None
    
    def is_skip_request(self, text: str) -> bool:
        """Проверяет, хочет ли пользователь пропустить напоминание"""
        text_lower = text.lower()
        skip_words = ['пропусти', 'не надо', 'не нужно', 'отмени', 'хватит', 'позже сегодня', 'skip', 'no']
        return any(word in text_lower for word in skip_words)


# Глобальный экземпляр
reminder_manager = ReminderManager()


async def start_reminder_loop():
    """Основной цикл проверки напоминаний"""
    logger.info("🔔 Запуск цикла напоминаний...")
    
    while True:
        try:
            now = datetime.now(timezone(timedelta(hours=3)))
            
            for reminder_id, reminder in list(reminder_manager.reminders.items()):
                # Пропускаем неактивные или подтверждённые
                if not reminder.is_active or reminder.is_confirmed:
                    continue
                
                # Проверяем snooze
                if reminder.snooze_until and now < reminder.snooze_until:
                    continue
                
                # Время пришло!
                if now >= reminder.scheduled_time:
                    await reminder_manager.send_reminder(reminder)
                    
                    # Запускаем эскалацию если есть
                    if reminder.escalate_after:
                        await reminder_manager.start_escalation(reminder)
            
            # Проверка каждую минуту
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле напоминаний: {e}")
            await asyncio.sleep(60)
