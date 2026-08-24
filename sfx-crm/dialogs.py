# -*- coding: utf-8 -*-
"""Диалоговые окна."""
import customtkinter as ctk
from theme import (ACCENT, ACCENT_DIM, CARD, CARD_HOVER, GREEN, MUTED, PANEL,
                   RED, TEXT, UI_FONT, UNITS, fmt_qty, parse_num)


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

    def _fit_height(self, width):
        """Высота по содержимому: на macOS шрифты выше, чем на Windows,
        и при жёсткой высоте нижние кнопки уезжают за край неизменяемого окна."""
        self.update_idletasks()
        self.geometry(f"{width}x{self.winfo_reqheight() + 4}")

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


class CategoryDialog(_Dialog):
    """Создание или переименование категории каталога."""

    def __init__(self, master, value=""):
        super().__init__(master,
                         "Переименовать категорию" if value else "Новая категория",
                         380, 190)
        self._label("Название категории", pady=(18, 2))
        self.name_entry = self._entry("например: Пиротехника", value)
        self._ok_button("Сохранить" if value else "Добавить")
        self.after(150, self.name_entry.focus)

    def _ok(self):
        name = self.name_entry.get().strip()
        if name:
            self.result = name
        self.destroy()


class ItemDialog(_Dialog):
    """Позиция каталога вручную, без Excel.

    on_save(data) вызывается при сохранении и возвращает текст ошибки либо None.
    В режиме добавления окно остаётся открытым, чтобы вводить позиции подряд.
    """

    def __init__(self, master, categories, on_save, item=None, default_category=""):
        self.editing = item is not None
        super().__init__(master,
                         "Правка позиции" if self.editing else "Новая позиция",
                         400, 470)
        self.on_save = on_save
        item = item or {}

        self._label("Название", pady=(16, 2))
        self.name_entry = self._entry("например: Дым-машина", item.get("name", ""))

        self._label("Категория")
        values = categories or ["Оборудование"]
        self.cat = ctk.CTkComboBox(self, values=values, fg_color=CARD,
                                   border_color=CARD, button_color=CARD,
                                   button_hover_color=CARD_HOVER,
                                   font=(UI_FONT, 14))
        self.cat.set(item.get("category") or default_category or values[0])
        self.cat.pack(fill="x", padx=20)

        self._label("Цена, ₽")
        self.price_entry = self._entry(
            "0", fmt_qty(item["price"]) if "price" in item else "0")

        self._label("Единица")
        self.unit = ctk.CTkOptionMenu(self, values=UNITS, fg_color=CARD,
                                      button_color=CARD,
                                      button_hover_color=CARD_HOVER,
                                      font=(UI_FONT, 14))
        self.unit.set(item.get("unit") or "шт")
        self.unit.pack(fill="x", padx=20)

        self._label("Склад, шт (пусто — не отслеживать)")
        stock = item.get("stock")
        self.stock_entry = self._entry(
            "—", fmt_qty(stock) if stock is not None else "")

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkButton(bar, text="Сохранить" if self.editing else "Добавить",
                      fg_color=ACCENT, hover_color=ACCENT_DIM,
                      font=(UI_FONT, 14, "bold"), height=38,
                      command=self._ok).pack(side="left", fill="x", expand=True)
        if not self.editing:
            ctk.CTkButton(bar, text="Готово", fg_color=CARD,
                          hover_color=CARD_HOVER, text_color=TEXT,
                          font=(UI_FONT, 14), height=38, width=90,
                          command=self.destroy).pack(side="left", padx=(8, 0))

        self.status = ctk.CTkLabel(self, text="", text_color=MUTED,
                                   font=(UI_FONT, 11), anchor="w")
        self.status.pack(fill="x", padx=20, pady=(0, 10))
        self._fit_height(400)
        self.after(150, self.name_entry.focus)

    def _collect(self):
        """Читает поля; при ошибке подсвечивает поле и возвращает None."""
        name = self.name_entry.get().strip()
        category = self.cat.get().strip()
        price = parse_num(self.price_entry.get())
        stock_text = self.stock_entry.get().strip()
        stock = None if not stock_text else parse_num(stock_text)

        self.name_entry.configure(border_color=CARD if name else RED)
        self.price_entry.configure(border_color=CARD if price is not None else RED)
        self.stock_entry.configure(
            border_color=RED if (stock_text and stock is None) else CARD)

        if not name:
            return self._fail("Укажите название позиции")
        if not category:
            return self._fail("Укажите категорию")
        if price is None:
            return self._fail("Цена должна быть числом")
        if stock_text and stock is None:
            return self._fail("Склад должен быть числом или пустым")
        return {"name": name, "category": category, "price": price,
                "unit": self.unit.get(), "stock": stock}

    def _fail(self, message):
        self.status.configure(text=message, text_color=RED)
        return None

    def _ok(self):
        data = self._collect()
        if data is None:
            return
        error = self.on_save(data)
        if error:
            self._fail(error)
            return
        self.result = data
        if self.editing:
            self.destroy()
            return
        # добавление подряд: категорию и единицу оставляем, остальное чистим
        self.status.configure(text=f"добавлено: {data['name']}", text_color=GREEN)
        self.name_entry.delete(0, "end")
        self.price_entry.delete(0, "end")
        self.price_entry.insert(0, "0")
        self.stock_entry.delete(0, "end")
        self.name_entry.focus()