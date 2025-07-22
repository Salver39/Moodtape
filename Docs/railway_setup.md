# 🚂 Настройка деплоймента на Railway

## 1. 📝 Обязательные переменные окружения

Перед запуском бота необходимо настроить следующие переменные в Railway:

### Критически важные (без них бот не запустится):
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

### Для Spotify интеграции (рекомендуется для создания плейлистов):
```
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=https://your-railway-app.railway.app/auth/spotify/callback
```

### Для Apple Music интеграции (опционально, требует платной подписки Apple Developer):
```
APPLE_TEAM_ID=your_apple_team_id
APPLE_KEY_ID=your_apple_key_id
APPLE_PRIVATE_KEY_PATH=/app/apple_auth_key.p8
```

> ⚠️ **Примечание**: Apple Music интеграция требует платную подписку Apple Developer Program ($99/год). Вы можете пропустить эти переменные и использовать только Spotify.

## 2. 🚀 Пошаговая настройка в Railway

### Шаг 1: Подключите репозиторий
1. Зайдите на [railway.app](https://railway.app)
2. Нажмите "New Project"
3. Выберите "Deploy from GitHub repo"
4. Выберите репозиторий `Salver39/Moodtape`

### Шаг 2: Настройте переменные окружения
1. В панели проекта перейдите во вкладку "Variables"
2. Добавьте каждую переменную:
   - Нажмите "New Variable"
   - Введите имя переменной (например, `TELEGRAM_BOT_TOKEN`)
   - Введите значение
   - Нажмите "Add"

### Шаг 3: Получите необходимые токены

#### Telegram Bot Token:
1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте полученный токен

#### OpenAI API Key:
1. Зайдите на [platform.openai.com](https://platform.openai.com)
2. Перейдите в API Keys
3. Создайте новый ключ
4. Скопируйте ключ (начинается с `sk-`)

#### Spotify API ключи (для создания плейлистов):
1. Зайдите на [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Войдите в ваш Spotify аккаунт
3. Нажмите **"Create app"**
4. Заполните форму:
   - **App name**: `Moodtape Bot`
   - **App description**: `AI music recommendation bot`
   - **Website**: `https://your-railway-app.railway.app`
   - **Redirect URI**: `https://your-railway-app.railway.app/auth/spotify/callback`
   - Поставьте галочки на согласиях
5. После создания скопируйте:
   - **Client ID** - это ваш `SPOTIPY_CLIENT_ID`
   - **Client Secret** - нажмите "Show client secret", это ваш `SPOTIPY_CLIENT_SECRET`

## 3. 🔧 Настройка Production режима

Добавьте эти переменные для production:
```
DEBUG=false
WEBHOOK_URL=https://your-railway-app.railway.app/webhook
```

## 4. 🏗️ Автоматический деплой

После настройки переменных:
1. Railway автоматически перезапустит приложение
2. Проверьте логи в разделе "Deployments"
3. Убедитесь что нет ошибок конфигурации

## 5. ✅ Проверка работы

В логах должны появиться сообщения:
```
✅ All required environment variables are configured
🚀 Bot started successfully
```

## 6. 🔗 Настройка Webhook (для production)

Если используете webhook режим:
1. Получите URL вашего Railway приложения
2. Установите переменную `WEBHOOK_URL=https://your-app.railway.app/webhook`
3. Перезапустите деплой

## 🆘 Устранение проблем

### Ошибка: "TELEGRAM_BOT_TOKEN environment variable is required"
- Убедитесь что переменная `TELEGRAM_BOT_TOKEN` добавлена в Railway
- Проверьте что значение не содержит пробелов
- Перезапустите деплой

### Ошибка: "OPENAI_API_KEY environment variable is required"
- Добавьте переменную `OPENAI_API_KEY` в Railway
- Убедитесь что API ключ действителен
- Проверьте баланс на OpenAI аккаунте

### Бот не отвечает:
- Проверьте логи в Railway
- Убедитесь что токен бота правильный
- Проверьте что бот не заблокирован

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи в Railway Dashboard
2. Убедитесь что все переменные окружения настроены
3. Проверьте статус всех внешних API

---

**💡 Рекомендуемый порядок настройки**:

1. **Минимальная конфигурация** (бот работает, но без плейлистов):
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`

2. **Полная конфигурация** (с созданием плейлистов):
   - Добавьте Spotify переменные:
   - `SPOTIPY_CLIENT_ID`
   - `SPOTIPY_CLIENT_SECRET`  
   - `SPOTIPY_REDIRECT_URI`

3. **Расширенная конфигурация** (опционально, в будущем):
   - Apple Music переменные (требует платную подписку)

**🎯 Начните с шагов 1-2, Apple Music можно добавить позже!** 