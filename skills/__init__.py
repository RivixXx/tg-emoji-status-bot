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
from brains.reminder_generator import clear_cache
from auras import confirm_health

from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def register_discovery_skills(client):
    @client.on(events.NewMessage(chats='me', pattern='(?i)id'))
    async def discovery_handler(event):
        logger.info(f"🔍 Детектор ID вызван пользователем {event.chat_id}")
        
        found = False
        if event.message.entities:
            for ent in event.message.entities:
                if isinstance(ent, types.MessageEntityCustomEmoji):
                    await event.reply(f"✅ Код кастомного эмодзи: <code>{ent.document_id}</code>\nСкопируй его и отправь мне.")
                    found = True
                    break
        
        if not found:
            await event.reply("❌ Это обычный эмодзи или текст. \nЧтобы получить ID для статуса, отправь **кастомный** эмодзи (из любого Premium-набора).")

def register_karina_base_skills(client):
    # Обработчик callback_query (кнопки напоминаний)
    @client.on(events.CallbackQuery())
    async def reminder_callback_handler(event):
        """Обработка нажатий на кнопки напоминаний"""
        data = event.data.decode('utf-8') if isinstance(event.data, bytes) else event.data
        logger.info(f"🔘 Callback: {data} от {event.chat_id}")
        
        # Получаем объект сообщения явно, чтобы избежать AttributeError
        message = await event.get_message()
        if not message:
            logger.error("❌ Не удалось получить сообщение для callback")
            return

        # Подтверждение здоровья
        if data == "confirm_health":
            await reminder_manager.confirm_reminder(f"health_{datetime.now().strftime('%Y%m%d')}")
            await confirm_health()
            await save_health_record(True)  # Сохраняем в базу!
            await event.answer("✅ Умничка! Я горжусь тобой! ❤️", alert=True)
            await event.edit(f"{message.text}\n\n✅ Подтверждено!")
            return
        
        # Отсрочка (snooze)
        if data.startswith("snooze_"):
            minutes = int(data.split("_")[1])
            # Ищем активное напоминание
            for rid, reminder in reminder_manager.reminders.items():
                if reminder.is_active and not reminder.is_confirmed:
                    await reminder_manager.snooze_reminder(rid, minutes)
                    await event.answer(f"⏰ Напомню через {minutes} мин!", alert=True)
                    await event.edit(f"{message.text}\n\n⏰ Отложено на {minutes} мин.")
                    return
        
        # Пропуск
        if data == "skip_health":
            await event.answer("Хорошо, но я ещё напомню! 😉", alert=True)
            await event.edit(f"{message.text}\n\n⏭️ Пропущено.")
            return
        
        # Подтверждение встречи
        if data == "confirm_meeting":
            await event.answer("👍 Отлично! Ты готов! 🚀", alert=True)
            await event.edit(f"{message.text}\n\n👍 Готов!")
            return
        
        # Подтверждение обеда
        if data == "confirm_lunch":
            await event.answer("🍽 Приятного аппетита! 🥗", alert=True)
            await event.edit(f"{message.text}\n\n🍽 Приятного!")
            return
        
        # Подтверждение перерыва
        if data == "confirm_break":
            await event.answer("🧘 Отлично! Отдыхай! 😊", alert=True)
            await event.edit(f"{message.text}\n\n🧘 Отдыхай!")
            return
        
        # Просто подтверждение (acknowledge)
        if data == "acknowledge":
            await event.answer("😊 Рада что ты со мной! 💕", alert=False)
            await event.edit(f"{message.text}\n\n😊 💕")
            return
        
        # По умолчанию
        await event.answer("👌 Ок!", alert=False)

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
    
    @client.on(events.NewMessage(pattern='/remember'))
    async def remember_handler(event):
        """Скилл: Запомнить факт"""
        text_to_save = event.text.replace('/remember', '').strip()
        if not text_to_save:
            await event.respond("Напиши, что именно мне нужно запомнить. 😊\nПример: `/remember Мой любимый цвет — синий`")
            return
        
        logger.info(f"🧠 Сохранение в память: {text_to_save}")
        success = await save_memory(text_to_save, metadata={"source": "manual_command", "user_id": event.chat_id})
        
        if success:
            await event.respond(f"✅ Запомнила! Теперь я буду это знать. 😊")
        else:
            await event.respond("Ой, что-то пошло не так при сохранении в базу памяти. 😔")

    @client.on(events.NewMessage(pattern='/weather'))
    async def weather_handler(event):
        logger.info(f"📩 /weather от пользователя {event.chat_id}")
        weather = await get_weather()
        if not weather:
            await event.respond("🌤 Ой, не смогла узнать погоду. Проверь API ключ в настройках! 😔")
        else:
            await event.respond(f"🌤 **Погода:**\n\n{weather}")
    
    @client.on(events.NewMessage(pattern='/clearrc'))
    async def clear_cache_handler(event):
        """Очистить кэш напоминаний (для тестирования)"""
        clear_cache()
        await event.respond("🧹 Кэш напоминаний очищен! Теперь все напоминания будут уникальными! ✨")

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
        
        # 1. Подтверждение здоровья (только если есть активное напоминание на сегодня)
        today_health_id = f"health_{datetime.now().strftime('%Y%m%d')}"
        is_waiting_health = False
        if today_health_id in reminder_manager.reminders:
            r = reminder_manager.reminders[today_health_id]
            if r.is_active and not r.is_confirmed:
                is_waiting_health = True

        if is_waiting_health and reminder_manager.is_health_confirmation(event.text):
            logger.info(f"✅ Подтверждение здоровья от {event.chat_id}")
            await reminder_manager.confirm_reminder(today_health_id)
            await confirm_health()
            await save_health_record(True)  # Сохраняем в базу!
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
                        await reminder_manager.snooze_reminder(rid, minutes)
                        await event.respond(f"⏰ Хорошо, напомню через {minutes} мин!")
                        return
        
        # 3. Пропуск напоминания
        if reminder_manager.is_skip_request(event.text):
            # Проверяем, есть ли что пропускать
            has_active = any(r.is_active and not r.is_confirmed for r in reminder_manager.reminders.values())
            if has_active:
                logger.info(f"⏭️ Пропуск напоминания от {event.chat_id}")
                await event.respond("Хорошо, пропускаем. Но я ещё напомню! 😉")
                return

        if event.is_private:
            logger.info(f"💬 Обработка сообщения в ЛС: {event.text[:30]}...")
            async with client.action(event.chat_id, 'typing'):
                response = await ask_karina(event.text, chat_id=event.chat_id)
                logger.info(f"💬 Ответ: {response[:50] if response else 'None'}...")
                await event.reply(response)
        else:
            logger.info(f"⚠️ Пропуск (не личный чат)")
