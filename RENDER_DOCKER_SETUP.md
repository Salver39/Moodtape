# 🐳 Render Docker Deployment Guide

## Проблема
Render не может правильно управлять версиями Python через `runtime.txt` или `.python-version`, постоянно используя Python 3.13.4 вместо требуемой Python 3.11.x.

## Решение: Docker Deployment

### 📋 Шаги для переключения на Docker в Render:

1. **Зайдите в Render Dashboard**
2. **Найдите ваш сервис Moodtape**
3. **Перейдите в Settings → Build & Deploy**
4. **Измените настройки:**

   **ДО (Native Python):**
   ```
   Environment: Python 3
   Build Command: pip install -e .
   Start Command: python -m bot.main
   ```

   **ПОСЛЕ (Docker):**
   ```
   Environment: Docker
   Build Command: (оставить пустым)
   Start Command: (оставить пустым)
   ```

5. **Нажмите "Save Changes"**
6. **Нажмите "Manual Deploy"** для принудительного редеплоя

### 🔧 Что изменилось в коде:

- **`Dockerfile`**: Обновлен для использования `python:3.11.9-slim`
- **`pyproject.toml`**: Убраны строгие ограничения версии Python
- **Удалены**: `runtime.txt`, `.python-version` (не нужны для Docker)

### ✅ Ожидаемые логи после переключения:

```
==> Building with Docker...
==> Step 1/10 : FROM python:3.11.9-slim
==> Successfully built [image-id]
==> Successfully tagged [image-tag]
==> Running container...
Warning: Apple Music credentials not configured, Apple Music will be disabled
2025-07-22 XX:XX:XX,XXX - config.settings - INFO - 🎵 Available music services: Spotify
2025-07-22 XX:XX:XX,XXX - __main__ - INFO - ✅ All required environment variables are configured
2025-07-22 XX:XX:XX,XXX - __main__ - INFO - 🚀 Bot started successfully in polling mode
```

### 🚀 Преимущества Docker approach:

- ✅ **Полный контроль** над версией Python
- ✅ **Стабильная среда** выполнения  
- ✅ **Нет проблем** с совместимостью
- ✅ **Воспроизводимые** деплойменты

### 📞 Если возникнут проблемы:

1. Проверьте что выбран **Environment: Docker** в настройках
2. Убедитесь что **Build Command и Start Command пустые**
3. Попробуйте **Manual Deploy** после изменения настроек 