import httpx
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Ссылка на RSS Хабра (раздел Транспорт)
NEWS_RSS_URL = "https://habr.com/ru/rss/hub/transport/all/?fl=ru"

async def get_latest_news(limit=3):
    """Получает последние новости из RSS ленты"""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(NEWS_RSS_URL)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                news_items = []
                
                for item in root.findall('.//item')[:limit]:
                    title = item.find('title').text
                    link = item.find('link').text
                    news_items.append(f"🔹 {title}\n🔗 {link}")
                
                if news_items:
                    return "\n\n".join(news_items)
                return "Сегодня новостей пока нет... ☕"
            else:
                logger.error(f"Ошибка получения новостей: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при парсинге новостей: {e}")
        return None
