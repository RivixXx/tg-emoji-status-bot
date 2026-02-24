"""
Tests for Circuit Breaker pattern in ai.py
"""
import pytest
import time
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brains.ai import CircuitBreaker


class TestCircuitBreaker:
    """Тесты для CircuitBreaker"""

    def test_initial_state(self):
        """Проверка начального состояния"""
        breaker = CircuitBreaker(max_failures=3, recovery_time=60)
        
        assert breaker.is_open == False
        assert breaker.failures == 0
        assert breaker.can_proceed() == True

    def test_record_success(self):
        """Проверка записи успеха"""
        breaker = CircuitBreaker()
        breaker.record_success()
        
        assert breaker.is_open == False
        assert breaker.failures == 0

    def test_record_failure_opens_circuit(self):
        """Проверка что circuit открывается после max_failures"""
        breaker = CircuitBreaker(max_failures=3, recovery_time=60)
        
        # 3 неудачи должны открыть circuit
        for i in range(3):
            breaker.record_failure()
        
        assert breaker.is_open == True
        assert breaker.failures == 3
        assert breaker.can_proceed() == False

    def test_recovery_after_timeout(self):
        """Проверка восстановления после recovery_time"""
        breaker = CircuitBreaker(max_failures=3, recovery_time=1)  # 1 секунда
        
        # Открываем circuit
        for i in range(3):
            breaker.record_failure()
        
        assert breaker.is_open == True
        
        # Ждём восстановления
        time.sleep(1.1)
        
        # После recovery_time можно попробовать снова
        assert breaker.can_proceed() == True
        
        # Успех закрывает circuit
        breaker.record_success()
        assert breaker.is_open == False
        assert breaker.failures == 0

    def test_success_resets_failures(self):
        """Проверка что успех сбрасывает счётчик неудач"""
        breaker = CircuitBreaker(max_failures=3, recovery_time=60)
        
        # 2 неудачи
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failures == 2
        
        # Успех сбрасывает
        breaker.record_success()
        assert breaker.failures == 0

    def test_partial_failures_then_success(self):
        """Проверка частичных неудач с последующим успехом"""
        breaker = CircuitBreaker(max_failures=5, recovery_time=60)
        
        # 3 неудачи из 5
        for i in range(3):
            breaker.record_failure()
        
        assert breaker.failures == 3
        assert breaker.is_open == False  # Ещё не открыт
        
        # Успех сбрасывает
        breaker.record_success()
        assert breaker.failures == 0
        assert breaker.is_open == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
