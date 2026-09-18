"""Доменные модели информационной системы сервисного центра «РемТех».

Модуль не зависит от базы данных и интерфейса: содержит перечисления,
dataclass-сущности и справочные структуры. Такое разделение позволяет
тестировать бизнес-правила отдельно от SQLite и tkinter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class RequestStatus(str, Enum):
    """Статусы заявки и допустимые переходы между ними."""

    NEW = "new"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    WAITING_PARTS = "waiting_parts"
    DONE = "done"
    CLOSED = "closed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        return STATUS_LABELS[self]

    @classmethod
    def from_value(cls, value: str) -> "RequestStatus":
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Неизвестный статус заявки: {value}") from exc


STATUS_LABELS: dict[RequestStatus, str] = {
    RequestStatus.NEW: "Новая",
    RequestStatus.ACCEPTED: "Принята",
    RequestStatus.IN_PROGRESS: "В работе",
    RequestStatus.WAITING_PARTS: "Ожидает детали",
    RequestStatus.DONE: "Выполнена",
    RequestStatus.CLOSED: "Закрыта",
    RequestStatus.CANCELLED: "Отменена",
}

# Разрешённые переходы. Словарь вынесен из метода, чтобы правило читалось
# как единая таблица и легко проверялось тестами.
TRANSITIONS: dict[RequestStatus, tuple[RequestStatus, ...]] = {
    RequestStatus.NEW: (
        RequestStatus.ACCEPTED,
        RequestStatus.CANCELLED,
    ),
    RequestStatus.ACCEPTED: (
        RequestStatus.IN_PROGRESS,
        RequestStatus.WAITING_PARTS,
        RequestStatus.CANCELLED,
    ),
    RequestStatus.IN_PROGRESS: (
        RequestStatus.WAITING_PARTS,
        RequestStatus.DONE,
        RequestStatus.CANCELLED,
    ),
    RequestStatus.WAITING_PARTS: (
        RequestStatus.IN_PROGRESS,
        RequestStatus.CANCELLED,
    ),
    RequestStatus.DONE: (RequestStatus.CLOSED,),
    RequestStatus.CLOSED: (),
    RequestStatus.CANCELLED: (),
}


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

    @property
    def label(self) -> str:
        return PRIORITY_LABELS[self]


PRIORITY_LABELS: dict[Priority, str] = {
    Priority.LOW: "Низкий",
    Priority.NORMAL: "Обычный",
    Priority.HIGH: "Высокий",
}


@dataclass(slots=True)
class Client:
    id: int | None
    full_name: str
    phone: str
    email: str = ""
    address: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass(slots=True)
class Equipment:
    id: int | None
    client_id: int
    kind: str
    brand: str
    model: str
    serial: str
    notes: str = ""


@dataclass(slots=True)
class Master:
    id: int | None
    full_name: str
    specialization: str
    phone: str
    active: bool = True


@dataclass(slots=True)
class WorkItem:
    id: int | None
    request_id: int
    title: str
    hours: float
    price: float


@dataclass(slots=True)
class ServiceRequest:
    id: int | None
    number: str
    client_id: int
    equipment_id: int
    description: str
    status: RequestStatus = RequestStatus.NEW
    priority: Priority = Priority.NORMAL
    master_id: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    planned_date: str | None = None
    completed_at: str | None = None
    cost: float = 0.0
    notes: str = ""

    def is_overdue(self, today: date | None = None) -> bool:
        """Просрочена ли заявка: срок прошёл, а работа ещё не завершена."""
        if not self.planned_date:
            return False
        if self.status in (RequestStatus.DONE, RequestStatus.CLOSED, RequestStatus.CANCELLED):
            return False
        current = today or date.today()
        return date.fromisoformat(self.planned_date) < current


@dataclass(slots=True)
class StatusChange:
    id: int | None
    request_id: int
    old_status: str
    new_status: str
    changed_at: str
    comment: str = ""


@dataclass(slots=True)
class RequestView:
    """Строка журнала заявок, собранная JOIN-запросом для интерфейса и отчётов."""

    id: int
    number: str
    client_name: str
    phone: str
    equipment: str
    master_name: str
    status: RequestStatus
    priority: Priority
    created_at: str
    planned_date: str | None
    cost: float
    description: str
    overdue: bool = False

    @property
    def equipment_title(self) -> str:
        return self.equipment

    @property
    def master_title(self) -> str:
        return self.master_name or "Не назначен"
