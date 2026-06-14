"""Нормализация телефона и поиск клиентов по номеру с разделителями."""

from sqlalchemy import select

from app.core.phones import normalize_phone
from app.models import Client


def test_normalize_phone_variants():
    # все варианты одного номера приводятся к одним 10 цифрам
    assert normalize_phone("+7 949 700-00-11") == "9497000011"
    assert normalize_phone("8 (949) 700 00 11") == "9497000011"
    assert normalize_phone("8949 700-00-11") == "9497000011"
    assert normalize_phone("9497000011") == "9497000011"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_validator_sets_phone_normalized():
    c = Client(name="A", phone_primary="+7 949 700-00-11")
    assert c.phone_normalized == "9497000011"
    # смена телефона пересчитывает нормализованный
    c.phone_primary = "8 (949) 700 00 22"
    assert c.phone_normalized == "9497000022"


async def test_search_by_phone_with_separators(session):
    session.add_all([
        Client(name="Иван", phone_primary="+7 949 700-00-11"),
        Client(name="Пётр", phone_primary="8 (949) 800-00-22"),
    ])
    await session.flush()

    # ищем по слитной строке цифр — раньше не находило из-за разделителей
    norm = normalize_phone("700 00 11")
    found = (
        await session.execute(
            select(Client).where(Client.phone_normalized.like(f"%{norm}%"))
        )
    ).scalars().all()
    assert [c.name for c in found] == ["Иван"]
