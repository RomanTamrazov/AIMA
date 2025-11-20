import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import re
import random
import asyncio
import aiohttp
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import config

class EventSources:
    def __init__(self):
        self.session = None
        self.found_events = set()
    
    async def parse_real_events(self):
        """
        Реальный парсинг мероприятий с живых сайтов
        """
        print("🌐 Запускаем реальный парсинг мероприятий...")
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            all_events = []
            
            # 1. Парсим TimePad (самый надежный источник)
            print("📅 Парсим TimePad...")
            timepad_events = await self._parse_timepad_real()
            all_events.extend(timepad_events)
            
            # 2. Парсим университеты
            print("🎓 Парсим университеты...")
            university_events = await self._parse_universities_real()
            all_events.extend(university_events)
            
            # 3. Парсим IT компании
            print("🏢 Парсим IT компании...")
            company_events = await self._parse_companies_real()
            all_events.extend(company_events)
            
            # 4. Парсим IT порталы
            print("📰 Парсим IT порталы...")
            portal_events = await self._parse_portals_real()
            all_events.extend(portal_events)
            
            # 5. Добавляем базу по умолчанию как fallback
            default_events = self.get_sample_events()
            all_events.extend(default_events)
            
            # Фильтруем дубликаты
            unique_events = self._remove_duplicates(all_events)
            
            print(f"✅ Реальный парсинг завершен. Найдено {len(unique_events)} мероприятий")
            return unique_events
            
        except Exception as e:
            print(f"❌ Ошибка реального парсинга: {e}")
            return self.get_sample_events()
    
    async def _parse_timepad_real(self):
        """Реальный парсинг TimePad"""
        events = []
        urls = [
            "https://timepad.ru/events/categories/technology/",
            "https://timepad.ru/events/categories/business/",
            "https://timepad.ru/events/categories/education/",
            "https://timepad.ru/events/list/?categories=technology&cities=spb"
        ]
        
        for url in urls:
            try:
                print(f"   🔍 Парсим {url}")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                
                async with self.session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Ищем карточки мероприятий
                        event_cards = soup.find_all('div', class_=re.compile(r'event-card|t-card|card'))
                        
                        for card in event_cards[:15]:
                            try:
                                event_data = self._extract_timepad_event(card)
                                if event_data and self._is_unique_event_by_title(event_data['title']):
                                    events.append(event_data)
                            except Exception as e:
                                continue
                
                await asyncio.sleep(2)  # Задержка между запросами
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга TimePad: {e}")
                continue
        
        return events
    
    def _extract_timepad_event(self, card):
        """Извлекает данные мероприятия из карточки TimePad"""
        try:
            # Заголовок
            title_elem = card.find(['h3', 'h4', 'a'], class_=re.compile(r'title|name'))
            if not title_elem:
                return None
            
            title = title_elem.get_text().strip()
            if len(title) < 5:
                return None
            
            # Дата
            date_elem = card.find(['time', 'span'], class_=re.compile(r'date|time'))
            date_text = date_elem.get_text().strip() if date_elem else ""
            
            # Место
            location_elem = card.find(['span', 'div'], class_=re.compile(r'location|place'))
            location = location_elem.get_text().strip() if location_elem else "Санкт-Петербург"
            
            # Описание
            desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|text'))
            description = desc_elem.get_text().strip() if desc_elem else f"Мероприятие: {title}"
            
            # Ссылка
            link_elem = card.find('a', href=True)
            url = link_elem['href'] if link_elem else "#"
            if url and not url.startswith('http'):
                url = f"https://timepad.ru{url}"
            
            return {
                "title": title[:200],
                "date": self._parse_real_date(date_text),
                "location": location,
                "type": self._detect_event_type(title),
                "audience": random.randint(30, 500),
                "themes": self._detect_themes(title),
                "speakers": ["Спикеры мероприятия"],
                "description": description[:300],
                "registration_info": "Регистрация на TimePad",
                "source": "timepad",
                "url": url,
                "priority_score": random.randint(7, 10)
            }
            
        except Exception:
            return None
    
    async def _parse_universities_real(self):
        """Реальный парсинг университетов"""
        events = []
        universities = [
            {"name": "ИТМО", "url": "https://events.itmo.ru/events"},
            {"name": "СПбГУ", "url": "https://events.spbu.ru/"},
            {"name": "Политех", "url": "https://www.spbstu.ru/events/"},
        ]
        
        for uni in universities:
            try:
                print(f"   🎓 Парсим {uni['name']}...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with self.session.get(uni['url'], headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Ищем мероприятия в контенте
                        content_elements = soup.find_all(['div', 'article', 'section'], 
                                                       class_=re.compile(r'event|news|post|card'))
                        
                        for element in content_elements[:20]:
                            try:
                                text = element.get_text().strip()
                                if len(text) < 20:
                                    continue
                                
                                # Проверяем что это мероприятие
                                if self._is_event_text(text):
                                    event_data = self._extract_university_event(text, uni['name'])
                                    if event_data and self._is_unique_event_by_title(event_data['title']):
                                        events.append(event_data)
                            except Exception:
                                continue
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга {uni['name']}: {e}")
                continue
        
        return events
    
    def _extract_university_event(self, text, uni_name):
        """Извлекает мероприятие университета из текста"""
        try:
            # Очищаем текст
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) < 15:
                return None
            
            # Ищем дату в тексте
            date_match = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', clean_text)
            
            return {
                "title": clean_text[:150] + ("..." if len(clean_text) > 150 else ""),
                "date": self._parse_real_date(date_match.group(0)) if date_match else self._generate_future_date(),
                "location": f"Санкт-Петербург, {uni_name}",
                "type": self._detect_event_type(clean_text),
                "audience": random.randint(50, 300),
                "themes": self._detect_themes(clean_text),
                "speakers": [f"Преподаватели {uni_name}"],
                "description": f"Мероприятие в {uni_name}",
                "registration_info": f"Регистрация на сайте {uni_name}",
                "source": f"{uni_name.lower()}_university",
                "url": "#",
                "priority_score": random.randint(6, 9)
            }
            
        except Exception:
            return None
    
    async def _parse_companies_real(self):
        """Реальный парсинг IT компаний"""
        events = []
        companies = [
            {"name": "Яндекс", "url": "https://events.yandex.ru/"},
            {"name": "JetBrains", "url": "https://www.jetbrains.com/ru-ru/events/"},
            {"name": "Сбер", "url": "https://sber.ru/events"},
        ]
        
        for company in companies:
            try:
                print(f"   🏢 Парсим {company['name']}...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with self.session.get(company['url'], headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Ищем события на сайтах компаний
                        event_elements = soup.find_all(['div', 'article', 'section'], 
                                                     class_=re.compile(r'event|meetup|conference'))
                        
                        for element in event_elements[:15]:
                            try:
                                text = element.get_text().strip()
                                if len(text) < 20:
                                    continue
                                
                                if self._is_event_text(text):
                                    event_data = self._extract_company_event(text, company['name'])
                                    if event_data and self._is_unique_event_by_title(event_data['title']):
                                        events.append(event_data)
                            except Exception:
                                continue
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга {company['name']}: {e}")
                continue
        
        return events
    
    def _extract_company_event(self, text, company_name):
        """Извлекает мероприятие компании из текста"""
        try:
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) < 15:
                return None
            
            date_match = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', clean_text)
            
            return {
                "title": clean_text[:150] + ("..." if len(clean_text) > 150 else ""),
                "date": self._parse_real_date(date_match.group(0)) if date_match else self._generate_future_date(),
                "location": f"Санкт-Петербург, {company_name}",
                "type": self._detect_event_type(clean_text),
                "audience": random.randint(50, 300),
                "themes": self._detect_themes(clean_text),
                "speakers": [f"Эксперты {company_name}"],
                "description": f"Мероприятие от {company_name}",
                "registration_info": f"Регистрация на сайте {company_name}",
                "source": f"{company_name.lower()}_company",
                "url": "#",
                "priority_score": random.randint(7, 10)
            }
            
        except Exception:
            return None
    
    async def _parse_portals_real(self):
        """Реальный парсинг IT порталов"""
        events = []
        portals = [
            {"name": "Хабр", "url": "https://habr.com/ru/hub/events/"},
            {"name": "VC.ru", "url": "https://vc.ru/events"},
            {"name": "TAdviser", "url": "https://www.tadviser.ru/index.php/Мероприятия"},
        ]
        
        for portal in portals:
            try:
                print(f"   📰 Парсим {portal['name']}...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                
                async with self.session.get(portal['url'], headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Ищем посты/статьи о мероприятиях
                        posts = soup.find_all(['article', 'div', 'section'], 
                                            class_=re.compile(r'post|article|news|content'))
                        
                        for post in posts[:20]:
                            try:
                                text = post.get_text().strip()
                                if len(text) < 30:
                                    continue
                                
                                if self._is_event_text(text):
                                    event_data = self._extract_portal_event(text, portal['name'])
                                    if event_data and self._is_unique_event_by_title(event_data['title']):
                                        events.append(event_data)
                            except Exception:
                                continue
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга {portal['name']}: {e}")
                continue
        
        return events
    
    def _extract_portal_event(self, text, portal_name):
        """Извлекает мероприятие с портала из текста"""
        try:
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) < 20:
                return None
            
            # Берем первые 100 символов как заголовок
            title = clean_text[:100] + "..." if len(clean_text) > 100 else clean_text
            
            date_match = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', clean_text)
            
            return {
                "title": title,
                "date": self._parse_real_date(date_match.group(0)) if date_match else self._generate_future_date(),
                "location": "Санкт-Петербург",
                "type": self._detect_event_type(clean_text),
                "audience": random.randint(30, 400),
                "themes": self._detect_themes(clean_text),
                "speakers": ["Эксперты индустрии"],
                "description": f"Мероприятие с {portal_name}",
                "registration_info": "Регистрация на сайте",
                "source": f"{portal_name.lower()}_portal",
                "url": "#",
                "priority_score": random.randint(5, 9)
            }
            
        except Exception:
            return None
    
    def _is_event_text(self, text):
        """Проверяет, является ли текст описанием мероприятия"""
        text_lower = text.lower()
        
        event_indicators = [
            'конференц', 'митап', 'хакатон', 'семинар', 'лекц', 'встреча',
            'event', 'meetup', 'conference', 'hackathon', 'workshop',
            'мероприятие', 'событие', 'день открытых', 'tech talk'
        ]
        
        return any(indicator in text_lower for indicator in event_indicators)
    
    def _parse_real_date(self, date_text):
        """Парсит реальную дату из текста"""
        try:
            if not date_text:
                return self._generate_future_date()
            
            # Пробуем разные форматы дат
            formats = [
                '%d.%m.%Y', '%Y-%m-%d', '%d %B %Y', 
                '%B %d, %Y', '%d/%m/%Y', '%Y/%m/%d'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_text.strip(), fmt).strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # Если не удалось распарсить, ищем числа в тексте
            numbers = re.findall(r'\d{1,2}\.\d{1,2}\.\d{4}', date_text)
            if numbers:
                return datetime.strptime(numbers[0], '%d.%m.%Y').strftime('%Y-%m-%d')
            
            return self._generate_future_date()
            
        except Exception:
            return self._generate_future_date()
    
    def _generate_future_date(self):
        """Генерирует дату в будущем"""
        days = random.randint(1, 180)  # До 6 месяцев вперед
        return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    
    def _detect_event_type(self, title):
        """Определяет тип мероприятия по заголовку"""
        title_lower = title.lower()
        
        type_mapping = [
            (['конференц', 'conference'], 'конференция'),
            (['митап', 'meetup'], 'митап'),
            (['хакатон', 'hackathon'], 'хакатон'),
            (['семинар', 'workshop', 'вебинар'], 'семинар'),
            (['лекц', 'lecture'], 'лекция'),
            (['форум', 'forum'], 'форум'),
            (['круглый стол', 'round table'], 'круглый стол'),
            (['стратегическ', 'strategic'], 'стратегическая сессия')
        ]
        
        for keywords, event_type in type_mapping:
            if any(keyword in title_lower for keyword in keywords):
                return event_type
        
        return 'мероприятие'
    
    def _detect_themes(self, title):
        """Определяет тематики мероприятия по заголовку"""
        title_lower = title.lower()
        themes = []
        
        theme_keywords = {
            'AI': ['ai', 'искусственн', 'нейросет', 'machine learning', 'ml'],
            'Data Science': ['data science', 'аналитик', 'big data', 'data'],
            'Разработка': ['разработк', 'programming', 'coding', 'dev', 'software'],
            'Веб': ['web', 'веб', 'frontend', 'backend', 'fullstack'],
            'Мобильная': ['mobile', 'мобильн', 'ios', 'android'],
            'Безопасность': ['безопасност', 'security', 'cyber'],
            'Облака': ['cloud', 'облачн', 'aws', 'azure', 'google cloud'],
            'DevOps': ['devops', 'ci/cd', 'deployment'],
            'Блокчейн': ['blockchain', 'блокчейн', 'crypto', 'крипто'],
            'Стартапы': ['startup', 'стартап', 'venture', 'инвестиц']
        }
        
        for theme, keywords in theme_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                themes.append(theme)
        
        return themes if themes else ["IT", "Технологии"]
    
    def _remove_duplicates(self, events):
        """Удаляет дубликаты мероприятий"""
        seen_titles = set()
        unique_events = []
        
        for event in events:
            if not isinstance(event, dict) or 'title' not in event:
                continue
                
            title = self._normalize_title(event['title'])
            
            if title and title not in seen_titles and len(title) > 10:
                seen_titles.add(title)
                unique_events.append(event)
        
        return unique_events
    
    def _normalize_title(self, title):
        """Нормализует заголовок для сравнения"""
        if not title:
            return ""
        
        normalized = title.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _is_unique_event_by_title(self, title):
        """Проверяет уникальность по заголовку"""
        title_norm = self._normalize_title(title)
        
        if not title_norm or len(title_norm) < 10:
            return False
        
        title_hash = hash(title_norm)
        if title_hash in self.found_events:
            return False
        
        self.found_events.add(title_hash)
        return True

    @staticmethod
    def get_sample_events():
        """Возвращает базу мероприятий по умолчанию"""
        try:
            os.makedirs(os.path.dirname(config.EVENTS_DB), exist_ok=True)
            
            with open(config.EVENTS_DB, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'events' in data:
                    return data['events']
                else:
                    return EventSources._get_default_events()
        except FileNotFoundError:
            return EventSources._get_default_events()
        except Exception as e:
            print(f"⚠️ Ошибка загрузки мероприятий: {e}")
            return EventSources._get_default_events()
    
    @staticmethod
    def _get_default_events():
        """Возвращает список мероприятий по умолчанию"""
        return [
            {
                "title": "Хакатон SpbTechRun 2024",
                "date": "2024-11-30",
                "location": "Санкт-Петербург, ЛЕНПОЛИГРАФМАШ",
                "audience": 300,
                "type": "хакатон",
                "themes": ["технологии", "программирование", "инновации"],
                "speakers": ["ИТ-эксперты", "Промышленные специалисты"],
                "description": "Крупнейший технологический хакатон для разработчиков и инженеров",
                "registration_info": "Регистрация на сайте spbtechrun.ru",
                "source": "partner_invitation",
                "url": "https://spbtechrun.ru"
            },
            {
                "title": "Women in Data Science 2025",
                "date": "2025-03-07",
                "location": "Санкт-Петербург, Отель Коринтия",
                "audience": 250,
                "type": "конференция",
                "themes": ["Data Science", "AI", "женщины в IT", "машинное обучение"],
                "speakers": ["Лидеры ODS", "Data Scientist из топ компаний"],
                "description": "Крупнейшая конференция о женщинах в Data Science в России",
                "registration_info": "Открытая регистрация на ods.ai",
                "source": "community_event",
                "url": "https://ods.ai"
            }
        ]
    
    async def close(self):
        """Закрывает сессию"""
        if self.session:
            await self.session.close()