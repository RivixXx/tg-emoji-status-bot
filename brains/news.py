"""
Модуль мониторинга новостей с отслеживанием прочитанного
- Телематика транспорта
- Тахография
- Вебинары и онлайн-мероприятия
- Инновации отрасли

Особенности:
- Сохранение истории показанных новостей в БД
- Фильтрация дублей по URL
- Показ только новых новостей
- Кэширование на 1 час
"""
import httpx
import logging
import xml.etree.ElementTree as ET
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from brains.clients import supabase_client
from brains.config import MISTRAL_API_KEY

logger = logging.getLogger(__name__)

# ============================================================================
# ИСТОЧНИКИ НОВОСТЕЙ
# ============================================================================
# Используем стабильные RSS-фиды с постоянными URL
NEWS_SOURCES = [
    {
        "name": "Habr Transport",
        "url": "https://habr.com/ru/rss/hubs/transport/articles/all/?fl=ru",
        "category": "innovations",
        "enabled": True
    },
    {
        "name": "Вестник ГЛОНАСС",
        "url": "http://vestnik-glonass.ru/rss/",
        "category": "telematics",
        "enabled": True
    },
    {
        "name": "Росавтотранс",
        "url": "http://rosavtotrans.ru/ru/news/rss/",
        "category": "tachography",
        "enabled": True
    },
    {
        "name": "TransportRussia",
        "url": "https://www.transrussia.org/rss/news",
        "category": "logistics",
        "enabled": True
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

# Кэш новостей
NEWS_CACHE = {
    "news": None,
    "expire_at": None
}


# ============================================================================
# РАБОТА С БД
# ============================================================================

async def get_shown_news_links(limit: int = 100) -> set:
    """Получает множество URL уже показанных новостей"""
    try:
        response = supabase_client.table("news_history")\
            .select("link")\
            .order("shown_at", desc=True)\
            .limit(limit)\
            .execute()
        
        if response.data:
            return {item["link"] for item in response.data}
        return set()
    except Exception as e:
        logger.error(f"Error getting shown news: {e}")
        return set()


async def get_news_history_count(days: int = 7) -> int:
    """Получает количество новостей за период"""
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        response = supabase_client.table("news_history")\
            .select("id", count="exact")\
            .gte("shown_at", cutoff.isoformat())\
            .execute()
        
        return response.count if hasattr(response, 'count') else 0
    except Exception as e:
        logger.error(f"Error getting news count: {e}")
        return 0


async def save_news_to_history(news_items: List[Dict], user_id: int = 0):
    """Сохраняет показанные новости в историю"""
    if not news_items:
        return
    
    try:
        records = []
        for news in news_items:
            records.append({
                "title": news["title"],
                "link": news["link"],
                "source": news["source"],
                "category": news.get("category", "general"),
                "published_at": news.get("published_at"),
                "user_id": user_id
            })
        
        # Используем upsert чтобы избежать дублей
        for record in records:
            try:
                supabase_client.table("news_history")\
                    .upsert(record, on_conflict="link")\
                    .execute()
            except Exception as e:
                logger.debug(f"News already exists: {record['link']}")
        
        logger.info(f"💾 Сохранено {len(records)} новостей в историю")
    except Exception as e:
        logger.error(f"Error saving news history: {e}")


async def clear_old_news_history(days: int = 30):
    """Очищает старую историю новостей"""
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        response = supabase_client.table("news_history")\
            .delete()\
            .lt("shown_at", cutoff.isoformat())\
            .execute()
        
        logger.info(f"🧹 Удалено старых новостей: {len(response.data) if response.data else 0}")
        return len(response.data) if response.data else 0
    except Exception as e:
        logger.error(f"Error clearing old news: {e}")
        return 0


# ============================================================================
# ПАРСИНГ RSS
# ============================================================================

def extract_publication_date(item) -> Optional[datetime]:
    """Извлекает дату публикации из RSS элемента"""
    date_fields = ['pubDate', 'published', 'updated', 'created']
    
    for field in date_fields:
        date_elem = item.find(field)
        if date_elem is not None and date_elem.text:
            try:
                # Пробуем разные форматы
                date_str = date_elem.text
                # RFC 822 формат
                if 'GMT' in date_str or '+' in date_str:
                    from email.utils import parsedate_to_datetime
                    return parsedate_to_datetime(date_str)
                # ISO формат
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except Exception:
                continue
    return datetime.now(timezone.utc)


async def fetch_rss(client: httpx.AsyncClient, source: Dict) -> List[Dict]:
    """Загружает и парсит один RSS источник"""
    try:
        response = await client.get(source["url"], timeout=15.0, follow_redirects=True)
        
        if response.status_code != 200:
            logger.warning(f"❌ Источник {source['name']} вернул {response.status_code}")
            return []
        
        root = ET.fromstring(response.text)
        items = []
        
        # Ищем элементы item или entry (для разных форматов RSS)
        rss_items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
        
        for item in rss_items[:15]:  # Берём максимум 15 последних
            title_elem = item.find('title')
            link_elem = item.find('link')
            
            # Для Atom формата link это элемент с атрибутом href
            if link_elem is not None and link_elem.text is None:
                link_elem = item.find('{http://www.w3.org/2005/Atom}link')
                if link_elem is not None and 'href' in link_elem.attrib:
                    link = link_elem.attrib['href']
                else:
                    continue
            else:
                link = link_elem.text if link_elem is not None else None
            
            if title_elem is None or not title_elem.text or not link:
                continue
            
            title = title_elem.text.strip()
            
            # Проверяем на ключевые слова
            match_score = sum(1 for kw in KEYWORDS if kw.lower() in title.lower())
            
            # Извлекаем дату публикации
            pub_date = extract_publication_date(item)
            
            items.append({
                "title": title,
                "link": link,
                "source": source["name"],
                "category": source["category"],
                "score": match_score,
                "published_at": pub_date.isoformat() if pub_date else None
            })
        
        return items
        
    except httpx.TimeoutException:
        logger.warning(f"⌛️ Таймаут источника {source['name']}")
        return []
    except Exception as e:
        logger.warning(f"❌ Ошибка источника {source['name']}: {e}")
        return []


# ============================================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================================

async def get_latest_news(limit: int = 5, force_refresh: bool = False, user_id: int = 0) -> str:
    """
    Собирает новости из всех источников, фильтрует уже показанные и возвращает
    курированный список
    
    Args:
        limit: Максимальное количество новостей
        force_refresh: Игнорировать кэш
        user_id: ID пользователя для персонализации
    """
    moscow_tz = timezone(timedelta(hours=3))
    now = datetime.now(moscow_tz)
    
    # Проверка кэша (если не force_refresh)
    if not force_refresh and NEWS_CACHE["news"] and NEWS_CACHE["expire_at"]:
        if now < NEWS_CACHE["expire_at"]:
            logger.debug("📰 Новости: используем кэш")
            return NEWS_CACHE["news"]
    
    # Получаем список уже показанных URL
    shown_links = await get_shown_news_links(limit=200)
    logger.info(f"📰 Найдено {len(shown_links)} уже показанных новостей")
    
    # Собираем новости из всех источников
    all_news = []
    enabled_sources = [s for s in NEWS_SOURCES if s.get("enabled", True)]
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [fetch_rss(client, source) for source in enabled_sources]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            all_news.extend(res)
    
    logger.info(f"📰 Всего собрано новостей: {len(all_news)}")
    
    # Фильтруем дубли и уже показанные
    unique_news = []
    seen_links = set()
    
    for news in all_news:
        # Пропускаем если URL уже есть в текущей выборке
        if news["link"] in seen_links:
            continue
        
        # Пропускаем если уже показывали
        if news["link"] in shown_links:
            continue
        
        seen_links.add(news["link"])
        unique_news.append(news)
    
    logger.info(f"📰 Новых новостей после фильтрации: {len(unique_news)}")
    
    # Если новых новостей нет
    if not unique_news:
        # Проверяем когда последний раз показывали новости
        count = await get_news_history_count(days=1)
        if count > 0:
            message = "📰 Новых новостей за сегодня нет. Всё важное я уже рассказывала! 😊"
        else:
            message = "📰 Новых новостей пока нет. Источники могут быть недоступны или в мире телематики тихо... ☕"
        
        NEWS_CACHE["news"] = message
        NEWS_CACHE["expire_at"] = now + timedelta(minutes=30)
        return message
    
    # Сортируем по релевантности и дате
    unique_news.sort(key=lambda x: (x["score"], x.get("published_at", "")), reverse=True)
    
    # Берём топ
    top_news = unique_news[:limit]
    
    # Сохраняем в историю
    await save_news_to_history(top_news, user_id)
    
    # Формируем отчёт
    report = await format_news_report(top_news)
    
    # Сохраняем в кэш на 1 час
    NEWS_CACHE["news"] = report
    NEWS_CACHE["expire_at"] = now + timedelta(hours=1)
    
    return report


async def format_news_report(news_list: List[Dict]) -> str:
    """Форматирует новости в красивый отчёт для Telegram"""
    if not news_list:
        return "Новостей нет."
    
    report = ["🗞 **Свежее в телематике и транспорте:**\n"]
    
    # Группируем по категориям
    categories_order = ["telematics", "tachography", "innovations", "logistics"]
    category_names = {
        "telematics": "🛰 Телематика и ГЛОНАСС",
        "tachography": "📊 Тахография и контроль",
        "innovations": "💡 Инновации",
        "logistics": "🚚 Логистика"
    }
    
    for category in categories_order:
        cat_news = [n for n in news_list if n.get("category") == category][:2]
        
        if cat_news:
            header = category_names.get(category, "📰 Новости")
            report.append(f"*{header}*")
            
            for n in cat_news:
                # Сокращаем длинные заголовки
                title = n["title"]
                if len(title) > 100:
                    title = title[:97] + "..."
                
                report.append(f"🔹 {title}")
                report.append(f"🔗 {n['link']}")
            
            report.append("")
    
    # Добавляем мероприятия
    today = datetime.now()
    upcoming_events = []
    
    for ev in INDUSTRY_EVENTS_2026:
        # Простая проверка - показываем все
        upcoming_events.append(ev)
    
    if upcoming_events:
        report.append("📅 **Ближайшие мероприятия 2026:**")
        for ev in upcoming_events[:3]:
            report.append(f"📍 {ev['date']} — {ev['title']}")
        report.append("")
    
    report.append("_Хочешь узнать подробнее? Просто спроси!_")
    
    return "\n".join(report)


# ============================================================================
# УПРАВЛЕНИЕ ИСТОЧНИКАМИ
# ============================================================================

async def get_news_sources() -> List[Dict]:
    """Получает список всех источников"""
    return NEWS_SOURCES.copy()


async def enable_source(source_name: str) -> bool:
    """Включает источник"""
    for source in NEWS_SOURCES:
        if source["name"].lower() == source_name.lower():
            source["enabled"] = True
            logger.info(f"✅ Источник '{source_name}' включен")
            return True
    return False


async def disable_source(source_name: str) -> bool:
    """Отключает источник"""
    for source in NEWS_SOURCES:
        if source["name"].lower() == source_name.lower():
            source["enabled"] = False
            logger.info(f"⏸️ Источник '{source_name}' отключен")
            return True
    return False


async def add_custom_source(name: str, url: str, category: str) -> bool:
    """Добавляет пользовательский источник"""
    # Проверка на дубликат URL
    for source in NEWS_SOURCES:
        if source["url"] == url:
            return False
    
    NEWS_SOURCES.append({
        "name": name,
        "url": url,
        "category": category,
        "enabled": True
    })
    
    logger.info(f"📰 Добавлен источник: {name}")
    return True


# ============================================================================
# ОЧИСТКА КЭША
# ============================================================================

def clear_news_cache():
    """Очищает кэш новостей"""
    NEWS_CACHE["news"] = None
    NEWS_CACHE["expire_at"] = None
    logger.info("🧹 Кэш новостей очищен")
