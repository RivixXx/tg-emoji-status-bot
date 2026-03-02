"""
Karina VPN UI - Dark Cyberpunk / Professional Space UI
Генерация красивых inline-сообщений с баннерами и структурированным текстом
"""
import os
from telethon.tl.custom import Button
from typing import Dict, Any

# ========== ПУТИ К БАННЕРАМ ==========
BANNERS_PATH = "banners"

BANNER_FILES = {
    "MENU": os.path.join(BANNERS_PATH, "menu.jpg"),
    "SUPPORT": os.path.join(BANNERS_PATH, "support.jpg"),
    "INSTRUCTIONS": os.path.join(BANNERS_PATH, "instructions.jpg"),
}

def get_status_bar():
    return "Статус сети: 🟢 Доступна (1.2 Gbps)\nUptime: 99.9%"

# ========== ТЕКСТЫ РАЗДЕЛОВ ==========

def get_main_menu_text(user: Dict[str, Any]) -> str:
    name = user.get("first_name", "Странник")
    return f"""
🌌 **KARINA VPN — ТВОЙ КЛЮЧ К СВОБОДЕ**

Привет, **{name}**! 🚀
Я обеспечу тебе максимальную анонимность и космическую скорость соединения.

{get_status_bar()}

━━━━━━━━━━━━━━━━━━━━
💡 *Выбирай тариф и подключайся за 30 секунд.*
"""

def get_tariffs_text() -> str:
    return """
💎 **ВИТРИНА ТАРИФОВ**

Все тарифы включают:
• ⚡️ Безлимитный трафик
• 🎬 YouTube 4K / Netflix без буферизации
• 🔐 Шифрование военного уровня
• 📱 До 5 устройств одновременно

━━━━━━━━━━━━━━━━━━━━
🎁 **Первый раз?** Возьми тест на 24 часа!
"""

def get_profile_text(user: Dict[str, Any]) -> str:
    email = user.get("email", "не привязан")
    balance = user.get("balance", 0)
    user_id = user.get("user_id", "N/A")
    sub_end = user.get("sub_end", "Нет активной подписки")
    
    return f"""
👤 **ЛИЧНЫЙ КАБИНЕТ**

🆔 **ID:** `{user_id}`
📧 **Email:** `{email}`
💳 **Баланс:** `{balance} ₽`

━━━━━━━━━━━━━━━━━━━━
📅 **Подписка до:** 
`{sub_end}`

*Управляй настройками и продлевай доступ в один клик.*
"""

def get_referral_text(user: Dict[str, Any], stats: Dict[str, Any]) -> str:
    total_referrals = stats.get("total_referrals", 0)
    total_commission = stats.get("total_commission", 0)
    user_id = user.get("user_id", "N/A")
    referral_link = f"https://t.me/your_bot?start={user_id}"
    
    return f"""
💼 **ПАРТНЕРСКАЯ ПРОГРАММА**

Приглашай друзей и получай **10%** от каждой их оплаты на свой баланс!

📈 **Твоя статистика:**
├─ Приглашено: `{total_referrals}`
└─ Заработано: `{total_commission} ₽`

🔗 **Твоя ссылка:**
`{referral_link}`

━━━━━━━━━━━━━━━━━━━━
💰 *Деньги с баланса можно тратить на оплату своего VPN.*
"""

def get_balance_text(user: Dict[str, Any]) -> str:
    balance = user.get("balance", 0)
    return f"""
💳 **ТВОЙ БАЛАНС**

Текущий счет: **{balance} ₽**

Ты можешь пополнить баланс через CryptoBot для быстрой оплаты подписок или использовать заработанные реферальные бонусы.
"""

def get_support_text() -> str:
    return """
💬 **ПОДДЕРЖКА**

Возникли проблемы с подключением или есть вопросы по оплате? Наш оператор поможет тебе во всем разобраться.

🕰 **Время работы:** 10:00 — 22:00 МСК
"""

def get_faq_main_text() -> str:
    return """
❓ **ЧАСТЫЕ ВОПРОСЫ (FAQ)**

1. **Работает ли в РФ?** Да, протокол VLESS/Reality обходит любые блокировки.
2. **Сколько устройств?** До 5 устройств на один ключ.
3. **Какая скорость?** Обычно 100+ Мбит/с.
"""

def get_trial_success_text():
    return """
🎉 **ТЕСТОВЫЙ ПЕРИОД АКТИВИРОВАН!**

Тебе выдано 24 часа доступа. Попробуй скорость прямо сейчас!
"""

def get_instructions_text() -> str:
    return """
📖 **ИНСТРУКЦИИ И НАСТРОЙКА**

Мы используем протокол **VLESS + Reality**. 

**Всего 3 шага:**
1. Скачай приложение.
2. Скопируй ключ.
3. Нажми "Подключиться".
"""

def get_download_text() -> str:
    return "📥 **СКАЧАТЬ ПРИЛОЖЕНИЯ**\n\nВыберите платформу:"

# ========== КНОПКИ ==========

def get_main_menu_keyboard() -> list:
    return [
        [Button.inline("🛒 КУПИТЬ VPN", b"menu_tariffs")],
        [Button.inline("🎁 Попробовать бесплатно (24ч)", b"buy_trial")],
        [Button.inline("👤 Профиль", b"menu_profile"), Button.inline("💳 Баланс", b"menu_balance")],
        [Button.inline("📖 Инструкции", b"menu_instructions"), Button.inline("📥 Скачать", b"menu_download")],
        [Button.inline("💼 Партнерка", b"menu_referral"), Button.inline("❓ FAQ", b"menu_faq")],
        [Button.inline("💬 Поддержка", b"menu_support")],
    ]

def get_tariffs_keyboard() -> list:
    return [
        [Button.inline("💎 1 Месяц — 150 ₽", b"pay_1")],
        [Button.inline("⭐️ 3 Месяца — 400 ₽", b"pay_3")],
        [Button.inline("🔥 6 Месяцев — 750 ₽", b"pay_6")],
        [Button.inline("◀️ Назад в меню", b"menu_main")],
    ]

def get_referral_keyboard() -> list:
    return [[Button.inline("📋 Скопировать ссылку", b"ref_copy")], [Button.inline("◀️ Назад", b"menu_main")]]

def get_faq_main_keyboard() -> list:
    return [[Button.inline("🌐 Общие вопросы", b"faq_general")], [Button.inline("◀️ Назад", b"menu_main")]]

def get_download_keyboard() -> list:
    return [
        [Button.url("🤖 Android", "https://play.google.com/store/apps/details?id=app.hiddify.com")],
        [Button.url("🍏 iOS", "https://apps.apple.com/app/hiddify-proxy/id6505229441")],
        [Button.inline("◀️ Назад", b"menu_main")]
    ]

def get_payment_methods_keyboard(amount: int, months: int):
    return [[Button.inline(f"💳 CryptoBot ({amount}₽)", f"pay_crypto_{months}_{amount}".encode())], [Button.inline("◀️ Назад", b"menu_tariffs")]]

def get_after_purchase_keyboard():
    return [[Button.inline("🔑 Мой ключ", b"get_my_key")], [Button.inline("🏠 В меню", b"menu_main")]]

def get_back_keyboard(main: bool = False) -> list:
    return [[Button.inline("🏠 Главное меню" if main else "◀️ Назад", b"menu_main" if main else b"menu_back")]]

def get_balance_keyboard() -> list:
    return [[Button.inline("💰 Пополнить", b"refill_crypto")], [Button.inline("◀️ Назад", b"menu_main")]]

def get_support_keyboard() -> list:
    return [[Button.inline("✍️ Написать оператору", b"support_write")], [Button.inline("◀️ Назад", b"menu_main")]]

def get_support_write_keyboard() -> list:
    return [[Button.inline("❌ Отмена", b"menu_support")]]

def get_platform_keyboard() -> list:
    return [[Button.inline("🤖 Android", b"instr_android"), Button.inline("🍏 iOS", b"instr_ios")], [Button.inline("◀️ Назад", b"menu_main")]]

def get_payment_keyboard(months: int) -> list:
    return [[Button.inline("✅ Я оплатил", f"checkpay_{months}".encode())], [Button.inline("◀️ Отмена", b"cancel_pay")]]

def get_instruction_platform_text(platform: str) -> str:
    return f"📱 Инструкция для {platform.upper()}: Скачай Hiddify и вставь ключ."
