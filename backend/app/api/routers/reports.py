from datetime import date as date_type

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import CashHandoverOut, CashHandoverRequest
from app.services.analytics import period_analytics
from app.services.cash import mark_cash_handover, remove_cash_handover
from app.services.report_export import export_daily_report
from app.services.reporting import daily_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily")
async def get_daily_report(date: date_type, session: SessionDep, _: CurrentUser) -> dict:
    """Дневной отчёт: заказы по статусам, бутыли, деньги по способам оплаты,
    касса по водителям, отказы с причинами, completed без оплаты."""
    return await daily_report(session, date)


@router.get("/analytics")
async def get_analytics(
    date_from: date_type, date_to: date_type, session: SessionDep, _: CurrentUser
) -> dict:
    """Аналитика за период (MVP-3): KPI, разбивки по дням/водителям/районам,
    топ товаров."""
    return await period_analytics(session, date_from, date_to)


@router.get("/export")
async def export_report(
    date: date_type, session: SessionDep, _: CurrentUser, format: str = "xlsx"
):
    """Экспорт дневного отчёта (MVP-2): format=csv|xlsx."""
    content, media_type, filename = await export_daily_report(session, date, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/cash-handover", response_model=CashHandoverOut, status_code=201)
async def cash_handover(body: CashHandoverRequest, session: SessionDep, user: CurrentUser):
    """Отметить, что водитель сдал кассу за дату (MVP-2)."""
    row = await mark_cash_handover(
        session, body.driver_id, body.date, body.amount, body.comment, user.id
    )
    await session.commit()
    return row


@router.delete("/cash-handover", status_code=204)
async def cancel_cash_handover(
    driver_id: int, date: date_type, session: SessionDep, _: CurrentUser
):
    """Снять отметку о сдаче кассы."""
    removed = await remove_cash_handover(session, driver_id, date)
    if not removed:
        raise HTTPException(404, "Отметка не найдена")
    await session.commit()
