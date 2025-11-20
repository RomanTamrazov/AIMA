import os
import json
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Импортируем config из корня
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import config

# Импортируем наш генератор .ics
from .ics_calendar import ICSGenerator

class CalendarIntegration:
    """Интеграция с календарями (Google Calendar + .ics файлы)"""
    
    def __init__(self):
        self.calendar_config = config.GOOGLE_CALENDAR_CONFIG
        self.service = None
        self.ics_generator = ICSGenerator()
        self.authenticate()
    
    def add_event_to_calendar(self, event, user_id=None, method='auto'):
        """
        Добавляет мероприятие в календарь
        
        Args:
            event: Объект мероприятия
            user_id: ID пользователя
            method: 'auto', 'google', 'ics'
        """
        if method == 'ics' or (method == 'auto' and not self.service):
            return self._add_event_via_ics(event, user_id)
        elif method == 'google' or (method == 'auto' and self.service):
            return self._add_event_to_google_calendar(event, user_id)
        else:
            return self._add_event_via_ics(event, user_id)
    
    def _add_event_via_ics(self, event, user_id):
        """Добавляет событие через .ics файл"""
        result = self.ics_generator.create_ics_event(event, user_id)
        
        if result['success']:
            return {
                'success': True,
                'method': 'ics',
                'filepath': result['filepath'],
                'filename': result['filename'],
                'message': self._get_ics_success_message(result['filename'])
            }
        else:
            return {
                'success': False,
                'method': 'ics',
                'error': result.get('error'),
                'message': "❌ Ошибка создания файла для календаря"
            }
    
    def _add_event_to_google_calendar(self, event, user_id):
        """Добавляет событие в Google Calendar (существующий код)"""
        if not self.service:
            return self._add_event_via_ics(event, user_id)
        
        try:
            calendar_id = user_id or self.calendar_config["calendar_id"]
            calendar_event = self._create_calendar_event(event)
            
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=calendar_event
            ).execute()
            
            print(f"✅ Мероприятие '{event['title']}' добавлено в Google Calendar")
            
            return {
                'success': True,
                'method': 'google',
                'event_id': created_event['id'],
                'html_link': created_event.get('htmlLink'),
                'message': f"✅ Мероприятие добавлено в Google Calendar!\n🔗 {created_event.get('htmlLink', 'Ссылка недоступна')}"
            }
            
        except HttpError as error:
            print(f'❌ Ошибка Google Calendar: {error}')
            # При ошибке Google Calendar пробуем .ics
            return self._add_event_via_ics(event, user_id)
    
    def _get_ics_success_message(self, filename):
        """Возвращает сообщение об успешном создании .ics файла"""
        return (
            "✅ Файл для календаря готов!\n\n"
            "📱 <b>Как добавить в календарь:</b>\n"
            "1. <b>iPhone:</b> Откройте файл → 'Добавить все' в приложении Календарь\n"
            "2. <b>Android:</b> Файл → Импорт в Google Календарь\n" 
            "3. <b>Любой телефон:</b> Сохраните файл и импортируйте в приложение календаря\n"
            "4. <b>Компьютер:</b> Двойной клик по файлу\n\n"
            "Файл будет отправлен следующим сообщением 📎"
        )
    
    def _create_calendar_event(self, event):
        """Создает объект события для Google Calendar"""
        # Парсим дату мероприятия
        event_date = self._parse_event_date(event['date'])
        
        # Создаем описание
        description = self._create_event_description(event)
        
        # Создаем объект события
        calendar_event = {
            'summary': f"🎯 {event['title']}",
            'location': event.get('location', 'Не указано'),
            'description': description,
            'start': {
                'dateTime': event_date.isoformat(),
                'timeZone': self.calendar_config["timezone"],
            },
            'end': {
                'dateTime': (event_date + timedelta(hours=3)).isoformat(),  # 3 часа по умолчанию
                'timeZone': self.calendar_config["timezone"],
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 24 * 60},  # За 1 день
                    {'method': 'popup', 'minutes': 60},       # За 1 час
                ],
            },
            'guestsCanInviteOthers': False,
            'guestsCanSeeOtherGuests': False,
        }
        
        # Если есть URL мероприятия, добавляем его
        if event.get('url'):
            calendar_event['description'] += f"\n\n🔗 Сайт мероприятия: {event['url']}"
        
        return calendar_event
    
    def _parse_event_date(self, date_str):
        """Парсит дату из строки в объект datetime"""
        try:
            # Пробуем разные форматы дат
            formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Если ни один формат не подошел, используем сегодняшнюю дату
            print(f"⚠️ Не удалось распарсить дату: {date_str}, использую сегодняшнюю дату")
            return datetime.now()
            
        except Exception as e:
            print(f"❌ Ошибка парсинга даты {date_str}: {e}")
            return datetime.now()
    
    def _create_event_description(self, event):
        """Создает подробное описание для события в календаре"""
        description_parts = []
        
        # Основная информация
        if event.get('description'):
            description_parts.append(f"📝 {event['description']}")
        
        # Детали мероприятия
        details = []
        if event.get('audience'):
            details.append(f"👥 Участников: {event['audience']}")
        if event.get('type'):
            details.append(f"🎪 Тип: {event['type']}")
        if event.get('themes'):
            details.append(f"🏷️ Темы: {', '.join(event['themes'])}")
        if event.get('speakers'):
            details.append(f"🎤 Спикеры: {', '.join(event['speakers'])}")
        if event.get('registration_info'):
            details.append(f"📋 Регистрация: {event['registration_info']}")
        if event.get('source'):
            details.append(f"📊 Источник: {event['source']}")
        
        if details:
            description_parts.append("\n".join(details))
        
        # Добавляем информацию о системе
        description_parts.append(f"\n---\n🤖 Добавлено AI-помощником Сбера\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        
        return '\n\n'.join(description_parts)
    
    def _add_event_fallback(self, event):
        """Резервный метод добавления события (без Google Calendar)"""
        print(f"✅ Мероприятие '{event['title']}' добавлено в локальный календарь")
        
        # Сохраняем в локальный файл для отслеживания
        self._save_event_to_file(event)
        
        return {
            'success': True,
            'event_id': f"local_{datetime.now().timestamp()}",
            'message': f"✅ Мероприятие '{event['title']}' добавлено в календарь!\n📅 {event['date']} | 📍 {event.get('location', 'Не указано')}"
        }
    
    def _save_event_to_file(self, event):
        """Сохраняет событие в локальный файл для отслеживания"""
        try:
            events_file = "data/added_to_calendar.json"
            os.makedirs(os.path.dirname(events_file), exist_ok=True)
            
            # Загружаем существующие события
            events = []
            if os.path.exists(events_file):
                with open(events_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            
            # Добавляем новое событие
            events.append({
                'title': event['title'],
                'date': event['date'],
                'location': event.get('location'),
                'added_at': datetime.now().isoformat(),
                'source': 'fallback'
            })
            
            # Сохраняем обратно
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"⚠️ Ошибка сохранения события в файл: {e}")
    
    def get_upcoming_events(self, max_results=10):
        """Получает предстоящие события из календаря"""
        if not self.service:
            return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            events_result = self.service.events().list(
                calendarId=self.calendar_config["calendar_id"],
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
            
        except HttpError as error:
            print(f'❌ Ошибка получения событий из календаря: {error}')
            return []
    
    def check_calendar_connection(self):
        """Проверяет подключение к Google Calendar"""
        if not self.service:
            return False
        
        try:
            # Пробуем получить список календарей
            calendar_list = self.service.calendarList().list().execute()
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к Google Calendar: {e}")
            return False