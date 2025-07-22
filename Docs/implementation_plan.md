---
description: "Implementation Plan for Moodtape Telegram Bot"
alwaysApply: false
---

> У каждого пункта есть статус выполнения. Начинай работу с первого невыполненного TODO. После выполнения задачи присваивай ей статус DONE.

## Milestone 1 — Инициализация проекта и инфраструктура

- TODO: Создать репозиторий с названием `moodtape`
- TODO: Добавить `.gitignore` с исключениями для `.env`, `__pycache__`, `*.pyc`, `data/`
- TODO: Создать базовую структуру папок (`bot/`, `moodtape_core/`, `auth/`, `utils/`, `tests/`, `config/`, `data/`)
- TODO: Добавить `pyproject.toml` с зависимостями (`python-telegram-bot`, `openai`, `spotipy`, `requests`, `python-dotenv`, `sqlite3`, `black`, `flake8`)
- TODO: Настроить `python-dotenv` для загрузки `.env` переменных
- TODO: Добавить Dockerfile (на базе `python:3.12-slim`) с корректным порядком инструкций
- TODO: Создать `.dockerignore` с исключением `data/`, `.env`, `__pycache__`, `*.pyc`
- TODO: Подготовить `README.md` с описанием проекта, командой запуска и схемой архитектуры


## Milestone 2 — Логика Telegram-бота: запуск и выбор стриминга

- TODO: Реализовать `/start` с определением языка (`ru`, `en`, `es`)
- TODO: Реализовать выбор стримингового сервиса (Spotify или Apple Music)
- TODO: Сохранить выбор сервиса и языка в сессию пользователя (в памяти)
- TODO: Добавить мультиязычную поддержку с автоопределением по `language_code`


## Milestone 3 — Обработка пользовательского запроса и вызов GPT-4o

- TODO: Настроить модуль `gpt_parser.py` с вызовом GPT-4o (модель: `gpt-4o`, temp=0.5)
- TODO: Получить JSON с параметрами (valence, energy, acousticness, genre_hints и пр.)
- TODO: Обработать ошибки OpenAI и fallback-сообщения для Telegram
- TODO: Добавить логирование GPT-запросов для отладки


## Milestone 4 — Интеграция Spotify API

- TODO: Настроить OAuth-авторизацию через Spotipy
- TODO: Получить liked tracks или top tracks пользователя
- TODO: Сохранить токены в `data/tokens.sqlite`
- TODO: Подключить API для создания кастомного плейлиста и загрузки треков


## Milestone 5 — Интеграция Apple Music API

- TODO: Настроить генерацию dev-токена Apple Music через JWT
- TODO: Реализовать поиск и создание плейлистов через REST API
- TODO: Ограничить функциональность Apple Music до общего mood-based подбора (без лайков)


## Milestone 6 — Сборка плейлиста по предпочтениям и настроению

- TODO: Реализовать `build_mood_playlist()` в `playlist_builder.py`
- TODO: Смешать рекомендации GPT с треками пользователя (если доступны)
- TODO: Ограничить длину плейлиста (например, 20 треков)
- TODO: Сохранить историю запросов и ответов в `data/query_log.sqlite`


## Milestone 7 — Отправка результата пользователю

- TODO: Отправить пользователю ссылку на плейлист
- TODO: Добавить мультиязычный текст для ответа (по `user_lang`)
- TODO: Логировать отправленные плейлисты по user_id


## Milestone 8 — Обратная связь

- TODO: После отправки плейлиста предложить оценку: 👍 / 👎 / текст
- TODO: Сохранить обратную связь в `data/feedback.sqlite`
- TODO: Привязать фидбэк к ID запроса и вектору GPT-эмоции


## Milestone 9 — Учет истории запросов и фидбэков (базовый ML)

- TODO: Добавить простой алгоритм: «если пользователь регулярно ставит 👎 при valence < 0.3 — повышать valence»
- TODO: Использовать SQLite для хранения пользовательского профиля
- TODO: Учитывать последние 5 фидбэков при генерации новых параметров


## Milestone 10 — Подготовка к продакшену

- TODO: Настроить `.env` с ключами: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `SPOTIPY_CLIENT_ID`, `APPLE_PRIVATE_KEY` и пр.
- TODO: Проверить работу Docker-образа
- TODO: Задеплоить бот на Railway
- TODO: Проверить работу бота в Telegram Web & iOS/Android
- TODO: Провести smoke-тестирование

---

## ✅ Acceptance Checklist

- [ ] Бот работает в Telegram, доступен публично
- [ ] Поддержка Spotify и Apple Music — подтверждена вручную
- [ ] GPT-4o корректно интерпретирует описания
- [ ] Мультиязычность (RU, EN, ES) работает без ошибок
- [ ] Фидбэк сохраняется и влияет на подбор
- [ ] Все окружения задокументированы и изолированы
- [ ] Бот не падает при сетевых или API-ошибках

---

> **@Cursor**: После завершения задачи поменяй её статус на DONE и добавь краткий маркер «// done by Cursor» с описанием, что именно сделано.

