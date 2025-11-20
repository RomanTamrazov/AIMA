#!/usr/bin/env python3
"""
Запуск Telegram бота
"""

import sys
import os
import asyncio

# Добавляем корневую директорию проекта в путь Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

def run_bot():
    """Запуск Telegram бота"""
    print("🤖 Запуск Telegram бота AI-помощника...")
    print("Центр исследований и разработки Сбера в Санкт-Петербурге")
    print("=" * 60)
    
    try:
        from chatbot.telegram_bot import TelegramBot
        import config
        
        # Проверяем токен
        if config.BOT_CONFIG["token"] == "YOUR_TELEGRAM_BOT_TOKEN":
            print("❌ Telegram токен не настроен!")
            print("   Откройте config.py и укажите REAL_TELEGRAM_BOT_TOKEN")
            print("   Или установите переменную окружения: TELEGRAM_BOT_TOKEN")
            return
        
        print("✅ Токен найден, запускаем бота...")
        print("   Используйте /start для начала работы")
        print("   Для остановки нажмите Ctrl+C")
        print("=" * 60)
        
        bot = TelegramBot()
        
        # Запускаем бота с обработкой исключений
        try:
            bot.run()
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен пользователем")
        except Exception as e:
            print(f"❌ Ошибка в работе бота: {e}")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("📁 Проверьте структуру файлов и зависимости")
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    run_bot()