#!/usr/bin/env python3
"""
Менеджер расширенного поиска мероприятий
"""

import asyncio
import json
from datetime import datetime
from .simple_llm_searcher import SimpleLLMSearcher  # ⬅️ ИЗМЕНЕНО

class SearchManager:
    """Управляет расширенным поиском мероприятий"""
    
    def __init__(self):
        self.searcher = SimpleLLMSearcher()  # ⬅️ ИЗМЕНЕНО
        self.search_cache = {}
    
    async def enhanced_search(self, search_type, params, max_results=15):
        """
        Расширенный поиск мероприятий
        """
        cache_key = f"{search_type}_{str(params)}"
        
        # Проверяем кэш (простой, без времени)
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]
        
        print(f"🔍 Запускаем расширенный поиск: {search_type}")
        
        try:
            if search_type == 'themes':
                events = await self.searcher.search_by_themes(params, max_results)
            elif search_type == 'upcoming':
                events = await self.searcher.search_upcoming_events(params, max_results)
            elif search_type == 'custom':
                events = await self.searcher.search_events_with_llm(params, max_results)
            else:
                events = []
            
            # Сохраняем в кэш
            self.search_cache[cache_key] = events
            
            return events
            
        except Exception as e:
            print(f"❌ Ошибка расширенного поиска: {e}")
            return []
    
    async def smart_recommendations(self, user_preferences, max_results=12):
        """
        Умные рекомендации на основе предпочтений пользователя
        """
        themes = user_preferences.get('themes', ['AI', 'IT'])
        
        # Ищем по приоритетным темам
        all_events = []
        
        for theme in themes[:2]:  # Берем топ-2 темы
            events = await self.searcher.search_by_themes([theme], max_results // 2)
            all_events.extend(events)
            await asyncio.sleep(1)  # Задержка между запросами
        
        # Убираем дубликаты
        unique_events = self._remove_duplicates(all_events)
        
        return unique_events[:max_results]
    
    def _remove_duplicates(self, events):
        """Убирает дубликаты мероприятий"""
        seen_titles = set()
        unique_events = []
        
        for event in events:
            title = event['title'].lower().strip()
            if title not in seen_titles:
                seen_titles.add(title)
                unique_events.append(event)
        
        return unique_events
    
    def get_search_statistics(self):
        """Возвращает статистику поиска"""
        return {
            'total_searches': len(self.search_cache),
            'cache_size': len(self.search_cache)
        }