"""Модульные тесты бизнес-логики сервисного центра."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from remteh.db import Database
from remteh.models import Priority, RequestStatus
from remteh.service import NotFoundError, RequestService, TransitionError, ValidationError


class ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Database(":memory:")
        self.service = RequestService(self.db)
        self.client_id = self.service.add_client(
            "Иванов Иван Иванович", "+7 (902) 100-20-30", "ivanov@mail.ru", "Волгоград"
        )
        self.equipment_id = self.service.add_equipment(
            self.client_id, "Стиральная машина", "Bosch", "Serie 6", "SN-0001"
        )
        self.master_id = self.service.add_master(
            "Петров Пётр Петрович", "Стиральные машины", "+7 (902) 200-30-40"
        )

    def tearDown(self) -> None:
        self.db.close()

    def _create(self, description: str = "Машина не сливает воду и гудит при отжиме") -> int:
        return self.service.create_request(
            self.client_id,
            self.equipment_id,
            description,
            Priority.NORMAL,
            (date.today() + timedelta(days=3)).isoformat(),
        )

    # ---------- клиенты ----------

    def test_client_created_and_found(self) -> None:
        client = self.service.clients.get(self.client_id)
        self.assertIsNotNone(client)
        self.assertEqual(client.full_name, "Иванов Иван Иванович")
        self.assertEqual(len(self.service.clients.list("Иванов")), 1)

    def test_client_requires_full_name(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_client("Иванов", "+7 (902) 100-20-30")

    def test_client_rejects_bad_phone(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_client("Иванов Иван", "123")

    def test_client_rejects_bad_email(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_client("Иванов Иван", "+7 (902) 100-20-30", "bad-mail")

    def test_client_update(self) -> None:
        client = self.service.clients.get(self.client_id)
        client.phone = "+7 (902) 999-99-99"
        self.service.update_client(client)
        self.assertEqual(self.service.clients.get(self.client_id).phone, "+7 (902) 999-99-99")

    def test_duplicate_serial_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_equipment(
                self.client_id, "Стиральная машина", "Bosch", "Serie 4", "SN-0001"
            )

    # ---------- заявки ----------

    def test_request_created_with_number_and_status(self) -> None:
        request_id = self._create()
        request = self.service.get_request(request_id)
        self.assertEqual(request.status, RequestStatus.NEW)
        self.assertTrue(request.number.startswith("З-"))
        self.assertTrue(request.number.endswith("0001"))

    def test_request_numbers_increment(self) -> None:
        first = self.service.get_request(self._create()).number
        second = self.service.get_request(self._create()).number
        self.assertNotEqual(first, second)
        self.assertEqual(int(second.rsplit("-", 1)[1]), int(first.rsplit("-", 1)[1]) + 1)

    def test_request_rejects_short_description(self) -> None:
        with self.assertRaises(ValidationError):
            self._create("Гудит")

    def test_request_rejects_past_date(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create_request(
                self.client_id,
                self.equipment_id,
                "Машина не сливает воду и гудит при отжиме",
                Priority.NORMAL,
                (date.today() - timedelta(days=1)).isoformat(),
            )

    def test_request_rejects_foreign_equipment(self) -> None:
        other_client = self.service.add_client("Сидоров Сидор", "+7 (902) 300-40-50")
        with self.assertRaises(ValidationError):
            self.service.create_request(
                other_client, self.equipment_id,
                "Машина не сливает воду и гудит при отжиме",
            )

    def test_assign_master_moves_request_to_accepted(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        request = self.service.get_request(request_id)
        self.assertEqual(request.status, RequestStatus.ACCEPTED)
        self.assertEqual(request.master_id, self.master_id)

    def test_assign_inactive_master_rejected(self) -> None:
        master = self.service.masters.get(self.master_id)
        master.active = False
        self.service.masters.update(master)
        with self.assertRaises(ValidationError):
            self.service.assign_master(self._create(), self.master_id)

    def test_assign_unknown_master_rejected(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.assign_master(self._create(), 999)

    def test_new_request_cannot_be_done(self) -> None:
        with self.assertRaises(TransitionError):
            self.service.change_status(self._create(), RequestStatus.DONE)

    def test_done_requires_work(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
        with self.assertRaises(ValidationError):
            self.service.change_status(request_id, RequestStatus.DONE)

    def test_full_lifecycle_and_history(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
        self.service.change_status(request_id, RequestStatus.DONE, "Работа выполнена")
        self.service.close_request(request_id, "Оплачено")
        request = self.service.get_request(request_id)
        self.assertEqual(request.status, RequestStatus.CLOSED)
        self.assertEqual(request.cost, 900)
        self.assertIsNotNone(request.completed_at)
        self.assertEqual(len(self.service.history(request_id)), 4)

    def test_same_status_rejected(self) -> None:
        request_id = self._create()
        with self.assertRaises(TransitionError):
            self.service.change_status(request_id, RequestStatus.NEW)

    # ---------- работы ----------

    def test_add_work_recalculates_cost(self) -> None:
        request_id = self._create()
        self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.add_work(request_id, "Замена насоса", 1.5, 3600)
        self.assertEqual(self.service.get_request(request_id).cost, 4500)

    def test_remove_work_recalculates_cost(self) -> None:
        request_id = self._create()
        work_id = self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.add_work(request_id, "Замена насоса", 1.5, 3600)
        self.service.remove_work(request_id, work_id)
        self.assertEqual(self.service.get_request(request_id).cost, 3600)

    def test_work_rejects_negative_hours(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_work(self._create(), "Диагностика", -1, 900)

    def test_work_rejects_negative_price(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.add_work(self._create(), "Диагностика", 1, -10)

    def test_closed_request_cannot_be_changed(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
        self.service.change_status(request_id, RequestStatus.DONE)
        self.service.close_request(request_id)
        with self.assertRaises(ValidationError):
            self.service.add_work(request_id, "Ещё работа", 1, 1000)

    # ---------- выборки и отчёты ----------

    def test_search_by_text_and_status(self) -> None:
        self._create("Не сливает воду, на дне лужа")
        self._create("Сильная вибрация при отжиме")
        self.assertEqual(len(self.service.search("вибрация")), 1)
        self.assertEqual(len(self.service.search(status=RequestStatus.NEW)), 2)

    def test_overdue_detection(self) -> None:
        request_id = self._create()
        self.db.execute(
            "UPDATE requests SET planned_date = ? WHERE id = ?",
            ((date.today() - timedelta(days=1)).isoformat(), request_id),
        )
        self.db.commit()
        overdue = self.service.overdue()
        self.assertEqual(len(overdue), 1)
        self.assertTrue(overdue[0].overdue)

    def test_revenue_period(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
        self.service.change_status(request_id, RequestStatus.DONE)
        today = date.today().isoformat()
        self.assertEqual(self.service.revenue(today, today), 900)

    def test_revenue_rejects_reversed_period(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.revenue("2026-12-31", "2026-01-01")

    def test_dashboard_counts(self) -> None:
        self._create()
        dashboard = self.service.dashboard()
        self.assertEqual(dashboard["total"], 1)
        self.assertEqual(dashboard["active"], 1)
        self.assertEqual(dashboard["statuses"]["Новая"], 1)

    def test_master_workload(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        row = next(item for item in self.service.master_workload()
                   if item["master"] == "Петров Пётр Петрович")
        self.assertEqual(row["total"], 1)
        self.assertEqual(row["active"], 1)


if __name__ == "__main__":
    unittest.main()
