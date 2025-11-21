import json
import os
import sys
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import config
from src.parsers.event_parser import EventParser
from src.analysis.criteria_filter import CriteriaFilter
from src.calendar_integration.telegram_calendar import TelegramCalendar

class TelegramBot:
    def __init__(self):
        self.token = config.BOT_CONFIG["token"]
        self.admin_password = config.BOT_CONFIG.get("admin_password", "admin123")
        self.manager_password = config.BOT_CONFIG.get("manager_password", "manager123")
        self.parser = EventParser()
        self.filter = CriteriaFilter()
        self.calendar = TelegramCalendar()
        self.application = None
        
        # Система пользователей
        self.user_events = {}
        self.user_favorites = {}
        self.user_settings = {}
        self.user_context = {}
        self.user_profiles = {}
        self.user_auth = {}  # {user_id: {'status': 'authenticated', 'role': 'employee', 'fio': '', 'position': ''}}
        self.pending_registrations = {}  # {user_id: {'fio': '', 'position': '', 'role': ''}}
        self.pending_approvals = {}
        self.managers_list = {}
        
        self.pending_approvals = {}  # {user_id: [{'event': event_data, 'manager_id': manager_id, 'status': 'pending'}]}
        self.user_managers = {}  # {user_id: manager_id} - связь сотрудник -> руководитель
        self.manager_employees = {}  # {manager_id: [user_id]} - связь руководитель -> сотрудники
        
        # Загрузка данных пользователей
        self._load_user_data()
    
    def _load_user_data(self):
        """Загружает данные пользователей из файла"""
        try:
            if os.path.exists('user_data.json'):
                with open('user_data.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_profiles = data.get('profiles', {})
                    self.user_auth = data.get('auth', {})
                    self.managers_list = data.get('managers', {})
        except Exception as e:
            print(f"❌ Ошибка загрузки данных пользователей: {e}")
    
    def _save_user_data(self):
        """Сохраняет данные пользователей в файл"""
        try:
            data = {
                'profiles': self.user_profiles,
                'auth': self.user_auth,
                'managers': self.managers_list
            }
            with open('user_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения данных пользователей: {e}")
    
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
                'setup_completed': False,
                'fio': '',
                'position': '',
                'registration_date': None
            }
        return self.user_profiles[user_id]
    
    def _get_user_auth(self, user_id):
        return self.user_auth.get(user_id, {'status': 'unauthorized', 'role': None})
    
    def _set_user_auth(self, user_id, auth_data):
        self.user_auth[user_id] = auth_data
        self._save_user_data()
    
    def _is_authenticated(self, user_id):
        auth = self._get_user_auth(user_id)
        return auth.get('status') == 'authenticated'
    
    def _is_admin(self, user_id):
        auth = self._get_user_auth(user_id)
        return auth.get('role') == 'admin'
    
    def _is_manager(self, user_id):
        auth = self._get_user_auth(user_id)
        return auth.get('role') == 'manager'
    
    def _is_employee(self, user_id):
        auth = self._get_user_auth(user_id)
        return auth.get('role') == 'employee'
    
    def _set_user_context(self, user_id, context):
        self.user_context[user_id] = context
    
    def _get_user_context(self, user_id):
        return self.user_context.get(user_id, 'main_menu')
    
    async def _require_auth(self, update: Update, context: CallbackContext):
        """Проверяет авторизацию и перенаправляет если не авторизован"""
        user_id = update.effective_user.id
        if not self._is_authenticated(user_id):
            await self._show_auth_menu(update, context)
            return False
        return True
    
    async def _require_admin(self, update: Update, context: CallbackContext):
        """Проверяет права администратора"""
        user_id = update.effective_user.id
        if not self._is_authenticated(user_id) or not self._is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам")
            return False
        return True
    
    async def _show_auth_menu(self, update: Update, context: CallbackContext):
        """Показывает меню авторизации/регистрации"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'auth_menu')
        
        auth_keyboard = [
            [KeyboardButton("🔐 Войти"), KeyboardButton("📝 Зарегистрироваться")],
            [KeyboardButton("❌ Отмена"), KeyboardButton("ℹ️ О боте")]
        ]
        reply_markup = ReplyKeyboardMarkup(auth_keyboard, resize_keyboard=True)
        
        text = """
    🤖 Добро пожаловать в AI-помощник по медиа от Центра исследований и разработки Сбера!

    Для использования бота необходимо:

    🔐 Войти - если у вас уже есть аккаунт
    📝 Зарегистрироваться - создать новый аккаунт

    После регистрации вам будет доступен:
    • Поиск IT-мероприятий в Санкт-Петербурге
    • Персонализированные рекомендации
    • Календарь мероприятий
    • Система согласования с руководителем
    • Статистика и аналитика

    Выберите действие:
            """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def _show_registration_step1(self, update: Update, context: CallbackContext):
        """Первый шаг регистрации - ФИО"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'registration_fio')
        
        registration_keyboard = [
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(registration_keyboard, resize_keyboard=True)
        
        text = """
    📝 Регистрация - Шаг 1 из 3

    Пожалуйста, введите ваше ФИО (Фамилия Имя Отчество):

    Пример: Иванов Иван Иванович

    Для отмены регистрации нажмите кнопку "❌ Отмена"
            """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _show_registration_step2(self, update: Update, context: CallbackContext):
        """Второй шаг регистрации - должность"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'registration_position')
        
        registration_keyboard = [
            [KeyboardButton("⬅️ Назад"), KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(registration_keyboard, resize_keyboard=True)
        
        text = """
    📝 Регистрация - Шаг 2 из 3

    Пожалуйста, введите вашу должность:

    Пример: 
    • Старший разработчик
    • Менеджер проектов
    • Data Scientist
    • Руководитель отдела

    Для возврата к предыдущему шагу нажмите "⬅️ Назад"
    Для отмены регистрации нажмите "❌ Отмена"
            """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _show_registration_step3(self, update: Update, context: CallbackContext):
        """Третий шаг регистрации - выбор роли"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'registration_role')
        
        registration_data = self.pending_registrations.get(user_id, {})
        fio = registration_data.get('fio', '')
        position = registration_data.get('position', '')
        
        role_keyboard = [
            [KeyboardButton("👨‍💼 Сотрудник")],
            [KeyboardButton("👔 Руководитель (требуется пароль)")],
            [KeyboardButton("⬅️ Назад"), KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(role_keyboard, resize_keyboard=True)
        
        text = f"""
    📝 Регистрация - Шаг 3 из 3

    Проверьте введенные данные:
    • ФИО: {fio}
    • Должность: {position}

    Теперь выберите вашу роль:

    👨‍💼 Сотрудник - стандартная роль для участия в мероприятиях
    👔 Руководитель - доступ к системе согласования заявок (требуется пароль)

    Для возврата к предыдущему шагу нажмите "⬅️ Назад"
    Для отмены регистрации нажмите "❌ Отмена"
            """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

        
    async def _show_manager_password(self, update: Update, context: CallbackContext):
        """Запрос пароля для роли руководителя"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'manager_password')
        
        password_keyboard = [
            [KeyboardButton("⬅️ Назад"), KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(password_keyboard, resize_keyboard=True)
        
        text = """
    🔐 Подтверждение роли руководителя

    Для выбора роли руководителя требуется ввести пароль.

    Пожалуйста, введите пароль для роли руководителя:

    (Пароль можно получить у администратора)

    Для возврата к выбору роли нажмите "⬅️ Назад"
    Для отмены регистрации нажмите "❌ Отмена"
            """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def _show_admin_menu(self, update: Update, context: CallbackContext):
        """Меню администратора"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'admin_menu')
        
        admin_keyboard = [
            [KeyboardButton("👥 Управление пользователями"), KeyboardButton("🔑 Сменить пароли")],
            [KeyboardButton("📊 Статистика системы"), KeyboardButton("📢 Рассылка")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(admin_keyboard, resize_keyboard=True)
        
        total_users = len([uid for uid, auth in self.user_auth.items() if auth.get('status') == 'authenticated'])
        managers_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'manager'])
        employees_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'employee'])
        
        text = f"""
👑 Панель администратора

📊 Статистика системы:
• Всего пользователей: {total_users}
• Руководителей: {managers_count}
• Сотрудников: {employees_count}
• Ожидают регистрации: {len(self.pending_registrations)}

Возможности:
• 👥 Управление пользователями - просмотр, редактирование, удаление
• 🔑 Смена паролей - для ролей руководителя и администратора
• 📊 Статистика системы - детальная аналитика
• 📢 Рассылка - отправка сообщений пользователям

Выберите действие:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def _show_user_management(self, update: Update, context: CallbackContext):
        """Управление пользователями"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'user_management')
        
        users_list = []
        for uid, auth in self.user_auth.items():
            if auth.get('status') == 'authenticated':
                profile = self.user_profiles.get(uid, {})
                users_list.append({
                    'user_id': uid,
                    'fio': profile.get('fio', 'Не указано'),
                    'position': profile.get('position', 'Не указано'),
                    'role': auth.get('role', 'Не указана')
                })
        
        users_keyboard = []
        for user in users_list[:10]:  # Показываем первых 10 пользователей
            users_keyboard.append([KeyboardButton(f"👤 {user['fio']} - {user['role']}")])
        
        users_keyboard.extend([
            [KeyboardButton("🔄 Обновить список")],
            [KeyboardButton("⬅️ Назад в админку")]
        ])
        
        reply_markup = ReplyKeyboardMarkup(users_keyboard, resize_keyboard=True)
        
        text = f"""
👥 Управление пользователями

Всего пользователей: {len(users_list)}

Список пользователей (первые 10):
        """
        
        for i, user in enumerate(users_list[:10], 1):
            text += f"\n{i}. {user['fio']} - {user['position']} ({user['role']})"
        
        text += "\n\nВыберите пользователя для управления или обновите список:"
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def _show_password_management(self, update: Update, context: CallbackContext):
        """Управление паролями"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'password_management')
        
        password_keyboard = [
            [KeyboardButton("🔑 Сменить пароль руководителей")],
            [KeyboardButton("👑 Сменить пароль администратора")],
            [KeyboardButton("👀 Показать текущие пароли")],
            [KeyboardButton("⬅️ Назад в админку")]
        ]
        reply_markup = ReplyKeyboardMarkup(password_keyboard, resize_keyboard=True)
        
        text = f"""
🔑 Управление паролями

Текущие настройки паролей:
• Пароль руководителей: {'*' * len(self.manager_password)}
• Пароль администратора: {'*' * len(self.admin_password)}

Возможности:
• Смена пароля для роли руководителя
• Смена пароля администратора
• Просмотр текущих паролей

Выберите действие:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        user_id = user.id
        
        # Проверяем авторизацию
        if not self._is_authenticated(user_id):
            await self._show_auth_menu(update, context)
            return
        
        profile = self._get_user_profile(user_id)
        auth = self._get_user_auth(user_id)
        
        # Для администратора показываем админ-меню
        if self._is_admin(user_id):
            await self._show_admin_menu(update, context)
            return
        
        # Для обычных пользователей - основное меню
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
👤 {profile.get('fio', '')}
💼 {profile.get('position', '')}

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
• Система согласования с руководителем

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
        
        # Добавляем кнопку админки для администраторов
        if self._is_admin(user_id):
            main_keyboard.append([KeyboardButton("👑 Админ панель")])
        
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
            
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def handle_auth(self, update: Update, context: CallbackContext):
        """Обработка меню авторизации"""
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        
        if current_context == 'auth_menu':
            if text == "🔐 Войти":
                await self._show_login(update, context)
            elif text == "📝 Зарегистрироваться":
                await self._show_registration_step1(update, context)
            elif text == "❌ Отмена":
                await update.message.reply_text(
                    "❌ Регистрация/авторизация отменена.\n\n"
                    "Если захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif text == "ℹ️ О боте":
                await self._show_about(update, context)
        
        elif current_context == 'login':
            if text == "⬅️ Назад":
                await self._show_auth_menu(update, context)
            elif text == "❌ Отмена":
                await update.message.reply_text(
                    "❌ Вход отменен.\n\n"
                    "Если захотите войти позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                # Проверяем авторизацию (пока просто пропускаем всех)
                auth_data = {
                    'status': 'authenticated',
                    'role': 'employee',  # По умолчанию сотрудник
                    'login_date': datetime.now().isoformat()
                }
                self._set_user_auth(user_id, auth_data)
                await update.message.reply_text("✅ Вы успешно вошли в систему!")
                await self.start(update, context)
        
        elif current_context == 'registration_fio':
            if text == "❌ Отмена":
                # Очищаем временные данные регистрации
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\n"
                    "Если захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif len(text.split()) >= 2:  # Проверяем что введено ФИО
                if user_id not in self.pending_registrations:
                    self.pending_registrations[user_id] = {}
                self.pending_registrations[user_id]['fio'] = text
                await self._show_registration_step2(update, context)
            else:
                await update.message.reply_text("❌ Пожалуйста, введите ФИО в формате 'Фамилия Имя Отчество'")
        
        elif current_context == 'registration_position':
            if text == "⬅️ Назад":
                await self._show_registration_step1(update, context)
            elif text == "❌ Отмена":
                # Очищаем временные данные регистрации
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\n"
                    "Если захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif user_id in self.pending_registrations:
                self.pending_registrations[user_id]['position'] = text
                await self._show_registration_step3(update, context)
            else:
                await self._show_registration_step1(update, context)
        
        elif current_context == 'registration_role':
            if text == "👨‍💼 Сотрудник":
                if user_id in self.pending_registrations:
                    registration_data = self.pending_registrations[user_id]
                    
                    # Сохраняем профиль
                    profile = self._get_user_profile(user_id)
                    profile['fio'] = registration_data['fio']
                    profile['position'] = registration_data['position']
                    profile['role'] = 'employee'
                    profile['registration_date'] = datetime.now().isoformat()
                    
                    # Авторизуем пользователя
                    auth_data = {
                        'status': 'authenticated',
                        'role': 'employee',
                        'registration_date': datetime.now().isoformat()
                    }
                    self._set_user_auth(user_id, auth_data)
                    
                    # Очищаем временные данные
                    del self.pending_registrations[user_id]
                    
                    await update.message.reply_text(
                        "✅ Регистрация завершена! Вы зарегистрированы как сотрудник.\n\n"
                        "Теперь настроим ваш профиль для персонализированных рекомендаций."
                    )
                    await self._show_role_selection(update, context)
            
            elif text == "👔 Руководитель (требуется пароль)":
                await self._show_manager_password(update, context)
            
            elif text == "⬅️ Назад":
                await self._show_registration_step2(update, context)
            
            elif text == "❌ Отмена":
                # Очищаем временные данные регистрации
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\n"
                    "Если захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
        
        elif current_context == 'manager_password':
            if text == "⬅️ Назад":
                await self._show_registration_step3(update, context)
            elif text == "❌ Отмена":
                # Очищаем временные данные регистрации
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\n"
                    "Если захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif text == self.manager_password:
                if user_id in self.pending_registrations:
                    registration_data = self.pending_registrations[user_id]
                    
                    # Сохраняем профиль
                    profile = self._get_user_profile(user_id)
                    profile['fio'] = registration_data['fio']
                    profile['position'] = registration_data['position']
                    profile['role'] = 'manager'
                    profile['registration_date'] = datetime.now().isoformat()
                    
                    # Авторизуем пользователя
                    auth_data = {
                        'status': 'authenticated',
                        'role': 'manager',
                        'registration_date': datetime.now().isoformat()
                    }
                    self._set_user_auth(user_id, auth_data)
                    
                    # Добавляем в список руководителей
                    self.managers_list[user_id] = {
                        'fio': registration_data['fio'],
                        'position': registration_data['position'],
                        'registration_date': datetime.now().isoformat()
                    }
                    
                    # Очищаем временные данные
                    del self.pending_registrations[user_id]
                    
                    await update.message.reply_text(
                        "✅ Регистрация завершена! Вы зарегистрированы как руководитель.\n\n"
                        "Теперь настроим ваш профиль для персонализированных рекомендаций."
                    )
                    await self._show_role_selection(update, context)
                else:
                    await update.message.reply_text("❌ Ошибка регистрации. Начните заново.")
                    await self._show_auth_menu(update, context)
            else:
                await update.message.reply_text("❌ Неверный пароль. Попробуйте еще раз или выберите роль сотрудника.")
        
        # Обработка контекстов настройки профиля
        elif current_context == 'role_selection':
            if text in ["👔 Руководитель", "👨‍💼 Сотрудник"]:
                profile = self._get_user_profile(user_id)
                profile['role'] = 'manager' if text == "👔 Руководитель" else 'employee'
                await self._show_location_preferences(update, context)
            elif text == "🏠 Главное меню":
                await self.start(update, context)
        
        elif current_context == 'location_preferences':
            if text in ["📍 Санкт-Петербург", "🌐 Онлайн"]:
                profile = self._get_user_profile(user_id)
                profile['preferences']['location_preference'] = text
                await self._show_audience_preferences(update, context)
            elif text == "⬅️ Назад":
                await self._show_role_selection(update, context)
            elif text == "🏠 Главное меню":
                await self.start(update, context)
        
        elif current_context == 'audience_preferences':
            if text in ["👥 Маленькие (до 50 человек)", "👥 Средние (50-200 человек)", 
                    "👥 Крупные (200+ человек)", "👥 Любого размера"]:
                profile = self._get_user_profile(user_id)
                profile['preferences']['audience_preference'] = text
                await self._show_participation_role_preferences(update, context)
            elif text == "⬅️ Назад":
                await self._show_location_preferences(update, context)
            elif text == "🏠 Главное меню":
                await self.start(update, context)
        
        elif current_context == 'participation_role_preferences':
            if text in ["🎤 Спикер", "👥 Участник", "👀 Наблюдатель", "🏗️ Организатор"]:
                profile = self._get_user_profile(user_id)
                profile['preferences']['participation_role'] = text
                await self._show_interests_preferences(update, context)
            elif text == "⬅️ Назад":
                await self._show_audience_preferences(update, context)
            elif text == "🏠 Главное меню":
                await self.start(update, context)
        
        elif current_context == 'interests_preferences':
            if text == "✅ Завершить настройку":
                await self._complete_profile_setup(update, context)
            elif text == "🏠 Главное меню":
                await self.start(update, context)
            elif text in ["🤖 Искусственный интеллект", "📊 Data Science", "🔐 Кибербезопасность",
                        "☁️ Облачные технологии", "📱 Мобильная разработка", "🌐 Веб-разработка",
                        "🚀 Стартапы и инновации", "💼 Бизнес и менеджмент"]:
                # Добавляем интерес если его еще нет
                profile = self._get_user_profile(user_id)
                if text not in profile['preferences']['interests']:
                    profile['preferences']['interests'].append(text)
                    await update.message.reply_text(f"✅ Добавлено: {text}")
    
    async def _show_login(self, update: Update, context: CallbackContext):
        """Показывает меню входа"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'login')
        
        login_keyboard = [
            [KeyboardButton("⬅️ Назад"), KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(login_keyboard, resize_keyboard=True)
        
        text = """
    🔐 Вход в систему

    Для входа в систему просто нажмите любую кнопку ниже.

    Система автоматически определит ваш аккаунт по ID Telegram.

    Если у вас еще нет аккаунта, нажмите "Назад" и выберите "Зарегистрироваться".

    Для возврата в меню авторизации нажмите "⬅️ Назад"
    Для отмены входа нажмите "❌ Отмена"
            """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def _show_about(self, update: Update, context: CallbackContext):
        """Показывает информацию о боте"""
        text = """
ℹ️ О боте

🤖 AI-помощник по медиа от Центра исследований и разработки Сбера

🎯 Основные возможности:
• Поиск IT-мероприятий в Санкт-Петербурге
• Персонализированные рекомендации
• Система ролей (сотрудник/руководитель/администратор)
• Календарь мероприятий
• Система согласования участия
• Статистика и аналитика

👥 Система ролей:
• 👨‍💼 Сотрудник - поиск и участие в мероприятиях
• 👔 Руководитель - согласование заявок сотрудников
• 👑 Администратор - управление системой

📞 Поддержка:
По вопросам работы бота обращайтесь к администратору системы.
        """
        
        await update.message.reply_text(text)
    
    async def handle_admin_commands(self, update: Update, context: CallbackContext):
        """Обработка команд администратора"""
        text = update.message.text
        user_id = update.effective_user.id
        
        if not await self._require_admin(update, context):
            return
        
        current_context = self._get_user_context(user_id)
        
        if current_context == 'admin_menu':
            if text == "👥 Управление пользователями":
                await self._show_user_management(update, context)
            elif text == "🔑 Сменить пароли":
                await self._show_password_management(update, context)
            elif text == "📊 Статистика системы":
                await self._show_system_stats(update, context)
            elif text == "📢 Рассылка":
                await self._show_broadcast_menu(update, context)
            elif text == "🏠 Главное меню":
                await self.start(update, context)
        
        elif current_context == 'user_management':
            if text == "🔄 Обновить список":
                await self._show_user_management(update, context)
            elif text == "⬅️ Назад в админку":
                await self._show_admin_menu(update, context)
            elif text.startswith("👤 "):
                # Обработка выбора конкретного пользователя
                await self._show_user_details(update, context, text)
        
        elif current_context == 'password_management':
            if text == "🔑 Сменить пароль руководителей":
                await self._change_manager_password(update, context)
            elif text == "👑 Сменить пароль администратора":
                await self._change_admin_password(update, context)
            elif text == "👀 Показать текущие пароли":
                await self._show_current_passwords(update, context)
            elif text == "⬅️ Назад в админку":
                await self._show_admin_menu(update, context)
        
        elif current_context == 'change_manager_password':
            if len(text) >= 4:
                self.manager_password = text
                # Сохраняем в конфиг
                config.BOT_CONFIG["manager_password"] = text
                await update.message.reply_text(f"✅ Пароль руководителей изменен на: {text}")
                await self._show_password_management(update, context)
            else:
                await update.message.reply_text("❌ Пароль должен содержать минимум 4 символа")
        
        elif current_context == 'change_admin_password':
            if len(text) >= 4:
                self.admin_password = text
                # Сохраняем в конфиг
                config.BOT_CONFIG["admin_password"] = text
                await update.message.reply_text(f"✅ Пароль администратора изменен на: {text}")
                await self._show_password_management(update, context)
            else:
                await update.message.reply_text("❌ Пароль должен содержать минимум 4 символа")
    
    async def _change_manager_password(self, update: Update, context: CallbackContext):
        """Смена пароля руководителей"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'change_manager_password')
        
        text = """
🔑 Смена пароля руководителей

Введите новый пароль для роли руководителя:

⚠️ Пароль должен содержать минимум 4 символа
⚠️ Сообщите новый пароль всем руководителям
        """
        
        await update.message.reply_text(text)
    
    async def _change_admin_password(self, update: Update, context: CallbackContext):
        """Смена пароля администратора"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'change_admin_password')
        
        text = """
👑 Смена пароля администратора

Введите новый пароль для роли администратора:

⚠️ Пароль должен содержать минимум 4 символа
⚠️ Сохраните пароль в надежном месте
        """
        
        await update.message.reply_text(text)
    
    async def _show_current_passwords(self, update: Update, context: CallbackContext):
        """Показывает текущие пароли"""
        text = f"""
🔑 Текущие пароли системы:

• Пароль руководителей: {self.manager_password}
• Пароль администратора: {self.admin_password}

⚠️ Никому не сообщайте эти пароли!
        """
        
        await update.message.reply_text(text)
    
    async def _show_system_stats(self, update: Update, context: CallbackContext):
        """Показывает статистику системы"""
        total_users = len([uid for uid, auth in self.user_auth.items() if auth.get('status') == 'authenticated'])
        managers_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'manager'])
        employees_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'employee'])
        admins_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'admin'])
        
        # Статистика по мероприятиям
        events = self.parser.load_events()
        events_stats = self.parser.get_events_statistics() if events else {'total': 0}
        
        text = f"""
📊 Статистика системы

👥 Пользователи:
• Всего: {total_users}
• Администраторов: {admins_count}
• Руководителей: {managers_count}
• Сотрудников: {employees_count}

🎪 Мероприятия:
• Всего в базе: {events_stats.get('total', 0)}
• Ожидают согласования: {len(self.pending_approvals)}

📅 Активность:
• Зарегистрировано сегодня: {len([uid for uid, auth in self.user_auth.items() 
                                 if auth.get('registration_date') and 
                                 datetime.fromisoformat(auth['registration_date']).date() == datetime.now().date()])}
        """
        
        await update.message.reply_text(text)
    
    async def _show_broadcast_menu(self, update: Update, context: CallbackContext):
        """Меню рассылки"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'broadcast_menu')
        
        broadcast_keyboard = [
            [KeyboardButton("📢 Всем пользователям")],
            [KeyboardButton("👔 Только руководителям")],
            [KeyboardButton("👨‍💼 Только сотрудникам")],
            [KeyboardButton("⬅️ Назад в админку")]
        ]
        reply_markup = ReplyKeyboardMarkup(broadcast_keyboard, resize_keyboard=True)
        
        text = """
📢 Система рассылки

Выберите целевую аудиторию для рассылки:

• 📢 Всем пользователям - общие уведомления
• 👔 Только руководителям - служебная информация
• 👨‍💼 Только сотрудникам - информация о мероприятиях

После выбора аудитории введите текст сообщения.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def _show_user_details(self, update: Update, context: CallbackContext, user_info: str):
        """Показывает детали пользователя"""
        # Здесь можно реализовать просмотр и редактирование конкретного пользователя
        await update.message.reply_text("👤 Функция просмотра пользователя в разработке")
    
    # ========== МЕТОДЫ НАСТРОЙКИ ПРОФИЛЯ ==========
    
    async def _show_role_selection(self, update: Update, context: CallbackContext):
        """Показывает выбор роли для настройки профиля"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'role_selection')
        
        role_keyboard = [
            [KeyboardButton("👔 Руководитель")],
            [KeyboardButton("👨‍💼 Сотрудник")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(role_keyboard, resize_keyboard=True)
        
        text = """
👤 Настройка профиля - Шаг 1 из 5

Выберите вашу основную роль для участия в мероприятиях:

👔 <b>Руководитель</b>
• Участие в стратегических сессиях
• Выступления на конференциях
• Нетворкинг с другими лидерами

👨‍💼 <b>Сотрудник</b>
• Технические воркшопы и митапы
• Хакатоны и конкурсы
• Образовательные мероприятия

Это поможет мне рекомендовать наиболее подходящие мероприятия.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_location_preferences(self, update: Update, context: CallbackContext):
        """Показывает выбор локации (только СПб и онлайн)"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'location_preferences')
        
        location_keyboard = [
            [KeyboardButton("📍 Санкт-Петербург"), KeyboardButton("🌐 Онлайн")],
            [KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, resize_keyboard=True)
        
        text = """
👤 Настройка профиля - Шаг 2 из 5

Выберите предпочтительную локацию мероприятий:

📍 <b>Санкт-Петербург</b>
• Офлайн мероприятия в вашем городе
• Личное участие и нетворкинг
• Локальные конференции и митапы

🌐 <b>Онлайн</b>
• Дистанционные мероприятия
• Участие из любого места
• Вебинары и онлайн-конференции

Рекомендуем выбрать "📍 Санкт-Петербург" для участия в локальных IT-мероприятиях.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_audience_preferences(self, update: Update, context: CallbackContext):
        """Показывает выбор размера аудитории"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'audience_preferences')
        
        audience_keyboard = [
            [KeyboardButton("👥 Маленькие (до 50 человек)"), KeyboardButton("👥 Средние (50-200 человек)")],
            [KeyboardButton("👥 Крупные (200+ человек)"), KeyboardButton("👥 Любого размера")],
            [KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(audience_keyboard, resize_keyboard=True)
        
        text = """
👤 Настройка профиля - Шаг 3 из 5

Выберите предпочтительный размер мероприятий:

👥 <b>Маленькие</b> (до 50 человек)
• Камерная атмосфера
• Глубокое нетворкинг
• Воркшопы и мастер-классы

👥 <b>Средние</b> (50-200 человек)  
• Баланс масштаба и интимности
• Разнообразные форматы
• Хорошие возможности для общения

👥 <b>Крупные</b> (200+ человек)
• Конференции и форумы
• Значительные спикеры
• Широкий охват тематик

👥 <b>Любого размера</b> - все варианты
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_participation_role_preferences(self, update: Update, context: CallbackContext):
        """Показывает выбор роли участия"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'participation_role_preferences')
        
        role_keyboard = [
            [KeyboardButton("🎤 Спикер"), KeyboardButton("👥 Участник")],
            [KeyboardButton("👀 Наблюдатель"), KeyboardButton("🏗️ Организатор")],
            [KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(role_keyboard, resize_keyboard=True)
        
        text = """
👤 Настройка профиля - Шаг 4 из 5

Выберите вашу предпочтительную роль на мероприятиях:

🎤 <b>Спикер</b> - выступления и доклады
👥 <b>Участник</b> - активное участие в обсуждениях
👀 <b>Наблюдатель</b> - изучение и анализ
🏗️ <b>Организатор</b> - помощь в проведении

Это поможет найти мероприятия где вы сможете максимально проявить себя.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _show_interests_preferences(self, update: Update, context: CallbackContext):
        """Показывает выбор интересов"""
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'interests_preferences')
        
        interests_keyboard = [
            [KeyboardButton("🤖 Искусственный интеллект"), KeyboardButton("📊 Data Science")],
            [KeyboardButton("🔐 Кибербезопасность"), KeyboardButton("☁️ Облачные технологии")],
            [KeyboardButton("📱 Мобильная разработка"), KeyboardButton("🌐 Веб-разработка")],
            [KeyboardButton("🚀 Стартапы и инновации"), KeyboardButton("💼 Бизнес и менеджмент")],
            [KeyboardButton("✅ Завершить настройку"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(interests_keyboard, resize_keyboard=True)
        
        text = """
👤 Настройка профиля - Шаг 5 из 5

Выберите тематики которые вас интересуют:

🤖 <b>Искусственный интеллект</b> - ML, нейросети, компьютерное зрение
📊 <b>Data Science</b> - анализ данных, визуализация, Big Data
🔐 <b>Кибербезопасность</b> - защита данных, pentesting
☁️ <b>Облачные технологии</b> - AWS, Azure, Google Cloud
📱 <b>Мобильная разработка</b> - iOS, Android, кроссплатформа
🌐 <b>Веб-разработка</b> - фронтенд, бэкенд, fullstack
🚀 <b>Стартапы и инновации</b> - венчурные инвестиции, pitching
💼 <b>Бизнес и менеджмент</b> - управление, стратегия, Agile

Выберите несколько наиболее интересных тематик.
Нажмите "✅ Завершить настройку" когда закончите.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    async def _complete_profile_setup(self, update: Update, context: CallbackContext):
        """Завершает настройку профиля"""
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        # Отмечаем что настройка завершена
        profile['setup_completed'] = True
        self._save_user_data()
        
        # Показываем подтверждение
        text = f"""
✅ <b>Настройка профиля завершена!</b>

👤 <b>Ваш профиль:</b>
• Роль: {'руководитель' if profile['role'] == 'manager' else 'сотрудник'}
• Локация: {profile['preferences']['location_preference']}
• Размер мероприятий: {profile['preferences']['audience_preference']}
• Роль участия: {profile['preferences']['participation_role']}
• Интересы: {', '.join(profile['preferences']['interests'])}

🎯 <b>Теперь я могу рекомендовать:</b>
• Мероприятия под вашу роль и интересы
• События в предпочитаемой локации
• Подходящие по формату участия
• Релевантные тематики

💡 Вы всегда можете изменить настройки в разделе 👤 Профиль

Начните с поиска мероприятий через 🔍 Поиск или 🎯 Рекомендованные!
        """
        
        await update.message.reply_text(text, parse_mode='HTML')
        await self.start(update, context)
    
    # ========== МЕТОД FIND_EVENTS И СВЯЗАННЫЕ МЕТОДЫ ==========
    
    async def find_events(self, update: Update, context: CallbackContext):
        """Поиск мероприятий по критериям"""
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed']:
            await update.message.reply_text(
                "❌ Пожалуйста, сначала завершите настройку профиля в разделе 👤 Профиль"
            )
            return
        
        await update.message.reply_text("🔍 Ищу подходящие мероприятия...")
        
        try:
            # Получаем мероприятия
            events = await self.parser.parse_events()
            
            # Фильтруем по критериям
            filtered_events = self.filter.filter_events(events)
            
            if not filtered_events:
                await update.message.reply_text(
                    "❌ Не найдено подходящих мероприятий.\n\n"
                    "💡 Попробуйте:\n"
                    "• Изменить критерии в 👤 Профиль\n"
                    "• Расширить интересы\n"
                    "• Использовать другие настройки поиска"
                )
                return
            
            # Сохраняем найденные мероприятия для пользователя
            self.user_events[user_id] = filtered_events
            
            # Показываем результаты
            await self._show_search_results(update, context, filtered_events[:10])
            
        except Exception as e:
            print(f"❌ Ошибка поиска мероприятий: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при поиске мероприятий.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
    
    async def _show_search_results(self, update: Update, context: CallbackContext, events):
        """Показывает результаты поиска"""
        if not events:
            await update.message.reply_text("❌ Не найдено мероприятий")
            return
        
        message = "🎯 <b>Найденные мероприятия:</b>\n\n"
        
        for i, event in enumerate(events, 1):
            # Получаем цвет приоритета
            priority_score = event.get('priority_score', 0)
            priority_color = "🟢" if priority_score >= 8 else "🟡" if priority_score >= 6 else "🟠"
            
            message += (
                f"{i}. {priority_color} <b>{event['title']}</b>\n"
                f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                f"   🎪 {event.get('type', 'мероприятие')} | ⭐ {priority_score}/10\n"
            )
            
            # Добавляем тематики если есть
            themes = event.get('themes', [])
            if themes:
                message += f"   🏷️ {', '.join(themes[:3])}\n"
            
            message += "\n"
        
        # Создаем клавиатуру с кнопками
        keyboard = []
        for i in range(len(events)):
            keyboard.append([
                InlineKeyboardButton(
                    f"📅 Добавить {i+1}",
                    callback_data=f"add_calendar_{i}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search"),
            InlineKeyboardButton("📋 Все мероприятия", callback_data="show_all_events")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def handle_callback(self, update: Update, context: CallbackContext):
        """Обработчик callback'ов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith('add_calendar_'):
            # Добавление мероприятия в календарь
            event_index = int(data.split('_')[2])
            await self._add_event_to_calendar(query, context, event_index)
        
        elif data == 'new_search':
            # Новый поиск
            await self.find_events_callback(query, context)
        
        elif data == 'show_all_events':
            # Показать все мероприятия
            await self._show_all_events(query, context)
        
        elif data == 'main_menu':
            # Возврат в главное меню
            await self._show_main_menu_callback(query, context)
    
    async def _add_event_to_calendar(self, query, context, event_index):
        """Добавляет мероприятие в календарь пользователя"""
        try:
            user_id = query.from_user.id
            
            if user_id not in self.user_events:
                await query.edit_message_text("❌ Данные мероприятий устарели. Выполните поиск заново.")
                return
            
            events = self.user_events[user_id]
            
            if event_index < len(events):
                event = events[event_index]
                result = self.calendar.add_event_to_calendar(event, user_id)
                
                if result['success']:
                    await query.edit_message_text(
                        result['message'],
                        parse_mode='HTML'
                    )
                else:
                    await query.edit_message_text(
                        "❌ Не удалось добавить мероприятие в календарь"
                    )
            else:
                await query.edit_message_text("❌ Мероприятие не найдено")
                
        except Exception as e:
            print(f"❌ Ошибка добавления в календарь: {e}")
            await query.edit_message_text("❌ Ошибка при добавлении в календарь")
    
    async def find_events_callback(self, query, context):
        """Обработчик callback'а поиска мероприятий"""
        try:
            await query.edit_message_text("🔍 Ищу подходящие мероприятия...")
            
            user_id = query.from_user.id
            events = await self.parser.parse_events()
            filtered_events = self.filter.filter_events(events)
            
            if not filtered_events:
                await query.edit_message_text(
                    "❌ Не найдено подходящих мероприятий.\n\n"
                    "💡 Попробуйте изменить критерии поиска."
                )
                return
            
            self.user_events[user_id] = filtered_events
            await self._show_search_results_callback(query, context, filtered_events[:10])
            
        except Exception as e:
            print(f"❌ Ошибка поиска мероприятий: {e}")
            await query.edit_message_text("❌ Ошибка при поиске мероприятий")
    
    async def _show_search_results_callback(self, query, context, events):
        """Показывает результаты поиска в callback'е"""
        if not events:
            await query.edit_message_text("❌ Не найдено мероприятий")
            return
        
        message = "🎯 <b>Найденные мероприятия:</b>\n\n"
        
        for i, event in enumerate(events, 1):
            priority_score = event.get('priority_score', 0)
            priority_color = "🟢" if priority_score >= 8 else "🟡" if priority_score >= 6 else "🟠"
            
            message += (
                f"{i}. {priority_color} <b>{event['title']}</b>\n"
                f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                f"   🎪 {event.get('type', 'мероприятие')} | ⭐ {priority_score}/10\n"
            )
            
            themes = event.get('themes', [])
            if themes:
                message += f"   🏷️ {', '.join(themes[:3])}\n"
            
            message += "\n"
        
        keyboard = []
        for i in range(len(events)):
            keyboard.append([
                InlineKeyboardButton(
                    f"📅 Добавить {i+1}",
                    callback_data=f"add_calendar_{i}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search"),
            InlineKeyboardButton("📋 Все мероприятия", callback_data="show_all_events")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def _show_all_events(self, query, context):
        """Показывает все мероприятия"""
        try:
            user_id = query.from_user.id
            
            if user_id not in self.user_events:
                await query.edit_message_text("❌ Данные мероприятий устарели. Выполните поиск заново.")
                return
            
            events = self.user_events[user_id]
            
            if not events:
                await query.edit_message_text("❌ Не найдено мероприятий")
                return
            
            message = "📋 <b>Все найденные мероприятия:</b>\n\n"
            
            for i, event in enumerate(events[:15], 1):  # Ограничиваем 15 мероприятиями
                priority_score = event.get('priority_score', 0)
                priority_color = "🟢" if priority_score >= 8 else "🟡" if priority_score >= 6 else "🟠"
                
                message += (
                    f"{i}. {priority_color} <b>{event['title']}</b>\n"
                    f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                    f"   ⭐ {priority_score}/10\n\n"
                )
            
            if len(events) > 15:
                message += f"... и ещё {len(events) - 15} мероприятий\n\n"
            
            message += "🎯 Используйте кнопку 'Новый поиск' для точного поиска"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
        except Exception as e:
            print(f"❌ Ошибка показа всех мероприятий: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке мероприятий")
    
    async def _show_main_menu_callback(self, query, context):
        """Показывает главное меню в callback'е"""
        try:
            user_id = query.from_user.id
            profile = self._get_user_profile(user_id)
            
            role_greeting = {
                'manager': "👔 Руководитель",
                'employee': "👨‍💼 Сотрудник"
            }
            
            welcome_text = f"""
🏠 Главное меню

{role_greeting.get(profile['role'], '👤 Пользователь')}
👤 {profile.get('fio', '')}

Выберите действие:
            """
            
            main_keyboard = [
                [KeyboardButton("🎯 Рекомендованные мероприятия"), KeyboardButton("📅 Мой календарь")],
                [KeyboardButton("🔍 Найти мероприятия"), KeyboardButton("⭐ Избранное")],
                [KeyboardButton("⚙️ Настройки"), KeyboardButton("👤 Профиль")],
                [KeyboardButton("📊 Статистика"), KeyboardButton("ℹ️ Помощь")]
            ]
            
            if self._is_admin(user_id):
                main_keyboard.append([KeyboardButton("👑 Админ панель")])
            
            reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
            
            await query.edit_message_text(welcome_text, reply_markup=reply_markup)
            
        except Exception as e:
            print(f"❌ Ошибка показа главного меню: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке меню")
    
    # ========== ОСТАЛЬНЫЕ МЕТОДЫ ==========
    
    async def show_events(self, update: Update, context: CallbackContext):
        if not await self._require_auth(update, context):
            return
        
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
        
        filtered_events = self.filter.filter_events(events)
        
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
        
        self.user_events[user_id] = filtered_events[:15]
        
        await self._show_search_results(update, context, filtered_events[:10])
    
    async def show_profile(self, update: Update, context: CallbackContext):
        if not await self._require_auth(update, context):
            return
        
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
    • ФИО: {profile.get('fio', 'Не указано')}
    • Должность: {profile.get('position', 'Не указано')}
    • Роль: {role_text}
    • Локация: {profile['preferences']['location_preference'] or 'не указана'}
    • Размер мероприятий: {profile['preferences']['audience_preference'] or 'не указан'}
    • Роль участия: {profile['preferences']['participation_role'] or 'не указана'}
    • Интересы: {', '.join(profile['preferences']['interests']) if profile['preferences']['interests'] else 'не указаны'}

    Выберите что хотите изменить:
        """
        
        await update.message.reply_text(profile_text, reply_markup=reply_markup)
        self._set_user_context(user_id, 'profile_edit')
        
    async def _reset_profile(self, update: Update, context: CallbackContext):
        """Сбрасывает настройки профиля"""
        user_id = update.effective_user.id
        
        reset_keyboard = [
            [KeyboardButton("✅ Да, сбросить"), KeyboardButton("❌ Нет, отмена")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(reset_keyboard, resize_keyboard=True)
        
        text = """
    🔄 Сброс профиля

    ⚠️ Вы уверены, что хотите сбросить настройки профиля?

    Это действие:
    • Удалит все ваши предпочтения
    • Сбросит настройки рекомендаций
    • Потребуется заново пройти настройку профиля

    Ваши личные данные (ФИО, должность, роль) сохранятся.

    Подтвердите сброс профиля:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        self._set_user_context(user_id, 'profile_reset_confirm')

    async def handle_message(self, update: Update, context: CallbackContext):
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        
        # Обработка меню авторизации
        if current_context in ['auth_menu', 'login', 'registration_fio', 'registration_position', 
                            'registration_role', 'manager_password']:
            await self.handle_auth(update, context)
            return
        
        # Обработка админ-меню
        if self._is_admin(user_id) and current_context in ['admin_menu', 'user_management', 
                                                        'password_management', 'change_manager_password',
                                                        'change_admin_password', 'broadcast_menu']:
            await self.handle_admin_commands(update, context)
            return
        
        # Обработка контекстов настройки профиля
        if current_context in ['role_selection', 'location_preferences', 'audience_preferences',
                            'participation_role_preferences', 'interests_preferences']:
            await self.handle_auth(update, context)
            return
        
        # Обработка редактирования профиля
        if current_context == 'profile_edit':
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
                await self._reset_profile(update, context)
            elif text == "🏠 Главное меню":
                await self.start(update, context)
            elif text == "🎯 Настроить профиль":
                await self._show_role_selection(update, context)
            else:
                await update.message.reply_text(
                    "Используйте кнопки меню для изменения профиля или вернитесь в главное меню.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("🏠 Главное меню")]
                    ], resize_keyboard=True)
                )
            return
        if current_context == 'profile_reset_confirm':
            if text == "✅ Да, сбросить":
                profile = self._get_user_profile(user_id)
                # Сохраняем только основные данные
                fio = profile.get('fio', '')
                position = profile.get('position', '')
                role = profile.get('role', 'employee')
                
                # Сбрасываем профиль
                self.user_profiles[user_id] = {
                    'role': role,
                    'preferences': {
                        'location_preference': None,
                        'audience_preference': None,
                        'participation_role': None,
                        'interests': []
                    },
                    'setup_completed': False,
                    'fio': fio,
                    'position': position,
                    'registration_date': profile.get('registration_date')
                }
                self._save_user_data()
                
                await update.message.reply_text(
                    "✅ Настройки профиля сброшены!\n\n"
                    "Теперь нужно заново настроить профиль для персонализированных рекомендаций.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("🎯 Настроить профиль")]
                    ], resize_keyboard=True)
                )
                self._set_user_context(user_id, 'main_menu')
                
            elif text == "❌ Нет, отмена" or text == "🏠 Главное меню":
                await self.show_profile(update, context)
            else:
                await update.message.reply_text(
                    "Пожалуйста, используйте кнопки для подтверждения сброса профиля.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("✅ Да, сбросить"), KeyboardButton("❌ Нет, отмена")],
                        [KeyboardButton("🏠 Главное меню")]
                    ], resize_keyboard=True)
                )
            return
            
        # Проверяем авторизацию для остальных команд
        if not await self._require_auth(update, context):
            return
        
        # Обработка основного меню
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed'] and current_context not in ['role_selection', 'preferences_setup', 
                                                                    'location_preferences', 'audience_preferences',
                                                                    'participation_role_preferences', 'interests_preferences']:
            await self._show_role_selection(update, context)
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
            await self.start(update, context)
        
        elif text == "📅 Мой календарь":
            await self.show_calendar(update, context)
        
        elif text == "👑 Админ панель" and self._is_admin(user_id):
            await self._show_admin_menu(update, context)
        
        else:
            await update.message.reply_text(
                "Используйте кнопки меню или команды:\n"
                "/start - главное меню\n"
                "/profile - настройка профиля\n" 
                "/help - помощь"
            )
    async def show_favorites(self, update: Update, context: CallbackContext):
        """Показывает избранные мероприятия"""
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        
        if user_id not in self.user_favorites or not self.user_favorites[user_id]:
            await update.message.reply_text(
                "⭐ <b>Ваши избранные мероприятия</b>\n\n"
                "📭 У вас пока нет избранных мероприятий\n\n"
                "💡 Чтобы добавить мероприятие в избранное:\n"
                "1. Найдите мероприятия через 🔍 Поиск\n"
                "2. Нажмите кнопку '⭐ Добавить в избранное'\n"
                "3. Все добавленные мероприятия появятся здесь",
                parse_mode='HTML'
            )
            return
        
        favorites = self.user_favorites[user_id]
        message = "⭐ <b>Ваши избранные мероприятия</b>\n\n"
        
        for i, event in enumerate(favorites[:10], 1):
            message += (
                f"{i}. <b>{event['title']}</b>\n"
                f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                f"   🎪 {event.get('type', 'мероприятие')}\n\n"
            )
        
        if len(favorites) > 10:
            message += f"... и ещё {len(favorites) - 10} мероприятий\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить избранное", callback_data="clear_favorites")],
            [InlineKeyboardButton("🎯 Найти мероприятия", callback_data="new_search")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')

    async def show_settings(self, update: Update, context: CallbackContext):
        """Показывает настройки"""
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        settings_keyboard = [
            [KeyboardButton("🔔 Уведомления"), KeyboardButton("🎯 Критерии поиска")],
            [KeyboardButton("📊 Статистика"), KeyboardButton("🔐 Безопасность")],
            [KeyboardButton("🔄 Сброс данных"), KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(settings_keyboard, resize_keyboard=True)
        
        text = """
⚙️ <b>Настройки системы</b>

Здесь вы можете настроить работу бота под ваши потребности:

🔔 <b>Уведомления</b>
• Настройка напоминаний о мероприятиях
• Уведомления о новых событиях

🎯 <b>Критерии поиска</b>
• Изменение параметров поиска
• Настройка приоритетов

📊 <b>Статистика</b>
• Просмотр вашей активности
• Анализ участия в мероприятиях

🔐 <b>Безопасность</b>
• Настройки конфиденциальности
• Управление данными

🔄 <b>Сброс данных</b>
• Очистка истории поиска
• Сброс избранного

Выберите категорию настроек:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        self._set_user_context(user_id, 'settings_menu')

    async def show_stats(self, update: Update, context: CallbackContext):
        """Показывает статистику"""
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        # Статистика пользователя
        favorites_count = len(self.user_favorites.get(user_id, []))
        events_found = len(self.user_events.get(user_id, []))
        
        # Получаем мероприятия для анализа
        events = await self.parser.parse_events()
        filtered_events = self.filter.filter_events(events)
        
        # Анализ по тематикам
        theme_stats = {}
        for event in filtered_events[:20]:  # Анализируем топ-20
            for theme in event.get('themes', []):
                theme_stats[theme] = theme_stats.get(theme, 0) + 1
        
        top_themes = sorted(theme_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        
        text = f"""
📊 <b>Ваша статистика</b>

👤 <b>Профиль:</b>
• Роль: {'руководитель' if profile['role'] == 'manager' else 'сотрудник'}
• В системе с: {profile.get('registration_date', 'Недавно')}

📈 <b>Активность:</b>
• Найдено мероприятий: {events_found}
• В избранном: {favorites_count}
• Рекомендовано сегодня: {len(filtered_events)}

🎯 <b>Топ тематик:</b>
"""
        
        for theme, count in top_themes:
            text += f"• {theme}: {count} мероприятий\n"
        
        text += f"""
📅 <b>Ближайшие мероприятия:</b>
• На этой неделе: {len([e for e in filtered_events if self._is_event_this_week(e)])}
• В этом месяце: {len([e for e in filtered_events if self._is_event_this_month(e)])}

💡 <b>Рекомендации:</b>
• Попробуйте расширить интересы для большего выбора
• Регулярно проверяйте обновления мероприятий
        """
        
        await update.message.reply_text(text, parse_mode='HTML')

    async def help_command(self, update: Update, context: CallbackContext):
        """Показывает помощь"""
        help_text = """
📖 <b>Помощь по AI-помощнику по медиа</b>

🤖 <b>О боте:</b>
Я помогаю сотрудникам Сбера находить и планировать участие в IT-мероприятиях Санкт-Петербурга.

🎯 <b>Основные команды:</b>
• /start - главное меню
• /find - поиск мероприятий
• /events - рекомендованные мероприятия
• /favorites - избранные мероприятия
• /profile - настройка профиля
• /stats - ваша статистика
• /help - эта справка

📋 <b>Как начать:</b>
1. 🔐 Зарегистрируйтесь через меню
2. 👔 Настройте профиль и предпочтения
3. 🔍 Ищите мероприятия через поиск
4. 📅 Добавляйте в календарь и избранное
5. 📊 Отслеживайте статистику участия

🎪 <b>Типы мероприятий:</b>
• Конференции и форумы
• Митапы и воркшопы
• Хакатоны и конкурсы
• Образовательные мероприятия

🔧 <b>Поддержка:</b>
По техническим вопросам и предложениям обращайтесь к администратору системы.

🚀 <b>Начните с поиска мероприятий!</b>
        """
        await update.message.reply_text(help_text, parse_mode='HTML')
    def _is_event_upcoming(self, event_date_str):
        """Проверяет, является ли мероприятие предстоящим"""
        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            return event_date >= today
        except:
            return False

    async def show_calendar(self, update: Update, context: CallbackContext):
        """Показывает календарь"""
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        
        # Получаем мероприятия пользователя из календаря
        user_events = self.get_calendar_events(user_id)
        
        if not user_events:
            text = """
    📅 <b>Ваш календарь мероприятий</b>

    📭 В вашем календаре пока нет мероприятий

    💡 <b>Как добавить мероприятия:</b>
    1. Найдите мероприятия через 🔍 Поиск
    2. Нажмите кнопку "📅 Добавить в календарь"
    3. Мероприятия появятся здесь

    🎯 <b>Преимущества календаря:</b>
    • Автоматические напоминания
    • Планирование участия
    • Отслеживание дат мероприятий
    • Управление расписанием

    Начните с поиска подходящих мероприятий!
            """
            keyboard = [
                [InlineKeyboardButton("🔍 Найти мероприятия", callback_data="new_search")],
                [InlineKeyboardButton("🎯 Рекомендованные", callback_data="show_events")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
            return
        
        # Показываем мероприятия из календаря
        text = "📅 <b>Ваш календарь мероприятий</b>\n\n"
        
        for i, event in enumerate(user_events[:10], 1):
            try:
                event_date = datetime.strptime(event['date'], '%Y-%m-%d')
                today = datetime.now().date()
                event_date_date = event_date.date()
                days_left = (event_date_date - today).days
                
                if days_left == 0:
                    days_text = "🎯 СЕГОДНЯ"
                elif days_left == 1:
                    days_text = "🚀 ЗАВТРА"
                elif days_left < 0:
                    days_text = "✅ ПРОШЛО"
                else:
                    days_text = f"⏳ Через {days_left} дн."
                
                text += (
                    f"{i}. <b>{event['title']}</b>\n"
                    f"   📅 {event['date']} ({days_text})\n"
                    f"   📍 {event.get('location', 'Не указано')}\n"
                )
                
                # Добавляем тип мероприятия если есть
                event_type = event.get('type', '')
                if event_type:
                    text += f"   🎪 {event_type}\n"
                
                text += "\n"
                
            except Exception as e:
                print(f"❌ Ошибка обработки мероприятия: {e}")
                continue
        
        if len(user_events) > 10:
            text += f"<i>... и ещё {len(user_events) - 10} мероприятий</i>\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить календарь", callback_data="clear_calendar")],
            [InlineKeyboardButton("🔍 Найти мероприятия", callback_data="new_search")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_calendar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    async def export_events(self, update: Update, context: CallbackContext):
        """Экспорт мероприятий"""
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        
        text = """
📤 <b>Экспорт мероприятий</b>

Вы можете экспортировать ваши мероприятия в различных форматах:

📅 <b>Форматы экспорта:</b>
• Google Calendar - автоматическая синхронизация
• Файл .ics - совместим с любыми календарями
• Excel таблица - для анализа и отчетности
• PDF документ - для печати и презентаций

🔧 <b>Что можно экспортировать:</b>
• Рекомендованные мероприятия
• Избранные события
• Весь календарь
• Статистику участия

💡 <b>Как использовать:</b>
1. Выберите тип экспорта
2. Укажите период и фильтры
3. Скачайте готовый файл

Выберите тип экспорта:
        """
        
        keyboard = [
            [KeyboardButton("📅 Экспорт в Google Calendar")],
            [KeyboardButton("📁 Экспорт в .ics файл")],
            [KeyboardButton("📊 Экспорт в Excel")],
            [KeyboardButton("📄 Экспорт в PDF")],
            [KeyboardButton("🏠 Главное меню")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        self._set_user_context(user_id, 'export_menu')

    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========

    def _is_event_this_week(self, event):
        """Проверяет, находится ли мероприятие на этой неделе"""
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return start_of_week.date() <= event_date.date() <= end_of_week.date()
        except:
            return False

    def _is_event_this_month(self, event):
        """Проверяет, находится ли мероприятие в этом месяце"""
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
            today = datetime.now()
            return event_date.month == today.month and event_date.year == today.year
        except:
            return False

    def _filter_events_by_profile(self, events, profile):
        """Фильтрует мероприятия по профилю пользователя"""
        if not events:
            return []
        
        filtered_events = []
        
        for event in events:
            # Проверяем локацию
            location_match = self._check_location_match(event, profile)
            
            # Проверяем тематики
            theme_match = self._check_theme_match(event, profile)
            
            # Проверяем тип мероприятия
            type_match = self._check_type_match(event, profile)
            
            # Если мероприятие подходит по всем критериям
            if location_match and theme_match and type_match:
                filtered_events.append(event)
        
        return filtered_events

    def _check_location_match(self, event, profile):
        """Проверяет соответствие локации"""
        location_pref = profile['preferences'].get('location_preference', '')
        event_location = event.get('location', '').lower()
        
        if not location_pref:
            return True
        
        # Для онлайн мероприятий
        if location_pref == "🌐 Онлайн" and any(word in event_location for word in ['онлайн', 'online', 'вебинар', 'webinar']):
            return True
        
        # Для Санкт-Петербурга
        if location_pref == "📍 Санкт-Петербург" and any(word in event_location for word in ['санкт-петербург', 'спб', 'петербург', 'питер']):
            return True
        
        return False

    def _check_theme_match(self, event, profile):
        """Проверяет соответствие тематик"""
        user_interests = profile['preferences'].get('interests', [])
        
        if not user_interests:
            return True
        
        event_themes = event.get('themes', [])
        event_description = event.get('description', '').lower()
        event_title = event.get('title', '').lower()
        
        # Проверяем совпадение тематик
        for interest in user_interests:
            interest_lower = interest.lower()
            
            # Проверяем в тематиках
            for theme in event_themes:
                if interest_lower in theme.lower():
                    return True
            
            # Проверяем в описании
            if interest_lower in event_description:
                return True
            
            # Проверяем в заголовке
            if interest_lower in event_title:
                return True
        
        return False

    def _check_type_match(self, event, profile):
        """Проверяет соответствие типа мероприятия"""
        role = profile['preferences'].get('participation_role', '')
        event_type = event.get('type', '').lower()
        
        if not role:
            return True
        
        # Для спикеров предпочтительны конференции с возможностью выступления
        if role == 'speaker' and any(t in event_type for t in ['конференция', 'форум', 'семинар']):
            return True
        
        # Для организаторов - любые мероприятия
        if role == 'organizer':
            return True
        
        # Для наблюдателей - все типы
        if role == 'observer':
            return True
        
        # Для участников - все кроме организационных
        if role == 'participant' and 'организацион' not in event_type:
            return True
        
        return True

    def _add_personalized_recommendations(self, events, profile):
        """Добавляет персонализированные рекомендации"""
        if not events:
            return []
        
        # Добавляем вес рекомендаций на основе профиля
        for event in events:
            personal_score = 0
            
            # Вес за соответствие локации
            if self._check_location_match(event, profile):
                personal_score += 30
            
            # Вес за соответствие тематикам
            if self._check_theme_match(event, profile):
                personal_score += 40
            
            # Вес за соответствие роли
            if self._check_type_match(event, profile):
                personal_score += 30
            
            # Добавляем к общему приоритету
            event['personal_score'] = personal_score
            event['total_priority'] = event.get('priority_score', 0) + (personal_score / 10)
        
        # Сортируем по общему приоритету
        events.sort(key=lambda x: x.get('total_priority', 0), reverse=True)
        
        return events

    async def _show_event_page(self, update, context, user_id, page):
        """Показывает страницу мероприятий"""
        if user_id not in self.user_events or not self.user_events[user_id]:
            await update.message.reply_text("❌ Нет мероприятий для показа")
            return
        
        events = self.user_events[user_id]
        start_idx = page * 5
        end_idx = start_idx + 5
        
        if start_idx >= len(events):
            await update.message.reply_text("📭 Это все мероприятия")
            return
        
        current_events = events[start_idx:end_idx]
        
        message = f"🎯 <b>Мероприятия (страница {page + 1})</b>\n\n"
        
        for i, event in enumerate(current_events, start_idx + 1):
            priority_score = event.get('priority_score', 0)
            priority_color = "🟢" if priority_score >= 8 else "🟡" if priority_score >= 6 else "🟠"
            
            message += (
                f"{i}. {priority_color} <b>{event['title']}</b>\n"
                f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                f"   🎪 {event.get('type', 'мероприятие')} | ⭐ {priority_score}/10\n"
            )
            
            themes = event.get('themes', [])
            if themes:
                message += f"   🏷️ {', '.join(themes[:3])}\n"
            
            message += "\n"
        
        # Создаем клавиатуру навигации
        keyboard = []
        
        # Кнопки для каждого мероприятия на странице
        for i in range(len(current_events)):
            global_idx = start_idx + i
            keyboard.append([
                InlineKeyboardButton(f"📅 Добавить {global_idx + 1}", callback_data=f"add_calendar_{global_idx}"),
                InlineKeyboardButton(f"⭐ В избранное {global_idx + 1}", callback_data=f"add_favorite_{global_idx}")
            ])
        
        # Кнопки навигации по страницам
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page - 1}"))
        
        if end_idx < len(events):
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page + 1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([
            InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='HTML')

    # ========== ОБНОВЛЕННЫЙ HANDLE_CALLBACK ==========

    async def handle_callback(self, update: Update, context: CallbackContext):
        """Обработчик callback'ов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith('add_calendar_'):
            # Добавление мероприятия в календарь
            event_index = int(data.split('_')[2])
            await self._add_event_to_calendar(query, context, event_index)
        
        elif data.startswith('add_favorite_'):
            # Добавление мероприятия в избранное
            event_index = int(data.split('_')[2])
            await self._add_event_to_favorites(query, context, event_index)
        
        elif data.startswith('page_'):
            # Навигация по страницам
            page = int(data.split('_')[1])
            await self._show_event_page(query, context, user_id, page)
        
        elif data == 'new_search':
            # Новый поиск
            await self.find_events_callback(query, context)
        
        elif data == 'show_all_events':
            # Показать все мероприятия
            await self._show_all_events(query, context)
        
        elif data == 'main_menu':
            # Возврат в главное меню
            await self._show_main_menu_callback(query, context)
        
        elif data == 'clear_favorites':
            # Очистка избранного
            await self._clear_favorites(query, context)
        
        elif data == 'show_events':
            # Показать мероприятия
            await self.show_events_callback(query, context)
        
        elif data == 'refresh_calendar':
            # Обновить календарь
            await self.show_calendar_callback(query, context)
        
        elif data == 'clear_calendar':
            # Очистка календаря
            await self._clear_calendar(query, context)

    async def _clear_calendar(self, query, context):
        """Очищает календарь пользователя"""
        user_id = query.from_user.id
        
        try:
            calendar_file = 'telegram_calendar.json'
            if os.path.exists(calendar_file):
                with open(calendar_file, 'r', encoding='utf-8') as f:
                    calendar_data = json.load(f)
                
                if str(user_id) in calendar_data:
                    del calendar_data[str(user_id)]
                    
                    with open(calendar_file, 'w', encoding='utf-8') as f:
                        json.dump(calendar_data, f, ensure_ascii=False, indent=2)
                    
                    await query.edit_message_text(
                        "✅ Календарь очищен!\n\n"
                        "Все мероприятия удалены из вашего календаря."
                    )
                else:
                    await query.edit_message_text("📭 Ваш календарь уже пуст")
            else:
                await query.edit_message_text("📭 Календарь не найден")
                
        except Exception as e:
            print(f"❌ Ошибка очистки календаря: {e}")
            await query.edit_message_text("❌ Ошибка при очистке календаря")

    async def _add_event_to_favorites(self, query, context, event_index):
        """Добавляет мероприятие в избранное"""
        try:
            user_id = query.from_user.id
            
            if user_id not in self.user_events:
                await query.edit_message_text("❌ Данные мероприятий устарели. Выполните поиск заново.")
                return
            
            events = self.user_events[user_id]
            
            if event_index < len(events):
                event = events[event_index]
                
                if user_id not in self.user_favorites:
                    self.user_favorites[user_id] = []
                
                # Проверяем, нет ли уже в избранном
                if not any(fav['title'] == event['title'] and fav['date'] == event['date'] 
                          for fav in self.user_favorites[user_id]):
                    self.user_favorites[user_id].append(event)
                    await query.edit_message_text(
                        f"✅ <b>Мероприятие добавлено в избранное!</b>\n\n"
                        f"🎯 {event['title']}\n"
                        f"📅 {event['date']}\n\n"
                        f"⭐ Теперь оно будет в вашем списке избранных мероприятий",
                        parse_mode='HTML'
                    )
                else:
                    await query.edit_message_text("✅ Это мероприятие уже в избранном")
            else:
                await query.edit_message_text("❌ Мероприятие не найдено")
                
        except Exception as e:
            print(f"❌ Ошибка добавления в избранное: {e}")
            await query.edit_message_text("❌ Ошибка при добавлении в избранное")

    async def _clear_favorites(self, query, context):
        """Очищает избранные мероприятия"""
        user_id = query.from_user.id
        
        if user_id in self.user_favorites:
            self.user_favorites[user_id] = []
            await query.edit_message_text("✅ Избранные мероприятия очищены")
        else:
            await query.edit_message_text("📭 В избранном и так пусто")

    async def show_events_callback(self, query, context):
        """Показывает мероприятия в callback'е"""
        try:
            user_id = query.from_user.id
            await query.edit_message_text("🔍 Ищу рекомендованные мероприятия...")
            
            events = await self.parser.parse_events()
            filtered_events = self.filter.filter_events(events)
            
            if not filtered_events:
                await query.edit_message_text(
                    "❌ Не найдено подходящих мероприятий.\n\n"
                    "💡 Попробуйте изменить критерии в профиле."
                )
                return
            
            self.user_events[user_id] = filtered_events
            await self._show_event_page(query, context, user_id, 0)
            
        except Exception as e:
            print(f"❌ Ошибка показа мероприятий: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке мероприятий")

    async def show_calendar_callback(self, query, context):
        """Показывает календарь в callback'е"""
        try:
            user_id = query.from_user.id
            await self.show_calendar(query, context)
        except Exception as e:
            print(f"❌ Ошибка показа календаря: {e}")
            await query.edit_message_text("❌ Ошибка при загрузке календаря")
    
    def run(self):
        """Надежный синхронный запуск бота"""
        try:
            # Создаем новое приложение и запускаем его
            self.application = Application.builder().token(self.token).build()
            
            # Регистрируем обработчики
            self._setup_handlers()
            
            print("🤖 Telegram бот запущен!")
            print("=" * 60)
            print("Используйте /start для начала работы")
            print("Для остановки нажмите Ctrl+C")
            print("=" * 60)
            
            # Запускаем polling с правильной обработкой event loop
            self.application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен пользователем")
        except Exception as e:
            print(f"❌ Ошибка при запуске бота: {e}")
            import traceback
            traceback.print_exc()
    
    async def _run_bot(self):
        """Внутренний асинхронный метод запуска"""
        try:
            # Создаем приложение
            self.application = Application.builder().token(self.token).build()
            
            # Регистрируем обработчики
            self._setup_handlers()
            
            print("🤖 Telegram бот запущен!")
            print("=" * 60)
            
            # Запускаем polling
            await self.application.run_polling()
            
        except Exception as e:
            print(f"❌ Ошибка в _run_bot: {e}")
            raise

    def _setup_handlers(self):
        """Настройка всех обработчиков"""
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("events", self.show_events))
        self.application.add_handler(CommandHandler("find", self.find_events))
        self.application.add_handler(CommandHandler("favorites", self.show_favorites))
        self.application.add_handler(CommandHandler("settings", self.show_settings))
        self.application.add_handler(CommandHandler("profile", self.show_profile))
        self.application.add_handler(CommandHandler("stats", self.show_stats))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("export", self.export_events))
        self.application.add_handler(CommandHandler("admin", self._show_admin_menu))
        self.application.add_handler(CommandHandler("calendar", self.show_calendar))
        
        # Callback queries
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Сообщения
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))