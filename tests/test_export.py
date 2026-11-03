"""Тесты экспорта журнала заявок в CSV."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from remteh.db import Database
from remteh.export import export_requests_csv
from remteh.models import Priority, RequestStatus, RequestView
from remteh.seed import seed_demo
from remteh.service import RequestService


class ExportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Database(":memory:")
        seed_demo(self.db)
        self.service = RequestService(self.db)
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.db.close()
        self.tmp.cleanup()

    def test_export_writes_header_and_rows(self) -> None:
        target = Path(self.tmp.name) / "requests.csv"
        views = self.service.search()
        export_requests_csv(views, target)
        text = target.read_text(encoding="utf-8-sig")
        lines = text.splitlines()
        self.assertEqual(len(lines), len(views) + 1)
        self.assertIn("Номер;Клиент", lines[0])
        self.assertIn("З-2026-0001", text)

    def test_export_single_view(self) -> None:
        target = Path(self.tmp.name) / "one.csv"
        view = RequestView(
            id=1,
            number="З-2026-0099",
            client_name="Иванов Иван",
            phone="+7 (902) 000-00-00",
            equipment="Чайник Bosch",
            master_name="",
            status=RequestStatus.NEW,
            priority=Priority.HIGH,
            created_at="2026-11-01T10:00:00",
            planned_date=None,
            cost=0.0,
            description="Не включается",
        )
        export_requests_csv([view], target)
        text = target.read_text(encoding="utf-8-sig")
        self.assertIn("З-2026-0099", text)
        self.assertIn("Не назначен", text)
        self.assertIn("да" if view.overdue else "нет", text)


if __name__ == "__main__":
    unittest.main()
