import json
from datetime import datetime, timedelta

# Импортируем config из корня
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import config

class CriteriaFilter:
    """Улучшенный фильтр мероприятий с гибкими критериями"""
    
    def __init__(self):
        self.criteria_config = config.load_criteria_config()
        if self.criteria_config:
            self.criteria = self.criteria_config.get("criteria", config.CRITERIA)
            self.scoring_weights = self.criteria_config.get("scoring_weights", {})
        else:
            self.criteria = config.CRITERIA
            self.scoring_weights = {}
        
        # Статистика фильтрации
        self.stats = {
            'processed': 0,
            'passed': 0,
            'rejected': 0,
            'rejection_reasons': {}
        }
    
    def filter_events(self, events):
        """Фильтрует мероприятия по заданным критериям"""
        print("🔍 Фильтруем мероприятия по критериям...")
        print(f"📊 Всего мероприятий до фильтрации: {len(events)}")
        
        filtered_events = []
        self.stats = {'processed': 0, 'passed': 0, 'rejected': 0, 'rejection_reasons': {}}
        
        for event in events:
            self.stats['processed'] += 1
            meets_criteria, reason = self._meets_criteria_with_reason(event)
            
            if meets_criteria:
                # Добавляем оценку приоритета
                event['priority_score'] = self._calculate_priority(event)
                event['match_reasons'] = self._get_match_reasons(event)
                filtered_events.append(event)
                self.stats['passed'] += 1
            else:
                self.stats['rejected'] += 1
                self.stats['rejection_reasons'][reason] = self.stats['rejection_reasons'].get(reason, 0) + 1
        
        # Сортируем по приоритету
        filtered_events.sort(key=lambda x: x['priority_score'], reverse=True)
        
        self._print_filter_stats()
        return filtered_events
    
    def _meets_criteria_with_reason(self, event):
        """Проверяет критерии и возвращает причину отказа"""
        
        # Проверка типа мероприятия (самая строгая проверка)
        type_ok, type_reason = self._check_event_type_with_reason(event)
        if not type_ok:
            return False, type_reason
        
        # Проверка местоположения
        location_ok, location_reason = self._check_location_with_reason(event)
        if not location_ok:
            return False, location_reason
        
        # Проверка аудитории
        audience_ok, audience_reason = self._check_audience_with_reason(event)
        if not audience_ok:
            return False, audience_reason
        
        # Проверка тематики (самая гибкая проверка)
        themes_ok, themes_reason = self._check_themes_with_reason(event)
        if not themes_ok:
            return False, themes_reason
        
        return True, "Все критерии пройдены"
    
    def _check_event_type_with_reason(self, event):
        """Проверка типа мероприятия с причиной"""
        event_type = event.get('type', '').lower()
        allowed_types = [t.lower() for t in self.criteria.get('event_types', [])]
        
        if not event_type:
            return True, "Тип не указан (пропускаем проверку)"
        
        if event_type in allowed_types:
            return True, f"Тип разрешен: {event_type}"
        else:
            return False, f"Тип не разрешен: {event_type}. Разрешены: {allowed_types}"
    
    def _check_location_with_reason(self, event):
        """Проверка местоположения с причиной"""
        location = event.get('location', '').lower()
        
        # Если локация не указана, пропускаем проверку
        if not location or location == 'не указано':
            return True, "Локация не указана (пропускаем проверку)"
        
        # Проверяем приоритетные локации
        priority_locations = self.criteria.get('location_priority', [])
        for loc in priority_locations:
            if loc.lower() in location:
                return True, f"Приоритетная локация: {loc}"
        
        # Проверяем исключенные локации
        excluded_locations = self.criteria.get('excluded_locations', [])
        for loc in excluded_locations:
            if loc.lower() in location:
                return False, f"Исключенная локация: {loc}"
        
        # Для неизвестных локаций разрешаем, но с пониженным приоритетом
        return True, f"Неизвестная локация (разрешено): {location}"
    
    def _check_audience_with_reason(self, event):
        """Проверка размера аудитории с причиной"""
        audience = event.get('audience', 0)
        min_audience = self.criteria.get('min_audience', 10)  # По умолчанию 10
        
        # Если аудитория не указана, пропускаем проверку
        if audience == 0 or audience == 'не указано':
            return True, "Аудитория не указана (пропускаем проверку)"
        
        if audience >= min_audience:
            return True, f"Аудитория {audience} >= {min_audience}"
        else:
            return False, f"Аудитория {audience} < {min_audience}"
    
    def _check_themes_with_reason(self, event):
        """Проверка тематики мероприятия с причиной"""
        themes = event.get('themes', [])
        event_title = event.get('title', '').lower()
        event_desc = event.get('description', '').lower()
        
        # Объединяем все тексты для поиска ключевых слов
        search_text = ' '.join(themes) + ' ' + event_title + ' ' + event_desc
        
        # Проверяем наличие приоритетных тем
        priority_themes = self.criteria.get('priority_themes', [])
        for theme in priority_themes:
            if theme.lower() in search_text:
                return True, f"Найдена тема: {theme}"
        
        # Если темы не найдены, все равно пропускаем (гибкая проверка)
        # но с пониженным приоритетом
        return True, "Приоритетные темы не найдены (но разрешено)"
    
    def _calculate_priority(self, event):
        """Рассчитывает приоритет мероприятия (0-10 баллов)"""
        score = 5  # Базовый балл
        
        # Баллы за размер аудитории
        audience = event.get('audience', 0)
        if audience >= 500:
            score += 3
        elif audience >= 200:
            score += 2
        elif audience >= 100:
            score += 1
        
        # Баллы за тематику
        themes = event.get('themes', [])
        themes_lower = [theme.lower() for theme in themes]
        event_text = ' '.join(themes_lower) + ' ' + event.get('title', '').lower()
        
        priority_themes = self.criteria.get('priority_themes', [])
        theme_matches = sum(1 for theme in priority_themes if theme.lower() in event_text)
        score += min(theme_matches, 3)  # Максимум +3 за темы
        
        # Баллы за тип мероприятия
        event_type = event.get('type', '').lower()
        if event_type in ['стратегическая сессия', 'правительственное мероприятие']:
            score += 2
        elif event_type in ['конференция', 'форум']:
            score += 2
        elif event_type in ['хакатон']:
            score += 2
        
        # Ограничиваем максимальный балл
        return min(score, 10)
    
    def _get_match_reasons(self, event):
        """Возвращает причины, по которым мероприятие подходит"""
        reasons = []
        
        # Проверка тематики
        themes = event.get('themes', [])
        event_text = ' '.join(themes) + ' ' + event.get('title', '') + ' ' + event.get('description', '')
        event_text = event_text.lower()
        
        priority_themes = self.criteria.get('priority_themes', [])
        matched_themes = [theme for theme in priority_themes if theme.lower() in event_text]
        
        if matched_themes:
            reasons.append(f"Темы: {', '.join(matched_themes[:2])}")
        
        # Проверка типа мероприятия
        event_type = event.get('type', '')
        if event_type:
            reasons.append(f"Тип: {event_type}")
        
        # Проверка аудитории
        audience = event.get('audience', 0)
        if audience >= 200:
            reasons.append(f"Аудитория: {audience}+")
        
        return reasons[:3]
    
    def _print_filter_stats(self):
        """Печатает статистику фильтрации"""
        print(f"✅ Отфильтровано {self.stats['passed']} подходящих мероприятий")
        print(f"❌ Отклонено {self.stats['rejected']} мероприятий")
        
        if self.stats['rejection_reasons']:
            print("\n📊 Причины отклонений:")
            for reason, count in self.stats['rejection_reasons'].items():
                if count > 0:  # Показываем только значимые причины
                    print(f"   - {reason}: {count}")