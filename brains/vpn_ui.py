"""
Karina VPN UI - Dark Cyberpunk / Professional Space UI
Генерация красивых inline-сообщений с баннерами и структурированным текстом
"""
import os
from telethon.tl.custom import Button
from typing import Optional, Dict, Any

# ========== ПУТИ К БАННЕРАМ ==========
BANNERS_PATH = "banners"

BANNER_FILES = {
    "MENU": os.path.join(BANNERS_PATH, "menu.jpg"),
    "SUPPORT": os.path.join(BANNERS_PATH, "support.jpg"),
    "INSTRUCTIONS": os.path.join(BANNERS_PATH, "instructions.jpg"),
}

# ========== ЦВЕТОВАЯ СХЕМА (Dark Cyberpunk) ==========
# Статусы: 🟢 Online | 🟡 High Load | 🔴 Maintenance

def get_status_bar():
    return "Статус сети: 🟢 Доступна (1.2 Gbps)\nUptime: 99.9%"

# ========== ТЕКСТЫ РАЗДЕЛОВ ==========

def get_main_menu_text(user: Dict[str, Any]) -> str:
    """Текст главного меню"""
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
    """Текст витрины с тарифами"""
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
    """Текст профиля пользователя"""
    email = user.get("email", "не привязан")
    balance = user.get("balance", 0)
    user_id = user.get("user_id", "N/A")
    # Допустим, мы добавим срок подписки
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

def get_trial_success_text():
    return """
🎉 **ТЕСТОВЫЙ ПЕРИОД АКТИВИРОВАН!**

Тебе выдано 24 часа полного доступа.
Попробуй скорость, посмотри видео в 4K.

👇 **Твой ключ и инструкции ниже:**
"""

# ========== КНОПКИ ==========

def get_main_menu_keyboard() -> list:
    """Клавиатура главного меню"""
    return [
        [Button.inline("🛒 КУПИТЬ VPN", b"menu_tariffs")],
        [Button.inline("🎁 Попробовать бесплатно (24ч)", b"buy_trial")],
        [Button.inline("👤 Профиль", b"menu_profile"), Button.inline("💳 Баланс", b"menu_balance")],
        [Button.inline("📖 Инструкции", b"menu_instructions"), Button.inline("📥 Скачать", b"menu_download")],
        [Button.inline("💼 Партнерка", b"menu_referral"), Button.inline("❓ FAQ", b"menu_faq")],
        [Button.inline("💬 Поддержка", b"menu_support")],
    ]

def get_tariffs_keyboard() -> list:
    """Клавиатура тарифов с маркетинговыми акцентами"""
    return [
        [Button.inline("💎 1 Месяц — 150 ₽", b"pay_1")],
        [Button.inline("⭐️ 3 Месяца — 400 ₽ (Выгода 12%)", b"pay_3")],
        [Button.inline("🔥 6 Месяцев — 750 ₽ (Выгода 20%)", b"pay_6")],
        [Button.inline("◀️ Назад в меню", b"menu_main")],
    ]

def get_payment_methods_keyboard(amount: int, months: int):
    """Выбор способа оплаты"""
    return [
        [Button.inline(f"💳 Оплатить {amount}₽ через CryptoBot", f"pay_crypto_{months}_{amount}".encode())],
        [Button.inline("⭐ Telegram Stars (Soon)", b"pay_stars_soon")],
        [Button.inline("◀️ Назад к тарифам", b"menu_tariffs")],
    ]

def get_after_purchase_keyboard():
    """Кнопки после покупки для Onboarding"""
    return [
        [Button.inline("🔑 Получить ключ", b"get_my_key")],
        [Button.inline("📱 Как настроить?", b"menu_instructions")],
        [Button.inline("🏠 В главное меню", b"menu_main")],
    ]

# (Остальные функции оставляем или оптимизируем по мере надобности)
def get_back_keyboard(main: bool = False) -> list:
    if main: return [[Button.inline("🏠 Главное меню", b"menu_main")]]
    return [[Button.inline("◀️ Назад", b"menu_back")]]

def get_balance_keyboard() -> list:
    return [
        [Button.inline("💰 Пополнить через CryptoBot", b"refill_crypto")],
        [Button.inline("◀️ Назад", b"menu_back")],
    ]

def get_support_keyboard() -> list:
    return [
        [Button.inline("❓ FAQ", b"menu_faq")],
        [Button.inline("✍️ Написать оператору", b"support_write")],
        [Button.inline("◀️ Назад", b"menu_main")],
    ]

def get_instructions_text() -> str:
    return """
📖 **ИНСТРУКЦИИ И НАСТРОЙКА**

Мы используем протокол **VLESS + Reality**. 
Это самая современная технология, которую невозможно заблокировать.

**Всего 3 шага:**
1. Скачай приложение под своё устройство.
2. Скопируй ключ из раздела "Профиль" или после оплаты.
3. Вставь ключ в приложение и нажми "Подключиться".

━━━━━━━━━━━━━━━━━━━━
👇 **Выбери свою платформу для деталей:**
"""

def get_platform_keyboard() -> list:
    return [
        [Button.inline("🤖 Android", b"instr_android"), Button.inline("🍏 iOS", b"instr_ios")],
        [Button.inline("💻 Windows", b"instr_windows"), Button.inline("🍎 macOS", b"instr_macos")],
        [Button.inline("◀️ Назад", b"menu_main")],
    ]

def get_instruction_platform_text(platform: str) -> str:
    # Оставляем существующие тексты инструкций, они хорошие
    from brains.vpn_ui import get_instruction_platform_text as original_text
    return original_text(platform)
