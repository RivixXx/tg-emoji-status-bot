"""
VPN Shop UI — Inline кнопки и тексты
"""
from datetime import datetime
from telethon import Button


# ========== INLINE КНОПКИ ==========
def inline_main_menu():
    return [
        [Button.inline("💎 Тарифы", b"shop_tariffs"), Button.inline("🎁 Тест", b"trial_activate")],
        [Button.inline("👤 Профиль", b"profile_menu"), Button.inline("📖 Инструкции", b"instructions_menu")],
        [Button.inline("💬 Поддержка", b"support_menu"), Button.inline("❓ FAQ", b"faq_menu")]
    ]


def inline_back():
    return [[Button.inline("◀️ Назад", b"main_menu")]]


def inline_tariffs():
    return [
        [Button.inline("1 мес — 150₽", b"tariff_1"), Button.inline("3 мес — 400₽", b"tariff_3")],
        [Button.inline("6 мес — 750₽", b"tariff_6")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]


def inline_profile(has_keys=False):
    buttons = [
        [Button.inline("🔑 Ключи", b"my_keys"), Button.inline("💳 Баланс", b"balance")],
        [Button.inline("📜 История", b"history")]
    ]
    if has_keys:
        buttons.insert(0, [Button.inline("⚡ Продлить", b"shop_tariffs")])
    buttons.append([Button.inline("◀️ Назад", b"main_menu")])
    return buttons


def inline_instructions():
    return [
        [Button.inline("📱 iOS", b"instr_ios"), Button.inline("🤖 Android", b"instr_android")],
        [Button.inline("💻 Windows", b"instr_windows"), Button.inline("🍎 macOS", b"instr_macos")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]


def inline_support():
    return [
        [Button.inline("✍️ Задать вопрос", b"support_ask")],
        [Button.inline("❓ FAQ", b"faq_menu")],
        [Button.inline("◀️ Назад", b"main_menu")]
    ]


# ========== ТЕКСТЫ ==========
def text_welcome(user_id):
    return f"""╔═══════════════════════╗
║     🌌  **KARINA VPN**  🌌     ║
╚═══════════════════════╝

👤 **Абонент:** `{user_id}`
🔐 **Статус:** `Активен`

Добро пожаловать в Karina VPN Shop.

Выберите раздел:"""


def text_profile(user_id, user_data):
    keys_count = len(user_data.get("keys", []))
    return f"""╔═══════════════════════╗
║       👤  **ПРОФИЛЬ**  👤      ║
╚═══════════════════════╝

🆔 **ID:** `{user_id}`
💳 **Баланс:** `{user_data.get('balance', 0)}₽`
🎁 **Тест:** `{'Использован' if user_data.get('trial_used') else 'Доступен'}`
📅 **В сервисе:** `{user_data.get('joined', datetime.now()).strftime('%d.%m.%Y')}`

🔑 **Ключи:** `{keys_count}`"""


def text_tariffs():
    return """╔═══════════════════════╗
║        💎  **ТАРИФЫ**  💎      ║
╚═══════════════════════╝

**1 месяц — 150₽**
• 3 ключа
• Безлимитный трафик

**3 месяца — 400₽** (выгода 50₽)

**6 месяцев — 750₽** (выгода 150₽)"""


def text_payment(amount, months):
    return f"""╔═══════════════════════╗
║      💳  **ОПЛАТА**  💳        ║
╚═══════════════════════╝

💰 **Сумма:** `{amount}₽`
📅 **Период:** `{months} мес.`

💳 **Тестовый режим:**
Ключ будет выдан сразу."""


def text_keys(keys):
    if not keys:
        return "📭 У вас пока нет ключей."
    
    text = """╔═══════════════════════╗
║     🔑  **ВАШИ КЛЮЧИ**  🔑     ║
╚═══════════════════════╝

"""
    for i, key in enumerate(keys, 1):
        device = key.get("device", "Устройство")
        expire = key.get("expire", datetime.now()).strftime('%d.%m.%Y')
        key_short = key.get("key", "N/A")[:50] + "..."
        text += f"**{i}. {device}** (до {expire})\n`{key_short}`\n\n"
    
    return text


def text_instruction(platform):
    instructions = {
        "ios": "📱 **iOS:**\n1. Скачайте V2RayX\n2. Нажмите + → Import\n3. Вставьте ключ",
        "android": "🤖 **Android:**\n1. Скачайте V2RayNG\n2. Нажмите + → Import\n3. Вставьте ключ",
        "windows": "💻 **Windows:**\n1. Скачайте v2rayN\n2. Import → Вставьте ключ",
        "macos": "🍎 **macOS:**\nСкоро будет доступно"
    }
    return instructions.get(platform, "📖 Инструкция в разработке")
