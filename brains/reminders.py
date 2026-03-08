"""
Система умных напоминаний Karina
- Здоровье (уколы, замеры)
- Встречи (календарь)
- Перерывы/обед
- Утренние/вечерние ритуалы
- Креативная генерация через AI
- Персистентность через Supabase
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import random

from telethon import types
from brains.reminder_generator import get_or_generate_reminder
from brains.clients import supabase_client
from brains.weather import get_weather
from brains.news import get_latest_news
from brains.calendar import get_upcoming_events

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

    def to_dict(self):
        """Преобразует объект в словарь для Supabase"""
        return {
            "id": self.id,
            "type": self.type.value,
            "message": self.message,
            "scheduled_time": self.scheduled_time.isoformat(),
            "escalate_after": self.escalate_after,
            "current_level": self.current_level.value,
            "is_active": self.is_active,
            "is_confirmed": self.is_confirmed,
            "snooze_until": self.snooze_until.isoformat() if self.snooze_until else None,
            "context": self.context,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }


class ReminderManager:
    """Менеджер напоминаний с поддержкой БД"""
    
    def __init__(self):
        self.reminders: Dict[str, Reminder] = {}
        self.active_escalations: Dict[str, asyncio.Task] = {}
        self.my_id: int = 0
        self.client = None
        
        # Фразы-фолбеки (если AI недоступен)
        self.health_phrases = ["Пора сделать укол! ❤️", "Напоминаю про укол! 😊"]
        self.morning_phrases = ["Доброе утро! ☀️", "Просыпайся! ☕️"]
        self.evening_phrases = ["Пора отдыхать! 😴", "Спокойной ночи! 🌙"]
        self.lunch_phrases = ["Приятного аппетита! 🍽"]
        self.break_phrases = ["Сделай перерыв! 🧘"]
        self.meeting_phrases = ["Встреча через {minutes} мин! ⏰"]

    def set_client(self, client, my_id: int):
        """Устанавливает клиент и ID пользователя"""
        self.client = client
        self.my_id = my_id

    async def _save_to_db(self, reminder: Reminder):
        """
        Сохраняет состояние напоминания в Supabase (Upsert).
        
        Args:
            reminder: Объект напоминания для сохранения
        """
        if not supabase_client:
            logger.debug("⚠️ Supabase клиент не инициализирован, пропускаем сохранение напоминания")
            return

        max_retries = 2
        for attempt in range(max_retries):
            try:
                data = reminder.to_dict()

                # Upsert: вставляем или обновляем существующую запись
                response = supabase_client.table("reminders").upsert(data, on_conflict="id").execute()

                if response.data:
                    logger.debug(f"💾 Reminder saved: {reminder.id}")
                else:
                    logger.error(f"❌ Supabase Reminder Save Error: {response}")
                    # Пробуем снова при пустом ответе
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)

            except asyncio.TimeoutError:
                logger.error(f"⌛️ Reminder save timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"❌ Failed to save reminder to DB (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

    async def load_active_reminders(self):
        """
        Загружает активные напоминания из базы при старте.
        
        Returns:
            Количество загруженных напоминаний
        """
        if not supabase_client:
            logger.warning("⚠️ Supabase клиент не инициализирован, пропускаем загрузку напоминаний")
            return 0

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = supabase_client.table("reminders")\
                    .select("*")\
                    .eq("is_active", True)\
                    .execute()

                if response.data:
                    for r_data in response.data:
                        try:
                            reminder = Reminder(
                                id=r_data["id"],
                                type=ReminderType(r_data["type"]),
                                message=r_data["message"],
                                scheduled_time=datetime.fromisoformat(r_data["scheduled_time"].replace('+00:00', '+00:00')),
                                escalate_after=r_data.get("escalate_after", [10, 30, 60]),
                                current_level=EscalationLevel(r_data.get("current_level", "soft")),
                                is_active=r_data.get("is_active", True),
                                is_confirmed=r_data.get("is_confirmed", False),
                                snooze_until=datetime.fromisoformat(r_data["snooze_until"].replace('+00:00', '+00:00')) if r_data.get("snooze_until") else None,
                                context=r_data.get("context", {})
                            )
                            self.reminders[reminder.id] = reminder
                        except (KeyError, ValueError) as e:
                            logger.error(f"❌ Ошибка парсинга напоминания из БД: {e}")
                            continue

                    logger.info(f"💾 Загружено {len(self.reminders)} активных напоминаний из БД")
                    return len(self.reminders)
                else:
                    logger.info("💾 Активных напоминаний в БД не найдено")
                    return 0

            except asyncio.TimeoutError:
                logger.error(f"⌛️ Reminder load timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"❌ Failed to load reminders from DB (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

        return 0

    async def send_reminder(self, reminder: Reminder, force_new: bool = False):
        """
        Отправляет напоминание пользователю.
        
        Args:
            reminder: Объект напоминания для отправки
            force_new: Принудительно сгенерировать новое сообщение
        """
        if not self.client or not self.my_id:
            logger.warning("⚠️ Клиент или my_id не установлены, пропускаем отправку напоминания")
            return

        try:
            ai_message = await get_or_generate_reminder(
                reminder_id=reminder.id,
                reminder_type=reminder.type.value,
                escalation_level=reminder.current_level.value,
                context=reminder.context,
                time_str=reminder.context.get("time"),
                force_new=force_new
            )

            message = ai_message or reminder.get_escalation_message(reminder.current_level)

            # 🌅 Утренний брифинг (автоматически добавляем новости и погоду)
            if reminder.type == ReminderType.MORNING:
                logger.info("☕️ Формирование утреннего брифинга...")
                try:
                    weather = await get_weather()
                    news = await get_latest_news(limit=3)
                    events = await get_upcoming_events(max_results=5)

                    briefing = f"\n\n🌤 **Погода:** {weather if weather else 'не удалось узнать'}"
                    briefing += f"\n\n🗓 **Планы на сегодня:**\n{events}"
                    briefing += f"\n\n{news}"
                    message += briefing
                except Exception as e:
                    logger.error(f"❌ Ошибка формирования брифинга: {type(e).__name__} - {e}")
                    # Продолжаем без брифинга

            buttons = await self._create_reminder_buttons(reminder)

            try:
                await self.client.send_message(self.my_id, message, buttons=buttons)
                logger.info(f"🔔 Отправлено: {reminder.id} ({reminder.current_level.value})")
                await self._save_to_db(reminder)  # Синхронизируем состояние
            except Exception as send_error:
                logger.error(f"❌ Ошибка отправки сообщения: {type(send_error).__name__} - {send_error}")
                # Пробуем сохранить состояние даже если отправка не удалась
                await self._save_to_db(reminder)

        except asyncio.TimeoutError:
            logger.error(f"⌛️ Таймаут при отправке напоминания {reminder.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в send_reminder: {type(e).__name__} - {e}")

    async def _create_reminder_buttons(self, reminder: Reminder):
        """Создаёт интерактивные кнопки для напоминания"""
        if reminder.type == ReminderType.HEALTH:
            return [
                [types.KeyboardButtonCallback("✅ Сделал!", data=b"confirm_health")],
                [types.KeyboardButtonCallback("⏰ 15 мин", data=b"snooze_15"), types.KeyboardButtonCallback("⏰ 30 мин", data=b"snooze_30")],
                [types.KeyboardButtonCallback("❌ Пропустить", data=b"skip_health")]
            ]
        elif reminder.type == ReminderType.MEETING:
            return [[types.KeyboardButtonCallback("👍 Готов!", data=b"confirm_meeting")], [types.KeyboardButtonCallback("⏰ 5 мин", data=b"snooze_5")]]
        elif reminder.type == ReminderType.LUNCH:
            return [[types.KeyboardButtonCallback("🍽 Иду обедать!", data=b"confirm_lunch")], [types.KeyboardButtonCallback("⏰ Позже", data=b"snooze_30")]]
        elif reminder.type == ReminderType.BREAK:
            return [[types.KeyboardButtonCallback("🧘 Отдыхаю!", data=b"confirm_break")], [types.KeyboardButtonCallback("⏰ 10 мин", data=b"snooze_10")]]
        elif reminder.type in [ReminderType.MORNING, ReminderType.EVENING]:
            return [[types.KeyboardButtonCallback("😊 Спасибо!", data=b"acknowledge")]]
        return [[types.KeyboardButtonCallback("👌 Понял", data=b"acknowledge")]]

    async def start_escalation(self, reminder: Reminder):
        """
        Запускает эскалацию напоминания.
        
        Args:
            reminder: Объект напоминания для эскалации
        """
        if reminder.id in self.active_escalations:
            logger.debug(f"⚠️ Отмена предыдущей эскалации для {reminder.id}")
            self.active_escalations[reminder.id].cancel()

        async def escalation_loop():
            """Фоновая задача эскалации с обработкой ошибок"""
            levels = [
                (EscalationLevel.FIRM, reminder.escalate_after[0] if len(reminder.escalate_after) > 0 else 10),
                (EscalationLevel.STRICT, reminder.escalate_after[1] if len(reminder.escalate_after) > 1 else 30),
                (EscalationLevel.URGENT, reminder.escalate_after[2] if len(reminder.escalate_after) > 2 else 60),
            ]
            for level, delay_minutes in levels:
                try:
                    if reminder.is_confirmed:
                        logger.debug(f"✅ Напоминание {reminder.id} подтверждено, эскалация остановлена")
                        return
                    await asyncio.sleep(delay_minutes * 60)
                    if reminder.is_confirmed:
                        logger.debug(f"✅ Напоминание {reminder.id} подтверждено во время ожидания")
                        return
                    reminder.current_level = level
                    await self.send_reminder(reminder, force_new=True)
                except asyncio.CancelledError:
                    logger.debug(f"⚠️ Эскалация {reminder.id} отменена")
                    return
                except Exception as e:
                    logger.error(f"❌ Ошибка в escalation_loop для {reminder.id}: {type(e).__name__} - {e}")
                    # Продолжаем эскалацию, несмотря на ошибку

        self.active_escalations[reminder.id] = asyncio.create_task(escalation_loop())

    async def add_reminder(self, reminder: Reminder):
        """Добавляет и сохраняет новое напоминание"""
        self.reminders[reminder.id] = reminder
        await self._save_to_db(reminder)

    def create_health_reminder(self, time_str: str = "22:00") -> Reminder:
        now = datetime.now(timezone(timedelta(hours=3)))
        hour, minute = map(int, time_str.split(':'))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled < now: scheduled += timedelta(days=1)
        return Reminder(
            id=f"health_{scheduled.strftime('%Y%m%d')}",
            type=ReminderType.HEALTH,
            message=random.choice(self.health_phrases),
            scheduled_time=scheduled,
            context={"time": time_str}
        )

    def create_meeting_reminder(self, title: str, start_time: datetime, minutes_before: int = 15) -> Reminder:
        scheduled = start_time - timedelta(minutes=minutes_before)
        return Reminder(
            id=f"meeting_{int(start_time.timestamp())}",
            type=ReminderType.MEETING,
            message=f"Встреча: {title}",
            scheduled_time=scheduled,
            context={"title": title, "minutes": minutes_before}
        )

    def create_lunch_reminder(self) -> Reminder:
        now = datetime.now(timezone(timedelta(hours=3)))
        scheduled = now.replace(hour=13, minute=0, second=0, microsecond=0)
        if scheduled < now: scheduled += timedelta(days=1)
        return Reminder(id=f"lunch_{scheduled.strftime('%Y%m%d')}", type=ReminderType.LUNCH, message="Время обеда!", scheduled_time=scheduled)

    def create_morning_greeting(self) -> Reminder:
        now = datetime.now(timezone(timedelta(hours=3)))
        scheduled = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if scheduled < now: scheduled += timedelta(days=1)
        return Reminder(id=f"morning_{scheduled.strftime('%Y%m%d')}", type=ReminderType.MORNING, message="Доброе утро!", scheduled_time=scheduled, escalate_after=[])

    def create_evening_reminder(self, time_str: str = "22:30") -> Reminder:
        now = datetime.now(timezone(timedelta(hours=3)))
        hour, minute = map(int, time_str.split(':'))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled < now: scheduled += timedelta(days=1)
        return Reminder(id=f"evening_{scheduled.strftime('%Y%m%d')}", type=ReminderType.EVENING, message="Пора отдыхать!", scheduled_time=scheduled, escalate_after=[])

    async def confirm_reminder(self, reminder_id: str):
        """
        Подтверждает напоминание.
        
        Args:
            reminder_id: ID напоминания для подтверждения
        """
        if reminder_id in self.reminders:
            r = self.reminders[reminder_id]
            r.is_confirmed = True
            r.is_active = False
            if reminder_id in self.active_escalations:
                self.active_escalations[reminder_id].cancel()
                del self.active_escalations[reminder_id]
            try:
                await self._save_to_db(r)
                logger.info(f"✅ Подтверждено: {reminder_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения подтверждения: {type(e).__name__} - {e}")
        else:
            logger.warning(f"⚠️ Напоминание не найдено для подтверждения: {reminder_id}")

    async def snooze_reminder(self, reminder_id: str, minutes: int):
        """
        Откладывает напоминание на указанное время.
        
        Args:
            reminder_id: ID напоминания для откладывания
            minutes: Количество минут для откладывания
        """
        if reminder_id in self.reminders:
            r = self.reminders[reminder_id]
            r.snooze_until = datetime.now(timezone(timedelta(hours=3))) + timedelta(minutes=minutes)
            r.is_active = False
            if reminder_id in self.active_escalations:
                self.active_escalations[reminder_id].cancel()
                del self.active_escalations[reminder_id]

            try:
                new_r = Reminder(
                    id=f"{reminder_id}_sn",
                    type=r.type,
                    message=r.message,
                    scheduled_time=r.snooze_until,
                    escalate_after=r.escalate_after,
                    context=r.context
                )
                await self.add_reminder(new_r)
                await self._save_to_db(r)
                logger.info(f"⏰ Отложено на {minutes} мин: {reminder_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка откладывания напоминания: {type(e).__name__} - {e}")
        else:
            logger.warning(f"⚠️ Напоминание не найдено для откладывания: {reminder_id}")

    def parse_snooze_command(self, text: str) -> Optional[int]:
        text_lower = text.lower()
        import re
        match = re.search(r'через\s+(\d+)\s*(мин|минут|минуты|м)', text_lower)
        if match: return int(match.group(1))
        match = re.search(r'через\s+(\d+)\s*(час|часа|часов|ч|ч.)', text_lower)
        if match: return int(match.group(1)) * 60
        match = re.search(r'на\s+(\d+)\s*(мин|минут|час|часа|часов|ч|ч.)', text_lower)
        if match:
            value = int(match.group(1))
            return value * 60 if 'час' in match.group(2) else value
        return None

    def is_health_confirmation(self, text: str) -> bool:
        """
        Проверяет подтверждение здоровья
        Работает ТОЛЬКО для коротких сообщений (до 50 символов)
        """
        text_lower = text.lower().strip()
        
        # Если сообщение слишком длинное — это не подтверждение
        if len(text_lower) > 50:
            return False
        
        import re
        # Ищем слова только целиком, чтобы не ловить 'да' в 'погода'
        confirm_patterns = [
            r'^\bсделал\b[.!]?$',      # "сделал!" или "сделал."
            r'^\bготово\b[.!]?$',       # "готово!"
            r'^\bуколол\b[.!]?$',       # "уколол!"
            r'^\bподтверждаю\b[.!]?$',  # "подтверждаю!"
            r'^\bok\b[.!]?$',           # "ok!"
            r'^\bда\b[.!]?$',           # "да!"
            r'^\byes\b[.!]?$',          # "yes!"
            r'^\bdone\b[.!]?$',         # "done!"
        ]
        return any(re.search(pattern, text_lower) for pattern in confirm_patterns)

    def is_snooze_request(self, text: str) -> bool:
        return any(word in text.lower() for word in ['напомни', 'отложи', 'позже', 'потом', 'через', 'snooze']) and self.parse_snooze_command(text) is not None

    def is_skip_request(self, text: str) -> bool:
        return any(word in text.lower() for word in ['пропусти', 'не надо', 'не нужно', 'отмени', 'хватит', 'skip', 'no'])


# Глобальный экземпляр
reminder_manager = ReminderManager()


async def start_reminder_loop():
    """
    Основной цикл проверки напоминаний.
    Запускается как фоновая задача и работает постоянно.
    """
    logger.info("🔔 Запуск цикла напоминаний...")

    # Загружаем активные напоминания из БД при старте
    try:
        await reminder_manager.load_active_reminders()
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки напоминаний при старте: {type(e).__name__} - {e}")

    while True:
        try:
            now = datetime.now(timezone(timedelta(hours=3)))
            
            for rid, r in list(reminder_manager.reminders.items()):
                try:
                    if not r.is_active or r.is_confirmed:
                        continue
                    if r.snooze_until and now < r.snooze_until:
                        continue

                    if now >= r.scheduled_time:
                        await reminder_manager.send_reminder(r)
                        r.is_active = False  # Деактивируем для основного цикла
                        await reminder_manager._save_to_db(r)  # Сохраняем неактивное состояние в БД!

                        if r.escalate_after:
                            await reminder_manager.start_escalation(r)
                except Exception as reminder_error:
                    logger.error(f"❌ Ошибка обработки напоминания {rid}: {type(reminder_error).__name__} - {reminder_error}")
                    # Продолжаем обработку остальных напоминаний
            
            await asyncio.sleep(60)
            
        except asyncio.CancelledError:
            logger.info("👋 Цикл напоминаний остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в главном цикле напоминаний: {type(e).__name__} - {e}")
            await asyncio.sleep(60)  # Пауза перед следующей попыткой
