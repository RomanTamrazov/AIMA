#!/usr/bin/env python3
"""
Конфигурация AI-помощника по медиа
"""

import os
from datetime import datetime
import json

# config.py

# Критерии фильтрации мероприятий
CRITERIA = {
    # Приоритетные тематики (расширенный список)
    "priority_themes": [
        "AI", "искусственный интеллект", "машинное обучение", "нейросети",
        "Data Science", "аналитика данных", "ML", "big data",
        "веб-разработка", "frontend", "backend", "fullstack", "web",
        "мобильная разработка", "iOS", "Android", "mobile",
        "кибербезопасность", "безопасность", "cybersecurity", "infosec",
        "облачные технологии", "cloud", "DevOps", "CI/CD", "микросервисы",
        "блокчейн", "криптовалюты", "Web3", "NFT", "DeFi",
        "геймдев", "разработка игр", "game development",
        "цифровая трансформация", "digital", "инновации",
        "образование", "наука", "research", "образование", "EDU",
        "стартапы", "предпринимательство", "startup", "бизнес"
    ],
    
    # Разрешенные типы мероприятий (расширенный список)
    "event_types": [
        "хакатон", "конференция", "митап", "семинар", "воркшоп",
        "лекция", "форум", "круглый стол", "панельная дискуссия",
        "стратегическая сессия", "нетворкинг", "выставка",
        "демо-день", "питч-сессия", "мастер-класс", "образовательное мероприятие"
    ],
    
    # Минимальный размер аудитории
    "min_audience": 50,
    
    # Приоритетные локации
    "location_priority": [
        "Санкт-Петербург", "СПб", "Петербург", 
        "онлайн", "online", "гибридный", "hybrid"
    ],
    
    # Исключенные локации
    "excluded_locations": [
        "Москва", "МСК", "Новосибирск", "Екатеринбург"
    ]
}

# Веса для расчета приоритета
SCORING_WEIGHTS = {
    "audience_size": {
        "high": 3,    # 500+
        "medium": 2,  # 200-499
        "low": 1      # 100-199
    },
    "speaker_level": {
        "government": 3,
        "university": 2,
        "industry": 2,
        "community": 1
    },
    "themes": {
        "ai": 3,
        "digital_transformation": 2,
        "education": 2,
        "development": 2,
        "security": 2,
        "startup": 2
    },
    "event_type": {
        "strategic": 3,
        "conference": 2,
        "educational": 2,
        "hackathon": 2,
        "networking": 1
    }
}

def load_criteria_config():
    """Загружает конфигурацию критериев"""
    try:
        # Можно добавить загрузку из внешнего файла
        return {
            "criteria": CRITERIA,
            "scoring_weights": SCORING_WEIGHTS
        }
    except Exception as e:
        print(f"⚠️ Ошибка загрузки конфигурации: {e}")
        return None

# Настройки календаря (только .ics)
CALENDAR_CONFIG = {
    "timezone": "Europe/Moscow",
    "default_duration_hours": 3,
    "default_time": "10:00"
}

# Пути к файлам данных
DATA_DIR = "data"
EVENTS_DB = os.path.join(DATA_DIR, "events_database.json")
CRITERIA_CONFIG = os.path.join(DATA_DIR, "criteria_config.json")
PARTNERS_DB = os.path.join(DATA_DIR, "partner_invitations.csv")

# Настройки парсинга
PARSING_INTERVAL = 24  # часов
MAX_EVENTS_PER_SOURCE = 50

def get_current_date():
    return datetime.now().strftime("%Y-%m-%d")

BOT_CONFIG = {
    "token": "8456658338:AAElzl0CF5iyRiF-n_5HvFYsvBvV-IIiRAg", # Токен бота
    "admin_password": "admin123",  # Пароль для администраторов
    "manager_password": "manager123"  # Пароль для руководителей
}
