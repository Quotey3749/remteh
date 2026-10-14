"""Графический интерфейс информационной системы сервисного центра «РемТех»."""

from __future__ import annotations

import argparse
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .db import Database
from .models import (
    Client,
    Equipment,
    Master,
    Priority,
    RequestStatus,
    RequestView,
    TRANSITIONS,
)
from .seed import seed_demo
from .service import NotFoundError, RequestService, ValidationError

BG = "#eef2f5"
CARD = "#ffffff"
NAVY = "#16324f"
NAVY_LIGHT = "#1f4368"
GREEN = "#1f7a5c"
GREEN_LIGHT = "#2d9c72"
MUTED = "#6b7c8f"
RED = "#c0392b"
BORDER = "#d7e0e8"
FONT = "DejaVu Sans"
MONO = "DejaVu Sans Mono"

STATUS_COLORS = {
    RequestStatus.NEW: "#2f80ed",
    RequestStatus.ACCEPTED: "#8e6bd8",
    RequestStatus.IN_PROGRESS: "#d68910",
    RequestStatus.WAITING_PARTS: "#c0392b",
    RequestStatus.DONE: "#1f7a5c",
    RequestStatus.CLOSED: "#6b7c8f",
    RequestStatus.CANCELLED: "#95a5a6",
}


def center(window: tk.Toplevel, parent: tk.Misc, width: int, height: int) -> None:
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 3
    window.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")


def make_tree(
    parent: tk.Misc,
    columns: tuple[str, ...],
    headings: tuple[str, ...],
    widths: tuple[int, ...],
    height: int = 16,
) -> tuple[ttk.Treeview, tk.Frame]:
    frame = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
    for column, heading, width in zip(columns, headings, widths):
        tree.heading(column, text=heading)
        tree.column(column, width=width, minwidth=max(width // 2, 50), anchor="w")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return tree, frame


class StatCard(tk.Frame):
    def __init__(self, parent: tk.Misc, title: str, accent: str = GREEN) -> None:
        super().__init__(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tk.Frame(self, bg=accent, height=4).pack(fill="x")
        self.title = tk.Label(self, text=title, bg=CARD, fg=MUTED, font=(FONT, 9))
        self.title.pack(anchor="w", padx=14, pady=(9, 0))
        self.value = tk.Label(self, text="0", bg=CARD, fg=NAVY, font=(FONT, 20, "bold"))
        self.value.pack(anchor="w", padx=14, pady=(0, 9))

    def set(self, value: str | int) -> None:
        self.value.configure(text=str(value))


class RequestDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp") -> None:
        super().__init__(parent)
        self.app = app
        self.title("Новая заявка")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        center(self, parent, 560, 520)
        self.grab_set()

        tk.Label(self, text="Регистрация заявки", bg=CARD, fg=NAVY,
                 font=(FONT, 16, "bold")).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(self, text="Заполните данные клиента и описание неисправности",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=24, pady=(0, 14))

        body = tk.Frame(self, bg=CARD)
        body.pack(fill="both", expand=True, padx=24)
        body.columnconfigure(1, weight=1)

        self.clients = app.service.clients.list()
        client_names = [client.full_name for client in self.clients]
        self.client_var = tk.StringVar(value=client_names[0] if client_names else "")
        self.equipment_var = tk.StringVar()
        self.priority_var = tk.StringVar(value=Priority.NORMAL.label)
        self.date_var = tk.StringVar(value=(date.today() + timedelta(days=3)).isoformat())

        self._label(body, "Клиент", 0)
        self.client_combo = ttk.Combobox(body, textvariable=self.client_var, values=client_names,
                                         state="readonly", width=38)
        self.client_combo.grid(row=0, column=1, sticky="ew", pady=5)
        self.client_combo.bind("<<ComboboxSelected>>", lambda _: self._load_equipment())

        self._label(body, "Оборудование", 1)
        self.equipment_combo = ttk.Combobox(body, textvariable=self.equipment_var,
                                            state="readonly", width=38)
        self.equipment_combo.grid(row=1, column=1, sticky="ew", pady=5)

        self._label(body, "Приоритет", 2)
        ttk.Combobox(body, textvariable=self.priority_var,
                     values=[priority.label for priority in Priority],
                     state="readonly", width=20).grid(row=2, column=1, sticky="w", pady=5)

        self._label(body, "Плановая дата", 3)
        tk.Entry(body, textvariable=self.date_var, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1).grid(
            row=3, column=1, sticky="w", ipady=5, pady=5, padx=1)

        self._label(body, "Неисправность", 4, anchor="nw")
        self.description = tk.Text(body, height=7, wrap="word", bg="#f7f9fb", relief="flat",
                                   highlightbackground=BORDER, highlightthickness=1,
                                   font=(FONT, 10), padx=8, pady=6)
        self.description.grid(row=4, column=1, sticky="ew", pady=5)
        self.description.insert(
            "1.0", "Опишите, что происходит с техникой и когда появилась проблема"
        )

        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", padx=24, pady=(8, 20))
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Создать заявку", style="Accent.TButton",
                   command=self._save).pack(side="right")
        self._load_equipment()
        self.client_combo.focus_set()

    def _label(self, parent: tk.Misc, text: str, row: int, anchor: str = "w") -> None:
        tk.Label(
            parent, text=text, bg=CARD, fg=NAVY, font=(FONT, 9, "bold"), anchor=anchor
        ).grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=(10, 5))

    def _load_equipment(self) -> None:
        client = next((c for c in self.clients if c.full_name == self.client_var.get()), None)
        self.equipment = (
            self.app.service.equipment.list_by_client(client.id)
            if client and client.id else []
        )
        titles = [f"{item.kind} {item.brand} {item.model}" for item in self.equipment]
        self.equipment_combo.configure(values=titles)
        self.equipment_var.set(titles[0] if titles else "")

    def _save(self) -> None:
        client = next((c for c in self.clients if c.full_name == self.client_var.get()), None)
        equipment = next(
            (item for item, title in zip(
                self.equipment,
                [f"{i.kind} {i.brand} {i.model}" for i in self.equipment],
            ) if title == self.equipment_var.get()),
            None,
        )
        if client is None or client.id is None:
            messagebox.showerror("Проверка данных", "Выберите клиента", parent=self)
            return
        if equipment is None or equipment.id is None:
            messagebox.showerror(
                "Проверка данных",
                "У клиента нет оборудования. Добавьте его в справочнике.",
                parent=self,
            )
            return
        priority = next(p for p in Priority if p.label == self.priority_var.get())
        try:
            self.app.service.create_request(
                client.id,
                equipment.id,
                self.description.get("1.0", "end").strip(),
                priority,
                self.date_var.get().strip(),
            )
        except (ValidationError, NotFoundError) as exc:
            messagebox.showerror("Проверка данных", str(exc), parent=self)
            return
        self.app.refresh_all()
        self.destroy()


class AssignDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp", request_id: int) -> None:
        super().__init__(parent)
        self.app = app
        self.request_id = request_id
        self.title("Назначение мастера")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        center(self, parent, 480, 300)
        self.grab_set()
        view = app.service.get_view(request_id)
        tk.Label(self, text="Назначение мастера", bg=CARD, fg=NAVY,
                 font=(FONT, 15, "bold")).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(self, text=f"{view.number} · {view.equipment}" if view else "",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=24, pady=(0, 14))
        self.masters = app.service.masters.list(active_only=True)
        names = [f"{m.full_name} — {m.specialization}" for m in self.masters]
        self.var = tk.StringVar(value=names[0] if names else "")
        tk.Label(self, text="Мастер", bg=CARD, fg=NAVY, font=(FONT, 9, "bold")).pack(
            anchor="w", padx=24)
        ttk.Combobox(self, textvariable=self.var, values=names, state="readonly",
                     width=48).pack(fill="x", padx=24, pady=(6, 6))
        load = " · ".join(
            f"{row['master'].split()[0]}: {row['active']}" for row in app.service.master_workload()
        )
        tk.Label(self, text="Активные заявки: " + load, bg=CARD, fg=MUTED,
                 font=(FONT, 8), wraplength=420, justify="left").pack(anchor="w", padx=24)
        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", padx=24, pady=18, side="bottom")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Назначить", style="Accent.TButton",
                   command=self._save).pack(side="right")

    def _save(self) -> None:
        chosen = next((m for m in self.masters
                       if f"{m.full_name} — {m.specialization}" == self.var.get()), None)
        if chosen is None or chosen.id is None:
            return
        try:
            self.app.service.assign_master(self.request_id, chosen.id)
        except (ValidationError, NotFoundError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self.app.refresh_all()
        self.destroy()


class StatusDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp", request_id: int) -> None:
        super().__init__(parent)
        self.app = app
        self.request_id = request_id
        self.request = app.service.get_request(request_id)
        self.title("Изменение статуса")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        center(self, parent, 460, 300)
        self.grab_set()
        tk.Label(self, text="Изменение статуса", bg=CARD, fg=NAVY,
                 font=(FONT, 15, "bold")).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(self, text=f"{self.request.number} · сейчас: {self.request.status.label}",
                 bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=24, pady=(0, 14))
        allowed = TRANSITIONS[self.request.status]
        self.var = tk.StringVar(value=allowed[0].label if allowed else "")
        tk.Label(self, text="Новый статус", bg=CARD, fg=NAVY, font=(FONT, 9, "bold")).pack(
            anchor="w", padx=24)
        ttk.Combobox(self, textvariable=self.var, values=[s.label for s in allowed],
                     state="readonly", width=32).pack(fill="x", padx=24, pady=(6, 8))
        tk.Label(self, text="Комментарий", bg=CARD, fg=NAVY, font=(FONT, 9, "bold")).pack(
            anchor="w", padx=24)
        self.comment = tk.Entry(self, bg="#f7f9fb", relief="flat",
                                highlightbackground=BORDER, highlightthickness=1)
        self.comment.pack(fill="x", padx=24, pady=(6, 8), ipady=5)
        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", padx=24, pady=18, side="bottom")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Применить", style="Accent.TButton",
                   command=self._save).pack(side="right")

    def _save(self) -> None:
        target = next(
            (s for s in TRANSITIONS[self.request.status] if s.label == self.var.get()),
            None,
        )
        if target is None:
            return
        try:
            self.app.service.change_status(self.request_id, target, self.comment.get())
        except (ValidationError, NotFoundError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self.app.refresh_all()
        self.destroy()


class WorksDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp", request_id: int) -> None:
        super().__init__(parent)
        self.app = app
        self.request_id = request_id
        request = app.service.get_request(request_id)
        self.title("Работы по заявке")
        self.configure(bg=CARD)
        self.transient(parent)
        center(self, parent, 680, 500)
        self.grab_set()
        tk.Label(self, text=f"Работы по заявке {request.number}", bg=CARD, fg=NAVY,
                 font=(FONT, 15, "bold")).pack(anchor="w", padx=24, pady=(20, 2))
        tk.Label(self, text=request.description, bg=CARD, fg=MUTED, font=(FONT, 9),
                 wraplength=620, justify="left").pack(anchor="w", padx=24, pady=(0, 10))
        self.total = tk.Label(self, text="", bg=CARD, fg=GREEN, font=(FONT, 11, "bold"))
        self.total.pack(anchor="e", padx=24)
        self.tree, frame = make_tree(
            self, ("title", "hours", "price"), ("Работа", "Часы", "Стоимость, руб."),
            (360, 90, 140), height=8,
        )
        frame.pack(fill="both", expand=True, padx=24, pady=8)
        form = tk.Frame(self, bg=CARD)
        form.pack(fill="x", padx=24, pady=(0, 4))
        self.title_var = tk.StringVar()
        self.hours_var = tk.StringVar(value="1")
        self.price_var = tk.StringVar()
        tk.Entry(form, textvariable=self.title_var, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1,
                 width=34).grid(row=0, column=0, padx=(0, 6), ipady=4)
        tk.Entry(form, textvariable=self.hours_var, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1,
                 width=6).grid(row=0, column=1, padx=(0, 6), ipady=4)
        tk.Entry(form, textvariable=self.price_var, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1,
                 width=10).grid(row=0, column=2, padx=(0, 6), ipady=4)
        ttk.Button(form, text="Добавить", style="Accent.TButton",
                   command=self._add).grid(row=0, column=3, padx=(4, 0))
        ttk.Button(form, text="Удалить", command=self._remove).grid(row=0, column=4, padx=(6, 0))
        tk.Label(form, text="Название работы / часы / цена", bg=CARD, fg=MUTED,
                 font=(FONT, 8)).grid(row=1, column=0, sticky="w", pady=(3, 10))
        self.refresh()

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for work in self.app.service.works(self.request_id):
            price = f"{work.price:,.2f}".replace(",", " ").replace(".", ",")
            self.tree.insert(
                "", "end", iid=str(work.id),
                values=(work.title, f"{work.hours:g}", price),
            )
        total = sum(work.price for work in self.app.service.works(self.request_id))
        total_text = f"{total:,.2f}".replace(",", " ").replace(".", ",")
        self.total.configure(text=f"Итого: {total_text} руб.")

    def _add(self) -> None:
        try:
            self.app.service.add_work(
                self.request_id,
                self.title_var.get(),
                float(self.hours_var.get().replace(",", ".")),
                float(self.price_var.get().replace(",", ".")),
            )
        except (ValueError, ValidationError, NotFoundError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self.title_var.set("")
        self.price_var.set("")
        self.refresh()
        self.app.refresh_all()

    def _remove(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        try:
            self.app.service.remove_work(self.request_id, int(selected[0]))
        except (ValidationError, NotFoundError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self.refresh()
        self.app.refresh_all()


class HistoryDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp", request_id: int) -> None:
        super().__init__(parent)
        self.title("История заявки")
        self.configure(bg=CARD)
        self.transient(parent)
        center(self, parent, 640, 420)
        self.grab_set()
        request = app.service.get_request(request_id)
        tk.Label(self, text=f"История заявки {request.number}", bg=CARD, fg=NAVY,
                 font=(FONT, 15, "bold")).pack(anchor="w", padx=24, pady=(20, 10))
        tree, frame = make_tree(
            self, ("date", "old", "new", "comment"),
            ("Дата", "Было", "Стало", "Комментарий"), (150, 120, 120, 210), height=10,
        )
        frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        for change in app.service.history(request_id):
            old = RequestStatus(change.old_status).label
            new = RequestStatus(change.new_status).label
            tree.insert(
                "", "end",
                values=(change.changed_at.replace("T", " "), old, new, change.comment),
            )
        if not tree.get_children():
            tree.insert("", "end", values=("—", "—", "—", "История пуста"))


class RequestsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "RemTechApp") -> None:
        super().__init__(parent, style="App.TFrame")
        self.app = app
        self.cards = {}
        cards = tk.Frame(self, bg=BG)
        cards.pack(fill="x", padx=14, pady=(12, 8))
        for index, (key, title, color) in enumerate([
            ("total", "Всего заявок", NAVY), ("active", "В работе", GREEN),
            ("overdue", "Просрочено", RED),
        ]):
            card = StatCard(cards, title, color)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
            cards.columnconfigure(index, weight=1)
            self.cards[key] = card

        toolbar = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=14, pady=(0, 8))
        self.search_var = tk.StringVar()
        search = tk.Entry(toolbar, textvariable=self.search_var, bg="#f7f9fb", relief="flat",
                          highlightbackground=BORDER, highlightthickness=1, width=30)
        search.pack(side="left", padx=(12, 8), pady=10, ipady=5)
        search.insert(0, "")
        tk.Label(toolbar, text="Поиск", bg=CARD, fg=MUTED, font=(FONT, 8)).pack(side="left")
        self.status_var = tk.StringVar(value="Все статусы")
        self.status_combo = ttk.Combobox(
            toolbar, textvariable=self.status_var, state="readonly", width=17,
            values=["Все статусы"] + [status.label for status in RequestStatus],
        )
        self.status_combo.pack(side="left", padx=(16, 8), pady=10)
        self.master_var = tk.StringVar(value="Все мастера")
        self.master_combo = ttk.Combobox(toolbar, textvariable=self.master_var,
                                         state="readonly", width=24)
        self.master_combo.pack(side="left", padx=(0, 8), pady=10)
        ttk.Button(toolbar, text="Найти", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Сбросить", command=self._reset).pack(side="left", padx=4)
        ttk.Button(toolbar, text="+ Новая заявка", style="Accent.TButton",
                   command=self._create).pack(side="right", padx=12)

        self.tree, frame = make_tree(
            self,
            ("number", "client", "equipment", "master", "status", "priority", "plan", "cost"),
            ("Номер", "Клиент", "Оборудование", "Мастер", "Статус", "Приоритет",
             "План", "Стоимость"),
            (92, 190, 225, 165, 115, 80, 88, 88),
            height=15,
        )
        self.tree.tag_configure("overdue", background="#fdecea")
        self.tree.tag_configure("closed", foreground="#8a9aa8")
        self.tree.bind("<Double-1>", lambda _: self._works())
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._update_buttons())

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=14, pady=(0, 12))
        self.selected_label = tk.Label(actions, text="Заявка не выбрана", bg=BG, fg=MUTED,
                                       font=(FONT, 9))
        self.selected_label.pack(side="left")
        for text, command in [
            ("Работы", self._works), ("История", self._history), ("Статус", self._status),
            ("Назначить", self._assign),
        ]:
            ttk.Button(actions, text=text, command=command).pack(side="right", padx=(6, 0))
        frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.refresh()

    def _reset(self) -> None:
        self.search_var.set("")
        self.status_var.set("Все статусы")
        self.master_var.set("Все мастера")
        self.refresh()

    def refresh(self) -> None:
        masters = self.app.service.masters.list()
        self.master_combo.configure(values=["Все мастера"] + [m.full_name for m in masters])
        status = next((s for s in RequestStatus if s.label == self.status_var.get()), None)
        master_id = next((m.id for m in masters if m.full_name == self.master_var.get()), None)
        views = self.app.service.search(self.search_var.get(), status, master_id)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for view in views:
            tags = []
            if view.overdue:
                tags.append("overdue")
            elif view.status in (RequestStatus.CLOSED, RequestStatus.CANCELLED):
                tags.append("closed")
            self.tree.insert(
                "", "end", iid=str(view.id), tags=tuple(tags),
                values=(
                    view.number, view.client_name, view.equipment, view.master_title,
                    view.status.label, view.priority.label,
                    view.planned_date or "—", f"{view.cost:,.0f}".replace(",", " "),
                ),
            )
        dashboard = self.app.service.dashboard()
        self.cards["total"].set(dashboard["total"])
        self.cards["active"].set(dashboard["active"])
        self.cards["overdue"].set(dashboard["overdue"])
        self._update_buttons()

    def _selected(self) -> int | None:
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def _update_buttons(self) -> None:
        request_id = self._selected()
        if request_id is None:
            self.selected_label.configure(text="Заявка не выбрана")
            return
        view = self.app.service.get_view(request_id)
        if view:
            self.selected_label.configure(
                text=f"Выбрана {view.number} · {view.client_name} · {view.status.label}")

    def _create(self) -> None:
        RequestDialog(self, self.app)

    def _assign(self) -> None:
        request_id = self._selected()
        if request_id is None:
            messagebox.showinfo("Заявка", "Выберите заявку в журнале", parent=self)
            return
        AssignDialog(self, self.app, request_id)

    def _status(self) -> None:
        request_id = self._selected()
        if request_id is None:
            messagebox.showinfo("Заявка", "Выберите заявку в журнале", parent=self)
            return
        StatusDialog(self, self.app, request_id)

    def _works(self) -> None:
        request_id = self._selected()
        if request_id is None:
            messagebox.showinfo("Заявка", "Выберите заявку в журнале", parent=self)
            return
        WorksDialog(self, self.app, request_id)

    def _history(self) -> None:
        request_id = self._selected()
        if request_id is None:
            messagebox.showinfo("Заявка", "Выберите заявку в журнале", parent=self)
            return
        HistoryDialog(self, self.app, request_id)


class ClientDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp", client: Client | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.client = client
        self.title("Клиент")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        center(self, parent, 500, 380)
        self.grab_set()
        tk.Label(self, text="Редактирование клиента" if client else "Новый клиент",
                 bg=CARD, fg=NAVY, font=(FONT, 15, "bold")).pack(anchor="w", padx=24, pady=(20, 14))
        body = tk.Frame(self, bg=CARD)
        body.pack(fill="both", expand=True, padx=24)
        body.columnconfigure(1, weight=1)
        self.vars = {
            "full_name": tk.StringVar(value=client.full_name if client else ""),
            "phone": tk.StringVar(value=client.phone if client else "+7 ("),
            "email": tk.StringVar(value=client.email if client else ""),
            "address": tk.StringVar(value=client.address if client else "Волгоград, "),
        }
        for row, (key, label) in enumerate([
            ("full_name", "ФИО"), ("phone", "Телефон"), ("email", "E-mail"), ("address", "Адрес"),
        ]):
            tk.Label(body, text=label, bg=CARD, fg=NAVY, font=(FONT, 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 14), pady=8)
            tk.Entry(body, textvariable=self.vars[key], bg="#f7f9fb", relief="flat",
                     highlightbackground=BORDER, highlightthickness=1).grid(
                row=row, column=1, sticky="ew", pady=8, ipady=4)
        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", padx=24, pady=20)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton",
                   command=self._save).pack(side="right")

    def _save(self) -> None:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        try:
            if self.client is None:
                self.app.service.add_client(**values)
            else:
                self.client.full_name = values["full_name"]
                self.client.phone = values["phone"]
                self.client.email = values["email"]
                self.client.address = values["address"]
                self.app.service.update_client(self.client)
        except (ValidationError, NotFoundError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self.app.refresh_all()
        self.destroy()


class ClientsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "RemTechApp") -> None:
        super().__init__(parent, style="App.TFrame")
        self.app = app
        toolbar = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=14, pady=12)
        tk.Label(toolbar, text="Клиенты", bg=CARD, fg=NAVY,
                 font=(FONT, 13, "bold")).pack(side="left", padx=12, pady=10)
        ttk.Button(toolbar, text="+ Добавить", style="Accent.TButton",
                   command=self._add).pack(side="right", padx=12)
        ttk.Button(toolbar, text="Изменить", command=self._edit).pack(side="right", padx=4)
        self.search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self.search_var, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1, width=26).pack(
            side="right", padx=(8, 12), ipady=4)
        tooltip = tk.Label(toolbar, text="поиск", bg=CARD, fg=MUTED, font=(FONT, 8))
        tooltip.pack(side="right")
        self.tree, frame = make_tree(
            self, ("name", "phone", "email", "address"),
            ("ФИО", "Телефон", "E-mail", "Адрес"), (260, 150, 210, 330), height=18,
        )
        frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.tree.bind("<Double-1>", lambda _: self._edit())
        self.refresh()

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        clients = self.app.service.clients.list(self.search_var.get())
        for client in clients:
            self.tree.insert("", "end", iid=str(client.id),
                             values=(client.full_name, client.phone, client.email, client.address))

    def _selected(self) -> Client | None:
        selected = self.tree.selection()
        if not selected:
            return None
        return self.app.service.clients.get(int(selected[0]))

    def _add(self) -> None:
        ClientDialog(self, self.app)

    def _edit(self) -> None:
        client = self._selected()
        if client is None:
            messagebox.showinfo("Клиент", "Выберите клиента", parent=self)
            return
        ClientDialog(self, self.app, client)


class EquipmentDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp", item: Equipment | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.item = item
        self.title("Оборудование")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        center(self, parent, 520, 430)
        self.grab_set()
        tk.Label(self, text="Редактирование оборудования" if item else "Новое оборудование",
                 bg=CARD, fg=NAVY, font=(FONT, 15, "bold")).pack(anchor="w", padx=24, pady=(20, 14))
        body = tk.Frame(self, bg=CARD)
        body.pack(fill="both", expand=True, padx=24)
        body.columnconfigure(1, weight=1)
        self.clients = app.service.clients.list()
        self.client_var = tk.StringVar(
            value=next((c.full_name for c in self.clients if item and c.id == item.client_id),
                       self.clients[0].full_name if self.clients else "")
        )
        self.vars = {
            "kind": tk.StringVar(value=item.kind if item else ""),
            "brand": tk.StringVar(value=item.brand if item else ""),
            "model": tk.StringVar(value=item.model if item else ""),
            "serial": tk.StringVar(value=item.serial if item else ""),
            "notes": tk.StringVar(value=item.notes if item else ""),
        }
        tk.Label(body, text="Клиент", bg=CARD, fg=NAVY, font=(FONT, 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 14), pady=7)
        ttk.Combobox(body, textvariable=self.client_var,
                     values=[c.full_name for c in self.clients], state="readonly").grid(
            row=0, column=1, sticky="ew", pady=7)
        for row, (key, label) in enumerate(
            [("kind", "Тип"), ("brand", "Производитель"), ("model", "Модель"),
             ("serial", "Серийный номер"), ("notes", "Примечание")], start=1
        ):
            tk.Label(body, text=label, bg=CARD, fg=NAVY, font=(FONT, 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 14), pady=7)
            tk.Entry(body, textvariable=self.vars[key], bg="#f7f9fb", relief="flat",
                     highlightbackground=BORDER, highlightthickness=1).grid(
                row=row, column=1, sticky="ew", pady=7, ipady=4)
        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", padx=24, pady=20)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton",
                   command=self._save).pack(side="right")

    def _save(self) -> None:
        client = next((c for c in self.clients if c.full_name == self.client_var.get()), None)
        if client is None or client.id is None:
            return
        values = {key: var.get().strip() for key, var in self.vars.items()}
        try:
            if self.item is None:
                self.app.service.add_equipment(client.id, **values)
            else:
                for key, value in values.items():
                    setattr(self.item, key, value)
                self.item.client_id = client.id
                self.app.service.update_equipment(self.item)
        except (ValidationError, NotFoundError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self.app.refresh_all()
        self.destroy()


class EquipmentTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "RemTechApp") -> None:
        super().__init__(parent, style="App.TFrame")
        self.app = app
        toolbar = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=14, pady=12)
        tk.Label(toolbar, text="Оборудование", bg=CARD, fg=NAVY,
                 font=(FONT, 13, "bold")).pack(side="left", padx=12, pady=10)
        ttk.Button(toolbar, text="+ Добавить", style="Accent.TButton",
                   command=self._add).pack(side="right", padx=12)
        ttk.Button(toolbar, text="Изменить", command=self._edit).pack(side="right", padx=4)
        self.search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self.search_var, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1, width=26).pack(
            side="right", padx=(8, 12), ipady=4)
        tk.Label(toolbar, text="поиск", bg=CARD, fg=MUTED, font=(FONT, 8)).pack(side="right")
        self.tree, frame = make_tree(
            self, ("client", "kind", "brand", "model", "serial"),
            ("Клиент", "Тип", "Производитель", "Модель", "Серийный номер"),
            (240, 190, 150, 210, 160), height=18,
        )
        frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.tree.bind("<Double-1>", lambda _: self._edit())
        self.refresh()

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        clients = {client.id: client.full_name for client in self.app.service.clients.list()}
        for item in self.app.service.equipment.list(self.search_var.get()):
            self.tree.insert("", "end", iid=str(item.id),
                             values=(clients.get(item.client_id, ""), item.kind, item.brand,
                                     item.model, item.serial))

    def _selected(self) -> Equipment | None:
        selected = self.tree.selection()
        return self.app.service.equipment.get(int(selected[0])) if selected else None

    def _add(self) -> None:
        EquipmentDialog(self, self.app)

    def _edit(self) -> None:
        item = self._selected()
        if item is None:
            messagebox.showinfo("Оборудование", "Выберите запись", parent=self)
            return
        EquipmentDialog(self, self.app, item)


class MasterDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, app: "RemTechApp", master: Master | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.master = master
        self.title("Мастер")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        center(self, parent, 500, 330)
        self.grab_set()
        tk.Label(self, text="Редактирование мастера" if master else "Новый мастер",
                 bg=CARD, fg=NAVY, font=(FONT, 15, "bold")).pack(anchor="w", padx=24, pady=(20, 14))
        body = tk.Frame(self, bg=CARD)
        body.pack(fill="both", expand=True, padx=24)
        body.columnconfigure(1, weight=1)
        self.vars = {
            "full_name": tk.StringVar(value=master.full_name if master else ""),
            "specialization": tk.StringVar(value=master.specialization if master else ""),
            "phone": tk.StringVar(value=master.phone if master else "+7 ("),
        }
        for row, (key, label) in enumerate([
            ("full_name", "ФИО"), ("specialization", "Специализация"), ("phone", "Телефон"),
        ]):
            tk.Label(body, text=label, bg=CARD, fg=NAVY, font=(FONT, 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=(0, 14), pady=8)
            tk.Entry(body, textvariable=self.vars[key], bg="#f7f9fb", relief="flat",
                     highlightbackground=BORDER, highlightthickness=1).grid(
                row=row, column=1, sticky="ew", pady=8, ipady=4)
        self.active_var = tk.BooleanVar(value=master.active if master else True)
        ttk.Checkbutton(body, text="Работает в центре", variable=self.active_var).grid(
            row=3, column=1, sticky="w", pady=8)
        buttons = tk.Frame(self, bg=CARD)
        buttons.pack(fill="x", padx=24, pady=20)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Сохранить", style="Accent.TButton",
                   command=self._save).pack(side="right")

    def _save(self) -> None:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        try:
            if self.master is None:
                self.app.service.add_master(**values)
            else:
                self.master.full_name = values["full_name"]
                self.master.specialization = values["specialization"]
                self.master.phone = values["phone"]
                self.master.active = self.active_var.get()
                self.app.service.update_master(self.master)
        except (ValidationError, NotFoundError) as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self)
            return
        self.app.refresh_all()
        self.destroy()


class MastersTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "RemTechApp") -> None:
        super().__init__(parent, style="App.TFrame")
        self.app = app
        toolbar = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=14, pady=12)
        tk.Label(toolbar, text="Мастера", bg=CARD, fg=NAVY,
                 font=(FONT, 13, "bold")).pack(side="left", padx=12, pady=10)
        ttk.Button(toolbar, text="+ Добавить", style="Accent.TButton",
                   command=self._add).pack(side="right", padx=12)
        ttk.Button(toolbar, text="Изменить", command=self._edit).pack(side="right", padx=4)
        self.tree, frame = make_tree(
            self, ("name", "spec", "phone", "active", "load"),
            ("ФИО", "Специализация", "Телефон", "Статус", "Активные заявки"),
            (260, 280, 160, 110, 130), height=16,
        )
        frame.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.tree.bind("<Double-1>", lambda _: self._edit())
        self.refresh()

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        load = {row["master"]: row["active"] for row in self.app.service.master_workload()}
        for master in self.app.service.masters.list():
            self.tree.insert("", "end", iid=str(master.id),
                             values=(master.full_name, master.specialization, master.phone,
                                     "Работает" if master.active else "Не работает",
                                     load.get(master.full_name, 0)))

    def _selected(self) -> Master | None:
        selected = self.tree.selection()
        return self.app.service.masters.get(int(selected[0])) if selected else None

    def _add(self) -> None:
        MasterDialog(self, self.app)

    def _edit(self) -> None:
        master = self._selected()
        if master is None:
            messagebox.showinfo("Мастер", "Выберите мастера", parent=self)
            return
        MasterDialog(self, self.app, master)


class ReportsTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "RemTechApp") -> None:
        super().__init__(parent, style="App.TFrame")
        self.app = app
        cards = tk.Frame(self, bg=BG)
        cards.pack(fill="x", padx=14, pady=(12, 8))
        self.cards = {}
        for index, (key, title, color) in enumerate([
            ("total", "Всего заявок", NAVY), ("active", "В работе", GREEN),
            ("overdue", "Просрочено", RED), ("revenue", "Выручка за год, руб.", "#b9770e"),
        ]):
            card = StatCard(cards, title, color)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
            cards.columnconfigure(index, weight=1)
            self.cards[key] = card

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=14)
        left = tk.Frame(content, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(left, text="Распределение заявок по статусам", bg=CARD, fg=NAVY,
                 font=(FONT, 10, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        self.status_tree, status_frame = make_tree(
            left, ("status", "count"), ("Статус", "Количество"), (190, 100), height=7)
        status_frame.pack(fill="x", padx=14, pady=(0, 10))
        self.chart = tk.Canvas(left, bg=CARD, height=230, highlightthickness=0)
        self.chart.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        right = tk.Frame(content, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        right.pack(side="right", fill="both", expand=True)
        tk.Label(right, text="Загрузка мастеров", bg=CARD, fg=NAVY,
                 font=(FONT, 10, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        self.master_tree, master_frame = make_tree(
            right, ("master", "total", "active"),
            ("Мастер", "Всего", "Активные"), (220, 70, 80), height=6)
        master_frame.pack(fill="x", padx=14, pady=(0, 10))

        tk.Label(right, text="Выручка за период", bg=CARD, fg=NAVY,
                 font=(FONT, 10, "bold")).pack(anchor="w", padx=14, pady=(8, 4))
        period = tk.Frame(right, bg=CARD)
        period.pack(fill="x", padx=14)
        self.start_var = tk.StringVar(value=date.today().replace(day=1).isoformat())
        self.end_var = tk.StringVar(value=date.today().isoformat())
        tk.Entry(period, textvariable=self.start_var, width=12, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1).pack(side="left", ipady=4)
        tk.Label(period, text="—", bg=CARD, fg=MUTED).pack(side="left", padx=6)
        tk.Entry(period, textvariable=self.end_var, width=12, bg="#f7f9fb", relief="flat",
                 highlightbackground=BORDER, highlightthickness=1).pack(side="left", ipady=4)
        ttk.Button(period, text="Рассчитать", command=self._revenue).pack(side="left", padx=8)
        self.revenue_label = tk.Label(right, text="", bg=CARD, fg=GREEN,
                                      font=(FONT, 13, "bold"))
        self.revenue_label.pack(anchor="w", padx=14, pady=(10, 4))
        tk.Label(right, text="Отчёт по периоду строится по завершённым и закрытым заявкам.",
                 bg=CARD, fg=MUTED, font=(FONT, 8), wraplength=330, justify="left").pack(
            anchor="w", padx=14)
        self.refresh()

    def refresh(self) -> None:
        dashboard = self.app.service.dashboard()
        self.cards["total"].set(dashboard["total"])
        self.cards["active"].set(dashboard["active"])
        self.cards["overdue"].set(dashboard["overdue"])
        self.cards["revenue"].set(f"{dashboard['revenue']:,.0f}".replace(",", " "))
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)
        for status, count in dashboard["statuses"].items():
            self.status_tree.insert("", "end", values=(status, count))
        for item in self.master_tree.get_children():
            self.master_tree.delete(item)
        for row in self.app.service.master_workload():
            self.master_tree.insert("", "end", values=(row["master"], row["total"], row["active"]))
        self._draw_chart(dashboard["statuses"])
        self._revenue()

    def _draw_chart(self, statuses: dict[str, int]) -> None:
        self.chart.delete("all")
        width = max(self.chart.winfo_width(), 420)
        height = 230
        left, top, bottom = 18, 24, height - 42
        max_value = max(statuses.values()) or 1
        bar_width = (width - 36) / max(len(statuses), 1) * 0.6
        step = (width - 36) / max(len(statuses), 1)
        colors = ["#2f80ed", "#8e6bd8", "#d68910", "#c0392b", "#1f7a5c", "#6b7c8f", "#95a5a6"]
        for index, (label, value) in enumerate(statuses.items()):
            x = left + index * step + (step - bar_width) / 2
            bar_height = (bottom - top) * value / max_value
            self.chart.create_rectangle(x, bottom - bar_height, x + bar_width, bottom,
                                        fill=colors[index % len(colors)], outline="")
            self.chart.create_text(x + bar_width / 2, bottom - bar_height - 10,
                                   text=str(value), fill=NAVY, font=(FONT, 9, "bold"))
            short = label.replace(" ", "\n") if len(label) > 10 else label
            self.chart.create_text(x + bar_width / 2, bottom + 14, text=short,
                                   fill=MUTED, font=(FONT, 7), justify="center")

    def _revenue(self) -> None:
        try:
            value = self.app.service.revenue(self.start_var.get(), self.end_var.get())
        except ValidationError as exc:
            self.revenue_label.configure(text=str(exc), fg=RED)
            return
        self.revenue_label.configure(text=f"{value:,.2f} руб.".replace(",", " "), fg=GREEN)


class RemTechApp(tk.Tk):
    def __init__(self, db_path: str | Path) -> None:
        super().__init__()
        self.title("РемТех — информационная система сервисного центра")
        self.geometry("1280x800")
        self.minsize(1080, 680)
        self.configure(bg=BG)
        self.db = Database(db_path)
        seed_demo(self.db)
        self.service = RequestService(self.db)
        self._configure_style()
        self._build_header()
        self._build_statusbar()
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.requests_tab = RequestsTab(self.notebook, self)
        self.clients_tab = ClientsTab(self.notebook, self)
        self.equipment_tab = EquipmentTab(self.notebook, self)
        self.masters_tab = MastersTab(self.notebook, self)
        self.reports_tab = ReportsTab(self.notebook, self)
        self.notebook.add(self.requests_tab, text="  Заявки  ")
        self.notebook.add(self.clients_tab, text="  Клиенты  ")
        self.notebook.add(self.equipment_tab, text="  Оборудование  ")
        self.notebook.add(self.masters_tab, text="  Мастера  ")
        self.notebook.add(self.reports_tab, text="  Отчёты  ")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh_all()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=BG)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=NAVY, font=(FONT, 10))
        style.configure("TButton", font=(FONT, 9), padding=(10, 6))
        style.configure("Accent.TButton", background=GREEN, foreground="white",
                        font=(FONT, 9, "bold"), padding=(12, 6))
        style.map("Accent.TButton", background=[("active", GREEN_LIGHT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=(FONT, 10), padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", CARD)],
                  foreground=[("selected", GREEN)])
        style.configure("Treeview", font=(FONT, 9), rowheight=29, background=CARD,
                        fieldbackground=CARD, borderwidth=0)
        style.configure("Treeview.Heading", font=(FONT, 9, "bold"), background="#e3eaf0",
                        foreground=NAVY, relief="flat", padding=(6, 5))
        style.map("Treeview", background=[("selected", "#d8efe5")],
                  foreground=[("selected", NAVY)])
        style.configure("TCombobox", padding=3)
        style.configure("TCheckbutton", background=CARD)

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=NAVY, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)
        logo = tk.Label(header, text="РемТех", bg=NAVY, fg="white",
                        font=(FONT, 22, "bold"))
        logo.pack(side="left", padx=(24, 10), pady=14)
        tk.Label(header, text="сервисный центр бытовой техники", bg=NAVY, fg="#a9c3d6",
                 font=(FONT, 9)).pack(side="left", pady=(26, 12))
        today = date.today().strftime("%d.%m.%Y")
        tk.Label(header, text=f"Журнал заявок · {today}", bg=NAVY, fg="#d7e6f0",
                 font=(FONT, 10)).pack(side="right", padx=24)

    def _build_statusbar(self) -> None:
        bar = tk.Frame(self, bg=NAVY_LIGHT, height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_label = tk.Label(bar, text="", bg=NAVY_LIGHT, fg="#d7e6f0",
                                     font=(FONT, 8))
        self.status_label.pack(side="left", padx=18)
        tk.Label(bar, text="SQLite · Python 3.10 · tkinter", bg=NAVY_LIGHT, fg="#9fb8c9",
                 font=(FONT, 8)).pack(side="right", padx=18)

    def refresh_all(self) -> None:
        for tab in (self.requests_tab, self.clients_tab, self.equipment_tab,
                    self.masters_tab, self.reports_tab):
            tab.refresh()
        dashboard = self.service.dashboard()
        self.status_label.configure(
            text=f"Заявок: {dashboard['total']} · активных: {dashboard['active']} · "
                 f"просрочено: {dashboard['overdue']}")

    def _on_close(self) -> None:
        self.db.close()
        self.destroy()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="РемТех — сервисный центр")
    parser.add_argument("--db", default="remteh.db", help="путь к файлу базы данных")
    parser.add_argument("--tab", type=int, default=0, help="номер открытой вкладки (0–4)")
    parser.add_argument(
        "--dialog", choices=("new", "works"), help="открыть диалог для демонстрации"
    )
    args = parser.parse_args(argv)
    app = RemTechApp(args.db)
    app.notebook.select(min(max(args.tab, 0), 4))
    if args.dialog == "new":
        app.after(600, lambda: RequestDialog(app.requests_tab, app))
    elif args.dialog == "works":
        app.after(600, lambda: WorksDialog(app.requests_tab, app, 1))
    app.mainloop()


if __name__ == "__main__":
    main()
