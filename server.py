"""
MCP-сервер для Яндекс.Диска.
Позволяет AI-ассистентам просматривать, искать и скачивать файлы.
"""

import os
import json
import logging
from typing import Optional, List

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# --- Конфигурация ---

YANDEX_OAUTH_TOKEN = os.environ.get("YANDEX_OAUTH_TOKEN", "")
YANDEX_API_BASE = "https://cloud-api.yandex.net/v1/disk"
PORT = int(os.environ.get("PORT", "8080"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yadisk_mcp")

# --- MCP-сервер ---

mcp = FastMCP("yadisk_mcp")

# --- HTTP-клиент ---

def _get_headers() -> dict:
    """Заголовки авторизации для Yandex Disk API."""
    return {
        "Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}",
        "Accept": "application/json",
    }


async def _api_get(path: str, params: Optional[dict] = None) -> dict:
    """GET-запрос к Yandex Disk API с обработкой ошибок."""
    url = f"{YANDEX_API_BASE}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_get_headers(), params=params or {})
        if resp.status_code == 404:
            return {"error": "Ресурс не найден. Проверьте путь или ссылку."}
        if resp.status_code == 401:
            return {"error": "Ошибка авторизации. Проверьте OAuth-токен."}
        if resp.status_code == 403:
            return {"error": "Доступ запрещён. Нет прав на этот ресурс."}
        if resp.status_code >= 400:
            return {"error": f"Ошибка API: {resp.status_code} — {resp.text[:300]}"}
        return resp.json()


async def _api_get_raw(url: str) -> bytes:
    """Скачать файл по прямой ссылке и вернуть содержимое."""
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _format_resource(item: dict) -> dict:
    """Краткий формат ресурса для вывода."""
    return {
        "name": item.get("name", ""),
        "type": item.get("type", ""),
        "path": item.get("path", ""),
        "size": item.get("size"),
        "created": item.get("created", ""),
        "modified": item.get("modified", ""),
        "mime_type": item.get("mime_type", ""),
        "md5": item.get("md5", ""),
        "preview": item.get("preview", ""),
    }


# --- Входные модели ---

class ListFolderInput(BaseModel):
    """Параметры для листинга папки."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        default="disk:/",
        description="Путь к папке на Яндекс.Диске (например 'disk:/' или 'disk:/Загрузки')"
    )
    limit: int = Field(
        default=50,
        description="Максимум файлов в ответе",
        ge=1,
        le=200,
    )
    offset: int = Field(
        default=0,
        description="Смещение для пагинации",
        ge=0,
    )


class FileInfoInput(BaseModel):
    """Параметры для получения информации о файле."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        ...,
        description="Полный путь к файлу на Яндекс.Диске (например 'disk:/Документы/договор.pdf')",
        min_length=1,
    )


class DownloadLinkInput(BaseModel):
    """Параметры для получения ссылки на скачивание."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        ...,
        description="Полный путь к файлу на Яндекс.Диске",
        min_length=1,
    )


class SearchFilesInput(BaseModel):
    """Параметры для поиска файлов."""
    model_config = ConfigDict(str_strip_whitespace=True)

    media_type: Optional[str] = Field(
        default=None,
        description="Тип медиа: document, spreadsheet, image, audio, video, compressed и др. Можно несколько через запятую."
    )
    limit: int = Field(
        default=20,
        description="Максимум файлов",
        ge=1,
        le=100,
    )
    offset: int = Field(
        default=0,
        description="Смещение для пагинации",
        ge=0,
    )


class PublicResourceInput(BaseModel):
    """Параметры для получения публичного ресурса."""
    model_config = ConfigDict(str_strip_whitespace=True)

    public_key: str = Field(
        ...,
        description="Публичная ссылка на Яндекс.Диск (например 'https://disk.yandex.ru/d/abc123')",
        min_length=1,
    )
    path: Optional[str] = Field(
        default=None,
        description="Путь внутри публичной папки (если ресурс — папка)"
    )


class ReadTextFileInput(BaseModel):
    """Параметры для чтения текстового файла."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: str = Field(
        ...,
        description="Полный путь к текстовому файлу на Яндекс.Диске",
        min_length=1,
    )
    max_size_kb: int = Field(
        default=512,
        description="Максимальный размер файла в КБ для чтения (защита от больших файлов)",
        ge=1,
        le=5120,
    )


# --- Инструменты ---

@mcp.tool(
    name="yadisk_list_folder",
    annotations={
        "title": "Листинг папки Яндекс.Диска",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def yadisk_list_folder(params: ListFolderInput) -> str:
    """Получить список файлов и папок по указанному пути на Яндекс.Диске.

    Args:
        params (ListFolderInput): Путь к папке, лимит и смещение.

    Returns:
        str: JSON со списком файлов и папок.
    """
    data = await _api_get("/resources", {
        "path": params.path,
        "limit": params.limit,
        "offset": params.offset,
        "fields": "_embedded.items.name,_embedded.items.type,_embedded.items.path,_embedded.items.size,_embedded.items.created,_embedded.items.modified,_embedded.items.mime_type,_embedded.total",
    })
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    embedded = data.get("_embedded", {})
    items = [_format_resource(i) for i in embedded.get("items", [])]
    result = {
        "path": params.path,
        "total": embedded.get("total", 0),
        "count": len(items),
        "offset": params.offset,
        "items": items,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(
    name="yadisk_get_file_info",
    annotations={
        "title": "Информация о файле",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def yadisk_get_file_info(params: FileInfoInput) -> str:
    """Получить метаинформацию о файле или папке на Яндекс.Диске.

    Args:
        params (FileInfoInput): Путь к файлу.

    Returns:
        str: JSON с метаинформацией (имя, размер, дата, тип).
    """
    data = await _api_get("/resources", {"path": params.path})
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(_format_resource(data), ensure_ascii=False, indent=2)


@mcp.tool(
    name="yadisk_download_link",
    annotations={
        "title": "Ссылка на скачивание файла",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def yadisk_download_link(params: DownloadLinkInput) -> str:
    """Получить прямую ссылку для скачивания файла с Яндекс.Диска.

    Args:
        params (DownloadLinkInput): Путь к файлу.

    Returns:
        str: JSON с прямой ссылкой на скачивание (действует ~30 минут).
    """
    data = await _api_get("/resources/download", {"path": params.path})
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)
    return json.dumps({
        "path": params.path,
        "download_url": data.get("href", ""),
        "method": data.get("method", "GET"),
    }, ensure_ascii=False, indent=2)


@mcp.tool(
    name="yadisk_search_files",
    annotations={
        "title": "Поиск файлов на Яндекс.Диске",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def yadisk_search_files(params: SearchFilesInput) -> str:
    """Получить последние загруженные файлы, с фильтрацией по типу медиа.

    Типы: document, spreadsheet, image, audio, video, compressed, executable и др.

    Args:
        params (SearchFilesInput): Тип медиа, лимит, смещение.

    Returns:
        str: JSON со списком файлов.
    """
    api_params = {
        "limit": params.limit,
        "offset": params.offset,
        "fields": "items.name,items.type,items.path,items.size,items.created,items.modified,items.mime_type",
    }
    if params.media_type:
        api_params["media_type"] = params.media_type

    data = await _api_get("/resources/files", api_params)
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    items = [_format_resource(i) for i in data.get("items", [])]
    return json.dumps({
        "media_type": params.media_type,
        "count": len(items),
        "offset": params.offset,
        "items": items,
    }, ensure_ascii=False, indent=2)


@mcp.tool(
    name="yadisk_public_resource",
    annotations={
        "title": "Публичный ресурс по ссылке",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def yadisk_public_resource(params: PublicResourceInput) -> str:
    """Получить информацию о публичном ресурсе на Яндекс.Диске по ссылке.

    Работает для любых публичных ссылок вида https://disk.yandex.ru/d/... или https://yadi.sk/d/...
    Если ресурс — папка, покажет содержимое.

    Args:
        params (PublicResourceInput): Публичная ссылка и путь внутри папки.

    Returns:
        str: JSON с информацией о ресурсе (имя, тип, размер, содержимое папки).
    """
    api_params = {"public_key": params.public_key}
    if params.path:
        api_params["path"] = params.path

    data = await _api_get("/public/resources", api_params)
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    result = _format_resource(data)

    # Если это папка — добавить содержимое
    embedded = data.get("_embedded", {})
    if embedded:
        result["total_items"] = embedded.get("total", 0)
        result["items"] = [_format_resource(i) for i in embedded.get("items", [])]

    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(
    name="yadisk_public_download_link",
    annotations={
        "title": "Скачать публичный ресурс",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def yadisk_public_download_link(params: PublicResourceInput) -> str:
    """Получить прямую ссылку на скачивание публичного ресурса.

    Args:
        params (PublicResourceInput): Публичная ссылка.

    Returns:
        str: JSON с прямой ссылкой на скачивание.
    """
    api_params = {"public_key": params.public_key}
    if params.path:
        api_params["path"] = params.path

    data = await _api_get("/public/resources/download", api_params)
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    return json.dumps({
        "public_key": params.public_key,
        "download_url": data.get("href", ""),
        "method": data.get("method", "GET"),
    }, ensure_ascii=False, indent=2)


@mcp.tool(
    name="yadisk_read_text_file",
    annotations={
        "title": "Прочитать текстовый файл",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def yadisk_read_text_file(params: ReadTextFileInput) -> str:
    """Скачать и вернуть содержимое текстового файла с Яндекс.Диска.

    Поддерживает .txt, .csv, .json, .xml, .md, .html и другие текстовые файлы.
    Для бинарных файлов (PDF, DOCX) используйте yadisk_download_link.

    Args:
        params (ReadTextFileInput): Путь к файлу и максимальный размер.

    Returns:
        str: Содержимое файла или ошибка.
    """
    # Сначала проверим размер
    info = await _api_get("/resources", {"path": params.path})
    if "error" in info:
        return json.dumps(info, ensure_ascii=False)

    size = info.get("size", 0)
    if size > params.max_size_kb * 1024:
        return json.dumps({
            "error": f"Файл слишком большой ({size // 1024} КБ). Максимум: {params.max_size_kb} КБ. Используйте yadisk_download_link для получения ссылки."
        }, ensure_ascii=False)

    # Получаем ссылку на скачивание
    dl = await _api_get("/resources/download", {"path": params.path})
    if "error" in dl:
        return json.dumps(dl, ensure_ascii=False)

    href = dl.get("href", "")
    if not href:
        return json.dumps({"error": "Не удалось получить ссылку на скачивание."}, ensure_ascii=False)

    # Скачиваем и декодируем
    try:
        raw = await _api_get_raw(href)
        text = raw.decode("utf-8", errors="replace")
        return json.dumps({
            "path": params.path,
            "size_bytes": len(raw),
            "content": text,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Ошибка при чтении файла: {str(e)}"}, ensure_ascii=False)


# --- Запуск ---

if __name__ == "__main__":
    if not YANDEX_OAUTH_TOKEN:
        logger.error("YANDEX_OAUTH_TOKEN не установлен! Сервер не сможет работать.")
    logger.info(f"Запуск yadisk_mcp на порту {PORT}")
    mcp.run(transport="sse", port=PORT)
