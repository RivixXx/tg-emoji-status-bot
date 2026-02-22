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
from brains.smart_summary import generate_weekly_summary
from brains.aura_settings import aura_settings_manager, UserAuraSettings
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

    @client.on(events.NewMessage(pattern='/summary'))
    async def summary_handler(event):
        """Скилл: Еженедельный отчёт Smart Summary"""
        logger.info(f"📩 /summary от пользователя {event.chat_id}")
        
        # Парсим аргументы (количество дней)
        args = event.text.split()
        days = 7
        if len(args) > 1:
            try:
                days = int(args[1])
                days = max(1, min(days, 30))  # От 1 до 30 дней
            except ValueError:
                pass
        
        await event.respond(f"📊 Генерирую отчёт за {days} дн...")
        
        summary = await generate_weekly_summary(event.chat_id, days)
        
        message = f"""
📊 **Еженедельный отчёт**
{summary['period']['start']} - {summary['period']['end']}

❤️ **Здоровье:**
✅ Подтверждено: {summary['health']['confirmed']}
❌ Пропущено: {summary['health']['missed']}
📈 Успешность: {summary['health']['compliance_rate']}%
📊 Тренд: {summary['health']['trend']}

🧠 **Память:**
📝 Новых воспоминаний: {summary['memories']['new_memories']}

{summary['ai_summary']}
"""
        await event.respond(message)

    @client.on(events.NewMessage(pattern='/aurasettings'))
    async def aura_settings_handler(event):
        """Скилл: Управление настройками аур"""
        logger.info(f"📩 /aurasettings от пользователя {event.chat_id}")
        
        args = event.text.split()
        
        if len(args) < 2:
            # Показываем текущие настройки
            settings = await aura_settings_manager.get_settings(event.chat_id)
            
            message = f"""
⚙️ **Настройки аур**

🎨 Emoji-статус: {'✅' if settings.emoji_status.enabled else '❌'} {settings.emoji_status.start_time}-{settings.emoji_status.end_time}
📝 Био-статус: {'✅' if settings.bio_status.enabled else '❌'} {settings.bio_status.start_time}-{settings.bio_status.end_time}
❤️ Напоминание о здоровье: {'✅' if settings.health_reminder.enabled else '❌'} {settings.health_reminder.start_time}
☀️ Утреннее приветствие: {'✅' if settings.morning_greeting.enabled else '❌'} {settings.morning_greeting.start_time}
🌙 Вечернее напоминание: {'✅' if settings.evening_reminder.enabled else '❌'} {settings.evening_reminder.start_time}
🍽 Обед: {'✅' if settings.lunch_reminder.enabled else '❌'} {settings.lunch_reminder.start_time}
🧘 Перерыв: {'✅' if settings.break_reminder.enabled else '❌'} {settings.break_reminder.start_time}

Используйте:
/aurasettings enable <aura_name> [time]
/aurasettings disable <aura_name>
"""
            await event.respond(message)
            return
        
        command = args[1].lower()
        
        if command == 'enable' and len(args) >= 3:
            aura_name = args[2].lower()
            time_val = args[3] if len(args) > 3 else None
            
            valid_auras = ['emoji_status', 'bio_status', 'health_reminder', 'morning_greeting', 
                          'evening_reminder', 'lunch_reminder', 'break_reminder']
            
            if aura_name not in valid_auras:
                await event.respond(f"❌ Неизвестная аура. Доступные: {', '.join(valid_auras)}")
                return
            
            await aura_settings_manager.update_aura(
                event.chat_id, 
                aura_name, 
                enabled=True,
                start_time=time_val
            )
            await event.respond(f"✅ Аура '{aura_name}' включена{' в ' + time_val if time_val else ''}")
        
        elif command == 'disable' and len(args) >= 3:
            aura_name = args[2].lower()
            
            await aura_settings_manager.update_aura(event.chat_id, aura_name, enabled=False)
            await event.respond(f"⏸️ Аура '{aura_name}' выключена")
        
        else:
            await event.respond("""
Используйте:
/aurasettings — показать настройки
/aurasettings enable <aura_name> [time] — включить
/aurasettings disable <aura_name> — выключить

Доступные ауры: emoji_status, bio_status, health_reminder, morning_greeting, evening_reminder, lunch_reminder, break_reminder
""")

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

        if not event.text:
            return

        if event.text.startswith('/'):
            logger.info(f"⚡️ Пропуск команды в чат-хендлере: {event.text.split()[0]}")
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
