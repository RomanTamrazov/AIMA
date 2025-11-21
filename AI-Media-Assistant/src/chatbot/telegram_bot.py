import json
import os
import sys
from datetime import datetime, timedelta, time 
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import asyncio
import pytz 
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

        self.work_time_start = time(9, 0)
        self.work_time_end = time(18, 0)
        self.timezone = pytz.timezone('Europe/Moscow')
        
        self.user_events = {}
        self.user_favorites = {}
        self.user_settings = {}
        self.user_context = {}
        self.user_profiles = {}
        self.user_auth = {}
        self.pending_registrations = {}
        self.pending_approvals = {}
        self.managers_list = {}
        self.pending_notifications = {}
        self._load_pending_notifications()

        self.pending_approvals = {}
        self.user_managers = {}
        self.manager_employees = {}
        
        self._load_user_data()
        
    def _load_user_data(self):
        """Загружает данные пользователей из файла"""
        try:
            file_path = '/Users/roman/AIMA/AI-Media-Assistant/user_data.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.user_profiles = data.get('profiles', {})
                        self.user_auth = data.get('auth', {})
                        self.managers_list = data.get('managers', {})
                        self.user_managers = data.get('user_managers', {})
                        self.manager_employees = data.get('manager_employees', {})
                        
                        # Конвертируем ключи user_managers и manager_employees в строки для consistency
                        if self.user_managers:
                            self.user_managers = {str(k): str(v) for k, v in self.user_managers.items()}
                        if self.manager_employees:
                            self.manager_employees = {str(k): [str(i) for i in v] for k, v in self.manager_employees.items()}
                            
                    else:
                        print("⚠️ Файл user_data.json пустой")
                        self.user_profiles = {}
                        self.user_auth = {}
                        self.managers_list = {}
                        self.user_managers = {}
                        self.manager_employees = {}
            else:
                print("⚠️ Файл user_data.json не найден")
                self.user_profiles = {}
                self.user_auth = {}
                self.managers_list = {}
                self.user_managers = {}
                self.manager_employees = {}
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка декодирования JSON: {e}")
            try:
                if os.path.exists(file_path):
                    backup_name = f'/Users/roman/AIMA/AI-Media-Assistant/user_data_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                    os.rename(file_path, backup_name)
                    print(f"📦 Создана резервная копия: {backup_name}")
            except:
                pass
            self.user_profiles = {}
            self.user_auth = {}
            self.managers_list = {}
            self.user_managers = {}
            self.manager_employees = {}
        except Exception as e:
            print(f"❌ Ошибка загрузки данных пользователей: {e}")
            self.user_profiles = {}
            self.user_auth = {}
            self.managers_list = {}
            self.user_managers = {}
            self.manager_employees = {}

    def _save_user_data(self):
        """Сохраняет данные пользователей в файл"""
        try:
            data = {
                'profiles': self.user_profiles,
                'auth': self.user_auth,
                'managers': self.managers_list,
                'user_managers': self.user_managers,
                'manager_employees': self.manager_employees
            }
            
            # Используем абсолютный путь к корню проекта
            file_path = '/Users/roman/AIMA/AI-Media-Assistant/user_data.json'
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("✅ Данные пользователей сохранены")
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
    
    def _is_work_time(self):
        try:
            now = datetime.now(self.timezone)
            current_time = now.time()
            current_weekday = now.weekday()
            
            is_work_day = current_weekday < 5
            is_work_time = self.work_time_start <= current_time <= self.work_time_end
            
            return is_work_day and is_work_time
        except Exception as e:
            print(f"❌ Ошибка проверки рабочего времени: {e}")
            return True
    
    def _get_next_work_time_message(self):
        now = datetime.now(self.timezone)
        current_time = now.time()
        current_weekday = now.weekday()
        
        if current_weekday >= 5:
            days_until_monday = 7 - current_weekday
            next_work_day = now + timedelta(days=days_until_monday)
            next_work_date = next_work_day.strftime('%d.%m.%Y')
            return f"⏰ Следующий рабочий день: {next_work_date} в {self.work_time_start.strftime('%H:%M')}"
        
        elif current_time < self.work_time_start:
            return f"⏰ Рабочий день начинается сегодня в {self.work_time_start.strftime('%H:%M')}"
        
        elif current_time > self.work_time_end:
            next_work_day = now + timedelta(days=1)
            if next_work_day.weekday() >= 5:
                days_until_monday = 7 - next_work_day.weekday()
                next_work_day += timedelta(days=days_until_monday)
            next_work_date = next_work_day.strftime('%d.%m.%Y')
            return f"⏰ Следующий рабочий день: {next_work_date} в {self.work_time_start.strftime('%H:%M')}"
        
        return None
    
    async def _send_manager_notification(self, context, manager_id, approval_text, reply_markup):
        try:
            if self._is_work_time():
                await context.bot.send_message(
                    chat_id=manager_id,
                    text=approval_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return True
            else:
                if manager_id not in self.pending_notifications:
                    self.pending_notifications[manager_id] = []
                
                self.pending_notifications[manager_id].append({
                    'text': approval_text,
                    'reply_markup': reply_markup,
                    'created_at': datetime.now().isoformat()
                })
                
                self._save_pending_notifications()
                
                next_work_time_msg = self._get_next_work_time_message()
                return False, next_work_time_msg
                
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления руководителю: {e}")
            return False, None
    
    async def _send_delayed_notifications(self, context, manager_id):
        try:
            if manager_id in self.pending_notifications and self.pending_notifications[manager_id]:
                notifications = self.pending_notifications[manager_id].copy()
                
                for notification in notifications:
                    try:
                        if context and hasattr(context, 'bot'):
                            await context.bot.send_message(
                                chat_id=manager_id,
                                text=notification['text'],
                                reply_markup=notification.get('reply_markup'),
                                parse_mode='HTML'
                            )
                            self.pending_notifications[manager_id].remove(notification)
                    except Exception as e:
                        print(f"❌ Ошибка отправки отложенного уведомления: {e}")
                
                self._save_pending_notifications()
                    
        except Exception as e:
            print(f"❌ Ошибка отправки отложенных уведомлений: {e}")
    
    def _save_pending_notifications(self):
        """Сохраняет отложенные уведомления в файл"""
        try:
            serializable_notifications = {}
            for manager_id, notifications in self.pending_notifications.items():
                serializable_notifications[manager_id] = []
                for notification in notifications:
                    serializable_notification = {
                        'text': notification['text'],
                        'created_at': notification['created_at']
                    }
                    if 'reply_markup' in notification and notification['reply_markup']:
                        keyboard_data = []
                        for row in notification['reply_markup'].inline_keyboard:
                            row_data = []
                            for button in row:
                                row_data.append({
                                    'text': button.text,
                                    'callback_data': button.callback_data,
                                    'url': button.url
                                })
                            keyboard_data.append(row_data)
                        serializable_notification['keyboard'] = keyboard_data
                    
                    serializable_notifications[manager_id].append(serializable_notification)
            
            # Используем абсолютный путь
            file_path = '/Users/roman/AIMA/AI-Media-Assistant/pending_notifications.json'
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_notifications, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"❌ Ошибка сохранения отложенных уведомлений: {e}")
    
    def _load_pending_notifications(self):
        """Загружает отложенные уведомления из файла"""
        try:
            file_path = '/Users/roman/AIMA/AI-Media-Assistant/pending_notifications.json'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        serializable_notifications = json.loads(content)
                    else:
                        serializable_notifications = {}
            else:
                serializable_notifications = {}
            
            self.pending_notifications = {}
            for manager_id, notifications in serializable_notifications.items():
                self.pending_notifications[manager_id] = []
                for notification in notifications:
                    loaded_notification = {
                        'text': notification['text'],
                        'created_at': notification.get('created_at', datetime.now().isoformat())
                    }
                    
                    if 'keyboard' in notification:
                        keyboard = []
                        for row_data in notification['keyboard']:
                            row = []
                            for button_data in row_data:
                                if 'url' in button_data and button_data['url']:
                                    row.append(InlineKeyboardButton(
                                        text=button_data['text'],
                                        url=button_data['url']
                                    ))
                                else:
                                    row.append(InlineKeyboardButton(
                                        text=button_data['text'],
                                        callback_data=button_data['callback_data']
                                    ))
                            keyboard.append(row)
                        loaded_notification['reply_markup'] = InlineKeyboardMarkup(keyboard)
                    
                    self.pending_notifications[manager_id].append(loaded_notification)
                            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка декодирования JSON: {e}")
            self.pending_notifications = {}
        except Exception as e:
            print(f"❌ Ошибка загрузки отложенных уведомлений: {e}")
            self.pending_notifications = {}
    
    async def _require_auth(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if not self._is_authenticated(user_id):
            await self._show_auth_menu(update, context)
            return False
        return True
    
    async def _require_admin(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if not self._is_authenticated(user_id) or not self._is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам")
            return False
        return True
    
    async def _show_auth_menu(self, update: Update, context: CallbackContext):
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
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'registration_role')
        
        registration_data = self.pending_registrations.get(user_id, {})
        fio = registration_data.get('fio', '')
        position = registration_data.get('position', '')
        
        role_keyboard = [
            [KeyboardButton("👨‍💼 Сотрудник")],
            [KeyboardButton("👔 Руководитель (требуется пароль)")],
            [KeyboardButton("👑 Администратор (требуется пароль)")],
            [KeyboardButton("⬅️ Назад"), KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(role_keyboard, resize_keyboard=True)
        
        text = f"""
    📝 Регистрация - Шаг 3 из 3

    Проверьте введенные данные:
    • ФИО: {fio}
    • Должность: {position}

    Теперь выберите вашу роль:

    👨‍💼 <b>Сотрудник</b> - стандартная роль для участия в мероприятиях
    👔 <b>Руководитель</b> - доступ к системе согласования заявок (требуется пароль)
    👑 <b>Администратор</b> - полный доступ к управлению системой (требуется пароль)

    Для возврата к предыдущему шагу нажмите "⬅️ Назад"
    Для отмены регистрации нажмите "❌ Отмена"
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
        
    async def _show_manager_password(self, update: Update, context: CallbackContext):
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
        
        # Статистика по назначениям руководителей
        assigned_employees = len(self.user_managers)
        unassigned_employees = employees_count - assigned_employees
        
        text = f"""
    👑 Панель администратора

    📊 Статистика системы:
    • Всего пользователей: {total_users}
    • Руководителей: {managers_count}
    • Сотрудников: {employees_count}
    • С назначенными руководителями: {assigned_employees}
    • Без руководителей: {unassigned_employees}
    • Ожидают регистрации: {len(self.pending_registrations)}

    Возможности:
    • 👥 Управление пользователями - просмотр, редактирование, назначение руководителей
    • 🔑 Смена паролей - для ролей руководителя и администратора
    • 📊 Статистика системы - детальная аналитика
    • 📢 Рассылка - отправка сообщений пользователям

    Выберите действие:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def start(self, update: Update, context: CallbackContext):
        user = update.effective_user
        user_id = user.id
        
        if not self._is_authenticated(user_id):
            await self._show_auth_menu(update, context)
            return
        
        profile = self._get_user_profile(user_id)
        auth = self._get_user_auth(user_id)
        
        if self._is_admin(user_id):
            await self._show_admin_menu(update, context)
            return
        
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
        
        if self._is_manager(user_id):
            main_keyboard.append([KeyboardButton("📋 Заявки на согласование")])
        
        if self._is_admin(user_id):
            main_keyboard.append([KeyboardButton("👑 Админ панель")])
        
        reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
            
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def _show_admin_password(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'admin_password')
        
        password_keyboard = [
            [KeyboardButton("⬅️ Назад"), KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(password_keyboard, resize_keyboard=True)
        
        text = """
    👑 Подтверждение роли администратора

    Для выбора роли администратора требуется ввести пароль.

    Пожалуйста, введите пароль для роли администратора:

    (Пароль можно получить у текущего администратора системы)

    Для возврата к выбору роли нажмите "⬅️ Назад"
    Для отмены регистрации нажмите "❌ Отмена"
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def handle_auth(self, update: Update, context: CallbackContext):
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
                    "❌ Регистрация/авторизация отменена.\n\nЕсли захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif text == "ℹ️ О боте":
                await self._show_about(update, context)
        
        elif current_context == 'login':
            if text == "⬅️ Назад":
                await self._show_auth_menu(update, context)
            elif text == "❌ Отмена":
                await update.message.reply_text(
                    "❌ Вход отменен.\n\nЕсли захотите войти позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                auth_data = {
                    'status': 'authenticated',
                    'role': 'employee',
                    'login_date': datetime.now().isoformat()
                }
                self._set_user_auth(user_id, auth_data)
                await update.message.reply_text("✅ Вы успешно вошли в систему!")
                await self.start(update, context)
        
        elif current_context == 'registration_fio':
            if text == "❌ Отмена":
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\nЕсли захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif len(text.split()) >= 2:
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
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\nЕсли захотите зарегистрироваться позже, используйте команду /start",
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
                    
                    profile = self._get_user_profile(user_id)
                    profile['fio'] = registration_data['fio']
                    profile['position'] = registration_data['position']
                    profile['role'] = 'employee'
                    profile['registration_date'] = datetime.now().isoformat()
                    
                    auth_data = {
                        'status': 'authenticated',
                        'role': 'employee',
                        'registration_date': datetime.now().isoformat()
                    }
                    self._set_user_auth(user_id, auth_data)
                    
                    del self.pending_registrations[user_id]
                    
                    await update.message.reply_text(
                        "✅ Регистрация завершена! Вы зарегистрированы как сотрудник.\n\nТеперь настроим ваш профиль для персонализированных рекомендаций."
                    )
                    await self._show_role_selection(update, context)
            
            elif text == "👔 Руководитель (требуется пароль)":
                await self._show_manager_password(update, context)
            
            elif text == "👑 Администратор (требуется пароль)":
                await self._show_admin_password(update, context)
            
            elif text == "⬅️ Назад":
                await self._show_registration_step2(update, context)
            
            elif text == "❌ Отмена":
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\nЕсли захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
        
        elif current_context == 'manager_password':
            if text == "⬅️ Назад":
                await self._show_registration_step3(update, context)
            elif text == "❌ Отмена":
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\nЕсли захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif text.strip() == self.manager_password:  # Обрабатываем любой введенный текст
                if user_id in self.pending_registrations:
                    registration_data = self.pending_registrations[user_id]
                    
                    profile = self._get_user_profile(user_id)
                    profile['fio'] = registration_data['fio']
                    profile['position'] = registration_data['position']
                    profile['role'] = 'manager'
                    profile['registration_date'] = datetime.now().isoformat()
                    
                    auth_data = {
                        'status': 'authenticated',
                        'role': 'manager',
                        'registration_date': datetime.now().isoformat()
                    }
                    self._set_user_auth(user_id, auth_data)
                    
                    self.managers_list[user_id] = {
                        'fio': registration_data['fio'],
                        'position': registration_data['position'],
                        'registration_date': datetime.now().isoformat()
                    }
                    
                    del self.pending_registrations[user_id]
                    
                    await update.message.reply_text(
                        "✅ Регистрация завершена! Вы зарегистрированы как руководитель.\n\nТеперь настроим ваш профиль для персонализированных рекомендаций."
                    )
                    await self._show_role_selection(update, context)
                else:
                    await update.message.reply_text("❌ Ошибка регистрации. Начните заново.")
                    await self._show_auth_menu(update, context)
            else:
                await update.message.reply_text("❌ Неверный пароль. Попробуйте еще раз или выберите роль сотрудника.")
        
        elif current_context == 'admin_password':
            if text == "⬅️ Назад":
                await self._show_registration_step3(update, context)
            elif text == "❌ Отмена":
                if user_id in self.pending_registrations:
                    del self.pending_registrations[user_id]
                await update.message.reply_text(
                    "❌ Регистрация отменена.\n\nЕсли захотите зарегистрироваться позже, используйте команду /start",
                    reply_markup=ReplyKeyboardRemove()
                )
            elif text.strip() == self.admin_password:  # Обрабатываем любой введенный текст
                if user_id in self.pending_registrations:
                    registration_data = self.pending_registrations[user_id]
                    
                    profile = self._get_user_profile(user_id)
                    profile['fio'] = registration_data['fio']
                    profile['position'] = registration_data['position']
                    profile['role'] = 'admin'
                    profile['registration_date'] = datetime.now().isoformat()
                    profile['setup_completed'] = True
                    
                    auth_data = {
                        'status': 'authenticated',
                        'role': 'admin',
                        'registration_date': datetime.now().isoformat()
                    }
                    self._set_user_auth(user_id, auth_data)
                    
                    del self.pending_registrations[user_id]
                    
                    await update.message.reply_text(
                        "👑 Регистрация завершена! Вы зарегистрированы как администратор.\n\nТеперь вам доступна админ-панель для управления системой.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    await self.start(update, context)
                else:
                    await update.message.reply_text("❌ Ошибка регистрации. Начните заново.")
                    await self._show_auth_menu(update, context)
            else:
                await update.message.reply_text("❌ Неверный пароль. Попробуйте еще раз или выберите другую роль.")
        
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
                profile = self._get_user_profile(user_id)
                if text not in profile['preferences']['interests']:
                    profile['preferences']['interests'].append(text)
                    await update.message.reply_text(f"✅ Добавлено: {text}")

    def _get_user_manager(self, user_id):
        return self.user_managers.get(str(user_id))

    async def _show_login(self, update: Update, context: CallbackContext):
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
    
    async def _show_role_selection(self, update: Update, context: CallbackContext):
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
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        profile['setup_completed'] = True
        self._save_user_data()
        
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
    
    async def find_events(self, update: Update, context: CallbackContext):
        """Поиск мероприятий по критериям"""
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed']:
            await update.message.reply_text("❌ Пожалуйста, сначала завершите настройку профиля в разделе 👤 Профиль")
            return
        
        await update.message.reply_text("🔍 Ищу подходящие мероприятия...")
        
        try:
            # Получаем мероприятия
            events = await self.parser.parse_events()
            
            # Фильтруем по критериям
            filtered_events = self.filter.filter_events(events)
            
            if not filtered_events:
                await update.message.reply_text(
                    "❌ Не найдено подходящих мероприятий.\n\n💡 Попробуйте:\n• Изменить критерии в 👤 Профиль\n• Расширить интересы\n• Использовать другие настройки поиска"
                )
                return
            
            # Сохраняем найденные мероприятия для пользователя
            self.user_events[user_id] = filtered_events
            
            # Показываем результаты - передаем is_new_message=True для первого сообщения
            await self._show_single_event(update, context, user_id, 0, is_new_message=True)
            
        except Exception as e:
            print(f"❌ Ошибка поиска мероприятий: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при поиске мероприятий.\nПопробуйте позже или обратитесь к администратору."
            )
    
    async def _show_single_event(self, update, context, user_id, event_index, is_new_message=False):
        """Показывает одно мероприятие с подробной информацией и кнопками"""
        try:
            # Проверяем, что у нас есть valid update object
            if not update:
                print("❌ Ошибка: update object is None")
                return
                
            # Проверяем наличие мероприятий
            if user_id not in self.user_events or not self.user_events[user_id]:
                error_msg = "❌ Нет мероприятий для показа"
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(error_msg)
                elif hasattr(update, 'message') and update.message:
                    await update.message.reply_text(error_msg)
                return
            
            events = self.user_events[user_id]
            
            if event_index >= len(events):
                end_msg = "📭 Это все мероприятия"
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text(end_msg)
                elif hasattr(update, 'message') and update.message:
                    await update.message.reply_text(end_msg)
                return
            
            event = events[event_index]
            
            # Формируем подробное сообщение
            message = self._format_event_details(event, event_index + 1, len(events))
            
            # Создаем клавиатуру с кнопками управления
            keyboard = self._create_event_keyboard(user_id, event_index, len(events))
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Определяем, как отправлять сообщение
            if hasattr(update, 'callback_query') and update.callback_query:
                # Это callback (нажатие кнопки) - редактируем существующее сообщение
                await update.callback_query.edit_message_text(
                    message, 
                    reply_markup=reply_markup, 
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            elif hasattr(update, 'message') and update.message:
                if is_new_message:
                    # Первое сообщение - отправляем новое
                    sent_message = await update.message.reply_text(
                        message, 
                        reply_markup=reply_markup, 
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    # Сохраняем ID сообщения для последующего редактирования
                    self.last_message_id = sent_message.message_id
                else:
                    # Обновляем существующее сообщение
                    try:
                        await update.message.edit_text(
                            message, 
                            reply_markup=reply_markup, 
                            parse_mode='HTML',
                            disable_web_page_preview=True
                        )
                    except Exception:
                        # Если не удалось отредактировать (например, сообщение слишком старое), отправляем новое
                        await update.message.reply_text(
                            message, 
                            reply_markup=reply_markup, 
                            parse_mode='HTML',
                            disable_web_page_preview=True
                        )
            else:
                print("❌ Неизвестный тип update объекта")
                
        except Exception as e:
            print(f"❌ Ошибка показа мероприятия: {e}")
            # Пытаемся отправить сообщение об ошибке
            try:
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.edit_message_text("❌ Ошибка при загрузке мероприятия")
                elif hasattr(update, 'message') and update.message:
                    await update.message.reply_text("❌ Ошибка при загрузке мероприятия")
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке: {inner_e}")

    def _format_event_details(self, event, current_num, total_events):
        priority_score = event.get('priority_score', 0)
        priority_color = "🟢" if priority_score >= 8 else "🟡" if priority_score >= 6 else "🟠"
        
        message = f"""
{priority_color} <b>Мероприятие {current_num} из {total_events}</b>

🎯 <b>{event['title']}</b>

📅 <b>Дата:</b> {event['date']}
📍 <b>Место:</b> {event.get('location', 'Не указано')}
🎪 <b>Тип:</b> {event.get('type', 'мероприятие')}
⭐ <b>Приоритет:</b> {priority_score}/10
"""

        themes = event.get('themes', [])
        if themes:
            message += f"🏷️ <b>Тематики:</b> {', '.join(themes[:5])}\n"

        description = event.get('description', '')
        if description and len(description) > 0:
            if len(description) > 300:
                description = description[:300] + "..."
            message += f"\n📝 <b>Описание:</b>\n{description}\n"

        url = event.get('url', '')
        if url:
            message += f"\n🔗 <b>Ссылка:</b> {url}"

        return message

    def _create_event_keyboard(self, user_id, event_index, total_events):
        keyboard = []
        
        action_buttons = []
        
        if self._is_employee(user_id):
            action_buttons.append(InlineKeyboardButton(
                "🤝 Согласовать с руководителем", 
                callback_data=f"request_approval_{event_index}"
            ))
        else:
            action_buttons.append(InlineKeyboardButton(
                "📅 Добавить в календарь", 
                callback_data=f"add_calendar_{event_index}"
            ))
        
        action_buttons.append(InlineKeyboardButton(
            "⭐ В избранное", 
            callback_data=f"add_favorite_{event_index}"
        ))
        
        keyboard.append(action_buttons)
        
        event = self.user_events[user_id][event_index]
        if event.get('url'):
            keyboard.append([
                InlineKeyboardButton("🔗 Перейти на сайт мероприятия", url=event['url'])
            ])
        
        nav_buttons = []
        
        if event_index > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"event_{event_index - 1}"))
        
        if event_index < total_events - 1:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"event_{event_index + 1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        additional_buttons = []
        
        if self._is_employee(user_id):
            additional_buttons.append(InlineKeyboardButton("ℹ️ О согласовании", callback_data="info_approval"))
        
        additional_buttons.extend([
            InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search"),
            InlineKeyboardButton("📋 Все мероприятия", callback_data="show_all_events")
        ])
        
        keyboard.append(additional_buttons)
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
        
        return keyboard
    
    async def _add_event_to_favorites(self, query, context, event_index):
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
                
                if not any(fav['title'] == event['title'] and fav['date'] == event['date'] 
                        for fav in self.user_favorites[user_id]):
                    self.user_favorites[user_id].append(event)
                    
                    current_event_index = event_index
                    
                    await query.edit_message_text(
                        f"✅ <b>Мероприятие добавлено в избранное!</b>\n\n🎯 {event['title']}\n📅 {event['date']}\n\n⭐ Теперь оно будет в вашем списке избранных мероприятий\n\nПродолжайте просмотр мероприятий 👇",
                        parse_mode='HTML'
                    )
                    
                    await self._show_single_event(query, context, user_id, current_event_index)
                else:
                    await query.edit_message_text("✅ Это мероприятие уже в избранном")
                    await self._show_single_event(query, context, user_id, event_index)
            else:
                await query.edit_message_text("❌ Мероприятие не найдено")
                
        except Exception as e:
            print(f"❌ Ошибка добавления в избранное: {e}")
            await query.edit_message_text("❌ Ошибка при добавлении в избранное")
    
    async def _add_event_to_calendar(self, query, context, event_index):
        try:
            user_id = query.from_user.id
            
            if self._is_employee(user_id):
                await query.edit_message_text(
                    "❌ <b>Требуется согласование с руководителем</b>\n\nДля добавления мероприятий в календарь вам необходимо получить согласие руководителя.\n\n💡 <b>Как это сделать:</b>\n1. Нажмите кнопку '🤝 Согласовать с руководителем'\n2. Ожидайте решения руководителя\n3. После одобрения мероприятие автоматически добавится в ваш календарь\n\nЕсли у вас нет назначенного руководителя, обратитесь к администратору системы.",
                    parse_mode='HTML'
                )
                return
            
            if user_id not in self.user_events:
                await query.edit_message_text("❌ Данные мероприятий устарели. Выполните поиск заново.")
                return
            
            events = self.user_events[user_id]
            
            if event_index < len(events):
                event = events[event_index]
                result = self.calendar.add_event_to_calendar(event, user_id)
                
                if result['success']:
                    await query.edit_message_text(result['message'], parse_mode='HTML')
                else:
                    await query.edit_message_text("❌ Не удалось добавить мероприятие в календарь")
            else:
                await query.edit_message_text("❌ Мероприятие не найдено")
                
        except Exception as e:
            print(f"❌ Ошибка добавления в календарь: {e}")
            await query.edit_message_text("❌ Ошибка при добавлении в календарь")
    
    async def _request_approval(self, query, context, event_index):
        try:
            user_id = query.from_user.id
            
            if not self._is_employee(user_id):
                await query.edit_message_text("❌ Эта функция доступна только сотрудникам")
                return
            
            if user_id not in self.user_events:
                await query.edit_message_text("❌ Данные мероприятий устарели. Выполните поиск заново.")
                return
            
            events = self.user_events[user_id]
            
            if event_index < len(events):
                event = events[event_index]
                profile = self._get_user_profile(user_id)
                
                manager_id = self._get_user_manager(user_id)
                
                if not manager_id:
                    await query.edit_message_text(
                        "❌ Не назначен руководитель\n\nДля согласования мероприятий вам необходимо иметь назначенного руководителя. Обратитесь к администратору системы."
                    )
                    return
                
                approval_request = {
                    'event': event,
                    'employee_id': user_id,
                    'employee_name': profile.get('fio', 'Сотрудник'),
                    'employee_position': profile.get('position', 'Не указано'),
                    'manager_id': manager_id,
                    'status': 'pending',
                    'request_date': datetime.now().isoformat(),
                    'event_index': event_index
                }
                
                if user_id not in self.pending_approvals:
                    self.pending_approvals[user_id] = []
                self.pending_approvals[user_id].append(approval_request)
                
                approval_keyboard = [
                    [
                        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_event_{user_id}_{len(self.pending_approvals[user_id])-1}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_event_{user_id}_{len(self.pending_approvals[user_id])-1}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(approval_keyboard)
                
                approval_text = f"""
📋 <b>Запрос на согласование мероприятия</b>

👤 <b>Сотрудник:</b> {profile.get('fio', 'Не указано')}
💼 <b>Должность:</b> {profile.get('position', 'Не указано')}

🎯 <b>Мероприятие:</b>
• Название: {event['title']}
• Дата: {event['date']}
• Место: {event.get('location', 'Не указано')}
• Тип: {event.get('type', 'мероприятие')}

📅 <b>Запрошено:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

Для согласования используйте кнопки ниже:
                """
                
                success, next_work_time_msg = await self._send_manager_notification(
                    context, manager_id, approval_text, reply_markup
                )
                
                if success:
                    await query.edit_message_text(
                        f"✅ <b>Запрос отправлен на согласование!</b>\n\n🎯 <b>Мероприятие:</b> {event['title']}\n📅 <b>Дата:</b> {event['date']}\n👔 <b>Руководитель уведомлен</b>\n\nОжидайте решения руководителя.",
                        parse_mode='HTML'
                    )
                else:
                    await query.edit_message_text(
                        f"✅ <b>Запрос отправлен на согласование!</b>\n\n🎯 <b>Мероприятие:</b> {event['title']}\n📅 <b>Дата:</b> {event['date']}\n\n⏰ <b>Уведомление руководителю будет отправлено:</b>\n{next_work_time_msg}\n\nЗаявка сохранена и будет обработана в рабочее время.",
                        parse_mode='HTML'
                    )
                
            else:
                await query.edit_message_text("❌ Мероприятие не найдено")
                
        except Exception as e:
            print(f"❌ Ошибка запроса согласования: {e}")
            await query.edit_message_text("❌ Ошибка при отправке запроса на согласование")

    async def _approve_event(self, query, context, employee_id, request_index):
        try:
            employee_id = int(employee_id)
            
            if employee_id not in self.pending_approvals:
                await query.edit_message_text("❌ Заявка не найдена")
                return
            
            if request_index >= len(self.pending_approvals[employee_id]):
                await query.edit_message_text("❌ Заявка не найдена")
                return
            
            approval_request = self.pending_approvals[employee_id][request_index]
            event = approval_request['event']
            
            result = self.calendar.add_event_to_calendar(event, employee_id)
            
            if result['success']:
                approval_request['status'] = 'approved'
                approval_request['approval_date'] = datetime.now().isoformat()
                approval_request['approved_by'] = query.from_user.id
                
                try:
                    employee_profile = self._get_user_profile(employee_id)
                    manager_profile = self._get_user_profile(query.from_user.id)
                    
                    await context.bot.send_message(
                        chat_id=employee_id,
                        text=f"""
✅ <b>Заявка на мероприятие одобрена!</b>

👔 <b>Руководитель:</b> {manager_profile.get('fio', 'Руководитель')}
🎯 <b>Мероприятие:</b> {event['title']}
📅 <b>Дата:</b> {event['date']}
📍 <b>Место:</b> {event.get('location', 'Не указано')}

Мероприятие добавлено в ваш календарь.
                        """,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    print(f"❌ Ошибка уведомления сотрудника: {e}")
                
                await query.edit_message_text(
                    f"✅ <b>Мероприятие одобрено!</b>\n\n🎯 {event['title']}\n📅 {event['date']}\n👤 {approval_request['employee_name']}\n\nМероприятие добавлено в календарь сотрудника.",
                    parse_mode='HTML'
                )
                
            else:
                await query.edit_message_text("❌ Ошибка при добавлении мероприятия в календарь")
                
        except Exception as e:
            print(f"❌ Ошибка одобрения мероприятия: {e}")
            await query.edit_message_text("❌ Ошибка при обработке запроса")

    async def _reject_event(self, query, context, employee_id, request_index):
        try:
            employee_id = int(employee_id)
            
            if employee_id not in self.pending_approvals:
                await query.edit_message_text("❌ Заявка не найдена")
                return
            
            if request_index >= len(self.pending_approvals[employee_id]):
                await query.edit_message_text("❌ Заявка не найдена")
                return
            
            approval_request = self.pending_approvals[employee_id][request_index]
            event = approval_request['event']
            
            approval_request['status'] = 'rejected'
            approval_request['rejection_date'] = datetime.now().isoformat()
            approval_request['rejected_by'] = query.from_user.id
            
            try:
                employee_profile = self._get_user_profile(employee_id)
                manager_profile = self._get_user_profile(query.from_user.id)
                
                await context.bot.send_message(
                    chat_id=employee_id,
                    text=f"""
❌ <b>Заявка на мероприятие отклонена</b>

👔 <b>Руководитель:</b> {manager_profile.get('fio', 'Руководитель')}
🎯 <b>Мероприятие:</b> {event['title']}
📅 <b>Дата:</b> {event['date']}

Обратитесь к руководителю для уточнения причин.
                    """,
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"❌ Ошибка уведомления сотрудника: {e}")
            
            await query.edit_message_text(
                f"❌ <b>Мероприятие отклонено!</b>\n\n🎯 {event['title']}\n📅 {event['date']}\n👤 {approval_request['employee_name']}\n\nСотрудник уведомлен об отклонении заявки.",
                parse_mode='HTML'
            )
            
        except Exception as e:
            print(f"❌ Ошибка отклонения мероприятия: {e}")
            await query.edit_message_text("❌ Ошибка при обработке запроса")
    
    async def find_events_callback(self, query, context):
        try:
            if not query:
                return
                
            await query.edit_message_text("🔍 Ищу подходящие мероприятия...")
            
            user_id = query.from_user.id
            events = await self.parser.parse_events()
            filtered_events = self.filter.filter_events(events)
            
            if not filtered_events:
                await query.edit_message_text("❌ Не найдено подходящих мероприятий.\n\n💡 Попробуйте изменить критерии в профиле.")
                return
            
            self.user_events[user_id] = filtered_events
            await self._show_single_event(query, context, user_id, 0)
            
        except Exception as e:
            print(f"❌ Ошибка поиска мероприятий: {e}")
            try:
                await query.edit_message_text("❌ Ошибка при поиске мероприятий")
            except:
                pass

    async def show_events_callback(self, query, context):
        try:
            if not query:
                return
                
            user_id = query.from_user.id
            await query.edit_message_text("🔍 Ищу рекомендованные мероприятия...")
            
            events = await self.parser.parse_events()
            filtered_events = self.filter.filter_events(events)
            
            if not filtered_events:
                await query.edit_message_text("❌ Не найдено подходящих мероприятий.\n\n💡 Попробуйте изменить критерии в профиле.")
                return
            
            self.user_events[user_id] = filtered_events
            await self._show_single_event(query, context, user_id, 0)
            
        except Exception as e:
            print(f"❌ Ошибка показа мероприятий: {e}")
            try:
                await query.edit_message_text("❌ Ошибка при загрузке мероприятий")
            except:
                pass

    async def show_events(self, update: Update, context: CallbackContext):
        if not await self._require_auth(update, context):
            return
        
        await update.message.reply_text("🔍 Ищу подходящие мероприятия по вашим критериям...")
        
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        if not profile['setup_completed']:
            await update.message.reply_text("❌ Пожалуйста, сначала завершите настройку профиля в разделе 👤 Профиль")
            return
        
        try:
            events = self.parser.load_events()
            if not events:
                events = await self.parser.parse_events()
            
            filtered_events = self.filter.filter_events(events)
            
            if not filtered_events:
                await update.message.reply_text(
                    "❌ Не найдено мероприятий по вашим критериям\n\n💡 Попробуйте:\n• Изменить критерии в 👤 Профиль\n• Расширить интересы\n• Использовать 🔍 Расширенный поиск"
                )
                return
            
            self.user_events[user_id] = filtered_events
            # Передаем is_new_message=True для первого сообщения
            await self._show_single_event(update, context, user_id, 0, is_new_message=True)
            
        except Exception as e:
            print(f"❌ Ошибка поиска мероприятий: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при поиске мероприятий.\nПопробуйте позже или обратитесь к администратору."
            )

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

    async def show_favorites(self, update: Update, context: CallbackContext):
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        
        if user_id not in self.user_favorites or not self.user_favorites[user_id]:
            await update.message.reply_text(
                "⭐ <b>Ваши избранные мероприятия</b>\n\n📭 У вас пока нет избранных мероприятий\n\n💡 Чтобы добавить мероприятие в избранное:\n1. Найдите мероприятия через 🔍 Поиск\n2. Нажмите кнопку '⭐ Добавить в избранное'\n3. Все добавленные мероприятия появятся здесь",
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
        if not await self._require_auth(update, context):
            return
        
        user_id = update.effective_user.id
        profile = self._get_user_profile(user_id)
        
        favorites_count = len(self.user_favorites.get(user_id, []))
        events_found = len(self.user_events.get(user_id, []))
        
        events = await self.parser.parse_events()
        filtered_events = self.filter.filter_events(events)
        
        theme_stats = {}
        for event in filtered_events[:20]:
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

    def _is_event_this_week(self, event):
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
            today = datetime.now()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return start_of_week.date() <= event_date.date() <= end_of_week.date()
        except:
            return False

    def _is_event_this_month(self, event):
        try:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
            today = datetime.now()
            return event_date.month == today.month and event_date.year == today.year
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
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
            return
        
        # Сортируем мероприятия по дате
        user_events.sort(key=lambda x: x.get('date', ''))
        
        text = "📅 <b>Ваш календарь мероприятий</b>\n\n"
        
        for i, event in enumerate(user_events[:10], 1):
            try:
                event_date = event.get('date', '')
                today = datetime.now().date()
                
                if event_date:
                    try:
                        event_date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
                        days_left = (event_date_obj - today).days
                        
                        if days_left == 0:
                            days_text = "🎯 СЕГОДНЯ"
                        elif days_left == 1:
                            days_text = "🚀 ЗАВТРА"
                        elif days_left < 0:
                            days_text = "✅ ПРОШЛО"
                        else:
                            days_text = f"⏳ Через {days_left} дн."
                    except:
                        days_text = "📅 Дата не определена"
                else:
                    days_text = "📅 Дата не указана"
                
                text += (
                    f"{i}. <b>{event['title']}</b>\n"
                    f"   📅 {event_date} ({days_text})\n"
                    f"   📍 {event.get('location', 'Не указано')}\n"
                )
                
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
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    def get_calendar_events(self, user_id):
        """Получает мероприятия из календаря пользователя"""
        try:
            return self.calendar.get_user_events(user_id)
        except Exception as e:
            print(f"❌ Ошибка получения мероприятий из календаря: {e}")
            return []

    async def handle_callback(self, update: Update, context: CallbackContext):
        """Обработчик callback'ов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith('event_'):
            event_index = int(data.split('_')[1])
            await self._show_single_event(update, context, user_id, event_index, is_new_message=False)
        
        elif data.startswith('add_calendar_'):
            event_index = int(data.split('_')[2])
            await self._add_event_to_calendar(query, context, event_index)
        
        elif data.startswith('request_approval_'):
            event_index = int(data.split('_')[2])
            await self._request_approval(query, context, event_index)
        
        elif data.startswith('add_favorite_'):
            event_index = int(data.split('_')[2])
            await self._add_event_to_favorites(query, context, event_index)
        
        elif data == 'new_search':
            await self.find_events_callback(query, context)
        
        elif data == 'show_all_events':
            await self._show_all_events_list(query, context)
        
        elif data == 'main_menu':
            await self._show_main_menu_callback(query, context)
        
        elif data.startswith('approve_event_'):
            parts = data.split('_')
            employee_id = parts[2]
            request_index = int(parts[3])
            await self._approve_event(query, context, employee_id, request_index)
        
        elif data.startswith('reject_event_'):
            parts = data.split('_')
            employee_id = parts[2]
            request_index = int(parts[3])
            await self._reject_event(query, context, employee_id, request_index)
        
        elif data == 'clear_favorites':
            await self._clear_favorites(query, context)
        
        elif data == 'refresh_calendar':
            await self.show_calendar_callback(query, context)
        
        elif data == 'clear_calendar':
            await self._clear_calendar(query, context)
        
        elif data == 'info_approval':
            await self._show_approval_info(query, context)
        
        elif data == 'refresh_approvals':
            await self.show_pending_approvals_callback(query, context)  # Используем callback версию
        
        elif data == 'show_events':
            await self.show_events_callback(query, context)

    async def _show_all_events_list(self, query, context):
        try:
            if not query:
                return
                
            user_id = query.from_user.id
            
            if user_id not in self.user_events:
                await query.edit_message_text("❌ Данные мероприятий устарели. Выполните поиск заново.")
                return
            
            events = self.user_events[user_id]
            
            if not events:
                await query.edit_message_text("❌ Не найдено мероприятий")
                return
            
            message = "📋 <b>Все найденные мероприятия:</b>\n\n"
            
            for i, event in enumerate(events[:15], 1):
                priority_score = event.get('priority_score', 0)
                priority_color = "🟢" if priority_score >= 8 else "🟡" if priority_score >= 6 else "🟠"
                
                message += (
                    f"{i}. {priority_color} <b>{event['title']}</b>\n"
                    f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                    f"   ⭐ {priority_score}/10\n\n"
                )
            
            if len(events) > 15:
                message += f"<i>... и ещё {len(events) - 15} мероприятий</i>\n\n"
            
            message += "🎯 Нажмите на номер мероприятия для подробного просмотра"
            
            keyboard = []
            row = []
            for i in range(min(10, len(events))):
                row.append(InlineKeyboardButton(str(i+1), callback_data=f"event_{i}"))
                if len(row) == 5:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            keyboard.extend([
                [InlineKeyboardButton("🔄 Новый поиск", callback_data="new_search")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')
            
        except Exception as e:
            print(f"❌ Ошибка показа всех мероприятий: {e}")
            try:
                await query.edit_message_text("❌ Ошибка при загрузке мероприятий")
            except:
                pass

    async def _show_main_menu_callback(self, query, context):
        try:
            if not query:
                return
                
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
            try:
                await query.edit_message_text("❌ Ошибка при загрузке меню")
            except:
                pass

    async def show_pending_approvals(self, update: Update, context: CallbackContext):
        """Показывает заявки на согласование для руководителя"""
        # Определяем user_id в зависимости от типа update
        if hasattr(update, 'callback_query') and update.callback_query:
            user_id = update.callback_query.from_user.id
            query = update.callback_query
        elif hasattr(update, 'message') and update.message:
            user_id = update.message.from_user.id
            query = None
        else:
            user_id = update.effective_user.id
            query = None
        
        if not await self._require_auth(update, context):
            return
        
        if not self._is_manager(user_id):
            if query:
                await query.edit_message_text("❌ Эта функция доступна только руководителям")
            else:
                await update.message.reply_text("❌ Эта функция доступна только руководителям")
            return
        
        # Находим все заявки для этого руководителя
        pending_requests = []
        for employee_id, requests in self.pending_approvals.items():
            for request in requests:
                if request.get('manager_id') == str(user_id) and request.get('status') == 'pending':
                    pending_requests.append({
                        'employee_id': employee_id,
                        'employee_name': request.get('employee_name', 'Сотрудник'),
                        'event': request['event'],
                        'request_date': request.get('request_date'),
                        'request_index': requests.index(request)
                    })
        
        if not pending_requests:
            message_text = "📋 <b>Заявки на согласование</b>\n\n📭 Нет ожидающих заявок\n\nВсе заявки от ваших сотрудников будут появляться здесь."
            if query:
                await query.edit_message_text(message_text, parse_mode='HTML')
            else:
                await update.message.reply_text(message_text, parse_mode='HTML')
            return
        
        text = "📋 <b>Заявки на согласование</b>\n\n"
        
        for i, request in enumerate(pending_requests, 1):
            event = request['event']
            text += (
                f"{i}. <b>{event['title']}</b>\n"
                f"   👤 {request['employee_name']}\n"
                f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                f"   🕒 Запрошено: {datetime.fromisoformat(request['request_date']).strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_approvals")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    async def show_pending_approvals_callback(self, query, context):
        """Показывает заявки на согласование для руководителя (callback версия)"""
        user_id = query.from_user.id
        
        if not self._is_manager(user_id):
            await query.edit_message_text("❌ Эта функция доступна только руководителям")
            return
        
        # Находим все заявки для этого руководителя
        pending_requests = []
        for employee_id, requests in self.pending_approvals.items():
            for request in requests:
                if request.get('manager_id') == str(user_id) and request.get('status') == 'pending':
                    pending_requests.append({
                        'employee_id': employee_id,
                        'employee_name': request.get('employee_name', 'Сотрудник'),
                        'event': request['event'],
                        'request_date': request.get('request_date'),
                        'request_index': requests.index(request)
                    })
        
        if not pending_requests:
            await query.edit_message_text(
                "📋 <b>Заявки на согласование</b>\n\n📭 Нет ожидающих заявок\n\nВсе заявки от ваших сотрудников будут появляться здесь.",
                parse_mode='HTML'
            )
            return
        
        text = "📋 <b>Заявки на согласование</b>\n\n"
        
        for i, request in enumerate(pending_requests, 1):
            event = request['event']
            text += (
                f"{i}. <b>{event['title']}</b>\n"
                f"   👤 {request['employee_name']}\n"
                f"   📅 {event['date']} | 📍 {event.get('location', 'Не указано')}\n"
                f"   🕒 Запрошено: {datetime.fromisoformat(request['request_date']).strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        # Создаем кнопки для каждой заявки
        keyboard = []
        for i, request in enumerate(pending_requests):
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Одобрить {i+1}", 
                    callback_data=f"approve_event_{request['employee_id']}_{request['request_index']}"
                ),
                InlineKeyboardButton(
                    f"❌ Отклонить {i+1}", 
                    callback_data=f"reject_event_{request['employee_id']}_{request['request_index']}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Обновить", callback_data="refresh_approvals"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    async def _show_approval_info(self, query, context):
        user_id = query.from_user.id
        profile = self._get_user_profile(user_id)
        manager_id = self._get_user_manager(user_id)
        
        info_text = """
ℹ️ <b>Процесс согласования мероприятий</b>

👥 <b>Для сотрудников:</b>
1. Найдите подходящее мероприятие
2. Нажмите "🤝 Согласовать с руководителем"
3. Ожидайте решения руководителя
4. После одобрения мероприятие автоматически добавится в ваш календарь

⏱️ <b>Сроки рассмотрения:</b>
• Руководитель получит уведомление сразу
• Обычно заявки рассматриваются в течение 1-2 рабочих дней
• Вы получите уведомление о решении

👔 <b>Ваш руководитель:</b>
"""
        
        if manager_id:
            try:
                manager_profile = self._get_user_profile(int(manager_id))
                manager_name = manager_profile.get('fio', 'Руководитель')
                manager_position = manager_profile.get('position', 'Должность не указана')
                info_text += f"• {manager_name} - {manager_position}"
            except:
                info_text += "• Информация о руководителе временно недоступна"
        else:
            info_text += "• ❌ Руководитель не назначен\n\nОбратитесь к администратору системы для назначения руководителя."
        
        current_event_index = 0
        try:
            if user_id in self.user_events and self.user_events[user_id]:
                current_event_index = 0
        except:
            pass
        
        keyboard = [
            [InlineKeyboardButton("🤝 Понятно, продолжить", callback_data=f"event_{current_event_index}")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(info_text, reply_markup=reply_markup, parse_mode='HTML')

    async def _clear_favorites(self, query, context):
        user_id = query.from_user.id
        
        if user_id in self.user_favorites:
            self.user_favorites[user_id] = []
            await query.edit_message_text("✅ Избранные мероприятия очищены")
        else:
            await query.edit_message_text("📭 В избранном и так пусто")

    async def _clear_calendar(self, query, context):
        """Очищает календарь пользователя"""
        try:
            user_id = query.from_user.id
            success = self.calendar.clear_user_calendar(user_id)
            
            if success:
                await query.edit_message_text("🗑️ Календарь очищен! Все мероприятия удалены.")
            else:
                await query.edit_message_text("❌ Ошибка при очистке календаря")
                
        except Exception as e:
            print(f"❌ Ошибка очистки календаря: {e}")
            await query.edit_message_text("❌ Ошибка при очистке календаря")

    async def show_calendar_callback(self, query, context):
        try:
            user_id = query.from_user.id
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
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
                return
            
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
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
            
        except Exception as e:
            print(f"❌ Ошибка показа календаря: {e}")
            try:
                await query.edit_message_text("❌ Ошибка при загрузке календаря")
            except:
                pass

    async def handle_message(self, update: Update, context: CallbackContext):
        text = update.message.text
        user_id = update.effective_user.id
        current_context = self._get_user_context(user_id)
        
        if current_context in ['auth_menu', 'login', 'registration_fio', 'registration_position', 
                            'registration_role', 'manager_password']:
            await self.handle_auth(update, context)
            return
        
        if self._is_admin(user_id) and current_context in ['admin_menu', 'user_management', 
                                                        'password_management', 'change_manager_password',
                                                        'change_admin_password', 'broadcast_menu']:
            await self.handle_admin_commands(update, context)
            return
        
        if current_context in ['role_selection', 'location_preferences', 'audience_preferences',
                            'participation_role_preferences', 'interests_preferences']:
            await self.handle_auth(update, context)
            return
        
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
            elif text == "📋 Заявки на согласование" and self._is_manager(user_id):
                await self.show_pending_approvals(update, context)
            else:
                await update.message.reply_text(
                    "Используйте кнопки меню для изменения профиля или вернитесь в главное меню.",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🏠 Главное меню")]], resize_keyboard=True)
                )
            return
        
        if current_context == 'profile_reset_confirm':
            if text == "✅ Да, сбросить":
                profile = self._get_user_profile(user_id)
                fio = profile.get('fio', '')
                position = profile.get('position', '')
                role = profile.get('role', 'employee')
                
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
                    "✅ Настройки профиля сброшены!\n\nТеперь нужно заново настроить профиль для персонализированных рекомендаций.",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🎯 Настроить профиль")]], resize_keyboard=True)
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
            
        if not await self._require_auth(update, context):
            return
        
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

        elif text == "📋 Заявки на согласование" and self._is_manager(user_id):
            await self.show_pending_approvals(update, context)
        
        else:
            await update.message.reply_text(
                "Используйте кнопки меню или команды:\n/start - главное меню\n/profile - настройка профиля\n/help - помощь"
            )

    async def _reset_profile(self, update: Update, context: CallbackContext):
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

    async def check_pending_notifications(self, context: CallbackContext = None):
        try:
            if self._is_work_time():
                for manager_id in list(self.pending_notifications.keys()):
                    await self._send_delayed_notifications(context, manager_id)
        except Exception as e:
            print(f"❌ Ошибка проверки отложенных уведомлений: {e}")
    
    def run(self):
        try:
            self.application = Application.builder().token(self.token).build()
            
            self._setup_handlers()
            
            if hasattr(self.application, 'job_queue') and self.application.job_queue:
                self.application.job_queue.run_repeating(
                    self.check_pending_notifications,
                    interval=300,
                    first=10
                )
                print("✅ Job queue инициализирован")
            else:
                print("⚠️ Job queue недоступен. Установите: pip install 'python-telegram-bot[job-queue]'")
            
            print("🤖 Telegram бот запущен!")
            print("=" * 60)
            print("Используйте /start для начала работы")
            print("Для остановки нажмите Ctrl+C")
            print("=" * 60)
            
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

    def _setup_handlers(self):
        if not self.application:
            return
            
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("events", self.show_events))
        self.application.add_handler(CommandHandler("find", self.find_events))
        self.application.add_handler(CommandHandler("favorites", self.show_favorites))
        self.application.add_handler(CommandHandler("settings", self.show_settings))
        self.application.add_handler(CommandHandler("profile", self.show_profile))
        self.application.add_handler(CommandHandler("stats", self.show_stats))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("admin", self._show_admin_menu))
        self.application.add_handler(CommandHandler("calendar", self.show_calendar))
        
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def handle_admin_commands(self, update: Update, context: CallbackContext):
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
            if text == "🎯 Назначить руководителя":
                await self._show_assign_manager_menu(update, context)
            elif text == "🔄 Обновить список":
                await self._show_user_management(update, context)
            elif text == "⬅️ Назад в админку":
                await self._show_admin_menu(update, context)
            elif text.startswith("👤 "):
                await self._show_user_details(update, context, text)
        
        elif current_context == 'assign_manager_select_employee':
            if text == "⬅️ Назад в админку":
                await self._show_admin_menu(update, context)
            elif text.startswith("👤 "):
                await self._select_manager_for_employee(update, context, text)
        
        elif current_context == 'assign_manager_select_manager':
            if text == "⬅️ Назад к выбору сотрудника":
                await self._show_assign_manager_menu(update, context)
            elif text.startswith("👔 ") or text == "❌ Удалить руководителя":
                await self._assign_manager_to_employee(update, context, text)
        
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
            if text == "⬅️ Назад":
                await self._show_password_management(update, context)
            elif len(text) >= 4:
                self.manager_password = text
                config.BOT_CONFIG["manager_password"] = text
                await update.message.reply_text(f"✅ Пароль руководителей изменен на: {text}")
                await self._show_password_management(update, context)
            else:
                await update.message.reply_text("❌ Пароль должен содержать минимум 4 символа")
        
        elif current_context == 'change_admin_password':
            if text == "⬅️ Назад":
                await self._show_password_management(update, context)
            elif len(text) >= 4:
                self.admin_password = text
                config.BOT_CONFIG["admin_password"] = text
                await update.message.reply_text(f"✅ Пароль администратора изменен на: {text}")
                await self._show_password_management(update, context)
            else:
                await update.message.reply_text("❌ Пароль должен содержать минимум 4 символа")
        
        elif current_context == 'broadcast_menu':
            if text == "📢 Всем пользователям":
                context.user_data['broadcast_audience'] = 'all'
                await self._request_broadcast_message(update, context)
            elif text == "👔 Только руководителям":
                context.user_data['broadcast_audience'] = 'managers'
                await self._request_broadcast_message(update, context)
            elif text == "👨‍💼 Только сотрудникам":
                context.user_data['broadcast_audience'] = 'employees'
                await self._request_broadcast_message(update, context)
            elif text == "⬅️ Назад в админку":
                await self._show_admin_menu(update, context)
        
        elif current_context == 'broadcast_message':
            audience = context.user_data.get('broadcast_audience', 'all')
            await self._send_broadcast(update, context, text, audience)
        
        else:
            await update.message.reply_text(
                "Используйте кнопки админ-панели для управления системой.",
                reply_markup=ReplyKeyboardMarkup([["🏠 Главное меню"]], resize_keyboard=True)
            )

    async def _show_user_management(self, update: Update, context: CallbackContext):
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
        for user in users_list[:10]:
            users_keyboard.append([KeyboardButton(f"👤 {user['fio']} - {user['role']}")])
        
        users_keyboard.extend([
            [KeyboardButton("🎯 Назначить руководителя")],
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
            manager_info = ""
            if str(user['user_id']) in self.user_managers:
                manager_id = self.user_managers[str(user['user_id'])]
                manager_profile = self.user_profiles.get(int(manager_id), {})
                manager_info = f" 👔 {manager_profile.get('fio', 'Руководитель')}"
            
            text += f"\n{i}. {user['fio']} - {user['position']} ({user['role']}){manager_info}"
        
        text += "\n\nВыберите пользователя для управления или обновите список:"
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _show_assign_manager_menu(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'assign_manager_select_employee')
        
        # Получаем список сотрудников (не руководителей)
        employees = []
        for uid, auth in self.user_auth.items():
            if auth.get('status') == 'authenticated' and auth.get('role') == 'employee':
                profile = self.user_profiles.get(uid, {})
                employees.append({
                    'user_id': uid,
                    'fio': profile.get('fio', 'Не указано'),
                    'position': profile.get('position', 'Не указано')
                })
        
        if not employees:
            await update.message.reply_text(
                "❌ Нет сотрудников для назначения руководителя",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад в админку"]], resize_keyboard=True)
            )
            return
        
        employees_keyboard = []
        for employee in employees[:10]:
            current_manager = ""
            if str(employee['user_id']) in self.user_managers:
                manager_id = self.user_managers[str(employee['user_id'])]
                manager_profile = self.user_profiles.get(int(manager_id), {})
                current_manager = f" (👔 {manager_profile.get('fio', 'Руководитель')})"
            
            employees_keyboard.append([KeyboardButton(
                f"👤 {employee['fio']}{current_manager}"
            )])
        
        employees_keyboard.append([KeyboardButton("⬅️ Назад в админку")])
        
        reply_markup = ReplyKeyboardMarkup(employees_keyboard, resize_keyboard=True)
        
        text = """
    🎯 Назначение руководителя

    Выберите сотрудника, которому хотите назначить руководителя:

    👤 - сотрудник
    👔 - текущий руководитель

    Выберите сотрудника из списка:
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _select_manager_for_employee(self, update: Update, context: CallbackContext, employee_info: str):
        user_id = update.effective_user.id
        self._set_user_context(user_id, 'assign_manager_select_manager')
        
        # Извлекаем ID сотрудника из текста кнопки
        employee_fio = employee_info.replace("👤 ", "").split(" (👔")[0].strip()
        employee_id = None
        
        for uid, profile in self.user_profiles.items():
            if profile.get('fio') == employee_fio and self._get_user_auth(uid).get('role') == 'employee':
                employee_id = uid
                break
        
        if not employee_id:
            await update.message.reply_text("❌ Сотрудник не найден")
            await self._show_user_management(update, context)
            return
        
        # Сохраняем выбранного сотрудника в контексте
        context.user_data['assign_manager_employee_id'] = employee_id
        context.user_data['assign_manager_employee_fio'] = employee_fio
        
        # Получаем список руководителей
        managers = []
        for uid, auth in self.user_auth.items():
            if auth.get('status') == 'authenticated' and auth.get('role') == 'manager':
                profile = self.user_profiles.get(uid, {})
                managers.append({
                    'user_id': uid,
                    'fio': profile.get('fio', 'Не указано'),
                    'position': profile.get('position', 'Не указано')
                })
        
        if not managers:
            await update.message.reply_text(
                "❌ В системе нет руководителей",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад в админку"]], resize_keyboard=True)
            )
            return
        
        managers_keyboard = []
        for manager in managers[:10]:
            managers_keyboard.append([KeyboardButton(f"👔 {manager['fio']}")])
        
        managers_keyboard.append([KeyboardButton("❌ Удалить руководителя")])
        managers_keyboard.append([KeyboardButton("⬅️ Назад к выбору сотрудника")])
        
        reply_markup = ReplyKeyboardMarkup(managers_keyboard, resize_keyboard=True)
        
        text = f"""
    🎯 Назначение руководителя

    Сотрудник: {employee_fio}

    Выберите руководителя из списка:

    👔 - руководитель

    Или нажмите "❌ Удалить руководителя" чтобы удалить текущее назначение.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def _assign_manager_to_employee(self, update: Update, context: CallbackContext, manager_info: str):
        user_id = update.effective_user.id
        
        if manager_info == "❌ Удалить руководителя":
            # Удаляем назначение руководителя
            employee_id = context.user_data.get('assign_manager_employee_id')
            employee_fio = context.user_data.get('assign_manager_employee_fio')
            
            if str(employee_id) in self.user_managers:
                del self.user_managers[str(employee_id)]
                # Также удаляем из manager_employees
                manager_id = self.user_managers.get(str(employee_id))
                if manager_id and manager_id in self.manager_employees:
                    if employee_id in self.manager_employees[manager_id]:
                        self.manager_employees[manager_id].remove(employee_id)
            
            await update.message.reply_text(
                f"✅ Руководитель удален у сотрудника {employee_fio}",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад в админку"]], resize_keyboard=True)
            )
            
            # Очищаем контекст
            context.user_data.pop('assign_manager_employee_id', None)
            context.user_data.pop('assign_manager_employee_fio', None)
            
            self._set_user_context(user_id, 'admin_menu')
            return
        
        # Извлекаем ID руководителя
        manager_fio = manager_info.replace("👔 ", "").strip()
        manager_id = None
        
        for uid, profile in self.user_profiles.items():
            if profile.get('fio') == manager_fio and self._get_user_auth(uid).get('role') == 'manager':
                manager_id = uid
                break
        
        if not manager_id:
            await update.message.reply_text("❌ Руководитель не найден")
            await self._show_user_management(update, context)
            return
        
        employee_id = context.user_data.get('assign_manager_employee_id')
        employee_fio = context.user_data.get('assign_manager_employee_fio')
        
        # Назначаем руководителя
        self.user_managers[str(employee_id)] = str(manager_id)
        
        # Обновляем manager_employees для обратной связи
        if str(manager_id) not in self.manager_employees:
            self.manager_employees[str(manager_id)] = []
        
        if employee_id not in self.manager_employees[str(manager_id)]:
            self.manager_employees[str(manager_id)].append(employee_id)
        
        # Сохраняем данные
        self._save_user_data()
        
        # Уведомляем сотрудника и руководителя
        try:
            await context.bot.send_message(
                chat_id=employee_id,
                text=f"""
    👔 Вам назначен руководитель

    Вашим руководителем назначен: {manager_fio}

    Теперь все заявки на участие в мероприятиях будут направляться ему на согласование.
                """,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Ошибка уведомления сотрудника: {e}")
        
        try:
            await context.bot.send_message(
                chat_id=manager_id,
                text=f"""
    👥 Вам назначен сотрудник

    Вам назначен сотрудник для согласования мероприятий:
    • {employee_fio}

    Теперь вы будете получать заявки от этого сотрудника на согласование участия в мероприятиях.
                """,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Ошибка уведомления руководителя: {e}")
        
        await update.message.reply_text(
            f"✅ Руководитель {manager_fio} назначен сотруднику {employee_fio}",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад в админку"]], resize_keyboard=True)
        )
        
        # Очищаем контекст
        context.user_data.pop('assign_manager_employee_id', None)
        context.user_data.pop('assign_manager_employee_fio', None)
        
        self._set_user_context(user_id, 'admin_menu')

    async def _show_password_management(self, update: Update, context: CallbackContext):
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

    async def _change_manager_password(self, update: Update, context: CallbackContext):
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
        text = f"""
🔑 Текущие пароли системы:

• Пароль руководителей: {self.manager_password}
• Пароль администратора: {self.admin_password}

⚠️ Никому не сообщайте эти пароли!
        """
        
        await update.message.reply_text(text)

    async def _show_system_stats(self, update: Update, context: CallbackContext):
        total_users = len([uid for uid, auth in self.user_auth.items() if auth.get('status') == 'authenticated'])
        managers_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'manager'])
        employees_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'employee'])
        admins_count = len([uid for uid, auth in self.user_auth.items() if auth.get('role') == 'admin'])
        
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
        await update.message.reply_text("👤 Функция просмотра пользователя в разработке")