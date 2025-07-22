# 🚀 Moodtape Bot - Руководство по развертыванию

Подробное руководство по развертыванию Moodtape бота в production окружении.

## 📋 Содержание

- [Требования](#требования)
- [Подготовка к развертыванию](#подготовка-к-развертыванию)
- [Развертывание на Railway](#развертывание-на-railway)
- [Развертывание на Heroku](#развертывание-на-heroku)
- [Развертывание на VPS](#развертывание-на-vps)
- [Развертывание с Docker](#развертывание-с-docker)
- [Настройка переменных окружения](#настройка-переменных-окружения)
- [Мониторинг и логирование](#мониторинг-и-логирование)
- [Troubleshooting](#troubleshooting)

## 🔧 Требования

### Системные требования
- **Python**: 3.10+
- **Память**: Минимум 512MB RAM (рекомендуется 1GB+)
- **Диск**: 1GB свободного места
- **Network**: Стабильное интернет соединение

### API ключи (обязательные)
- **Telegram Bot Token**: Получить у [@BotFather](https://t.me/botfather)
- **OpenAI API Key**: Получить на [platform.openai.com](https://platform.openai.com)

### API ключи (опциональные)
- **Spotify**: Client ID и Client Secret
- **Apple Music**: Team ID, Key ID, Private Key (.p8 файл)

## 🎯 Подготовка к развертыванию

### 1. Создание Telegram бота

```bash
# 1. Найдите @BotFather в Telegram
# 2. Отправьте /newbot
# 3. Следуйте инструкциям для создания бота
# 4. Сохраните полученный токен

# Пример токена:
# 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 2. Настройка Spotify API (опционально)

```bash
# 1. Перейдите на https://developer.spotify.com/dashboard
# 2. Создайте новое приложение
# 3. Добавьте Redirect URI: https://yourdomain.com/auth/spotify/callback
# 4. Сохраните Client ID и Client Secret
```

### 3. Настройка Apple Music API (опционально)

```bash
# 1. Зарегистрируйтесь в Apple Developer Program
# 2. Создайте MusicKit Identifier
# 3. Создайте private key (.p8 файл)
# 4. Сохраните Team ID, Key ID и приватный ключ
```

## 🚂 Развертывание на Railway

Railway - рекомендуемая платформа для развертывания.

### Пошаговая инструкция

1. **Подготовка репозитория**
```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/moodtape.git
cd moodtape

# Создайте railway.json (опционально)
echo '{
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}' > railway.json
```

2. **Развертывание через Railway CLI**
```bash
# Установите Railway CLI
npm install -g @railway/cli

# Войдите в аккаунт
railway login

# Создайте новый проект
railway init

# Добавьте переменные окружения
railway variables set TELEGRAM_BOT_TOKEN=your_token_here
railway variables set OPENAI_API_KEY=your_openai_key_here
railway variables set ENVIRONMENT=production

# Деплой
railway up
```

3. **Настройка Webhook**
```bash
# Получите URL вашего приложения
railway domain

# Установите webhook (замените YOUR_DOMAIN на полученный URL)
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://YOUR_DOMAIN.railway.app/webhook"}'
```

## 📦 Развертывание на Heroku

### Подготовка

```bash
# Установите Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Войдите в аккаунт
heroku login

# Создайте приложение
heroku create your-moodtape-bot

# Добавьте buildpack для Python
heroku buildpacks:set heroku/python
```

### Развертывание

```bash
# Добавьте переменные окружения
heroku config:set TELEGRAM_BOT_TOKEN=your_token_here
heroku config:set OPENAI_API_KEY=your_openai_key_here
heroku config:set ENVIRONMENT=production
heroku config:set WEBHOOK_URL=https://your-moodtape-bot.herokuapp.com

# Деплой
git push heroku main

# Установите webhook
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://your-moodtape-bot.herokuapp.com/webhook"}'
```

## 🖥️ Развертывание на VPS

### Подготовка сервера

```bash
# Обновите систему (Ubuntu/Debian)
sudo apt update && sudo apt upgrade -y

# Установите зависимости
sudo apt install -y python3.10 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Создайте пользователя для бота
sudo useradd -m -s /bin/bash moodtape
sudo su - moodtape
```

### Установка приложения

```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/moodtape.git
cd moodtape

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -e .

# Создайте .env файл
cp env.example .env
# Отредактируйте .env с вашими API ключами

# Создайте директории
mkdir -p data logs
```

### Настройка Nginx

```bash
# Создайте конфигурацию Nginx
sudo nano /etc/nginx/sites-available/moodtape

# Содержимое файла:
server {
    listen 80;
    server_name your-domain.com;

    location /webhook {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}

# Активируйте конфигурацию
sudo ln -s /etc/nginx/sites-available/moodtape /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Получите SSL сертификат
sudo certbot --nginx -d your-domain.com
```

### Создание systemd службы

```bash
# Создайте файл службы
sudo nano /etc/systemd/system/moodtape.service

# Содержимое файла:
[Unit]
Description=Moodtape Telegram Bot
After=network.target

[Service]
Type=simple
User=moodtape
WorkingDirectory=/home/moodtape/moodtape
Environment=PATH=/home/moodtape/moodtape/venv/bin
ExecStart=/home/moodtape/moodtape/venv/bin/python -m bot.main
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target

# Запустите службу
sudo systemctl daemon-reload
sudo systemctl enable moodtape
sudo systemctl start moodtape

# Проверьте статус
sudo systemctl status moodtape
```

## 🐳 Развертывание с Docker

### Docker Compose (рекомендуется)

```yaml
# docker-compose.yml
version: '3.8'

services:
  moodtape:
    build: .
    container_name: moodtape-bot
    restart: unless-stopped
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ENVIRONMENT=production
      - WEBHOOK_URL=${WEBHOOK_URL}
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: moodtape-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - moodtape
```

### Команды для запуска

```bash
# Создайте .env файл
cp env.example .env
# Заполните переменные окружения

# Запустите контейнеры
docker-compose up -d

# Проверьте логи
docker-compose logs -f moodtape

# Остановите контейнеры
docker-compose down
```

## 🔧 Настройка переменных окружения

### Обязательные переменные

```bash
# Основные API ключи
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
OPENAI_API_KEY=sk-...

# Окружение
ENVIRONMENT=production
WEBHOOK_URL=https://your-domain.com
```

### Опциональные переменные

```bash
# Spotify API (опционально)
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret

# Apple Music API (опционально)
APPLE_TEAM_ID=your_team_id
APPLE_KEY_ID=your_key_id
APPLE_PRIVATE_KEY_PATH=/path/to/AuthKey.p8

# Настройки производительности
MAX_CONCURRENT_REQUESTS=100
REQUEST_TIMEOUT_SECONDS=30
MEMORY_LIMIT_MB=512

# Логирование
LOG_LEVEL=INFO
ENABLE_JSON_LOGGING=true

# Безопасность
WEBHOOK_SECRET_TOKEN=your_secret_token
ADMIN_USER_IDS=123456789,987654321

# Премиум функции
ENABLE_PREMIUM_FEATURES=false
PREMIUM_USER_IDS=123456789
```

### Полный список переменных

Смотрите файл `env.example` для полного списка доступных переменных окружения.

## 📊 Мониторинг и логирование

### Health Checks

```bash
# Проверка работоспособности
curl http://your-domain.com/health

# Ответ должен быть:
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "services": {
    "database": "ok",
    "openai": "ok",
    "spotify": "ok"
  }
}
```

### Логирование

```bash
# Просмотр логов (systemd)
sudo journalctl -u moodtape -f

# Просмотр логов (Docker)
docker-compose logs -f moodtape

# Ротация логов
sudo logrotate -f /etc/logrotate.d/moodtape
```

### Мониторинг ресурсов

```bash
# Использование памяти
free -h

# Использование диска
df -h

# Нагрузка на процессор
htop

# Статистика по боту (если настроен Prometheus)
curl http://your-domain.com/metrics
```

## 🛠️ Troubleshooting

### Частые проблемы

#### Бот не отвечает

```bash
# Проверьте статус webhook
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"

# Проверьте логи
sudo journalctl -u moodtape -n 50

# Проверьте доступность
curl -I http://your-domain.com/health
```

#### Ошибки API

```bash
# OpenAI API лимиты
# Проверьте квоты на https://platform.openai.com/usage

# Spotify API лимиты
# Проверьте в Spotify Developer Dashboard

# Telegram API лимиты
# Обычно 30 сообщений в секунду
```

#### Проблемы с базой данных

```bash
# Проверьте размер базы данных
ls -lh data/

# Создайте бэкап
cp data/moodtape.db data/moodtape_backup_$(date +%Y%m%d).db

# Проверьте целостность
sqlite3 data/moodtape.db "PRAGMA integrity_check;"
```

### Полезные команды

```bash
# Перезапуск бота
sudo systemctl restart moodtape

# Обновление кода
cd /home/moodtape/moodtape
git pull origin main
sudo systemctl restart moodtape

# Очистка логов
sudo journalctl --vacuum-time=7d

# Проверка дискового пространства
du -sh data/
```

## 🔒 Безопасность

### Рекомендации

1. **Используйте HTTPS** для webhook'ов
2. **Установите WEBHOOK_SECRET_TOKEN** для проверки webhook'ов
3. **Ограничьте доступ** к серверу через firewall
4. **Регулярно обновляйте** зависимости
5. **Настройте бэкапы** базы данных
6. **Мониторьте логи** на подозрительную активность

### Firewall настройки

```bash
# Базовые правила UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 📈 Масштабирование

### Горизонтальное масштабирование

Для высоких нагрузок рассмотрите:

1. **Load Balancer** (Nginx, HAProxy)
2. **Redis** для распределенного rate limiting
3. **PostgreSQL** вместо SQLite
4. **Kubernetes** для оркестрации контейнеров

### Вертикальное масштабирование

1. Увеличьте RAM и CPU
2. Настройте `MAX_CONCURRENT_REQUESTS`
3. Оптимизируйте базу данных
4. Используйте SSD диски

## 📞 Поддержка

При проблемах с развертыванием:

1. Проверьте [Issues](https://github.com/your-username/moodtape/issues)
2. Создайте новый issue с подробным описанием
3. Приложите логи и конфигурацию (без API ключей!)

---

**Успешного развертывания! 🚀** 