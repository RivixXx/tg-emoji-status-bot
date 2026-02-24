-- VPN Shop Tables Migration
-- Karina AI v1.1
-- Дата: 25 февраля 2026 г.


-- ============================================================================
-- ТАБЛИЦЫ
-- ============================================================================

-- Таблица для пользователей VPN Shop
CREATE TABLE IF NOT EXISTS vpn_shop_users (
    user_id BIGINT PRIMARY KEY,
    email TEXT,
    state TEXT DEFAULT 'NEW',
    verification_code TEXT,
    referred_by BIGINT REFERENCES vpn_shop_users(user_id),
    balance NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для рефералов
CREATE TABLE IF NOT EXISTS vpn_shop_referrals (
    id BIGSERIAL PRIMARY KEY,
    referrer_id BIGINT REFERENCES vpn_shop_users(user_id),
    referred_id BIGINT REFERENCES vpn_shop_users(user_id),
    commission NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для заказов
CREATE TABLE IF NOT EXISTS vpn_shop_orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES vpn_shop_users(user_id),
    months INTEGER,
    amount NUMERIC,
    status TEXT DEFAULT 'pending',
    vless_key TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- ИНДЕКСЫ
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_vpn_users_state ON vpn_shop_users(state);
CREATE INDEX IF NOT EXISTS idx_vpn_users_referred_by ON vpn_shop_users(referred_by);
CREATE INDEX IF NOT EXISTS idx_vpn_referrals_referrer ON vpn_shop_referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_vpn_referrals_referred ON vpn_shop_referrals(referred_id);
CREATE INDEX IF NOT EXISTS idx_vpn_orders_user ON vpn_shop_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_vpn_orders_status ON vpn_shop_orders(status);

-- ============================================================================
-- КОММЕНТАРИИ
-- ============================================================================

COMMENT ON TABLE vpn_shop_users IS 'Пользователи VPN Shop с состояниями и рефералами';
COMMENT ON COLUMN vpn_shop_users.user_id IS 'Telegram User ID';
COMMENT ON COLUMN vpn_shop_users.email IS 'Email пользователя для верификации';
COMMENT ON COLUMN vpn_shop_users.state IS 'Состояние: NEW, WAITING_EMAIL, WAITING_CODE, REGISTERED';
COMMENT ON COLUMN vpn_shop_users.verification_code IS '4-значный код подтверждения';
COMMENT ON COLUMN vpn_shop_users.referred_by IS 'ID реферера (кто пригласил)';
COMMENT ON COLUMN vpn_shop_users.balance IS 'Баланс для реферальных комиссий';

COMMENT ON TABLE vpn_shop_referrals IS 'Реферальные связи и комиссии';
COMMENT ON COLUMN vpn_shop_referrals.referrer_id IS 'ID пригласившего';
COMMENT ON COLUMN vpn_shop_referrals.referred_id IS 'ID приглашённого';
COMMENT ON COLUMN vpn_shop_referrals.commission IS 'Сумма комиссии (10% от покупки)';

COMMENT ON TABLE vpn_shop_orders IS 'Заказы на VPN подписки';
COMMENT ON COLUMN vpn_shop_orders.months IS 'Срок подписки в месяцах';
COMMENT ON COLUMN vpn_shop_orders.amount IS 'Сумма заказа в рублях';
COMMENT ON COLUMN vpn_shop_orders.status IS 'Статус: pending, completed, cancelled';
COMMENT ON COLUMN vpn_shop_orders.vless_key IS 'VLESS ключ доступа';

-- ============================================================================
-- ТРИГГЕРЫ (автоматическое обновление updated_at)
-- ============================================================================

-- Функция для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для vpn_shop_users
DROP TRIGGER IF EXISTS update_vpn_shop_users_updated_at ON vpn_shop_users;
CREATE TRIGGER update_vpn_shop_users_updated_at
    BEFORE UPDATE ON vpn_shop_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- RLS (Row Level Security) - ОПЦИОНАЛЬНО
-- ============================================================================

-- Включить RLS (если нужно)
-- ALTER TABLE vpn_shop_users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE vpn_shop_referrals ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE vpn_shop_orders ENABLE ROW LEVEL SECURITY;

-- Политики (пример)
-- CREATE POLICY "Users can view own data" ON vpn_shop_users
--     FOR SELECT USING (user_id = current_setting('app.current_user_id')::bigint);

-- ============================================================================
-- ПРИМЕРЫ ДАННЫХ (для тестирования)
-- ============================================================================

-- Тестовый пользователь
-- INSERT INTO vpn_shop_users (user_id, email, state, balance) 
-- VALUES (123456789, 'test@test.com', 'REGISTERED', 0);

-- Тестовый заказ
-- INSERT INTO vpn_shop_orders (user_id, months, amount, status, vless_key) 
-- VALUES (123456789, 1, 150, 'completed', 'vless://test-key');

-- ============================================================================
-- ЗАПРОСЫ ДЛЯ ПРОВЕРКИ
-- ============================================================================

-- Проверка количества пользователей
-- SELECT state, COUNT(*) FROM vpn_shop_users GROUP BY state;

-- Проверка рефералов
-- SELECT referrer_id, COUNT(*) as referrals, SUM(commission) as total_commission 
-- FROM vpn_shop_referrals GROUP BY referrer_id;

-- Проверка заказов
-- SELECT status, COUNT(*) as orders, SUM(amount) as total_amount 
-- FROM vpn_shop_orders GROUP BY status;

-- ============================================================================
-- ОТКАТ (DROP TABLES)
-- ============================================================================

-- Для удаления таблиц (если нужно):
-- DROP TABLE IF EXISTS vpn_shop_orders CASCADE;
-- DROP TABLE IF EXISTS vpn_shop_referrals CASCADE;
-- DROP TABLE IF EXISTS vpn_shop_users CASCADE;
-- DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;
