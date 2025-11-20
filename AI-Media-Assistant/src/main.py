#!/usr/bin/env python3
"""
Главный файл AI-помощника по медиа - Анализ мероприятий
Центр исследований и разработки Сбера в Санкт-Петербурге
"""

import sys
import os
import asyncio

# Добавляем корневую директорию проекта в путь Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.parsers.event_parser import EventParser
from src.analysis.criteria_filter import CriteriaFilter

async def main():
    """Основная функция приложения - анализ с расширенным поиском"""
    print("🚀 Запуск AI-помощника по медиа...")
    print("Центр исследований и разработки Сбера в Санкт-Петербурге")
    print("=" * 60)
    
    # Инициализация компонентов
    parser = EventParser()
    filter = CriteriaFilter()
    
    try:
        # РАСШИРЕННЫЙ ПАРСИНГ МЕРОПРИЯТИЙ
        print("\n📥 Загружаем мероприятия...")
        events = await parser.parse_events(
            use_llm_search=True, 
            use_real_parsing=True,  # ⬅️ ВКЛЮЧАЕМ РЕАЛЬНЫЙ ПАРСИНГ!
            use_web_search=True     # ⬅️ ВКЛЮЧАЕМ ВЕБ-ПОИСК!
        )
        
        # Показываем статистику
        stats = parser.get_events_statistics()
        print(f"\n📊 Статистика мероприятий:")
        print(f"   Всего мероприятий: {stats['total']}")
        
        if 'by_type' in stats:
            print(f"   По типам: {stats['by_type']}")
        if 'by_source' in stats:
            print(f"   По источникам: {stats['by_source']}")
        
        # Фильтрация мероприятий
        print("\n🔍 Фильтруем мероприятия по критериям...")
        filtered_events = filter.filter_events(events)
        
        print(f"\n📊 Всего мероприятий до фильтрации: {len(events)}")
        print(f"✅ Отфильтровано {len(filtered_events)} подходящих мероприятий")
        
        if len(events) > 0:
            rejected_count = len(events) - len(filtered_events)
            print(f"❌ Отклонено {rejected_count} мероприятий")
        
        # Показываем топ-3 рекомендованных мероприятия
        if filtered_events:
            print("\n🎯 Топ-3 рекомендованных мероприятия:")
            for i, event in enumerate(filtered_events[:3]):
                print(f"{i+1}. {event['title']} (Приоритет: {event.get('priority_score', 'N/A')})")
                print(f"   📅 {event['date']} | 👥 {event.get('audience', 'N/A')} | 🎪 {event.get('type', 'N/A')}")
                if event.get('source'):
                    print(f"   📍 Источник: {event['source']}")
                print()
        
        print(f"\n🤖 Для запуска Telegram бота выполните: python src/run_bot.py")
        
    except Exception as e:
        print(f"❌ Ошибка в работе AI-помощника: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # ВАЖНО: Закрываем ресурсы
        await parser.close()
        print("\n🔚 Работа завершена")

if __name__ == "__main__":
    asyncio.run(main())