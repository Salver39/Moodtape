## Moodtape — Tech Stack Document

| Layer              | Library/Service                  | Version         | Purpose                                                                 | Docs URL                                                   |
|-------------------|----------------------------------|------------------|------------------------------------------------------------------------|-------------------------------------------------------------|
| **Runtime**       | Python                           | 3.10+            | Язык и среда исполнения приложения                                     | https://www.python.org/doc/                                  |
| **Bot SDK**       | python-telegram-bot              | 20.3             | SDK для создания Telegram-бота с поддержкой asyncio                   | https://docs.python-telegram-bot.org/en/stable/             |
| **OpenAI SDK**    | openai                           | 1.x              | Вызовы к GPT-4o для анализа настроения                                | https://platform.openai.com/docs                             |
| **Spotify SDK**   | spotipy                          | 2.23.0           | Доступ к Spotify API: треки, лайки, создание плейлистов              | https://spotipy.readthedocs.io/                              |
| **Apple Music**   | custom requests + dev token      | N/A              | Запросы к Apple Music API через токен разработчика                    | https://developer.apple.com/documentation/applemusicapi     |
| **Database**      | SQLite (через `sqlite3`)         | built-in         | Хранение сессий, истории запросов и фидбэка                          | https://docs.python.org/3/library/sqlite3.html               |
| **Deployment**    | Railway                          | latest           | PaaS для развёртывания бота и фоновых задач                          | https://docs.railway.app/                                    |
| **Env Manager**   | python-dotenv                    | 1.0.1            | Загрузка ключей API и переменных окружения из `.env` файлов           | https://saurabh-kumar.com/python-dotenv/                     |
| **Formatter**     | black                            | 24.3.0           | Форматирование кода по строгим правилам                              | https://black.readthedocs.io/en/stable/                      |
| **Linter**        | flake8                           | 6.1.0            | Проверка стиля кода и потенциальных ошибок                          | https://flake8.pycqa.org/en/latest/                          |

---

### ➕ Дополнительно добавлено:

#### Env Manager — `python-dotenv`
*Обоснование:* Moodtape использует переменные окружения (`OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, и т.д.). `python-dotenv` облегчает локальную разработку и деплой.

#### Apple Music — custom requests
*Обоснование:* Официальной Python-библиотеки нет. Поэтому используется ручная интеграция с REST API через `requests`.

#### SQLite
*Обоснование:* Для хранения истории запросов, фидбэка и токенов достаточно встроенной БД. Можно заменить на PostgreSQL при масштабировании.

