import logging
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from parser import parse_all_sources
from utils import clean_html, escape_markdown

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

events_cache = []

# Словари для отображения
EVENT_TYPES = {
    'conference': 'Конференция',
    'hackathon': 'Хакатон',
    'olympiad': 'Олимпиада',
    'contest': 'Соревнование'
}

THEMES = {
    'ai_ml': 'AI/ML',
    'security': 'ИБ',
    'robotics': 'Робототехника',
    'bigdata': 'Big Data',
    'devops': 'DevOps'
}

CITIES = {
    'moscow': 'Москва',
    'spb': 'Санкт-Петербург',
    'online': 'Онлайн',
    'all': 'Все города'
}

def format_event(event: dict) -> str:
    name = event.get("name", "Без названия")
    date = event.get("date", "Дата не указана")
    location = event.get("location", "Место не указано")
    desc = clean_html(event.get("description", ""))
    url = event.get("url", "")
    source_url = event.get("source_url", "")

    name_esc = escape_markdown(name)
    date_esc = escape_markdown(date)
    location_esc = escape_markdown(location)
    desc_esc = escape_markdown(desc)

    msg = f"*{name_esc}*\n\n"
    msg += f"📅 *Дата:* {date_esc}\n"
    msg += f"📍 *Место:* {location_esc}\n"
    if desc_esc:
        msg += f"📝 *Описание:* {desc_esc}\n"

    if url:
        msg += f"\n🔗 [Подробнее]({url})"
    elif source_url:
        msg += f"\n🔗 [Источник]({source_url})"

    return msg

def filter_events(events, filters):
    """Фильтрует события по выбранным критериям."""
    selected_types = filters.get('types', [])
    selected_themes = filters.get('themes', [])
    selected_city = filters.get('city', 'all')

    filtered = []
    for ev in events:
        # Фильтр по типу
        if selected_types:
            ev_type = ev.get('type', '').lower()
            if ev_type not in selected_types:
                continue
        # Фильтр по городу
        if selected_city != 'all':
            location = ev.get('location', '').lower()
            city_map = {'moscow': 'москва', 'spb': 'санкт-петербург', 'online': 'онлайн'}
            expected = city_map.get(selected_city, '')
            if expected not in location:
                continue
        # Фильтр по тематике (проверяем в названии и описании)
        if selected_themes:
            text = (ev.get('name', '') + ' ' + ev.get('description', '')).lower()
            theme_keywords = {
                'ai_ml': ['ai', 'ml', 'ии', 'нейросеть', 'машинное обучение', 'искусственный интеллект'],
                'security': ['безопасность', 'security', 'ib', 'инфобез', 'защита'],
                'robotics': ['робот', 'робототехника', 'robotics'],
                'bigdata': ['big data', 'большие данные', 'data science', 'аналитика'],
                'devops': ['devops', 'ci/cd', 'инфраструктура', 'контейнеризация']
            }
            matched = False
            for theme in selected_themes:
                keywords = theme_keywords.get(theme, [])
                if any(kw in text for kw in keywords):
                    matched = True
                    break
            if not matched:
                continue
        filtered.append(ev)
    return filtered

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение с постоянной клавиатурой."""
    # Создаём клавиатуру
    keyboard = [
        [KeyboardButton("📂 Тип"), KeyboardButton("🏷 Тематика"), KeyboardButton("🌍 Город")],
        [KeyboardButton("🔍 Показать события"), KeyboardButton("🔄 Обновить события")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Я бот для поиска IT-мероприятий.\n"
        "Используй кнопки ниже, чтобы настроить фильтры и показать события.",
        reply_markup=reply_markup
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия кнопок главной клавиатуры."""
    text = update.message.text
    if text == "📂 Тип":
        await show_type_menu(update, context)
    elif text == "🏷 Тематика":
        await show_theme_menu(update, context)
    elif text == "🌍 Город":
        await show_city_menu(update, context)
    elif text == "🔍 Показать события":
        await show_events(update, context)
    elif text == "🔄 Обновить события":
        await refresh_events(update, context)
    else:
        await update.message.reply_text("Используй кнопки.")

async def show_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инлайн-клавиатуру для выбора типов событий."""
    current = context.user_data.get('filter_types', [])
    keyboard = []
    for key, label in EVENT_TYPES.items():
        emoji = "✅" if key in current else "❌"
        keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"type_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    await update.message.reply_text(
        "Выберите типы мероприятий:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_theme_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инлайн-клавиатуру для выбора тематик."""
    current = context.user_data.get('filter_themes', [])
    keyboard = []
    for key, label in THEMES.items():
        emoji = "✅" if key in current else "❌"
        keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"theme_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    await update.message.reply_text(
        "Выберите тематики (ключевые слова будут искаться в названии и описании):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_city_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инлайн-клавиатуру для выбора города."""
    current = context.user_data.get('filter_city', 'all')
    keyboard = []
    for key, label in CITIES.items():
        emoji = "✅" if key == current else " "
        keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"city_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    await update.message.reply_text(
        "Выберите город:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор фильтров из инлайн-клавиатур."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("type_"):
        key = data[5:]
        current = context.user_data.get('filter_types', [])
        if key in current:
            current.remove(key)
        else:
            current.append(key)
        context.user_data['filter_types'] = current
        await query.edit_message_reply_markup(reply_markup=await build_type_markup(current))
    elif data.startswith("theme_"):
        key = data[6:]
        current = context.user_data.get('filter_themes', [])
        if key in current:
            current.remove(key)
        else:
            current.append(key)
        context.user_data['filter_themes'] = current
        await query.edit_message_reply_markup(reply_markup=await build_theme_markup(current))
    elif data.startswith("city_"):
        key = data[5:]
        context.user_data['filter_city'] = key
        await query.edit_message_reply_markup(reply_markup=await build_city_markup(key))
    elif data == "main_menu":
        await query.edit_message_text("Настройки сохранены. Используйте главную клавиатуру.")
    else:
        await query.edit_message_text("Неизвестная команда")

async def build_type_markup(selected):
    keyboard = []
    for key, label in EVENT_TYPES.items():
        emoji = "✅" if key in selected else "❌"
        keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"type_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def build_theme_markup(selected):
    keyboard = []
    for key, label in THEMES.items():
        emoji = "✅" if key in selected else "❌"
        keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"theme_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def build_city_markup(selected):
    keyboard = []
    for key, label in CITIES.items():
        emoji = "✅" if key == selected else " "
        keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"city_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def show_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает события с учётом текущих фильтров."""
    await update.message.reply_text("🔍 Загружаю события... Это может занять минуту.")

    global events_cache
    if not events_cache:
        try:
            events_cache = await parse_all_sources()
        except Exception as e:
            logger.error(f"Parse error: {e}")
            await update.message.reply_text("❌ Ошибка загрузки. Попробуйте позже.")
            return

    if not events_cache:
        await update.message.reply_text("😕 Мероприятия не найдены.")
        return

    # Собираем фильтры
    filters = {
        'types': context.user_data.get('filter_types', []),
        'themes': context.user_data.get('filter_themes', []),
        'city': context.user_data.get('filter_city', 'all')
    }
    filtered = filter_events(events_cache, filters)

    if not filtered:
        await update.message.reply_text(
            "😕 Нет мероприятий по выбранным фильтрам.\n"
            "Измените фильтры и попробуйте снова."
        )
        return

    context.user_data["filtered_events"] = filtered
    context.user_data["current_index"] = 0
    await send_event(update, context, chat_id=update.effective_chat.id)

async def send_event(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    events = context.user_data.get("filtered_events", [])
    idx = context.user_data.get("current_index", 0)

    if not events:
        await context.bot.send_message(chat_id=chat_id, text="😕 Мероприятия не найдены")
        return

    event = events[idx]
    text = format_event(event)

    keyboard = []
    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_event"))
    if idx < len(events) - 1:
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data="next_event"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение с событием, чтобы не путаться с редактированием
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)

async def nav_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    idx = context.user_data.get("current_index", 0)
    if action == "next_event":
        context.user_data["current_index"] = idx + 1
    elif action == "prev_event":
        context.user_data["current_index"] = idx - 1
    # Удаляем текущее сообщение и отправляем новое (чтобы избежать ошибок с редактированием)
    await query.message.delete()
    await send_event(update, context, chat_id=query.message.chat_id)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    # Возвращаем главное меню с клавиатурой
    keyboard = [
        [KeyboardButton("📂 Тип"), KeyboardButton("🏷 Тематика"), KeyboardButton("🌍 Город")],
        [KeyboardButton("🔍 Показать события"), KeyboardButton("🔄 Обновить события")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Главное меню:",
        reply_markup=reply_markup
    )

async def refresh_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global events_cache
    events_cache = []
    context.user_data["filtered_events"] = []
    await update.message.reply_text("🔄 Обновляю список...")
    try:
        events_cache = await parse_all_sources(force_refresh=True)
        if events_cache:
            await update.message.reply_text(f"✅ Найдено {len(events_cache)} событий.")
        else:
            await update.message.reply_text("😕 Новых событий не найдено.")
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        await update.message.reply_text("❌ Ошибка обновления.")

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern="^(type_|theme_|city_|main_menu)"))
    app.add_handler(CallbackQueryHandler(nav_events, pattern="^(next_event|prev_event)$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))

    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()