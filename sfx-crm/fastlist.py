# -*- coding: utf-8 -*-
"""FastList — список, нарисованный на одном холсте."""
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from theme import CARD, CARD_HOVER, MUTED, PANEL, TEXT, UI_FONT

PAD_X = 6
IN_X = 10
BTN_W, BTN_H = 30, 26
ROW_GAP = 4
RADIUS = 8


def _rrect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class FastList(ctk.CTkFrame):
    def __init__(self, master, bg=PANEL, empty_text=""):
        super().__init__(master, fg_color="transparent")
        self.bg = bg
        self.empty_text = empty_text
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0,
                                yscrollincrement=1)
        self.sb = ctk.CTkScrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")
        self._parent_canvas = self.canvas
        self._parent_frame = self
        self._orientation = "vertical"

        try:
            scale = ctk.ScalingTracker.get_widget_scaling(self)
        except Exception:
            scale = 1.0

        def px(size):
            return -int(round(size * scale))

        self.f_title = tkfont.Font(family=UI_FONT, size=px(13))
        self.f_title_b = tkfont.Font(family=UI_FONT, size=px(13), weight="bold")
        self.f_sub = tkfont.Font(family=UI_FONT, size=px(11))
        self.f_head = tkfont.Font(family=UI_FONT, size=px(11), weight="bold")
        self.f_btn = tkfont.Font(family=UI_FONT, size=px(15), weight="bold")

        self.rows = []
        self._geom = []
        self._hover = None
        self.selected_key = None
        self._width = 0

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(None))
        self.canvas.bind("<Button-1>", self._on_click)

    def set_rows(self, rows, keep_scroll=False):
        frac = self.canvas.yview()[0] if keep_scroll else 0.0
        self.rows = rows
        self._layout()
        self.canvas.yview_moveto(frac)

    def select(self, key):
        self.selected_key = key
        self._repaint_fills()

    def _on_resize(self, _e):
        w = self.canvas.winfo_width()
        if abs(w - self._width) > 2:
            self._width = w
            self._layout()

    def _layout(self):
        c = self.canvas
        c.delete("all")
        self._geom = []
        self._hover = None
        w = self._width or c.winfo_width()
        if w <= 10:
            return
        y = 4
        for row in self.rows:
            if "header" in row:
                c.create_text(PAD_X + 4, y + 14, text=row["header"],
                              anchor="w", font=self.f_head,
                              fill=row.get("color", MUTED))
                specs, _ = self._button_slots(row.get("buttons", []), w)
                zones = self._paint_buttons(specs, y, 30)
                if zones:
                    # без подложки — заголовок не подсвечивается при наведении
                    self._geom.append((y, y + 30, row, None, zones))
                y += 30
                continue
            btn_specs, bx = self._button_slots(row.get("buttons", []), w)
            text_w = max(bx - PAD_X - IN_X - 8, 60)

            title_font = self.f_title_b if row.get("bold") else self.f_title
            t_id = c.create_text(PAD_X + IN_X, y + 8, text=row.get("title", ""),
                                 anchor="nw", font=title_font, width=text_w,
                                 fill=row.get("title_color", TEXT))
            bb = c.bbox(t_id)
            ty = bb[3]
            s_id = None
            if row.get("sub"):
                s_id = c.create_text(PAD_X + IN_X, ty + 2, text=row["sub"],
                                     anchor="nw", font=self.f_sub, width=text_w,
                                     fill=row.get("sub_color", MUTED))
                ty = c.bbox(s_id)[3]
            row_h = max(ty - y + 8, 40)
            y2 = y + row_h

            bg = _rrect(c, PAD_X, y, w - PAD_X, y2, RADIUS,
                        fill=CARD, outline="")
            c.tag_lower(bg)

            zones = self._paint_buttons(btn_specs, y, row_h)
            self._geom.append((y, y2, row, bg, zones))
            y = y2 + ROW_GAP

        if not self._geom and self.empty_text:
            c.create_text(w / 2, 60, text=self.empty_text, font=self.f_sub,
                          fill=MUTED, width=w - 40, justify="center")
            y = 120
        c.configure(scrollregion=(0, 0, w, y + 4))
        self._repaint_fills()

    def _button_slots(self, buttons, w):
        """Раскладывает кнопки справа налево. Отдаёт спеки и левую границу."""
        bx = w - PAD_X - 6
        specs = []
        for b in buttons:
            x1 = bx - BTN_W
            specs.append((x1, bx, b))
            bx = x1 - 4
        return specs, bx

    def _paint_buttons(self, specs, y, height):
        zones = []
        for x1, x2, b in specs:
            by1 = y + (height - BTN_H) / 2
            by2 = by1 + BTN_H
            if b.get("fill"):
                _rrect(self.canvas, x1, by1, x2, by2, 6, fill=b["fill"], outline="")
            self.canvas.create_text((x1 + x2) / 2, (by1 + by2) / 2, text=b["text"],
                                    font=self.f_btn, fill=b.get("text_color", TEXT))
            zones.append((x1, by1, x2, by2, b["cb"]))
        return zones

    def _fill_for(self, row, hovered):
        if row.get("key") is not None and row["key"] == self.selected_key:
            return CARD_HOVER
        return CARD_HOVER if hovered else CARD

    def _repaint_fills(self):
        for i, (_y1, _y2, row, bg, _z) in enumerate(self._geom):
            if bg is None:  # заголовок категории — подложки нет
                continue
            self.canvas.itemconfig(bg, fill=self._fill_for(row, i == self._hover))

    def _row_at(self, y_canvas):
        for i, (y1, y2, _row, _bg, _zones) in enumerate(self._geom):
            if y1 <= y_canvas <= y2:
                return i
        return None

    def _set_hover(self, i):
        if i == self._hover:
            return
        old, self._hover = self._hover, i
        for idx in (old, i):
            if idx is not None and idx < len(self._geom):
                _y1, _y2, row, bg, _z = self._geom[idx]
                if bg is None:
                    continue
                self.canvas.itemconfig(bg, fill=self._fill_for(row, idx == self._hover))

    def _on_motion(self, e):
        yc = self.canvas.canvasy(e.y)
        i = self._row_at(yc)
        self._set_hover(i)
        cursor = ""
        if i is not None:
            _y1, _y2, row, _bg, zones = self._geom[i]
            over_btn = any(x1 <= e.x <= x2 and y1 <= yc <= y2
                           for x1, y1, x2, y2, _cb in zones)
            if over_btn or row.get("on_click"):
                cursor = "hand2"
        if self.canvas["cursor"] != cursor:
            self.canvas.configure(cursor=cursor)

    def _on_click(self, e):
        yc = self.canvas.canvasy(e.y)
        i = self._row_at(yc)
        if i is None:
            return
        _y1, _y2, row, _bg, zones = self._geom[i]
        for x1, y1, x2, y2, cb in zones:
            if x1 <= e.x <= x2 and y1 <= yc <= y2:
                cb()
                return
        if row.get("on_click"):
            row["on_click"]()