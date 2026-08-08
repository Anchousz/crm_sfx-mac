# -*- coding: utf-8 -*-
"""Палитра, форматирование и плавная прокрутка."""
import sys

import customtkinter as ctk

IS_MAC = sys.platform == "darwin"
UI_FONT = "Helvetica Neue" if IS_MAC else "Segoe UI"
WHEEL_PX = 8.0 if IS_MAC else 0.6

BG = "#0f1014"
PANEL = "#17181f"
CARD = "#1e2029"
CARD_HOVER = "#262936"
ACCENT = "#ff6b2c"
ACCENT_DIM = "#c94f1c"
TEXT = "#ececf1"
MUTED = "#8b8d98"
GREEN = "#4ade80"
RED = "#f87171"
BLUE = "#60a5fa"
YELLOW = "#fbbf24"

STATUSES = ["предварительная", "финальная", "оплачена"]
STATUS_COLORS = {"предварительная": YELLOW, "финальная": BLUE, "оплачена": GREEN}
UNITS = ["шт", "л", "км", "ч", "смена", "кв.м", "кг"]


def fmt_money(v):
    s = f"{v:,.0f}".replace(",", " ")
    return f"{s} ₽"


def fmt_qty(v):
    return f"{v:g}"


def parse_num(text):
    try:
        return float(str(text).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


SCROLL_TICK_MS = 10
SCROLL_EASE = 0.35
SCROLL_STATS = {"ticks": 0, "steps": []}


def install_smooth_scroll(root):
    import time as _time

    frames = []

    def collect(widget):
        for child in widget.winfo_children():
            if hasattr(child, "_parent_canvas") and hasattr(child, "_parent_frame"):
                frames.append(child)
            collect(child)

    collect(root)
    for sf in frames:
        sf._parent_canvas.configure(yscrollincrement=1, xscrollincrement=1)

    def frame_under_pointer(x_root, y_root):
        try:
            w = root.winfo_containing(x_root, y_root)
        except (KeyError, TypeError):
            return None
        if w is None:
            return None
        path = str(w)
        best = None
        for sf in frames:
            if not sf.winfo_exists():
                continue
            prefix = str(sf._parent_frame)
            if path == prefix or path.startswith(prefix + "."):
                if best is None or len(prefix) > len(str(best._parent_frame)):
                    best = sf
        return best

    s = {"rem_x": 0.0, "rem_y": 0.0, "sf": None, "job": None,
         "px": 0, "py": 0, "probe_ts": 0.0}

    def resolve_target(event):
        now = _time.monotonic()
        sf = s["sf"]
        if (sf is not None and sf.winfo_exists()
                and abs(event.x_root - s["px"]) < 40
                and abs(event.y_root - s["py"]) < 40
                and now - s["probe_ts"] < 0.25):
            s["probe_ts"] = now
            return sf
        s["probe_ts"] = now
        return frame_under_pointer(event.x_root, event.y_root)

    def tick():
        s["job"] = None
        sf = s["sf"]
        if sf is None or not sf.winfo_exists():
            s["rem_x"] = s["rem_y"] = 0.0
            return
        canvas = sf._parent_canvas
        active = False
        for rem_key, view, do_scroll in (
                ("rem_y", canvas.yview, canvas.yview_scroll),
                ("rem_x", canvas.xview, canvas.xview_scroll)):
            rem = s[rem_key]
            if abs(rem) < 0.5:
                s[rem_key] = 0.0
                continue
            if view() == (0.0, 1.0):
                s[rem_key] = 0.0
                continue
            step = rem * SCROLL_EASE
            step = int(step) or (1 if rem > 0 else -1)
            do_scroll(step, "units")
            s[rem_key] = rem - step
            active = True
            SCROLL_STATS["ticks"] += 1
            SCROLL_STATS["steps"].append((_time.monotonic(), step))
        if active:
            s["job"] = root.after(SCROLL_TICK_MS, tick)

    def queue_scroll(px, horizontal, event):
        sf = resolve_target(event)
        if sf is None:
            return
        if sf is not s["sf"]:
            s["rem_x"] = s["rem_y"] = 0.0
            s["sf"] = sf
        s["px"], s["py"] = event.x_root, event.y_root
        if getattr(sf, "_orientation", "vertical") == "horizontal":
            horizontal = True
        s["rem_x" if horizontal else "rem_y"] -= px
        if s["job"] is None:
            tick()

    def on_wheel(event):
        px = event.delta * WHEEL_PX
        if 0 < abs(px) < 1:
            px = 1 if px > 0 else -1
        queue_scroll(px, bool(event.state & 0x1), event)
        return "break"

    root.unbind_all("<MouseWheel>")
    root.unbind_all("<Shift-MouseWheel>")
    root.bind_all("<MouseWheel>", on_wheel)
    root.bind_all("<Shift-MouseWheel>", on_wheel)

    def on_touchpad(event):
        d = event.delta
        dy = d & 0xFFFF
        if dy >= 0x8000:
            dy -= 0x10000
        dx = d >> 16
        if dy:
            queue_scroll(dy, False, event)
        if dx:
            queue_scroll(dx, True, event)
        return "break"

    try:
        root.unbind_all("<TouchpadScroll>")
        root.bind_all("<TouchpadScroll>", on_touchpad)
    except Exception:
        pass