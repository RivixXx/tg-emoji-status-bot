-- =====================================================
-- VPN Shop Миграция
-- Таблицы для продажи VPN-доступов через Telegram-бота
-- =====================================================

-- Пользователи VPN Shop
CREATE TABLE IF NOT EXISTS vpn_shop_users (
    user_id BIGINT PRIMARY KEY,
    state TEXT DEFAULT 'NEW',  -- NEW, WAITING_EMAIL, WAITING_CODE, REGISTERED
    email TEXT,
    verification_code TEXT,
    balance DECIMAL DEFAULT 0,
    vless_key TEXT,
    referred_by BIGINT REFERENCES vpn_shop_users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vpn_users_state ON vpn_shop_users(state);
CREATE INDEX IF NOT EXISTS idx_vpn_users_email ON vpn_shop_users(email);
CREATE INDEX IF NOT EXISTS idx_vpn_users_referred_by ON vpn_shop_users(referred_by);

-- Заказы VPN
CREATE TABLE IF NOT EXISTS vpn_shop_orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES vpn_shop_users(user_id),
    months INT NOT NULL,
    amount DECIMAL NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, completed, cancelled, refunded
    vless_key TEXT,
    payment_method TEXT,  -- sbp, crypto, balance
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON vpn_shop_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON vpn_shop_orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON vpn_shop_orders(created_at);

-- Рефералы
CREATE TABLE IF NOT EXISTS vpn_shop_referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT REFERENCES vpn_shop_users(user_id),
    referred_id BIGINT REFERENCES vpn_shop_users(user_id),
    commission DECIMAL DEFAULT 0,
    from_order_id INT REFERENCES vpn_shop_orders(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON vpn_shop_referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred_id ON vpn_shop_referrals(referred_id);

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_vpn_users_updated_at
    BEFORE UPDATE ON vpn_shop_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RPC функция для поиска рефералов
CREATE OR REPLACE FUNCTION get_referral_stats(user_id_param BIGINT)
RETURNS TABLE(
    total_referrals BIGINT,
    total_commission DECIMAL,
    active_referrals BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT r.referred_id)::BIGINT,
        COALESCE(SUM(r.commission), 0)::DECIMAL,
        COUNT(DISTINCT CASE WHEN u.state = 'REGISTERED' THEN r.referred_id END)::BIGINT
    FROM vpn_shop_referrals r
    LEFT JOIN vpn_shop_users u ON r.referred_id = u.user_id
    WHERE r.referrer_id = user_id_param;
END;
$$ LANGUAGE plpgsql;

-- Тестовые данные (для разработки)
-- INSERT INTO vpn_shop_users (user_id, state, email, balance) VALUES
-- (7480815681, 'REGISTERED', 'test@example.com', 100);

-- Комментарии
COMMENT ON TABLE vpn_shop_users IS 'Пользователи VPN Shop';
COMMENT ON TABLE vpn_shop_orders IS 'Заказы на VPN подписки';
COMMENT ON TABLE vpn_shop_referrals IS 'Реферальные начисления';

COMMENT ON COLUMN vpn_shop_users.state IS 'NEW: новый, WAITING_EMAIL: ожидание email, WAITING_CODE: ожидание кода, REGISTERED: зарегистрирован';
COMMENT ON COLUMN vpn_shop_orders.status IS 'pending: ожидает оплаты, completed: оплачен, cancelled: отменён, refunded: возвращён';
