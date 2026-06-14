"""Seed-данные для разработки и приёмки (SPEC.md, раздел 16):
4 района, 2 пользователя, 3 водителя, 12 клиентов с адресами и координатами,
15 заказов на сегодня/завтра, настройки.

Запуск: python seed.py (повторный запуск ничего не дублирует).
"""

import asyncio
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.api.security import hash_password
from app.core.enums import GeocodeStatus, PaymentMethodPlan, TimeWindowType, UserRole
from app.db import SessionLocal
from app.models import Address, Client, District, Driver, Order, OrderEvent, Setting, User
from app.services.orders import create_order

DISTRICTS = ["Левобережный", "Кальмиуский", "Центральный", "Приморский"]

DRIVERS = [
    ("Сергей Иванов", "+7 949 101-01-01", "ГАЗель А123ВС", 40),
    ("Андрей Петренко", "+7 949 202-02-02", "Largus Б456ДЕ", 25),
    ("Михаил Козлов", "+7 949 303-03-03", "ГАЗель В789ЖЗ", 45),
]

# (имя, телефон, адрес, район idx, lat, lon, подъезд, этаж)
CLIENTS = [
    ("Иван Смирнов", "+7 949 111-11-01", "пр. Мира, 12, кв. 5", 2, "47.0971", "37.5434", "2", "3"),
    ("Ольга Ковальчук", "+7 949 111-11-02", "ул. Ленина, 45, кв. 12", 2, "47.0995", "37.5511", "1", "4"),
    ("Магазин «Родник»", "+7 949 111-11-03", "ул. Куприна, 3", 0, "47.1102", "37.5012", None, None),
    ("Пётр Лысенко", "+7 949 111-11-04", "ул. Морская, 78, кв. 1", 3, "47.0855", "37.5723", "3", "1"),
    ("Анна Гончарова", "+7 949 111-11-05", "пр. Нахимова, 21, кв. 44", 3, "47.0812", "37.5688", "4", "9"),
    ("Офис «Азов-Сталь»", "+7 949 111-11-06", "ул. Заводская, 1, офис 210", 0, "47.1201", "37.4955", None, "2"),
    ("Мария Дубова", "+7 949 111-11-07", "ул. Гранитная, 64, кв. 8", 1, "47.1133", "37.5601", "1", "2"),
    ("Николай Ткаченко", "+7 949 111-11-08", "ул. Азовстальская, 22, кв. 30", 1, "47.1088", "37.5677", "2", "7"),
    ("Кафе «Бриз»", "+7 949 111-11-09", "наб. Приморская, 5", 3, "47.0790", "37.5760", None, None),
    ("Екатерина Волкова", "+7 949 111-11-10", "пр. Строителей, 98, кв. 17", 1, "47.1156", "37.5489", "5", "5"),
    ("Дмитрий Орлов", "+7 949 111-11-11", "ул. Бахчиванджи, 7, кв. 2", 0, "47.1245", "37.5077", "1", "1"),
    ("Светлана Мельник", "+7 949 111-11-12", "б-р Шевченко, 30, кв. 55", 2, "47.1011", "37.5390", "3", "8"),
]


async def main() -> None:
    random.seed(42)
    async with SessionLocal() as session:
        existing = (await session.execute(select(User))).scalars().first()
        if existing is not None:
            print("Seed уже выполнен — пропускаю.")
            return

        session.add_all(
            [
                User(
                    login="admin",
                    password_hash=hash_password("admin123"),
                    name="Администратор",
                    role=UserRole.admin,
                ),
                User(
                    login="dispatcher",
                    password_hash=hash_password("dispatcher123"),
                    name="Диспетчер Елена",
                    role=UserRole.dispatcher,
                ),
            ]
        )
        districts = [District(name=n, sort_order=i) for i, n in enumerate(DISTRICTS, 1)]
        session.add_all(districts)
        drivers = [
            Driver(name=n, phone=p, vehicle=v, capacity_bottles=c)
            for n, p, v, c in DRIVERS
        ]
        session.add_all(drivers)
        session.add_all(
            [
                Setting(key="max_route_points", value=9),
                Setting(key="timezone", value="Europe/Moscow"),
                Setting(key="geocode_confidence_threshold", value=0.7),
                Setting(
                    key="scoring_rules",
                    value={
                        "completed": 1,
                        "day_no_failed_bonus": 2,
                        "failed_no_reason": -2,
                        "late_exact": -1,
                        "refused_not_driver_fault": 0,
                    },
                ),
            ]
        )
        await session.flush()

        clients: list[tuple[Client, Address]] = []
        for name, phone, addr, di, lat, lon, entrance, floor in CLIENTS:
            client = Client(name=name, phone_primary=phone)
            session.add(client)
            await session.flush()
            address = Address(
                client_id=client.id,
                raw_address=addr,
                district_id=districts[di].id,
                latitude=Decimal(lat),
                longitude=Decimal(lon),
                geocode_status=GeocodeStatus.manual,
                entrance=entrance,
                floor=floor,
            )
            session.add(address)
            clients.append((client, address))
        await session.flush()

        today, tomorrow = date.today(), date.today() + timedelta(days=1)
        windows = [TimeWindowType.any, TimeWindowType.first_half, TimeWindowType.second_half]
        for i in range(15):
            client, address = clients[i % len(clients)]
            pc = random.randint(0, 3)
            pet = random.randint(0, 2) if pc == 0 else random.randint(0, 1)
            if pc + pet == 0:
                pc = 2
            await create_order(
                session,
                {
                    "client_id": client.id,
                    "address_id": address.id,
                    "delivery_date": today if i < 9 else tomorrow,
                    "time_window_type": windows[i % 3],
                    "bottles_pc_qty": pc,
                    "bottles_pet_qty": pet,
                    "pumps_qty": 1 if i % 7 == 0 else 0,
                    "total_amount": Decimal(300 * (pc + pet) + (250 if i % 7 == 0 else 0)),
                    "payment_method_plan": (
                        PaymentMethodPlan.cash if i % 2 == 0 else PaymentMethodPlan.cashless
                    ),
                },
                actor_id=None,
            )
        await session.commit()
        print(
            f"Seed готов: {len(DISTRICTS)} района, 2 пользователя, {len(DRIVERS)} водителя, "
            f"{len(CLIENTS)} клиентов, 15 заказов (9 на сегодня, 6 на завтра).\n"
            "Логины: admin/admin123, dispatcher/dispatcher123 (только для разработки)."
        )


if __name__ == "__main__":
    asyncio.run(main())
