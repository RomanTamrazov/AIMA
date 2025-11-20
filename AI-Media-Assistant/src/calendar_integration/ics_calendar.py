#!/usr/bin/env python3
"""
Чистый .ics генератор для импорта в любые календари
"""

import os
from datetime import datetime, timedelta
import uuid

# Импортируем config из корня
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import config

class SimpleICSCalendar:
    """Простой генератор .ics файлов для импорта в календари"""
    
    def __init__(self, output_dir="data/calendar_exports"):
        self.output_dir = output_dir
        self.calendar_config = config.CALENDAR_CONFIG
        os.makedirs(self.output_dir, exist_ok=True)
        print("✅ ICS календарь инициализирован")
    
    def add_event_to_calendar(self, event, user_id=None):
        """
        Создает .ics файл для мероприятия
        
        Args:
            event: Объект мероприятия
            user_id: ID пользователя (для имени файла)
        """
        try:
            # Создаем содержимое .ics файла
            ics_content = self._create_ics_content(event)
            
            # Сохраняем в файл
            filename = self._generate_filename(event, user_id)
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(ics_content)
            
            print(f"✅ Создан .ics файл: {filename}")
            return {
                'success': True,
                'filepath': filepath,
                'filename': filename,
                'message': self._get_success_message(filename)
            }
            
        except Exception as e:
            print(f"❌ Ошибка создания .ics файла: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': "❌ Ошибка создания файла для календаря"
            }
    
    def _create_ics_content(self, event):
        """Создает содержимое .ics файла"""
        event_datetime = self._parse_event_datetime(event['date'])
        duration_hours = self.calendar_config.get("default_duration_hours", 3)
        event_end = event_datetime + timedelta(hours=duration_hours)
        
        # Форматируем даты для .ics
        dtstart = event_datetime.strftime('%Y%m%dT%H%M%S')
        dtend = event_end.strftime('%Y%m%dT%H%M%S')
        dtstamp = datetime.now().strftime('%Y%m%dT%H%M%SZ')
        
        # Создаем уникальный ID
        uid = f"{uuid.uuid4()}@sber-ai-assistant"
        
        # Описание события
        description = self._create_event_description(event)
        # Экранируем специальные символы для .ics
        description = description.replace('\n', '\\n')
        description = description.replace(',', '\\,')
        description = description.replace(';', '\\;')
        
        # Название события
        summary = f"🎯 {event['title']}"
        summary = summary.replace(',', '\\,').replace(';', '\\;')
        
        # Локация
        location = event.get('location', 'Не указано')
        location = location.replace(',', '\\,').replace(';', '\\;')
        
        # Создаем .ics содержимое
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Sber AI Assistant//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:{location}
BEGIN:VALARM
TRIGGER:-P1D
ACTION:DISPLAY
DESCRIPTION:Напоминание: {event['title']}
END:VALARM
BEGIN:VALARM
TRIGGER:-PT1H
ACTION:DISPLAY
DESCRIPTION:Скоро: {event['title']}
END:VALARM
END:VEVENT
END:VCALENDAR"""
        
        return ics_content
    
    def _parse_event_datetime(self, date_str):
        """Парсит дату и устанавливает разумное время по умолчанию"""
        try:
            # Пробуем разные форматы дат
            formats = ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']
            for fmt in formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                # Если ни один формат не подошел, используем сегодня
                date_obj = datetime.now()
            
            # Устанавливаем время по умолчанию
            default_time = self.calendar_config.get("default_time", "10:00")
            hour, minute = map(int, default_time.split(':'))
            
            return datetime.combine(date_obj, datetime.min.time().replace(hour=hour, minute=minute))
            
        except Exception as e:
            print(f"❌ Ошибка парсинга даты {date_str}: {e}")
            return datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    def _create_event_description(self, event):
        """Создает описание для события"""
        description_parts = []
        
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
        if event.get('url'):
            details.append(f"🔗 Сайт мероприятия: {event['url']}")
        
        if details:
            description_parts.append("\n".join(details))
        
        # Информация о системе
        description_parts.append(
            f"---\n"
            f"🤖 Добавлено AI-помощником Сбера\n"
            f"📅 Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        return '\n\n'.join(description_parts)
    
    def _generate_filename(self, event, user_id=None):
        """Генерирует имя файла"""
        # Очищаем название от специальных символов
        clean_title = "".join(c for c in event['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_title = clean_title.replace(' ', '_')[:30]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_suffix = f"_{user_id}" if user_id else ""
        
        return f"event_{clean_title}_{timestamp}{user_suffix}.ics"
    
    def _get_success_message(self, filename):
        """Возвращает сообщение об успешном создании .ics файла"""
        return (
            "✅ Файл для календаря готов!\n\n"
            "📱 <b>Как добавить в календарь:</b>\n"
            "1. <b>iPhone:</b> Откройте файл → 'Добавить все' в приложении Календарь\n"
            "2. <b>Android:</b> Файл → Импорт в Google Календарь\n" 
            "3. <b>Любой телефон:</b> Сохраните файл и импортируйте в приложение календаря\n"
            "4. <b>Компьютер:</b> Двойной клик по файлу\n\n"
            "📎 Файл будет отправлен следующим сообщением"
        )
    
    def create_multiple_events_ics(self, events, user_id=None):
        """Создает .ics файл с несколькими событиями"""
        try:
            ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Sber AI Assistant//EN\n"
            
            for event in events:
                # Создаем содержимое для каждого события
                event_ics = self._create_ics_content(event)
                # Извлекаем только VEVENT часть
                event_lines = event_ics.split('\n')
                in_vevent = False
                vevent_lines = []
                
                for line in event_lines:
                    if line == 'BEGIN:VEVENT':
                        in_vevent = True
                    if in_vevent:
                        vevent_lines.append(line)
                    if line == 'END:VEVENT':
                        break
                
                ics_content += '\n'.join(vevent_lines) + '\n'
            
            ics_content += "END:VCALENDAR"
            
            # Сохраняем файл
            filename = f"multiple_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ics"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(ics_content)
            
            print(f"✅ Создан .ics файл с {len(events)} событиями: {filename}")
            return {
                'success': True,
                'filepath': filepath,
                'filename': filename
            }
            
        except Exception as e:
            print(f"❌ Ошибка создания множественного .ics файла: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_files(self, max_age_hours=24):
        """Очищает старые .ics файлы"""
        try:
            current_time = datetime.now()
            deleted_count = 0
            
            for filename in os.listdir(self.output_dir):
                if filename.endswith('.ics'):
                    filepath = os.path.join(self.output_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    
                    if (current_time - file_time).total_seconds() > max_age_hours * 3600:
                        os.remove(filepath)
                        deleted_count += 1
            
            if deleted_count > 0:
                print(f"🧹 Удалено {deleted_count} старых .ics файлов")
                
        except Exception as e:
            print(f"⚠️ Ошибка очистки старых файлов: {e}")