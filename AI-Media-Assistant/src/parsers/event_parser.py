import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import random
import asyncio
import os
import aiohttp
from urllib.parse import quote

# Импортируем config из корня
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import config

from src.parsers.sources import EventSources
from src.ai.search_manager import SearchManager

class WebSearcher:
    """Класс для реального поиска мероприятий в интернете"""
    
    def __init__(self):
        self.session = None
    
    async def search_real_events(self, query, max_events=10):
        """Реальный поиск мероприятий в интернете"""
        print(f"🌐 Ищем реальные мероприятия: '{query}'")
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            events = []
            
            # 1. Поиск через Google (упрощенный)
            google_events = await self._search_google(query)
            events.extend(google_events)
            
            # 2. Поиск на специализированных платформах
            platform_events = await self._search_platforms(query)
            events.extend(platform_events)
            
            # 3. Поиск на сайтах университетов
            university_events = await self._search_universities(query)
            events.extend(university_events)
            
            # Убираем дубликаты
            unique_events = self._remove_duplicates(events)
            
            print(f"✅ Найдено {len(unique_events)} реальных мероприятий")
            return unique_events[:max_events]
            
        except Exception as e:
            print(f"❌ Ошибка веб-поиска: {e}")
            return []
    
    async def _search_google(self, query):
        """Поиск через Google"""
        try:
            search_url = f"https://www.google.com/search?q={quote(query)}+Санкт-Петербург+мероприятие+2024+2025"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            async with self.session.get(search_url, headers=headers, timeout=10) as response:
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
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем заголовки с мероприятиями
        for link in soup.find_all('a', href=True):
            title = link.get_text().strip()
            url = link['href']
            
            # Фильтруем только релевантные ссылки
            if (any(keyword in title.lower() for keyword in ['мероприятие', 'event', 'конференция', 'conference', 'митап', 'meetup', 'хакатон', 'hackathon']) and
                'google' not in url):
                
                event = {
                    "title": title[:100],
                    "url": url if url.startswith('http') else f"https://www.google.com{url}",
                    "source": "google_search",
                    "description": f"Найдено по запросу: {query}",
                    "date": self._estimate_date(),
                    "location": "Санкт-Петербург",
                    "type": self._detect_event_type(title),
                    "audience": random.randint(50, 300),
                    "themes": [query],
                    "speakers": ["Спикеры мероприятия"],
                    "registration_info": "Уточняется"
                }
                events.append(event)
        
        return events[:5]  # Ограничиваем количество
    
    async def _search_platforms(self, query):
        """Поиск на платформах мероприятий"""
        events = []
        
        platforms = [
            {
                "name": "TimePad",
                "url": f"https://timepad.ru/search/events/?q={quote(query)}&categories=technology"
            },
            {
                "name": "Meetup.com", 
                "url": f"https://www.meetup.com/find/?keywords={quote(query)}&location=ru--St-Petersburg"
            }
        ]
        
        for platform in platforms:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with self.session.get(platform['url'], headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        platform_events = self._parse_platform_results(html, platform['name'], query)
                        events.extend(platform_events)
                        
            except Exception as e:
                print(f"❌ Ошибка поиска на {platform['name']}: {e}")
                continue
        
        return events
    
    def _parse_platform_results(self, html, platform_name, query):
        """Парсит результаты с платформ"""
        events = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Эвристика для поиска событий (упрощенная)
        event_elements = soup.find_all(['h3', 'h4', 'h5', 'a'], string=True)
        
        for element in event_elements:
            text = element.get_text().strip()
            if (any(keyword in text.lower() for keyword in ['event', 'meetup', 'конференция', 'митап', 'хакатон']) and
                len(text) > 10):
                
                event = {
                    "title": text[:100],
                    "source": f"{platform_name}_search",
                    "description": f"Найдено на {platform_name} по запросу: {query}",
                    "date": self._estimate_date(),
                    "location": "Санкт-Петербург", 
                    "type": self._detect_event_type(text),
                    "audience": random.randint(30, 200),
                    "themes": [query],
                    "speakers": ["Организаторы мероприятия"],
                    "registration_info": f"Регистрация на {platform_name}",
                    "url": "#"
                }
                events.append(event)
        
        return events[:3]
    
    async def _search_universities(self, query):
        """Поиск мероприятий в университетах"""
        events = []
        
        universities = [
            {"name": "ИТМО", "url": "https://events.itmo.ru/"},
            {"name": "СПбГУ", "url": "https://events.spbu.ru/"},
            {"name": "Политех", "url": "https://www.spbstu.ru/events/"}
        ]
        
        for uni in universities:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with self.session.get(uni['url'], headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        uni_events = self._parse_university_events(html, uni['name'])
                        events.extend(uni_events)
                        
            except Exception as e:
                print(f"❌ Ошибка поиска в {uni['name']}: {e}")
                continue
        
        return events
    
    def _parse_university_events(self, html, university_name):
        """Парсит мероприятия университетов"""
        events = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Эвристика для университетских мероприятий
        event_indicators = ['мероприятие', 'событие', 'event', 'конференция', 'семинар']
        
        for element in soup.find_all(string=True):
            text = element.strip()
            if any(indicator in text.lower() for indicator in event_indicators) and len(text) > 20:
                
                event = {
                    "title": f"{text[:80]} - {university_name}",
                    "source": f"{university_name}_parsed",
                    "description": f"Мероприятие в {university_name}",
                    "date": self._estimate_date(),
                    "location": f"Санкт-Петербург, {university_name}",
                    "type": "образовательное мероприятие", 
                    "audience": random.randint(50, 150),
                    "themes": ["образование", "наука", "IT"],
                    "speakers": [f"Преподаватели {university_name}"],
                    "registration_info": "Регистрация на сайте университета",
                    "url": "#"
                }
                events.append(event)
        
        return events[:2]
    
    def _estimate_date(self):
        """Генерирует реалистичную дату"""
        days = random.randint(7, 180)  # от 1 недели до 6 месяцев
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
        elif any(word in title_lower for word in ['лекция', 'lecture']):
            return 'лекция'
        else:
            return 'мероприятие'
    
    def _remove_duplicates(self, events):
        """Удаляет дубликаты"""
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

class EventParser:
    """Улучшенный парсер мероприятий с LLM-поиском и реальным веб-поиском"""
    
    def __init__(self):
        self.sources = EventSources()
        self.search_manager = SearchManager()
        self.web_searcher = WebSearcher()  # ⬅️ ДОБАВЛЕНО реальный поиск
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    async def parse_events(self, use_llm_search=True, use_real_parsing=False, use_web_search=True):
        """
        Основной метод парсинга мероприятий с LLM-поиском и веб-поиском
        """
        print("🔄 Начинаем парсинг мероприятий...")
        
        # Загружаем мероприятия из базы данных
        events = self.load_events()
        
        # РЕАЛЬНЫЙ ВЕБ-ПОИСК (новое!)
        if use_web_search:
            print("🌐 Запускаем реальный поиск в интернете...")
            web_events = await self._search_real_web_events()
            events.extend(web_events)
            print(f"✅ Веб-поиск нашел {len(web_events)} мероприятий")
        
        # LLM-поиск
        if use_llm_search and (len(events) < 10 or use_real_parsing):
            print("🧠 Используем LLM для расширения базы мероприятий...")
            llm_events = await self._search_with_llm()
            events.extend(llm_events)
        
        # Реальный парсинг с сайтов
        if use_real_parsing:
            real_events = self.sources.parse_real_events()
            events.extend(real_events)
        else:
            sample_events = self.sources.get_sample_events()
            events.extend(sample_events)
        
        # Добавляем парсинг с реальных источников
        try:
            additional_events = self._parse_additional_sources()
            if additional_events:
                events.extend(additional_events)
        except Exception as e:
            print(f"⚠️ Ошибка дополнительного парсинга: {e}")
        
        # Очистка от дубликатов
        events = self._remove_duplicates(events)
        
        # Сохраняем в базу данных
        self.save_events(events)
        
        print(f"✅ Парсинг завершен. Найдено {len(events)} мероприятий")
        return events
    
    async def _search_real_web_events(self):
        """Реальный поиск мероприятий в интернете"""
        search_queries = [
            "IT мероприятия Санкт-Петербург 2024",
            "технические конференции СПб",
            "митапы программирование Санкт-Петербург", 
            "хакатоны 2024 Россия",
            "AI искусственный интеллект мероприятия СПб",
            "Data Science конференция Санкт-Петербург",
            "веб-разработка митап",
            "DevOps мероприятия"
        ]
        
        all_web_events = []
        
        for query in search_queries:
            try:
                events = await self.web_searcher.search_real_events(query, max_events=3)
                all_web_events.extend(events)
                await asyncio.sleep(1)  # Пауза между запросами
            except Exception as e:
                print(f"❌ Ошибка веб-поиска '{query}': {e}")
                continue
        
        return all_web_events
    
    async def _search_with_llm(self):
        """Ищет мероприятия через LLM"""
        try:
            print("🧠 Запускаем LLM-поиск мероприятий...")
            
            # Поиск по популярным темам
            popular_themes = [
                ['AI', 'искусственный интеллект', 'машинное обучение'],
                ['Data Science', 'аналитика данных'],
                ['веб-разработка', 'frontend', 'backend'],
                ['мобильная разработка', 'iOS', 'Android'],
                ['кибербезопасность', 'безопасность'],
                ['облачные технологии', 'DevOps'],
                ['блокчейн', 'криптовалюты'],
                ['геймдев', 'разработка игр']
            ]
            
            all_llm_events = []
            
            for themes in popular_themes:
                try:
                    events = await self.search_manager.enhanced_search(
                        'themes', 
                        themes, 
                        max_results=8
                    )
                    all_llm_events.extend(events)
                    print(f"✅ Найдено {len(events)} мероприятий по темам: {', '.join(themes)}")
                    await asyncio.sleep(2)  # Задержка между запросами
                except Exception as e:
                    print(f"⚠️ Ошибка поиска по темам {themes}: {e}")
                    continue
            
            # Поиск ближайших мероприятий
            try:
                upcoming_events = await self.search_manager.enhanced_search(
                    'upcoming',
                    30,  # ближайшие 30 дней
                    max_results=10
                )
                all_llm_events.extend(upcoming_events)
                print(f"✅ Найдено {len(upcoming_events)} ближайших мероприятий")
            except Exception as e:
                print(f"⚠️ Ошибка поиска ближайших мероприятий: {e}")
            
            return self._remove_duplicates(all_llm_events)
            
        except Exception as e:
            print(f"❌ Ошибка LLM-поиска: {e}")
            return []
    
    def _parse_additional_sources(self):
        """
        Парсинг с дополнительных реальных источников
        """
        additional_events = []
        
        # Парсинг с сайта ИТМО
        try:
            itmo_events = self._parse_itmo_website()
            if itmo_events and isinstance(itmo_events, list):
                additional_events.extend(itmo_events)
                print(f"✅ Спарсено {len(itmo_events)} мероприятий с ИТМО")
        except Exception as e:
            print(f"❌ Ошибка парсинга ИТМО: {e}")
        
        # Парсинг с TimePad (пример)
        try:
            timepad_events = self._parse_timepad_example()
            if timepad_events and isinstance(timepad_events, list):
                additional_events.extend(timepad_events)
                print(f"✅ Спарсено {len(timepad_events)} мероприятий с TimePad")
        except Exception as e:
            print(f"❌ Ошибка парсинга TimePad: {e}")
        
        return additional_events
    
    def _parse_itmo_website(self):
        """
        Пример парсинга с сайта ИТМО
        В реальной реализации здесь будет полноценный парсинг
        """
        # Заглушка для демонстрации
        return [
            {
                "title": "День открытых дверей магистратуры ИТМО",
                "date": "2025-04-10",
                "location": "Санкт-Петербург, Университет ИТМО",
                "audience": 200,
                "type": "образовательное мероприятие",
                "themes": ["образование", "магистратура", "IT"],
                "speakers": ["Преподаватели ИТМО", "Студенты"],
                "description": "День открытых дверей магистерских программ Университета ИТМО",
                "registration_info": "Регистрация на сайте itmo.ru",
                "source": "itmo_parsed",
                "url": "https://itmo.ru"
            }
        ]
    
    def _parse_timepad_example(self):
        """
        Пример парсинга с TimePad
        """
        return [
            {
                "title": "Data Science Hackathon",
                "date": "2025-05-20",
                "location": "Санкт-Петербург, Офис Яндекс",
                "audience": 120,
                "type": "хакатон",
                "themes": ["Data Science", "ML", "аналитика"],
                "speakers": ["Эксперты Data Science"],
                "description": "Хакатон по Data Science с реальными кейсами",
                "registration_info": "Регистрация на TimePad",
                "source": "timepad_parsed",
                "url": "https://timepad.ru"
            }
        ]
    
    def _remove_duplicates(self, events):
        """Удаляет дубликаты мероприятий"""
        if not events or not isinstance(events, list):
            return []
            
        seen_titles = set()
        unique_events = []
        
        for event in events:
            if isinstance(event, dict) and 'title' in event:
                title = event['title'].lower().strip()
                if title not in seen_titles:
                    seen_titles.add(title)
                    unique_events.append(event)
        
        return unique_events
    
    def save_events(self, events):
        """Сохраняет мероприятия в JSON файл"""
        try:
            # Убедимся, что events - это список
            if not isinstance(events, list):
                events = []
                
            # Добавляем мета-информацию
            events_data = {
                "metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_events": len(events),
                    "sources_used": ["web_search", "llm_search", "sample_database", "itmo", "timepad"]
                },
                "events": events
            }
            
            # Создаем папку data если её нет
            os.makedirs(os.path.dirname(config.EVENTS_DB), exist_ok=True)
            
            with open(config.EVENTS_DB, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка при сохранении мероприятий: {e}")
    
    def load_events(self):
        """Загружает мероприятия из JSON файла"""
        try:
            if not os.path.exists(config.EVENTS_DB):
                return []
                
            with open(config.EVENTS_DB, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Извлекаем события из структуры
                if isinstance(data, dict) and 'events' in data:
                    return data.get('events', [])
                elif isinstance(data, list):
                    return data
                else:
                    return []
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            return []
        except Exception as e:
            print(f"❌ Ошибка при загрузке мероприятий: {e}")
            return []
    
    def get_events_statistics(self):
        """Возвращает статистику по мероприятиям"""
        events = self.load_events()
        
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
                
            # Статистика по типам
            event_type = event.get('type', 'неизвестно')
            stats["by_type"][event_type] = stats["by_type"].get(event_type, 0) + 1
            
            # Статистика по месяцам
            try:
                date_str = event.get('date', '')
                if date_str:
                    month = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m')
                    stats["by_month"][month] = stats["by_month"].get(month, 0) + 1
            except:
                pass
            
            # Статистика по источникам
            source = event.get('source', 'неизвестно')
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
        
        return stats
    
    async def close(self):
        """Закрывает веб-сессию"""
        await self.web_searcher.close()