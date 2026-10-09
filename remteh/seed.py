"""Демонстрационные данные для первого запуска и скриншотов."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .db import Database
from .models import (
    Client,
    Equipment,
    Master,
    Priority,
    RequestStatus,
    ServiceRequest,
    StatusChange,
    WorkItem,
)
from .repositories import (
    ClientRepository,
    EquipmentRepository,
    MasterRepository,
    RequestRepository,
)


def _iso(day: date, hour: int = 10, minute: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, minute).isoformat(timespec="seconds")


def seed_demo(db: Database, force: bool = False) -> bool:
    """Заполняет пустую базу примерами. Возвращает True, если данные добавлены."""
    clients_repo = ClientRepository(db)
    equipment_repo = EquipmentRepository(db)
    masters_repo = MasterRepository(db)
    requests_repo = RequestRepository(db)
    if clients_repo.list() and not force:
        return False

    today = date.today()
    clients = [
        Client(None, "Смирнова Анна Павловна", "+7 (902) 111-22-33", "a.smirnova@mail.ru",
               "Волгоград, ул. Мира, 15", _iso(today - timedelta(days=120))),
        Client(None, "Кузнецов Игорь Викторович", "+7 (927) 555-44-22", "igor.k@yandex.ru",
               "Волгоград, пр. Ленина, 42", _iso(today - timedelta(days=95))),
        Client(None, "Орлова Мария Сергеевна", "+7 (904) 777-31-18", "orlova.m@gmail.com",
               "Волгоград, ул. Землячки, 7", _iso(today - timedelta(days=80))),
        Client(None, "Гаврилов Пётр Андреевич", "+7 (988) 300-12-90", "gavrilov@mail.ru",
               "Волгоград, ул. 8-й Воздушной армии, 3", _iso(today - timedelta(days=60))),
        Client(None, "Лебедева Ольга Игоревна", "+7 (960) 240-55-71", "o.lebedeva@mail.ru",
               "Волгоград, ул. Рокоссовского, 18", _iso(today - timedelta(days=40))),
    ]
    client_ids = [clients_repo.add(client) for client in clients]

    equipment = [
        Equipment(None, client_ids[0], "Стиральная машина", "Bosch", "Serie 6 WLG 2426",
                  "BSH-77120", "Гарантия истекла в 2025 году"),
        Equipment(None, client_ids[0], "Холодильник", "LG", "DoorCooling GA-B509",
                  "LG-44201", ""),
        Equipment(None, client_ids[1], "Пылесос", "Dyson", "V11 SV14", "DYS-11873", ""),
        Equipment(None, client_ids[2], "Кофемашина", "De'Longhi", "Magnifica ECAM 22.110",
                  "DL-90312", "На гарантии"),
        Equipment(None, client_ids[3], "Телевизор", "Samsung", "QE55 Q60B", "SAM-55617", ""),
        Equipment(None, client_ids[4], "Посудомоечная машина", "Electrolux", "ESL 94510",
                  "ELX-22087", ""),
        Equipment(None, client_ids[1], "Микроволновая печь", "Panasonic", "NN-ST342",
                  "PAN-77129", ""),
    ]
    equipment_ids = [equipment_repo.add(item) for item in equipment]

    masters = [
        Master(None, "Ковалёв Сергей Николаевич", "Стиральные и посудомоечные машины",
               "+7 (902) 444-10-20"),
        Master(None, "Данилов Артём Игоревич", "Холодильники и кондиционеры",
               "+7 (927) 888-22-31"),
        Master(None, "Белова Ирина Максимовна", "Мелкая бытовая техника",
               "+7 (904) 123-77-45"),
        Master(None, "Титов Максим Олегович", "Телевизоры и аудиотехника",
               "+7 (988) 765-43-21"),
        Master(None, "Ершов Никита Дмитриевич", "Универсал", "+7 (960) 333-90-11", False),
    ]
    master_ids = [masters_repo.add(master) for master in masters]

    rows = [
        # номер, клиент, оборудование, мастер, описание, статус, приоритет,
        # план, завершение, работы
        ("З-2026-0001", 0, 0, 0, "Сильная вибрация при отжиме, машина смещается с места",
         RequestStatus.IN_PROGRESS, Priority.HIGH, today + timedelta(days=2), None,
         [("Диагностика", 0.5, 900), ("Замена подшипникового узла", 1.5, 3200)]),
        ("З-2026-0002", 1, 2, 2, "Не держит заряд, работает не более пяти минут",
         RequestStatus.NEW, Priority.NORMAL, today + timedelta(days=1), None, []),
        ("З-2026-0003", 2, 3, 2, "Приготовление кофе останавливается с ошибкой 05",
         RequestStatus.WAITING_PARTS, Priority.HIGH, today - timedelta(days=2), None,
         [("Диагностика", 0.5, 900)]),
        ("З-2026-0004", 3, 4, 3, "Нет изображения, звук присутствует, подсветка работает",
         RequestStatus.ACCEPTED, Priority.NORMAL, today + timedelta(days=3), None, []),
        ("З-2026-0005", 4, 5, 0, "Не сливает воду, на дне остаётся лужа",
         RequestStatus.DONE, Priority.NORMAL, today - timedelta(days=1),
         _iso(today - timedelta(days=1), 16, 40),
         [("Диагностика", 0.5, 900), ("Замена сливного насоса", 1.5, 3600)]),
        ("З-2026-0006", 0, 1, 1, "Морозильная камера не держит температуру, намерзает лёд",
         RequestStatus.IN_PROGRESS, Priority.HIGH, today - timedelta(days=1), None,
         [("Диагностика", 0.7, 1200), ("Замена компрессора", 3.0, 6500)]),
        ("З-2026-0007", 1, 6, 2, "Не включается микроволновая печь, нет реакции на кнопки",
         RequestStatus.CLOSED, Priority.LOW, today - timedelta(days=10),
         _iso(today - timedelta(days=8), 12, 15),
         [("Диагностика", 0.5, 900), ("Замена предохранителя", 0.5, 900)]),
        ("З-2026-0008", 3, 4, 3, "Клиент отказался от ремонта, купил новый телевизор",
         RequestStatus.CANCELLED, Priority.LOW, today - timedelta(days=3), None, []),
        ("З-2026-0009", 4, 5, 0, "Шумит при наборе воды, слышен скрежет в насосе",
         RequestStatus.NEW, Priority.NORMAL, today + timedelta(days=4), None, []),
        ("З-2026-0010", 2, 3, 2, "Течёт вода из-под корпуса при промывке",
         RequestStatus.IN_PROGRESS, Priority.NORMAL, today + timedelta(days=1), None,
         [("Диагностика", 0.5, 900), ("Замена уплотнителя", 1.0, 1600)]),
        ("З-2026-0011", 1, 2, 2, "Замена аккумулятора и фильтра после диагностики",
         RequestStatus.DONE, Priority.LOW, today - timedelta(days=5),
         _iso(today - timedelta(days=4), 18, 5),
         [("Диагностика", 0.5, 900), ("Замена аккумулятора", 1.0, 4200)]),
        ("З-2026-0012", 0, 0, 0, "Профилактическая чистка и замена уплотнителя люка",
         RequestStatus.CLOSED, Priority.NORMAL, today - timedelta(days=20),
         _iso(today - timedelta(days=18), 14, 30),
         [("Профилактика", 1.0, 1800), ("Замена уплотнителя", 0.8, 2100)]),
    ]

    for index, (number, client_idx, equipment_idx, master_idx, description, status,
                priority, planned, completed, works) in enumerate(rows):
        created = today - timedelta(days=14 - index)
        cost = sum(price for _, _, price in works)
        request_id = requests_repo.add(
            ServiceRequest(
                id=None,
                number=number,
                client_id=client_ids[client_idx],
                equipment_id=equipment_ids[equipment_idx],
                master_id=master_ids[master_idx] if master_idx is not None else None,
                description=description,
                status=status,
                priority=priority,
                created_at=_iso(created, 9, 20 + index),
                planned_date=planned.isoformat(),
                completed_at=completed,
                cost=cost,
            )
        )
        for title, hours, price in works:
            requests_repo.add_work(WorkItem(None, request_id, title, hours, price))

    history = [
        (0, [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS]),
        (2, [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.WAITING_PARTS]),
        (4, [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS,
             RequestStatus.DONE]),
        (6, [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.IN_PROGRESS,
             RequestStatus.DONE, RequestStatus.CLOSED]),
        (7, [RequestStatus.NEW, RequestStatus.CANCELLED]),
    ]
    for request_index, chain in history:
        request_id = request_index + 1
        for step in range(1, len(chain)):
            requests_repo.add_history(
                StatusChange(
                    None,
                    request_id,
                    chain[step - 1].value,
                    chain[step].value,
                    _iso(today - timedelta(days=14 - request_index - step), 11, 0),
                    "Демонстрационная запись",
                )
            )
    return True
