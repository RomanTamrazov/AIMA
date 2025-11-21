#!/usr/bin/env python3
"""
Главный файл AI-помощника по медиа - Анализ мероприятий
Центр исследований и разработки Сбера в Санкт-Петербурге
"""

import sys
import os
import asyncio
from datetime import datetime

# Добавляем корневую директорию проекта в путь Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.parsers.event_parser import EventParser
from src.analysis.criteria_filter import CriteriaFilter

async def main():
    """Основная функция приложения - мгновенная загрузка мероприятий"""
    print("🚀 Запуск AI-помощника по медиа...")
    print("Центр исследований и разработки Сбера в Санкт-Петербурге")
    print("=" * 60)
    
    # Инициализация компонентов
    parser = EventParser()
    filter = CriteriaFilter()
    
    try:
        # МГНОВЕННАЯ ЗАГРУЗКА МЕРОПРИЯТИЙ
        print("\n📥 Загружаем мероприятия...")
        events = await parser.parse_events()  # Мгновенная загрузка из sources.py
        
        # Показываем статистику
        stats = parser.get_events_statistics()
        print(f"\n📊 Статистика мероприятий:")
        print(f"   Всего мероприятий: {stats['total']}")
        
        if 'by_type' in stats:
            print(f"   По типам:")
            for event_type, count in stats['by_type'].items():
                print(f"     - {event_type}: {count}")
        
        # Фильтрация мероприятий
        print("\n🔍 Фильтруем мероприятия по критериям...")
        filtered_events = filter.filter_events(events)
        
        print(f"\n📊 Всего мероприятий: {len(events)}")
        print(f"✅ Подходящих мероприятий: {len(filtered_events)}")
        
        # Показываем топ рекомендованных мероприятий
        if filtered_events:
            print(f"\n🎯 Топ-{min(5, len(filtered_events))} рекомендованных мероприятий:")
            for i, event in enumerate(filtered_events[:5]):
                print(f"\n{i+1}. 🎪 {event['title']}")
                print(f"   📅 Дата: {event['date']}")
                print(f"   📍 Место: {event['location']}")
                print(f"   👥 Аудитория: {event.get('audience', 'N/A')}")
                print(f"   🎯 Приоритет: {event.get('priority_score', 'N/A')}/10")
                
                # Показываем тематики
                themes = event.get('themes', [])
                if themes:
                    print(f"   🏷️  Тематики: {', '.join(themes[:3])}")
        else:
            print("\n❌ Не найдено подходящих мероприятий")
        
        # Ближайшие мероприятия
        upcoming_events = parser.get_upcoming_events(days=30)
        if upcoming_events:
            print(f"\n📅 Ближайшие мероприятия (30 дней): {len(upcoming_events)}")
            for event in upcoming_events[:3]:
                print(f"   - {event['title']} ({event['date']})")
        
        print(f"\n🤖 Для запуска Telegram бота: python src/run_bot.py")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await parser.close()
        print("\n🔚 Работа завершена")

if __name__ == "__main__":
    asyncio.run(main())