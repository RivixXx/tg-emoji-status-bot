"""
Tests for Reminder Manager
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brains.reminders import (
    Reminder, ReminderType, EscalationLevel, ReminderManager
)


class TestReminder:
    """Тесты для модели Reminder"""

    def test_create_reminder(self):
        """Проверка создания напоминания"""
        now = datetime.now(timezone.utc)
        reminder = Reminder(
            id="test_123",
            type=ReminderType.HEALTH,
            message="Тестовое напоминание",
            scheduled_time=now
        )
        
        assert reminder.id == "test_123"
        assert reminder.type == ReminderType.HEALTH
        assert reminder.is_active == True
        assert reminder.is_confirmed == False

    def test_get_escalation_message(self):
        """Проверка сообщений эскалации"""
        now = datetime.now(timezone.utc)
        reminder = Reminder(
            id="test_123",
            type=ReminderType.HEALTH,
            message="Напоминание",
            scheduled_time=now
        )
        
        assert reminder.get_escalation_message(EscalationLevel.SOFT) == "Напоминание"
        assert reminder.get_escalation_message(EscalationLevel.FIRM) == "⚠️ Напоминание"
        assert reminder.get_escalation_message(EscalationLevel.STRICT) == "🚨 Напоминание"
        assert reminder.get_escalation_message(EscalationLevel.URGENT) == "❗️ Напоминание"

    def test_to_dict(self):
        """Проверка преобразования в словарь"""
        now = datetime.now(timezone.utc)
        reminder = Reminder(
            id="test_123",
            type=ReminderType.HEALTH,
            message="Тест",
            scheduled_time=now
        )
        
        data = reminder.to_dict()
        
        assert data["id"] == "test_123"
        assert data["type"] == "health"
        assert data["message"] == "Тест"
        assert data["is_active"] == True


class TestReminderManager:
    """Тесты для ReminderManager"""

    def test_create_health_reminder(self):
        """Проверка создания напоминания о здоровье"""
        manager = ReminderManager()
        reminder = manager.create_health_reminder("22:00")
        
        assert reminder.type == ReminderType.HEALTH
        assert "health_" in reminder.id
        assert reminder.escalate_after == [10, 30, 60]

    def test_create_lunch_reminder(self):
        """Проверка создания напоминания об обеде"""
        manager = ReminderManager()
        reminder = manager.create_lunch_reminder()
        
        assert reminder.type == ReminderType.LUNCH
        assert "lunch_" in reminder.id
        assert reminder.scheduled_time.hour == 13

    def test_create_morning_reminder(self):
        """Проверка создания утреннего напоминания"""
        manager = ReminderManager()
        reminder = manager.create_morning_greeting()
        
        assert reminder.type == ReminderType.MORNING
        assert "morning_" in reminder.id
        assert reminder.scheduled_time.hour == 7
        assert reminder.escalate_after == []  # Без эскалации

    def test_create_evening_reminder(self):
        """Проверка создания вечернего напоминания"""
        manager = ReminderManager()
        reminder = manager.create_evening_reminder("22:30")
        
        assert reminder.type == ReminderType.EVENING
        assert "evening_" in reminder.id
        assert reminder.scheduled_time.hour == 22
        assert reminder.scheduled_time.minute == 30

    def test_create_meeting_reminder(self):
        """Проверка создания напоминания о встрече"""
        manager = ReminderManager()
        meeting_time = datetime.now(timezone.utc) + timedelta(hours=2)
        reminder = manager.create_meeting_reminder(
            title="Встреча с командой",
            start_time=meeting_time,
            minutes_before=15
        )
        
        assert reminder.type == ReminderType.MEETING
        assert "meeting_" in reminder.id
        assert reminder.context["title"] == "Встреча с командой"

    def test_is_health_confirmation(self):
        """Проверка распознавания подтверждения здоровья"""
        manager = ReminderManager()
        
        # Должны распознаваться
        assert manager.is_health_confirmation("сделал!") == True
        assert manager.is_health_confirmation("готово") == True
        assert manager.is_health_confirmation("уколол!") == True
        assert manager.is_health_confirmation("да") == True
        assert manager.is_health_confirmation("ok") == True
        assert manager.is_health_confirmation("done") == True
        
        # Не должны распознаваться
        assert manager.is_health_confirmation("погода сегодня хорошая") == False
        assert manager.is_health_confirmation("как дела") == False

    def test_is_health_confirmation_length_limit(self):
        """Проверка ограничения длины сообщения"""
        manager = ReminderManager()
        
        # Длинные сообщения не должны распознаваться
        long_text = "сделал! " * 20  # Длиннее 50 символов
        assert manager.is_health_confirmation(long_text) == False

    def test_parse_snooze_command_minutes(self):
        """Проверка парсинга команды snooze (минуты)"""
        manager = ReminderManager()
        
        assert manager.parse_snooze_command("напомни через 15 минут") == 15
        assert manager.parse_snooze_command("отложи на 30 мин") == 30
        assert manager.parse_snooze_command("через 10 мин") == 10

    def test_parse_snooze_command_hours(self):
        """Проверка парсинга команды snooze (часы)"""
        manager = ReminderManager()
        
        assert manager.parse_snooze_command("через 2 часа") == 120
        assert manager.parse_snooze_command("напомни через 1 час") == 60

    def test_parse_snooze_command_invalid(self):
        """Проверка невалидных команд snooze"""
        manager = ReminderManager()
        
        assert manager.parse_snooze_command("привет") is None
        assert manager.parse_snooze_command("") is None

    def test_is_snooze_request(self):
        """Проверка распознавания запроса snooze"""
        manager = ReminderManager()
        
        assert manager.is_snooze_request("напомни через 15 минут") == True
        assert manager.is_snooze_request("отложи на 30 мин") == True
        assert manager.is_snooze_request("позже") == False  # Нет времени

    def test_is_skip_request(self):
        """Проверка распознавания запроса пропуска"""
        manager = ReminderManager()
        
        assert manager.is_skip_request("пропусти") == True
        assert manager.is_skip_request("не надо") == True
        assert manager.is_skip_request("отмени") == True
        assert manager.is_skip_request("skip") == True
        assert manager.is_skip_request("привет") == False


@pytest.mark.asyncio
class TestReminderManagerAsync:
    """Асинхронные тесты для ReminderManager"""

    async def test_confirm_reminder(self):
        """Проверка подтверждения напоминания"""
        manager = ReminderManager()
        reminder = manager.create_health_reminder()
        manager.reminders[reminder.id] = reminder
        
        with patch.object(manager, '_save_to_db', new_callable=AsyncMock):
            await manager.confirm_reminder(reminder.id)
            
            assert manager.reminders[reminder.id].is_confirmed == True
            assert manager.reminders[reminder.id].is_active == False

    async def test_snooze_reminder(self):
        """Проверка откладывания напоминания"""
        manager = ReminderManager()
        reminder = manager.create_health_reminder()
        manager.reminders[reminder.id] = reminder
        
        with patch.object(manager, '_save_to_db', new_callable=AsyncMock):
            await manager.snooze_reminder(reminder.id, 15)
            
            # Старое стало неактивным
            assert manager.reminders[reminder.id].is_active == False
            
            # Новое создано с snooze_until
            snooze_id = f"{reminder.id}_sn"
            assert snooze_id in manager.reminders

    async def test_add_reminder(self):
        """Проверка добавления напоминания"""
        manager = ReminderManager()
        reminder = manager.create_health_reminder()
        
        with patch.object(manager, '_save_to_db', new_callable=AsyncMock):
            await manager.add_reminder(reminder)
            
            assert reminder.id in manager.reminders


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
