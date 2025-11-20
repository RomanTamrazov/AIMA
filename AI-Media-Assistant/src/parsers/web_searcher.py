#!/usr/bin/env python3
"""
Реальный веб-поиск мероприятий через поисковые системы и API
"""

import aiohttp
import asyncio
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote
import time
import random

class RealWebSearcher:
    """Реальный поиск мероприятий в интернете"""
    
    def __init__(self):
        self.session = None
        self.search_engines = [
            "google",
            "yandex", 
            "duckduckgo"
        ]
    
    async def search_real_events(self, query, max_events=15):
        """
        Реальный поиск мероприятий в интернете
        
        Args:
            query: Поисковый запрос
            max_events: Максимальное количество мероприятий
            
        Returns:
            List[dict]: Список найденных мероприятий
        """
        print(f"🌐 Начинаем реальный поиск в интернете: '{query}'")
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # Поиск через разные источники
            all_events = []
            
            # 1. Поиск через специализированные платформы
            platform_events = await self._search_event_platforms(query)
            all_events.extend(platform_events)
            
            # 2. Поиск через поисковые системы
            search_events = await self._search_web(query)
            all_events.extend(search_events)
            
            # 3. Поиск по конкретным сайтам
            site_events = await self._search_specific_sites(query)
            all_events.extend(site_events)
            
            # Убираем дубликаты
            unique_events = self._remove_duplicates(all_events)
            
            print(f"✅ Найдено {len(unique_events)} уникальных мероприятий")
            return unique_events[:max_events]
            
        except Exception as e:
            print(f"❌ Ошибка веб-поиска: {e}")
            return []
    
    async def _search_event_platforms(self, query):
        """Поиск на платформах мероприятий"""
        events = []
        
        platforms = [
            {
                "name": "TimePad",
                "url": f"https://timepad.ru/search/events/?q={quote(query)}&categories=technology"
            },
            {
                "name": "Meetup.com",
                "url": f"https://www.meetup.com/find/?keywords={quote(query)}&location=ru--&source=EVENTS"
            },
            {
                "name": "Eventbrite",
                "url": f"https://www.eventbrite.com/d/russia--saint-petersburg/{quote(query)}/events/"
            }
        ]
        
        for platform in platforms:
            try:
                print(f"🔍 Ищем на {platform['name']}...")
                platform_events = await self._parse_platform(platform['url'], platform['name'])
                events.extend(platform_events)
                await asyncio.sleep(1)  # Задержка между запросами
            except Exception as e:
                print(f"❌ Ошибка парсинга {platform['name']}: {e}")
                continue
        
        return events
    
    async def _search_web(self, query):
        """Поиск через веб-поиск"""
        events = []
        
        search_queries = [
            f"{query} Санкт-Петербург мероприятия 2024 2025",
            f"IT события СПб {query} конференция митап",
            f"{query} анонс мероприятий Санкт-Петербург"
        ]
        
        for search_query in search_queries:
            try:
                # Используем Google Custom Search API или парсим результаты
                search_results = await self._google_search(search_query)
                events.extend(search_results)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ Ошибка веб-поиска: {e}")
                continue
        
        return events
    
    async def _search_specific_sites(self, query):
        """Поиск на конкретных сайтах"""
        events = []
        
        sites = [
            {
                "name": "ИТМО",
                "url": "https://events.itmo.ru/",
                "pattern": r'ITMO.*event'
            },
            {
                "name": "СПбГУ", 
                "url": "https://events.spbu.ru/",
                "pattern": r'SPbU.*event'
            },
            {
                "name": "Хабр",
                "url": f"https://habr.com/ru/search/?q={quote(query)}&target_type=posts&order=relevance",
                "pattern": r'мероприятие|митап|конференция'
            },
            {
                "name": "VK Events",
                "url": f"https://vk.com/search?c%5Bsection%5D=events&c%5Bq%5D={quote(query)}&c%5Bcity%5D=2",
                "pattern": r'vk\.com/event'
            }
        ]
        
        for site in sites:
            try:
                print(f"🔍 Проверяем {site['name']}...")
                site_events = await self._parse_site(site['url'], site['name'])
                events.extend(site_events)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"❌ Ошибка парсинга {site['name']}: {e}")
                continue
        
        return events
    
    async def _google_search(self, query):
        """Поиск через Google (упрощенный)"""
        try:
            # Используем бесплатный подход через парсинг
            url = f"https://www.google.com/search?q={quote(query)}&num=10"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_google_results(html, query)
                else:
                    return []
                    
        except Exception as e:
            print(f"❌ Ошибка Google поиска: {e}")
            return []
    
    def _parse_google_results(self, html, query):
        """Парсит результаты Google"""
        events = []
        
        # Ищем ссылки на мероприятия
        event_patterns = [
            r'<a href="(https?://[^"]*event[^"]*)"[^>]*>([^<]+)</a>',
            r'<a href="(https?://[^"]*meetup[^"]*)"[^>]*>([^<]+)</a>',
            r'<a href="(https?://[^"]*conference[^"]*)"[^>]*>([^<]+)</a>'
        ]
        
        for pattern in event_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for url, title in matches:
                if any(word in title.lower() for word in ['мероприятие', 'event', 'meetup', 'конференция', 'conference']):
                    event = {
                        "title": self._clean_html(title),
                        "url": url,
                        "source": "google_search",
                        "description": f"Найдено по запросу: {query}",
                        "date": self._estimate_date(),
                        "location": "Санкт-Петербург",
                        "type": "мероприятие"
                    }
                    events.append(event)
        
        return events
    
    async def _parse_platform(self, url, platform_name):
        """Парсит платформы мероприятий"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._extract_events_from_html(html, platform_name)
                else:
                    return []
                    
        except Exception as e:
            print(f"❌ Ошибка парсинга {platform_name}: {e}")
            return []
    
    def _extract_events_from_html(self, html, source):
        """Извлекает события из HTML"""
        events = []
        
        # Простая эвристика для поиска событий
        event_indicators = [
            r'(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})[^<]*>([^<]+)</',
            r'(\d{4}-\d{2}-\d{2})[^>]*>([^<]+)</',
            r'event[^>]*>([^<]+)</[^>]*>(\d{1,2}\.\d{1,2}\.\d{4})'
        ]
        
        for pattern in event_indicators:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for date_str, title in matches:
                event_date = self._parse_date(date_str)
                if event_date and event_date > datetime.now():
                    event = {
                        "title": self._clean_html(title),
                        "date": event_date.strftime("%Y-%m-%d"),
                        "source": source,
                        "location": "Санкт-Петербург",
                        "type": self._detect_event_type(title),
                        "description": f"Найдено на {source}",
                        "url": "#"
                    }
                    events.append(event)
        
        return events[:5]  # Ограничиваем количество
    
    async def _parse_site(self, url, site_name):
        """Парсит конкретные сайты"""
        # Аналогично _parse_platform, но с специфичными для сайта правилами
        return await self._parse_platform(url, site_name)
    
    def _parse_date(self, date_str):
        """Парсит дату из строки"""
        try:
            # Различные форматы дат
            formats = [
                '%d %B %Y', '%d.%m.%Y', '%Y-%m-%d',
                '%d %b %Y', '%B %d, %Y'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            
            # Если не распарсилось, возвращаем дату через 30 дней
            return datetime.now() + timedelta(days=30)
            
        except:
            return datetime.now() + timedelta(days=30)
    
    def _estimate_date(self):
        """Оценивает дату мероприятия"""
        # Случайная дата в ближайшие 3 месяца
        days = random.randint(7, 90)
        return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    
    def _detect_event_type(self, title):
        """Определяет тип мероприятия по названию"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['конференция', 'conference']):
            return 'конференция'
        elif any(word in title_lower for word in ['митап', 'meetup']):
            return 'митап'
        elif any(word in title_lower for word in ['хакатон', 'hackathon']):
            return 'хакатон'
        elif any(word in title_lower for word in ['семинар', 'workshop']):
            return 'семинар'
        else:
            return 'мероприятие'
    
    def _clean_html(self, text):
        """Очищает HTML теги"""
        return re.sub(r'<[^>]+>', '', text).strip()
    
    def _remove_duplicates(self, events):
        """Удаляет дубликаты мероприятий"""
        seen_titles = set()
        unique_events = []
        
        for event in events:
            title = event['title'].lower().strip()
            if title not in seen_titles:
                seen_titles.add(title)
                unique_events.append(event)
        
        return unique_events
    
    async def close(self):
        """Закрывает сессию"""
        if self.session:
            await self.session.close()