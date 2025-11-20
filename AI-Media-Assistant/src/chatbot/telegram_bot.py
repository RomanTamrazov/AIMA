import json
import os
import sys
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# Добавляем путь для импорта из корня
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import config
from src.parsers.event_parser import EventParser
from src.analysis.criteria_filter import CriteriaFilter
from src.calendar_integration.ics_calendar import SimpleICSCalendar  # ⬅️ ИЗМЕНЕНО

class TelegramBot:
    """Telegram бот для взаимодействия с пользователем"""
    
    def __init__(self):
        self.token = config.BOT_CONFIG["token"]
        self.parser = EventParser()
        self.filter = CriteriaFilter()
        self.calendar = SimpleICSCalendar()  # ⬅️ ИЗМЕНЕНО
        self.application = None
        self.user_events = {}
        self.user_favorites = {}
        self.user_settings = {}
        self.user_context = {}# Контекст для отслеживания текущего действия
    
    def _get_user_settings(self, user_id):
        """Получает настройки пользователя"""
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {
                'location': 'Санкт-Петербург',
                'min_audience': 50,
                'themes': ['AI', 'цифровая трансформация', 'образование'],
                'event_types': ['конференция', 'митап', 'хакатон', 'стратегическая сессия'],
                'notifications': True,
                'notification_time': '09:00'
            }
        return self.user_settings[user_id]
    
    def _set_user_context(self, user_id, context):
        """Устанавливает контекст для пользователя"""
        self.user_context[user_id] = context
    
    def _get_user_context(self, user_id):
        """Получает контекст пользователя"""
        return self.user_context.get(user_id, 'main_menu')
    
    async def start(self, update: Update, context: CallbackContext):
        """Обработчик команды /start"""
        user = update.effective_user
        self._set_user_context(user.id, 'main_menu')
        
        # Создаем главную клавиатуру
        main_keyboard = [
            [KeyboardButton("🎯 Рекомендованные мероприятия")],
            [KeyboardButton("🔍 Найти мероприятия"), KeyboardButton("⭐ Избранное")],
            [KeyboardButton("⚙️ Настройки"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        welcome_text = f"""
🤖 Привет, {user.first_name}!

Я - AI-помощник по медиа от Центра исследований и разработки Сбера.

🎯 <b>Мои возможности:</b>
• Найти подходящие IT-мероприятия в Санкт-Петербурге
• Рекомендовать мероприятия по вашим критериям
• Добавлять мероприятия в календарь и избранное
• Показывать статистику и аналитику

Выбери действие ниже или используй команды:
/events - рекомендованные мероприятия
/find - найти мероприятия
/favorites - избранное
/settings - настройки критериев
/stats - статистика
/help - помощь
        """
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def show_events(self, update: Update, context: CallbackContext):
        """Показывает рекомендованные мероприятия"""
        await update.message.reply_text("🔍 Ищу подходящие мероприятия...")
        
        user_id = update.effective_user.id
        user_settings = self._get_user_settings(user_id)
        
        # Обновляем критерии фильтрации
        self.filter.criteria = {
            "min_audience": user_settings['min_audience'],
            "target_audience": ["IT-специалисты", "Исследователи", "Студенты"],
            "speaker_level": ["ТОП-спикеры", "Вице-губернаторы"],
            "event_types": user_settings['event_types'],
            "priority_themes": user_settings['themes'],
            "location": user_settings['location']
        }
        
        # Получаем и фильтруем мероприятия
        events = self.parser.load_events()
        if not events:
            events = self.parser.parse_events()
        
        filtered_events = self.filter.filter_events(events)
        
        if not filtered_events:
            await update.message.reply_text("❌ Не найдено подходящих мероприятий")
            return
        
        # Сохраняем события для пользователя
        self.user_events[user_id] = filtered_events[:15]
        
        # Показываем первое мероприятие с инлайн-клавиатурой
        await self._show_event_page(update, context, user_id, 0)
    
    async def _show_event_page(self, update: Update, context: CallbackContext, user_id: int, page: int):
        """Показывает мероприятие с пагинацией"""
        events = self.user_events.get(user_id, [])
        
        if not events:
            await update.message.reply_text("❌ Нет доступных мероприятий")
            return
        
        if page >= len(events):
            page = 0
        
        event = events[page]
        event_text = self._format_event_message(event, page + 1)
        
        # Проверяем, есть ли мероприятие в избранном
        is_favorite = False
        if user_id in self.user_favorites:
            favorite_titles = [e['title'] for e in self.user_favorites[user_id]]
            is_favorite = event['title'] in favorite_titles
        
        # Создаем инлайн-клавиатуру
        keyboard = []
        
        # Кнопки действий
        favorite_text = "❌ Удалить из избранного" if is_favorite else "⭐ В избранное"
        action_buttons = [
            InlineKeyboardButton("📅 Добавить в календарь", callback_data=f"add_{page}"),
            InlineKeyboardButton(favorite_text, callback_data=f"fav_{page}"),
        ]
        
        if event.get('url'):
            action_buttons.append(InlineKeyboardButton("🔗 Сайт", url=event['url']))
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(f"{page+1}/{len(events)}", callback_data="info"))
        
        if page < len(events) - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page+1}"))
        
        keyboard.append(action_buttons)
        keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("🎯 Главное меню", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение
        if update.callback_query:
            await update.callback_query.edit_message_text(
                event_text, 
                reply_markup=reply_markup,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text(
                event_text, 
                reply_markup=reply_markup,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
    
    def _format_event_message(self, event, index):
        """Форматирует сообщение о мероприятии"""
        type_emojis = {
            'конференция': '🎤',
            'митап': '👥',
            'хакатон': '💻',
            'стратегическая сессия': '🎯',
            'круглый стол': '💬',
            'форум': '🏛️',
            'семинар': '📚',
            'default': '🎪'
        }
        
        event_type = event.get('type', 'default')
        emoji = type_emojis.get(event_type, type_emojis['default'])
        
        return f"""
<b>{index}. {emoji} {event['title']}</b>

📅 <b>Дата:</b> {event['date']}
📍 <b>Место:</b> {event.get('location', 'Не указано')}
👥 <b>Участники:</b> {event.get('audience', 'Не указано')}
🎪 <b>Тип:</b> {event_type}
⭐ <b>Приоритет:</b> {event.get('priority_score', 0)}/10

📝 <b>Описание:</b> {event.get('description', 'Нет описания')}
🎤 <b>Спикеры:</b> {', '.join(event.get('speakers', ['Не указаны']))}
📋 <b>Регистрация:</b> {event.get('registration_info', 'Не указана')}

🏷️ <b>Темы:</b> {', '.join(event.get('themes', []))}
        """
    
    async def handle_callback(self, update: Update, context: CallbackContext):
        """Обработчик callback-запросов от инлайн-клавиатур"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith('page_'):
            page = int(data.split('_')[1])
            await self._show_event_page(update, context, user_id, page)
        
        elif data.startswith('add_'):
            # Добавление в календарь через .ics файл
            page = int(data.split('_')[1])
            events = self.user_events.get(user_id, [])
            if events and page < len(events):
                event = events[page]
                
                await query.answer("📅 Создаем файл для календаря...")
                
                # Создаем .ics файл
                result = self.calendar.add_event_to_calendar(event, user_id)
                
                if result['success']:
                    # Отправляем .ics файл
                    try:
                        with open(result['filepath'], 'rb') as ics_file:
                            await context.bot.send_document(
                                chat_id=query.message.chat_id,
                                document=ics_file,
                                filename=result['filename'],
                                caption=result['message'],
                                parse_mode='HTML'
                            )
                        
                        # Обновляем оригинальное сообщение
                        keyboard = [
                            [InlineKeyboardButton("🎯 Следующее мероприятие", callback_data=f"page_{page}")],
                            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_text(
                            f"✅ <b>Файл отправлен!</b>\n\n"
                            f"<b>{event['title']}</b>\n"
                            f"📅 {event['date']}\n"
                            f"📍 {event.get('location', 'Не указано')}\n\n"
                            f"<i>Проверьте следующее сообщение с файлом 📎</i>",
                            reply_markup=reply_markup,
                            parse_mode='HTML'
                        )
                        
                    except Exception as e:
                        print(f"❌ Ошибка отправки .ics файла: {e}")
                        await query.edit_message_text(
                            "❌ Ошибка отправки файла. Попробуйте еще раз.",
                            parse_mode='HTML'
                        )
                
                else:
                    await query.edit_message_text(
                        f"❌ {result['message']}\n\n"
                        f"<b>{event['title']}</b>\n"
                        f"📅 {event['date']}\n"
                        f"📍 {event.get('location', 'Не указано')}",
                        parse_mode='HTML'
                    )
    
    async def _show_main_menu(self, update: Update, context: CallbackContext):
        """Показывает главное меню"""
        main_keyboard = [
            [KeyboardButton("🎯 Рекомендованные мероприятия")],
            [KeyboardButton("🔍 Найти мероприятия"), KeyboardButton("⭐ Избранное")],
            [KeyboardButton("⚙️ Настройки"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def find_events(self, update: Update, context: CallbackContext):
        """Поиск мероприятий по критериям"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_menu')
        
        search_keyboard = [
            [KeyboardButton("🔍 По тематике"), KeyboardButton("📅 По дате")],
            [KeyboardButton("👥 По аудитории"), KeyboardButton("🎪 По типу")],
            [KeyboardButton("📍 По локации"), KeyboardButton("🎯 Рекомендованные")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(search_keyboard, resize_keyboard=True)
        
        text = """
🔍 <b>Поиск мероприятий</b>

Выберите критерий поиска:
• <b>По тематике</b> - AI, Data Science, разработка и т.д.
• <b>По дате</b> - ближайшие мероприятия
• <b>По аудитории</b> - размер мероприятия  
• <b>По типу</b> - конференции, митапы, хакатоны
• <b>По локации</b> - изменить город/район
• <b>Рекомендованные</b> - лучшие предложения

Выберите параметр для поиска:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def handle_search_menu(self, update: Update, context: CallbackContext):
        """Обработчик меню поиска"""
        text = update.message.text
        user_id = update.effective_user.id
        
        if text == "🔍 По тематике":
            await self._show_search_themes(update, context)
        
        elif text == "📅 По дате":
            await self._show_search_by_date(update, context)
        
        elif text == "👥 По аудитории":
            await self._show_search_by_audience(update, context)
        
        elif text == "🎪 По типу":
            await self._show_search_by_type(update, context)
        
        elif text == "📍 По локации":
            await self._show_search_by_location(update, context)
        
        elif text == "🎯 Рекомендованные":
            await self.show_events(update, context)
        
        elif text == "🏠 Главное меню":
            self._set_user_context(user_id, 'main_menu')
            await self._show_main_menu(update, context)
        
        else:
            await update.message.reply_text("Используйте кнопки поиска или вернитесь в главное меню")
    
    async def _show_search_themes(self, update: Update, context: CallbackContext):
        """Поиск по тематике"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_themes')
        
        themes_keyboard = [
            [KeyboardButton("🤖 AI и Машинное обучение"), KeyboardButton("📊 Data Science")],
            [KeyboardButton("💻 Разработка и Программирование"), KeyboardButton("🔐 Кибербезопасность")],
            [KeyboardButton("🌐 Цифровая трансформация"), KeyboardButton("🎓 Образование и Наука")],
            [KeyboardButton("🚀 Стартапы и Инновации"), KeyboardButton("📈 Бизнес и Экономика")],
            [KeyboardButton("🎯 Все темы"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(themes_keyboard, resize_keyboard=True)
        
        text = """
🔍 <b>Поиск по тематике</b>

Выберите интересующую тематику:
• <b>AI и Машинное обучение</b> - нейросети, искусственный интеллект
• <b>Data Science</b> - анализ данных, большие данные
• <b>Разработка и Программирование</b> - IT, программирование
• <b>Кибербезопасность</b> - защита данных, безопасность
• <b>Цифровая трансформация</b> - digital, инновации
• <b>Образование и Наука</b> - EdTech, исследования
• <b>Стартапы и Инновации</b> - венчурные инвестиции
• <b>Бизнес и Экономика</b> - предпринимательство
• <b>Все темы</b> - показать все мероприятия

Система найдет мероприятия по выбранной тематике.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_search_by_date(self, update: Update, context: CallbackContext):
        """Поиск по дате"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_date')
        
        date_keyboard = [
            [KeyboardButton("⏰ Сегодня"), KeyboardButton("📅 Завтра")],
            [KeyboardButton("🗓️ На этой неделе"), KeyboardButton("📆 В этом месяце")],
            [KeyboardButton("🔮 Будущие мероприятия"), KeyboardButton("📋 Все даты")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(date_keyboard, resize_keyboard=True)
        
        today = datetime.now().strftime("%d.%m.%Y")
        
        text = f"""
📅 <b>Поиск по дате</b>

Сегодня: {today}

Выберите период поиска:
• <b>Сегодня</b> - мероприятия на сегодня
• <b>Завтра</b> - мероприятия на завтра
• <b>На этой неделе</b> - ближайшие 7 дней
• <b>В этом месяце</b> - мероприятия текущего месяца
• <b>Будущие мероприятия</b> - все предстоящие события
• <b>Все даты</b> - показать все мероприятия

Система отфильтрует мероприятия по выбранному периоду.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_search_by_audience(self, update: Update, context: CallbackContext):
        """Поиск по аудитории"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_audience')
        
        audience_keyboard = [
            [KeyboardButton("👤 Камерные (1-50)"), KeyboardButton("👥 Средние (50-200)")],
            [KeyboardButton("👨‍👩‍👧‍👦 Крупные (200-500)"), KeyboardButton("🏛️ Массовые (500+)")],
            [KeyboardButton("🌟 Любого размера"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(audience_keyboard, resize_keyboard=True)
        
        text = """
👥 <b>Поиск по размеру аудитории</b>

Выберите предпочтительный размер мероприятия:
• <b>Камерные (1-50)</b> - небольшие встречи, воркшопы
• <b>Средние (50-200)</b> - митапы, семинары, круглые столы
• <b>Крупные (200-500)</b> - конференции, форумы
• <b>Массовые (500+)</b> - масштабные события, выставки
• <b>Любого размера</b> - все мероприятия

Система найдет мероприятия соответствующего масштаба.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_search_by_type(self, update: Update, context: CallbackContext):
        """Поиск по типу мероприятия"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_type')
        
        type_keyboard = [
            [KeyboardButton("🎤 Конференции"), KeyboardButton("👥 Митапы")],
            [KeyboardButton("💻 Хакатоны"), KeyboardButton("🎯 Стратегические сессии")],
            [KeyboardButton("💬 Круглые столы"), KeyboardButton("📚 Семинары и Лекции")],
            [KeyboardButton("🏛️ Форум"), KeyboardButton("🚀 Стартап-ивенты")],
            [KeyboardButton("🎪 Все типы"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(type_keyboard, resize_keyboard=True)
        
        text = """
🎪 <b>Поиск по типу мероприятия</b>

Выберите тип мероприятия:
• <b>Конференции</b> - масштабные отраслевые события
• <b>Митапы</b> - встречи сообществ, нетворкинг
• <b>Хакатоны</b> - соревнования, практические сессии
• <b>Стратегические сессии</b> - обсуждения, планирование
• <b>Круглые столы</b> - экспертные дискуссии
• <b>Семинары и Лекции</b> - образовательные мероприятия
• <b>Форум</b> - площадки для обсуждения
• <b>Стартап-ивенты</b> - презентации, питчи
• <b>Все типы</b> - показать все мероприятия

Система найдет мероприятия выбранного формата.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_search_by_location(self, update: Update, context: CallbackContext):
        """Поиск по локации"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_location')
        
        location_keyboard = [
            [KeyboardButton("📍 Центр СПб"), KeyboardButton("📍 Василеостровский")],
            [KeyboardButton("📍 Петроградский"), KeyboardButton("📍 Выборгский")],
            [KeyboardButton("📍 Калининский"), KeyboardButton("📍 Невский")],
            [KeyboardButton("📍 Онлайн"), KeyboardButton("📍 Весь СПб")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, resize_keyboard=True)
        
        text = """
📍 <b>Поиск по локации</b>

Выберите район или тип мероприятия:
• <b>Центр СПб</b> - исторический центр города
• <b>Василеостровский</b> - район с вузами и бизнес-центрами
• <b>Петроградский</b> - престижный район
• <b>Выборгский</b> - промышленный и бизнес-район
• <b>Калининский</b> - густонаселенный район
• <b>Невский</b> - крупный административный район
• <b>Онлайн</b> - дистанционные мероприятия
• <b>Весь СПб</b> - все локации города

Система найдет мероприятия в выбранной локации.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def handle_search_selection(self, update: Update, context: CallbackContext):
        """Обработка выбора критериев поиска"""
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        settings = self._get_user_settings(user_id)
        
        # Временные настройки для поиска (не сохраняются в основных настройках)
        temp_settings = settings.copy()
        
        # Поиск по тематике
        if current_context == 'search_themes':
            theme_map = {
                "🤖 AI и Машинное обучение": ['AI', 'искусственный интеллект', 'машинное обучение', 'нейросети'],
                "📊 Data Science": ['Data Science', 'аналитика', 'большие данные', 'ML'],
                "💻 Разработка и Программирование": ['разработка', 'программирование', 'IT', 'DevOps', 'Cloud'],
                "🔐 Кибербезопасность": ['кибербезопасность', 'безопасность', 'защита данных'],
                "🌐 Цифровая трансформация": ['цифровая трансформация', 'digital', 'инновации'],
                "🎓 Образование и Наука": ['образование', 'наука', 'исследования', 'EdTech'],
                "🚀 Стартапы и Инновации": ['стартапы', 'инновации', 'венчурные инвестиции'],
                "📈 Бизнес и Экономика": ['бизнес', 'экономика', 'предпринимательство']
            }
            
            if text in theme_map:
                temp_settings['themes'] = theme_map[text]
                await update.message.reply_text(f"🔍 Ищу мероприятия по теме: {text}")
                await self._show_search_results(update, context, temp_settings)
            elif text == "🎯 Все темы":
                temp_settings['themes'] = []  # Пустой список = все темы
                await update.message.reply_text("🔍 Показываю все мероприятия")
                await self._show_search_results(update, context, temp_settings)
        
        # Поиск по дате
        elif current_context == 'search_date':
            today = datetime.now()
            
            if text == "⏰ Сегодня":
                await update.message.reply_text("📅 Ищу мероприятия на сегодня")
                # Здесь будет логика фильтрации по дате
                await self._show_search_results(update, context, temp_settings)
            
            elif text == "📅 Завтра":
                await update.message.reply_text("📅 Ищу мероприятия на завтра")
                await self._show_search_results(update, context, temp_settings)
            
            elif text == "🗓️ На этой неделе":
                await update.message.reply_text("📅 Ищу мероприятия на этой неделе")
                await self._show_search_results(update, context, temp_settings)
            
            elif text == "📆 В этом месяце":
                await update.message.reply_text("📅 Ищу мероприятия в этом месяце")
                await self._show_search_results(update, context, temp_settings)
            
            elif text == "🔮 Будущие мероприятия":
                await update.message.reply_text("📅 Ищу все будущие мероприятия")
                await self._show_search_results(update, context, temp_settings)
            
            elif text == "📋 Все даты":
                await update.message.reply_text("📅 Показываю все мероприятия")
                await self._show_search_results(update, context, temp_settings)
        
        # Поиск по аудитории
        elif current_context == 'search_audience':
            audience_map = {
                "👤 Камерные (1-50)": 10,
                "👥 Средние (50-200)": 50,
                "👨‍👩‍👧‍👦 Крупные (200-500)": 200,
                "🏛️ Массовые (500+)": 500,
                "🌟 Любого размера": 0
            }
            
            if text in audience_map:
                temp_settings['min_audience'] = audience_map[text]
                await update.message.reply_text(f"👥 Ищу мероприятия: {text}")
                await self._show_search_results(update, context, temp_settings)
        
        # Поиск по типу
        elif current_context == 'search_type':
            type_map = {
                "🎤 Конференции": ['конференция', 'форум'],
                "👥 Митапы": ['митап'],
                "💻 Хакатоны": ['хакатон'],
                "🎯 Стратегические сессии": ['стратегическая сессия'],
                "💬 Круглые столы": ['круглый стол'],
                "📚 Семинары и Лекции": ['семинар', 'лекция', 'образовательный семинар'],
                "🏛️ Форум": ['форум'],
                "🚀 Стартап-ивенты": ['стартап-конференция', 'стартап']
            }
            
            if text in type_map:
                temp_settings['event_types'] = type_map[text]
                await update.message.reply_text(f"🎪 Ищу мероприятия: {text}")
                await self._show_search_results(update, context, temp_settings)
            elif text == "🎪 Все типы":
                temp_settings['event_types'] = []  # Пустой список = все типы
                await update.message.reply_text("🎪 Показываю все типы мероприятий")
                await self._show_search_results(update, context, temp_settings)
        
        # Поиск по локации
        elif current_context == 'search_location':
            location_map = {
                "📍 Центр СПб": "центр",
                "📍 Василеостровский": "Василеостровский",
                "📍 Петроградский": "Петроградский", 
                "📍 Выборгский": "Выборгский",
                "📍 Калининский": "Калининский",
                "📍 Невский": "Невский",
                "📍 Онлайн": "Онлайн",
                "📍 Весь СПб": "Санкт-Петербург"
            }
            
            if text in location_map:
                temp_settings['location'] = location_map[text]
                await update.message.reply_text(f"📍 Ищу мероприятия: {text}")
                await self._show_search_results(update, context, temp_settings)
        
        # Возврат в главное меню
        if text == "🏠 Главное меню":
            self._set_user_context(user_id, 'main_menu')
            await self._show_main_menu(update, context)
    
    async def _show_search_results(self, update: Update, context: CallbackContext, search_settings):
        """Показывает результаты поиска"""
        user_id = update.effective_user.id
        
        # Обновляем критерии фильтрации для поиска
        self.filter.criteria = {
            "min_audience": search_settings.get('min_audience', 0),
            "target_audience": ["IT-специалисты", "Исследователи", "Студенты"],
            "speaker_level": ["ТОП-спикеры", "Вице-губернаторы"],
            "event_types": search_settings.get('event_types', []),
            "priority_themes": search_settings.get('themes', []),
            "location": search_settings.get('location', 'Санкт-Петербург')
        }
        
        # Получаем и фильтруем мероприятия
        events = self.parser.load_events()
        if not events:
            events = self.parser.parse_events()
        
        filtered_events = self.filter.filter_events(events)
        
        if not filtered_events:
            await update.message.reply_text("❌ По вашему запросу ничего не найдено")
            return
        
        # Сохраняем события для пользователя
        self.user_events[user_id] = filtered_events[:15]
        
        # Показываем первое мероприятие
        await self._show_event_page(update, context, user_id, 0)
    
    async def show_favorites(self, update: Update, context: CallbackContext):
        """Показывает избранные мероприятия"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_favorites or not self.user_favorites[user_id]:
            await update.message.reply_text("⭐ У вас пока нет избранных мероприятий")
            return
        
        self.user_events[user_id] = self.user_favorites[user_id]
        await self._show_event_page(update, context, user_id, 0)
    
    async def show_settings(self, update: Update, context: CallbackContext):
        """Настройки критериев"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'settings_menu')
        settings = self._get_user_settings(user_id)
        
        settings_keyboard = [
            [KeyboardButton("🎯 Изменить приоритеты"), KeyboardButton("📍 Изменить локацию")],
            [KeyboardButton("👥 Настройка аудитории"), KeyboardButton("🎪 Типы мероприятий")],
            [KeyboardButton("🔔 Уведомления"), KeyboardButton("📊 Сбросить настройки")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(settings_keyboard, resize_keyboard=True)
        
        text = f"""
⚙️ <b>Настройки</b>

Текущие критерии отбора:
• <b>Локация:</b> {settings['location']}
• <b>Мин. аудитория:</b> {settings['min_audience']} человек
• <b>Приоритетные темы:</b> {', '.join(settings['themes'])}
• <b>Типы мероприятий:</b> {', '.join(settings['event_types'])}
• <b>Уведомления:</b> {'✅ Включены' if settings['notifications'] else '❌ Выключены'}

Выберите параметр для изменения:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def handle_settings_menu(self, update: Update, context: CallbackContext):
        """Обработчик главного меню настроек"""
        text = update.message.text
        user_id = update.effective_user.id
        
        if text == "🎯 Изменить приоритеты":
            await self._show_themes_settings(update, context)
        
        elif text == "📍 Изменить локацию":
            await self._show_location_settings(update, context)
        
        elif text == "👥 Настройка аудитории":
            await self._show_audience_settings(update, context)
        
        elif text == "🎪 Типы мероприятий":
            await self._show_event_types_settings(update, context)
        
        elif text == "🔔 Уведомления":
            await self._show_notification_settings(update, context)
        
        elif text == "📊 Сбросить настройки":
            await self._reset_settings(update, context)
        
        elif text == "🏠 Главное меню":
            self._set_user_context(user_id, 'main_menu')
            await self._show_main_menu(update, context)
        
        else:
            await update.message.reply_text("Используйте кнопки настроек или вернитесь в главное меню")
    
    async def _show_themes_settings(self, update: Update, context: CallbackContext):
        """Настройка приоритетных тем"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'themes_settings')
        settings = self._get_user_settings(user_id)
        
        themes_keyboard = [
            [KeyboardButton("🤖 AI и ML"), KeyboardButton("📊 Data Science")],
            [KeyboardButton("💻 Разработка"), KeyboardButton("🔐 Кибербезопасность")],
            [KeyboardButton("🌐 Цифровая трансформация"), KeyboardButton("🎓 Образование")],
            [KeyboardButton("✅ Сохранить темы"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(themes_keyboard, resize_keyboard=True)
        
        text = f"""
🎯 <b>Настройка приоритетных тем</b>

Текущие темы: {', '.join(settings['themes'])}

Выберите темы для добавления:
• <b>AI и ML</b> - искусственный интеллект и машинное обучение
• <b>Data Science</b> - анализ данных и большие данные
• <b>Разработка</b> - программирование и IT
• <b>Кибербезопасность</b> - защита данных и безопасность
• <b>Цифровая трансформация</b> - digital и инновации
• <b>Образование</b> - EdTech и обучение

Нажмите <b>✅ Сохранить темы</b> когда закончите выбор.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_location_settings(self, update: Update, context: CallbackContext):
        """Настройка локации"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'location_settings')
        
        location_keyboard = [
            [KeyboardButton("📍 Санкт-Петербург"), KeyboardButton("📍 Москва")],
            [KeyboardButton("📍 Онлайн"), KeyboardButton("📍 Любая")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, resize_keyboard=True)
        
        text = """
📍 <b>Настройка локации</b>

Выберите предпочтительную локацию мероприятий:
• <b>Санкт-Петербург</b> - только мероприятия в СПб
• <b>Москва</b> - мероприятия в Москве
• <b>Онлайн</b> - онлайн мероприятия
• <b>Любая</b> - все локации

Текущая настройка будет применена к новым рекомендациям.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_audience_settings(self, update: Update, context: CallbackContext):
        """Настройка аудитории"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'audience_settings')
        
        audience_keyboard = [
            [KeyboardButton("👤 Маленькие (1-50)"), KeyboardButton("👥 Средние (50-200)")],
            [KeyboardButton("👨‍👩‍👧‍👦 Крупные (200+)"), KeyboardButton("🌟 Любые")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(audience_keyboard, resize_keyboard=True)
        
        text = """
👥 <b>Настройка размера аудитории</b>

Выберите предпочтительный размер мероприятий:
• <b>Маленькие</b> - камерные мероприятия до 50 человек
• <b>Средние</b> - мероприятия на 50-200 участников  
• <b>Крупные</b> - масштабные события от 200+ человек
• <b>Любые</b> - все размеры аудитории

Рекомендуем средние и крупные мероприятия для максимальной эффективности.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_event_types_settings(self, update: Update, context: CallbackContext):
        """Настройка типов мероприятий"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'event_types_settings')
        
        types_keyboard = [
            [KeyboardButton("🎤 Конференции"), KeyboardButton("👥 Митапы")],
            [KeyboardButton("💻 Хакатоны"), KeyboardButton("🎯 Страт. сессии")],
            [KeyboardButton("💬 Круглые столы"), KeyboardButton("📚 Семинары")],
            [KeyboardButton("✅ Сохранить типы"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(types_keyboard, resize_keyboard=True)
        
        text = """
🎪 <b>Настройка типов мероприятий</b>

Выберите предпочтительные типы мероприятий:
• <b>Конференции</b> - масштабные отраслевые события
• <b>Митапы</b> - встречи сообществ и нетворкинг
• <b>Хакатоны</b> - соревнования и практика
• <b>Страт. сессии</b> - стратегические обсуждения
• <b>Круглые столы</b> - экспертные дискуссии
• <b>Семинары</b> - образовательные мероприятия

Нажмите <b>✅ Сохранить типы</b> когда закончите выбор.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_notification_settings(self, update: Update, context: CallbackContext):
        """Настройка уведомлений"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'notification_settings')
        settings = self._get_user_settings(user_id)
        
        notification_keyboard = [
            [KeyboardButton("🔔 Включить уведомления"), KeyboardButton("🔕 Выключить уведомления")],
            [KeyboardButton("⏰ Время уведомлений"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(notification_keyboard, resize_keyboard=True)
        
        status = "✅ Включены" if settings['notifications'] else "❌ Выключены"
        
        text = f"""
🔔 <b>Настройка уведомлений</b>

Текущий статус: {status}
Время уведомлений: {settings['notification_time']}

Опции:
• <b>Включить уведомления</b> - получать уведомления о новых мероприятиях
• <b>Выключить уведомления</b> - отключить все уведомления
• <b>Время уведомлений</b> - настроить время ежедневных уведомлений

Уведомления включают: новые мероприятия, напоминания, рекомендации.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _reset_settings(self, update: Update, context: CallbackContext):
        """Сброс настроек к defaults"""
        user_id = update.effective_user.id
        self.user_settings[user_id] = {
            'location': 'Санкт-Петербург',
            'min_audience': 50,
            'themes': ['AI', 'цифровая трансформация', 'образование'],
            'event_types': ['конференция', 'митап', 'хакатон', 'стратегическая сессия'],
            'notifications': True,
            'notification_time': '09:00'
        }
        
        text = """
🔄 <b>Настройки сброшены!</b>

Восстановлены настройки по умолчанию:
• <b>Локация:</b> Санкт-Петербург
• <b>Мин. аудитория:</b> 50 человек
• <b>Приоритетные темы:</b> AI, цифровая трансформация, образование
• <b>Типы мероприятий:</b> конференции, митапы, хакатоны, стратегические сессии
• <b>Уведомления:</b> ✅ Включены

Теперь вы можете заново настроить параметры под себя.
        """
        
        await update.message.reply_text(text, parse_mode='HTML')
        await self.show_settings(update, context)
    
    async def handle_setting_selection(self, update: Update, context: CallbackContext):
        """Обработка выбора настроек"""
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        settings = self._get_user_settings(user_id)
        
        # Обработка выбора тематики
        if current_context == 'themes_settings':
            if text in ["🤖 AI и ML", "📊 Data Science", "💻 Разработка", "🔐 Кибербезопасность", "🌐 Цифровая трансформация", "🎓 Образование"]:
                theme_map = {
                    "🤖 AI и ML": "AI",
                    "📊 Data Science": "Data Science", 
                    "💻 Разработка": "разработка",
                    "🔐 Кибербезопасность": "кибербезопасность",
                    "🌐 Цифровая трансформация": "цифровая трансформация",
                    "🎓 Образование": "образование"
                }
                
                theme = theme_map[text]
                if theme not in settings['themes']:
                    settings['themes'].append(theme)
                    await update.message.reply_text(f"✅ Тема '{theme}' добавлена в приоритеты")
                else:
                    await update.message.reply_text(f"ℹ️ Тема '{theme}' уже в приоритетах")
            
            elif text == "✅ Сохранить темы":
                await update.message.reply_text("✅ Приоритетные темы сохранены!")
                await self.show_settings(update, context)
        
        # Обработка локации
        elif current_context == 'location_settings':
            if text in ["📍 Санкт-Петербург", "📍 Москва", "📍 Онлайн", "📍 Любая"]:
                location_map = {
                    "📍 Санкт-Петербург": "Санкт-Петербург",
                    "📍 Москва": "Москва",
                    "📍 Онлайн": "Онлайн", 
                    "📍 Любая": "Любая"
                }
                settings['location'] = location_map[text]
                await update.message.reply_text(f"✅ Локация изменена на: {location_map[text]}")
                await self.show_settings(update, context)
        
        # Обработка аудитории
        elif current_context == 'audience_settings':
            if text in ["👤 Маленькие (1-50)", "👥 Средние (50-200)", "👨‍👩‍👧‍👦 Крупные (200+)", "🌟 Любые"]:
                audience_map = {
                    "👤 Маленькие (1-50)": 10,
                    "👥 Средние (50-200)": 50,
                    "👨‍👩‍👧‍👦 Крупные (200+)": 200,
                    "🌟 Любые": 0
                }
                settings['min_audience'] = audience_map[text]
                await update.message.reply_text(f"✅ Минимальная аудитория установлена: {text}")
                await self.show_settings(update, context)
        
        # Обработка типов мероприятий
        elif current_context == 'event_types_settings':
            if text in ["🎤 Конференции", "👥 Митапы", "💻 Хакатоны", "🎯 Страт. сессии", "💬 Круглые столы", "📚 Семинары"]:
                type_map = {
                    "🎤 Конференции": "конференция",
                    "👥 Митапы": "митап", 
                    "💻 Хакатоны": "хакатон",
                    "🎯 Страт. сессии": "стратегическая сессия",
                    "💬 Круглые столы": "круглый стол",
                    "📚 Семинары": "семинар"
                }
                
                event_type = type_map[text]
                if event_type not in settings['event_types']:
                    settings['event_types'].append(event_type)
                    await update.message.reply_text(f"✅ Тип '{event_type}' добавлен в предпочтения")
                else:
                    await update.message.reply_text(f"ℹ️ Тип '{event_type}' уже в предпочтениях")
            
            elif text == "✅ Сохранить типы":
                await update.message.reply_text("✅ Типы мероприятий сохранены!")
                await self.show_settings(update, context)
        
        # Обработка уведомлений
        elif current_context == 'notification_settings':
            if text == "🔔 Включить уведомления":
                settings['notifications'] = True
                await update.message.reply_text("✅ Уведомления включены")
                await self.show_settings(update, context)
            
            elif text == "🔕 Выключить уведомления":
                settings['notifications'] = False
                await update.message.reply_text("✅ Уведомления выключены")
                await self.show_settings(update, context)
        
        # Возврат в главное меню
        if text == "🏠 Главное меню":
            self._set_user_context(user_id, 'main_menu')
            await self._show_main_menu(update, context)
    
    async def show_stats(self, update: Update, context: CallbackContext):
        """Показывает статистику"""
        events = self.parser.load_events()
        if not events:
            events = self.parser.parse_events()
        
        stats = self.parser.get_events_statistics()
        filtered_events = self.filter.filter_events(events)
        user_id = update.effective_user.id
        favorites_count = len(self.user_favorites.get(user_id, []))
        
        text = f"""
📊 <b>Статистика мероприятий</b>

📈 <b>Общая статистика:</b>
• Всего мероприятий в базе: {stats['total']}
• Подходящих вам мероприятий: {len(filtered_events)}
• Ваших избранных: {favorites_count}
• Источников данных: {len(stats.get('by_source', {}))}

🎪 <b>Распределение по типам:</b>
"""
        
        for event_type, count in list(stats.get('by_type', {}).items())[:5]:
            text += f"• {event_type}: {count}\n"
        
        text += f"\n📍 <b>Топ источников:</b>\n"
        for source, count in list(stats.get('by_source', {}).items())[:3]:
            text += f"• {source}: {count}\n"
        
        upcoming_events = [e for e in filtered_events if e.get('date') and e['date'] >= datetime.now().strftime('%Y-%m-%d')]
        text += f"\n📅 <b>Ближайшие мероприятия:</b> {len(upcoming_events)}"
        
        await update.message.reply_text(text, parse_mode='HTML')
    
    async def handle_search(self, update: Update, context: CallbackContext):
        """Обработчик поисковых запросов"""
        text = update.message.text
        
        if text == "🔍 По тематике":
            await self._show_themes_settings(update, context)
        elif text == "📅 По дате":
            await update.message.reply_text("📅 Функция поиска по дате в разработке...")
        elif text == "👥 По аудитории":
            await self._show_audience_settings(update, context)
        elif text == "🎪 По типу":
            await self._show_event_types_settings(update, context)
        elif text == "📍 По локации":
            await self._show_location_settings(update, context)
        else:
            await self._apply_search_criteria(update, context, text)
    
    async def _apply_search_criteria(self, update: Update, context: CallbackContext, criteria: str):
        """Применяет выбранные критерии поиска"""
        user_id = update.effective_user.id
        settings = self._get_user_settings(user_id)
        
        if criteria == "🤖 AI и Машинное обучение":
            settings['themes'] = ['AI', 'искусственный интеллект', 'машинное обучение', 'нейросети']
            await update.message.reply_text("✅ Установлены темы: AI и Машинное обучение")
        
        elif criteria == "📊 Data Science":
            settings['themes'] = ['Data Science', 'аналитика', 'большие данные']
            await update.message.reply_text("✅ Установлены темы: Data Science")
        
        elif criteria == "👤 До 100 человек":
            settings['min_audience'] = 10
            await update.message.reply_text("✅ Установлена минимальная аудитория: до 100 человек")
        
        elif criteria == "🎤 Конференции":
            settings['event_types'] = ['конференция', 'форум']
            await update.message.reply_text("✅ Показываю только конференции и форумы")
        
        await self.show_events(update, context)
    
    async def help_command(self, update: Update, context: CallbackContext):
        """Обработчик команды /help"""
        help_text = """
📋 <b>Доступные команды:</b>

<b>Основные команды:</b>
/start - Главное меню
/events - Рекомендованные мероприятия
/find - Поиск мероприятий
/favorites - Избранные мероприятия
/settings - Настройки критериев
/stats - Статистика
/help - Эта справка

<b>Настройки:</b>
• Приоритетные темы (AI, Data Science и др.)
• Локация мероприятий
• Размер аудитории  
• Типы мероприятий
• Уведомления

<b>Функции:</b>
• 📅 - Добавление в календарь
• ⭐ - Избранное
• 🔍 - Расширенный поиск
• 📊 - Статистика
        """
        await update.message.reply_text(help_text, parse_mode='HTML')

    async def export_events(self, update: Update, context: CallbackContext):
        """Экспорт всех избранных мероприятий в .ics файл"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_favorites or not self.user_favorites[user_id]:
            await update.message.reply_text("⭐ У вас нет избранных мероприятий для экспорта")
            return
        
        await update.message.reply_text("📦 Создаю файл со всеми избранными мероприятиями...")
        
        events = self.user_favorites[user_id]
        result = self.calendar.ics_generator.create_multiple_events_ics(events, user_id)
        
        if result['success']:
            try:
                with open(result['filepath'], 'rb') as ics_file:
                    await context.bot.send_document(
                        chat_id=update.message.chat_id,
                        document=ics_file,
                        filename=result['filename'],
                        caption=(
                            "📦 <b>Файл со всеми избранными мероприятиями готов!</b>\n\n"
                            f"Содержит: {len(events)} мероприятий\n\n"
                            "📱 <b>Как импортировать:</b>\n"
                            "1. Скачайте файл\n"
                            "2. Откройте его на телефоне\n"
                            "3. Выберите 'Добавить в календарь'\n\n"
                            "Все мероприятия будут добавлены в ваш календарь! ✅"
                        ),
                        parse_mode='HTML'
                    )
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка отправки файла: {e}")
        else:
            await update.message.reply_text("❌ Ошибка создания файла экспорта")
    
    async def handle_message(self, update: Update, context: CallbackContext):
        """Обработчик текстовых сообщений"""
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        
        # Определяем контекст и перенаправляем в соответствующий обработчик
        if current_context == 'settings_menu':
            await self.handle_settings_menu(update, context)
        elif current_context in ['themes_settings', 'location_settings', 'audience_settings', 'event_types_settings', 'notification_settings']:
            await self.handle_setting_selection(update, context)
        elif current_context == 'search_menu':
            await self.handle_search_menu(update, context)
        elif current_context in ['search_themes', 'search_date', 'search_audience', 'search_type', 'search_location']:
            await self.handle_search_selection(update, context)
        else:
            # Главное меню
            if text == "🎯 Рекомендованные мероприятия":
                await self.show_events(update, context)
            
            elif text == "🔍 Найти мероприятия":
                await self.find_events(update, context)
            
            elif text == "⭐ Избранное":
                await self.show_favorites(update, context)
            
            elif text == "⚙️ Настройки":
                await self.show_settings(update, context)
            
            elif text == "📊 Статистика":
                await self.show_stats(update, context)
            
            elif text == "ℹ️ Помощь":
                await self.help_command(update, context)
            
            elif text == "🏠 Главное меню":
                await self._show_main_menu(update, context)
            
            elif text == "🎯 Рекомендованные":
                await self.show_events(update, context)
            
            else:
                await update.message.reply_text(
                    "Используйте кнопки меню или команды:\n"
                    "/start - главное меню\n"
                    "/help - помощь"
                )
    
    def run(self):
        """Запускает бота"""
        if not self.token or self.token == "YOUR_TELEGRAM_BOT_TOKEN":
            print("❌ Укажите TELEGRAM_BOT_TOKEN в config.py")
            return
        
        self.application = Application.builder().token(self.token).build()
        
        # Добавляем обработчики команд
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("events", self.show_events))
        self.application.add_handler(CommandHandler("find", self.find_events))
        self.application.add_handler(CommandHandler("favorites", self.show_favorites))
        self.application.add_handler(CommandHandler("settings", self.show_settings))
        self.application.add_handler(CommandHandler("stats", self.show_stats))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("export", self.export_events))
        
        # Добавляем обработчики callback-запросов
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Добавляем обработчик текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        print("🤖 Telegram бот запущен с полным функционалом настроек!")
        print("✅ Все кнопки настроек теперь работают:")
        print("   • 🎯 Изменить приоритеты - настройка тематик")
        print("   • 📍 Изменить локацию - выбор города/формата")
        print("   • 👥 Настройка аудитории - размер мероприятий") 
        print("   • 🎪 Типы мероприятий - выбор форматов")
        print("   • 🔔 Уведомления - управление уведомлениями")
        print("   • 📊 Сбросить настройки - восстановление defaults")
        
        try:
            # Запускаем в отдельном event loop
            import asyncio
            
            # Проверяем, есть ли уже запущенный loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # Если loop уже запущен, запускаем бота в отдельной задаче
                print("⚠️  Event loop уже запущен, запускаем бота в фоне...")
                loop.create_task(self.application.run_polling())
            else:
                # Если loop не запущен, запускаем его
                loop.run_until_complete(self.application.run_polling())
                
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен пользователем")
        except Exception as e:
            print(f"❌ Ошибка при запуске бота: {e}")