# -*- coding: utf-8 -*-
"""Диалоговые окна."""
import customtkinter as ctk
from theme import ACCENT, ACCENT_DIM, CARD, MUTED, PANEL, UI_FONT, parse_num


class _Dialog(ctk.CTkToplevel):
    def __init__(self, master, title, width=380, height=240):
        super().__init__(master, fg_color=PANEL)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(120, self.grab_set)

    def _label(self, text, pady=(12, 2)):
        ctk.CTkLabel(self, text=text, text_color=MUTED,
                     font=(UI_FONT, 12)).pack(anchor="w", padx=20, pady=pady)

    def _entry(self, placeholder="", value=""):
        e = ctk.CTkEntry(self, fg_color=CARD, border_color=CARD,
                         placeholder_text=placeholder, font=(UI_FONT, 14))
        if value:
            e.insert(0, value)
        e.pack(fill="x", padx=20)
        return e

    def _ok_button(self, text="Добавить"):
        ctk.CTkButton(self, text=text, fg_color=ACCENT, hover_color=ACCENT_DIM,
                      font=(UI_FONT, 14, "bold"), height=38,
                      command=self._ok).pack(fill="x", padx=20, pady=16)

    def _ok(self):
        raise NotImplementedError


class AddDayDialog(_Dialog):
    def __init__(self, master, default_date):
        super().__init__(master, "Добавить день", 380, 250)
        self._label("Дата смены (ДД.ММ.ГГГГ)", pady=(18, 2))
        self.date_entry = self._entry(value=default_date)
        self._label("…или название этапа")
        self.label_entry = self._entry("например: освоение, закупка материала")
        self._ok_button()
        self.after(150, self.date_entry.focus)

    def _ok(self):
        label = self.label_entry.get().strip() or self.date_entry.get().strip()
        if label:
            self.result = label
        self.destroy()


class OvertimeDialog(_Dialog):
    def __init__(self, master, personnel_names):
        super().__init__(master, "Переработка", 380, 300)
        self._label("Кто (позиция)", pady=(16, 2))
        values = personnel_names or ["Постановщик SFX"]
        self.who = ctk.CTkComboBox(self, values=values, fg_color=CARD,
                                   border_color=CARD, button_color=CARD,
                                   font=(UI_FONT, 14))
        self.who.set(values[0])
        self.who.pack(fill="x", padx=20)
        self._label("Ставка за час, ₽")
        self.rate = self._entry(value="1000")
        self._label("Часов")
        self.hours = self._entry(value="1")
        self._ok_button()

    def _ok(self):
        rate = parse_num(self.rate.get())
        hours = parse_num(self.hours.get())
        who = self.who.get().strip()
        if who and rate is not None and hours is not None:
            self.result = {"name": who, "price": rate, "qty": hours, "ot": True}
        self.destroy()


class SavePresetDialog(_Dialog):
    def __init__(self, master, default_name):
        super().__init__(master, "Новый комплект", 380, 190)
        self._label("Название комплекта", pady=(18, 2))
        self.name_entry = self._entry("например: Дождь стандарт", default_name)
        self._ok_button("Сохранить")
        self.after(150, self.name_entry.focus)

    def _ok(self):
        name = self.name_entry.get().strip()
        if name:
            self.result = name
        self.destroy()