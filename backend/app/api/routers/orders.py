from datetime import date as date_type

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import (
    AssignDriverRequest,
    OrderDetailOut,
    OrderIn,
    OrderListOut,
    OrderOut,
    OrderPatch,
    PaymentOut,
    PaymentRequest,
    TransitionRequest,
)
from app.core.enums import ActorType, OrderStatus, TimeWindowType
from app.core.routes import point_link
from app.models import Order
from app.services import orders as orders_service
from app.services import payments as payments_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(body: OrderIn, session: SessionDep, user: CurrentUser):
    order = await orders_service.create_order(session, body.model_dump(), user.id)
    await session.commit()
    return order


@router.get("", response_model=OrderListOut)
async def list_orders(
    session: SessionDep,
    _: CurrentUser,
    date: date_type | None = None,
    district_id: int | None = None,
    part: TimeWindowType | None = None,
    status: OrderStatus | None = None,
    driver_id: int | None = None,
    client_id: int | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    items, total = await orders_service.list_orders(
        session,
        delivery_date=date,
        district_id=district_id,
        part=part,
        status=status,
        driver_id=driver_id,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )
    return OrderListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{order_id}", response_model=OrderDetailOut)
async def get_order(order_id: int, session: SessionDep, _: CurrentUser):
    order = (
        await session.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.events), selectinload(Order.address))
        )
    ).scalar_one_or_none()
    if order is None:
        from app.services.errors import NotFoundError

        raise NotFoundError("Заказ не найден")
    out = OrderDetailOut.model_validate(order)
    out.point_url = point_link(order.address.latitude, order.address.longitude, order.address_text)
    return out


@router.patch("/{order_id}", response_model=OrderOut)
async def patch_order(order_id: int, body: OrderPatch, session: SessionDep, user: CurrentUser):
    order = await orders_service.get_order(session, order_id)
    order = await orders_service.update_order(
        session, order, body.model_dump(exclude_unset=True), user.id
    )
    await session.commit()
    return order


@router.post("/{order_id}/assign-driver", response_model=OrderOut)
async def assign_driver(
    order_id: int, body: AssignDriverRequest, session: SessionDep, user: CurrentUser
):
    order = await orders_service.get_order(session, order_id)
    order = await orders_service.assign_driver(session, order, body.driver_id, user.id)
    await session.commit()
    return order


@router.post("/{order_id}/transition", response_model=OrderOut)
async def transition(
    order_id: int, body: TransitionRequest, session: SessionDep, user: CurrentUser
):
    """Смена статуса — только через машину состояний."""
    order = await orders_service.get_order(session, order_id)
    order = await orders_service.transition_order(
        session,
        order,
        body.status,
        ActorType.dispatcher,
        user.id,
        comment=body.comment or body.reason,
    )
    await session.commit()
    return order


@router.post("/{order_id}/payment", response_model=PaymentOut, status_code=201)
async def add_payment(order_id: int, body: PaymentRequest, session: SessionDep, user: CurrentUser):
    order = await orders_service.get_order(session, order_id)
    payment = await payments_service.register_payment(
        session, order, body.method, body.amount, ActorType.dispatcher, user.id
    )
    await session.commit()
    return payment
