from datetime import date as date_type

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import CurrentUser, SessionDep
from app.services.report_export import export_daily_report
from app.services.reporting import daily_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily")
async def get_daily_report(date: date_type, session: SessionDep, _: CurrentUser) -> dict:
    """Дневной отчёт: заказы по статусам, бутыли, деньги по способам оплаты,
    касса по водителям, отказы с причинами, completed без оплаты."""
    return await daily_report(session, date)


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
