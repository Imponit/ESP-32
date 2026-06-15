"""Эвристическое извлечение полей из текста заявки (SPEC.md, раздел 3 MVP-3).

Это базовый разбор регулярками и ключевыми словами — достаточный для черновика,
который диспетчер проверяет вручную. Полноценное ML-извлечение — позже (TODO).
Чистая функция без БД; возвращает найденные поля и список замечаний.
"""

import re
from datetime import date, timedelta

# Телефон: 10–11 цифр с возможными +, пробелами, скобками, дефисами
_PHONE_RE = re.compile(r"(?:\+7|8|7)?[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
_BOTTLES_RE = re.compile(r"(\d+)\s*(?:бут|бутыл|шт|штук)", re.IGNORECASE)
_NAME_RE = re.compile(r"(?:меня зовут|моё имя|мое имя|имя[:\s])\s*([А-ЯЁ][а-яёА-ЯЁ\- ]{1,40})")
# Адрес: маркер улицы как отдельный токен (граница слова + пробел после),
# чтобы «пр» не цеплялся внутри слов вроде «Просто».
_ADDR_RE = re.compile(
    r"\b((?:улица|проспект|переулок|бульвар|набережная|площадь|микрорайон|"
    r"ул|пр|пер|б-р|наб|пл|мкр)\.?\s+[^\n,;]+)",
    re.IGNORECASE,
)


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    return digits


def parse_request_text(text: str, today: date | None = None) -> dict:
    """Возвращает {fields: {...}, notes: [...]} — черновик заявки для проверки."""
    today = today or date.today()
    text = text or ""
    fields: dict = {}
    notes: list[str] = []

    m = _PHONE_RE.search(text)
    if m:
        norm = _normalize_phone(m.group(0))
        if len(norm) == 10:
            fields["phone"] = m.group(0).strip()
            fields["phone_normalized"] = norm
    if "phone" not in fields:
        notes.append("телефон не распознан")

    m = _NAME_RE.search(text)
    if m:
        fields["name"] = m.group(1).strip()

    m = _ADDR_RE.search(text)
    if m:
        # убираем затесавшийся в адрес телефон (когда нет запятой-разделителя)
        addr = _PHONE_RE.sub("", m.group(1))
        fields["address"] = re.sub(r"\s+", " ", addr).strip(" .,")
    else:
        notes.append("адрес не распознан")

    bottles = sum(int(x) for x in _BOTTLES_RE.findall(text))
    if bottles:
        fields["bottles_pc_qty"] = bottles

    low = text.lower()
    if "послезавтра" in low:
        fields["delivery_date"] = (today + timedelta(days=2)).isoformat()
    elif "завтра" in low:
        fields["delivery_date"] = (today + timedelta(days=1)).isoformat()
    elif "сегодня" in low:
        fields["delivery_date"] = today.isoformat()
    else:
        d = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\b", text)
        if d:
            day, month = int(d.group(1)), int(d.group(2))
            year = int(d.group(3) or today.year)
            if year < 100:
                year += 2000
            try:
                fields["delivery_date"] = date(year, month, day).isoformat()
            except ValueError:
                notes.append("дата не распознана")

    if "first" not in fields and ("первой половин" in low or "до обеда" in low or "утром" in low):
        fields["time_window_type"] = "first_half"
    elif "второй половин" in low or "после обеда" in low or "вечером" in low:
        fields["time_window_type"] = "second_half"

    return {"fields": fields, "notes": notes}
