import os
import json
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import calendar

class TelegramCalendar:
    """Встроенный календарь для Telegram бота"""
    
    def __init__(self):
        self.calendar_events = {}
        self.load_calendar_events()
    
    def load_calendar_events(self):
        """Загружает события календаря из файла"""
        try:
            calendar_file = "data/telegram_calendar.json"
            if os.path.exists(calendar_file):
                with open(calendar_file, 'r', encoding='utf-8') as f:
                    self.calendar_events = json.load(f)
            else:
                self.calendar_events = {}
        except Exception as e:
            print(f"❌ Ошибка загрузки календаря: {e}")
            self.calendar_events = {}
    
    def save_calendar_events(self):
        """Сохраняет события календаря в файл"""
        try:
            os.makedirs("data", exist_ok=True)
            calendar_file = "data/telegram_calendar.json"
            with open(calendar_file, 'w', encoding='utf-8') as f:
                json.dump(self.calendar_events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения календаря: {e}")
    
    def add_event_to_calendar(self, event, user_id):
        """Добавляет мероприятие в календарь пользователя"""
        try:
            if str(user_id) not in self.calendar_events:
                self.calendar_events[str(user_id)] = []
            
            # Создаем запись события
            calendar_event = {
                'id': f"{event['title'][:20]}_{datetime.now().timestamp()}",
                'title': event['title'],
                'date': event['date'],
                'location': event.get('location', 'Не указано'),
                'type': event.get('type', 'мероприятие'),
                'description': event.get('description', ''),
                'url': event.get('url', ''),
                'added_date': datetime.now().isoformat(),
                'notified': False
            }
            
            # Добавляем в календарь пользователя
            self.calendar_events[str(user_id)].append(calendar_event)
            
            # Сохраняем изменения
            self.save_calendar_events()
            
            return {
                'success': True,
                'event_id': calendar_event['id'],
                'message': self._get_success_message(event)
            }
            
        except Exception as e:
            print(f"❌ Ошибка добавления в календарь: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': "❌ Ошибка добавления в календарь"
            }
    
    def _get_success_message(self, event):
        """Возвращает сообщение об успешном добавлении"""
        return (
            f"✅ <b>Мероприятие добавлено в календарь!</b>\n\n"
            f"🎯 <b>{event['title']}</b>\n"
            f"📅 <b>Дата:</b> {event['date']}\n"
            f"📍 <b>Место:</b> {event.get('location', 'Не указано')}\n\n"
            f"📱 <b>Просмотреть календарь:</b> /calendar\n"
            f"🔔 <b>Напоминания:</b> Будут приходить за 1 день до мероприятия"
        )
    
    def get_user_calendar(self, user_id, month=None, year=None):
        """Возвращает календарь пользователя на указанный месяц"""
        now = datetime.now()
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        user_events = self.calendar_events.get(str(user_id), [])
        
        # Фильтруем события по месяцу и году
        month_events = []
        for event in user_events:
            try:
                event_date = datetime.strptime(event['date'], '%Y-%m-%d')
                if event_date.month == month and event_date.year == year:
                    month_events.append(event)
            except:
                continue
        
        return {
            'month': month,
            'year': year,
            'events': month_events
        }
    
    def create_calendar_keyboard(self, user_id, month=None, year=None):
        """Создает клавиатуру календаря на месяц"""
        now = datetime.now()
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        # Получаем события пользователя
        calendar_data = self.get_user_calendar(user_id, month, year)
        month_events = calendar_data['events']
        
        # Создаем календарь
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        
        # Заголовок календаря
        keyboard = []
        header_row = [
            InlineKeyboardButton("⬅️", callback_data=f"calendar_prev_{month}_{year}"),
            InlineKeyboardButton(f"{month_name} {year}", callback_data="calendar_info"),
            InlineKeyboardButton("➡️", callback_data=f"calendar_next_{month}_{year}")
        ]
        keyboard.append(header_row)
        
        # Дни недели
        week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        keyboard.append([InlineKeyboardButton(day, callback_data="calendar_day_info") for day in week_days])
        
        # Дни месяца
        today = datetime.now().date()
        
        for week in cal:
            week_row = []
            for day in week:
                if day == 0:
                    week_row.append(InlineKeyboardButton(" ", callback_data="calendar_empty"))
                else:
                    day_date = datetime(year, month, day).date()
                    
                    # Проверяем есть ли события в этот день
                    has_events = any(
                        datetime.strptime(e['date'], '%Y-%m-%d').date() == day_date 
                        for e in month_events
                    )
                    
                    # Определяем эмодзи и стиль
                    if day_date == today:
                        day_text = f"🎯{day}" if has_events else f"📅{day}"
                    elif has_events:
                        day_text = f"⭐{day}"
                    else:
                        day_text = f"{day}"
                    
                    week_row.append(
                        InlineKeyboardButton(
                            day_text, 
                            callback_data=f"calendar_day_{year}_{month}_{day}"
                        )
                    )
            keyboard.append(week_row)
        
        # Кнопки навигации
        nav_row = [
            InlineKeyboardButton("📅 Сегодня", callback_data="calendar_today"),
            InlineKeyboardButton("📋 Список событий", callback_data="calendar_list"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
        keyboard.append(nav_row)
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_day_events(self, user_id, year, month, day):
        """Возвращает события на конкретный день"""
        try:
            target_date = datetime(year, month, day).strftime('%Y-%m-%d')
            user_events = self.calendar_events.get(str(user_id), [])
            
            day_events = []
            for event in user_events:
                if event['date'] == target_date:
                    day_events.append(event)
            
            return day_events
        except Exception as e:
            print(f"❌ Ошибка получения событий дня: {e}")
            return []
    
    def get_events_list(self, user_id, limit=10):
        """Возвращает список ближайших событий"""
        try:
            user_events = self.calendar_events.get(str(user_id), [])
            
            # Сортируем по дате
            sorted_events = sorted(user_events, key=lambda x: x['date'])
            
            # Фильтруем только будущие события
            today = datetime.now().strftime('%Y-%m-%d')
            future_events = [e for e in sorted_events if e['date'] >= today]
            
            return future_events[:limit]
        except Exception as e:
            print(f"❌ Ошибка получения списка событий: {e}")
            return []
    
    def remove_event(self, user_id, event_id):
        """Удаляет событие из календаря"""
        try:
            user_events = self.calendar_events.get(str(user_id), [])
            
            # Ищем и удаляем событие
            for i, event in enumerate(user_events):
                if event['id'] == event_id:
                    removed_event = user_events.pop(i)
                    self.calendar_events[str(user_id)] = user_events
                    self.save_calendar_events()
                    
                    return {
                        'success': True,
                        'message': f"✅ Событие '{removed_event['title']}' удалено из календаря"
                    }
            
            return {
                'success': False,
                'message': "❌ Событие не найдено"
            }
            
        except Exception as e:
            print(f"❌ Ошибка удаления события: {e}")
            return {
                'success': False,
                'message': "❌ Ошибка удаления события"
            }
    
    def format_calendar_message(self, month, year, events_count):
        """Форматирует сообщение календаря"""
        month_name = calendar.month_name[month]
        
        if events_count == 0:
            events_text = "📭 На этот месяц событий нет"
        elif events_count == 1:
            events_text = "⭐ 1 событие"
        else:
            events_text = f"⭐ {events_count} событий"
        
        return (
            f"📅 <b>Календарь мероприятий</b>\n\n"
            f"<b>{month_name} {year}</b>\n"
            f"{events_text}\n\n"
            f"🎯 <b>Выберите день для просмотра событий</b>\n"
            f"⭐ - день с событиями\n"
            f"🎯 - сегодня с событиями\n"
            f"📅 - сегодня без событий"
        )
    
    def format_day_events_message(self, year, month, day, events):
        """Форматирует сообщение с событиями дня"""
        date_str = datetime(year, month, day).strftime('%d.%m.%Y')
        
        if not events:
            return (
                f"📅 <b>{date_str}</b>\n\n"
                f"📭 На этот день событий нет\n\n"
                f"Используйте кнопки ниже для навигации"
            )
        
        events_text = ""
        for i, event in enumerate(events, 1):
            events_text += (
                f"\n{i}. <b>{event['title']}</b>\n"
                f"   📍 {event.get('location', 'Не указано')}\n"
                f"   🎪 {event.get('type', 'мероприятие')}\n"
            )
        
        return (
            f"📅 <b>{date_str}</b>\n\n"
            f"<b>События дня:</b>{events_text}\n\n"
            f"Используйте кнопки ниже для управления событиями"
        )
    
    def format_events_list_message(self, events):
        """Форматирует сообщение со списком событий с ограничением длины"""
        if not events:
            return (
                "📋 <b>Ваши мероприятия</b>\n\n"
                "📭 У вас нет запланированных мероприятий\n\n"
                "🎯 Используйте кнопку 'Рекомендованные мероприятия' "
                "чтобы найти интересные события!"
            )
        
        events_text = ""
        events_count = min(len(events), 8)  # Ограничиваем количество событий
        
        for i, event in enumerate(events[:events_count], 1):
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').strftime('%d.%m.%Y')
            days_left = (datetime.strptime(event['date'], '%Y-%m-%d') - datetime.now()).days
            
            if days_left == 0:
                days_text = "🎯 Сегодня"
            elif days_left == 1:
                days_text = "🚀 Завтра"
            else:
                days_text = f"⏳ Через {days_left} дн."
            
            # Ограничиваем длину названия
            title = event['title']
            if len(title) > 40:
                title = title[:40] + "..."
            
            events_text += (
                f"\n{i}. <b>{title}</b>\n"
                f"   📅 {event_date} ({days_text})\n"
                f"   📍 {event.get('location', 'Не указано')}\n"
            )
        
        # Добавляем информацию если события были обрезаны
        if len(events) > events_count:
            events_text += f"\n... и ещё {len(events) - events_count} мероприятий"
        
        return (
            f"📋 <b>Ваши мероприятия</b>\n\n"
            f"<b>Ближайшие события:</b>{events_text}\n\n"
            f"🎯 Всего запланировано: <b>{len(events)} мероприятий</b>"
        )
    def create_day_events_keyboard(self, year, month, day, events):
        """Создает клавиатуру для событий дня"""
        keyboard = []
        
        # Кнопки для каждого события
        for i, event in enumerate(events, 1):
            keyboard.append([
                InlineKeyboardButton(
                    f"📝 {i}. {event['title'][:20]}...", 
                    callback_data=f"calendar_event_{event['id']}"
                )
            ])
        
        # Кнопки навигации
        nav_row = [
            InlineKeyboardButton("⬅️ Назад к календарю", callback_data="calendar_back"),
            InlineKeyboardButton("🗑️ Очистить день", callback_data=f"calendar_clear_{year}_{month}_{day}")
        ]
        keyboard.append(nav_row)
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_event_details_keyboard(self, event_id):
        """Создает клавиатуру для деталей события"""
        keyboard = [
            [
                InlineKeyboardButton("🔗 Открыть сайт", callback_data=f"event_url_{event_id}"),
                InlineKeyboardButton("🗑️ Удалить", callback_data=f"event_delete_{event_id}")
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="calendar_back_to_day"),
                InlineKeyboardButton("📅 В календарь", callback_data="calendar_back")
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)