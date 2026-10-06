"""Бизнес-логика сервисного центра: проверки, статусы, стоимость, отчёты."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from .db import Database
from .models import (
    Client,
    Equipment,
    Master,
    Priority,
    RequestStatus,
    RequestView,
    ServiceRequest,
    StatusChange,
    TRANSITIONS,
    WorkItem,
)
from .repositories import (
    ClientRepository,
    EquipmentRepository,
    MasterRepository,
    RequestRepository,
)

PHONE_RE = re.compile(r"^\+?[0-9()\-\s]{10,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(ValueError):
    """Нарушено бизнес-правило или формат введённых данных."""


class NotFoundError(LookupError):
    """Запрошенная сущность не найдена."""


class TransitionError(ValidationError):
    """Недопустимый переход статуса заявки."""


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("Дата должна быть в формате ГГГГ-ММ-ДД") from exc


def money(value: float) -> float:
    """Округление денежных сумм до копеек без ошибок двоичной арифметики."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class RequestService:
    """Фасад над репозиториями, в котором сосредоточены правила предметной области."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.clients = ClientRepository(db)
        self.equipment = EquipmentRepository(db)
        self.masters = MasterRepository(db)
        self.requests = RequestRepository(db)

    # ---------- клиенты и оборудование ----------

    def add_client(
        self, full_name: str, phone: str, email: str = "", address: str = ""
    ) -> int:
        full_name = full_name.strip()
        phone = phone.strip()
        if len(full_name.split()) < 2:
            raise ValidationError("Укажите фамилию и имя клиента")
        if not PHONE_RE.match(phone):
            raise ValidationError("Телефон должен содержать 10–20 цифр и символов + ( ) -")
        if email and not EMAIL_RE.match(email.strip()):
            raise ValidationError("Некорректный адрес электронной почты")
        return self.clients.add(Client(None, full_name, phone, email.strip(), address.strip()))

    def update_client(self, client: Client) -> None:
        if client.id is None:
            raise ValidationError("Клиент не выбран")
        if not client.full_name.strip():
            raise ValidationError("ФИО клиента не может быть пустым")
        if not PHONE_RE.match(client.phone.strip()):
            raise ValidationError("Некорректный телефон")
        if client.email and not EMAIL_RE.match(client.email.strip()):
            raise ValidationError("Некорректный адрес электронной почты")
        self.clients.update(client)

    def add_equipment(
        self, client_id: int, kind: str, brand: str, model: str, serial: str, notes: str = ""
    ) -> int:
        if self.clients.get(client_id) is None:
            raise NotFoundError("Клиент не найден")
        if not all(part.strip() for part in (kind, brand, model, serial)):
            raise ValidationError("Тип, производитель, модель и серийный номер обязательны")
        try:
            return self.equipment.add(
                Equipment(
                    None,
                    client_id,
                    kind.strip(),
                    brand.strip(),
                    model.strip(),
                    serial.strip(),
                    notes.strip(),
                )
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                "Оборудование с таким серийным номером уже зарегистрировано"
            ) from exc

    def update_equipment(self, item: Equipment) -> None:
        if item.id is None:
            raise ValidationError("Оборудование не выбрано")
        if self.clients.get(item.client_id) is None:
            raise NotFoundError("Клиент не найден")
        if not item.serial.strip():
            raise ValidationError("Серийный номер обязателен")
        try:
            self.equipment.update(item)
        except sqlite3.IntegrityError as exc:
            raise ValidationError(
                "Оборудование с таким серийным номером уже зарегистрировано"
            ) from exc

    def add_master(self, full_name: str, specialization: str, phone: str) -> int:
        if len(full_name.split()) < 2:
            raise ValidationError("Укажите фамилию и имя мастера")
        if not specialization.strip():
            raise ValidationError("Укажите специализацию")
        if not PHONE_RE.match(phone.strip()):
            raise ValidationError("Некорректный телефон мастера")
        return self.masters.add(
            Master(None, full_name.strip(), specialization.strip(), phone.strip())
        )

    def update_master(self, master: Master) -> None:
        if master.id is None:
            raise ValidationError("Мастер не выбран")
        if not master.full_name.strip():
            raise ValidationError("ФИО мастера не может быть пустым")
        self.masters.update(master)

    # ---------- заявки ----------

    def create_request(
        self,
        client_id: int,
        equipment_id: int,
        description: str,
        priority: Priority = Priority.NORMAL,
        planned_date: str | None = None,
    ) -> int:
        client = self.clients.get(client_id)
        if client is None:
            raise NotFoundError("Клиент не найден")
        equipment = self.equipment.get(equipment_id)
        if equipment is None:
            raise NotFoundError("Оборудование не найдено")
        if equipment.client_id != client_id:
            raise ValidationError("Оборудование принадлежит другому клиенту")
        description = description.strip()
        if len(description) < 10:
            raise ValidationError("Описание неисправности должно содержать не менее 10 символов")
        planned = parse_date(planned_date)
        if planned and planned < date.today():
            raise ValidationError("Плановая дата не может быть в прошлом")
        number = self.requests.next_number(date.today().year)
        request = ServiceRequest(
            id=None,
            number=number,
            client_id=client_id,
            equipment_id=equipment_id,
            description=description,
            priority=priority,
            planned_date=planned.isoformat() if planned else None,
        )
        return self.requests.add(request)

    def assign_master(self, request_id: int, master_id: int) -> None:
        request = self._get_request(request_id)
        master = self.masters.get(master_id)
        if master is None:
            raise NotFoundError("Мастер не найден")
        if not master.active:
            raise ValidationError("Нельзя назначить неактивного мастера")
        if request.status in (RequestStatus.DONE, RequestStatus.CLOSED, RequestStatus.CANCELLED):
            raise ValidationError("Нельзя назначить мастера на завершённую заявку")
        if request.status is RequestStatus.NEW:
            self._change_status(
                request, RequestStatus.ACCEPTED, f"Назначен мастер {master.full_name}"
            )
        self.requests.assign_master(request_id, master_id)

    def change_status(self, request_id: int, new_status: RequestStatus, comment: str = "") -> None:
        request = self._get_request(request_id)
        self._change_status(request, new_status, comment)

    def _change_status(
        self, request: ServiceRequest, new_status: RequestStatus, comment: str
    ) -> None:
        old_status = request.status
        self._validate_transition(request, new_status)
        completed_at = self._completion_time(request, new_status)
        self.requests.set_status(request.id or 0, new_status, completed_at)
        self.requests.add_history(
            StatusChange(
                None,
                request.id or 0,
                old_status.value,
                new_status.value,
                datetime.now().isoformat(timespec="seconds"),
                comment.strip(),
            )
        )
        request.status = new_status
        request.completed_at = completed_at

    def _validate_transition(
        self, request: ServiceRequest, new_status: RequestStatus
    ) -> None:
        if new_status is request.status:
            raise TransitionError("Заявка уже находится в этом статусе")
        if new_status not in TRANSITIONS[request.status]:
            raise TransitionError(
                f"Переход «{request.status.label} → {new_status.label}» не разрешён"
            )
        if new_status is RequestStatus.DONE and not self.requests.list_works(request.id or 0):
            raise ValidationError("Перед завершением добавьте хотя бы одну выполненную работу")

    @staticmethod
    def _completion_time(
        request: ServiceRequest, new_status: RequestStatus
    ) -> str | None:
        if new_status in (RequestStatus.DONE, RequestStatus.CLOSED) and not request.completed_at:
            return datetime.now().isoformat(timespec="seconds")
        return request.completed_at

    def _get_request(self, request_id: int) -> ServiceRequest:
        request = self.requests.get(request_id)
        if request is None:
            raise NotFoundError("Заявка не найдена")
        return request

    def add_work(self, request_id: int, title: str, hours: float, price: float) -> int:
        request = self._get_request(request_id)
        if request.status in (RequestStatus.DONE, RequestStatus.CLOSED, RequestStatus.CANCELLED):
            raise ValidationError("Нельзя изменить работы по завершённой заявке")
        title = title.strip()
        if len(title) < 3:
            raise ValidationError("Название работы слишком короткое")
        if hours <= 0:
            raise ValidationError("Трудоёмкость должна быть больше нуля")
        if price < 0:
            raise ValidationError("Стоимость не может быть отрицательной")
        work_id = self.requests.add_work(WorkItem(None, request_id, title, hours, money(price)))
        self._recalculate_cost(request_id)
        return work_id

    def remove_work(self, request_id: int, work_id: int) -> None:
        request = self._get_request(request_id)
        if request.status in (RequestStatus.DONE, RequestStatus.CLOSED, RequestStatus.CANCELLED):
            raise ValidationError("Нельзя изменить работы по завершённой заявке")
        self.requests.delete_work(work_id)
        self._recalculate_cost(request_id)

    def _recalculate_cost(self, request_id: int) -> float:
        total = money(self.requests.works_total(request_id))
        self.requests.update_cost(request_id, total)
        return total

    def close_request(self, request_id: int, comment: str = "") -> None:
        self.change_status(request_id, RequestStatus.CLOSED, comment)

    # ---------- выборки и отчёты ----------

    def search(
        self,
        text: str = "",
        status: RequestStatus | None = None,
        master_id: int | None = None,
        only_active: bool = False,
    ) -> list[RequestView]:
        return self.requests.list_views(text, status, master_id, only_active)

    def get_request(self, request_id: int) -> ServiceRequest:
        return self._get_request(request_id)

    def get_view(self, request_id: int) -> RequestView | None:
        return self.requests.get_view(request_id)

    def history(self, request_id: int) -> list[StatusChange]:
        return self.requests.list_history(request_id)

    def works(self, request_id: int) -> list[WorkItem]:
        return self.requests.list_works(request_id)

    def overdue(self) -> list[RequestView]:
        return [view for view in self.requests.list_views() if view.overdue]

    def status_counts(self) -> dict[str, int]:
        counts = self.requests.count_by_status()
        return {status.label: counts[status] for status in RequestStatus}

    def master_workload(self) -> list[dict[str, object]]:
        return [
            {"master": name, "total": total, "active": active}
            for name, total, active in self.requests.master_load()
        ]

    def revenue(self, start: str, end: str) -> float:
        start_date = parse_date(start)
        end_date = parse_date(end)
        if not start_date or not end_date:
            raise ValidationError("Укажите период отчёта")
        if start_date > end_date:
            raise ValidationError("Начало периода позже окончания")
        return money(self.requests.revenue_between(start, end))

    def dashboard(self) -> dict[str, object]:
        counts = self.requests.count_by_status()
        return {
            "total": sum(counts.values()),
            "active": self.requests.count_active(),
            "overdue": self.requests.count_overdue(),
            "revenue": money(
                self.requests.revenue_between(
                    date.today().replace(month=1, day=1).isoformat(),
                    date.today().isoformat(),
                )
            ),
            "statuses": {status.label: counts[status] for status in RequestStatus},
        }


def select_priority(value: str) -> Priority:
    """Преобразование подписи из интерфейса в перечисление."""
    for priority in Priority:
        if value in (priority.value, priority.label):
            return priority
    raise ValidationError("Неизвестный приоритет")
