from datetime import date as date_type

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.adapters.telegram import get_telegram_client
from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import (
    BatchCreateRequest,
    BatchCreateResponse,
    BatchDetailOut,
    BatchOut,
    OrderOut,
)
from app.models import Order, RouteBatch
from app.services import dispatch as dispatch_service
from app.services import planning as planning_service

router = APIRouter(tags=["planning"])


@router.post("/planning/batches", response_model=BatchCreateResponse, status_code=201)
async def create_batch(body: BatchCreateRequest, session: SessionDep, _: CurrentUser):
    batch, warnings = await planning_service.create_batch(
        session,
        delivery_date=body.date,
        day_part=body.day_part,
        district_id=body.district_id,
        driver_id=body.driver_id,
        order_ids=body.order_ids,
        optimize=body.optimize,
    )
    await session.commit()
    return BatchCreateResponse(batch=BatchOut.model_validate(batch), warnings=warnings)


@router.get("/route-batches", response_model=list[BatchDetailOut])
async def list_batches(session: SessionDep, _: CurrentUser, date: date_type | None = None):
    batches = await planning_service.list_batches(session, date)
    result = []
    for b in batches:
        orders = (
            (
                await session.execute(
                    select(Order).where(Order.route_batch_id == b.id).order_by(Order.route_position)
                )
            )
            .scalars()
            .all()
        )
        # строим из скалярных полей пакета (не трогаем ленивое b.orders) +
        # уже выбранные заказы
        base = BatchOut.model_validate(b)
        out = BatchDetailOut(
            **base.model_dump(),
            orders=[OrderOut.model_validate(o) for o in orders],
        )
        result.append(out)
    return result


@router.post("/dispatch/send/{batch_id}", response_model=BatchOut)
async def send_batch(batch_id: int, session: SessionDep, _: CurrentUser):
    """Отправить пакет водителю в Telegram (в dry-run — сообщение в лог)."""
    batch = (
        await session.execute(
            select(RouteBatch)
            .where(RouteBatch.id == batch_id)
            .options(selectinload(RouteBatch.driver), selectinload(RouteBatch.district))
        )
    ).scalar_one_or_none()
    if batch is None:
        from app.services.errors import NotFoundError

        raise NotFoundError("Пакет не найден")
    batch = await dispatch_service.send_batch(session, batch, get_telegram_client())
    await session.commit()
    return batch
