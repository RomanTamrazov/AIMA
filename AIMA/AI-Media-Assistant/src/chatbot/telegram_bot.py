import json
import os
import sys
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import config
from src.parsers.event_parser import EventParser
from src.analysis.criteria_filter import CriteriaFilter
from src.calendar_integration.telegram_calendar import TelegramCalendar

class TelegramBot:
    def __init__(self):
        self.token = config.BOT_CONFIG["token"]
        self.parser = EventParser()
        self.filter = CriteriaFilter()
        self.calendar = TelegramCalendar()
        self.application = None
        self.user_events = {}
        self.user_favorites = {}
        self.user_settings = {}
        self.user_context = {}
        self.user_profiles = {}
    
    def _get_user_profile(self, user_id):
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'role': None,
                'preferences': {
                    'location_preference': None,
                    'audience_preference': None,
                    'participation_role': None,
                    'interests': []
                },
                'setup_completed': False
            }
        return self.user_profiles[user_id]
    
    def _get_user_settings(self, user_id):
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
        self.user_context[user_id] = context
    
    def _get_user_context(self, user_id):
        return self.user_context.get(user_id, 'main_menu')
    
    async def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        user_id = user.id
        
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed']:
            await self._show_role_selection(update, context)
            return
        
        self._set_user_context(user_id, 'main_menu')
        
        role_greeting = {
            'manager': "👔 Руководитель",
            'employee': "👨‍💼 Сотрудник"
        }
        
        welcome_text = f"""
🤖 Привет, {user.first_name}!

{role_greeting.get(profile['role'], '👤 Пользователь')}

Я - AI-помощник по медиа от Центра исследований и разработки Сбера.

🎯 Персонализированные рекомендации:
• Мероприятия под вашу роль: {'руководитель' if profile['role'] == 'manager' else 'сотрудник'}
• Предпочтительная локация: {profile['preferences']['location_preference'] or 'не указана'}
• Размер мероприятий: {profile['preferences']['audience_preference'] or 'не указан'}
• Роль участия: {profile['preferences']['participation_role'] or 'не указана'}

📋 Мои возможности:
• Найти подходящие IT-мероприятия в Санкт-Петербурге
• Рекомендовать мероприятия по вашим критериям
• Добавлять мероприятия в календарь и избранное
• Показывать статистику и аналитику

Выбери действие ниже или используй команды:
/events - рекомендованные мероприятия
/find - найти мероприятия
/favorites - избранное
/settings - настройки критериев
/profile - изменить профиль
/stats - статистика
/help - помощь
        """
        
        main_keyboard = [
            [KeyboardButton("🎯 Рекомендованные мероприятия"), KeyboardButton("📅 Мой календарь")],
            [KeyboardButton("🔍 Найти мероприятия"), KeyboardButton("⭐ Избранное")],
            [KeyboardButton("⚙️ Настройки"), KeyboardButton("👤 Профиль")],
            [KeyboardButton("📊 Статистика"), KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
            
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _show_role_selection(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'role_selection')
        
        role_keyboard = [
            [KeyboardButton("👔 Руководитель"), KeyboardButton("👨‍💼 Сотрудник")]
        ]
        reply_markup = ReplyKeyboardMarkup(role_keyboard, resize_keyboard=True)
        
        welcome_text = """
🤖 Добро пожаловать в AI-помощник по медиа!

Я помогу вам найти подходящие IT-мероприятия в Санкт-Петербурге. 

🎯 Для персонализированных рекомендаций выберите вашу роль:

👔 Руководитель:
• Стратегические мероприятия для развития компании
• Встречи с партнерами и представителями власти
• Конференции для установления деловых контактов
• Мероприятия где ваше присутствие будет полезно для компании

👨‍💼 Сотрудник:
• Образовательные мероприятия для профессионального роста
• Хакатоны и митапы для практического опыта
• Конференции для обучения и нетворкинга
• Возможности участия в разных ролях

Выберите вашу роль для начала:
        """
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _show_preferences_setup(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'preferences_setup')
        
        preferences_keyboard = [
            [KeyboardButton("📍 Локация"), KeyboardButton("👥 Аудитория")],
            [KeyboardButton("🎭 Роль участия"), KeyboardButton("🎯 Интересы")],
            [KeyboardButton("✅ Завершить настройку")]
        ]
        reply_markup = ReplyKeyboardMarkup(preferences_keyboard, resize_keyboard=True)
        
        profile = self._get_user_profile(user_id)
        role_text = "руководитель" if profile['role'] == 'manager' else "сотрудник"
        
        preferences_text = f"""
👤 Настройка профиля

Ваша роль: {role_text}

Теперь настроим ваши предпочтения для точных рекомендаций:

📍 Локация - где предпочитаете участвовать в мероприятиях
👥 Аудитория - предпочтительный размер мероприятий  
🎭 Роль участия - как хотите участвовать в мероприятиях
🎯 Интересы - тематики которые вас интересуют

Нажмите ✅ Завершить настройку когда закончите.
        """
        
        await update.message.reply_text(preferences_text, reply_markup=reply_markup)
    
    async def _show_location_preferences(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'location_preferences')
        
        location_keyboard = [
            [KeyboardButton("🏙️ Центр города"), KeyboardButton("🏫 Бизнес-центры")],
            [KeyboardButton("🎓 Университеты"), KeyboardButton("🏢 Офисы компаний")],
            [KeyboardButton("💻 Онлайн"), KeyboardButton("📍 Любая локация")],
            [KeyboardButton("⬅️ Назад к настройкам")]
        ]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, resize_keyboard=True)
        
        profile = self._get_user_profile(user_id)
        role_specific_text = {
            'manager': "Руководителям рекомендую бизнес-центры и офисы компаний для деловых встреч",
            'employee': "Сотрудникам подойдут университеты и онлайн форматы для обучения"
        }
        
        location_text = f"""
📍 Выбор предпочтительной локации

{role_specific_text.get(profile['role'], 'Выберите где вам удобно участвовать в мероприятиях:')}

🏙️ Центр города - мероприятия в историческом центре
🏫 Бизнес-центры - деловые районы, бизнес-центры
🎓 Университеты - вузы, образовательные площадки  
🏢 Офисы компаний - корпоративные мероприятия
💻 Онлайн - дистанционное участие
📍 Любая локация - все варианты подходят

Текущая настройка: {profile['preferences']['location_preference'] or 'не выбрана'}
        """
        
        await update.message.reply_text(location_text, reply_markup=reply_markup)
    
    async def _show_audience_preferences(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'audience_preferences')
        
        audience_keyboard = [
            [KeyboardButton("👤 Камерные (до 50)"), KeyboardButton("👥 Средние (50-200)")],
            [KeyboardButton("👨‍👩‍👧‍👦 Крупные (200-500)"), KeyboardButton("🏛️ Массовые (500+)")],
            [KeyboardButton("🌟 Любой размер"), KeyboardButton("⬅️ Назад к настройкам")]
        ]
        reply_markup = ReplyKeyboardMarkup(audience_keyboard, resize_keyboard=True)
        
        profile = self._get_user_profile(user_id)
        role_specific_text = {
            'manager': "Руководителям рекомендую средние и крупные мероприятия для установления контактов",
            'employee': "Сотрудникам подойдут любые форматы для обучения и нетворкинга"
        }
        
        audience_text = f"""
👥 Выбор размера мероприятий

{role_specific_text.get(profile['role'], 'Выберите предпочтительный размер мероприятий:')}

👤 Камерные - до 50 человек, интимная атмосфера
👥 Средние - 50-200 человек, баланс общения и обучения
👨‍👩‍👧‍👦 Крупные - 200-500 человек, масштабные события
🏛️ Массовые - 500+ человек, конференции и форумы
🌟 Любой размер - все форматы подходят

Текущая настройка: {profile['preferences']['audience_preference'] or 'не выбран'}
        """
        
        await update.message.reply_text(audience_text, reply_markup=reply_markup)
    
    async def _show_participation_role_preferences(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'participation_role_preferences')
        
        profile = self._get_user_profile(user_id)
        
        if profile['role'] == 'manager':
            role_keyboard = [
                [KeyboardButton("🎯 Спикер"), KeyboardButton("🤝 Эксперт")],
                [KeyboardButton("🏢 Представитель компании"), KeyboardButton("📊 Участник")],
                [KeyboardButton("🌟 Любая роль"), KeyboardButton("⬅️ Назад к настройкам")]
            ]
            
            role_description = """
🎯 Спикер - выступление с докладом или презентацией
🤝 Эксперт - участие в панельных дискуссиях как эксперт
🏢 Представитель компании - официальное представительство
📊 Участник - участие в качестве слушателя
🌟 Любая роль - все варианты подходят
            """
        else:
            role_keyboard = [
                [KeyboardButton("🎓 Студент"), KeyboardButton("👨‍💼 Участник")],
                [KeyboardButton("🛠️ Менеджер мероприятия"), KeyboardButton("👥 Ассистент")],
                [KeyboardButton("🏢 Представитель компании"), KeyboardButton("🌟 Любая роль")],
                [KeyboardButton("⬅️ Назад к настройкам")]
            ]
            
            role_description = """
🎓 Студент - участие в образовательных программах
👨‍💼 Участник - стандартное участие как слушатель
🛠️ Менеджер мероприятия - организационная роль
👥 Ассистент - помощь в проведении мероприятия
🏢 Представитель компании - представление интересов компании
🌟 Любая роль - все варианты подходят
            """
        
        reply_markup = ReplyKeyboardMarkup(role_keyboard, resize_keyboard=True)
        
        role_specific_text = {
            'manager': "Руководителям доступны роли спикера, эксперта и представителя компании",
            'employee': "Сотрудники могут участвовать в разных ролях для профессионального роста"
        }
        
        participation_text = f"""
🎭 Выбор роли участия

{role_specific_text.get(profile['role'], 'Выберите в какой роли хотите участвовать:')}

{role_description}

Текущая настройка: {profile['preferences']['participation_role'] or 'не выбрана'}
        """
        
        await update.message.reply_text(participation_text, reply_markup=reply_markup)
    
    async def _show_interests_preferences(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'interests_preferences')
        
        interests_keyboard = [
            [KeyboardButton("🤖 AI и ML"), KeyboardButton("📊 Data Science")],
            [KeyboardButton("💻 Разработка"), KeyboardButton("🔐 Кибербезопасность")],
            [KeyboardButton("🌐 Цифровая трансформация"), KeyboardButton("🎓 Образование")],
            [KeyboardButton("🚀 Стартапы"), KeyboardButton("📈 Бизнес")],
            [KeyboardButton("✅ Сохранить интересы"), KeyboardButton("⬅️ Назад к настройкам")]
        ]
        reply_markup = ReplyKeyboardMarkup(interests_keyboard, resize_keyboard=True)
        
        profile = self._get_user_profile(user_id)
        current_interests = ', '.join(profile['preferences']['interests']) if profile['preferences']['interests'] else 'не выбраны'
        
        interests_text = f"""
🎯 Выбор интересов

Выберите тематики которые вас интересуют:

🤖 AI и ML - искусственный интеллект, машинное обучение
📊 Data Science - анализ данных, большие данные
💻 Разработка - программирование, IT-технологии
🔐 Кибербезопасность - защита данных, информационная безопасность
🌐 Цифровая трансформация - digital, инновации в бизнесе
🎓 Образование - EdTech, обучение, наука
🚀 Стартапы - венчурные инвестиции, инновации
📈 Бизнес - предпринимательство, экономика

Нажимайте на темы для добавления, затем ✅ Сохранить интересы

Текущие интересы: {current_interests}
        """
        
        await update.message.reply_text(interests_text, reply_markup=reply_markup)
    
    async def handle_profile_setup(self, update: Update, context: CallbackContext):
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        profile = self._get_user_profile(user_id)
        
        if current_context == 'role_selection':
            if text == "👔 Руководитель":
                profile['role'] = 'manager'
                await update.message.reply_text(
                    "✅ Отлично! Вы выбрали роль Руководителя\n\n"
                    "Теперь я буду рекомендовать вам стратегические мероприятия "
                    "где ваше присутствие будет полезно для компании."
                )
                await self._show_preferences_setup(update, context)
            
            elif text == "👨‍💼 Сотрудник":
                profile['role'] = 'employee'
                await update.message.reply_text(
                    "✅ Отлично! Вы выбрали роль Сотрудника\n\n"
                    "Теперь я буду рекомендовать вам мероприятия для профессионального "
                    "роста и участия в разных ролях."
                )
                await self._show_preferences_setup(update, context)
        
        elif current_context == 'preferences_setup':
            if text == "📍 Локация":
                await self._show_location_preferences(update, context)
            elif text == "👥 Аудитория":
                await self._show_audience_preferences(update, context)
            elif text == "🎭 Роль участия":
                await self._show_participation_role_preferences(update, context)
            elif text == "🎯 Интересы":
                await self._show_interests_preferences(update, context)
            elif text == "✅ Завершить настройку":
                await self._complete_profile_setup(update, context)
        
        elif current_context == 'location_preferences':
            location_map = {
                "🏙️ Центр города": "Центр города",
                "🏫 Бизнес-центры": "Бизнес-центры", 
                "🎓 Университеты": "Университеты",
                "🏢 Офисы компаний": "Офисы компаний",
                "💻 Онлайн": "Онлайн",
                "📍 Любая локация": "Любая локация"
            }
            
            if text in location_map:
                profile['preferences']['location_preference'] = location_map[text]
                await update.message.reply_text(f"✅ Локация установлена: {location_map[text]}")
                await self._show_preferences_setup(update, context)
            elif text == "⬅️ Назад к настройкам":
                await self._show_preferences_setup(update, context)
        
        elif current_context == 'audience_preferences':
            audience_map = {
                "👤 Камерные (до 50)": "Камерные (до 50)",
                "👥 Средние (50-200)": "Средние (50-200)",
                "👨‍👩‍👧‍👦 Крупные (200-500)": "Крупные (200-500)",
                "🏛️ Массовые (500+)": "Массовые (500+)",
                "🌟 Любой размер": "Любой размер"
            }
            
            if text in audience_map:
                profile['preferences']['audience_preference'] = audience_map[text]
                await update.message.reply_text(f"✅ Размер мероприятий установлен: {audience_map[text]}")
                await self._show_preferences_setup(update, context)
            elif text == "⬅️ Назад к настройкам":
                await self._show_preferences_setup(update, context)
        
        elif current_context == 'participation_role_preferences':
            role_map = {
                "🎯 Спикер": "Спикер",
                "🤝 Эксперт": "Эксперт", 
                "🏢 Представитель компании": "Представитель компании",
                "📊 Участник": "Участник",
                "🎓 Студент": "Студент",
                "👨‍💼 Участник": "Участник",
                "🛠️ Менеджер мероприятия": "Менеджер мероприятия",
                "👥 Ассистент": "Ассистент",
                "🌟 Любая роль": "Любая роль"
            }
            
            if text in role_map:
                profile['preferences']['participation_role'] = role_map[text]
                await update.message.reply_text(f"✅ Роль участия установлена: {role_map[text]}")
                await self._show_preferences_setup(update, context)
            elif text == "⬅️ Назад к настройкам":
                await self._show_preferences_setup(update, context)
        
        elif current_context == 'interests_preferences':
            interests_map = {
                "🤖 AI и ML": "AI и ML",
                "📊 Data Science": "Data Science",
                "💻 Разработка": "Разработка",
                "🔐 Кибербезопасность": "Кибербезопасность", 
                "🌐 Цифровая трансформация": "Цифровая трансформация",
                "🎓 Образование": "Образование",
                "🚀 Стартапы": "Стартапы",
                "📈 Бизнес": "Бизнес"
            }
            
            if text in interests_map:
                interest = interests_map[text]
                if interest not in profile['preferences']['interests']:
                    profile['preferences']['interests'].append(interest)
                    await update.message.reply_text(f"✅ Интерес добавлен: {interest}")
                else:
                    await update.message.reply_text(f"ℹ️ Интерес {interest} уже добавлен")
            
            elif text == "✅ Сохранить интересы":
                await update.message.reply_text("✅ Интересы сохранены!")
                await self._show_preferences_setup(update, context)
            
            elif text == "⬅️ Назад к настройкам":
                await self._show_preferences_setup(update, context)

    def _truncate_message(self, text, max_length=4000):
        if len(text) <= max_length:
            return text
        
        truncated = text[:max_length]
        last_newline = truncated.rfind('\n')
        
        if last_newline > max_length - 100:
            return text[:last_newline] + "\n\n... (сообщение сокращено)"
        else:
            return text[:max_length-50] + "\n\n... (сообщение сокращено)"
    
    async def _complete_profile_setup(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        if not profile['role']:
            await update.message.reply_text("❌ Пожалуйста, сначала выберите вашу роль")
            return
        
        profile['setup_completed'] = True
        
        role_text = "руководитель" if profile['role'] == 'manager' else "сотрудник"
        
        completion_text = f"""
🎉 Настройка профиля завершена!

✅ Ваш профиль:
• Роль: {role_text}
• Локация: {profile['preferences']['location_preference'] or 'не указана'}
• Размер мероприятий: {profile['preferences']['audience_preference'] or 'не указан'}  
• Роль участия: {profile['preferences']['participation_role'] or 'не указана'}
• Интересы: {', '.join(profile['preferences']['interests']) if profile['preferences']['interests'] else 'не указаны'}

Теперь я буду подбирать мероприятия специально для вас!
Используйте команду /profile чтобы изменить настройки.

Начнем поиск подходящих мероприятий?
        """
        
        self._set_user_context(user_id, 'main_menu')
        
        main_keyboard = [
            [KeyboardButton("🎯 Рекомендованные мероприятия")],
            [KeyboardButton("🔍 Найти мероприятия"), KeyboardButton("⭐ Избранное")],
            [KeyboardButton("⚙️ Настройки"), KeyboardButton("👤 Профиль")],
            [KeyboardButton("📊 Статистика"), KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        await update.message.reply_text(completion_text, reply_markup=reply_markup)
    
    async def show_profile(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed']:
            await self._show_role_selection(update, context)
            return
        
        profile_keyboard = [
            [KeyboardButton("👔 Изменить роль"), KeyboardButton("📍 Изменить локацию")],
            [KeyboardButton("👥 Изменить аудиторию"), KeyboardButton("🎭 Изменить роль участия")],
            [KeyboardButton("🎯 Изменить интересы"), KeyboardButton("🔄 Сбросить профиль")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(profile_keyboard, resize_keyboard=True)
        
        role_text = "руководитель" if profile['role'] == 'manager' else "сотрудник"
        
        profile_text = f"""
👤 Ваш профиль

Основная информация:
• Роль: {role_text}
• Локация: {profile['preferences']['location_preference'] or 'не указана'}
• Размер мероприятий: {profile['preferences']['audience_preference'] or 'не указан'}
• Роль участия: {profile['preferences']['participation_role'] or 'не указана'}
• Интересы: {', '.join(profile['preferences']['interests']) if profile['preferences']['interests'] else 'не указаны'}

Выберите что хотите изменить:
        """
        
        await update.message.reply_text(profile_text, reply_markup=reply_markup)
        self._set_user_context(user_id, 'profile_edit')

    async def _show_themes_search(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_themes')
        
        themes_keyboard = [
            [KeyboardButton("🤖 AI и ML"), KeyboardButton("📊 Data Science")],
            [KeyboardButton("💻 Разработка"), KeyboardButton("🔐 Кибербезопасность")],
            [KeyboardButton("🌐 Цифровая трансформация"), KeyboardButton("🎓 Образование")],
            [KeyboardButton("🚀 Стартапы"), KeyboardButton("📈 Бизнес")],
            [KeyboardButton("🔍 Найти по темам"), KeyboardButton("⬅️ Назад к поиску")]
        ]
        reply_markup = ReplyKeyboardMarkup(themes_keyboard, resize_keyboard=True)
        
        text = """
🔍 Поиск по тематике

Выберите интересующие темы:

🤖 AI и ML - искусственный интеллект, машинное обучение
📊 Data Science - анализ данных, большие данные
💻 Разработка - программирование, IT-технологии
🔐 Кибербезопасность - защита данных, информационная безопасность
🌐 Цифровая трансформация - digital, инновации в бизнесе
🎓 Образование - EdTech, обучение, наука
🚀 Стартапы - венчурные инвестиции, инновации
📈 Бизнес - предпринимательство, экономика

Нажимайте на темы для выбора, затем 🔍 Найти по темам
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _show_date_search(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_date')
        
        date_keyboard = [
            [KeyboardButton("📅 Сегодня"), KeyboardButton("📅 Завтра")],
            [KeyboardButton("📅 Эта неделя"), KeyboardButton("📅 Следующая неделя")],
            [KeyboardButton("📅 Этот месяц"), KeyboardButton("📅 Следующий месяц")],
            [KeyboardButton("🔍 Найти по дате"), KeyboardButton("⬅️ Назад к поиску")]
        ]
        reply_markup = ReplyKeyboardMarkup(date_keyboard, resize_keyboard=True)
        
        text = """
📅 Поиск по дате

Выберите период для поиска мероприятий:

📅 Сегодня - мероприятия на сегодня
📅 Завтра - мероприятия на завтра
📅 Эта неделя - мероприятия на текущей неделе
📅 Следующая неделя - мероприятия на следующей неделе
📅 Этот месяц - мероприятия в текущем месяце
📅 Следующий месяц - мероприятия в следующем месяце

Выберите период и нажмите 🔍 Найти по дате
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _show_audience_search(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_audience')
        
        audience_keyboard = [
            [KeyboardButton("👤 Камерные (до 50)"), KeyboardButton("👥 Средние (50-200)")],
            [KeyboardButton("👨‍👩‍👧‍👦 Крупные (200-500)"), KeyboardButton("🏛️ Массовые (500+)")],
            [KeyboardButton("🌟 Любой размер"), KeyboardButton("🔍 Найти по аудитории")],
            [KeyboardButton("⬅️ Назад к поиску")]
        ]
        reply_markup = ReplyKeyboardMarkup(audience_keyboard, resize_keyboard=True)
        
        text = """
👥 Поиск по размеру аудитории

Выберите предпочтительный размер мероприятий:

👤 Камерные - до 50 человек, интимная атмосфера
👥 Средние - 50-200 человек, баланс общения и обучения
👨‍👩‍👧‍👦 Крупные - 200-500 человек, масштабные события
🏛️ Массовые - 500+ человек, конференции и форумы
🌟 Любой размер - все форматы подходят

Выберите размер и нажмите 🔍 Найти по аудитории
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _show_type_search(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_type')
        
        type_keyboard = [
            [KeyboardButton("🎤 Конференция"), KeyboardButton("👥 Митап")],
            [KeyboardButton("💻 Хакатон"), KeyboardButton("🎯 Стратегическая сессия")],
            [KeyboardButton("💬 Круглый стол"), KeyboardButton("🏛️ Форум")],
            [KeyboardButton("📚 Семинар"), KeyboardButton("🔍 Найти по типу")],
            [KeyboardButton("⬅️ Назад к поиску")]
        ]
        reply_markup = ReplyKeyboardMarkup(type_keyboard, resize_keyboard=True)
        
        text = """
🎪 Поиск по типу мероприятия

Выберите тип мероприятий:

🎤 Конференция - масштабные профессиональные встречи
👥 Митап - неформальные встречи специалистов
💻 Хакатон - соревнования по программированию
🎯 Стратегическая сессия - деловые стратегические встречи
💬 Круглый стол - дискуссии и обсуждения
🏛️ Форум - крупные отраслевые мероприятия
📚 Семинар - обучающие мероприятия

Выберите тип и нажмите 🔍 Найти по типу
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _show_location_search(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'search_location')
        
        location_keyboard = [
            [KeyboardButton("🏙️ Центр города"), KeyboardButton("🏫 Бизнес-центры")],
            [KeyboardButton("🎓 Университеты"), KeyboardButton("🏢 Офисы компаний")],
            [KeyboardButton("💻 Онлайн"), KeyboardButton("📍 Любая локация")],
            [KeyboardButton("🔍 Найти по локации"), KeyboardButton("⬅️ Назад к поиску")]
        ]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, resize_keyboard=True)
        
        text = """
📍 Поиск по локации

Выберите предпочтительную локацию:

🏙️ Центр города - мероприятия в историческом центре
🏫 Бизнес-центры - деловые районы, бизнес-центры
🎓 Университеты - вузы, образовательные площадки  
🏢 Офисы компаний - корпоративные мероприятия
💻 Онлайн - дистанционное участие
📍 Любая локация - все варианты подходят

Выберите локацию и нажмите 🔍 Найти по локации
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def handle_profile_edit(self, update: Update, context: CallbackContext):
        text = update.message.text
        user_id = update.effective_user.id
        
        if text == "👔 Изменить роль":
            await self._show_role_selection(update, context)
        elif text == "📍 Изменить локацию":
            await self._show_location_preferences(update, context)
        elif text == "👥 Изменить аудиторию":
            await self._show_audience_preferences(update, context)
        elif text == "🎭 Изменить роль участия":
            await self._show_participation_role_preferences(update, context)
        elif text == "🎯 Изменить интересы":
            await self._show_interests_preferences(update, context)
        elif text == "🔄 Сбросить профиль":
            self.user_profiles[user_id] = {
                'role': None,
                'preferences': {
                    'location_preference': None,
                    'audience_preference': None, 
                    'participation_role': None,
                    'interests': []
                },
                'setup_completed': False
            }
            await update.message.reply_text("🔄 Профиль сброшен. Давайте настроим его заново!")
            await self._show_role_selection(update, context)
        elif text == "🏠 Главное меню":
            self._set_user_context(user_id, 'main_menu')
            await self.start(update, context)
    
    async def show_events(self, update: Update, context: CallbackContext):
        await update.message.reply_text("🔍 Ищу подходящие мероприятия по вашим критериям...")
        
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed']:
            await update.message.reply_text(
                "❌ Пожалуйста, сначала завершите настройку профиля в разделе 👤 Профиль"
            )
            return
        
        events = self.parser.load_events()
        if not events:
            events = await self.parser.parse_events()
        
        filtered_events = self._filter_events_by_profile(events, profile)
        
        if not filtered_events:
            await update.message.reply_text(
                "❌ Не найдено мероприятий по вашим критериям\n\n"
                "💡 Попробуйте:\n"
                "• Изменить критерии в 👤 Профиль\n" 
                "• Расширить интересы\n"
                "• Выбрать 'Любая локация' или 'Любой размер'\n"
                "• Использовать 🔍 Расширенный поиск"
            )
            return
        
        personalized_events = self._add_personalized_recommendations(filtered_events, profile)
        
        self.user_events[user_id] = personalized_events[:15]
        
        await self._show_event_page(update, context, user_id, 0)
    
    def _get_personalized_criteria(self, profile, user_settings):
        criteria = {
            "min_audience": user_settings['min_audience'],
            "event_types": user_settings['event_types'],
            "priority_themes": user_settings['themes'],
            "location": user_settings['location']
        }
        
        if profile['preferences']['interests']:
            criteria['priority_themes'] = list(set(criteria['priority_themes'] + profile['preferences']['interests']))
        
        if profile['role'] == 'manager':
            criteria['event_types'] = list(set(criteria['event_types'] + [
                'стратегическая сессия', 'форум', 'круглый стол', 'панельная дискуссия'
            ]))
            criteria['min_audience'] = max(criteria.get('min_audience', 50), 100)
        else:
            criteria['event_types'] = list(set(criteria['event_types'] + [
                'хакатон', 'митап', 'семинар', 'лекция', 'воркшоп'
            ]))
        
        location_pref = profile['preferences']['location_preference']
        if location_pref and location_pref != "Любая локация":
            criteria['location_preference'] = location_pref
        
        audience_pref = profile['preferences']['audience_preference']
        if audience_pref and audience_pref != "Любой размер":
            criteria['audience_preference'] = audience_pref
        
        return criteria

    def _filter_events_by_profile(self, events, profile):
        filtered_events = []
        
        for event in events:
            score = 0
            matches_criteria = True
            
            location_pref = profile['preferences']['location_preference']
            if location_pref and location_pref != "Любая локация":
                event_location = event.get('location', '').lower()
                if location_pref.lower() in event_location:
                    score += 3
                elif not self._location_matches_preference(event_location, location_pref):
                    matches_criteria = False
            
            audience_pref = profile['preferences']['audience_preference']
            if audience_pref and audience_pref != "Любой размер":
                event_audience = event.get('audience', '')
                if self._audience_matches_preference(event_audience, audience_pref):
                    score += 2
                else:
                    matches_criteria = False
            
            user_interests = profile['preferences']['interests']
            if user_interests:
                event_themes = event.get('themes', [])
                event_description = event.get('description', '').lower()
                event_title = event.get('title', '').lower()
                
                interest_matches = 0
                for interest in user_interests:
                    interest_lower = interest.lower()
                    if (any(interest_lower in theme.lower() for theme in event_themes) or
                        interest_lower in event_title or 
                        interest_lower in event_description):
                        interest_matches += 1
                        score += 2
                
                if interest_matches == 0:
                    score -= 1
            
            if profile['role'] == 'manager':
                event_type = event.get('type', '').lower()
                if any(role_type in event_type for role_type in 
                    ['стратегическая', 'форум', 'конференция', 'круглый стол']):
                    score += 3
            else:
                event_type = event.get('type', '').lower()
                if any(role_type in event_type for role_type in 
                    ['хакатон', 'митап', 'семинар', 'лекция', 'воркшоп']):
                    score += 3
            
            participation_role = profile['preferences']['participation_role']
            if participation_role and participation_role != "Любая роль":
                if self._participation_role_matches(event, participation_role):
                    score += 2
            
            if matches_criteria:
                event['priority_score'] = score
                filtered_events.append(event)
        
            filtered_events.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        return filtered_events
    
    def _add_personalized_recommendations(self, events, profile):
        for event in events:
            recommendation_reasons = []
            
            event_themes = event.get('themes', [])
            user_interests = profile['preferences']['interests']
            matching_interests = [interest for interest in user_interests if any(interest.lower() in theme.lower() for theme in event_themes)]
            if matching_interests:
                recommendation_reasons.append(f"Соответствует вашим интересам: {', '.join(matching_interests[:2])}")
            
            if profile['role'] == 'manager':
                if any(role_type in event.get('type', '').lower() for role_type in ['стратегическая', 'форум', 'конференция']):
                    recommendation_reasons.append("Стратегическое мероприятие для руководителя")
            else:
                if any(role_type in event.get('type', '').lower() for role_type in ['хакатон', 'митап', 'семинар']):
                    recommendation_reasons.append("Отличная возможность для профессионального роста")
            
            preferred_role = profile['preferences']['participation_role']
            if preferred_role and preferred_role != "Любая роль":
                recommendation_reasons.append(f"Подходит для роли: {preferred_role}")
            
            event['personalized_recommendation'] = recommendation_reasons
        
        return events

    async def _show_event_page(self, update: Update, context: CallbackContext, user_id: int, page: int):
        events = self.user_events.get(user_id, [])
        
        if not events:
            await update.message.reply_text("❌ Нет доступных мероприятий")
            return
        
        if page >= len(events):
            page = 0
        
        event = events[page]
        event_text = self._format_event_message(event, page + 1)
        
        is_favorite = False
        if user_id in self.user_favorites:
            favorite_titles = [e['title'] for e in self.user_favorites[user_id]]
            is_favorite = event['title'] in favorite_titles
        
        keyboard = []
        
        favorite_text = "❌ Удалить из избранного" if is_favorite else "⭐ В избранное"
        action_buttons = [
            InlineKeyboardButton("📅 Добавить в календарь", callback_data=f"add_{page}"),
            InlineKeyboardButton(favorite_text, callback_data=f"fav_{page}"),
        ]
        
        if event.get('url') and event['url'] not in ['', '#']:
            action_buttons.append(InlineKeyboardButton("🔗 Сайт", url=event['url']))
        
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
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                event_text, 
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text(
                event_text, 
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )

    def _location_matches_preference(self, event_location, location_pref):
        location_mapping = {
            'центр города': ['центр', 'центральный', 'невский', 'адмиралтейск', 'васильевск'],
            'бизнес-центры': ['бц', 'бизнес-центр', 'бизнес центр', 'деловой'],
            'университеты': ['университет', 'вуз', 'политех', 'итмо', 'спбгу'],
            'офисы компаний': ['офис', 'офисе', 'компании', 'сбер', 'яндекс', 'вк'],
            'онлайн': ['онлайн', 'online', 'zoom', 'webinar']
        }
        
        if location_pref.lower() in location_mapping:
            keywords = location_mapping[location_pref.lower()]
            return any(keyword in event_location for keyword in keywords)
        
        return False

    def _audience_matches_preference(self, event_audience, audience_pref):
        import re
        numbers = re.findall(r'\d+', str(event_audience))
        if numbers:
            audience_size = int(numbers[0])
            
            audience_ranges = {
                'Камерные (до 50)': (0, 50),
                'Средние (50-200)': (50, 200),
                'Крупные (200-500)': (200, 500),
                'Массовые (500+)': (500, float('inf'))
            }
            
            if audience_pref in audience_ranges:
                min_aud, max_aud = audience_ranges[audience_pref]
                return min_aud <= audience_size <= max_aud
        
        return True

    def _participation_role_matches(self, event, participation_role):
        event_type = event.get('type', '').lower()
        event_desc = event.get('description', '').lower()
        
        role_mapping = {
            'спикер': ['спикер', 'докладчик', 'выступление'],
            'эксперт': ['эксперт', 'панель', 'дискуссия'],
            'представитель компании': ['представитель', 'компания', 'корпоратив'],
            'участник': ['участник', 'слушатель', 'посетитель'],
            'студент': ['студент', 'обучение', 'образовательн'],
            'менеджер мероприятия': ['организатор', 'координатор'],
            'ассистент': ['ассистент', 'помощник']
        }
        
        if participation_role.lower() in role_mapping:
            keywords = role_mapping[participation_role.lower()]
            return any(keyword in event_type or keyword in event_desc for keyword in keywords)
        
        return True
    
    def _format_event_message(self, event, index):
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
        
        base_text = f"""
{index}. {emoji} {event['title']}

📅 Дата: {event['date']}
📍 Место: {event.get('location', 'Не указано')}
👥 Участники: {event.get('audience', 'Не указано')}
🎪 Тип: {event_type}
⭐ Приоритет: {event.get('priority_score', 0)}/10
"""
        
        description = event.get('description', 'Нет описания')
        if len(description) > 500:
            description = description[:500] + "..."
        base_text += f"\n📝 Описание: {description}"
        
        speakers = event.get('speakers', ['Не указаны'])
        if len(speakers) > 5:
            speakers = speakers[:5] + ["..."]
        base_text += f"\n🎤 Спикеры: {', '.join(speakers)}"
        
        base_text += f"\n📋 Регистрация: {event.get('registration_info', 'Не указана')}"
        
        themes = event.get('themes', [])
        if len(themes) > 8:
            themes = themes[:8] + ["..."]
        base_text += f"\n\n🏷️ Темы: {', '.join(themes)}"
        
        if event.get('personalized_recommendation'):
            base_text += f"\n\n🎯 Почему рекомендовано:\n"
            for reason in event['personalized_recommendation'][:2]:
                base_text += f"• {reason}\n"
        
        return self._truncate_message(base_text.strip())

    async def handle_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        try:
            if data.startswith('calendar_'):
                await self.handle_calendar_callback(update, context)
            
            elif data.startswith('event_'):
                await self.handle_event_callback(update, context)
            
            elif data.startswith('page_'):
                page = int(data.split('_')[1])
                await self._show_event_page(update, context, user_id, page)
            
            elif data.startswith('add_'):
                page = int(data.split('_')[1])
                events = self.user_events.get(user_id, [])
                if events and page < len(events):
                    event = events[page]
                    await self._add_to_calendar(update, context, event, page)
            
            elif data.startswith('fav_'):
                page = int(data.split('_')[1])
                await self._toggle_favorite(update, context, user_id, page)
            
            elif data == "main_menu":
                await self._show_main_menu(update, context)
            
            elif data == "events_0":
                await self.show_events(update, context)
            
            elif data == "settings":
                await self.show_settings(update, context)
            
            elif data == "profile":
                await self.show_profile(update, context)

            elif data == "calendar_today":
                await self.show_calendar(update, context)
            
            else:
                await self._show_main_menu(update, context)
        
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка в обработке callback: {error_msg}")
            
            if "Message_too_long" in error_msg or "message is too long" in error_msg.lower():
                try:
                    await query.edit_message_text(
                        "❌ Сообщение слишком длинное. Попробуйте другое мероприятие или используйте поиск."
                    )
                except:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="❌ Сообщение слишком длинное. Попробуйте другое мероприятие."
                    )
            else:
                try:
                    await query.edit_message_text(
                        "❌ Произошла ошибка. Возвращаемся в главное меню..."
                    )
                    await self._show_main_menu(update, context)
                except Exception as e2:
                    print(f"❌ Критическая ошибка: {e2}")
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="❌ Произошла ошибка. Используйте /start для перезапуска."
                    )

    async def handle_event_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        try:
            if data.startswith('event_delete_'):
                event_id = data.replace('event_delete_', '')
                result = self.calendar.remove_event(user_id, event_id)
                await query.edit_message_text(result['message'])
                await self.show_calendar(update, context)
            
            elif data.startswith('event_url_'):
                event_id = data.replace('event_url_', '')
                user_events = self.calendar.calendar_events.get(str(user_id), [])
                event = next((e for e in user_events if e['id'] == event_id), None)
                
                if event and event.get('url') and event['url'] not in ['', '#']:
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔗 Перейти на сайт", url=event['url'])
                    ]])
                    await query.edit_message_text(
                        f"🔗 Ссылка на мероприятие:\n\n{event['url']}",
                        reply_markup=keyboard
                    )
                else:
                    await query.edit_message_text("❌ Ссылка на мероприятие недоступна")
            
            elif data == "calendar_back_to_day":
                await self.show_calendar(update, context)
            
            else:
                await query.edit_message_text("❌ Неизвестная команда события")
        
        except Exception as e:
            print(f"❌ Ошибка в обработке события: {e}")
            await query.edit_message_text("❌ Произошла ошибка при обработке события")
                
    async def handle_search_menu(self, update: Update, context: CallbackContext):
        text = update.message.text
        user_id = update.effective_user.id
        
        if text == "🔍 По тематике":
            await self._show_themes_search(update, context)
        
        elif text == "📅 По дате":
            await self._show_date_search(update, context)
        
        elif text == "👥 По аудитории":
            await self._show_audience_search(update, context)
        
        elif text == "🎪 По типу":
            await self._show_type_search(update, context)
        
        elif text == "📍 По локации":
            await self._show_location_search(update, context)
        
        elif text == "🎯 Рекомендованные":
            await self.show_events(update, context)
        
        elif text == "🏠 Главное меню":
            await self._show_main_menu(update, context)
        
        else:
            await update.message.reply_text(
                "Пожалуйста, используйте кнопки меню поиска",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("🔍 По тематике"), KeyboardButton("📅 По дате")],
                    [KeyboardButton("👥 По аудитории"), KeyboardButton("🎪 По типу")],
                    [KeyboardButton("📍 По локации"), KeyboardButton("🎯 Рекомендованные")],
                    [KeyboardButton("🏠 Главное меню")]
                ], resize_keyboard=True)
            )

    async def _toggle_favorite(self, update: Update, context: CallbackContext, user_id: int, page: int):
        events = self.user_events.get(user_id, [])
        if not events or page >= len(events):
            return
        
        event = events[page]
        
        if user_id not in self.user_favorites:
            self.user_favorites[user_id] = []
        
        favorite_titles = [e['title'] for e in self.user_favorites[user_id]]
        
        if event['title'] in favorite_titles:
            self.user_favorites[user_id] = [e for e in self.user_favorites[user_id] if e['title'] != event['title']]
            await update.callback_query.answer("❌ Удалено из избранного")
        else:
            self.user_favorites[user_id].append(event)
            await update.callback_query.answer("⭐ Добавлено в избранное")
        
        await self._show_event_page(update, context, user_id, page)

    async def _add_to_calendar(self, update: Update, context: CallbackContext, event: dict, page: int):
        user_id = update.callback_query.from_user.id
        
        await update.callback_query.answer("📅 Добавляем в календарь...")
        
        result = self.calendar.add_event_to_calendar(event, user_id)
        
        if result['success']:
            keyboard = [
                [InlineKeyboardButton("🎯 Следующее мероприятие", callback_data=f"page_{page}")],
                [InlineKeyboardButton("📅 Мой календарь", callback_data="calendar_today")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(result['message'], reply_markup=reply_markup)
        
        else:
            await update.callback_query.edit_message_text(f"❌ {result['message']}")
        
    async def _show_main_menu(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        main_keyboard = [
            [KeyboardButton("🎯 Рекомендованные мероприятия")],
            [KeyboardButton("🔍 Найти мероприятия"), KeyboardButton("⭐ Избранное")],
            [KeyboardButton("⚙️ Настройки"), KeyboardButton("👤 Профиль")],
            [KeyboardButton("📊 Статистика"), KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        
        role_text = "руководитель" if profile['role'] == 'manager' else "сотрудник"
        text = f"🏠 Главное меню\n\nРоль: {role_text}\n\nВыберите действие:"
        
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            except Exception as e:
                await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)

    async def find_events(self, update: Update, context: CallbackContext):
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
🔍 Поиск мероприятий

Выберите критерий поиска:
• По тематике - AI, Data Science, разработка и т.д.
• По дате - ближайшие мероприятия
• По аудитории - размер мероприятия  
• По типу - конференции, митапы, хакатоны
• По локации - изменить город/район
• Рекомендованные - лучшие предложения

Выберите параметр для поиска:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def show_favorites(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if user_id not in self.user_favorites or not self.user_favorites[user_id]:
            await update.message.reply_text("⭐ У вас пока нет избранных мероприятий")
            return
        
        self.user_events[user_id] = self.user_favorites[user_id]
        await self._show_event_page(update, context, user_id, 0)

    async def show_settings(self, update: Update, context: CallbackContext):
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
⚙️ Настройки

Текущие критерии отбора:
• Локация: {settings['location']}
• Мин. аудитория: {settings['min_audience']} человек
• Приоритетные темы: {', '.join(settings['themes'])}
• Типы мероприятий: {', '.join(settings['event_types'])}
• Уведомления: {'✅ Включены' if settings['notifications'] else '❌ Выключены'}

Выберите параметр для изменения:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def show_stats(self, update: Update, context: CallbackContext):
        events = self.parser.load_events()
        if not events:
            events = await self.parser.parse_events()
        
        stats = self.parser.get_events_statistics()
        filtered_events = self.filter.filter_events(events)
        user_id = update.effective_user.id
        favorites_count = len(self.user_favorites.get(user_id, []))
        
        text = f"""
📊 Статистика мероприятий

📈 Общая статистика:
• Всего мероприятий в базе: {stats['total']}
• Подходящих вам мероприятий: {len(filtered_events)}
• Ваших избранных: {favorites_count}
• Источников данных: {len(stats.get('by_source', {}))}

🎪 Распределение по типам:
"""
        
        for event_type, count in list(stats.get('by_type', {}).items())[:5]:
            text += f"• {event_type}: {count}\n"
        
        text += f"\n📍 Топ источников:\n"
        for source, count in list(stats.get('by_source', {}).items())[:3]:
            text += f"• {source}: {count}\n"
        
        upcoming_events = [e for e in filtered_events if e.get('date') and e['date'] >= datetime.now().strftime('%Y-%m-%d')]
        text += f"\n📅 Ближайшие мероприятия: {len(upcoming_events)}"
        
        await update.message.reply_text(text)

    async def help_command(self, update: Update, context: CallbackContext):
        help_text = """
📋 Доступные команды:

Основные команды:
/start - Главное меню
/events - Рекомендованные мероприятия
/find - Поиск мероприятий
/favorites - Избранные мероприятия
/settings - Настройки критериев
/profile - Настройка профиля
/stats - Статистика
/help - Эта справка

Настройки профиля:
• Роль (руководитель/сотрудник)
• Предпочтительная локация
• Размер аудитории  
• Роль участия
• Интересы

Функции:
• 📅 - Добавление в календарь
• ⭐ - Избранное
• 🔍 - Расширенный поиск
• 📊 - Статистика
        """
        await update.message.reply_text(help_text)

    async def export_events(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if user_id not in self.user_favorites or not self.user_favorites[user_id]:
            await update.message.reply_text("⭐ У вас нет избранных мероприятий для экспорта")
            return
        
        await update.message.reply_text("📦 Создаю файл со всеми избранными мероприятиями...")
        
        events = self.user_favorites[user_id]
        result = self.calendar.create_multiple_events_ics(events, user_id)
        
        if result['success']:
            try:
                with open(result['filepath'], 'rb') as ics_file:
                    await context.bot.send_document(
                        chat_id=update.message.chat_id,
                        document=ics_file,
                        filename=result['filename'],
                        caption=(
                            "📦 Файл со всеми избранными мероприятиями готов!\n\n"
                            f"Содержит: {len(events)} мероприятий\n\n"
                            "📱 Как импортировать:\n"
                            "1. Скачайте файл\n"
                            "2. Откройте его на телефоне\n"
                            "3. Выберите 'Добавить в календарь'\n\n"
                            "Все мероприятия будут добавлены в ваш календарь! ✅"
                        )
                    )
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка отправки файла: {e}")
        else:
            await update.message.reply_text("❌ Ошибка создания файла экспорта")

    async def handle_message(self, update: Update, context: CallbackContext):
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed'] and current_context not in ['role_selection', 'preferences_setup', 
                                                                    'location_preferences', 'audience_preferences',
                                                                    'participation_role_preferences', 'interests_preferences']:
            await self._show_role_selection(update, context)
            return
        
        if current_context in ['role_selection', 'preferences_setup', 'location_preferences', 
                            'audience_preferences', 'participation_role_preferences', 'interests_preferences']:
            await self.handle_profile_setup(update, context)
            return
        
        if current_context == 'profile_edit':
            await self.handle_profile_edit(update, context)
            return
        
        if current_context == 'search_menu':
            await self.handle_search_menu(update, context)
            return
        
        if current_context.startswith('search_'):
            await self.handle_search_criteria(update, context)
            return
        
        if text == "🎯 Рекомендованные мероприятия":
            await self.show_events(update, context)
        
        elif text == "🔍 Найти мероприятия":
            await self.find_events(update, context)
        
        elif text == "⭐ Избранное":
            await self.show_favorites(update, context)
        
        elif text == "⚙️ Настройки":
            await self.show_settings(update, context)
        
        elif text == "👤 Профиль":
            await self.show_profile(update, context)
        
        elif text == "📊 Статистика":
            await self.show_stats(update, context)
        
        elif text == "ℹ️ Помощь":
            await self.help_command(update, context)
        
        elif text == "🏠 Главное меню":
            await self._show_main_menu(update, context)
        
        elif text == "📅 Мой календарь":
            await self.show_calendar(update, context)
        
        else:
            await update.message.reply_text(
                "Используйте кнопки меню или команды:\n"
                "/start - главное меню\n"
                "/profile - настройка профиля\n" 
                "/help - помощь"
            )

    async def handle_search_criteria(self, update: Update, context: CallbackContext):
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        
        if 'search_criteria' not in context.user_data:
            context.user_data['search_criteria'] = {}
        
        if current_context == 'search_themes':
            themes_map = {
                "🤖 AI и ML": "AI и ML",
                "📊 Data Science": "Data Science",
                "💻 Разработка": "Разработка",
                "🔐 Кибербезопасность": "Кибербезопасность",
                "🌐 Цифровая трансформация": "Цифровая трансформация",
                "🎓 Образование": "Образование",
                "🚀 Стартапы": "Стартапы",
                "📈 Бизнес": "Бизнес"
            }
            
            if text in themes_map:
                if 'themes' not in context.user_data['search_criteria']:
                    context.user_data['search_criteria']['themes'] = []
                
                theme = themes_map[text]
                if theme not in context.user_data['search_criteria']['themes']:
                    context.user_data['search_criteria']['themes'].append(theme)
                    await update.message.reply_text(f"✅ Добавлена тема: {theme}")
                else:
                    await update.message.reply_text(f"ℹ️ Тема {theme} уже добавлена")
            
            elif text == "🔍 Найти по темам":
                if 'themes' in context.user_data['search_criteria'] and context.user_data['search_criteria']['themes']:
                    await self._execute_search(update, context, 'themes')
                else:
                    await update.message.reply_text("❌ Пожалуйста, выберите хотя бы одну тему")
            
            elif text == "⬅️ Назад к поиску":
                await self.find_events(update, context)
        
        elif current_context == 'search_date':
            date_map = {
                "📅 Сегодня": "today",
                "📅 Завтра": "tomorrow", 
                "📅 Эта неделя": "this_week",
                "📅 Следующая неделя": "next_week",
                "📅 Этот месяц": "this_month",
                "📅 Следующий месяц": "next_month"
            }
            
            if text in date_map:
                context.user_data['search_criteria']['date_range'] = date_map[text]
                await update.message.reply_text(f"✅ Установлен период: {text}")
            
            elif text == "🔍 Найти по дате":
                if 'date_range' in context.user_data['search_criteria']:
                    await self._execute_search(update, context, 'date')
                else:
                    await update.message.reply_text("❌ Пожалуйста, выберите период")
            
            elif text == "⬅️ Назад к поиску":
                await self.find_events(update, context)
        
        elif current_context == 'search_audience':
            audience_map = {
                "👤 Камерные (до 50)": "Камерные (до 50)",
                "👥 Средние (50-200)": "Средние (50-200)",
                "👨‍👩‍👧‍👦 Крупные (200-500)": "Крупные (200-500)",
                "🏛️ Массовые (500+)": "Массовые (500+)",
                "🌟 Любой размер": "Любой размер"
            }
            
            if text in audience_map:
                context.user_data['search_criteria']['audience'] = audience_map[text]
                await update.message.reply_text(f"✅ Установлен размер аудитории: {audience_map[text]}")
            
            elif text == "🔍 Найти по аудитории":
                if 'audience' in context.user_data['search_criteria']:
                    await self._execute_search(update, context, 'audience')
                else:
                    await update.message.reply_text("❌ Пожалуйста, выберите размер аудитории")
            
            elif text == "⬅️ Назад к поиску":
                await self.find_events(update, context)
        
        elif current_context == 'search_type':
            type_map = {
                "🎤 Конференция": "конференция",
                "👥 Митап": "митап",
                "💻 Хакатон": "хакатон",
                "🎯 Стратегическая сессия": "стратегическая сессия",
                "💬 Круглый стол": "круглый стол",
                "🏛️ Форум": "форум",
                "📚 Семинар": "семинар"
            }
            
            if text in type_map:
                if 'event_types' not in context.user_data['search_criteria']:
                    context.user_data['search_criteria']['event_types'] = []
                
                event_type = type_map[text]
                if event_type not in context.user_data['search_criteria']['event_types']:
                    context.user_data['search_criteria']['event_types'].append(event_type)
                    await update.message.reply_text(f"✅ Добавлен тип: {text}")
                else:
                    await update.message.reply_text(f"ℹ️ Тип {text} уже добавлен")
            
            elif text == "🔍 Найти по типу":
                if 'event_types' in context.user_data['search_criteria'] and context.user_data['search_criteria']['event_types']:
                    await self._execute_search(update, context, 'type')
                else:
                    await update.message.reply_text("❌ Пожалуйста, выберите хотя бы один тип мероприятия")
            
            elif text == "⬅️ Назад к поиску":
                await self.find_events(update, context)
        
        elif current_context == 'search_location':
            location_map = {
                "🏙️ Центр города": "Центр города",
                "🏫 Бизнес-центры": "Бизнес-центры",
                "🎓 Университеты": "Университеты",
                "🏢 Офисы компаний": "Офисы компаний",
                "💻 Онлайн": "Онлайн",
                "📍 Любая локация": "Любая локация"
            }
            
            if text in location_map:
                context.user_data['search_criteria']['location'] = location_map[text]
                await update.message.reply_text(f"✅ Установлена локация: {location_map[text]}")
            
            elif text == "🔍 Найти по локации":
                if 'location' in context.user_data['search_criteria']:
                    await self._execute_search(update, context, 'location')
                else:
                    await update.message.reply_text("❌ Пожалуйста, выберите локацию")
            
            elif text == "⬅️ Назад к поиску":
                await self.find_events(update, context)

    def _filter_events_by_search_criteria(self, events, search_criteria):
        filtered_events = []
        
        for event in events:
            matches = True
            
            if 'themes' in search_criteria and search_criteria['themes']:
                event_themes = event.get('themes', [])
                event_desc = event.get('description', '').lower()
                event_title = event.get('title', '').lower()
                
                theme_match = False
                for search_theme in search_criteria['themes']:
                    search_theme_lower = search_theme.lower()
                    if (any(search_theme_lower in theme.lower() for theme in event_themes) or
                        search_theme_lower in event_title or
                        search_theme_lower in event_desc):
                        theme_match = True
                        break
                
                if not theme_match:
                    matches = False
            
            if 'date_range' in search_criteria and matches:
                event_date = event.get('date', '')
                if event_date:
                    today = datetime.now().date()
                    event_date_obj = None
                    
                    try:
                        for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']:
                            try:
                                event_date_obj = datetime.strptime(event_date, fmt).date()
                                break
                            except ValueError:
                                continue
                    except:
                        event_date_obj = None
                    
                    if event_date_obj:
                        date_range = search_criteria['date_range']
                        
                        if date_range == 'today' and event_date_obj != today:
                            matches = False
                        elif date_range == 'tomorrow' and event_date_obj != today + timedelta(days=1):
                            matches = False
                        elif date_range == 'this_week':
                            week_start = today - timedelta(days=today.weekday())
                            week_end = week_start + timedelta(days=6)
                            if not (week_start <= event_date_obj <= week_end):
                                matches = False
                        elif date_range == 'next_week':
                            next_week_start = today + timedelta(days=7 - today.weekday())
                            next_week_end = next_week_start + timedelta(days=6)
                            if not (next_week_start <= event_date_obj <= next_week_end):
                                matches = False
                        elif date_range == 'this_month' and event_date_obj.month != today.month:
                            matches = False
                        elif date_range == 'next_month':
                            next_month = today.month + 1 if today.month < 12 else 1
                            next_year = today.year if today.month < 12 else today.year + 1
                            if event_date_obj.month != next_month or event_date_obj.year != next_year:
                                matches = False
            
            if 'audience' in search_criteria and matches and search_criteria['audience'] != "Любой размер":
                event_audience = event.get('audience', '')
                if event_audience:
                    import re
                    numbers = re.findall(r'\d+', str(event_audience))
                    if numbers:
                        audience_size = int(numbers[0])
                        
                        audience_ranges = {
                            'Камерные (до 50)': (0, 50),
                            'Средние (50-200)': (50, 200),
                            'Крупные (200-500)': (200, 500),
                            'Массовые (500+)': (500, float('inf'))
                        }
                        
                        if search_criteria['audience'] in audience_ranges:
                            min_aud, max_aud = audience_ranges[search_criteria['audience']]
                            if not (min_aud <= audience_size <= max_aud):
                                matches = False
            
            if 'event_types' in search_criteria and search_criteria['event_types'] and matches:
                event_type = event.get('type', '').lower()
                type_match = any(search_type.lower() in event_type for search_type in search_criteria['event_types'])
                if not type_match:
                    matches = False
            
            if 'location' in search_criteria and matches and search_criteria['location'] != "Любая локация":
                event_location = event.get('location', '').lower()
                location_pref = search_criteria['location'].lower()
                
                location_mapping = {
                    'центр города': ['центр', 'центральный', 'невский', 'адмиралтейск', 'васильевск'],
                    'бизнес-центры': ['бц', 'бизнес-центр', 'бизнес центр', 'деловой'],
                    'университеты': ['университет', 'вуз', 'политех', 'итмо', 'спбгу'],
                    'офисы компаний': ['офис', 'офисе', 'компании', 'сбер', 'яндекс', 'вк'],
                    'онлайн': ['онлайн', 'online', 'zoom', 'webinar']
                }
                
                if location_pref in location_mapping:
                    keywords = location_mapping[location_pref]
                    location_match = any(keyword in event_location for keyword in keywords)
                    if not location_match:
                        matches = False
            
            if matches:
                filtered_events.append(event)
        
        return filtered_events
    
    async def _execute_search(self, update: Update, context: CallbackContext, search_type: str):
        user_id = update.effective_user.id
        
        criteria_text = self._format_search_criteria(context.user_data['search_criteria'])
        await update.message.reply_text(f"🔍 Ищу мероприятия по критериям:\n{criteria_text}")
        
        events = self.parser.load_events()
        if not events:
            events = await self.parser.parse_events()
        
        filtered_events = self._filter_events_by_search_criteria(events, context.user_data['search_criteria'])
        
        if not filtered_events:
            await update.message.reply_text(
                "❌ Не найдено мероприятий по выбранным критериям\n\n"
                "💡 Попробуйте:\n"
                "• Расширить критерии поиска\n"
                "• Выбрать меньше параметров\n"
                "• Использовать другой период\n"
                "• Проверить рекомендованные мероприятия"
            )
            
            context.user_data['search_criteria'] = {}
            self._set_user_context(user_id, 'main_menu')
            return
        
        self.user_events[user_id] = filtered_events[:15]
        
        await update.message.reply_text(f"✅ Найдено мероприятий: {len(filtered_events)}")
        
        await self._show_event_page(update, context, user_id, 0)
        
        context.user_data['search_criteria'] = {}
        self._set_user_context(user_id, 'main_menu')

    def _format_search_criteria(self, criteria):
        if not criteria:
            return "❌ Критерии не выбраны"
        
        text = ""
        
        if 'themes' in criteria and criteria['themes']:
            text += f"• 🎯 Темы: {', '.join(criteria['themes'])}\n"
        
        if 'date_range' in criteria:
            date_map = {
                'today': '📅 Сегодня',
                'tomorrow': '📅 Завтра',
                'this_week': '📅 Эта неделя',
                'next_week': '📅 Следующая неделя',
                'this_month': '📅 Этот месяц',
                'next_month': '📅 Следующий месяц'
            }
            text += f"• {date_map.get(criteria['date_range'], criteria['date_range'])}\n"
        
        if 'audience' in criteria:
            text += f"• 👥 Аудитория: {criteria['audience']}\n"
        
        if 'event_types' in criteria and criteria['event_types']:
            text += f"• 🎪 Типы: {', '.join(criteria['event_types'])}\n"
        
        if 'location' in criteria:
            text += f"• 📍 Локация: {criteria['location']}\n"
        
        return text
    
    async def show_calendar(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        user_calendar = self.calendar.get_user_calendar(user_id)
        events_count = len(user_calendar.get('events', []))
        
        keyboard = self.calendar.create_calendar_keyboard(user_id)
        
        message = f"📅 Ваш календарь мероприятий\n\n"
        message += f"📊 Мероприятий в календаре: {events_count}\n\n"
        message += "Выберите дату для просмотра мероприятий:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=keyboard)
        else:
            await update.message.reply_text(message, reply_markup=keyboard)

    async def handle_calendar_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        try:
            if data.startswith('calendar_prev_'):
                parts = data.split('_')
                if len(parts) >= 4:
                    month = int(parts[2])
                    year = int(parts[3])
                    month -= 1
                    if month < 1:
                        month = 12
                        year -= 1
                    
                    user_calendar = self.calendar.get_user_calendar(user_id, month, year)
                    events_count = len(user_calendar.get('events', []))
                    
                    keyboard = self.calendar.create_calendar_keyboard(user_id, month, year)
                    message = self.calendar.format_calendar_message(month, year, events_count)
                    await query.edit_message_text(message, reply_markup=keyboard)
            
            elif data.startswith('calendar_next_'):
                parts = data.split('_')
                if len(parts) >= 4:
                    month = int(parts[2])
                    year = int(parts[3])
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
                    
                    user_calendar = self.calendar.get_user_calendar(user_id, month, year)
                    events_count = len(user_calendar.get('events', []))
                    
                    keyboard = self.calendar.create_calendar_keyboard(user_id, month, year)
                    message = self.calendar.format_calendar_message(month, year, events_count)
                    await query.edit_message_text(message, reply_markup=keyboard)
            
            elif data.startswith('calendar_day_'):
                parts = data.split('_')
                if len(parts) >= 5:
                    year = int(parts[2])
                    month = int(parts[3])
                    day = int(parts[4])
                    
                    events = self.calendar.get_day_events(user_id, year, month, day)
                    keyboard = self.calendar.create_day_events_keyboard(year, month, day, events)
                    message = self.calendar.format_day_events_message(year, month, day, events)
                    await query.edit_message_text(message, reply_markup=keyboard)
            
            elif data == "calendar_today":
                await self.show_calendar(update, context)
            
            elif data == "calendar_list":
                events = self.calendar.get_events_list(user_id)
                message = self.calendar.format_events_list_message(events)
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("📅 К календарю", callback_data="calendar_back"),
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]])
                await query.edit_message_text(message, reply_markup=keyboard)
            
            elif data.startswith('calendar_event_'):
                event_id = data.replace('calendar_event_', '')
                await self.show_event_details(update, context, event_id)
            
            elif data == "calendar_back":
                await self.show_calendar(update, context)
            
            else:
                await query.edit_message_text("❌ Неизвестная команда календаря")
        
        except Exception as e:
            print(f"❌ Ошибка в обработке календаря: {e}")
            await query.edit_message_text("❌ Произошла ошибка при работе с календарем")

    async def show_event_details(self, update: Update, context: CallbackContext, event_id: str):
        query = update.callback_query
        user_id = query.from_user.id
        
        user_events = self.calendar.calendar_events.get(str(user_id), [])
        event = next((e for e in user_events if e['id'] == event_id), None)
        
        if not event:
            await query.edit_message_text("❌ Событие не найдено")
            return
        
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').strftime('%d.%m.%Y')
        except:
            event_date = event['date']
        
        message = f"🎯 {event['title']}\n\n"
        message += f"📅 Дата: {event_date}\n"
        message += f"📍 Место: {event.get('location', 'Не указано')}\n"
        message += f"🎪 Тип: {event.get('type', 'мероприятие')}\n"
        
        if event.get('description'):
            desc = event['description']
            if len(desc) > 300:
                desc = desc[:300] + "..."
            message += f"\n📝 Описание:\n{desc}\n"
        
        if event.get('url') and event['url'] not in ['', '#']:
            message += f"\n🔗 Сайт: {event['url']}"
        
        message = self._truncate_message(message)
        
        keyboard = self.calendar.create_event_details_keyboard(event_id)
        
        await query.edit_message_text(message, reply_markup=keyboard)

    def run(self):
        if not self.token or self.token == "YOUR_TELEGRAM_BOT_TOKEN":
            print("❌ Укажите TELEGRAM_BOT_TOKEN в config.py")
            return
        
        self.application = Application.builder().token(self.token).build()
        
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("events", self.show_events))
        self.application.add_handler(CommandHandler("find", self.find_events))
        self.application.add_handler(CommandHandler("favorites", self.show_favorites))
        self.application.add_handler(CommandHandler("settings", self.show_settings))
        self.application.add_handler(CommandHandler("profile", self.show_profile))
        self.application.add_handler(CommandHandler("stats", self.show_stats))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("export", self.export_events))
        
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        print("🤖 Telegram бот запущен с системой ролей и персонализированных рекомендаций!")
        print("✅ Новые возможности:")
        print("   • 👔 Выбор роли (руководитель/сотрудник)")
        print("   • 🎯 Персонализированные рекомендации") 
        print("   • 📍 Настройка предпочтений локации")
        print("   • 👥 Настройка размера аудитории")
        print("   • 🎭 Выбор роли участия")
        print("   • 🎯 Настройка интересов")
        
        try:
            import asyncio
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                print("⚠️  Event loop уже запущен, запускаем бота в фоне...")
                loop.create_task(self.application.run_polling())
            else:
                loop.run_until_complete(self.application.run_polling())
                
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен пользователем")
        except Exception as e:
            print(f"❌ Ошибка при запуске бота: {e}")