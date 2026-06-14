"""Адаптер входящих заявок из Google Sheets (SPEC.md, раздел 3, MVP-3).

Читаем таблицу как CSV-экспорт (для таблицы с доступом «по ссылке» или
опубликованной в веб — OAuth не нужен):
  https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>

Возвращаем строки как список словарей {заголовок: значение}. Реальная выборка —
CsvExportGoogleSheetsAdapter; для тестов — MockGoogleSheetsAdapter.
"""

import csv
import io
import logging
from typing import Protocol

import httpx

logger = logging.getLogger("google_sheets")


class GoogleSheetsAdapter(Protocol):
    async def fetch_rows(self) -> list[dict]: ...


class GoogleSheetsUnavailableError(Exception):
    pass


def _rows_from_csv(text: str) -> list[dict]:
    reader = csv.reader(io.StringIO(text))
    rows = [[(c or "").strip() for c in row] for row in reader]
    if not rows:
        return []
    headers, *data = rows
    result = []
    for raw in data:
        if not any(raw):
            continue
        result.append({headers[i]: (raw[i] if i < len(raw) else "") for i in range(len(headers))})
    return result


class CsvExportGoogleSheetsAdapter:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self._url = url
        self._timeout = timeout

    async def fetch_rows(self) -> list[dict]:
        logger.info("Google Sheets sync: %s", self._url)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                resp = await client.get(self._url)
        except httpx.HTTPError as e:
            raise GoogleSheetsUnavailableError(str(e)) from e
        if resp.status_code != 200:
            raise GoogleSheetsUnavailableError(f"HTTP {resp.status_code}")
        return _rows_from_csv(resp.text)


class MockGoogleSheetsAdapter:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def fetch_rows(self) -> list[dict]:
        return list(self.rows)


def get_google_sheets_adapter() -> GoogleSheetsAdapter | None:
    from app.config import settings

    if not settings.google_sheets_csv_url:
        return None
    return CsvExportGoogleSheetsAdapter(settings.google_sheets_csv_url)
