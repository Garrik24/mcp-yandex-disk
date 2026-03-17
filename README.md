# MCP Yandex Disk Server

MCP-сервер для доступа к Яндекс.Диску из Claude.ai и других MCP-клиентов.

## Возможности

- 📁 Листинг папок
- 🔍 Поиск файлов по типу (документы, изображения и т.д.)
- 📥 Получение ссылок на скачивание
- 🔗 Работа с публичными ссылками (https://disk.yandex.ru/d/...)
- 📄 Чтение текстовых файлов

## Деплой на Railway

1. Форкни репозиторий
2. Создай проект на Railway, подключи GitHub
3. Установи переменные окружения:
   - `YANDEX_OAUTH_TOKEN` — OAuth-токен
   - `PORT` — 8080
4. Деплой

## Получение OAuth-токена

1. Зарегистрируй приложение: https://oauth.yandex.ru/client/new/api
2. Права: `cloud_api:disk.read`, `cloud_api:disk.write`
3. Получи токен: `https://oauth.yandex.ru/authorize?response_type=token&client_id=YOUR_CLIENT_ID`

## Подключение к Claude.ai

URL: `https://<your-railway-url>/mcp/sse`
