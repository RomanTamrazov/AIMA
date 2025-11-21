import os
import json
from datetime import datetime, timedelta
import re
from .priority_calculator import PriorityCalculator
class CriteriaFilter:
    """Фильтр мероприятий по критериям релевантности"""
    
    def __init__(self):
        self.criteria = self.load_criteria()
    
    def load_criteria(self):
        """Загружает критерии фильтрации"""
        return {
            "priority_weights": {
                "location_match": 30,
                "date_relevance": 25, 
                "theme_match": 20,
                "audience_size": 15,
                "event_type": 10
            },
            "preferred_locations": ["санкт-петербург", "спб", "петербург", "онлайн", "online"],
            "rejected_locations": ["киев", "kyiv", "украина", "україна"],
            "preferred_themes": ["AI", "Data Science", "Machine Learning", "машинное обучение", "искусственный интеллект", "нейросети"],
            "min_audience": 50,
            "max_audience": 5000,
            "max_days_past": 0,  # Не показывать прошедшие мероприятия
            "max_days_future": 365  # Показывать мероприятия до года вперед
        }
    
    def filter_events(self, events):
        """Фильтрует мероприятия по критериям с использованием нового калькулятора"""
        if not events:
            return []
        
        scored_events = []
        
        for event in events:
            # Используем новый калькулятор приоритета
            priority_score = PriorityCalculator.calculate_event_priority(event)
            event['priority_score'] = priority_score
            
            # Фильтруем по минимальному порогу
            if priority_score >= 4.0:  # Минимальный порог
                scored_events.append(event)
        
        # Сортируем по приоритету
        scored_events.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        
        return scored_events
    
    def _calculate_event_score(self, event):
        """Рассчитывает рейтинг мероприятия"""
        score = 0
        reasons = []
        
        # 1. Проверка локации
        location_score, location_reason = self._check_location(event.get('location', ''))
        score += location_score
        if location_reason:
            reasons.append(location_reason)
        
        # 2. Проверка даты
        date_score, date_reason = self._check_date(event.get('date', ''))
        score += date_score
        if date_reason:
            reasons.append(date_reason)
        
        # 3. Проверка тематик
        theme_score, theme_reason = self._check_themes(event.get('themes', []))
        score += theme_score
        if theme_reason:
            reasons.append(theme_reason)
        
        # 4. Проверка размера аудитории
        audience_score, audience_reason = self._check_audience(event.get('audience', 0))
        score += audience_score
        if audience_reason:
            reasons.append(audience_reason)
        
        # 5. Проверка типа мероприятия
        type_score, type_reason = self._check_event_type(event.get('type', ''))
        score += type_score
        if type_reason:
            reasons.append(type_reason)
        
        return score, reasons
    
    def _check_location(self, location):
        """Проверяет релевантность локации"""
        location_lower = location.lower()
        
        # Отклоняем нежелательные локации
        for rejected_loc in self.criteria["rejected_locations"]:
            if rejected_loc in location_lower:
                return 0, f"Локация не подходит: {location}"
        
        # Проверяем предпочтительные локации
        for preferred_loc in self.criteria["preferred_locations"]:
            if preferred_loc in location_lower:
                return self.criteria["priority_weights"]["location_match"], ""
        
        # Для других локаций даем средний балл
        return 10, f"Локация не в приоритете: {location}"
    
    def _check_date(self, date_str):
        """Проверяет актуальность даты"""
        try:
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Прошедшие мероприятия
            if event_date < today:
                days_past = (today - event_date).days
                if days_past <= self.criteria["max_days_past"]:
                    return 15, ""  # Недавно прошедшие еще могут быть актуальны
                else:
                    return 0, f"Мероприятие уже прошло: {date_str}"
            
            # Будущие мероприятия
            days_future = (event_date - today).days
            
            if days_future <= 7:
                return self.criteria["priority_weights"]["date_relevance"], ""  # На этой неделе
            elif days_future <= 30:
                return self.criteria["priority_weights"]["date_relevance"] - 5, ""  # В этом месяце
            elif days_future <= 90:
                return self.criteria["priority_weights"]["date_relevance"] - 10, ""  # В ближайшие 3 месяца
            elif days_future <= self.criteria["max_days_future"]:
                return 10, ""  # В пределах года
            else:
                return 5, "Слишком далекая дата"
                
        except Exception:
            return 5, "Неверный формат даты"
    
    def _check_themes(self, themes):
        """Проверяет соответствие тематик"""
        if not themes:
            return 5, "Нет тематик"
        
        theme_score = 0
        for theme in themes:
            if any(pref_theme.lower() in theme.lower() for pref_theme in self.criteria["preferred_themes"]):
                theme_score += self.criteria["priority_weights"]["theme_match"] / len(themes)
        
        if theme_score > 0:
            return theme_score, ""
        else:
            return 5, "Тематики не в приоритете"
    
    def _check_audience(self, audience):
        """Проверяет размер аудитории"""
        try:
            audience_size = int(audience)
            min_audience = self.criteria["min_audience"]
            max_audience = self.criteria["max_audience"]
            
            if min_audience <= audience_size <= max_audience:
                # Нормализуем оценку аудитории
                if audience_size <= 100:
                    return self.criteria["priority_weights"]["audience_size"], ""
                elif audience_size <= 500:
                    return self.criteria["priority_weights"]["audience_size"] - 3, ""
                else:
                    return self.criteria["priority_weights"]["audience_size"] - 5, ""
            elif audience_size < min_audience:
                return 5, f"Слишком маленькая аудитория: {audience_size}"
            else:
                return 8, f"Большая аудитория: {audience_size}"
                
        except (ValueError, TypeError):
            return 5, "Неизвестный размер аудитории"
    
    def _check_event_type(self, event_type):
        """Проверяет тип мероприятия"""
        event_type_lower = event_type.lower()
        
        type_weights = {
            'конференция': 10,
            'митап': 8, 
            'хакатон': 9,
            'семинар': 7,
            'лекция': 6,
            'образовательное мероприятие': 7,
            'форум': 8
        }
        
        score = type_weights.get(event_type_lower, 5)
        return score, ""
    
    def update_criteria(self, new_criteria):
        """Обновляет критерии фильтрации"""
        self.criteria.update(new_criteria)
    
    def get_filter_stats(self, events):
        """Возвращает статистику фильтрации"""
        filtered = self.filter_events(events)
        return {
            "total_events": len(events),
            "filtered_events": len(filtered),
            "filter_rate": len(filtered) / len(events) if events else 0
        }