class PriorityCalculator:
    """Калькулятор приоритета для входящих приглашений"""
    
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
        """Категоризирует приоритет по баллам"""
        if score >= 8:
            return "Высокий"
        elif score >= 5:
            return "Средний"
        else:
            return "Низкий"