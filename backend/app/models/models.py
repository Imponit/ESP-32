"""Модели MVP-1 (SPEC.md, раздел 5).

Снапшот-поля заказа (phone, client_name, district_id, entrance, floor, address_text)
дублируют данные клиента/адреса намеренно: заказ — исторический документ.

Таблицы MVP-2 (geocode_cache, driver_scores) и MVP-3 (incoming_messages,
message_sources, products, order_items) — TODO, добавятся своими миграциями.
"""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates

from app.core.enums import (
    ActorType,
    BatchStatus,
    DayPart,
    GeocodeStatus,
    IncomingStatus,
    OrderStatus,
    PaymentMethod,
    PaymentMethodPlan,
    PaymentStatus,
    ProductKind,
    SourceType,
    TimeWindowType,
    UserRole,
    WorkStatus,
)
from app.core.phones import normalize_phone


def _enum(enum_cls, name: str, length: int | None = None):
    # native_enum=False -> VARCHAR: работает и в PostgreSQL, и в SQLite (тесты).
    # length задаём явно там, где значения могут расширяться (source_type).
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone_primary: Mapped[str] = mapped_column(String(50), index=True)
    # Только цифры (нормализованный телефон) — для поиска и дедупликации.
    # Заполняется автоматически из phone_primary (см. validates ниже).
    phone_normalized: Mapped[str] = mapped_column(String(20), index=True, default="")
    comment: Mapped[str | None] = mapped_column(Text)
    # Слияние дублей (MVP-2): карточка-источник не удаляется, а помечается
    # ссылкой на основную карточку (историчность). merged_into_id is None — активна.
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    addresses: Mapped[list["Address"]] = relationship(back_populates="client")
    contacts: Mapped[list["ClientContact"]] = relationship(back_populates="client")

    @validates("phone_primary")
    def _sync_phone_normalized(self, key: str, value: str) -> str:
        self.phone_normalized = normalize_phone(value)
        return value


class ClientContact(Base):
    __tablename__ = "client_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))  # phone | telegram | other
    value: Mapped[str] = mapped_column(String(200))
    comment: Mapped[str | None] = mapped_column(Text)

    client: Mapped[Client] = relationship(back_populates="contacts")


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    raw_address: Mapped[str] = mapped_column(Text)
    normalized_address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    geocode_status: Mapped[GeocodeStatus] = mapped_column(
        _enum(GeocodeStatus, "geocode_status"), default=GeocodeStatus.none
    )
    geocode_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    entrance: Mapped[str | None] = mapped_column(String(50))
    floor: Mapped[str | None] = mapped_column(String(50))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship(back_populates="addresses")
    district: Mapped[District | None] = relationship()


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(50), index=True)
    telegram_id: Mapped[int | None] = mapped_column(unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # административный флаг
    work_status: Mapped[WorkStatus] = mapped_column(  # оперативный статус
        _enum(WorkStatus, "work_status"), default=WorkStatus.idle
    )
    district_default_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    vehicle: Mapped[str | None] = mapped_column(String(200))
    capacity_bottles: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    address_id: Mapped[int] = mapped_column(ForeignKey("addresses.id"))
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    time_window_type: Mapped[TimeWindowType] = mapped_column(
        _enum(TimeWindowType, "time_window_type"), default=TimeWindowType.any
    )
    time_window_from: Mapped[time | None] = mapped_column(Time)
    time_window_to: Mapped[time | None] = mapped_column(Time)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))  # снапшот
    bottles_pc_qty: Mapped[int] = mapped_column(Integer, default=0)
    bottles_pet_qty: Mapped[int] = mapped_column(Integer, default=0)
    pumps_qty: Mapped[int] = mapped_column(Integer, default=0)
    floor: Mapped[str | None] = mapped_column(String(50))  # снапшот
    entrance: Mapped[str | None] = mapped_column(String(50))  # снапшот
    phone: Mapped[str] = mapped_column(String(50))  # снапшот
    client_name: Mapped[str] = mapped_column(String(200))  # снапшот
    address_text: Mapped[str] = mapped_column(Text)  # снапшот
    comment: Mapped[str | None] = mapped_column(Text)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    payment_method_plan: Mapped[PaymentMethodPlan] = mapped_column(
        _enum(PaymentMethodPlan, "payment_method_plan"), default=PaymentMethodPlan.unknown
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        _enum(PaymentStatus, "payment_status"), default=PaymentStatus.unpaid
    )
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus, "order_status"), default=OrderStatus.new, index=True
    )
    assigned_driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), index=True)
    route_batch_id: Mapped[int | None] = mapped_column(ForeignKey("route_batches.id"), index=True)
    route_position: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type", length=20), default=SourceType.manual
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship()
    address: Mapped[Address] = relationship()
    driver: Mapped[Driver | None] = relationship()
    batch: Mapped["RouteBatch | None"] = relationship(back_populates="orders")
    events: Mapped[list["OrderEvent"]] = relationship(
        back_populates="order", order_by="OrderEvent.id"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")


class RouteBatch(Base):
    __tablename__ = "route_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    day_part: Mapped[DayPart] = mapped_column(_enum(DayPart, "day_part"), default=DayPart.any)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"))
    status: Mapped[BatchStatus] = mapped_column(
        _enum(BatchStatus, "batch_status"), default=BatchStatus.draft
    )
    route_url: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    driver: Mapped[Driver] = relationship()
    district: Mapped[District | None] = relationship()
    orders: Mapped[list[Order]] = relationship(
        back_populates="batch", order_by="Order.route_position"
    )


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))  # status_change | payment | comment | ...
    old_status: Mapped[str | None] = mapped_column(String(50))
    new_status: Mapped[str | None] = mapped_column(String(50))
    actor_type: Mapped[ActorType] = mapped_column(_enum(ActorType, "actor_type"))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    order: Mapped[Order] = relationship(back_populates="events")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod, "payment_method"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    order: Mapped[Order] = relationship(back_populates="payments")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class GeocodeCache(Base):
    """Кэш геокодинга по нормализованному адресу (SPEC.md, раздел 11, MVP-2).

    Если адрес уже в кэше — к провайдеру повторно не ходим.
    """

    __tablename__ = "geocode_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_normalized: Mapped[str] = mapped_column(Text, unique=True, index=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    precision: Mapped[str | None] = mapped_column(String(50))  # сырая точность провайдера
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    normalized_address: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50), default="yandex")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DriverScore(Base):
    """Сохранённый снимок баллов водителя за период (SPEC.md, раздел 14, MVP-2).

    Расчёт всегда идёт по orders/order_events; эта таблица хранит зафиксированный
    результат с разбивкой (breakdown) на момент расчёта.
    """

    __tablename__ = "driver_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date] = mapped_column(Date)
    points: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    breakdown: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CashHandover(Base):
    """Отметка «водитель сдал кассу» за дату (SPEC.md, раздел 13, MVP-2).

    Наличие записи = касса сдана. Одна запись на (водитель, дата).
    """

    __tablename__ = "cash_handovers"
    __table_args__ = (UniqueConstraint("driver_id", "handover_date", name="uq_cash_driver_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    handover_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # фактически сдано
    comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageSource(Base):
    """Источник входящих заявок (SPEC.md, раздел 5, MVP-3). Реестр каналов.

    Заготовка: канал идентифицируется типом; конфиг канала (токены, чаты) — в config.
    """

    __tablename__ = "message_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[SourceType] = mapped_column(_enum(SourceType, "source_type", length=20))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IncomingMessage(Base):
    """Входящая заявка от клиента (SPEC.md, раздел 5/3, MVP-3).

    Все входящие из любых каналов складываются сюда; диспетчер проверяет очередь
    черновиков и конвертирует в заказ. parsed — авто-извлечённые поля (имя, телефон,
    адрес, дата, количество, комментарий).
    """

    __tablename__ = "incoming_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[SourceType] = mapped_column(
        _enum(SourceType, "source_type", length=20), index=True
    )
    source_id: Mapped[int | None] = mapped_column(ForeignKey("message_sources.id"))
    external_id: Mapped[str | None] = mapped_column(String(200))  # id сообщения в канале
    sender: Mapped[str | None] = mapped_column(String(200))  # телефон / username / chat_id
    sender_name: Mapped[str | None] = mapped_column(String(200))
    raw_text: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[IncomingStatus] = mapped_column(
        _enum(IncomingStatus, "incoming_status"), default=IncomingStatus.new, index=True
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    """Каталог товаров/услуг (SPEC.md, раздел 3 MVP-3). kind связывает товар с
    фиксированными полями количества заказа (bottle_pc/bottle_pet/pump), `other` —
    прочие позиции, не считающиеся в бутыли."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[ProductKind] = mapped_column(
        _enum(ProductKind, "product_kind"), default=ProductKind.other
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderItem(Base):
    """Позиция заказа (SPEC.md, раздел 3 MVP-3). Снапшот наименования и цены —
    как и поля заказа, позиция историческая и не меняется вслед за каталогом."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(200))  # снапшот наименования
    kind: Mapped[ProductKind] = mapped_column(
        _enum(ProductKind, "product_kind"), default=ProductKind.other
    )
    qty: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))  # снапшот
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
