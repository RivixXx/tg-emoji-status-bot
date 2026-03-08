"""
Supabase Retry Utility
Универсальный декоратор и функции для retry-логики Supabase запросов
"""
import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
from supabase import Client

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def supabase_retry(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 10.0,
    timeout: float = 60.0,
    **kwargs
) -> Optional[T]:
    """
    Выполняет Supabase запрос с retry-логикой и экспоненциальной задержкой.
    
    Args:
        func: Функция Supabase для выполнения (например, table().insert().execute)
        *args: Позиционные аргументы для функции
        max_retries: Максимальное количество попыток
        base_delay: Базовая задержка между попытками (сек)
        max_delay: Максимальная задержка (сек)
        timeout: Таймаут для каждой попытки (сек)
        **kwargs: Именованные аргументы для функции
    
    Returns:
        Результат выполнения или None при неудаче
    
    Пример использования:
        result = await supabase_retry(
            supabase_client.table("memories").insert(data).execute,
            max_retries=3
        )
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Выполняем с таймаутом
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            last_error = TimeoutError(f"Supabase request timeout after {timeout}s")
            logger.warning(f"⌛️ Supabase timeout (attempt {attempt + 1}/{max_retries})")
            
        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            logger.warning(f"⚠️ Supabase error (attempt {attempt + 1}/{max_retries}): {error_type} - {e}")
        
        # Экспоненциальная задержка перед следующей попыткой
        if attempt < max_retries - 1:
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.info(f"⏳ Жду {delay:.1f}s перед следующей попыткой...")
            await asyncio.sleep(delay)
    
    # Все попытки исчерпаны
    logger.error(f"❌ Supabase request failed after {max_retries} attempts: {last_error}")
    return None


async def safe_supabase_insert(
    client: Client,
    table_name: str,
    data: dict,
    max_retries: int = 3
) -> Optional[Any]:
    """
    Безопасная вставка данных в таблицу Supabase.
    
    Args:
        client: Supabase клиент
        table_name: Имя таблицы
        data: Данные для вставки
        max_retries: Максимальное количество попыток
    
    Returns:
        Результат или None при ошибке
    """
    if not client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None
    
    return await supabase_retry(
        client.table(table_name).insert(data).execute,
        max_retries=max_retries
    )


async def safe_supabase_select(
    client: Client,
    table_name: str,
    columns: str = "*",
    filters: Optional[dict] = None,
    limit: Optional[int] = None,
    order_by: Optional[str] = None,
    order_desc: bool = False,
    max_retries: int = 3
) -> Optional[list]:
    """
    Безопасное чтение данных из таблицы Supabase.
    
    Args:
        client: Supabase клиент
        table_name: Имя таблицы
        columns: Столбцы для выбора
        filters: Фильтры в формате {"column": value}
        limit: Максимальное количество записей
        order_by: Столбец для сортировки
        order_desc: Сортировка по убыванию
        max_retries: Максимальное количество попыток
    
    Returns:
        Список записей или None при ошибке
    """
    if not client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None
    
    query = client.table(table_name).select(columns)
    
    if filters:
        for column, value in filters.items():
            query = query.eq(column, value)
    
    if limit:
        query = query.limit(limit)
    
    if order_by:
        query = query.order(order_by, desc=order_desc)
    
    result = await supabase_retry(query.execute, max_retries=max_retries)
    
    if result and result.data:
        return result.data
    return []


async def safe_supabase_update(
    client: Client,
    table_name: str,
    data: dict,
    eq_column: str,
    eq_value: Any,
    max_retries: int = 3
) -> Optional[Any]:
    """
    Безопасное обновление данных в таблице Supabase.
    
    Args:
        client: Supabase клиент
        table_name: Имя таблицы
        data: Данные для обновления
        eq_column: Столбец для условия WHERE
        eq_value: Значение для условия WHERE
        max_retries: Максимальное количество попыток
    
    Returns:
        Результат или None при ошибке
    """
    if not client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None
    
    return await supabase_retry(
        client.table(table_name).update(data).eq(eq_column, eq_value).execute,
        max_retries=max_retries
    )


async def safe_supabase_delete(
    client: Client,
    table_name: str,
    eq_column: str,
    eq_value: Any,
    max_retries: int = 3
) -> Optional[Any]:
    """
    Безопасное удаление данных из таблицы Supabase.
    
    Args:
        client: Supabase клиент
        table_name: Имя таблицы
        eq_column: Столбец для условия WHERE
        eq_value: Значение для условия WHERE
        max_retries: Максимальное количество попыток
    
    Returns:
        Результат или None при ошибке
    """
    if not client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None
    
    return await supabase_retry(
        client.table(table_name).delete().eq(eq_column, eq_value).execute,
        max_retries=max_retries
    )


async def safe_supabase_rpc(
    client: Client,
    function_name: str,
    params: Optional[dict] = None,
    max_retries: int = 2
) -> Optional[Any]:
    """
    Безопасный вызов RPC функции Supabase.
    
    Args:
        client: Supabase клиент
        function_name: Имя RPC функции
        params: Параметры для функции
        max_retries: Максимальное количество попыток
    
    Returns:
        Результат или None при ошибке
    """
    if not client:
        logger.error("❌ Supabase клиент не инициализирован")
        return None
    
    params = params or {}
    
    return await supabase_retry(
        client.rpc(function_name, params).execute,
        max_retries=max_retries
    )
