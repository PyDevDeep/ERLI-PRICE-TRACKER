LEXICON: dict[str, dict[str, str]] = {
    "uk": {
        # Команди та загальний UI
        "start": (
            "👋 Привіт! Я ERLI.PL Price Tracker Bot.\n\n"
            "Я допоможу тобі автоматично відстежувати знижки на товари.\n\n"
            "Доступні команди:\n"
            "🔹 /add — Додати новий товар\n"
            "🔹 /list — Список моїх товарів\n"
            "🔹 /help — Довідка"
        ),
        "help": (
            "💡 <b>Довідка:</b>\n\n"
            "Відправ мені посилання на товар з erli.pl через команду /add, "
            "і я буду перевіряти його ціну кожні кілька годин.\n\n"
            "<b>Команди:</b>\n"
            "/add — Додати товар (бот запитає посилання)\n"
            "/list — Переглянути всі товари та їхні останні ціни\n"
            "/history &lt;ID&gt; — Переглянути історію цін конкретного товару\n"
            "/delete &lt;ID&gt; — Видалити товар"
        ),
        "fallback": "Я не розумію цю команду. Натисни /help для довідки.",
        "ask_url": "🔗 Відправ мені валідне посилання на товар з erli.pl:",
        "invalid_url": "❌ Некоректне посилання. Спробуй ще раз (має починатися з https://erli.pl/produkt/):",
        "added_success": "✅ Товар успішно додано до відстеження!",
        "already_exists": "ℹ️ Цей товар уже є у твоєму списку.",
        "cancel": "🚫 Дію скасовано.",
        "btn_cancel": "❌ Скасувати",
        # Сповіщення (Alerts)
        "alert_title": "🔔 <b>Зміна ціни:</b> {product_name}",
        "price_drop": "📉 {old_price} zł → {new_price} zł (⬇️ {delta_percent}%)",
        "price_rise": "📈 {old_price} zł → {new_price} zł (⬆️ {delta_percent}%)",
        "alert_link": "🔗 <a href='{url}'>Переглянути на Erli.pl</a>",
    },
    "en": {
        # Commands and general UI
        "start": (
            "👋 Hi! I'm ERLI.PL Price Tracker Bot.\n\n"
            "I will help you automatically track price drops for products.\n\n"
            "Available commands:\n"
            "🔹 /add — Add new product\n"
            "🔹 /list — My product list\n"
            "🔹 /help — Help"
        ),
        "help": (
            "💡 <b>Help:</b>\n\n"
            "Send me a link to a product from erli.pl using the /add command, "
            "and I will check its price every few hours.\n\n"
            "<b>Commands:</b>\n"
            "/add — Add product (the bot will ask for a link)\n"
            "/list — View all products and their latest prices\n"
            "/history &lt;ID&gt; — View price history of a specific product\n"
            "/delete &lt;ID&gt; — Delete product"
        ),
        "fallback": "I don't understand this command. Press /help for assistance.",
        "ask_url": "🔗 Please send me a valid product link from erli.pl:",
        "invalid_url": "❌ Invalid link. Please try again (must start with https://erli.pl/produkt/):",
        "added_success": "✅ Product successfully added to tracking!",
        "already_exists": "ℹ️ This product is already in your list.",
        "cancel": "🚫 Action cancelled.",
        "btn_cancel": "❌ Cancel",
        # Alerts
        "alert_title": "🔔 <b>Price Alert:</b> {product_name}",
        "price_drop": "📉 {old_price} zł → {new_price} zł (⬇️ {delta_percent}%)",
        "price_rise": "📈 {old_price} zł → {new_price} zł (⬆️ {delta_percent}%)",
        "alert_link": "🔗 <a href='{url}'>View on Erli.pl</a>",
    },
}

ALERTS: dict[str, dict[str, str]] = {
    "uk": {
        "title": "🔔 <b>Зміна ціни:</b> {product_name}",
        "price_drop": "📉 {old_price} zł → {new_price} zł (⬇️ {delta_percent}%)",
        "price_rise": "📈 {old_price} zł → {new_price} zł (⬆️ {delta_percent}%)",
        "link": "🔗 <a href='{url}'>Переглянути на Erli.pl</a>",
    },
    "en": {
        "title": "🔔 <b>Price Alert:</b> {product_name}",
        "price_drop": "📉 {old_price} zł → {new_price} zł (⬇️ {delta_percent}%)",
        "price_rise": "📈 {old_price} zł → {new_price} zł (⬆️ {delta_percent}%)",
        "link": "🔗 <a href='{url}'>View on Erli.pl</a>",
    },
}
