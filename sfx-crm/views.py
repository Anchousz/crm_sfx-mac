# -*- coding: utf-8 -*-
"""Экраны SFX CRM: смета, проекты, календарь, каталог, настройки."""
import calendar
import os
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

import db
import excel_io
import paths
import pdf_io
from dialogs import (AddDayDialog, CategoryDialog, ItemDialog, OvertimeDialog,
                     SavePresetDialog)
from excel_io import parse_date
from fastlist import FastList
from theme import (ACCENT, ACCENT_DIM, CARD, CARD_HOVER, GREEN, MUTED, PANEL,
                   RED, STATUS_COLORS, STATUSES, TEXT, UI_FONT, UNITS, YELLOW,
                   fmt_money, fmt_qty, parse_num)

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль",
          "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class EstimateView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.project_id = None
        self.days = []
        self.current = -1
        self._autosave_job = None

        self._build_top()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=2, uniform="cols")
        body.grid_columnconfigure(1, weight=3, uniform="cols")
        body.grid_rowconfigure(0, weight=1)
        self._build_catalog(body)
        self._build_days(body)
        self.new_project()

    def _build_top(self):
        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        top.pack(fill="x", pady=(0, 10))

        row1 = ctk.CTkFrame(top, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(row1, text="Проект", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(4, 6))
        self.name_entry = ctk.CTkEntry(row1, width=240, fg_color=CARD, border_color=CARD,
                                       placeholder_text="Название проекта",
                                       font=(UI_FONT, 14))
        self.name_entry.pack(side="left")
        ctk.CTkLabel(row1, text="Заказчик", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(14, 6))
        self.client_entry = ctk.CTkEntry(row1, width=170, fg_color=CARD, border_color=CARD,
                                         placeholder_text="например: ВТБ",
                                         font=(UI_FONT, 14))
        self.client_entry.pack(side="left")
        ctk.CTkLabel(row1, text="Статус", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(14, 6))
        self.status_menu = ctk.CTkOptionMenu(
            row1, values=STATUSES, width=170, fg_color=CARD,
            button_color=CARD, button_hover_color=CARD_HOVER,
            font=(UI_FONT, 13), command=lambda _v: self._touch())
        self.status_menu.pack(side="left")
        ctk.CTkLabel(row1, text="Налог, %", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(14, 6))
        self.tax_entry = ctk.CTkEntry(row1, width=60, fg_color=CARD, border_color=CARD,
                                      font=(UI_FONT, 14), justify="center")
        self.tax_entry.insert(0, "0")
        self.tax_entry.pack(side="left")
        self.tax_entry.bind("<KeyRelease>", lambda e: self._on_meta_edit())

        row2 = ctk.CTkFrame(top, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 10))
        self.save_lbl = ctk.CTkLabel(row2, text="автосохранение включено",
                                     text_color=MUTED, font=(UI_FONT, 11))
        self.save_lbl.pack(side="left", padx=4)
        ctk.CTkButton(row2, text="Выгрузить в Excel", fg_color=ACCENT,
                      hover_color=ACCENT_DIM, font=(UI_FONT, 13, "bold"),
                      height=32, command=self.export_excel).pack(side="right", padx=(8, 4))
        ctk.CTkButton(row2, text="PDF", fg_color=CARD, hover_color=CARD_HOVER,
                      font=(UI_FONT, 13), height=32, width=70,
                      command=self.export_pdf).pack(side="right")
        ctk.CTkButton(row2, text="Сохранить", fg_color=CARD, hover_color=CARD_HOVER,
                      font=(UI_FONT, 13), height=32, width=100,
                      command=self.save_now).pack(side="right", padx=8)
        ctk.CTkButton(row2, text="Новая смета", fg_color=CARD, hover_color=CARD_HOVER,
                      font=(UI_FONT, 13), height=32, width=110,
                      command=self.new_project).pack(side="right")

        for entry in (self.name_entry, self.client_entry):
            entry.bind("<KeyRelease>", lambda e: self._touch())

    def _build_catalog(self, body):
        panel = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(head, text="Каталог позиций", font=(UI_FONT, 15, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(head, text="+ позиция", fg_color=CARD,
                      hover_color=CARD_HOVER, text_color=ACCENT, width=96,
                      height=26, font=(UI_FONT, 12),
                      command=self.new_catalog_item).pack(side="right")
        self.search = ctk.CTkEntry(panel, fg_color=CARD, border_color=CARD,
                                   placeholder_text="Поиск…", font=(UI_FONT, 13))
        self.search.pack(fill="x", padx=14, pady=(0, 8))
        self.search.bind("<KeyRelease>", lambda e: self.refresh_catalog())
        self.cat_list = FastList(panel, empty_text="Ничего не найдено")
        self.cat_list.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self.refresh_catalog()

    def on_show(self):
        self.refresh_catalog(keep_scroll=True)

    def refresh_catalog(self, keep_scroll=False):
        query = self.search.get().strip().lower()
        stock = db.stock_map()
        rows = []
        self.cat_list.empty_text = (
            "Ничего не найдено" if query else
            "Каталог пуст — нажмите «+ позиция» вверху,\n"
            "чтобы завести её вручную")

        presets = [p for p in db.list_presets()
                   if not query or query in p["name"].lower()]
        if presets:
            rows.append({"header": "КОМПЛЕКТЫ", "color": YELLOW})
            for p in presets:
                rows.append({
                    "title": p["name"], "bold": True,
                    "sub": f"{len(p['lines'])} поз. · {fmt_money(p['total'])}",
                    "on_click": lambda p=p: self.add_preset(p),
                    "buttons": [
                        {"text": "+", "fill": YELLOW, "text_color": "#1a1a1a",
                         "cb": lambda p=p: self.add_preset(p)},
                        {"text": "✕", "text_color": MUTED,
                         "cb": lambda p=p: self.delete_preset(p)},
                    ]})

        for _cid, cname, items in db.list_catalog():
            shown = [it for it in items if not query or query in it[1].lower()]
            if not shown:
                continue
            rows.append({"header": cname.upper(), "color": ACCENT})
            for _iid, name, price, unit, _stk in shown:
                sub = f"{fmt_money(price)}/{unit}"
                if name.strip() in stock:
                    sub += f" · склад: {fmt_qty(stock[name.strip()][0])}"
                add = lambda n=name, p=price, u=unit: self.add_line(n, p, u)
                rows.append({
                    "title": name, "sub": sub, "on_click": add,
                    "buttons": [{"text": "+", "fill": ACCENT,
                                 "text_color": "#ffffff", "cb": add}]})
        self.cat_list.set_rows(rows, keep_scroll=keep_scroll)

    def new_catalog_item(self):
        """Завести позицию каталога, не уходя со сметы — сразу ставим её в день."""
        cats = [c[1] for c in db.list_categories()]
        dlg = ItemDialog(self.app, cats, self._save_catalog_item)
        self.app.wait_window(dlg)
        self.refresh_catalog(keep_scroll=True)
        self.app.catalog_view.refresh(keep_scroll=True)

    def _save_catalog_item(self, data):
        cid = db.find_or_create_category(data["category"])
        if db.item_exists(cid, data["name"]):
            return f"«{data['name']}» уже есть в этой категории"
        db.add_item(cid, data["name"], data["price"], data["unit"], data["stock"])
        if self.current >= 0:
            self.add_line(data["name"], data["price"], data["unit"])
        return None

    def _build_days(self, body):
        panel = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12)
        panel.grid(row=0, column=1, sticky="nsew")

        bar = ctk.CTkFrame(panel, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(bar, text="Смета по дням", font=(UI_FONT, 15, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(bar, text="Удалить день", fg_color=CARD, hover_color=CARD_HOVER,
                      text_color=RED, width=104, height=28, font=(UI_FONT, 12),
                      command=self.delete_day).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bar, text="В комплект", fg_color=CARD, hover_color=CARD_HOVER,
                      text_color=YELLOW, width=96, height=28, font=(UI_FONT, 12),
                      command=self.day_to_preset).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bar, text="Дублировать", fg_color=CARD, hover_color=CARD_HOVER,
                      width=104, height=28, font=(UI_FONT, 12),
                      command=self.duplicate_day).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bar, text="+ день", fg_color=ACCENT, hover_color=ACCENT_DIM,
                      width=84, height=28, font=(UI_FONT, 12, "bold"),
                      command=self.add_day).pack(side="right")

        self.chips = ctk.CTkScrollableFrame(panel, fg_color="transparent",
                                            orientation="horizontal", height=48)
        self.chips.pack(fill="x", padx=10)

        tools = ctk.CTkFrame(panel, fg_color="transparent")
        tools.pack(fill="x", padx=10, pady=(4, 0))
        ctk.CTkLabel(tools, text="Заметка дня", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(4, 6))
        self.note_entry = ctk.CTkEntry(tools, fg_color=CARD, border_color=CARD,
                                       placeholder_text="локация, время, контакты…",
                                       font=(UI_FONT, 13))
        self.note_entry.pack(side="left", fill="x", expand=True)
        self.note_entry.bind("<KeyRelease>", lambda e: self._on_note_edit())
        ctk.CTkButton(tools, text="+ переработка", fg_color=CARD,
                      hover_color=CARD_HOVER, text_color=ACCENT, width=120,
                      height=28, font=(UI_FONT, 12),
                      command=self.add_overtime).pack(side="left", padx=(8, 0))

        self.lines_scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.lines_scroll.pack(fill="both", expand=True, padx=6, pady=(4, 0))

        total_bar = ctk.CTkFrame(panel, fg_color=CARD, corner_radius=12)
        total_bar.pack(fill="x", padx=10, pady=10)
        left_box = ctk.CTkFrame(total_bar, fg_color="transparent")
        left_box.pack(side="left", padx=14, pady=8)
        self.day_total_lbl = ctk.CTkLabel(left_box, text="", text_color=MUTED,
                                          font=(UI_FONT, 13), anchor="w")
        self.day_total_lbl.pack(anchor="w")
        self.breakdown_lbl = ctk.CTkLabel(left_box, text="", text_color=MUTED,
                                          font=(UI_FONT, 11), anchor="w")
        self.breakdown_lbl.pack(anchor="w")
        self.grand_lbl = ctk.CTkLabel(total_bar, text="Итого: 0 ₽", text_color=GREEN,
                                      font=(UI_FONT, 19, "bold"))
        self.grand_lbl.pack(side="right", padx=14, pady=8)

    def _default_next_date(self):
        for day in reversed(self.days):
            d = parse_date(day["label"])
            if d:
                return (d + timedelta(days=1)).strftime("%d.%m.%Y")
        return datetime.now().strftime("%d.%m.%Y")

    def add_day(self):
        dlg = AddDayDialog(self.app, self._default_next_date())
        self.app.wait_window(dlg)
        if dlg.result:
            self.days.append({"label": dlg.result, "note": "", "lines": []})
            self.current = len(self.days) - 1
            self.refresh_days()
            self._touch()

    def duplicate_day(self):
        if self.current < 0:
            return
        src = self.days[self.current]
        d = parse_date(src["label"])
        new_label = (d + timedelta(days=1)).strftime("%d.%m.%Y") if d else src["label"] + " (копия)"
        self.days.insert(self.current + 1,
                         {"label": new_label, "note": src.get("note", ""),
                          "lines": [dict(l) for l in src["lines"]]})
        self.current += 1
        self.refresh_days()
        self._touch()

    def delete_day(self):
        if self.current < 0:
            return
        del self.days[self.current]
        self.current = min(self.current, len(self.days) - 1)
        self.refresh_days()
        self._touch()

    def day_to_preset(self):
        if self.current < 0:
            return
        day = self.days[self.current]
        lines = [l for l in day["lines"] if not l.get("ot")]
        if not lines:
            messagebox.showinfo("Комплект", "В этом дне нет позиций.")
            return
        dlg = SavePresetDialog(self.app, day["label"])
        self.app.wait_window(dlg)
        if dlg.result:
            db.save_preset(dlg.result, lines)
            self.refresh_catalog()

    def add_preset(self, preset):
        if self.current < 0:
            messagebox.showinfo("Смета", "Сначала добавьте день («+ день»).")
            return
        lines = self.days[self.current]["lines"]
        for l in preset["lines"]:
            lines.append(dict(l))
        self.refresh_days()
        self._touch()

    def delete_preset(self, preset):
        if messagebox.askyesno("Комплект", f"Удалить комплект «{preset['name']}»?"):
            db.delete_preset(preset["id"])
            self.refresh_catalog()

    def refresh_days(self):
        for w in self.chips.winfo_children():
            w.destroy()
        for i, day in enumerate(self.days):
            total = sum(l["price"] * l["qty"] for l in day["lines"])
            sel = i == self.current
            ctk.CTkButton(
                self.chips, text=f"{day['label']}\n{fmt_money(total)}",
                fg_color=ACCENT if sel else CARD,
                hover_color=ACCENT_DIM if sel else CARD_HOVER,
                text_color="#ffffff" if sel else MUTED,
                font=(UI_FONT, 12, "bold" if sel else "normal"),
                corner_radius=10, height=40,
                command=lambda i=i: self.select_day(i)).pack(side="left", padx=3, pady=2)
        self.note_entry.delete(0, "end")
        if self.current >= 0:
            self.note_entry.insert(0, self.days[self.current].get("note", ""))
        self.refresh_lines()

    def select_day(self, i):
        self.current = i
        self.refresh_days()

    def add_line(self, name, price, unit="шт"):
        if self.current < 0:
            messagebox.showinfo("Смета", "Сначала добавьте день («+ день»).")
            return
        lines = self.days[self.current]["lines"]
        for l in lines:
            if l["name"] == name and l["price"] == price and not l.get("ot"):
                l["qty"] += 1
                self.refresh_days()
                self._touch()
                return
        lines.append({"name": name, "price": price, "qty": 1.0, "unit": unit})
        self.refresh_days()
        self._touch()

    def add_overtime(self):
        if self.current < 0:
            messagebox.showinfo("Смета", "Сначала добавьте день («+ день»).")
            return
        personnel = []
        for _cid, cname, items in db.list_catalog():
            if "персонал" in cname.lower():
                personnel += [it[1] for it in items]
        dlg = OvertimeDialog(self.app, personnel)
        self.app.wait_window(dlg)
        if dlg.result:
            self.days[self.current]["lines"].append(dlg.result)
            self.refresh_days()
            self._touch()

    def _availability(self, day):
        d = parse_date(day["label"])
        stock = db.stock_map()
        if not d or not stock:
            return {}
        usage = db.usage_by_date(self.project_id).get(d.date().isoformat(), [])
        result = {}
        for name, (total, _unit) in stock.items():
            here = sum(l["qty"] for l in day["lines"] if l["name"].strip() == name and not l.get("ot"))
            if here == 0:
                continue
            conflicts = [(q, proj) for n, q, proj in usage if n == name]
            used_elsewhere = sum(q for q, _ in conflicts)
            result[name] = (total - used_elsewhere - here, total, conflicts)
        return result

    def refresh_lines(self):
        for w in self.lines_scroll.winfo_children():
            w.destroy()
        if self.current < 0:
            ctk.CTkLabel(self.lines_scroll,
                         text="Добавьте день съёмок и выбирайте позиции из каталога слева",
                         text_color=MUTED, font=(UI_FONT, 13)).pack(pady=40)
            self._update_totals()
            return
        day = self.days[self.current]
        if not day["lines"]:
            ctk.CTkLabel(self.lines_scroll,
                         text="Пусто. Жмите «+» на позициях и комплектах слева.",
                         text_color=MUTED, font=(UI_FONT, 13)).pack(pady=40)
        avail = self._availability(day)
        for idx, line in enumerate(day["lines"]):
            self._line_row(idx, line, avail)
        self._update_totals()

    def _line_row(self, idx, line, avail):
        is_ot = bool(line.get("ot"))
        row = ctk.CTkFrame(self.lines_scroll, fg_color=CARD, corner_radius=8)
        row.pack(fill="x", padx=6, pady=2)

        ctk.CTkButton(row, text="✕", width=28, height=24, fg_color="transparent",
                      hover_color=CARD_HOVER, text_color=RED, font=(UI_FONT, 13),
                      command=lambda: self._remove_line(idx)).pack(side="right", padx=(0, 6))
        cost_lbl = ctk.CTkLabel(row, text=fmt_money(line["price"] * line["qty"]),
                                text_color=GREEN, font=(UI_FONT, 13, "bold"),
                                width=95, anchor="e")
        cost_lbl.pack(side="right", padx=4)

        unit = "ч" if is_ot else line.get("unit", "шт")
        ctk.CTkLabel(row, text=unit, text_color=MUTED, font=(UI_FONT, 12),
                     width=34, anchor="w").pack(side="right")
        qty = ctk.CTkEntry(row, width=54, fg_color=PANEL, border_color=PANEL,
                           font=(UI_FONT, 13), justify="center")
        qty.insert(0, fmt_qty(line["qty"]))
        qty.pack(side="right", padx=2, pady=5)
        ctk.CTkLabel(row, text="×", text_color=MUTED,
                     font=(UI_FONT, 13)).pack(side="right")
        price = ctk.CTkEntry(row, width=76, fg_color=PANEL, border_color=PANEL,
                             font=(UI_FONT, 13), justify="right")
        price.insert(0, fmt_qty(line["price"]))
        price.pack(side="right", padx=2, pady=5)

        def on_edit(_e=None):
            p, q = parse_num(price.get()), parse_num(qty.get())
            price.configure(border_color=PANEL if p is not None else RED)
            qty.configure(border_color=PANEL if q is not None else RED)
            if p is None or q is None:
                return
            line["price"], line["qty"] = p, q
            cost_lbl.configure(text=fmt_money(p * q))
            self._update_totals()
            self._touch()
        price.bind("<KeyRelease>", on_edit)
        qty.bind("<KeyRelease>", on_edit)
        price.bind("<FocusOut>", lambda e: self.refresh_days())
        qty.bind("<FocusOut>", lambda e: self.refresh_days())

        box = ctk.CTkFrame(row, fg_color="transparent")
        box.pack(side="left", fill="x", expand=True, padx=(10, 4), pady=3)
        name_text = ("Переработка — " if is_ot else "") + line["name"]
        ctk.CTkLabel(box, text=name_text, text_color=ACCENT if is_ot else TEXT,
                     anchor="w", font=(UI_FONT, 13), wraplength=330,
                     justify="left").pack(anchor="w")
        info = avail.get(line["name"].strip())
        if info and not is_ot:
            free, total, conflicts = info
            if free < 0:
                msg = f"⚠ не хватает {fmt_qty(-free)} (склад {fmt_qty(total)}"
                if conflicts:
                    msg += f", занято в: {conflicts[0][1]}"
                msg += ")"
                ctk.CTkLabel(box, text=msg, text_color=RED, anchor="w",
                             font=(UI_FONT, 11)).pack(anchor="w")
            else:
                ctk.CTkLabel(box, text=f"склад: свободно {fmt_qty(free)} из {fmt_qty(total)}",
                             text_color=MUTED, anchor="w",
                             font=(UI_FONT, 11)).pack(anchor="w")

    def _remove_line(self, idx):
        del self.days[self.current]["lines"][idx]
        self.refresh_days()
        self._touch()

    def _update_totals(self):
        tax = parse_num(self.tax_entry.get()) or 0
        t = db.project_totals(self.days, tax)
        self.grand_lbl.configure(text=f"Итого: {fmt_money(t['final'])}")
        self.breakdown_lbl.configure(
            text=f"позиции {fmt_money(t['positions'])} · переработки "
                 f"{fmt_money(t['overtime'])} · налог {fmt_money(t['tax_amount'])}")
        if self.current >= 0:
            day = self.days[self.current]
            day_total = sum(l["price"] * l["qty"] for l in day["lines"])
            self.day_total_lbl.configure(text=f"{day['label']}: {fmt_money(day_total)}")
        else:
            self.day_total_lbl.configure(text="")

    def _on_note_edit(self):
        if self.current >= 0:
            self.days[self.current]["note"] = self.note_entry.get()
            self._touch()

    def _on_meta_edit(self):
        tax = parse_num(self.tax_entry.get())
        self.tax_entry.configure(border_color=CARD if tax is not None else RED)
        self._update_totals()
        self._touch()

    def _touch(self):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
        self._autosave_job = self.after(1500, self._autosave)

    def _autosave(self):
        self._autosave_job = None
        if not self.name_entry.get().strip() and not any(d["lines"] for d in self.days):
            return
        name = self.name_entry.get().strip() or "Черновик"
        tax = parse_num(self.tax_entry.get()) or 0
        self.project_id = db.save_project(
            name, self.client_entry.get().strip(), self.days,
            self.status_menu.get(), tax, self.project_id)
        self.save_lbl.configure(text=f"автосохранено {datetime.now():%H:%M:%S}")

    def save_now(self):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
        self._autosave()
        self.save_lbl.configure(text=f"сохранено ✓ {datetime.now():%H:%M:%S}")

    def new_project(self):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
            self._autosave()
        self.project_id = None
        self.days = []
        self.current = -1
        self.name_entry.delete(0, "end")
        self.client_entry.delete(0, "end")
        self.status_menu.set(STATUSES[0])
        self.tax_entry.delete(0, "end")
        self.tax_entry.insert(0, "0")
        self.refresh_days()

    def load(self, project):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
        self.project_id = project["id"]
        self.days = project["days"]
        self.current = 0 if self.days else -1
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, project["name"])
        self.client_entry.delete(0, "end")
        self.client_entry.insert(0, project["client"])
        self.status_menu.set(project.get("status") or STATUSES[0])
        self.tax_entry.delete(0, "end")
        self.tax_entry.insert(0, fmt_qty(project.get("tax") or 0))
        self.refresh_days()

    def _project_dict(self):
        return {"name": self.name_entry.get().strip() or "Смета",
                "client": self.client_entry.get().strip(),
                "days": self.days,
                "status": self.status_menu.get(),
                "tax": parse_num(self.tax_entry.get()) or 0}

    def export_excel(self):
        if not any(d["lines"] for d in self.days):
            messagebox.showwarning("Экспорт", "Смета пустая — добавьте позиции.")
            return
        self.save_now()
        proj = self._project_dict()
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=f"Смета {proj['name']}.xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        excel_io.export_estimate(path, proj, db.get_settings())
        if messagebox.askyesno("Экспорт", f"Смета сохранена:\n{path}\n\nОткрыть файл?"):
            paths.open_path(path)

    def export_pdf(self):
        if not any(d["lines"] for d in self.days):
            messagebox.showwarning("Экспорт", "Смета пустая — добавьте позиции.")
            return
        self.save_now()
        proj = self._project_dict()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialfile=f"Смета {proj['name']}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        totals = db.project_totals(proj["days"], proj["tax"])
        pdf_io.export_pdf(path, proj, db.get_settings(), totals)
        if messagebox.askyesno("Экспорт", f"PDF сохранён:\n{path}\n\nОткрыть файл?"):
            paths.open_path(path)


class ProjectsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        head = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        head.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(head, text="Проекты", font=(UI_FONT, 15, "bold"),
                     text_color=TEXT).pack(side="left", padx=16, pady=12)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=12)
        self.scroll.pack(fill="both", expand=True)
        self.refresh()

    def on_show(self):
        self.refresh()

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        projects = db.list_projects()
        if not projects:
            ctk.CTkLabel(self.scroll, text="Пока нет сохранённых проектов",
                         text_color=MUTED, font=(UI_FONT, 13)).pack(pady=40)
        for p in projects:
            row = ctk.CTkFrame(self.scroll, fg_color=CARD, corner_radius=10)
            row.pack(fill="x", padx=8, pady=4)
            ctk.CTkButton(row, text="Удалить", width=80, height=28,
                          fg_color="transparent", hover_color=CARD_HOVER,
                          text_color=RED, font=(UI_FONT, 12),
                          command=lambda pid=p["id"]: self._delete(pid)
                          ).pack(side="right", padx=8)
            ctk.CTkButton(row, text="Открыть", width=90, height=28,
                          fg_color=ACCENT, hover_color=ACCENT_DIM,
                          font=(UI_FONT, 12, "bold"),
                          command=lambda pid=p["id"]: self._open(pid)
                          ).pack(side="right", padx=4)
            money_box = ctk.CTkFrame(row, fg_color="transparent")
            money_box.pack(side="right", padx=8)
            ctk.CTkLabel(money_box, text=fmt_money(p["totals"]["final"]),
                         text_color=GREEN, font=(UI_FONT, 14, "bold"),
                         anchor="e").pack(anchor="e")
            if p["totals"]["overtime"] or p["totals"]["tax_amount"]:
                ctk.CTkLabel(money_box,
                             text=f"позиции {fmt_money(p['totals']['positions'])}",
                             text_color=MUTED, font=(UI_FONT, 10),
                             anchor="e").pack(anchor="e")
            status_color = STATUS_COLORS.get(p["status"], MUTED)
            ctk.CTkLabel(row, text="● " + p["status"], text_color=status_color,
                         font=(UI_FONT, 12), width=130,
                         anchor="w").pack(side="right", padx=4)
            box = ctk.CTkFrame(row, fg_color="transparent")
            box.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            info = p["name"] + (f" · {p['client']}" if p["client"] else "")
            ctk.CTkLabel(box, text=info, text_color=TEXT, anchor="w",
                         font=(UI_FONT, 14, "bold")).pack(anchor="w")
            ctk.CTkLabel(box, text=f"{len(p['days'])} дн. · изменён {p['updated']}",
                         text_color=MUTED, anchor="w",
                         font=(UI_FONT, 11)).pack(anchor="w")

    def _open(self, pid):
        project = db.load_project(pid)
        if project:
            self.app.estimate_view.load(project)
            self.app.show("estimate")

    def _delete(self, pid):
        if messagebox.askyesno("Удаление", "Удалить проект?"):
            db.delete_project(pid)
            self.refresh()


class CalendarView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        today = date.today()
        self.year, self.month = today.year, today.month

        head = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        head.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(head, text="Календарь проектов", font=(UI_FONT, 15, "bold"),
                     text_color=TEXT).pack(side="left", padx=16, pady=12)
        ctk.CTkButton(head, text="›", width=36, height=28, fg_color=CARD,
                      hover_color=CARD_HOVER, font=(UI_FONT, 15, "bold"),
                      command=lambda: self._shift(1)).pack(side="right", padx=(4, 16))
        self.month_lbl = ctk.CTkLabel(head, text="", text_color=TEXT,
                                      font=(UI_FONT, 14, "bold"), width=140)
        self.month_lbl.pack(side="right")
        ctk.CTkButton(head, text="‹", width=36, height=28, fg_color=CARD,
                      hover_color=CARD_HOVER, font=(UI_FONT, 15, "bold"),
                      command=lambda: self._shift(-1)).pack(side="right", padx=4)
        ctk.CTkButton(head, text="сегодня", width=70, height=28, fg_color=CARD,
                      hover_color=CARD_HOVER, font=(UI_FONT, 12),
                      command=self._today).pack(side="right", padx=4)

        self.grid_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        self.grid_frame.pack(fill="both", expand=True)
        self.refresh()

    def on_show(self):
        self.refresh()

    def _shift(self, delta):
        m = self.month + delta
        self.year += (m - 1) // 12
        self.month = (m - 1) % 12 + 1
        self.refresh()

    def _today(self):
        today = date.today()
        self.year, self.month = today.year, today.month
        self.refresh()

    def refresh(self):
        self.month_lbl.configure(text=f"{MONTHS[self.month - 1]} {self.year}")
        for w in self.grid_frame.winfo_children():
            w.destroy()

        by_date = {}
        for p in db.list_projects():
            for day in p["days"]:
                d = parse_date(day["label"])
                if d:
                    by_date.setdefault(d.date(), []).append(p)

        for c in range(7):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform="cal")
            ctk.CTkLabel(self.grid_frame, text=WEEKDAYS[c], text_color=MUTED,
                         font=(UI_FONT, 12, "bold")).grid(row=0, column=c, pady=(10, 2))
        weeks = calendar.Calendar().monthdayscalendar(self.year, self.month)
        for r in range(1, len(weeks) + 1):
            self.grid_frame.grid_rowconfigure(r, weight=1, uniform="calr")
        today = date.today()
        for r, week in enumerate(weeks, start=1):
            for c, daynum in enumerate(week):
                cell = ctk.CTkFrame(self.grid_frame,
                                    fg_color=CARD if daynum else "transparent",
                                    corner_radius=8)
                cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
                if not daynum:
                    continue
                d = date(self.year, self.month, daynum)
                is_today = d == today
                ctk.CTkLabel(cell, text=str(daynum),
                             text_color=ACCENT if is_today else MUTED,
                             font=(UI_FONT, 12, "bold" if is_today else "normal")
                             ).pack(anchor="nw", padx=7, pady=(3, 0))
                projects = {p["id"]: p for p in by_date.get(d, [])}.values()
                for i, p in enumerate(projects):
                    if i == 3:
                        ctk.CTkLabel(cell, text=f"+ ещё {len(projects) - 3}",
                                     text_color=MUTED, font=(UI_FONT, 10)
                                     ).pack(anchor="w", padx=6)
                        break
                    color = STATUS_COLORS.get(p["status"], MUTED)
                    name = p["name"] if len(p["name"]) <= 16 else p["name"][:15] + "…"
                    ctk.CTkButton(cell, text=name, height=20, corner_radius=6,
                                  fg_color=PANEL, hover_color=CARD_HOVER,
                                  text_color=color, font=(UI_FONT, 11),
                                  anchor="w",
                                  command=lambda pid=p["id"]: self._open(pid)
                                  ).pack(fill="x", padx=4, pady=1)

    def _open(self, pid):
        project = db.load_project(pid)
        if project:
            self.app.estimate_view.load(project)
            self.app.show("estimate")


class CatalogView(ctk.CTkFrame):
    HINT = "кликните позицию в списке, чтобы править"

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.sel = None

        head = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        head.pack(fill="x", pady=(0, 10))
        row1 = ctk.CTkFrame(head, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(row1, text="Каталог и цены", font=(UI_FONT, 15, "bold"),
                     text_color=TEXT).pack(side="left", padx=4)
        ctk.CTkButton(row1, text="+ Позиция", fg_color=ACCENT,
                      hover_color=ACCENT_DIM, height=32, width=110,
                      font=(UI_FONT, 13, "bold"),
                      command=self._add_item).pack(side="right", padx=4)
        ctk.CTkButton(row1, text="+ Категория", fg_color=CARD,
                      hover_color=CARD_HOVER, height=32, width=110,
                      font=(UI_FONT, 12),
                      command=self._add_category).pack(side="right", padx=4)
        ctk.CTkButton(row1, text="Импорт из Excel", fg_color=CARD,
                      hover_color=CARD_HOVER, height=32, font=(UI_FONT, 12),
                      command=self._import).pack(side="right", padx=4)
        self.cat_search = ctk.CTkEntry(row1, width=200, fg_color=CARD,
                                       border_color=CARD, font=(UI_FONT, 13),
                                       placeholder_text="Поиск…")
        self.cat_search.pack(side="right", padx=8)
        self.cat_search.bind("<KeyRelease>", lambda e: self.refresh(keep_scroll=True))

        row2 = ctk.CTkFrame(head, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 10))
        self.sel_lbl = ctk.CTkLabel(row2, text=self.HINT,
                                    text_color=MUTED, font=(UI_FONT, 13), anchor="w")
        self.sel_lbl.pack(side="left", padx=4, fill="x", expand=True)
        ctk.CTkButton(row2, text="Правка", fg_color=CARD, hover_color=CARD_HOVER,
                      width=80, height=28, font=(UI_FONT, 12),
                      command=self._edit_item).pack(side="left", padx=(4, 8))
        ctk.CTkLabel(row2, text="Цена", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(8, 4))
        self.price_entry = ctk.CTkEntry(row2, width=90, fg_color=CARD,
                                        border_color=CARD, font=(UI_FONT, 13),
                                        justify="right")
        self.price_entry.pack(side="left")
        self.price_entry.bind("<KeyRelease>", lambda e: self._on_edit())
        ctk.CTkLabel(row2, text="Ед.", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(10, 4))
        self.unit_menu = ctk.CTkOptionMenu(
            row2, values=UNITS, width=80, height=28, fg_color=CARD,
            button_color=CARD, button_hover_color=CARD_HOVER,
            font=(UI_FONT, 12), command=lambda _u: self._on_edit())
        self.unit_menu.pack(side="left")
        ctk.CTkLabel(row2, text="Склад", text_color=MUTED,
                     font=(UI_FONT, 12)).pack(side="left", padx=(10, 4))
        self.stock_entry = ctk.CTkEntry(row2, width=70, fg_color=CARD,
                                        border_color=CARD, font=(UI_FONT, 13),
                                        justify="center", placeholder_text="—")
        self.stock_entry.pack(side="left", padx=(0, 4))
        self.stock_entry.bind("<KeyRelease>", lambda e: self._on_edit())

        self.list = FastList(
            self, empty_text="Каталог пуст — нажмите «+ Позиция», чтобы завести\n"
                             "первую позицию вручную, или импортируйте прайс из Excel")
        self.list.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self, keep_scroll=False):
        query = self.cat_search.get().strip().lower() if hasattr(self, "cat_search") else ""
        rows = []
        for cid, cname, items in db.list_catalog():
            shown = [it for it in items if not query or query in it[1].lower()]
            if not shown and query:
                continue
            rows.append({
                "header": cname.upper(), "color": ACCENT,
                "buttons": [
                    {"text": "✕", "text_color": MUTED,
                     "cb": lambda i=cid, n=cname: self._delete_category(i, n)},
                    # «…» — не эмодзи: рисуется шрифтом интерфейса на обеих ОС
                    {"text": "…", "text_color": MUTED,
                     "cb": lambda i=cid, n=cname: self._rename_category(i, n)},
                    {"text": "+", "text_color": ACCENT,
                     "cb": lambda n=cname: self._add_item(n)},
                ]})
            if not shown:
                rows.append({
                    "title": "категория пуста",
                    "title_color": MUTED,
                    "sub": "нажмите «+» справа от названия, чтобы добавить позицию",
                    "on_click": lambda n=cname: self._add_item(n)})
                continue
            for iid, name, price, unit, stk in shown:
                sub = f"{fmt_money(price)}/{unit}"
                sub += f" · склад: {fmt_qty(stk)}" if stk is not None else " · склад не отслеживается"
                rows.append({"title": name, "sub": sub, "key": iid,
                             "on_click": lambda i=iid, n=name: self._select(i, n),
                             "buttons": [
                                 {"text": "✕", "text_color": MUTED,
                                  "cb": lambda i=iid, n=name: self._delete_item(i, n)}]})
        self.list.set_rows(rows, keep_scroll=keep_scroll)

    def _reload(self):
        """Каталог правится в двух местах — обновляем оба списка."""
        self.refresh(keep_scroll=True)
        self.app.estimate_view.refresh_catalog(keep_scroll=True)

    def _select(self, iid, name):
        self.sel = iid
        self.list.select(iid)
        self.sel_lbl.configure(text=name, text_color=TEXT)
        with db.connect() as con:
            row = con.execute("SELECT price, unit, stock FROM items WHERE id=?", (iid,)).fetchone()
        if not row:
            return
        price, unit, stk = row
        self.price_entry.delete(0, "end")
        self.price_entry.insert(0, fmt_qty(price))
        self.unit_menu.set(unit)
        self.stock_entry.delete(0, "end")
        if stk is not None:
            self.stock_entry.insert(0, fmt_qty(stk))

    def _clear_selection(self):
        self.sel = None
        self.list.select(None)
        self.sel_lbl.configure(text=self.HINT, text_color=MUTED)
        self.price_entry.delete(0, "end")
        self.stock_entry.delete(0, "end")

    def _add_category(self):
        dlg = CategoryDialog(self.app)
        self.app.wait_window(dlg)
        if dlg.result:
            db.find_or_create_category(dlg.result)
            self._reload()

    def _rename_category(self, cid, name):
        dlg = CategoryDialog(self.app, name)
        self.app.wait_window(dlg)
        if dlg.result and dlg.result != name:
            db.rename_category(cid, dlg.result)
            self._reload()

    def _delete_category(self, cid, name):
        count = db.category_item_count(cid)
        msg = f"Удалить категорию «{name}»?"
        if count:
            msg += f"\n\nВместе с ней удалятся позиции: {count} шт."
        if messagebox.askyesno("Удаление", msg):
            db.delete_category(cid)
            self._clear_selection()
            self._reload()

    def _add_item(self, category=""):
        cats = [c[1] for c in db.list_categories()]
        dlg = ItemDialog(self.app, cats, self._save_new_item,
                         default_category=category)
        self.app.wait_window(dlg)
        self._reload()

    def _save_new_item(self, data):
        cid = db.find_or_create_category(data["category"])
        if db.item_exists(cid, data["name"]):
            return f"«{data['name']}» уже есть в этой категории"
        db.add_item(cid, data["name"], data["price"], data["unit"], data["stock"])
        return None

    def _edit_item(self):
        if self.sel is None:
            messagebox.showinfo("Каталог", "Сначала выберите позицию в списке.")
            return
        item = db.get_item(self.sel)
        if not item:
            return
        cats = [c[1] for c in db.list_categories()]
        dlg = ItemDialog(self.app, cats, self._save_edited_item, item=item)
        self.app.wait_window(dlg)
        if dlg.result:
            self.sel_lbl.configure(text=dlg.result["name"], text_color=TEXT)
        self._reload()

    def _save_edited_item(self, data):
        cid = db.find_or_create_category(data["category"])
        if db.item_exists(cid, data["name"], exclude_id=self.sel):
            return f"«{data['name']}» уже есть в этой категории"
        db.update_item(self.sel, name=data["name"], price=data["price"],
                       unit=data["unit"], stock=data["stock"], category_id=cid)
        return None

    def _delete_item(self, iid, name):
        if not messagebox.askyesno("Удаление", f"Удалить позицию «{name}»?"):
            return
        db.delete_item(iid)
        if self.sel == iid:
            self._clear_selection()
        self._reload()

    def _on_edit(self):
        if self.sel is None:
            return
        price = parse_num(self.price_entry.get())
        self.price_entry.configure(border_color=CARD if price is not None else RED)
        stock_text = self.stock_entry.get().strip()
        stock = None if not stock_text else parse_num(stock_text)
        bad_stock = stock_text and stock is None
        self.stock_entry.configure(border_color=RED if bad_stock else CARD)
        if price is None or bad_stock:
            return
        db.update_item(self.sel, price=price, unit=self.unit_menu.get(), stock=stock)
        self.refresh(keep_scroll=True)

    def _import(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        merge = messagebox.askyesnocancel(
            "Импорт прайса",
            "Добавить позиции из файла к текущему каталогу?\n\n"
            "Да — добавить (свои позиции останутся)\n"
            "Нет — заменить каталог целиком\n"
            "Отмена — ничего не делать")
        if merge is None:
            return
        data = excel_io.import_prices(path)
        added = skipped = 0
        if not merge:
            db.clear_catalog()
        for cat, items in data:
            cid = db.find_or_create_category(cat) if merge else db.add_category(cat)
            for name, price, unit in items:
                if merge and db.item_exists(cid, name):
                    skipped += 1
                    continue
                db.add_item(cid, name, price, unit)
                added += 1
        self._clear_selection()
        self._reload()
        report = f"Категорий: {len(data)}, позиций добавлено: {added}"
        if skipped:
            report += f"\nПропущено (уже были в каталоге): {skipped}"
        messagebox.showinfo("Импорт", report)


class SettingsView(ctk.CTkFrame):
    FIELDS = [("company_name", "Название компании (в шапке сметы)"),
              ("company_phone", "Телефон"),
              ("company_email", "E-mail"),
              ("company_extra", "Дополнительно (реквизиты, сайт)")]

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        panel = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12)
        panel.pack(fill="x")
        ctk.CTkLabel(panel, text="Реквизиты для Excel и PDF",
                     font=(UI_FONT, 15, "bold"), text_color=TEXT
                     ).pack(anchor="w", padx=20, pady=(16, 4))
        settings = db.get_settings()
        self.entries = {}
        for key, label in self.FIELDS:
            ctk.CTkLabel(panel, text=label, text_color=MUTED,
                         font=(UI_FONT, 12)).pack(anchor="w", padx=20, pady=(10, 2))
            e = ctk.CTkEntry(panel, fg_color=CARD, border_color=CARD,
                             font=(UI_FONT, 14), width=520)
            e.insert(0, settings.get(key, ""))
            e.pack(anchor="w", padx=20)
            self.entries[key] = e
        self.saved_lbl = ctk.CTkLabel(panel, text="", text_color=GREEN,
                                      font=(UI_FONT, 12))
        ctk.CTkButton(panel, text="Сохранить", fg_color=ACCENT,
                      hover_color=ACCENT_DIM, font=(UI_FONT, 14, "bold"),
                      height=36, width=160, command=self._save
                      ).pack(anchor="w", padx=20, pady=(16, 4))
        self.saved_lbl.pack(anchor="w", padx=20, pady=(0, 8))
        logo_state = "найден ✓" if paths.logo_path() else "не найден"
        ctk.CTkLabel(panel,
                     text=f"Логотип: положите файл logo.png в папку данных ({logo_state}). База данных: crm.db там же:\n{paths.data_dir()}",
                     text_color=MUTED, font=(UI_FONT, 11), justify="left"
                     ).pack(anchor="w", padx=20, pady=(4, 16))
        ctk.CTkLabel(self, text="by bisquare", text_color=MUTED,
                     font=(UI_FONT, 10)).pack(side="bottom", anchor="w", padx=6, pady=4)

    def _save(self):
        for key, entry in self.entries.items():
            db.set_setting(key, entry.get().strip())
        self.saved_lbl.configure(text=f"сохранено ✓ {datetime.now():%H:%M:%S}")