#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений бота
"""

import sys
import os
sys.path.insert(0, '/Users/iakovenkom81/Documents/Moodtape')

def test_imports():
    """Тестируем импорты"""
    print("🔄 Тестирование импортов...")
    
    try:
        from config.settings import validate_required_env_vars, TELEGRAM_BOT_TOKEN
        print("  ✅ Config импортирован")
        
        from utils.database import db_manager
        print("  ✅ Database импортирован")
        
        from bot.handlers.start import start_command
        print("  ✅ Start handler импортирован")
        
        from bot.middleware.rate_limiter import rate_limiter
        print("  ✅ Rate limiter импортирован")
        
        return True
    except Exception as e:
        print(f"  ❌ Ошибка импорта: {e}")
        return False

def test_environment():
    """Тестируем переменные окружения"""
    print("\n🔄 Тестирование токенов...")
    
    try:
        from config.settings import validate_required_env_vars, TELEGRAM_BOT_TOKEN, OPENAI_API_KEY
        
        print(f"  - TELEGRAM_BOT_TOKEN: {'✅ OK' if TELEGRAM_BOT_TOKEN and 'your_telegram_bot_token_here' not in TELEGRAM_BOT_TOKEN else '❌ НЕ НАСТРОЕН'}")
        print(f"  - OPENAI_API_KEY: {'✅ OK' if OPENAI_API_KEY and 'your_openai_api_key_here' not in OPENAI_API_KEY else '❌ НЕ НАСТРОЕН'}")
        
        validate_required_env_vars()
        print("  ✅ Все токены настроены правильно")
        return True
        
    except Exception as e:
        print(f"  ❌ Проблема с токенами: {e}")
        return False

def test_data_directory():
    """Тестируем папку данных"""
    print("\n🔄 Тестирование папки данных...")
    
    try:
        from config.settings import DATA_DIR
        
        if DATA_DIR.exists():
            print(f"  ✅ Папка data существует: {DATA_DIR}")
        else:
            DATA_DIR.mkdir(exist_ok=True)
            print(f"  ✅ Папка data создана: {DATA_DIR}")
        
        # Тестируем права на запись
        test_file = DATA_DIR / ".test_write"
        test_file.touch()
        test_file.unlink()
        print("  ✅ Права на запись в папку data")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Проблема с папкой data: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🔧 Тестирование исправлений Moodtape бота\n")
    
    tests = [
        ("Импорты", test_imports),
        ("Токены", test_environment),
        ("Папка данных", test_data_directory)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Ошибка в тесте '{test_name}': {e}")
            results[test_name] = False
    
    print("\n📊 Результаты тестирования:")
    print("=" * 40)
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{test_name:.<25} {status}")
        if not result:
            all_passed = False
    
    print("=" * 40)
    
    if all_passed:
        print("🎉 Все тесты пройдены! Запускайте бота:")
        print("PYTHONPATH=/Users/iakovenkom81/Documents/Moodtape python3 bot/main.py")
    else:
        print("⚠️ Найдены проблемы. Проверьте ошибки выше.")
    
    return all_passed

if __name__ == "__main__":
    main() 