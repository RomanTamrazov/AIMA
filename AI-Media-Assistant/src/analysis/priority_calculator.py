class PriorityCalculator:
    """Калькулятор приоритета для мероприятий и приглашений"""
    
    @staticmethod
    def calculate_event_priority(event):
        """
        Рассчитывает приоритет мероприятия по комплексным критериям
        Возвращает оценку от 0 до 10
        """
        score = 0
        max_possible_score = 100  # Базовый максимум для нормализации
        
        # 1. Тематическая релевантность (макс 30 баллов)
        theme_score = PriorityCalculator._calculate_theme_score(event.get('themes', []))
        score += theme_score
        
        # 2. Временная релевантность (макс 25 баллов)
        date_score = PriorityCalculator._calculate_date_score(event.get('date', ''))
        score += date_score
        
        # 3. Географическая релевантность (макс 20 баллов)
        location_score = PriorityCalculator._calculate_location_score(event.get('location', ''))
        score += location_score
        
        # 4. Масштаб мероприятия (макс 15 баллов)
        audience_score = PriorityCalculator._calculate_audience_score(event.get('audience', 0))
        score += audience_score
        
        # 5. Тип мероприятия (макс 10 баллов)
        type_score = PriorityCalculator._calculate_type_score(event.get('type', ''))
        score += type_score
        
        # Нормализуем до шкалы 0-10
        normalized_score = (score / max_possible_score) * 10
        
        return round(normalized_score, 1)
    
    @staticmethod
    def _calculate_theme_score(themes):
        """Оценка тематической релевантности"""
        priority_themes = {
            'AI': 30, 'искусственный интеллект': 30, 'машинное обучение': 30,
            'Data Science': 25, 'аналитика данных': 25, 'большие данные': 25,
            'нейросети': 25, 'Computer Vision': 25,
            'highload': 20, 'производительность': 20, 'базы данных': 20,
            'DevOps': 20, 'облака': 20, 'Kubernetes': 20,
            'тестирование': 15, 'QA': 15, 'автоматизация': 15,
            'JavaScript': 15, 'Python': 15, 'Go': 15,
            'frontend': 10, 'backend': 10, 'мобильная разработка': 10,
            'кибербезопасность': 10, 'security': 10,
            'образование': 5, 'карьера': 5, 'стартапы': 5
        }
        
        if not themes:
            return 5
        
        max_theme_score = 0
        for theme in themes:
            for priority_theme, points in priority_themes.items():
                if priority_theme.lower() in theme.lower():
                    max_theme_score = max(max_theme_score, points)
        
        return max_theme_score if max_theme_score > 0 else 5
    
    @staticmethod
    def _calculate_date_score(date_str):
        """Оценка временной релевантности"""
        try:
            from datetime import datetime
            event_date = datetime.strptime(date_str, '%Y-%m-%d')
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            days_diff = (event_date - today).days
            
            if days_diff < 0:
                return 0  # Прошедшие мероприятия
            
            if days_diff <= 7:
                return 25  # На этой неделе
            elif days_diff <= 30:
                return 20  # В этом месяце
            elif days_diff <= 90:
                return 15  # В ближайшие 3 месяца
            elif days_diff <= 180:
                return 10  # В ближайшие 6 месяцев
            else:
                return 5   # Более 6 месяцев
            
        except Exception:
            return 3  # Неверная дата
    
    @staticmethod
    def _calculate_location_score(location):
        """Оценка географической релевантности"""
        location_lower = location.lower()
        
        # Высший приоритет - СПб + онлайн
        if any(loc in location_lower for loc in ['санкт-петербург', 'спб', 'петербург']) and \
           any(online in location_lower for online in ['онлайн', 'online']):
            return 20
        
        # Высокий приоритет - только СПб
        elif any(loc in location_lower for loc in ['санкт-петербург', 'спб', 'петербург']):
            return 18
        
        # Высокий приоритет - онлайн из любого места
        elif any(online in location_lower for online in ['онлайн', 'online']):
            return 16
        
        # Средний приоритет - Москва + онлайн
        elif 'москва' in location_lower and any(online in location_lower for online in ['онлайн', 'online']):
            return 14
        
        # Низкий приоритет - другие локации
        elif any(loc in location_lower for loc in ['москва', 'новосибирск']):
            return 8
        
        # Минимальный приоритет - неизвестные локации
        else:
            return 5
    
    @staticmethod
    def _calculate_audience_score(audience):
        """Оценка масштаба мероприятия"""
        try:
            audience_size = int(audience)
            
            if audience_size >= 1000:
                return 15  # Крупные конференции
            elif audience_size >= 500:
                return 12  # Большие мероприятия
            elif audience_size >= 200:
                return 10  # Средние мероприятия
            elif audience_size >= 100:
                return 8   # Небольшие мероприятия
            elif audience_size >= 50:
                return 6   # Маленькие встречи
            else:
                return 4   # Очень маленькие
            
        except (ValueError, TypeError):
            return 5  # Неизвестный размер
    
    @staticmethod
    def _calculate_type_score(event_type):
        """Оценка типа мероприятия"""
        type_weights = {
            'конференция': 10,
            'хакатон': 9,
            'митап': 8,
            'семинар': 7,
            'лекция': 6,
            'образовательное мероприятие': 6,
            'форум': 8,
            'круглый стол': 7,
            'мероприятие': 5
        }
        
        return type_weights.get(event_type.lower(), 5)
    
    @staticmethod
    def calculate_partner_priority(invitation):
        """
        Рассчитывает приоритет приглашения от партнеров
        на основе критериев из кейса
        """
        priority_factors = {
            'strategic_partner': 3,
            'long_term_partner': 2,
            'new_partner': 1,
            'high_audience': 2,
            'government_related': 3,
            'educational': 2,
            'international': 2
        }
        
        score = 0
        
        # Анализ типа партнера
        partner_type = invitation.get('partner_type', '')
        if partner_type in ['government', 'university']:
            score += priority_factors['strategic_partner']
        elif partner_type == 'long_term':
            score += priority_factors['long_term_partner']
        else:
            score += priority_factors['new_partner']
        
        # Анализ аудитории
        if invitation.get('expected_audience', 0) >= 200:
            score += priority_factors['high_audience']
        
        # Дополнительные факторы
        if invitation.get('is_government_related', False):
            score += priority_factors['government_related']
        
        if invitation.get('is_educational', False):
            score += priority_factors['educational']
        
        if invitation.get('is_international', False):
            score += priority_factors['international']
        
        return score
    
    @staticmethod
    def categorize_priority(score):
        """Категоризирует приоритет по баллам (0-10 шкала)"""
        if score >= 8.0:
            return "🔥 Высокий"
        elif score >= 6.0:
            return "✅ Средний"
        elif score >= 4.0:
            return "ℹ️ Низкий"
        else:
            return "❌ Очень низкий"
    
    @staticmethod
    def get_priority_color(score):
        """Возвращает цвет для визуализации приоритета"""
        if score >= 8.0:
            return "🟢"  # Зеленый
        elif score >= 6.0:
            return "🟡"  # Желтый
        elif score >= 4.0:
            return "🟠"  # Оранжевый
        else:
            return "🔴"  # Красный