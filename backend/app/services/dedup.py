"""Дедупликация клиентов: поиск дублей и слияние карточек (SPEC.md, раздел 3 MVP-2).

Слияние не удаляет карточку-источник, а проставляет ей `merged_into_id` (надгробие)
и переносит её адреса, контакты и заказы на основную карточку. Снапшот-поля заказов
не трогаются — они исторические.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.phones import normalize_phone as _normalize_phone
from app.models import Address, Client, ClientContact, Order
from app.services.errors import NotFoundError, ValidationError
from app.services.geocoding import normalize_address


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


@dataclass
class DuplicateGroup:
    client_ids: list[int]
    reasons: list[str] = field(default_factory=list)


async def find_duplicate_groups(session: AsyncSession) -> list[dict]:
    """Группы потенциальных дублей среди активных (не слитых) клиентов.

    Сигналы: одинаковый телефон, одинаковое имя, общий адрес. Группы с одинаковым
    набором участников объединяются, причины суммируются.
    """
    clients = (
        (
            await session.execute(
                select(Client)
                .where(Client.merged_into_id.is_(None))
                .options(selectinload(Client.addresses))
            )
        )
        .scalars()
        .all()
    )
    by_id = {c.id: c for c in clients}

    by_phone: dict[str, list[int]] = {}
    by_name: dict[str, list[int]] = {}
    by_address: dict[str, list[int]] = {}
    for c in clients:
        if (ph := _normalize_phone(c.phone_primary)):
            by_phone.setdefault(ph, []).append(c.id)
        if (nm := _normalize_name(c.name)):
            by_name.setdefault(nm, []).append(c.id)
        seen_addr: set[str] = set()
        for a in c.addresses:
            key = normalize_address(a.raw_address)
            if key and key not in seen_addr:
                seen_addr.add(key)
                by_address.setdefault(key, []).append(c.id)

    # member-set (frozenset) -> набор причин
    groups: dict[frozenset[int], set[str]] = {}

    def add(ids: list[int], reason: str) -> None:
        uniq = sorted(set(ids))
        if len(uniq) > 1:
            groups.setdefault(frozenset(uniq), set()).add(reason)

    for ids in by_phone.values():
        add(ids, "одинаковый телефон")
    for ids in by_name.values():
        add(ids, "совпадает имя")
    for ids in by_address.values():
        add(ids, "общий адрес")

    result = []
    for members, reasons in groups.items():
        ordered = sorted(members)
        result.append(
            {
                "client_ids": ordered,
                "reasons": sorted(reasons),
                "clients": [
                    {
                        "id": cid,
                        "name": by_id[cid].name,
                        "phone_primary": by_id[cid].phone_primary,
                        "addresses_count": len(by_id[cid].addresses),
                    }
                    for cid in ordered
                ],
            }
        )
    # Стабильный порядок: больше участников и «сильные» причины — выше
    result.sort(key=lambda g: (-len(g["client_ids"]), g["client_ids"]))
    return result


async def merge_clients(
    session: AsyncSession, target_id: int, source_ids: list[int]
) -> dict:
    """Слить source_ids в target_id: перенести адреса/контакты/заказы, пометить источники."""
    source_ids = [s for s in dict.fromkeys(source_ids)]  # уникальные, сохранить порядок
    if not source_ids:
        raise ValidationError("Не указаны карточки для слияния")
    if target_id in source_ids:
        raise ValidationError("Основная карточка не может быть среди сливаемых")

    target = await session.get(Client, target_id)
    if target is None or target.merged_into_id is not None:
        raise NotFoundError("Основная карточка не найдена или сама слита")

    moved = {"orders": 0, "addresses": 0, "contacts": 0}
    target_phone_norm = _normalize_phone(target.phone_primary)
    existing_contacts = {
        _normalize_phone(c.value)
        for c in (
            await session.execute(
                select(ClientContact).where(ClientContact.client_id == target_id)
            )
        ).scalars()
    }

    for sid in source_ids:
        source = await session.get(Client, sid)
        if source is None or source.merged_into_id is not None:
            raise NotFoundError(f"Карточка {sid} не найдена или уже слита")

        moved["addresses"] += (
            await session.execute(
                update(Address).where(Address.client_id == sid).values(client_id=target_id)
            )
        ).rowcount
        moved["contacts"] += (
            await session.execute(
                update(ClientContact)
                .where(ClientContact.client_id == sid)
                .values(client_id=target_id)
            )
        ).rowcount
        moved["orders"] += (
            await session.execute(
                update(Order).where(Order.client_id == sid).values(client_id=target_id)
            )
        ).rowcount

        # Телефон источника не теряем: добавим контактом, если он другой
        src_norm = _normalize_phone(source.phone_primary)
        if src_norm and src_norm != target_phone_norm and src_norm not in existing_contacts:
            session.add(
                ClientContact(
                    client_id=target_id,
                    type="phone",
                    value=source.phone_primary,
                    comment=f"из слитой карточки #{sid} ({source.name})",
                )
            )
            existing_contacts.add(src_norm)

        source.merged_into_id = target_id

    await session.flush()
    return {
        "target_id": target_id,
        "merged_source_ids": source_ids,
        "moved": moved,
    }
