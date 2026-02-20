"""
Модуль мониторинга новостей и мероприятий
- Телематика транспорта
- Тахография
- Вебинары и онлайн-мероприятия
- Инновации отрасли
"""
import httpx
import logging
import xml.etree.ElementTree as ET
import asyncio
from datetime import datetime
from brains.config import MISTRAL_API_KEY

logger = logging.getLogger(__name__)

# Источники новостей
NEWS_SOURCES = [
    {
        "name": "Habr Transport",
        "url": "https://habr.com/ru/rss/hubs/transport/articles/all/?fl=ru",
        "category": "innovations"
    },
    {
        "name": "Вестник ГЛОНАСС",
        "url": "http://vestnik-glonass.ru/rss/",
        "category": "telematics"
    },
    {
        "name": "Росавтотранс",
        "url": "http://rosavtotrans.ru/ru/news/rss/",
        "category": "tachography"
    }
]

# Ключевые слова для фильтрации (приоритет)
KEYWORDS = [
    "телематика", "тахограф", "мониторинг транспорта", "глонасс", 
    "gps", "логистика", "цифровизация", "вебинар", "онлайн-встреча",
    "минтранс", "автопарк", "скуд", "учет топлива", "эра-глонасс"
]

# Календарь подтвержденных мероприятий 2026
INDUSTRY_EVENTS_2026 = [
    {"date": "24-25.03.2026", "title": "ИТС регионам 2026 (Тула)", "desc": "Телематика, мониторинг, ИТС"},
    {"date": "01-03.04.2026", "title": "Транспортно-логистический форум (СПб)", "desc": "B2B логистика и IT"},
    {"date": "02-03.04.2026", "title": "Управление автопарком 2026 (Астана)", "desc": "ИИ и безопасность флота"},
    {"date": "09-11.06.2026", "title": "Электроника-Транспорт 2026 (Москва)", "desc": "Навигационные сервисы на ВДНХ"},
    {"date": "Апрель 2026", "title": "НАВИТЕХ-2026", "desc": "Главная выставка навигации в РФ"}
]

async def fetch_rss(client, source):
    """Загружает и парсит один RSS источник"""
    try:
        response = await client.get(source["url"], timeout=10.0)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            items = []
            for item in root.findall('.//item')[:10]:
                title = item.find('title').text
                link = item.find('link').text
                # Проверяем на ключевые слова
                match_score = sum(1 for kw in KEYWORDS if kw.lower() in title.lower())
                items.append({
                    "title": title,
                    "link": link,
                    "source": source["name"],
                    "category": source["category"],
                    "score": match_score
                })
            return items
    except Exception as e:
        logger.warning(f"Ошибка источника {source['name']}: {e}")
    return []

async def get_latest_news(limit=5):
    """
    Собирает новости из всех источников, фильтрует и возвращает 
    курированный список (через AI если возможно)
    """
    all_news = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_rss(client, source) for source in NEWS_SOURCES]
        results = await asyncio.gather(*tasks)
        for res in results:
            all_news.extend(res)

    # Сортируем по релевантности (сначала те, где есть ключевые слова)
    all_news.sort(key=lambda x: x["score"], reverse=True)
    
    # Берем топ релевантных
    top_news = all_news[:10]
    
    if not top_news:
        return "Сегодня в мире телематики тишина... ☕"

    # Формируем отчет
    report = ["🗞 **Актуально в телематике и тахографии:**\n"]
    
    # Группируем по категориям
    for category in ["telematics", "tachography", "innovations"]:
        cat_news = [n for n in top_news if n["category"] == category][:2]
        if cat_news:
            header = {
                "telematics": "🛰 Телематика и ГЛОНАСС",
                "tachography": "📊 Тахография и контроль",
                "innovations": "💡 Инновации"
            }.get(category)
            report.append(f"*{header}*")
            for n in cat_news:
                report.append(f"🔹 {n['title']}\n🔗 {n['link']}")
            report.append("")

    # Добавляем мероприятия
    report.append("📅 **Ближайшие мероприятия 2026:**")
    today = datetime.now()
    # Показываем только будущие (упрощенно)
    for ev in INDUSTRY_EVENTS_2026[:3]:
        report.append(f"📍 {ev['date']} — {ev['title']}")
    
    report.append("\n_Хочешь узнать подробнее о конкретном событии? Просто спроси меня!_")
    
    return "\n".join(report)

async def curate_news_with_ai(news_list: list):
    """
    (Опционально) Использует Mistral для выбора 3-5 самых важных новостей
    """
    if not MISTRAL_API_KEY or not news_list:
        return None
    
    prompt = "Ниже список новостей по телематике. Выбери 3 самых важных и кратко (одной фразой) объясни почему. Верни в красивом формате Telegram.\n\n"
    for i, n in enumerate(news_list):
        prompt += f"{i+1}. {n['title']}\n"

    # Тут можно вызвать ask_karina, но чтобы не было рекурсии, лучше отдельный простой вызов
    # Оставим это на будущее развитие
    return None
