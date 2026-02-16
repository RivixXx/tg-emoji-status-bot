import logging
import random
import os
from telethon import events, types
from brains.weather import get_weather
from brains.ai import ask_karina
from brains.news import get_latest_news
from brains.memory import save_memory
from brains.calendar import get_upcoming_events, add_calendar
from brains.stt import transcribe_voice
from auras import confirm_health

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
        await event.respond(
            "Привет! Я Карина. 😊\n\nЯ теперь не просто бот, у меня есть удобная панель управления! Нажми кнопку ниже или используй /app.",
            buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
        )

    @client.on(events.NewMessage(pattern='/app'))
    async def app_command_handler(event):
        """Скилл: Открыть Mini App"""
        await event.respond(
            "Твоя персональная панель управления Кариной:",
            buttons=[types.KeyboardButtonWebView("Открыть панель 📱", url="https://tg-emoji-status-bot-production.up.railway.app/")]
        )

    @client.on(events.NewMessage(pattern='/calendar'))
    async def calendar_handler(event):
        info = await get_upcoming_events()
        await event.respond(f"🗓 **Твои планы:**\n\n{info}")

    @client.on(events.NewMessage(pattern='/news'))
    async def news_handler(event):
        news = await get_latest_news()
        await event.respond(f"🗞 **Новости:**\n\n{news}")

    @client.on(events.NewMessage(incoming=True))
    async def chat_handler(event):
        """Интеллектуальное общение (текст + голос)"""
        # Если пришло голосовое сообщение
        if event.voice or event.audio:
            if not event.is_private: return
            
            async with client.action(event.chat_id, 'record-audio'):
                path = await event.download_media(file="voice_msg.ogg")
                text = await transcribe_voice(path)
                if os.path.exists(path): os.remove(path)
                
                if not text:
                    await event.reply("Ой, я не смогла разобрать, что ты сказал... 🎤")
                    return
                
                event.text = text
                logger.info(f"🎤 Голос расшифрован: {text}")

        if not event.text or event.text.startswith('/'): return
        
        # Детектор подтверждения здоровья (высокий приоритет)
        text_low = event.text.lower()
        if any(word in text_low for word in ['сделал', 'готово', 'окей', 'уколол']):
            await confirm_health()
            await event.respond(random.choice(["Умничка! 🥰", "Так держать! 👍", "Я спокойна. 😊"]))
            return

        if event.is_private:
            async with client.action(event.chat_id, 'typing'):
                response = await ask_karina(event.text, chat_id=event.chat_id)
                await event.reply(response)
