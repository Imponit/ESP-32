"""Pydantic-схемы API."""

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActorType,
    BatchStatus,
    DayPart,
    GeocodeStatus,
    OrderStatus,
    PaymentMethod,
    PaymentMethodPlan,
    PaymentStatus,
    SourceType,
    TimeWindowType,
    UserRole,
    WorkStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: int
    login: str
    name: str
    role: UserRole
    is_active: bool


# --- Справочники ---


class DistrictIn(BaseModel):
    name: str
    is_active: bool = True
    sort_order: int = 0


class DistrictPatch(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class DistrictOut(ORMModel):
    id: int
    name: str
    is_active: bool
    sort_order: int


# --- Клиенты и адреса ---


class AddressIn(BaseModel):
    raw_address: str
    district_id: int | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    entrance: str | None = None
    floor: str | None = None
    comment: str | None = None


class AddressPatch(BaseModel):
    raw_address: str | None = None
    district_id: int | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    entrance: str | None = None
    floor: str | None = None
    comment: str | None = None


class AddressOut(ORMModel):
    id: int
    client_id: int
    raw_address: str
    normalized_address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    geocode_status: GeocodeStatus
    geocode_confidence: Decimal | None = None
    district_id: int | None
    entrance: str | None
    floor: str | None
    comment: str | None


class IncomingIn(BaseModel):
    source_type: SourceType = SourceType.telegram
    text: str
    sender: str | None = None
    sender_name: str | None = None
    external_id: str | None = None


class IncomingOut(ORMModel):
    id: int
    source_type: SourceType
    external_id: str | None
    sender: str | None
    sender_name: str | None
    raw_text: str
    parsed: dict | None
    status: str
    order_id: int | None
    received_at: datetime | None
    created_at: datetime


class IncomingListOut(BaseModel):
    items: list[IncomingOut]
    total: int
    limit: int
    offset: int


class IncomingConvertRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    district_id: int | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    entrance: str | None = None
    floor: str | None = None
    delivery_date: date
    time_window_type: TimeWindowType = TimeWindowType.any
    bottles_pc_qty: int = 0
    bottles_pet_qty: int = 0
    pumps_qty: int = 0
    total_amount: Decimal = Decimal("0.00")
    comment: str | None = None


class DuplicateClientOut(BaseModel):
    id: int
    name: str
    phone_primary: str
    addresses_count: int


class DuplicateGroupOut(BaseModel):
    client_ids: list[int]
    reasons: list[str]
    clients: list[DuplicateClientOut]


class MergeRequest(BaseModel):
    target_id: int
    source_ids: list[int]


class MergeResultOut(BaseModel):
    target_id: int
    merged_source_ids: list[int]
    moved: dict


class GeocodeResponse(BaseModel):
    address_id: int
    # ok | failed | pending | skipped_manual | already_has_coords
    status: str
    latitude: str | None = None
    longitude: str | None = None
    confidence: str | None = None
    precision: str | None = None
    from_cache: bool = False
    imprecise: bool = False
    needs_review_order_ids: list[int] = Field(default_factory=list)


class ClientIn(BaseModel):
    name: str
    phone_primary: str
    comment: str | None = None
    addresses: list[AddressIn] = Field(default_factory=list)


class ClientPatch(BaseModel):
    name: str | None = None
    phone_primary: str | None = None
    comment: str | None = None


class ClientOut(ORMModel):
    id: int
    name: str
    phone_primary: str
    comment: str | None
    created_at: datetime


class ClientDetailOut(ClientOut):
    addresses: list[AddressOut] = Field(default_factory=list)


# --- Водители ---


class DriverIn(BaseModel):
    name: str
    phone: str
    telegram_id: int | None = None
    district_default_id: int | None = None
    vehicle: str | None = None
    capacity_bottles: int = 0
    comment: str | None = None


class DriverPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    telegram_id: int | None = None
    is_active: bool | None = None
    district_default_id: int | None = None
    vehicle: str | None = None
    capacity_bottles: int | None = None
    comment: str | None = None


class DriverOut(ORMModel):
    id: int
    name: str
    phone: str
    telegram_id: int | None
    is_active: bool
    work_status: WorkStatus
    district_default_id: int | None
    vehicle: str | None
    capacity_bottles: int
    comment: str | None


# --- Заказы ---


class OrderIn(BaseModel):
    client_id: int
    address_id: int
    delivery_date: date
    time_window_type: TimeWindowType = TimeWindowType.any
    time_window_from: time | None = None
    time_window_to: time | None = None
    bottles_pc_qty: int = 0
    bottles_pet_qty: int = 0
    pumps_qty: int = 0
    comment: str | None = None
    total_amount: Decimal = Decimal("0.00")
    payment_method_plan: PaymentMethodPlan = PaymentMethodPlan.unknown
    source_type: SourceType = SourceType.manual


class OrderPatch(BaseModel):
    address_id: int | None = None
    delivery_date: date | None = None
    time_window_type: TimeWindowType | None = None
    time_window_from: time | None = None
    time_window_to: time | None = None
    bottles_pc_qty: int | None = None
    bottles_pet_qty: int | None = None
    pumps_qty: int | None = None
    comment: str | None = None
    total_amount: Decimal | None = None
    payment_method_plan: PaymentMethodPlan | None = None


class OrderOut(ORMModel):
    id: int
    client_id: int
    address_id: int
    delivery_date: date
    time_window_type: TimeWindowType
    time_window_from: time | None
    time_window_to: time | None
    district_id: int | None
    bottles_pc_qty: int
    bottles_pet_qty: int
    pumps_qty: int
    floor: str | None
    entrance: str | None
    phone: str
    client_name: str
    address_text: str
    comment: str | None
    total_amount: Decimal
    payment_method_plan: PaymentMethodPlan
    payment_status: PaymentStatus
    paid_amount: Decimal
    status: OrderStatus
    assigned_driver_id: int | None
    route_batch_id: int | None
    route_position: int | None
    source_type: SourceType
    completed_at: datetime | None
    created_at: datetime


class OrderEventOut(ORMModel):
    id: int
    order_id: int
    event_type: str
    old_status: str | None
    new_status: str | None
    actor_type: ActorType
    actor_id: int | None
    comment: str | None
    created_at: datetime


class OrderDetailOut(OrderOut):
    point_url: str | None = None
    events: list[OrderEventOut] = Field(default_factory=list)


class OrderListOut(BaseModel):
    items: list[OrderOut]
    total: int
    limit: int
    offset: int


class AssignDriverRequest(BaseModel):
    driver_id: int | None  # None — снять назначение


class TransitionRequest(BaseModel):
    status: OrderStatus
    reason: str | None = None
    comment: str | None = None


class PaymentRequest(BaseModel):
    method: PaymentMethod
    amount: Decimal


class PaymentOut(ORMModel):
    id: int
    order_id: int
    driver_id: int | None
    method: PaymentMethod
    amount: Decimal
    created_at: datetime


# --- Планирование ---


class BatchCreateRequest(BaseModel):
    date: date
    day_part: DayPart = DayPart.any
    district_id: int | None = None
    driver_id: int
    order_ids: list[int]


class BatchOut(ORMModel):
    id: int
    delivery_date: date
    day_part: DayPart
    district_id: int | None
    driver_id: int
    status: BatchStatus
    route_url: str | None
    sent_at: datetime | None


class BatchCreateResponse(BaseModel):
    batch: BatchOut
    warnings: list[str]


class BatchDetailOut(BatchOut):
    orders: list[OrderOut] = Field(default_factory=list)


# --- Настройки ---


class JournalEventOut(BaseModel):
    id: int
    order_id: int
    event_type: str
    old_status: str | None
    new_status: str | None
    actor_type: str
    actor_id: int | None
    actor_name: str
    comment: str | None
    created_at: datetime
    order_client_name: str | None
    order_address: str | None


class JournalListOut(BaseModel):
    items: list[JournalEventOut]
    total: int
    limit: int
    offset: int


class DriverScoreOut(BaseModel):
    driver_id: int
    driver_name: str
    points: float
    breakdown: dict


class DriverScoreSavedOut(BaseModel):
    saved: int
    period_from: date
    period_to: date


class ImportReportOut(BaseModel):
    total_rows: int
    imported: int
    clients_created: int
    addresses_created: int
    errors: list[dict] = Field(default_factory=list)
    dry_run: bool
    order_ids: list[int] = Field(default_factory=list)


class CashHandoverRequest(BaseModel):
    driver_id: int
    date: date
    amount: Decimal | None = None
    comment: str | None = None


class CashHandoverOut(ORMModel):
    id: int
    driver_id: int
    handover_date: date
    amount: Decimal | None
    comment: str | None
    created_at: datetime


class SettingOut(BaseModel):
    key: str
    value: object


class SettingPatch(BaseModel):
    value: object
