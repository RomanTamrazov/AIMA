import os
import json
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import calendar

class TelegramCalendar:
    def __init__(self):
        self.calendar_events = {}
        self.load_calendar_events()
    
    def load_calendar_events(self):
        try:
            os.makedirs("data", exist_ok=True)
            calendar_file = "data/telegram_calendar.json"
            
            if os.path.exists(calendar_file):
                with open(calendar_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self.calendar_events = json.loads(content)
                    else:
                        self.calendar_events = {}
            else:
                self.calendar_events = {}
                
        except json.JSONDecodeError:
            self.calendar_events = {}
        except Exception as e:
            print(f"Ошибка загрузки календаря: {e}")
            self.calendar_events = {}
    
    def save_calendar_events(self):
        try:
            os.makedirs("data", exist_ok=True)
            calendar_file = "data/telegram_calendar.json"
            with open(calendar_file, 'w', encoding='utf-8') as f:
                json.dump(self.calendar_events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения календаря: {e}")
    
    def add_event_to_calendar(self, event, user_id):
        try:
            if str(user_id) not in self.calendar_events:
                self.calendar_events[str(user_id)] = []
            
            event_id = f"{event['title']}_{event['date']}_{datetime.now().timestamp()}"
            event_with_id = event.copy()
            event_with_id['id'] = event_id
            
            if not any(e['title'] == event['title'] and e['date'] == event['date'] 
                      for e in self.calendar_events[str(user_id)]):
                self.calendar_events[str(user_id)].append(event_with_id)
                self.save_calendar_events()
                return {
                    'success': True,
                    'message': f"✅ Мероприятие '{event['title']}' добавлено в календарь"
                }
            else:
                return {
                    'success': False,
                    'message': "❌ Это мероприятие уже есть в вашем календаре"
                }
        except Exception as e:
            print(f"Ошибка добавления мероприятия: {e}")
            return {'success': False, 'message': "❌ Ошибка при добавлении в календарь"}
    
    def get_user_events(self, user_id):
        try:
            return self.calendar_events.get(str(user_id), [])
        except Exception as e:
            print(f"Ошибка получения мероприятий: {e}")
            return []
    
    def clear_user_calendar(self, user_id):
        try:
            if str(user_id) in self.calendar_events:
                self.calendar_events[str(user_id)] = []
                self.save_calendar_events()
                return True
            return False
        except Exception as e:
            print(f"Ошибка очистки календаря: {e}")
            return False
    
    def get_user_calendar(self, user_id, month=None, year=None):
        now = datetime.now()
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        user_events = self.calendar_events.get(str(user_id), [])
        
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
        try:
            now = datetime.now()
            if not month:
                month = now.month
            if not year:
                year = now.year
            
            calendar_data = self.get_user_calendar(user_id, month, year)
            month_events = calendar_data['events']
            
            cal = calendar.monthcalendar(year, month)
            month_name = self._get_month_name(month)
            
            keyboard = []
            header_row = [
                InlineKeyboardButton("⬅️", callback_data=f"calendar_prev_{month}_{year}"),
                InlineKeyboardButton(f"{month_name} {year}", callback_data="ignore"),
                InlineKeyboardButton("➡️", callback_data=f"calendar_next_{month}_{year}")
            ]
            keyboard.append(header_row)
            
            week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in week_days])
            
            today = datetime.now().date()
            
            for week in cal:
                week_row = []
                for day in week:
                    if day == 0:
                        week_row.append(InlineKeyboardButton(" ", callback_data="ignore"))
                    else:
                        day_date = datetime(year, month, day).date()
                        
                        has_events = any(
                            datetime.strptime(e['date'], '%Y-%m-%d').date() == day_date 
                            for e in month_events
                        )
                        
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
            
            nav_row = [
                InlineKeyboardButton("📅 Сегодня", callback_data="calendar_today"),
                InlineKeyboardButton("📋 Список событий", callback_data="calendar_list"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ]
            keyboard.append(nav_row)
            
            return InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            print(f"Ошибка создания календаря: {e}")
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Обновить календарь", callback_data="calendar")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])
    
    def _get_month_name(self, month):
        months = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август", 
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        return months.get(month, "Месяц")
    
    def get_day_events(self, user_id, year, month, day):
        try:
            target_date = datetime(year, month, day).strftime('%Y-%m-%d')
            user_events = self.calendar_events.get(str(user_id), [])
            
            day_events = []
            for event in user_events:
                if event['date'] == target_date:
                    day_events.append(event)
            
            return day_events
        except Exception as e:
            print(f"Ошибка получения событий дня: {e}")
            return []
    
    def remove_event(self, user_id, event_id):
        try:
            user_events = self.calendar_events.get(str(user_id), [])
            
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
            print(f"Ошибка удаления события: {e}")
            return {
                'success': False,
                'message': "❌ Ошибка удаления события"
            }
    
    def remove_day_events(self, user_id, year, month, day):
        try:
            target_date = datetime(year, month, day).strftime('%Y-%m-%d')
            user_events = self.calendar_events.get(str(user_id), [])
            
            remaining_events = [e for e in user_events if e['date'] != target_date]
            removed_count = len(user_events) - len(remaining_events)
            
            if removed_count > 0:
                self.calendar_events[str(user_id)] = remaining_events
                self.save_calendar_events()
                
                return {
                    'success': True,
                    'message': f"✅ Удалено {removed_count} событий за {day:02d}.{month:02d}.{year}",
                    'removed_count': removed_count
                }
            else:
                return {
                    'success': False,
                    'message': f"❌ На {day:02d}.{month:02d}.{year} событий не найдено"
                }
                
        except Exception as e:
            print(f"Ошибка удаления событий дня: {e}")
            return {
                'success': False,
                'message': "❌ Ошибка удаления событий"
            }
    
    def format_calendar_message(self, month, year, events_count):
        month_name = self._get_month_name(month)
        
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
        date_str = datetime(year, month, day).strftime('%d.%m.%Y')
        
        if not events:
            return (
                f"📅 <b>{date_str}</b>\n\n"
                f"📭 На этот день событий нет\n\n"
                f"Используйте кнопки ниже для навигации"
            )
        
        events_text = ""
        for i, event in enumerate(events, 1):
            title = event['title']
            if len(title) > 35:
                title = title[:35] + "..."
                
            events_text += (
                f"\n{i}. <b>{title}</b>\n"
                f"   📍 {event.get('location', 'Не указано')}\n"
                f"   🎪 {event.get('type', 'мероприятие')}\n"
            )
        
        return (
            f"📅 <b>{date_str}</b>\n\n"
            f"<b>События дня:</b>{events_text}\n\n"
            f"Используйте кнопки ниже для управления событиями"
        )
    
    def format_events_list_message(self, events):
        if not events:
            return (
                "📋 <b>Ваши мероприятия</b>\n\n"
                "📭 У вас нет запланированных мероприятий\n\n"
                "🎯 Используйте кнопку 'Рекомендованные мероприятия' "
                "чтобы найти интересные события!"
            )
        
        events_text = ""
        events_count = min(len(events), 8)
        
        for i, event in enumerate(events[:events_count], 1):
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').strftime('%d.%m.%Y')
            days_left = (datetime.strptime(event['date'], '%Y-%m-%d') - datetime.now()).days
            
            if days_left == 0:
                days_text = "🎯 Сегодня"
            elif days_left == 1:
                days_text = "🚀 Завтра"
            else:
                days_text = f"⏳ Через {days_left} дн."
            
            title = event['title']
            if len(title) > 40:
                title = title[:40] + "..."
            
            events_text += (
                f"\n{i}. <b>{title}</b>\n"
                f"   📅 {event_date} ({days_text})\n"
                f"   📍 {event.get('location', 'Не указано')}\n"
            )
        
        if len(events) > events_count:
            events_text += f"\n... и ещё {len(events) - events_count} мероприятий"
        
        return (
            f"📋 <b>Ваши мероприятия</b>\n\n"
            f"<b>Ближайшие события:</b>{events_text}\n\n"
            f"🎯 Всего запланировано: <b>{len(events)} мероприятий</b>"
        )
    
    def format_event_details(self, event):
        event_date = datetime.strptime(event['date'], '%Y-%m-%d').strftime('%d.%m.%Y')
        days_left = (datetime.strptime(event['date'], '%Y-%m-%d') - datetime.now()).days
        
        if days_left == 0:
            days_text = "🎯 <b>СЕГОДНЯ!</b>"
        elif days_left == 1:
            days_text = "🚀 <b>ЗАВТРА!</b>"
        else:
            days_text = f"⏳ Через <b>{days_left}</b> дней"
        
        message = (
            f"🎯 <b>Детали мероприятия</b>\n\n"
            f"<b>{event['title']}</b>\n\n"
            f"📅 <b>Дата:</b> {event_date} ({days_text})\n"
            f"📍 <b>Место:</b> {event.get('location', 'Не указано')}\n"
            f"🎪 <b>Тип:</b> {event.get('type', 'мероприятие')}\n"
        )
        
        if event.get('description'):
            desc = event['description']
            if len(desc) > 200:
                desc = desc[:200] + "..."
            message += f"📝 <b>Описание:</b> {desc}\n"
        
        if event.get('url') and event['url'] != '#':
            message += f"🔗 <b>Ссылка:</b> {event['url']}\n"
        
        message += f"\n🆔 <code>ID: {event['id']}</code>"
        
        return message
    
    def create_day_events_keyboard(self, year, month, day, events):
        keyboard = []
        
        for i, event in enumerate(events, 1):
            button_text = event['title']
            if len(button_text) > 20:
                button_text = button_text[:20] + "..."
                
            keyboard.append([
                InlineKeyboardButton(
                    f"📝 {i}. {button_text}", 
                    callback_data=f"calendar_event_{event['id']}"
                )
            ])
        
        nav_row = [
            InlineKeyboardButton("⬅️ Назад к календарю", callback_data="calendar_back"),
            InlineKeyboardButton("🗑️ Очистить день", callback_data=f"calendar_clear_{year}_{month}_{day}")
        ]
        keyboard.append(nav_row)
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_event_details_keyboard(self, event_id, event_url=None):
        keyboard = []
        
        if event_url and event_url != '#':
            keyboard.append([
                InlineKeyboardButton("🔗 Открыть сайт мероприятия", url=event_url)
            ])
        
        keyboard.extend([
            [
                InlineKeyboardButton("🗑️ Удалить", callback_data=f"event_delete_{event_id}"),
                InlineKeyboardButton("⬅️ Назад", callback_data="calendar_back_to_day")
            ],
            [
                InlineKeyboardButton("📅 В календарь", callback_data="calendar_back")
            ]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_events_list_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("📅 Открыть календарь", callback_data="calendar"),
                InlineKeyboardButton("🔍 Найти мероприятия", callback_data="find_events")
            ],
            [
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_event_by_id(self, user_id, event_id):
        try:
            user_events = self.calendar_events.get(str(user_id), [])
            for event in user_events:
                if event['id'] == event_id:
                    return event
            return None
        except Exception as e:
            print(f"Ошибка поиска события: {e}")
            return None
    
    def get_upcoming_reminders(self, days_before=1):
        try:
            reminders = []
            today = datetime.now().date()
            target_date = today + timedelta(days=days_before)
            
            for user_id, events in self.calendar_events.items():
                for event in events:
                    try:
                        event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
                        if (event_date == target_date and 
                            not event.get('notified', False) and
                            event_date >= today):
                            reminders.append({
                                'user_id': user_id,
                                'event': event
                            })
                    except:
                        continue
            
            return reminders
        except Exception as e:
            print(f"Ошибка получения напоминаний: {e}")
            return []
    
    def mark_event_notified(self, user_id, event_id):
        try:
            user_events = self.calendar_events.get(str(user_id), [])
            for event in user_events:
                if event['id'] == event_id:
                    event['notified'] = True
                    self.save_calendar_events()
                    return True
            return False
        except Exception as e:
            print(f"Ошибка отметки уведомления: {e}")
            return False