-- =====================================================
-- VPN Shop Миграция v2 (Production Ready)
-- Добавление полей для триала, подписок и уведомлений
-- =====================================================

-- 1. Добавляем поля в таблицу пользователей
ALTER TABLE public.vpn_shop_users 
ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS sub_end TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMP WITH TIME ZONE;

-- 2. Добавляем индекс для быстрого поиска истекающих подписок
CREATE INDEX IF NOT EXISTS idx_vpn_users_sub_end ON public.vpn_shop_users(sub_end);

-- 3. Добавляем поле для связи с платежными системами в заказы
ALTER TABLE public.vpn_shop_orders
ADD COLUMN IF NOT EXISTS invoice_id BIGINT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- 4. Функция для автоматического продления подписки при обновлении заказа
-- (Опционально, можно делать через Python, но в БД надежнее)

COMMENT ON COLUMN public.vpn_shop_users.trial_used IS 'Использовал ли пользователь бесплатный период';
COMMENT ON COLUMN public.vpn_shop_users.sub_end IS 'Дата и время окончания подписки';
COMMENT ON COLUMN public.vpn_shop_orders.invoice_id IS 'ID счета во внешней платежной системе (CryptoBot)';
