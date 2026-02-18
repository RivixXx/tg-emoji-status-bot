import logging
import random
import os
from telethon import events, types
from brains.weather import get_weather
from brains.ai import ask_karina
from brains.news import get_latest_news
from brains.memory import save_memory
from brains.calendar import get_upcoming_events, add_calendar, get_conflict_report
from brains.health import get_health_report_text, save_health_record
from brains.stt import transcribe_voice
from brains.reminders import reminder_manager, ReminderType
from auras import confirm_health

from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def register_discovery_skills(client):
    @client.on(events.NewMessage(chats='me', pattern='(?i)id'))
    async def discovery_handler(event):
        if event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, types.MessageEntityCustomEmoji):
                    await event.reply(f"Код эмодзи: <code>{ent.document_id}</code>")
                    return

def register_karina_base_skills(client):
    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        logger.info(f"📩 /start от пользователя {event.chat_id}")
        await event.respond(
            "Привет! Я Карина. 😊\n\nЯ теперь не просто бот, у меня есть удобная панель управления! Нажми кнопку ниже или используй /app.",
            buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
        )

    @client.on(events.NewMessage(pattern='/app'))
    async def app_command_handler(event):
        """Скилл: Открыть Mini App"""
        logger.info(f"📩 /app от пользователя {event.chat_id}")
        await event.respond(
            "Твоя персональная панель управления Кариной:",
            buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
        )

    @client.on(events.NewMessage(pattern='/calendar'))
    async def calendar_handler(event):
        logger.info(f"📩 /calendar от пользователя {event.chat_id}")
        info = await get_upcoming_events()
        await event.respond(f"🗓 **Твои планы:**\n\n{info}")

    @client.on(events.NewMessage(pattern='/conflicts'))
    async def conflicts_handler(event):
        """Скилл: Проверка конфликтов в календаре"""
        logger.info(f"📩 /conflicts от пользователя {event.chat_id}")
        report = await get_conflict_report()
        await event.respond(report)

    @client.on(events.NewMessage(pattern='/health'))
    async def health_handler(event):
        """Скилл: Статистика здоровья"""
        logger.info(f"📩 /health от пользователя {event.chat_id}")
        report = await get_health_report_text(7)
        await event.respond(report)

    @client.on(events.NewMessage(pattern='/news'))
    async def news_handler(event):
        logger.info(f"📩 /news от пользователя {event.chat_id}")
        news = await get_latest_news()
        await event.respond(f"🗞 **Новости:**\n\n{news}")

    @client.on(events.NewMessage(incoming=True))
    async def chat_handler(event):
        """Интеллектуальное общение (текст + голос) + Обработка напоминаний"""
        logger.info(f"📩 Сообщение от {event.chat_id}: {event.text[:50] if event.text else 'no text'}")
        
        # Если пришло голосовое сообщение
        if event.voice or event.audio:
            logger.info(f"🎤 Голосовое сообщение от {event.chat_id}")
            if not event.is_private:
                logger.info("⚠️ Пропуск (не личный чат)")
                return

            async with client.action(event.chat_id, 'record-audio'):
                path = await event.download_media(file="voice_msg.ogg")
                text = await transcribe_voice(path)
                if os.path.exists(path): os.remove(path)

                if not text:
                    await event.reply("Ой, я не смогла разобрать, что ты сказал... 🎤")
                    return

                event.text = text
                logger.info(f"🎤 Голос расшифрован: {text}")

        if not event.text or event.text.startswith('/'):
            logger.info(f"⚠️ Пропуск (нет текста или команда)")
            return

        # 🔔 ПРОВЕРКА НАПОМИНАНИЙ
        
        # 1. Подтверждение здоровья
        if reminder_manager.is_health_confirmation(event.text):
            logger.info(f"✅ Подтверждение здоровья от {event.chat_id}")
            reminder_manager.confirm_reminder(f"health_{datetime.now().strftime('%Y%m%d')}")
            await confirm_health()
            await event.respond(random.choice([
                "Умничка! 🥰",
                "Так держать! 👍",
                "Я спокойна. 😊",
                "Молодец! ❤️"
            ]))
            return
        
        # 2. Отсрочка напоминания
        if reminder_manager.is_snooze_request(event.text):
            minutes = reminder_manager.parse_snooze_command(event.text)
            if minutes:
                # Ищем активное напоминание
                for rid, reminder in reminder_manager.reminders.items():
                    if reminder.is_active and not reminder.is_confirmed:
                        reminder_manager.snooze_reminder(rid, minutes)
                        await event.respond(f"⏰ Хорошо, напомню через {minutes} мин!")
                        return
        
        # 3. Пропуск напоминания
        if reminder_manager.is_skip_request(event.text):
            logger.info(f"⏭️ Пропуск напоминания от {event.chat_id}")
            await event.respond("Хорошо, пропускаем. Но я ещё напомню! 😉")
            return
        
        # Детектор подтверждения здоровья (высокий приоритет)
        text_low = event.text.lower()
        if any(word in text_low for word in ['сделал', 'готово', 'окей', 'уколол']):
            logger.info(f"✅ Подтверждение здоровья от {event.chat_id}")
            await confirm_health()
            await event.respond(random.choice(["Умничка! 🥰", "Так держать! 👍", "Я спокойна. 😊"]))
            return

        if event.is_private:
            logger.info(f"💬 Обработка сообщения в ЛС: {event.text[:30]}...")
            async with client.action(event.chat_id, 'typing'):
                response = await ask_karina(event.text, chat_id=event.chat_id)
                logger.info(f"💬 Ответ: {response[:50] if response else 'None'}...")
                await event.reply(response)
        else:
            logger.info(f"⚠️ Пропуск (не личный чат)")
