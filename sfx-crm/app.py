# -*- coding: utf-8 -*-
"""SFX CRM — сметы на спецэффекты.

Запуск:  python app.py
"""
import os
import sys
import traceback
from datetime import datetime


def _crash_log_path():
    """Не зависит от paths/db — работает, даже если сами эти модули не импортировались."""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/SFX CRM")
    elif os.environ.get("APPDATA"):
        base = os.path.join(os.environ["APPDATA"], "SFX CRM")
    else:
        base = os.path.expanduser("~/.sfx-crm")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "crash.log")


def _log_crash(text):
    log = _crash_log_path()
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{text}")
    except OSError:
        pass
    return log


def _report_crash(exc_type, exc, tb):
    """В собранном exe нет консоли — пишем в crash.log и показываем окно."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    log = _log_crash(text)
    try:
        from tkinter import messagebox
        messagebox.showerror(
            "SFX CRM — ошибка",
            f"Произошла ошибка:\n{exc}\n\nПодробности: {log}")
    except Exception:
        pass


sys.excepthook = _report_crash

try:
    import customtkinter as ctk

    import db
    import paths
    from theme import (ACCENT, BG, CARD, CARD_HOVER, MUTED, PANEL, TEXT, UI_FONT,
                       install_smooth_scroll)
    from views import (CalendarView, CatalogView, EstimateView, ProjectsView,
                       SettingsView)
except Exception:
    # Импорт мог упасть ДО того, как sys.excepthook вызовется для верхнего уровня
    # (в замороженном .app эта ошибка иначе просто теряется без единого следа).
    _report_crash(*sys.exc_info())
    raise

ctk.set_appearance_mode("dark")

VERSION = "3.1"

NAV = [("estimate", "Смета"),
       ("projects", "Проекты"),
       ("calendar", "Календарь"),
       ("catalog", "Каталог и цены"),
       ("settings", "Настройки")]


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.title("SFX CRM — сметы на спецэффекты")
        self.geometry("1380x820")
        self.minsize(1150, 700)
        icon = paths.resource("assets", "icon.icns")  # для macOS
        if sys.platform == "darwin" and os.path.exists(icon):
            try:
                self.iconbitmap(icon)  # на маке работает с .icns
            except:
                pass

        sidebar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text="SFX CRM", text_color=ACCENT,
                     font=(UI_FONT, 22, "bold")).pack(pady=(24, 2))
        ctk.CTkLabel(sidebar, text="спецэффекты · сметы", text_color=MUTED,
                     font=(UI_FONT, 11)).pack(pady=(0, 24))

        self.nav_buttons = {}
        for key, label in NAV:
            btn = ctk.CTkButton(sidebar, text=label, anchor="w", height=40,
                                corner_radius=10, fg_color="transparent",
                                hover_color=CARD_HOVER, text_color=TEXT,
                                font=(UI_FONT, 14),
                                command=lambda k=key: self.show(k))
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = btn
        ctk.CTkLabel(sidebar, text=f"версия {VERSION}", text_color=MUTED,
                     font=(UI_FONT, 10)).pack(side="bottom", pady=14)

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True, padx=14, pady=14)

        self.estimate_view = EstimateView(self.content, self)
        self.projects_view = ProjectsView(self.content, self)
        self.calendar_view = CalendarView(self.content, self)
        self.catalog_view = CatalogView(self.content, self)
        self.settings_view = SettingsView(self.content, self)
        self.views = {"estimate": self.estimate_view,
                      "projects": self.projects_view,
                      "calendar": self.calendar_view,
                      "catalog": self.catalog_view,
                      "settings": self.settings_view}
        self.show("estimate")
        install_smooth_scroll(self)

    def show(self, key):
        for k, v in self.views.items():
            v.pack_forget()
            self.nav_buttons[k].configure(
                fg_color=CARD if k == key else "transparent",
                text_color=ACCENT if k == key else TEXT)
        view = self.views[key]
        if hasattr(view, "on_show"):
            view.on_show()
        view.pack(fill="both", expand=True)

    def report_callback_exception(self, exc_type, exc, tb):
        _report_crash(exc_type, exc, tb)


def main():
    db.init_db()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()