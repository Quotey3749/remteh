"""Сценарные (интеграционные) тесты полного цикла работы сервисного центра.

Каждый тест проходит путь пользователя целиком: от создания клиента и
оборудования до закрытия заявки, отчётов и экспорта. В отличие от модульных
тестов здесь проверяется совместная работа сервиса, репозиториев и SQLite.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from remteh.db import Database
from remteh.export import export_requests_csv
from remteh.models import Priority, RequestStatus
from remteh.service import RequestService, TransitionError, ValidationError


class ScenarioTestCase(unittest.TestCase):
    """Сквозные сценарии работы сервисного центра."""

    def setUp(self) -> None:
        self.db = Database(":memory:")
        self.service = RequestService(self.db)
        self.client_id = self.service.add_client(
            "Смирнова Анна Петровна", "+7 (902) 111-22-33", "anna@example.ru", "Волгоград"
        )
        self.equipment_id = self.service.add_equipment(
            self.client_id, "Стиральная машина", "Bosch", "Serie 6", "SC-1001"
        )
        self.master_id = self.service.add_master(
            "Ковалёв Сергей Иванович", "Стиральные машины", "+7 (902) 444-55-66"
        )
        self.master2_id = self.service.add_master(
            "Белова Ольга Викторовна", "Встраиваемая техника", "+7 (902) 777-88-99"
        )

    def tearDown(self) -> None:
        self.db.close()

    def _create(self, description: str = "Не сливает воду, при отжиме гудит") -> int:
        return self.service.create_request(
            self.client_id,
            self.equipment_id,
            description,
            Priority.NORMAL,
            (date.today() + timedelta(days=2)).isoformat(),
        )

    def test_scenario_full_repair_cycle(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
        self.service.add_work(request_id, "Замена насоса", 1.5, 3600)
        self.service.change_status(request_id, RequestStatus.DONE, "Работа выполнена")
        self.service.close_request(request_id, "Оплачено")

        request = self.service.get_request(request_id)
        self.assertEqual(request.status, RequestStatus.CLOSED)
        self.assertEqual(request.cost, 4500)
        self.assertIsNotNone(request.completed_at)
        self.assertEqual(len(self.service.history(request_id)), 4)
        self.assertEqual(self.service.dashboard()["total"], 1)
        self.assertEqual(self.service.revenue(date.today().isoformat(),
                                              date.today().isoformat()), 4500)

    def test_scenario_cancellation_before_acceptance(self) -> None:
        request_id = self._create("Клиент передумал ремонтировать технику")
        self.service.change_status(request_id, RequestStatus.CANCELLED, "Отказ клиента")

        request = self.service.get_request(request_id)
        self.assertEqual(request.status, RequestStatus.CANCELLED)
        self.assertEqual(self.service.dashboard()["active"], 0)
        self.assertEqual(len(self.service.overdue()), 0)
        self.assertEqual(len(self.service.history(request_id)), 1)
        with self.assertRaises(ValidationError):
            self.service.add_work(request_id, "Диагностика", 1, 500)

    def test_scenario_overdue_request_in_dashboard(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        self.db.execute(
            "UPDATE requests SET planned_date = ? WHERE id = ?",
            ((date.today() - timedelta(days=2)).isoformat(), request_id),
        )
        self.db.commit()

        overdue = self.service.overdue()
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0].id, request_id)
        self.assertTrue(overdue[0].overdue)
        self.assertEqual(self.service.dashboard()["overdue"], 1)

    def test_scenario_master_workload_and_reassignment(self) -> None:
        first = self._create("Первый ремонт: шум при отжиме")
        second = self._create("Второй ремонт: не открывается дверца")
        third = self._create("Третий ремонт: ошибка E18 на дисплее")
        self.service.assign_master(first, self.master_id)
        self.service.assign_master(second, self.master_id)
        self.service.assign_master(third, self.master2_id)
        self.service.assign_master(second, self.master2_id)

        load = {row["master"]: (row["total"], row["active"])
                for row in self.service.master_workload()}
        self.assertEqual(load["Ковалёв Сергей Иванович"], (1, 1))
        self.assertEqual(load["Белова Ольга Викторовна"], (2, 2))

    def test_scenario_search_and_csv_export(self) -> None:
        first = self._create("Не сливает воду, на дне лужа")
        self._create("Сильная вибрация при отжиме")
        self.service.assign_master(first, self.master_id)

        self.assertEqual(len(self.service.search("вибрация")), 1)
        self.assertEqual(len(self.service.search(status=RequestStatus.ACCEPTED)), 1)
        views = self.service.search()
        self.assertEqual(len(views), 2)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "scenario.csv"
            export_requests_csv(views, target)
            with target.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream, delimiter=";"))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], "Номер")
        self.assertTrue(any(row[1] == "Смирнова Анна Петровна" for row in rows[1:]))

    def test_scenario_waiting_for_parts(self) -> None:
        request_id = self._create()
        self.service.assign_master(request_id, self.master_id)
        self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
        self.service.change_status(request_id, RequestStatus.WAITING_PARTS, "Нет насоса")
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS, "Деталь получена")
        self.service.change_status(request_id, RequestStatus.DONE)
        self.service.close_request(request_id)

        self.assertEqual(self.service.get_request(request_id).status, RequestStatus.CLOSED)
        self.assertEqual(len(self.service.history(request_id)), 6)

    def test_scenario_revenue_and_dashboard(self) -> None:
        first = self._create()
        second = self._create("Не нагревает воду, ошибка датчика")
        for request_id, price in ((first, 1200), (second, 2300)):
            self.service.assign_master(request_id, self.master_id)
            self.service.add_work(request_id, "Ремонт", 1, price)
            self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
            self.service.change_status(request_id, RequestStatus.DONE)
            self.service.close_request(request_id)

        today = date.today().isoformat()
        self.assertEqual(self.service.revenue(today, today), 3500)
        dashboard = self.service.dashboard()
        self.assertEqual(dashboard["total"], 2)
        self.assertEqual(dashboard["revenue"], 3500)
        self.assertEqual(dashboard["statuses"]["Закрыта"], 2)

    def test_scenario_validation_guards(self) -> None:
        request_id = self._create()
        with self.assertRaises(TransitionError):
            self.service.change_status(request_id, RequestStatus.DONE)

        self.service.assign_master(request_id, self.master_id)
        self.service.change_status(request_id, RequestStatus.IN_PROGRESS)
        with self.assertRaises(ValidationError):
            self.service.change_status(request_id, RequestStatus.DONE)

        self.service.add_work(request_id, "Диагностика", 0.5, 900)
        self.service.change_status(request_id, RequestStatus.DONE)
        self.service.close_request(request_id)
        with self.assertRaises(ValidationError):
            self.service.assign_master(request_id, self.master2_id)


if __name__ == "__main__":
    unittest.main()
