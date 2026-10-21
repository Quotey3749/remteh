"""Тесты репозиториев: CRUD, фильтры и агрегаты SQL."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from remteh.db import Database
from remteh.models import (
    Client,
    Equipment,
    Master,
    RequestStatus,
    ServiceRequest,
    StatusChange,
)
from remteh.repositories import (
    ClientRepository,
    EquipmentRepository,
    MasterRepository,
    RequestRepository,
)


class RepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Database(":memory:")
        self.clients = ClientRepository(self.db)
        self.equipment = EquipmentRepository(self.db)
        self.masters = MasterRepository(self.db)
        self.requests = RequestRepository(self.db)
        self.client_id = self.clients.add(
            Client(None, "Сидоров Сидор Сидорович", "+7 (902) 000-11-22")
        )
        self.equipment_id = self.equipment.add(
            Equipment(None, self.client_id, "Холодильник", "LG", "GA-B509", "LG-1")
        )
        self.master_id = self.masters.add(
            Master(None, "Орлов Олег Олегович", "Холодильники", "+7 (902) 111-22-33")
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_client_crud(self) -> None:
        client = self.clients.get(self.client_id)
        self.assertEqual(client.full_name, "Сидоров Сидор Сидорович")
        client.address = "Волгоград"
        self.clients.update(client)
        self.assertEqual(self.clients.get(self.client_id).address, "Волгоград")
        self.assertEqual(len(self.clients.list("Сидоров")), 1)
        self.assertEqual(len(self.clients.list("Петров")), 0)

    def test_equipment_by_client(self) -> None:
        self.assertEqual(len(self.equipment.list_by_client(self.client_id)), 1)
        self.assertEqual(len(self.equipment.list("LG")), 1)

    def test_master_active_filter(self) -> None:
        inactive = self.masters.add(
            Master(None, "Неактивов Иван", "Универсал", "+7 (902) 222-33-44", False)
        )
        self.assertEqual(len(self.masters.list(active_only=True)), 1)
        self.assertEqual(len(self.masters.list()), 2)
        self.assertIsNotNone(self.masters.get(inactive))

    def test_request_number_sequence(self) -> None:
        first = self.requests.next_number(2026)
        self.assertEqual(first, "З-2026-0001")
        self.requests.add(
            ServiceRequest(None, first, self.client_id, self.equipment_id, "Первый заказ")
        )
        self.assertEqual(self.requests.next_number(2026), "З-2026-0002")

    def test_request_view_joins_client_and_master(self) -> None:
        request_id = self.requests.add(
            ServiceRequest(
                None, "З-2026-0001", self.client_id, self.equipment_id,
                "Холодильник не морозит", master_id=self.master_id,
                planned_date=(date.today() + timedelta(days=2)).isoformat(),
            )
        )
        view = self.requests.get_view(request_id)
        self.assertEqual(view.client_name, "Сидоров Сидор Сидорович")
        self.assertEqual(view.master_title, "Орлов Олег Олегович")
        self.assertIn("Холодильник", view.equipment)

    def test_status_and_history(self) -> None:
        request_id = self.requests.add(
            ServiceRequest(None, "З-2026-0001", self.client_id, self.equipment_id,
                           "Холодильник не морозит")
        )
        self.requests.set_status(request_id, RequestStatus.ACCEPTED, None)
        self.requests.add_history(
            StatusChange(None, request_id, "new", "accepted", "2026-11-01T10:00:00", "Принята")
        )
        self.assertEqual(self.requests.get(request_id).status, RequestStatus.ACCEPTED)
        self.assertEqual(len(self.requests.list_history(request_id)), 1)

    def test_counts_and_revenue(self) -> None:
        self.requests.add(
            ServiceRequest(None, "З-2026-0001", self.client_id, self.equipment_id,
                           "Холодильник не морозит", status=RequestStatus.DONE,
                           completed_at=date.today().isoformat(), cost=1200)
        )
        self.requests.add(
            ServiceRequest(None, "З-2026-0002", self.client_id, self.equipment_id,
                           "Холодильник шумит", status=RequestStatus.NEW)
        )
        self.assertEqual(self.requests.count_by_status()[RequestStatus.NEW], 1)
        self.assertEqual(self.requests.count_active(), 1)
        self.assertEqual(self.requests.revenue_between(
            date.today().isoformat(), date.today().isoformat()), 1200)

    def test_master_load(self) -> None:
        self.requests.add(
            ServiceRequest(None, "З-2026-0001", self.client_id, self.equipment_id,
                           "Холодильник не морозит", master_id=self.master_id,
                           status=RequestStatus.IN_PROGRESS)
        )
        load = {row[0]: (row[1], row[2]) for row in self.requests.master_load()}
        self.assertEqual(load["Орлов Олег Олегович"], (1, 1))


if __name__ == "__main__":
    unittest.main()
