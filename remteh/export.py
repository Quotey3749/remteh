"""Экспорт журнала заявок в CSV для обмена с другими системами."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import RequestView


def export_requests_csv(views: list[RequestView], path: str | Path) -> Path:
    """Сохраняет выборку заявок в CSV с разделителем «;» и BOM для Excel."""
    target = Path(path)
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow([
            "Номер",
            "Клиент",
            "Телефон",
            "Оборудование",
            "Мастер",
            "Статус",
            "Приоритет",
            "Создана",
            "Плановая дата",
            "Стоимость, руб.",
            "Просрочена",
        ])
        for view in views:
            writer.writerow([
                view.number,
                view.client_name,
                view.phone,
                view.equipment,
                view.master_title,
                view.status.label,
                view.priority.label,
                view.created_at[:10],
                view.planned_date or "",
                f"{view.cost:.2f}".replace(".", ","),
                "да" if view.overdue else "нет",
            ])
    return target
