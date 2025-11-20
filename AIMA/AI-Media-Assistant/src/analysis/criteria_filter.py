import json
from datetime import datetime, timedelta
import re

class CriteriaFilter:
    """Улучшенный фильтр мероприятий с гибкими критериями"""
    
    def __init__(self, criteria=None):
        self.criteria = criteria or self._get_default_criteria()
        self.rejection_stats = {}
    
    def _get_default_criteria(self):
        """Возвращает критерии по умолчанию"""
        return {
            "min_audience": 50,
            "event_types": [
                'хакатон', 'конференция', 'митап', 'семинар', 'воркшоп', 
                'лекция', 'форум', 'круглый стол', 'панельная дискуссия', 
                'стратегическая сессия', 'нетворкинг', 'выставка', 
                'демо-день', 'питч-сессия', 'мастер-класс', 
                'образовательное мероприятие', 'мероприятие'  # ⬅️ ДОБАВЛЕНО!
            ],
            "priority_themes": [
                'AI', 'Data Science', 'Разработка', 'Веб', 'Мобильная',
                'Безопасность', 'Облака', 'DevOps', 'Блокчейн', 'Стартапы',
                'Образование', 'Бизнес'
            ],
            "location": "Санкт-Петербург",
            "max_days_future": 365,
            "min_days_future": 0
        }
    
    def filter_events(self, events):
        """Фильтрует мероприятия по критериям с улучшенной логикой"""
        if not events:
            return []
        
        print(f"🔍 Фильтруем мероприятия по критериям...")
        print(f"📊 Всего мероприятий до фильтрации: {len(events)}")
        
        filtered_events = []
        self.rejection_stats = {}
        
        for event in events:
            if self._event_matches_criteria(event):
                # Добавляем приоритет на основе критериев
                event = self._calculate_event_priority(event)
                filtered_events.append(event)
            else:
                # Записываем причину отклонения
                reason = self._get_rejection_reason(event)
                self.rejection_stats[reason] = self.rejection_stats.get(reason, 0) + 1
        
        # Сортируем по приоритету
        filtered_events.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        
        print(f"✅ Отфильтровано {len(filtered_events)} подходящих мероприятий")
        rejected_count = len(events) - len(filtered_events)
        if rejected_count > 0:
            print(f"❌ Отклонено {rejected_count} мероприятий")
        
        # Показываем причины отклонений
        if self.rejection_stats:
            print(f"\n📊 Причины отклонений:")
            for reason, count in self.rejection_stats.items():
                print(f"   - {reason}: {count}")
        
        return filtered_events
    
    def _event_matches_criteria(self, event):
        """Проверяет, соответствует ли мероприятие критериям"""
        if not isinstance(event, dict):
            return False
        
        # 1. Проверяем валидность мероприятия
        if not self._is_valid_event(event):
            return False
        
        # 2. Проверяем тип мероприятия
        if not self._matches_event_type(event):
            return False
        
        # 3. Проверяем локацию
        if not self._matches_location(event):
            return False
        
        # 4. Проверяем дату
        if not self._matches_date(event):
            return False
        
        # 5. Проверяем аудиторию (не строгая проверка)
        if not self._matches_audience(event):
            return False
        
        return True
    
    def _is_valid_event(self, event):
        """Проверяет, что мероприятие валидное и не содержит мусора"""
        title = event.get('title', '')
        description = event.get('description', '')
        
        # Проверяем наличие обязательных полей
        if not title or not isinstance(title, str):
            return False
        
        # Проверяем, что заголовок не содержит HTML/JSON кода
        invalid_patterns = [
            '<script', '</script>', 'DOCTYPE', '<html', '</html>',
            'var ', 'function(', 'JSON.parse', 'xmlns='
        ]
        
        title_lower = title.lower()
        desc_lower = description.lower() if description else ''
        
        for pattern in invalid_patterns:
            if pattern in title_lower or pattern in desc_lower:
                return False
        
        # Проверяем длину заголовка
        if len(title) < 5 or len(title) > 300:
            return False
        
        # Проверяем, что заголовок не является URL
        if title.startswith(('http://', 'https://', 'www.')):
            return False
        
        # Проверяем на наличие мусорных символов
        if re.search(r'[\[\]{}()<>]+', title) and len(title) < 20:
            return False
        
        return True
    
    def _matches_event_type(self, event):
        """Проверяет соответствие типа мероприятия"""
        event_type = event.get('type', '').lower()
        
        # Если тип не указан, пытаемся определить по заголовку
        if not event_type or event_type == 'undefined':
            event_type = self._detect_event_type(event.get('title', ''))
            event['type'] = event_type  # Обновляем тип
        
        # Разрешаем все типы из критериев + автоматически определенные
        allowed_types = self.criteria.get('event_types', [])
        
        return event_type in allowed_types
    
    def _detect_event_type(self, title):
        """Автоматически определяет тип мероприятия по заголовку"""
        title_lower = title.lower()
        
        type_mapping = [
            (['конференц', 'conference', 'conf'], 'конференция'),
            (['митап', 'meetup', 'meeting'], 'митап'),
            (['хакатон', 'hackathon', 'coding marathon'], 'хакатон'),
            (['семинар', 'workshop', 'вебинар', 'webinar'], 'семинар'),
            (['лекц', 'lecture', 'talk'], 'лекция'),
            (['форум', 'forum'], 'форум'),
            (['круглый стол', 'round table', 'panel'], 'круглый стол'),
            (['стратегическ', 'strategic'], 'стратегическая сессия'),
            (['панельн', 'panel discussion'], 'панельная дискуссия'),
            (['демо-день', 'demo day', 'demo'], 'демо-день'),
            (['питч', 'pitch', 'startup'], 'питч-сессия'),
            (['мастер-класс', 'master class', 'masterclass'], 'мастер-класс'),
            (['встреча', 'meeting', 'network', 'networking'], 'нетворкинг'),
            (['выставка', 'exhibition', 'expo'], 'выставка'),
            (['день открытых дверей', 'open doors'], 'образовательное мероприятие'),
            (['образовательн', 'education', 'edu', 'обучен'], 'образовательное мероприятие'),
            (['научн', 'science', 'research', 'исследован'], 'семинар'),
            (['tech', 'технологи', 'digital', 'цифров'], 'мероприятие'),
            (['data', 'аналитик', 'big data'], 'семинар'),
            (['ai', 'ии', 'искусственн', 'machine learning'], 'семинар')
        ]
        
        for keywords, event_type in type_mapping:
            if any(keyword in title_lower for keyword in keywords):
                return event_type
        
        return 'мероприятие'
    
    def _matches_location(self, event):
        """Проверяет соответствие локации"""
        location = event.get('location', '').lower()
        target_location = self.criteria.get('location', 'санкт-петербург').lower()
        
        # Гибкая проверка локации
        location_indicators = {
            'санкт-петербург': ['санкт-петербург', 'спб', 'петербург', 'st. petersburg'],
            'москва': ['москва', 'мск', 'moscow']
        }
        
        if target_location in location_indicators:
            allowed_indicators = location_indicators[target_location]
            return any(indicator in location for indicator in allowed_indicators)
        
        # Если локация не указана, считаем что подходит
        if not location:
            return True
            
        return target_location in location
    
    def _matches_date(self, event):
        """Проверяет соответствие даты"""
        date_str = event.get('date', '')
        if not date_str:
            return True  # Если даты нет, не фильтруем
        
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            
            # Проверяем что дата в будущем
            if event_date < today:
                return False
            
            # Проверяем максимальный срок
            max_days = self.criteria.get('max_days_future', 365)
            if (event_date - today).days > max_days:
                return False
            
            return True
            
        except ValueError:
            # Если дата в неправильном формате, не фильтруем по дате
            return True
    
    def _matches_audience(self, event):
        """Проверяет соответствие аудитории (не строгая проверка)"""
        audience = event.get('audience')
        min_audience = self.criteria.get('min_audience', 0)
        
        # Если аудитория не указана, считаем что подходит
        if audience is None:
            return True
        
        # Если аудитория указана как строка, пытаемся извлечь число
        if isinstance(audience, str):
            numbers = re.findall(r'\d+', audience)
            if numbers:
                audience = int(numbers[0])
            else:
                return True  # Если не можем извлечь число, считаем что подходит
        
        # Проверяем минимальную аудиторию
        return audience >= min_audience
    
    def _calculate_event_priority(self, event):
        """Рассчитывает приоритет мероприятия на основе критериев"""
        priority_score = event.get('priority_score', 5)  # Базовый приоритет
        
        # Повышаем приоритет по темам
        event_themes = event.get('themes', [])
        priority_themes = self.criteria.get('priority_themes', [])
        
        theme_matches = sum(1 for theme in event_themes if theme in priority_themes)
        priority_score += theme_matches * 2
        
        # Повышаем приоритет за указанную аудиторию
        if event.get('audience'):
            priority_score += 1
        
        # Повышаем приоритет за указанную дату
        if event.get('date'):
            priority_score += 1
        
        # Повышаем приоритет за описание
        if event.get('description') and len(event.get('description', '')) > 50:
            priority_score += 1
        
        # Повышаем приоритет за URL
        if event.get('url') and event['url'] not in ['', '#']:
            priority_score += 1
        
        # Ограничиваем приоритет
        event['priority_score'] = min(priority_score, 10)
        
        return event
    
    def _get_rejection_reason(self, event):
        """Возвращает причину отклонения мероприятия"""
        # Проверяем валидность
        if not self._is_valid_event(event):
            return "Невалидное мероприятие (HTML/JSON мусор или некорректные данные)"
        
        # Проверяем тип
        event_type = event.get('type', '').lower()
        if not event_type or event_type == 'undefined':
            event_type = self._detect_event_type(event.get('title', ''))
        
        allowed_types = self.criteria.get('event_types', [])
        if event_type not in allowed_types:
            return f"Тип не разрешен: {event_type}"
        
        # Проверяем локацию
        location = event.get('location', '').lower()
        target_location = self.criteria.get('location', 'санкт-петербург').lower()
        
        location_indicators = {
            'санкт-петербург': ['санкт-петербург', 'спб', 'петербург', 'st. petersburg']
        }
        
        if target_location in location_indicators:
            allowed_indicators = location_indicators[target_location]
            if not any(indicator in location for indicator in allowed_indicators):
                return f"Локация не подходит: {location}"
        
        # Проверяем дату
        date_str = event.get('date', '')
        if date_str:
            try:
                event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                today = datetime.now().date()
                
                if event_date < today:
                    return f"Мероприятие уже прошло: {date_str}"
                
                max_days = self.criteria.get('max_days_future', 365)
                if (event_date - today).days > max_days:
                    return f"Слишком далекая дата: {date_str}"
                    
            except ValueError:
                pass
        
        # Проверяем аудиторию
        audience = event.get('audience')
        min_audience = self.criteria.get('min_audience', 0)
        if audience is not None:
            if isinstance(audience, str):
                numbers = re.findall(r'\d+', audience)
                if numbers:
                    audience_num = int(numbers[0])
                    if audience_num < min_audience:
                        return f"Слишком маленькая аудитория: {audience}"
            elif isinstance(audience, int) and audience < min_audience:
                return f"Слишком маленькая аудитория: {audience}"
        
        return "Неизвестная причина"
    
    def get_rejection_stats(self):
        """Возвращает статистику отклонений"""
        return self.rejection_stats.copy()
    
    def update_criteria(self, new_criteria):
        """Обновляет критерии фильтрации"""
        if isinstance(new_criteria, dict):
            self.criteria.update(new_criteria)
    
    def get_current_criteria(self):
        """Возвращает текущие критерии"""
        return self.criteria.copy()