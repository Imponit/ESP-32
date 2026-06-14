"""Доменные перечисления. Не зависят от FastAPI/SQLAlchemy."""

import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    dispatcher = "dispatcher"


class OrderStatus(str, enum.Enum):
    draft = "draft"
    new = "new"
    needs_review = "needs_review"
    planned = "planned"
    assigned = "assigned"
    sent_to_driver = "sent_to_driver"
    accepted_by_driver = "accepted_by_driver"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    refused = "refused"
    postponed = "postponed"
    cancelled = "cancelled"


class TimeWindowType(str, enum.Enum):
    any = "any"
    first_half = "first_half"
    second_half = "second_half"
    exact = "exact"


class DayPart(str, enum.Enum):
    any = "any"
    first_half = "first_half"
    second_half = "second_half"


class PaymentMethodPlan(str, enum.Enum):
    cash = "cash"
    cashless = "cashless"
    unknown = "unknown"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    cashless = "cashless"
    other = "other"


class PaymentStatus(str, enum.Enum):
    unpaid = "unpaid"
    paid = "paid"
    partial = "partial"


class GeocodeStatus(str, enum.Enum):
    # В MVP-1 используются none и manual; pending/ok/failed — для геокодера (MVP-2)
    none = "none"
    pending = "pending"
    ok = "ok"
    failed = "failed"
    manual = "manual"


class WorkStatus(str, enum.Enum):
    idle = "idle"
    on_route = "on_route"


class BatchStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    started = "started"
    finished = "finished"


class ActorType(str, enum.Enum):
    dispatcher = "dispatcher"
    driver = "driver"
    system = "system"


class SourceType(str, enum.Enum):
    manual = "manual"
    import_ = "import"
    telegram = "telegram"
    sms = "sms"
    max = "max"
    whatsapp = "whatsapp"
    phone = "phone"


class IncomingStatus(str, enum.Enum):
    # MVP-3: входящие заявки -> очередь черновиков на проверку диспетчером
    new = "new"
    converted = "converted"  # из заявки создан заказ
    ignored = "ignored"
