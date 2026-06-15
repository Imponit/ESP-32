"""Приём входящих заявок и конвертация в заказ (SPEC.md, раздел 3 MVP-3).

Поток: канал -> IncomingPayload -> incoming_messages (с авто-разбором) ->
очередь черновиков -> диспетчер проверяет -> convert_to_order / ignore.
"""

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.incoming import IncomingPayload
from app.core.enums import GeocodeStatus, IncomingStatus, SourceType
from app.core.intake_parser import parse_request_text
from app.core.phones import normalize_phone
from app.models import Address, Client, IncomingMessage, Order
from app.services.errors import NotFoundError, ValidationError
from app.services.orders import create_order


async def ingest_payload(
    session: AsyncSession, payload: IncomingPayload, parsed: dict | None = None
) -> IncomingMessage:
    """Сохранить входящее сообщение. parsed=None — прогнать эвристический разбор
    текста; для структурированных источников (Google Sheets) разбор передаётся готовым."""
    if parsed is None:
        parsed = parse_request_text(payload.text)
        # если у отправителя нет телефона в тексте, но есть номер-сендер — подскажем
        if (
            "phone" not in parsed["fields"]
            and payload.sender
            and payload.sender.lstrip("+").isdigit()
        ):
            norm = normalize_phone(payload.sender)
            if len(norm) == 10:
                parsed["fields"]["phone"] = payload.sender
                parsed["fields"]["phone_normalized"] = norm
    msg = IncomingMessage(
        source_type=payload.source_type,
        external_id=payload.external_id,
        sender=payload.sender,
        sender_name=payload.sender_name,
        raw_text=payload.text,
        parsed=parsed,
        status=IncomingStatus.new,
        received_at=payload.received_at or datetime.now(UTC),
    )
    session.add(msg)
    await session.flush()
    return msg


async def list_incoming(
    session: AsyncSession,
    status: IncomingStatus | None = None,
    source_type: SourceType | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[IncomingMessage], int]:
    q = select(IncomingMessage)
    if status is not None:
        q = q.where(IncomingMessage.status == status)
    if source_type is not None:
        q = q.where(IncomingMessage.source_type == source_type)
    total = (
        await session.execute(q.with_only_columns(func.count(IncomingMessage.id)))
    ).scalar_one()
    rows = (
        (await session.execute(q.order_by(IncomingMessage.id.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return list(rows), total


async def get_incoming(session: AsyncSession, message_id: int) -> IncomingMessage:
    msg = await session.get(IncomingMessage, message_id)
    if msg is None:
        raise NotFoundError("Входящее сообщение не найдено")
    return msg


async def ignore_message(session: AsyncSession, message_id: int) -> IncomingMessage:
    msg = await get_incoming(session, message_id)
    if msg.status == IncomingStatus.converted:
        raise ValidationError("Заявка уже сконвертирована в заказ")
    msg.status = IncomingStatus.ignored
    await session.flush()
    return msg


async def convert_to_order(
    session: AsyncSession, message_id: int, data: dict, actor_id: int | None
) -> Order:
    """Создать заказ из заявки. data — проверенные диспетчером поля.

    Клиент ищется/создаётся по телефону, адрес — создаётся новой строкой.
    Заявка помечается converted и связывается с заказом.
    """
    msg = await get_incoming(session, message_id)
    if msg.status == IncomingStatus.converted:
        raise ValidationError("Заявка уже сконвертирована")

    name = (data.get("name") or msg.sender_name or "").strip()
    phone = (data.get("phone") or "").strip()
    address_text = (data.get("address") or "").strip()
    if not name:
        raise ValidationError("Не указано имя клиента")
    if not phone:
        raise ValidationError("Не указан телефон клиента")
    if not address_text:
        raise ValidationError("Не указан адрес")
    if not data.get("delivery_date"):
        raise ValidationError("Не указана дата доставки")

    # find-or-create клиента по нормализованному телефону
    norm = normalize_phone(phone)
    client = None
    if norm:
        candidates = (
            (await session.execute(select(Client).where(Client.phone_normalized == norm)))
            .scalars()
            .all()
        )
        client = next((c for c in candidates if c.merged_into_id is None), None)
    if client is None:
        client = Client(name=name, phone_primary=phone)
        session.add(client)
        await session.flush()

    has_coords = data.get("latitude") is not None and data.get("longitude") is not None
    address = Address(
        client_id=client.id,
        raw_address=address_text,
        district_id=data.get("district_id"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        geocode_status=GeocodeStatus.manual if has_coords else GeocodeStatus.none,
        entrance=data.get("entrance"),
        floor=data.get("floor"),
    )
    session.add(address)
    await session.flush()

    order = await create_order(
        session,
        {
            "client_id": client.id,
            "address_id": address.id,
            "delivery_date": date.fromisoformat(data["delivery_date"])
            if isinstance(data["delivery_date"], str)
            else data["delivery_date"],
            "time_window_type": data.get("time_window_type", "any"),
            "bottles_pc_qty": int(data.get("bottles_pc_qty") or 0),
            "bottles_pet_qty": int(data.get("bottles_pet_qty") or 0),
            "pumps_qty": int(data.get("pumps_qty") or 0),
            "total_amount": data.get("total_amount") or 0,
            "comment": data.get("comment"),
            "source_type": msg.source_type,
        },
        actor_id=actor_id,
    )
    msg.status = IncomingStatus.converted
    msg.order_id = order.id
    await session.flush()
    return order
