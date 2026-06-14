from datetime import date as date_type

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import JournalListOut
from app.core.enums import ActorType
from app.services.events import list_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=JournalListOut)
async def get_events(
    session: SessionDep,
    _: CurrentUser,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    order_id: int | None = None,
    actor_type: ActorType | None = None,
    event_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    """Журнал событий (лента order_events) с фильтрами и пагинацией."""
    items, total = await list_events(
        session,
        date_from=date_from,
        date_to=date_to,
        order_id=order_id,
        actor_type=actor_type,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return JournalListOut(items=items, total=total, limit=limit, offset=offset)
