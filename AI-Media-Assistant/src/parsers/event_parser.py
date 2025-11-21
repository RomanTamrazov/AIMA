import json
import os
from datetime import datetime
import re

# Импортируем config из корня
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import config

from src.parsers.sources import EventSources

class EventParser:
    """Упрощенный парсер мероприятий - берет данные напрямую из sources.py"""
    
    def __init__(self):
        self.sources = EventSources()
    
    async def parse_events(self, use_llm_search=False, use_real_parsing=False, use_web_search=False):
        """
        Просто возвращает мероприятия из проверенной базы
        """
        print("📥 Загружаем мероприятия из проверенной базы...")
        
        # Берем мероприятия напрямую из sources.py
        events = self.sources._get_verified_real_events()
        
        print(f"✅ Загружено {len(events)} проверенных мероприятий")
        return events
    
    def save_events(self, events):
        """Сохраняет мероприятия в JSON файл (для совместимости)"""
        try:
            if not isinstance(events, list):
                events = []
                
            events_data = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_events": len(events),
                    "sources_used": ["verified_database"]
                },
                "events": events
            }
            
            os.makedirs(os.path.dirname(config.EVENTS_DB), exist_ok=True)
            
            with open(config.EVENTS_DB, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"❌ Ошибка при сохранении мероприятий: {e}")
    
    def load_events(self):
        """Загружает мероприятия из JSON файла"""
        try:
            if not os.path.exists(config.EVENTS_DB):
                return self.sources._get_verified_real_events()
                
            with open(config.EVENTS_DB, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'events' in data:
                    return data.get('events', [])
                elif isinstance(data, list):
                    return data
                else:
                    return self.sources._get_verified_real_events()
        except Exception:
            return self.sources._get_verified_real_events()
    
    def get_events_statistics(self):
        """Возвращает статистику по мероприятиям"""
        events = self.sources._get_verified_real_events()
        
        if not events:
            return {"total": 0}
        
        stats = {
            "total": len(events),
            "by_type": {},
            "by_month": {},
            "by_source": {}
        }
        
        for event in events:
            if not isinstance(event, dict):
                continue
                
            event_type = event.get('type', 'неизвестно')
            stats["by_type"][event_type] = stats["by_type"].get(event_type, 0) + 1
            
            try:
                date_str = event.get('date', '')
                if date_str:
                    month = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m')
                    stats["by_month"][month] = stats["by_month"].get(month, 0) + 1
            except:
                pass
            
            source = event.get('source', 'неизвестно')
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
        
        return stats
    
    def get_events_by_themes(self, themes):
        """Возвращает мероприятия по тематикам"""
        events = self.sources._get_verified_real_events()
        
        if not themes or not events:
            return []
        
        filtered_events = []
        for event in events:
            event_themes = event.get('themes', [])
            # Проверяем пересечение тематик
            if any(theme.lower() in ' '.join(event_themes).lower() for theme in themes):
                filtered_events.append(event)
        
        return filtered_events
    
    def get_upcoming_events(self, days=30):
        """Возвращает ближайшие мероприятия"""
        events = self.sources._get_verified_real_events()
        
        if not events:
            return []
        
        today = datetime.now().date()
        upcoming = []
        
        for event in events:
            try:
                event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
                days_diff = (event_date - today).days
                if 0 <= days_diff <= days:
                    upcoming.append(event)
            except:
                continue
        
        # Сортируем по дате
        upcoming.sort(key=lambda x: x['date'])
        return upcoming
    
    async def close(self):
        """Закрывает ресурсы"""
        await self.sources.close()