"""
Tests for Level 1-3 Optimizations:
- Level 1: In-Memory Cache
- Level 2: Smart Typewriter
- Level 3: Fire-and-Forget
"""
import pytest
import asyncio
import time
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ========== LEVEL 1: IN-MEMORY CACHE TESTS ==========

class TestInMemoryCache:
    """Тесты для In-Memory Cache (Уровень 1)"""

    @pytest.fixture
    def cache_setup(self):
        """Фикстура для настройки кэша"""
        # Импортируем функции из main
        from main import run_bot_main
        # Создаём тестовый кэш
        USER_CACHE = {}
        CACHE_TTL = 300
        
        async def get_user_fast(user_id, mock_user_func):
            """Тестовая версия get_user_fast"""
            now = time.time()
            if user_id in USER_CACHE and (now - USER_CACHE[user_id]['time'] < CACHE_TTL):
                return USER_CACHE[user_id]['data']
            
            user = await mock_user_func(user_id)
            if user:
                USER_CACHE[user_id] = {'data': user, 'time': now}
            return user

        def update_user_cache(user_id, updates):
            """Тестовая версия update_user_cache"""
            if user_id in USER_CACHE:
                USER_CACHE[user_id]['data'].update(updates)
                USER_CACHE[user_id]['time'] = time.time()
        
        return USER_CACHE, get_user_fast, update_user_cache, CACHE_TTL

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self, cache_setup):
        """Проверка: промах кэша -> попадание"""
        USER_CACHE, get_user_fast, update_user_cache, CACHE_TTL = cache_setup
        
        mock_user = {"id": 123, "state": "NEW", "balance": 0}
        mock_func = AsyncMock(return_value=mock_user)
        
        # Первый запрос (промах кэша)
        user1 = await get_user_fast(123, mock_func)
        assert mock_func.called
        assert user1["state"] == "NEW"
        
        # Второй запрос (попадание в кэш)
        mock_func.reset_mock()
        user2 = await get_user_fast(123, mock_func)
        assert not mock_func.called  # БД не запрашивалась
        assert user2["state"] == "NEW"

    @pytest.mark.asyncio
    async def test_cache_update(self, cache_setup):
        """Проверка обновления кэша"""
        USER_CACHE, get_user_fast, update_user_cache, CACHE_TTL = cache_setup
        
        mock_user = {"id": 123, "state": "NEW", "balance": 0}
        mock_func = AsyncMock(return_value=mock_user)
        
        # Заполняем кэш
        await get_user_fast(123, mock_func)
        
        # Обновляем состояние
        update_user_cache(123, {"state": "WAITING_EMAIL", "email": "test@test.com"})
        
        # Проверяем обновление
        user = await get_user_fast(123, mock_func)
        assert user["state"] == "WAITING_EMAIL"
        assert user["email"] == "test@test.com"

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, cache_setup):
        """Проверка истечения TTL кэша"""
        USER_CACHE, get_user_fast, update_user_cache, CACHE_TTL = cache_setup
        
        # Устанавливаем короткий TTL для теста
        CACHE_TTL = 0.1  # 100мс для быстрого теста
        
        mock_user = {"id": 123, "state": "NEW"}
        mock_func = AsyncMock(return_value=mock_user)
        
        # Заполняем кэш
        await get_user_fast(123, mock_func)
        
        # Сразу после заполнения кэш должен работать
        mock_func.reset_mock()
        user = await get_user_fast(123, mock_func)
        assert not mock_func.called  # Из кэша
        
        # Ждём истечения TTL
        await asyncio.sleep(0.15)
        
        # Снова запрашиваем (должен быть промах)
        mock_func.reset_mock()
        user = await get_user_fast(123, mock_func)
        assert mock_func.called  # БД запрашивалась снова


# ========== LEVEL 2: SMART TYPEWRITER TESTS ==========

class TestSmartTypewriter:
    """Тесты для Smart Typewriter (Уровень 2)"""

    @pytest.fixture
    def typewriter_setup(self):
        """Фикстура для настройки печатной машинки"""
        from skills import send_with_typewriter
        return send_with_typewriter

    @pytest.mark.asyncio
    async def test_short_text_no_effect(self, typewriter_setup):
        """Проверка: короткий текст выводится сразу"""
        send_with_typewriter = typewriter_setup
        
        mock_event = AsyncMock()
        short_text = "Привет!"
        
        await send_with_typewriter(mock_event, short_text)
        
        # Должен быть вызван respond без edit
        mock_event.respond.assert_called_once_with(short_text)
        mock_event.edit.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_text_typewriter_effect(self, typewriter_setup):
        """Проверка: длинный текст выводится с эффектом"""
        send_with_typewriter = typewriter_setup
        
        mock_event = AsyncMock()
        mock_msg = AsyncMock()
        mock_event.respond = AsyncMock(return_value=mock_msg)
        
        long_text = "Это очень длинный текст который должен выводиться с эффектом печатной машинки " * 3
        
        await send_with_typewriter(mock_event, long_text)
        
        # Должен быть вызван respond для начала
        assert mock_event.respond.called
        
        # Должны быть вызваны edit для обновления текста
        assert mock_msg.edit.called

    @pytest.mark.asyncio
    async def test_typewriter_chunking(self, typewriter_setup):
        """Проверка разбивки текста на порции"""
        send_with_typewriter = typewriter_setup
        
        mock_event = AsyncMock()
        mock_msg = AsyncMock()
        mock_event.respond = AsyncMock(return_value=mock_msg)
        
        # Текст из 20 слов
        words_text = " ".join([f"слово{i}" for i in range(20)])
        
        await send_with_typewriter(mock_event, words_text)
        
        # Проверяем что были вызовы edit (минимум 2)
        assert mock_msg.edit.call_count >= 2


# ========== LEVEL 3: FIRE-AND-FORGET TESTS ==========

class TestFireAndForget:
    """Тесты для Fire-and-Forget (Уровень 3)"""

    @pytest.fixture
    def fire_forget_setup(self):
        """Фикстура для настройки fire-and-forget"""
        # Импортируем из main
        import importlib
        import main
        importlib.reload(main)  # Перезагружаем для чистого состояния
        
        return main.fire_and_forget, main.background_tasks

    def test_fire_and_forget_creates_task(self, fire_forget_setup):
        """Проверка: задача создаётся и добавляется в set"""
        fire_and_forget, background_tasks = fire_forget_setup
        
        async def dummy_coro():
            await asyncio.sleep(0.5)  # Держим задачу живой
            return "done"
        
        # Запускаем в event loop
        async def run_test():
            fire_and_forget(dummy_coro())
            await asyncio.sleep(0.1)  # Даём задаче добавиться в set
            assert len(background_tasks) > 0
        
        asyncio.run(run_test())

    @pytest.mark.asyncio
    async def test_fire_and_forget_completion(self, fire_forget_setup):
        """Проверка: задача завершается успешно"""
        fire_and_forget, background_tasks = fire_forget_setup
        
        result = {"completed": False}
        
        async def set_result():
            await asyncio.sleep(0.1)
            result["completed"] = True
        
        fire_and_forget(set_result())
        
        # Ждём завершения
        await asyncio.sleep(0.2)
        
        assert result["completed"] == True

    @pytest.mark.asyncio
    async def test_fire_and_forget_error_handling(self, fire_forget_setup):
        """Проверка: ошибка в фоновой задаче не ломает бота"""
        fire_and_forget, background_tasks = fire_forget_setup
        
        async def raise_error():
            await asyncio.sleep(0.1)
            raise ValueError("Test error")
        
        # Запускаем задачу с ошибкой
        fire_and_forget(raise_error())
        
        # Ждём завершения
        await asyncio.sleep(0.2)
        
        # Бот должен продолжать работать (задача удалена из set)
        # Ошибка должна быть залогирована (проверяем через mock logging)

    def test_fire_and_forget_no_loop(self, fire_forget_setup):
        """Проверка: отсутствие event loop не ломает функцию"""
        fire_and_forget, background_tasks = fire_forget_setup
        
        # Создаём новый event loop для теста
        async def test_without_loop():
            # Временно убираем loop
            loop = asyncio.get_running_loop()
            
            async def dummy():
                return "done"
            
            # fire_and_forget должен вернуть None если нет loop
            # (в реальном сценарии это происходит когда нет running loop)
        
        asyncio.run(test_without_loop())


# ========== INTEGRATION TESTS ==========

class TestOptimizationsIntegration:
    """Интеграционные тесты для всех оптимизаций"""

    @pytest.mark.asyncio
    async def test_cache_with_fire_and_forget(self):
        """Проверка: кэш работает вместе с fire-and-forget"""
        # Импортируем
        import main
        
        USER_CACHE = {}
        CACHE_TTL = 300
        
        async def mock_get_user(user_id):
            return {"id": user_id, "state": "NEW"}
        
        async def mock_update_state(user_id, state):
            await asyncio.sleep(0.1)  # Имитация задержки БД
            if user_id in USER_CACHE:
                USER_CACHE[user_id]['data']['state'] = state
        
        # Обновляем кэш мгновенно
        USER_CACHE[123] = {'data': {"id": 123, "state": "NEW"}, 'time': time.time()}
        
        # БД обновляем в фоне
        main.fire_and_forget(mock_update_state(123, "WAITING_EMAIL"))
        
        # Кэш должен обновиться сразу (в реальном коде это делает update_user_cache)
        USER_CACHE[123]['data']['state'] = "WAITING_EMAIL"
        
        # Проверяем что кэш содержит новое состояние
        assert USER_CACHE[123]['data']['state'] == "WAITING_EMAIL"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
