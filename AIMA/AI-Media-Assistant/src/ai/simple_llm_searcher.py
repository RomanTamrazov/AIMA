#!/usr/bin/env python3
"""
Упрощенный LLM-поисковик мероприятий через бесплатные API
"""

import aiohttp
import json
import re
import random
from datetime import datetime, timedelta
import asyncio
from src.parsers.web_searcher import RealWebSearcher

class SimpleLLMSearcher:
    def __init__(self):
        self.api_endpoints = [
            "https://api.deepinfra.com/v1/openai/chat/completions",
            "https://openrouter.ai/api/v1/chat/completions",
        ]
        self.headers = {
            "Content-Type": "application/json", 
            "User-Agent": "Sber-AI-Assistant/1.0"
        }
        self.web_searcher = RealWebSearcher()  # Добавляем реальный поиск
    
    async def search_events_with_llm(self, query, max_events=10, use_web_search=True):
        """
        Ищет мероприятия через LLM и реальный веб-поиск
        """
        all_events = []
        
        # 1. Сначала реальный веб-поиск
        if use_web_search:
            print("🌐 Запускаем реальный поиск в интернете...")
            web_events = await self.web_searcher.search_real_events(query, max_events//2)
            all_events.extend(web_events)
            print(f"✅ Веб-поиск нашел {len(web_events)} мероприятий")
        
        # 2. Затем LLM-поиск для дополнения
        if len(all_events) < max_events:
            print("🧠 Дополняем результаты через LLM...")
            llm_events = await self._search_with_llm_models(query, max_events - len(all_events))
            all_events.extend(llm_events)
        
        # 3. Если ничего не найдено, используем тестовые данные
        if not all_events:
            print("⚠️  Ничего не найдено, используем тестовые данные...")
            all_events = self._generate_test_events(query, max_events)
        
        return all_events[:max_events]
    
    async def _search_with_llm_models(self, query, max_events):
        """Поиск через LLM модели"""
        prompt = self._create_search_prompt(query, max_events)
        
        models = [
            "meta-llama/Meta-Llama-3-70B-Instruct",
            "microsoft/WizardLM-2-8x22B", 
            "google/gemma-2-27b-it",
        ]
        
        for model in models:
            try:
                print(f"🔍 Ищем через {model}...")
                events = await self._try_deepinfra(model, prompt)
                if events:
                    print(f"✅ LLM нашел {len(events)} мероприятий")
                    return events
            except Exception as e:
                print(f"❌ Ошибка в {model}: {e}")
                continue
        
        return []
    
    async def _try_deepinfra(self, model, prompt):
        """Пробует получить данные через DeepInfra"""
        try:
            url = "https://api.deepinfra.com/v1/openai/chat/completions"
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.7
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    json=payload, 
                    headers=self.headers,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        return self._parse_llm_response(content)
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except asyncio.TimeoutError:
            print(f"⏰ Таймаут для {model}")
            return []
        except Exception as e:
            print(f"❌ Ошибка DeepInfra {model}: {e}")
            return []
    
    def _create_search_prompt(self, query, max_events):
        """Создает промпт для поиска мероприятий"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        
        return f"""
Ты AI-ассистент для поиска IT-мероприятий в Санкт-Петербурге. Найди РЕАЛЬНЫЕ мероприятия по запросу: "{query}"

ВАЖНЫЕ ТРЕБОВАНИЯ:
- Только реальные, предстоящие мероприятия в Санкт-Петербурге (2024-2025)
- Только IT, технологии, программирование, AI, Data Science тематики
- Даты должны быть между {current_date} и {future_date}
- Максимум {max_events} мероприятий
- Только публичные мероприятия

ФОРМАТ ОТВЕТА (строго JSON):
{{
    "events": [
        {{
            "title": "Название мероприятия",
            "date": "2024-12-15",
            "location": "Место проведения, Санкт-Петербург",
            "audience": 150,
            "type": "конференция",
            "themes": ["AI", "машинное обучение"],
            "speakers": ["Иван Петров", "Мария Сидорова"],
            "description": "Краткое описание мероприятия",
            "registration_info": "Бесплатная регистрация на сайте",
            "url": "https://example.com",
            "source": "llm_search"
        }}
    ]
}}

ПРИМЕРЫ РЕАЛЬНЫХ МЕРОПРИЯТИЙ В СПб:
- SPB Python Meetup
- AI Conference SPb 
- Data Science Hackathon
- Frontend Conf SPb
- DevOps Days Petersburg
- CyberSecurity Forum
- Mobile Development Summit
- Blockchain & Crypto Meetup

Верни ТОЛЬКО JSON без дополнительного текста.
"""
    
    def _parse_llm_response(self, response):
        """Парсит ответ LLM в структурированные данные"""
        try:
            # Очищаем ответ от markdown и лишнего текста
            cleaned_response = re.sub(r'```json\s*|\s*```', '', response).strip()
            
            # Ищем JSON
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if not json_match:
                print(f"❌ JSON не найден: {response[:200]}...")
                return []
            
            json_str = json_match.group()
            data = json.loads(json_str)
            
            events = data.get('events', [])
            validated_events = []
            
            for event in events:
                validated_event = self._validate_event(event)
                if validated_event:
                    validated_events.append(validated_event)
            
            return validated_events
            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return []
        except Exception as e:
            print(f"❌ Ошибка парсинга: {e}")
            return []
    
    def _validate_event(self, event):
        """Валидирует и очищает данные мероприятия"""
        try:
            # Обязательные поля
            if not event.get('title') or not event.get('date'):
                return None
            
            # Валидация даты
            try:
                event_date = datetime.strptime(event['date'], '%Y-%m-%d')
                if event_date < datetime.now():
                    return None
            except ValueError:
                return None
            
            # Стандартизируем location
            if 'location' not in event:
                event['location'] = 'Санкт-Петербург'
            elif 'санкт-петербург' not in event['location'].lower():
                event['location'] += ', Санкт-Петербург'
            
            # Обеспечиваем списки
            if isinstance(event.get('themes'), str):
                event['themes'] = [event['themes']]
            elif not event.get('themes'):
                event['themes'] = ['IT']
            
            if isinstance(event.get('speakers'), str):
                event['speakers'] = [event['speakers']]
            elif not event.get('speakers'):
                event['speakers'] = ['Эксперты индустрии']
            
            # Добавляем источник
            event['source'] = 'llm_search'
            
            return event
            
        except Exception as e:
            print(f"❌ Ошибка валидации: {e}")
            return None
    
    def _generate_test_events(self, query, max_events):
        """Генерирует тестовые мероприятия если API недоступны"""
        print("🧪 Генерируем тестовые мероприятия...")
        
        base_events = [
            {
                "title": "AI & Machine Learning Meetup SPb",
                "date": "2024-12-10",
                "location": "Санкт-Петербург, Офис Яндекс",
                "audience": 120,
                "type": "митап",
                "themes": ["AI", "машинное обучение"],
                "speakers": ["Алексей AI-эксперт", "Мария Data Scientist"],
                "description": "Ежемесячная встреча AI-сообщества Санкт-Петербурга",
                "registration_info": "Бесплатная регистрация на сайте",
                "url": "https://example.com/ai-meetup",
                "source": "test_data"
            },
            {
                "title": "Data Science Hackathon 2024",
                "date": "2024-11-25",
                "location": "Санкт-Петербург, Университет ИТМО",
                "audience": 200,
                "type": "хакатон", 
                "themes": ["Data Science", "аналитика данных"],
                "speakers": ["Профессор Иванов", "Доктор Петрова"],
                "description": "24-часовой хакатон по Data Science с реальными кейсами",
                "registration_info": "Регистрация для команд до 20 ноября",
                "url": "https://example.com/ds-hackathon",
                "source": "test_data"
            },
            {
                "title": "Frontend Conf SPb 2024",
                "date": "2024-12-05",
                "location": "Санкт-Петербург, Лофт Проект ЭТАЖИ",
                "audience": 300,
                "type": "конференция",
                "themes": ["frontend", "JavaScript", "React"],
                "speakers": ["Senior Frontend Developer", "Tech Lead"],
                "description": "Крупнейшая конференция по фронтенд-разработке в СПб",
                "registration_info": "Билеты от 2000 руб",
                "url": "https://example.com/frontend-conf",
                "source": "test_data"
            },
            {
                "title": "DevOps Days Petersburg",
                "date": "2025-01-20", 
                "location": "Санкт-Петербург, Экспофорум",
                "audience": 500,
                "type": "конференция",
                "themes": ["DevOps", "облачные технологии", "CI/CD"],
                "speakers": ["DevOps инженеры", "Архитекторы"],
                "description": "Конференция по DevOps практикам и инструментам",
                "registration_info": "Ранняя регистрация до 15 января",
                "url": "https://example.com/devops-days",
                "source": "test_data"
            },
            {
                "title": "Blockchain & Crypto Meetup",
                "date": "2024-12-15",
                "location": "Санкт-Петербург, Коворкинг Таврида",
                "audience": 80,
                "type": "митап",
                "themes": ["блокчейн", "криптовалюты", "Web3"],
                "speakers": ["Blockchain Developer", "Crypto Analyst"],
                "description": "Встреча блокчейн-сообщества Санкт-Петербурга",
                "registration_info": "Бесплатно по предварительной регистрации",
                "url": "https://example.com/blockchain-meetup",
                "source": "test_data"
            }
        ]
        
        # Фильтруем по запросу
        query_lower = query.lower()
        filtered_events = []
        
        for event in base_events:
            if (query_lower in event['title'].lower() or 
                any(query_lower in theme.lower() for theme in event['themes']) or
                query_lower in event['type'].lower()):
                filtered_events.append(event)
        
        return filtered_events[:max_events] if filtered_events else base_events[:max_events]
    
    async def search_by_themes(self, themes, max_events=10):
        """Ищет мероприятия по темам"""
        query = f"IT мероприятия в Санкт-Петербурге по темам: {', '.join(themes)}"
        return await self.search_events_with_llm(query, max_events)
    
    async def search_upcoming_events(self, days=30, max_events=8):
        """Ищет ближайшие мероприятия"""
        future_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        query = f"Ближайшие IT мероприятия в Санкт-Петербурге до {future_date}"
        return await self.search_events_with_llm(query, max_events)