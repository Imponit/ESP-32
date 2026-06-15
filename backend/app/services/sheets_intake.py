"""Синхронизация заявок из Google Sheets в очередь входящих (SPEC.md, раздел 3 MVP-3).

Каждая строка таблицы -> запись в incoming_messages со структурированным разбором
(поля прямо из колонок, без эвристик). Повторная синхронизация не дублирует уже
принятые строки (дедуп по хешу содержимого строки).
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.google_sheets import GoogleSheetsAdapter
from app.adapters.incoming import IncomingPayload
from app.core.enums import SourceType
from app.core.phones import normalize_phone
from app.models import IncomingMessage
from app.services.importing import (
    HEADER_ALIASES,
    _norm_header,
    _parse_date,
    _parse_int,
)
from app.services.intake import ingest_payload

# Колонки, которые маппим в поля черновика (подмножество импорта)
_FIELD_KEYS = (
    "name", "phone", "address", "district", "date", "day_part",
    "bottles_pc", "bottles_pet", "pumps", "amount", "comment",
)

_DAY_PART_MAP = {
    "первая": "first_half", "первая половина": "first_half", "до обеда": "first_half",
    "first_half": "first_half",
    "вторая": "second_half", "вторая половина": "second_half", "после обеда": "second_half",
    "second_half": "second_half",
}


def _build_header_map(headers: list[str]) -> dict[str, str]:
    """нормализованный заголовок -> канонический ключ."""
    result = {}
    for h in headers:
        key = _norm_header(h)
        for canon, aliases in HEADER_ALIASES.items():
            if key in aliases:
                result[h] = canon
    return result


def row_to_fields(row: dict, header_map: dict[str, str]) -> dict:
    """Структурированный разбор строки таблицы -> parsed.fields для черновика."""
    canon: dict[str, str] = {}
    for raw_header, value in row.items():
        c = header_map.get(raw_header)
        if c:
            canon[c] = (value or "").strip()

    fields: dict = {}
    if canon.get("name"):
        fields["name"] = canon["name"]
    if canon.get("phone"):
        fields["phone"] = canon["phone"]
        norm = normalize_phone(canon["phone"])
        if norm:
            fields["phone_normalized"] = norm
    if canon.get("address"):
        fields["address"] = canon["address"]
    if canon.get("district"):
        fields["district_name"] = canon["district"]  # справочно; район выбирает диспетчер
    if canon.get("date"):
        try:
            fields["delivery_date"] = _parse_date(canon["date"]).isoformat()
        except ValueError:
            pass
    if canon.get("day_part"):
        dp = _DAY_PART_MAP.get(_norm_header(canon["day_part"]))
        if dp:
            fields["time_window_type"] = dp
    for src, dst in (("bottles_pc", "bottles_pc_qty"), ("bottles_pet", "bottles_pet_qty"),
                     ("pumps", "pumps_qty")):
        if canon.get(src):
            try:
                fields[dst] = _parse_int(canon[src], src)
            except ValueError:
                pass
    if canon.get("amount"):
        fields["total_amount"] = canon["amount"]
    if canon.get("comment"):
        fields["comment"] = canon["comment"]
    return fields


def _row_external_id(row: dict) -> str:
    """Стабильный id строки = хеш содержимого (одинаковые строки не дублируются)."""
    joined = "|".join(f"{k}={row[k]}" for k in sorted(row))
    return "gsheet:" + hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def _row_text(fields: dict, row: dict) -> str:
    parts = [f"{k}: {v}" for k, v in row.items() if v]
    return "; ".join(parts)


async def sync_google_sheet(session: AsyncSession, adapter: GoogleSheetsAdapter) -> dict:
    rows = await adapter.fetch_rows()
    if not rows:
        return {"total_rows": 0, "ingested": 0, "skipped": 0}

    header_map = _build_header_map(list(rows[0].keys()))

    # уже принятые строки таблиц — дедуп по external_id (gsheet:<hash>)
    existing_ids = set(
        (
            await session.execute(
                select(IncomingMessage.external_id).where(
                    IncomingMessage.external_id.like("gsheet:%")
                )
            )
        ).scalars()
    )

    ingested = skipped = 0
    for row in rows:
        ext_id = _row_external_id(row)
        if ext_id in existing_ids:
            skipped += 1
            continue
        fields = row_to_fields(row, header_map)
        payload = IncomingPayload(
            source_type=SourceType.google_sheets,
            text=_row_text(fields, row),
            external_id=ext_id,
            sender=fields.get("phone"),
            sender_name=fields.get("name"),
        )
        await ingest_payload(session, payload, parsed={"fields": fields, "notes": []})
        existing_ids.add(ext_id)
        ingested += 1

    await session.flush()
    return {"total_rows": len(rows), "ingested": ingested, "skipped": skipped}
