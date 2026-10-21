"""Тесты доменных моделей: статусы, приоритеты, просрочка."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from remteh.models import (
    Priority,
    RequestStatus,
    ServiceRequest,
    TRANSITIONS,
)


class ModelsTestCase(unittest.TestCase):
    def test_status_labels(self) -> None:
        self.assertEqual(RequestStatus.NEW.label, "Новая")
        self.assertEqual(RequestStatus.WAITING_PARTS.label, "Ожидает детали")

    def test_all_statuses_have_transition_rule(self) -> None:
        self.assertEqual(set(TRANSITIONS), set(RequestStatus))

    def test_terminal_statuses_have_no_transitions(self) -> None:
        self.assertEqual(TRANSITIONS[RequestStatus.CLOSED], ())
        self.assertEqual(TRANSITIONS[RequestStatus.CANCELLED], ())

    def test_priority_labels(self) -> None:
        self.assertEqual(Priority.HIGH.label, "Высокий")
        self.assertEqual(Priority.NORMAL.label, "Обычный")

    def test_overdue_for_active_request(self) -> None:
        request = ServiceRequest(
            None, "З-2026-0001", 1, 1, "Не сливает воду", status=RequestStatus.IN_PROGRESS,
            planned_date=(date.today() - timedelta(days=1)).isoformat(),
        )
        self.assertTrue(request.is_overdue())

    def test_not_overdue_for_done_request(self) -> None:
        request = ServiceRequest(
            None, "З-2026-0001", 1, 1, "Не сливает воду", status=RequestStatus.DONE,
            planned_date=(date.today() - timedelta(days=1)).isoformat(),
        )
        self.assertFalse(request.is_overdue())

    def test_not_overdue_without_planned_date(self) -> None:
        request = ServiceRequest(None, "З-2026-0001", 1, 1, "Не сливает воду")
        self.assertFalse(request.is_overdue())


if __name__ == "__main__":
    unittest.main()
