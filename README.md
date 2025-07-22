# 🎵 Moodtape

Telegram-бот, который создает персональные музыкальные плейлисты на основе эмоционального описания пользователя.

## 📝 Описание

Moodtape использует GPT-4o для анализа текстового описания настроения и создает музыкальные плейлисты в Spotify или Apple Music, учитывая как эмоциональный контекст, так и музыкальные предпочтения пользователя.

### Основные возможности

- 🤖 **Умный анализ настроения**: GPT-4o интерпретирует любое описание (например, "осень, одиночество и тёплый чай")
- 🎧 **Интеграция со стримингами**: 
  - **Spotify**: Персональные плейлисты с OAuth авторизацией
  - **Apple Music**: Mood-based поиск через Developer API
- 🌍 **Мультиязычность**: Русский, английский, испанский
- 🧠 **Продвинутая персонализация**: 
  - Анализ фидбэков и автоматическая корректировка параметров
  - Изучение предпочтений по жанрам, настроению и музыкальным характеристикам
  - Адаптивные рекомендации на основе истории оценок
- 📊 **Расширенная система обратной связи**:
  - Оценки 👍👎 для быстрого фидбэка
  - Текстовые комментарии для детального анализа
  - Команды `/preferences` и `/stats` для просмотра изученных предпочтений
- 🎯 **Интеллектуальные рекомендации**: 
  - **Spotify**: Комбинирует ваши лайки с персонализированными параметрами настроения
  - **Apple Music**: Адаптирует поиск на основе изученных предпочтений

## 🚀 Быстрый старт

### Локальный запуск

1. **Клонируйте репозиторий**:
   ```bash
   git clone https://github.com/moodtape/moodtape.git
   cd moodtape
   ```

2. **Установите зависимости**:
   ```bash
   pip install -e .
   ```

3. **Настройте переменные окружения**:
   ```bash
   cp .env.example .env
   # Отредактируйте .env файл с вашими ключами
   ```

4. **Запустите бота**:
   ```bash
   python -m bot.main
   ```

### Запуск через Docker

```bash
# Сборка образа
docker build -t moodtape .

# Запуск контейнера
docker run -d --name moodtape-bot --env-file .env moodtape
```

### Деплой на Railway

```bash
# Установите Railway CLI и авторизуйтесь
railway login
railway link

# Добавьте переменные окружения
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set OPENAI_API_KEY=your_key
# ... остальные переменные

# Деплой
railway up
```

## 🏗️ Архитектура

```
moodtape/
├── bot/                    # Telegram bot логика
│   ├── handlers/          # Обработчики команд и сообщений
│   ├── middleware/        # Middleware для логирования, auth
│   └── main.py           # Точка входа бота
├── moodtape_core/         # Основная бизнес-логика
│   ├── gpt_parser.py     # Парсинг настроения через GPT-4o
│   ├── playlist_builder.py # Создание плейлистов
│   └── personalization.py # Алгоритмы персонализации
├── auth/                  # Авторизация в стримингах
│   ├── spotify_auth.py   # OAuth для Spotify
│   └── apple_auth.py     # JWT для Apple Music
├── utils/                 # Утилиты
│   ├── database.py       # Работа с SQLite
│   ├── i18n.py          # Интернационализация
│   └── logger.py        # Логирование
├── config/               # Конфигурация
│   └── settings.py      # Настройки приложения
├── data/                # Данные (исключено из git)
│   ├── tokens.sqlite    # Токены пользователей
│   ├── feedback.sqlite  # База фидбэков
│   └── query_log.sqlite # История запросов
└── tests/               # Тесты
    ├── unit/
    └── integration/
```

### Поток данных

1. **Пользователь** отправляет описание настроения в Telegram
2. **Bot Handler** обрабатывает сообщение и определяет язык
3. **GPT Parser** анализирует текст и возвращает музыкальные параметры
4. **Playlist Builder** создает плейлист на основе параметров и предпочтений
5. **Streaming API** (Spotify/Apple Music) создает плейлист
6. **Результат** отправляется пользователю с возможностью фидбэка

## ⚙️ Переменные окружения

Создайте `.env` файл с следующими переменными:

```env
# Telegram Bot (обязательно)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# OpenAI GPT-4o (обязательно)
OPENAI_API_KEY=your_openai_api_key

# Spotify API (опционально, для персональных плейлистов)
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback

# Apple Music API (опционально, только mood-based поиск)
APPLE_TEAM_ID=your_apple_team_id
APPLE_KEY_ID=your_apple_key_id
APPLE_PRIVATE_KEY_PATH=path/to/your/AuthKey.p8

# Database
DATABASE_URL=sqlite:///data/moodtape.db

# Logging
LOG_LEVEL=INFO
```

## 🛠️ Разработка

### Установка для разработки

```bash
# Установка с dev зависимостями
pip install -e ".[dev]"

# Настройка pre-commit хуков
pre-commit install
```

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=moodtape_core --cov-report=html
```

### Форматирование кода

```bash
# Автоформатирование
black .

# Проверка стиля
flake8
```

## 📋 Roadmap

- [x] **M1**: Инициализация проекта и Docker ✅
- [x] **M2**: Базовая Telegram логика ✅
- [x] **M3**: Интеграция GPT-4o ✅
- [x] **M4**: Поддержка Spotify ✅
- [x] **M5**: Поддержка Apple Music ✅
- [x] **M6**: Расширенная система фидбэков и персонализация ✅
- [x] **M7**: Production готовность и финальное тестирование ✅

🎉 **MVP готов к продакшену!** 🎉

## 🚀 Production готовность

### ✅ Реализованные возможности

- **🤖 AI-powered анализ настроения** с GPT-4o
- **🎵 Dual music streaming** (Spotify + Apple Music)
- **🧠 Интеллектуальная персонализация** на основе ML
- **📊 Расширенная система фидбэков** (👍👎 + комментарии)
- **🌍 Мультиязычность** (RU/EN/ES)
- **🛡️ Production middleware** (error handling, rate limiting)
- **📈 Аналитика пользователей** (/preferences, /stats)
- **🐳 Готовые Docker конфигурации**
- **📚 Полная документация по развертыванию**

### 🔧 Запуск тестов

```bash
# Проверка production готовности
python tests/test_production.py

# Запуск бота локально
python -m bot.main

# Запуск в Docker
docker-compose up -d
```

### 📖 Документация

- **[Руководство по развертыванию](Docs/deployment.md)** - полная инструкция по развертыванию
- **[Описание проекта](Docs/prd.md)** - Product Requirements Document
- **[План реализации](Docs/implementation_plan.md)** - детальный план разработки

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте feature ветку (`git checkout -b feature/amazing-feature`)
3. Закоммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Запушьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 📞 Контакты

- **Telegram**: [@moodtape_bot](https://t.me/moodtape_bot)
- **Email**: team@moodtape.com
- **Issues**: [GitHub Issues](https://github.com/moodtape/moodtape/issues) 