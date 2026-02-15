import logging
from telethon import events, types
from brains.weather import get_weather
from brains.ai import ask_karina

logger = logging.getLogger(__name__)

def register_discovery_skills(client):
    """Скилл поиска ID кастомных эмодзи (для UserBot)"""
    @client.on(events.NewMessage(chats='me'))
    async def discovery_handler(event):
        if event.message.text and event.message.text.lower().startswith('id'):
            if event.message.entities:
                found = False
                for ent in event.message.entities:
                    if isinstance(ent, types.MessageEntityCustomEmoji):
                        await event.reply(f"Код для emoji_map:\n<code>{ent.document_id}</code>")
                        found = True
                if not found:
                    await event.reply("В этом сообщении не найдено кастомных эмодзи.")

def register_karina_base_skills(client):
    """Базовые команды Карины (Bot)"""
    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond("Привет! Я Карина, твой личный ассистент. 😊\n\nЯ могу:\n— Менять твой статус и био\n— Напоминать о работе\n— Рассказывать о погоде (/weather)")

    @client.on(events.NewMessage(pattern='/weather'))
    async def weather_command_handler(event):
        """Скилл: Узнать погоду по команде"""
        await event.respond("Секунду, сверяюсь с метеостанцией... 📡")
        info = await get_weather()
        if info:
            await event.respond(f"🌤 **Текущая погода:**\n{info}")
        else:
            await event.respond("К сожалению, не смогла достучаться до сервера погоды. Проверь API_KEY в настройках. ☁️")

    @client.on(events.NewMessage(incoming=True))
    async def chat_handler(event):
        """Интеллектуальное общение через LLM"""
        if event.text and not event.text.startswith('/'):
            # Отвечаем только в личке
            if event.is_private:
                async with client.action(event.chat_id, 'typing'):
                    response = await ask_karina(event.text)
                    await event.reply(response)
