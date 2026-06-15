from datetime import date as date_type

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import (
    DriverIn,
    DriverOut,
    DriverPatch,
    DriverScoreOut,
    DriverScoreSavedOut,
)
from app.models import Driver
from app.services.scoring import compute_driver_scores, save_driver_scores

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=list[DriverOut])
async def list_drivers(session: SessionDep, _: CurrentUser, include_inactive: bool = True):
    q = select(Driver).order_by(Driver.id)
    if not include_inactive:
        q = q.where(Driver.is_active.is_(True))
    return list((await session.execute(q)).scalars().all())


@router.get("/scores", response_model=list[DriverScoreOut])
async def driver_scores(
    session: SessionDep,
    _: CurrentUser,
    date_from: date_type,
    date_to: date_type,
    driver_id: int | None = None,
):
    """Баллы водителей за период (SPEC.md, раздел 14). Коэффициенты — из настроек."""
    return await compute_driver_scores(session, date_from, date_to, driver_id)


@router.post("/scores/save", response_model=DriverScoreSavedOut)
async def save_scores(
    session: SessionDep, _: CurrentUser, date_from: date_type, date_to: date_type
):
    """Сохранить снимок баллов за период в driver_scores."""
    rows = await save_driver_scores(session, date_from, date_to)
    await session.commit()
    return DriverScoreSavedOut(saved=len(rows), period_from=date_from, period_to=date_to)


@router.post("", response_model=DriverOut, status_code=201)
async def create_driver(body: DriverIn, session: SessionDep, _: CurrentUser):
    driver = Driver(**body.model_dump())
    session.add(driver)
    await session.commit()
    return driver


@router.patch("/{driver_id}", response_model=DriverOut)
async def patch_driver(driver_id: int, body: DriverPatch, session: SessionDep, _: CurrentUser):
    """Правка водителя: активация/деактивация, привязка Telegram ID вручную и т.д."""
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(404, "Водитель не найден")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(driver, k, v)
    await session.commit()
    return driver
