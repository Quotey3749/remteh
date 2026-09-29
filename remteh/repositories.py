"""Репозитории: SQL-запросы и преобразование строк SQLite в доменные объекты."""

from __future__ import annotations

import sqlite3
from datetime import date

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
    WorkItem,
)


def _client(row: sqlite3.Row) -> Client:
    return Client(
        id=row["id"],
        full_name=row["full_name"],
        phone=row["phone"],
        email=row["email"],
        address=row["address"],
        created_at=row["created_at"],
    )


def _equipment(row: sqlite3.Row) -> Equipment:
    return Equipment(
        id=row["id"],
        client_id=row["client_id"],
        kind=row["kind"],
        brand=row["brand"],
        model=row["model"],
        serial=row["serial"],
        notes=row["notes"],
    )


def _master(row: sqlite3.Row) -> Master:
    return Master(
        id=row["id"],
        full_name=row["full_name"],
        specialization=row["specialization"],
        phone=row["phone"],
        active=bool(row["active"]),
    )


def _request(row: sqlite3.Row) -> ServiceRequest:
    return ServiceRequest(
        id=row["id"],
        number=row["number"],
        client_id=row["client_id"],
        equipment_id=row["equipment_id"],
        master_id=row["master_id"],
        description=row["description"],
        status=RequestStatus(row["status"]),
        priority=Priority(row["priority"]),
        created_at=row["created_at"],
        planned_date=row["planned_date"],
        completed_at=row["completed_at"],
        cost=row["cost"],
        notes=row["notes"],
    )


class ClientRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, client: Client) -> int:
        cur = self.db.execute(
            """INSERT INTO clients (full_name, phone, email, address, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (client.full_name, client.phone, client.email, client.address, client.created_at),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get(self, client_id: int) -> Client | None:
        row = self.db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return _client(row) if row else None

    def list(self, search: str = "") -> list[Client]:
        pattern = f"%{search.strip()}%"
        rows = self.db.execute(
            """SELECT * FROM clients
               WHERE full_name LIKE ? OR phone LIKE ? OR email LIKE ? OR address LIKE ?
               ORDER BY full_name""",
            (pattern, pattern, pattern, pattern),
        ).fetchall()
        return [_client(row) for row in rows]

    def update(self, client: Client) -> None:
        if client.id is None:
            raise ValueError("Нельзя обновить клиента без идентификатора")
        self.db.execute(
            """UPDATE clients
               SET full_name = ?, phone = ?, email = ?, address = ?
               WHERE id = ?""",
            (client.full_name, client.phone, client.email, client.address, client.id),
        )
        self.db.commit()

    def has_requests(self, client_id: int) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM requests WHERE client_id = ? LIMIT 1", (client_id,)
        ).fetchone()
        return row is not None


class EquipmentRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, item: Equipment) -> int:
        cur = self.db.execute(
            """INSERT INTO equipment (client_id, kind, brand, model, serial, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item.client_id, item.kind, item.brand, item.model, item.serial, item.notes),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get(self, equipment_id: int) -> Equipment | None:
        row = self.db.execute("SELECT * FROM equipment WHERE id = ?", (equipment_id,)).fetchone()
        return _equipment(row) if row else None

    def list(self, search: str = "") -> list[Equipment]:
        pattern = f"%{search.strip()}%"
        rows = self.db.execute(
            """SELECT * FROM equipment
               WHERE kind LIKE ? OR brand LIKE ? OR model LIKE ? OR serial LIKE ?
               ORDER BY brand, model""",
            (pattern, pattern, pattern, pattern),
        ).fetchall()
        return [_equipment(row) for row in rows]

    def list_by_client(self, client_id: int) -> list[Equipment]:
        rows = self.db.execute(
            "SELECT * FROM equipment WHERE client_id = ? ORDER BY brand, model",
            (client_id,),
        ).fetchall()
        return [_equipment(row) for row in rows]

    def update(self, item: Equipment) -> None:
        if item.id is None:
            raise ValueError("Нельзя обновить оборудование без идентификатора")
        self.db.execute(
            """UPDATE equipment
               SET client_id = ?, kind = ?, brand = ?, model = ?, serial = ?, notes = ?
               WHERE id = ?""",
            (
                item.client_id,
                item.kind,
                item.brand,
                item.model,
                item.serial,
                item.notes,
                item.id,
            ),
        )
        self.db.commit()

    def has_requests(self, equipment_id: int) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM requests WHERE equipment_id = ? LIMIT 1", (equipment_id,)
        ).fetchone()
        return row is not None


class MasterRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, master: Master) -> int:
        cur = self.db.execute(
            """INSERT INTO masters (full_name, specialization, phone, active)
               VALUES (?, ?, ?, ?)""",
            (master.full_name, master.specialization, master.phone, int(master.active)),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get(self, master_id: int) -> Master | None:
        row = self.db.execute("SELECT * FROM masters WHERE id = ?", (master_id,)).fetchone()
        return _master(row) if row else None

    def list(self, active_only: bool = False) -> list[Master]:
        sql = "SELECT * FROM masters"
        if active_only:
            sql += " WHERE active = 1"
        rows = self.db.execute(sql + " ORDER BY full_name").fetchall()
        return [_master(row) for row in rows]

    def update(self, master: Master) -> None:
        if master.id is None:
            raise ValueError("Нельзя обновить мастера без идентификатора")
        self.db.execute(
            """UPDATE masters
               SET full_name = ?, specialization = ?, phone = ?, active = ?
               WHERE id = ?""",
            (master.full_name, master.specialization, master.phone, int(master.active), master.id),
        )
        self.db.commit()


class RequestRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def next_number(self, year: int) -> str:
        prefix = f"З-{year}-"
        row = self.db.execute(
            "SELECT number FROM requests WHERE number LIKE ? ORDER BY number DESC LIMIT 1",
            (prefix + "%",),
        ).fetchone()
        last = int(row["number"].rsplit("-", 1)[1]) if row else 0
        return f"{prefix}{last + 1:04d}"

    def add(self, request: ServiceRequest) -> int:
        cur = self.db.execute(
            """INSERT INTO requests
               (number, client_id, equipment_id, master_id, description, status,
                priority, created_at, planned_date, completed_at, cost, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.number,
                request.client_id,
                request.equipment_id,
                request.master_id,
                request.description,
                request.status.value,
                request.priority.value,
                request.created_at,
                request.planned_date,
                request.completed_at,
                request.cost,
                request.notes,
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def get(self, request_id: int) -> ServiceRequest | None:
        row = self.db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        return _request(row) if row else None

    def set_status(self, request_id: int, status: RequestStatus, completed_at: str | None) -> None:
        self.db.execute(
            "UPDATE requests SET status = ?, completed_at = ? WHERE id = ?",
            (status.value, completed_at, request_id),
        )
        self.db.commit()

    def assign_master(self, request_id: int, master_id: int | None) -> None:
        self.db.execute(
            "UPDATE requests SET master_id = ? WHERE id = ?", (master_id, request_id)
        )
        self.db.commit()

    def update_cost(self, request_id: int, cost: float) -> None:
        self.db.execute("UPDATE requests SET cost = ? WHERE id = ?", (cost, request_id))
        self.db.commit()

    def list_views(
        self,
        search: str = "",
        status: RequestStatus | None = None,
        master_id: int | None = None,
        only_active: bool = False,
    ) -> list[RequestView]:
        conditions: list[str] = []
        params: list[object] = []
        if search.strip():
            pattern = f"%{search.strip()}%"
            conditions.append(
                "(r.number LIKE ? OR c.full_name LIKE ? OR c.phone LIKE ? "
                "OR e.brand LIKE ? OR e.model LIKE ? OR r.description LIKE ?)"
            )
            params.extend([pattern] * 6)
        if status is not None:
            conditions.append("r.status = ?")
            params.append(status.value)
        if master_id is not None:
            conditions.append("r.master_id = ?")
            params.append(master_id)
        if only_active:
            conditions.append("r.status NOT IN ('closed', 'cancelled', 'done')")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = (
            """SELECT r.*, c.full_name AS client_name, c.phone AS phone,
                      e.kind || ' ' || e.brand || ' ' || e.model AS equipment,
                      m.full_name AS master_name
               FROM requests r
               JOIN clients c ON c.id = r.client_id
               JOIN equipment e ON e.id = r.equipment_id
               LEFT JOIN masters m ON m.id = r.master_id"""
            + where
            + " ORDER BY r.created_at DESC, r.id DESC"
        )
        rows = self.db.execute(sql, tuple(params)).fetchall()
        today = date.today()
        views: list[RequestView] = []
        for row in rows:
            request = _request(row)
            views.append(
                RequestView(
                    id=request.id or 0,
                    number=request.number,
                    client_name=row["client_name"],
                    phone=row["phone"],
                    equipment=row["equipment"],
                    master_name=row["master_name"] or "",
                    status=request.status,
                    priority=request.priority,
                    created_at=request.created_at,
                    planned_date=request.planned_date,
                    cost=request.cost,
                    description=request.description,
                    overdue=request.is_overdue(today),
                )
            )
        return views

    def get_view(self, request_id: int) -> RequestView | None:
        rows = self.list_views()
        return next((view for view in rows if view.id == request_id), None)

    def add_work(self, work: WorkItem) -> int:
        cur = self.db.execute(
            "INSERT INTO works (request_id, title, hours, price) VALUES (?, ?, ?, ?)",
            (work.request_id, work.title, work.hours, work.price),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def list_works(self, request_id: int) -> list[WorkItem]:
        rows = self.db.execute(
            "SELECT * FROM works WHERE request_id = ? ORDER BY id", (request_id,)
        ).fetchall()
        return [
            WorkItem(
                id=row["id"],
                request_id=row["request_id"],
                title=row["title"],
                hours=row["hours"],
                price=row["price"],
            )
            for row in rows
        ]

    def delete_work(self, work_id: int) -> None:
        self.db.execute("DELETE FROM works WHERE id = ?", (work_id,))
        self.db.commit()

    def works_total(self, request_id: int) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(price), 0) AS total FROM works WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return float(row["total"])

    def add_history(self, change: StatusChange) -> int:
        cur = self.db.execute(
            """INSERT INTO status_history
               (request_id, old_status, new_status, changed_at, comment)
               VALUES (?, ?, ?, ?, ?)""",
            (
                change.request_id,
                change.old_status,
                change.new_status,
                change.changed_at,
                change.comment,
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def list_history(self, request_id: int) -> list[StatusChange]:
        rows = self.db.execute(
            "SELECT * FROM status_history WHERE request_id = ? ORDER BY id",
            (request_id,),
        ).fetchall()
        return [
            StatusChange(
                id=row["id"],
                request_id=row["request_id"],
                old_status=row["old_status"],
                new_status=row["new_status"],
                changed_at=row["changed_at"],
                comment=row["comment"],
            )
            for row in rows
        ]

    def count_by_status(self) -> dict[RequestStatus, int]:
        counts = {status: 0 for status in RequestStatus}
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS amount FROM requests GROUP BY status"
        ).fetchall()
        for row in rows:
            counts[RequestStatus(row["status"])] = int(row["amount"])
        return counts

    def master_load(self) -> list[tuple[str, int, int]]:
        rows = self.db.execute(
            """SELECT m.full_name,
                      COUNT(r.id) AS total,
                      COALESCE(SUM(CASE WHEN r.status IN ('new', 'accepted', 'in_progress',
                                                         'waiting_parts') THEN 1 ELSE 0 END), 0)
                          AS active
               FROM masters m
               LEFT JOIN requests r ON r.master_id = m.id
               GROUP BY m.id
               ORDER BY active DESC, m.full_name"""
        ).fetchall()
        return [(row["full_name"], int(row["total"]), int(row["active"])) for row in rows]

    def revenue_between(self, start: str, end: str) -> float:
        row = self.db.execute(
            """SELECT COALESCE(SUM(cost), 0) AS total
               FROM requests
               WHERE status IN ('done', 'closed')
                 AND date(completed_at) BETWEEN date(?) AND date(?)""",
            (start, end),
        ).fetchone()
        return float(row["total"])

    def count_active(self) -> int:
        row = self.db.execute(
            """SELECT COUNT(*) AS amount FROM requests
               WHERE status NOT IN ('done', 'closed', 'cancelled')"""
        ).fetchone()
        return int(row["amount"])

    def count_overdue(self) -> int:
        row = self.db.execute(
            """SELECT COUNT(*) AS amount FROM requests
               WHERE planned_date IS NOT NULL
                 AND date(planned_date) < date('now')
                 AND status NOT IN ('done', 'closed', 'cancelled')"""
        ).fetchone()
        return int(row["amount"])
