import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re

# Импортируем config из корня
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import config
class EventSources:
    """Класс для управления источниками мероприятий с реальными ссылками"""
    
    # Реальные источники IT-мероприятий в Санкт-Петербурге
    SOURCE_URLS = {
        # IT-порталы и агрегаторы
        "habr_events": "https://habr.com/ru/hub/events/",
        "vc_events": "https://vc.ru/events",
        "timepad_it": "https://timepad.ru/events/categories/it/",
        "piterit": "https://piter.it/events/",
        
        # Университеты Санкт-Петербурга
        "itmo_events": "https://events.itmo.ru/",
        "spbu_events": "https://events.spbu.ru/",
        "spbstu_events": "https://www.spbstu.ru/events/",
        "unecon_events": "https://unecon.ru/events",
        
        # IT-компании и сообщества
        "yandex_events": "https://events.yandex.ru/",
        "jetbrains_events": "https://www.jetbrains.com/ru-ru/events/",
        "ods_events": "https://ods.ai/events",
        "datafest": "https://datafest.ru/",
        
        # Конференции и форумы
        "codefest": "https://codefest.ru/",
        "heilum": "https://heilum.ru/",
        "ritfest": "https://ritfest.ru/",
        "rootconf": "https://rootconf.ru/",
        
        # Государственные IT-мероприятия
        "it_dialog": "https://it-dialog.ru/",
        "digital_spb": "https://digital.spb.ru/events/",
        
        # Стартап события
        "startup_spb": "https://startupspb.com/events/",
        "piterstartup": "https://piterstartup.ru/events/"
    }
    
    @staticmethod
    def get_sample_events():
        """
        Расширенная база примеров мероприятий
        """
        try:
            # Создаем папку data если её нет
            os.makedirs(os.path.dirname(config.EVENTS_DB), exist_ok=True)
            
            with open(config.EVENTS_DB, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Проверяем структуру данных
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
        """Возвращает расширенный список мероприятий по умолчанию"""
        return [
            {
            "title": "Хакатон SpbTechRun 2024",
            "date": "2024-11-30",
            "end_date": "2024-12-01",
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
            "title": "Круглый стол 'Цифровая трансформация бизнеса'",
            "date": "2025-02-11",
            "location": "Санкт-Петербург, Деловой Петербург",
            "audience": 80,
            "type": "круглый стол",
            "themes": ["цифровая трансформация", "бизнес", "IT"],
            "speakers": ["ТОП-менеджеры", "IT-директора", "Эксперты рынка"],
            "description": "Обсуждение трендов цифровизации российского бизнеса",
            "registration_info": "По приглашениям для руководителей",
            "source": "partner_invitation",
            "url": "https://www.dp.ru"
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
            },
            {
            "title": "Стратегическая сессия по развитию IT-кластера СПб",
            "date": "2024-11-25",
            "location": "Санкт-Петербург, Смольный",
            "audience": 120,
            "type": "стратегическая сессия",
            "themes": ["экономика", "IT-развитие", "цифровизация", "инновации"],
            "speakers": ["вице-губернаторы Санкт-Петербурга", "руководители IT-компаний"],
            "description": "Стратегическая сессия по развитию IT-кластера Санкт-Петербурга",
            "registration_info": "Для участников правительства и IT-компаний",
            "source": "government_event",
            "url": "https://gov.spb.ru"
            },
            {
            "title": "AI Journey 2024",
            "date": "2024-09-01",
            "location": "Калининград",
            "audience": 500,
            "type": "конференция",
            "themes": ["искусственный интеллект", "образование", "нейросети"],
            "speakers": ["Эксперты Сбера", "Преподаватели вузов", "AI-специалисты"],
            "description": "Международная конференция по искусственному интеллекту",
            "registration_info": "Открытая регистрация на ai-journey.ru",
            "source": "educational_event",
            "url": "https://ai-journey.ru"
            },
            {
            "title": "ИТМО TOP AI Conference",
            "date": "2025-07-21",
            "location": "Санкт-Петербург, Университет ИТМО",
            "audience": 400,
            "type": "конференция",
            "themes": ["AI", "исследование", "образование", "инновации"],
            "speakers": ["Профессора ИТМО", "Исследователи AI", "Промышленные эксперты"],
            "description": "Ежегодная конференция по искусственному интеллекту от ведущего IT-вуза",
            "registration_info": "Регистрация на сайте itmo.ru",
            "source": "university_event",
            "url": "https://events.itmo.ru"
            },
            {
            "title": "День Науки с СПб ФИЦ РАН",
            "date": "2025-02-07",
            "location": "Санкт-Петербург, СПб ФИЦ РАН",
            "audience": 200,
            "type": "научная конференция",
            "themes": ["наука", "исследования", "IT", "инновации"],
            "speakers": ["Ученые РАН", "Исследователи", "Академики"],
            "description": "Научная конференция с участием ведущих исследователей РАН",
            "registration_info": "Для научных сотрудников и партнеров",
            "source": "science_event",
            "url": "https://spbrc.ru"
            },
            {
            "title": "Петербургский международный образовательный форум",
            "date": "2025-03-27",
            "location": "Санкт-Петербург, Академия талантов",
            "audience": 300,
            "type": "форум",
            "themes": ["образование", "IT-образование", "цифровизация"],
            "speakers": ["Эксперты образования", "IT-специалисты", "Педагоги"],
            "description": "Крупнейший образовательный форум Северо-Запада",
            "registration_info": "Регистрация на сайте academy-talant.ru",
            "source": "educational_event",
            "url": "https://academy-talant.ru"
            },
            {
            "title": "Startup Village 2025",
            "date": "2025-06-15",
            "location": "Санкт-Петербург, Сколково Парк",
            "audience": 1000,
            "type": "стартап-конференция",
            "themes": ["стартапы", "венчурные инвестиции", "IT", "инновации"],
            "speakers": ["Инвесторы", "Основатели стартапов", "Эксперты"],
            "description": "Крупнейшая стартап-конференция Северо-Запада",
            "registration_info": "Открытая регистрация на startupvillage.ru",
            "source": "startup_event",
            "url": "https://startupvillage.ru"
            },
            {
            "title": "CodeFest 2025",
            "date": "2025-04-12",
            "location": "Санкт-Петербург, Экспофорум",
            "audience": 1500,
            "type": "IT-конференция",
            "themes": ["программирование", "разработка", "DevOps", "Cloud"],
            "speakers": ["Lead Developer из Яндекс", "Architect из Сбера", "Google Developer Expert"],
            "description": "Одна из крупнейших IT-конференций для разработчиков",
            "registration_info": "Билеты на codefest.ru",
            "source": "it_conference",
            "url": "https://codefest.ru"
            },
            {
            "title": "Data Science Meetup от JetBrains",
            "date": "2025-05-20",
            "location": "Санкт-Петербург, Офис JetBrains",
            "audience": 150,
            "type": "митап",
            "themes": ["Data Science", "машинное обучение", "аналитика"],
            "speakers": ["Data Scientist из JetBrains", "Эксперты ML"],
            "description": "Регулярный митап по Data Science от ведущей IT-компании",
            "registration_info": "Регистрация на meetup.com",
            "source": "community_event",
            "url": "https://meetup.com"
            },
            {
            "title": "Кибербезопасность и AI",
            "date": "2025-08-10",
            "location": "Санкт-Петербург, СПбГУ",
            "audience": 180,
            "type": "семинар",
            "themes": ["кибербезопасность", "AI", "защита данных", "ML"],
            "speakers": ["Профессора СПбГУ", "Эксперты по безопасности"],
            "description": "Семинар по применению AI в кибербезопасности",
            "registration_info": "Для студентов и партнеров СПбГУ",
            "source": "university_event",
            "url": "https://spbu.ru"
            },
            {
            "title": "IT Диалог 2025",
            "date": "2025-11-05",
            "location": "Санкт-Петербург, Таврический дворец",
            "audience": 800,
            "type": "форум",
            "themes": ["IT-индустрия", "бизнес", "государство", "инновации"],
            "speakers": ["Министры", "IT-директора", "Эксперты"],
            "description": "Ежегодный форум диалога IT-сообщества и государства",
            "registration_info": "По приглашениям и регистрации",
            "source": "government_event",
            "url": "https://it-dialog.ru"
            },
            {
            "title": "Frontend Conf 2025",
            "date": "2025-09-18",
            "location": "Санкт-Петербург, Лофт Проект ЭТАЖИ",
            "audience": 400,
            "type": "конференция",
            "themes": ["frontend", "JavaScript", "React", "Vue", "Web"],
            "speakers": ["Lead Frontend Developer", "Google Developer Expert"],
            "description": "Крупнейшая конференция по фронтенд-разработке в СПб",
            "registration_info": "Билеты на frontendconf.ru",
            "source": "it_conference",
            "url": "https://frontendconf.ru"
            },
            {
            "title": "AI Research Day в СПбПУ",
            "date": "2025-10-15",
            "location": "Санкт-Петербург, СПбПУ",
            "audience": 120,
            "type": "научный семинар",
            "themes": ["AI исследования", "нейросети", "машинное обучение"],
            "speakers": ["Профессора СПбПУ", "Исследователи AI"],
            "description": "Научный семинар по последним исследованиям в области AI",
            "registration_info": "Для научного сообщества",
            "source": "university_event",
            "url": "https://spbstu.ru"
            }
        ]
            
    @staticmethod
    def parse_real_events():
        """
        Парсинг мероприятий с реальных источников
        (заглушки для демонстрации, в реальности будут парсить сайты)
        """
        parsed_events = []
        
        # Пример парсинга с ITMO events
        try:
            itmo_events = EventSources._parse_itmo_events()
            parsed_events.extend(itmo_events)
        except Exception as e:
            print(f"❌ Ошибка парсинга ITMO: {e}")
        
        # Пример парсинга с TimePad
        try:
            timepad_events = EventSources._parse_timepad_events()
            parsed_events.extend(timepad_events)
        except Exception as e:
            print(f"❌ Ошибка парсинга TimePad: {e}")
        
        return parsed_events
    
    @staticmethod
    def _parse_itmo_events():
        """
        Парсинг мероприятий Университета ИТМО
        """
        # В реальной реализации здесь будет requests + BeautifulSoup
        return [
            {
                "title": "AI Research Day в ИТМО",
                "date": "2025-03-15",
                "location": "Санкт-Петербург, Университет ИТМО",
                "audience": 150,
                "type": "научный семинар",
                "themes": ["AI", "исследования", "нейросети"],
                "speakers": ["Профессора ИТМО", "Исследователи AI"],
                "description": "Ежеквартальный научный семинар по исследованиям AI",
                "registration_info": "Регистрация на events.itmo.ru",
                "source": "itmo_events",
                "url": "https://events.itmo.ru/ai-research"
            }
        ]
    
    @staticmethod
    def _parse_timepad_events():
        """
        Парсинг IT-мероприятий с TimePad
        """
        return [
            {
                "title": "Python Meetup SPb",
                "date": "2025-04-05",
                "location": "Санкт-Петербург, Коворкинг Таврида",
                "audience": 100,
                "type": "митап",
                "themes": ["Python", "программирование", "разработка"],
                "speakers": ["Python Developer", "Tech Lead"],
                "description": "Регулярный митап Python-разработчиков Санкт-Петербурга",
                "registration_info": "Бесплатная регистрация на TimePad",
                "source": "timepad",
                "url": "https://timepad.ru/python-spb"
            }
        ]
    
    @staticmethod
    def get_parsing_sources():
        """Возвращает список источников для парсинга"""
        return [
            {
                "name": "Университет ИТМО",
                "url": "https://events.itmo.ru/",
                "type": "university",
                "active": True
            },
            {
                "name": "СПбГУ Мероприятия", 
                "url": "https://events.spbu.ru/",
                "type": "university",
                "active": True
            },
            {
                "name": "СПбПУ События",
                "url": "https://www.spbstu.ru/events/",
                "type": "university", 
                "active": True
            },
            {
                "name": "TimePad IT",
                "url": "https://timepad.ru/events/categories/it/",
                "type": "aggregator",
                "active": True
            },
            {
                "name": "Piter IT Events",
                "url": "https://piter.it/events/",
                "type": "community",
                "active": True
            },
            {
                "name": "Яндекс События",
                "url": "https://events.yandex.ru/",
                "type": "company",
                "active": True
            },
            {
                "name": "JetBrains Events",
                "url": "https://www.jetbrains.com/ru-ru/events/",
                "type": "company", 
                "active": True
            },
            {
                "name": "ODS Events",
                "url": "https://ods.ai/events",
                "type": "community",
                "active": True
            },
            {
                "name": "CodeFest",
                "url": "https://codefest.ru/",
                "type": "conference",
                "active": True
            },
            {
                "name": "IT Dialog",
                "url": "https://it-dialog.ru/",
                "type": "government",
                "active": True
            }
        ]