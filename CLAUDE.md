# MCP Yandex Disk Server

## Что это
MCP-сервер для доступа к Яндекс.Диску через Claude.ai. Позволяет просматривать файлы, скачивать, искать, получать публичные ресурсы по ссылке.

## Стек
- Python 3.11+
- FastMCP (mcp[cli])
- httpx для HTTP-запросов к Yandex Disk REST API
- Деплой: Railway (SSE transport)

## Переменные окружения
- `YANDEX_OAUTH_TOKEN` — OAuth-токен Яндекс.Диска (обязательно)
- `PORT` — порт сервера (по умолчанию 8080)

## Yandex Disk REST API
- Базовый URL: `https://cloud-api.yandex.net/v1/disk`
- Авторизация: заголовок `Authorization: OAuth <token>`
- Документация: https://yandex.com/dev/disk/api/concepts/about.html

### Ключевые эндпоинты:
- `GET /v1/disk/resources?path=<path>` — метаинформация о файле/папке
- `GET /v1/disk/resources?path=<path>&limit=100` — листинг папки
- `GET /v1/disk/resources/download?path=<path>` — получить ссылку на скачивание
- `GET /v1/disk/resources/files?limit=20&media_type=document` — последние файлы
- `GET /v1/disk/public/resources?public_key=<url>` — публичный ресурс по ссылке
- `GET /v1/disk/public/resources/download?public_key=<url>` — скачать публичный ресурс

## Архитектура
Один файл `server.py` с FastMCP:
- `yadisk_list_folder` — листинг папки
- `yadisk_get_file_info` — метаинформация о файле
- `yadisk_download_link` — получить прямую ссылку на скачивание
- `yadisk_search_files` — поиск файлов (последние загруженные, по типу)
- `yadisk_public_resource` — получить инфо о публичном ресурсе по ссылке
- `yadisk_public_download_link` — получить ссылку на скачивание публичного ресурса
- `yadisk_read_text_file` — прочитать текстовый файл и вернуть содержимое

## Деплой на Railway
1. Создать репозиторий на GitHub: `Garrik24/mcp-yandex-disk`
2. Подключить к Railway
3. Установить переменные: `YANDEX_OAUTH_TOKEN`, `PORT=8080`
4. Railway автоматически задетектит Python и запустит через Procfile
5. URL сервера будет вида: `https://mcp-yandex-disk-production.up.railway.app/sse`

## Подключение к Claude.ai
В настройках Claude.ai → Integrations → добавить MCP-сервер:
- URL: `https://mcp-yandex-disk-production.up.railway.app/sse`
- Название: `Yandex Disk`

## Важно
- Если Railway (Амстердам) не может достучаться до Yandex API — нужно деплоить на российский VPS
- Токен имеет срок жизни ~1 год, потом нужно обновить
- Файлы из amoCRM автоматически синхронизируются на Яндекс.Диск — можно искать по имени
