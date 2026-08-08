# -*- coding: utf-8 -*-
"""Выгрузка сметы в PDF (reportlab)."""
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

import paths
from excel_io import parse_date
from theme import fmt_money, fmt_qty

_registered = False

_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]


def _register_fonts():
    global _registered
    if _registered:
        return
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("Arial", regular))
            pdfmetrics.registerFont(TTFont("Arial-Bold", bold))
            _registered = True
            return
    raise FileNotFoundError("Не найден шрифт Arial с кириллицей для PDF")


def export_pdf(path, project, company=None, totals=None):
    _register_fonts()
    company = company or {}

    st = ParagraphStyle("base", fontName="Arial", fontSize=9, leading=12)
    st_muted = ParagraphStyle("muted", parent=st, textColor=colors.HexColor("#707070"))
    st_h1 = ParagraphStyle("h1", fontName="Arial-Bold", fontSize=14, leading=18)
    st_h2 = ParagraphStyle("h2", fontName="Arial-Bold", fontSize=11, leading=14,
                           spaceBefore=10)
    st_right = ParagraphStyle("right", parent=st, alignment=2)

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=15*mm,
                            rightMargin=15*mm, topMargin=14*mm,
                            bottomMargin=14*mm, title=project["name"])
    story = []

    logo = paths.logo_path()
    if company.get("company_name"):
        head_text = [Paragraph(company["company_name"],
                               ParagraphStyle("c", parent=st_h1, fontSize=12))]
        contacts = " · ".join(x for x in (company.get("company_phone"),
                                          company.get("company_email")) if x)
        if contacts:
            head_text.append(Paragraph(contacts, st_muted))
        if company.get("company_extra"):
            head_text.append(Paragraph(company["company_extra"], st_muted))
        if logo:
            try:
                img = Image(logo)
                scale = (14 * mm) / img.imageHeight
                img.drawHeight = img.imageHeight * scale
                img.drawWidth = img.imageWidth * scale
                head = Table([[head_text, img]], colWidths=[None, 40*mm])
                head.setStyle(TableStyle([
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ("ALIGN", (1,0), (1,0), "RIGHT"),
                    ("LEFTPADDING", (0,0), (-1,-1), 0),
                    ("RIGHTPADDING", (0,0), (-1,-1), 0),
                ]))
                story.append(head)
            except Exception:
                story.extend(head_text)
        else:
            story.extend(head_text)
        story.append(Spacer(1, 6*mm))

    title = project["name"] + (f" — {project['client']}" if project.get("client") else "")
    story.append(Paragraph(title, st_h1))
    story.append(Paragraph(
        f"Смета от {datetime.now():%d.%m.%Y} · статус: "
        f"{project.get('status', 'предварительная')}", st_muted))
    story.append(Spacer(1, 4*mm))

    col_w = [None, 22*mm, 16*mm, 12*mm, 24*mm]
    grid = TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Arial"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("FONTNAME", (0,0), (-1,0), "Arial-Bold"),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F2F2")),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("LINEBELOW", (0,0), (-1,0), 0.5, colors.HexColor("#BFBFBF")),
        ("LINEABOVE", (0,-1), (-1,-1), 0.5, colors.HexColor("#BFBFBF")),
        ("FONTNAME", (0,-1), (-1,-1), "Arial-Bold"),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ])

    for day in project["days"]:
        lines = day["lines"]
        if not lines:
            continue
        d = parse_date(day["label"])
        label = d.strftime("%d.%m.%Y") if d else day["label"]
        story.append(Paragraph(label, st_h2))
        if day.get("note"):
            story.append(Paragraph(day["note"], st_muted))
        data = [["Наименование", "Цена", "Кол-во", "Ед.", "Стоимость"]]
        day_total = 0.0
        for ln in lines:
            is_ot = bool(ln.get("ot"))
            cost = ln["price"] * ln["qty"]
            day_total += cost
            data.append([
                Paragraph(ln["name"] + (" — переработка" if is_ot else ""), st),
                fmt_money(ln["price"]).replace(" ₽", ""),
                fmt_qty(ln["qty"]),
                "ч" if is_ot else ln.get("unit", "шт"),
                fmt_money(cost).replace(" ₽", ""),
            ])
        data.append(["", "", "", "", fmt_money(day_total)])
        t = Table(data, colWidths=col_w, repeatRows=1)
        t.setStyle(grid)
        story.append(t)

    if totals:
        story.append(Spacer(1, 6*mm))
        rows = [
            ("Позиции, без учёта налога и переработок", fmt_money(totals["positions"])),
            ("Переработки", fmt_money(totals["overtime"])),
            ("Итого до налога", fmt_money(totals["before_tax"])),
            (f"Налог {project.get('tax') or 0:g}%", fmt_money(totals["tax_amount"])),
            ("ИТОГО", fmt_money(totals["final"])),
        ]
        st_b = ParagraphStyle("b", parent=st, fontName="Arial-Bold", fontSize=11)
        st_rb = ParagraphStyle("rb", parent=st_right, fontName="Arial-Bold", fontSize=11)
        data = [[Paragraph(n, st), Paragraph(v, st_right)] for n, v in rows[:-1]]
        data.append([Paragraph(rows[-1][0], st_b), Paragraph(rows[-1][1], st_rb)])
        t = Table(data, colWidths=[None, 40*mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), "Arial"),
            ("FONTNAME", (0,-1), (-1,-1), "Arial-Bold"),
            ("LINEABOVE", (0,-1), (-1,-1), 1, colors.HexColor("#404040")),
            ("TOPPADDING", (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]))
        story.append(t)

    doc.build(story)