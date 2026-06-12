from datetime import date as date_type

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.services.reporting import daily_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily")
async def get_daily_report(date: date_type, session: SessionDep, _: CurrentUser) -> dict:
    """Дневной отчёт: заказы по статусам, бутыли, деньги по способам оплаты,
    касса по водителям, отказы с причинами, completed без оплаты."""
    return await daily_report(session, date)


@router.get("/export")
async def export_report(date: date_type, format: str = "xlsx"):
    """TODO MVP-2: экспорт отчётов в XLSX/CSV."""
    raise HTTPException(501, "Экспорт отчётов — MVP-2")
