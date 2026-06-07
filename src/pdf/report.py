"""Генерация PDF-отчёта прогноза (ReportLab).

Кириллица — через TTF-шрифт (Arial на Windows / DejaVuSans в Docker/Linux).
"""

from __future__ import annotations

import os
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.services.report_data import BracketMatch, GroupTable, ReportData

# --- Палитра ---
HEADER_BG = colors.HexColor("#14532d")
HEADER_FG = colors.white
QUAL_BG = colors.HexColor("#bbf7d0")
THIRD_BG = colors.HexColor("#fde68a")
ALT_BG = colors.HexColor("#f1f5f9")
GOLD = colors.HexColor("#fcd34d")
SILVER = colors.HexColor("#e5e7eb")
BRONZE = colors.HexColor("#fcc89b")
GRID = colors.HexColor("#cbd5e1")

# --- Шрифты ---
_FONT_CANDIDATES: list[tuple[str, str]] = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
]
_registered: tuple[str, str] | None = None


def _fonts() -> tuple[str, str]:
    global _registered
    if _registered is not None:
        return _registered
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            pdfmetrics.registerFont(TTFont("Main", regular))
            if os.path.exists(bold):
                pdfmetrics.registerFont(TTFont("Main-Bold", bold))
                _registered = ("Main", "Main-Bold")
            else:
                _registered = ("Main", "Main")
            return _registered
    _registered = ("Helvetica", "Helvetica-Bold")
    return _registered


def _styles() -> dict[str, ParagraphStyle]:
    main, bold = _fonts()
    return {
        "title": ParagraphStyle(
            "title", fontName=bold, fontSize=22, alignment=TA_CENTER,
            textColor=HEADER_BG, spaceAfter=14, leading=26,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=main, fontSize=11, alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"), spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", fontName=bold, fontSize=14, textColor=HEADER_BG,
            spaceBefore=14, spaceAfter=6,
        ),
        "groupname": ParagraphStyle("groupname", fontName=bold, fontSize=10),
        "normal": ParagraphStyle("normal", fontName=main, fontSize=9),
    }


def _group_block(g: GroupTable, st: dict[str, ParagraphStyle]) -> Table:
    main, bold = _fonts()
    rows = [["", f"Группа {g.letter}", "И", "О", "РМ"]]
    for i, r in enumerate(g.rows, start=1):
        rows.append([str(i), r.team_name[:18], str(r.played), str(r.points),
                     f"{r.gd:+d}"])
    tbl = Table(rows, colWidths=[0.6 * cm, 4.3 * cm, 0.9 * cm, 0.9 * cm, 1.0 * cm])
    style = [
        ("FONTNAME", (0, 0), (-1, -1), main),
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    # Подсветка: 1-2 место зелёным, 3-е жёлтым.
    if len(g.rows) >= 1:
        style.append(("BACKGROUND", (0, 1), (-1, 1), QUAL_BG))
    if len(g.rows) >= 2:
        style.append(("BACKGROUND", (0, 2), (-1, 2), QUAL_BG))
    if len(g.rows) >= 3:
        style.append(("BACKGROUND", (0, 3), (-1, 3), THIRD_BG))
    tbl.setStyle(TableStyle(style))
    return tbl


def _two_column(blocks: list[Table]) -> Table:
    """Разложить блоки групп в 2 колонки."""
    grid = []
    for i in range(0, len(blocks), 2):
        pair = blocks[i : i + 2]
        if len(pair) == 1:
            pair.append("")
        grid.append(pair)
    outer = Table(grid, colWidths=[8.7 * cm, 8.7 * cm])
    outer.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return outer


def _round_table(matches: list[BracketMatch]) -> Table:
    main, bold = _fonts()
    rows = []
    for m in matches:
        score = (
            f"{m.home_score}:{m.away_score}"
            if m.home_score is not None
            else "—"
        )
        rows.append([m.home, score, m.away, f"→ {m.winner or '—'}"])
    tbl = Table(rows, colWidths=[5.3 * cm, 1.4 * cm, 5.3 * cm, 5.4 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), main),
                ("FONTNAME", (3, 0), (3, -1), bold),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ALT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return tbl


def _podium(data: ReportData) -> Table:
    main, bold = _fonts()
    rows = [
        ["Чемпион мира", data.champion],
        ["Финалист", data.runner_up],
        ["3-е место", data.third_place],
    ]
    tbl = Table(rows, colWidths=[5 * cm, 12.4 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), bold),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (0, 0), GOLD),
                ("BACKGROUND", (0, 1), (0, 1), SILVER),
                ("BACKGROUND", (0, 2), (0, 2), BRONZE),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tbl


def _awards_table(awards: list[tuple[str, str]]) -> Table:
    main, bold = _fonts()
    tbl = Table(awards, colWidths=[7 * cm, 10.4 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), main),
                ("FONTNAME", (1, 0), (1, -1), bold),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ALT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tbl


PITCH_GREEN = colors.HexColor("#2f7d4f")


def _short(name: str, n: int = 13) -> str:
    return name if len(name) <= n else name[: n - 1] + "…"


# Порядок матчей сетки сверху вниз (левая и правая половины) — для визуальной сетки.
_LEAF_R32 = [74, 77, 73, 75, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87]
_R16 = [89, 90, 93, 94, 91, 92, 95, 96]
_QF = [97, 98, 99, 100]
_SF = [101, 102]


def _bracket_table(bracket: dict) -> Table:
    """Визуальная сетка плей-офф: победители сходятся к финалу (объединённые ячейки)."""
    main, bold = _fonts()

    def w(num: int) -> str:
        bm = bracket.get(num)
        return _short(bm.winner) if bm and bm.winner else "—"

    header = ["1/16", "1/8", "1/4", "1/2", "Финал"]
    grid = [header] + [["", "", "", "", ""] for _ in range(16)]
    for i, num in enumerate(_LEAF_R32):
        grid[1 + i][0] = w(num)
    for i, num in enumerate(_R16):
        grid[1 + i * 2][1] = w(num)
    for i, num in enumerate(_QF):
        grid[1 + i * 4][2] = w(num)
    for i, num in enumerate(_SF):
        grid[1 + i * 8][3] = w(num)
    grid[1][4] = w(104)

    style = [
        ("FONTNAME", (0, 0), (-1, -1), main),
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
        ("GRID", (0, 1), (-1, -1), 0.4, GRID),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, HEADER_BG),
        ("TOPPADDING", (0, 1), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 1),
    ]
    for i in range(8):
        style.append(("SPAN", (1, 1 + i * 2), (1, 2 + i * 2)))
    for i in range(4):
        style.append(("SPAN", (2, 1 + i * 4), (2, 4 + i * 4)))
    for i in range(2):
        style.append(("SPAN", (3, 1 + i * 8), (3, 8 + i * 8)))
    style.append(("SPAN", (4, 1), (4, 16)))
    style.append(("BACKGROUND", (4, 1), (4, 16), GOLD))
    style.append(("FONTNAME", (4, 1), (4, 16), bold))

    tbl = Table(
        grid, colWidths=[3.8 * cm, 3.6 * cm, 3.4 * cm, 3.4 * cm, 3.2 * cm]
    )
    tbl.setStyle(TableStyle(style))
    return tbl


class Pitch(Flowable):
    """Футбольное поле со схемой символической сборной (линии снизу вверх: GK→FW)."""

    def __init__(self, lines: list[tuple[str, list[str]]], width: float, height: float):
        super().__init__()
        self.lines = lines
        self.width = width
        self.height = height

    def wrap(self, aW, aH):  # noqa: N803 (reportlab API)
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        main, _bold = _fonts()
        w, h = self.width, self.height
        # Поле.
        c.setFillColor(PITCH_GREEN)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setStrokeColor(colors.white)
        c.setLineWidth(1)
        c.rect(8, 8, w - 16, h - 16, fill=0)
        c.line(8, h / 2, w - 8, h / 2)
        c.circle(w / 2, h / 2, 1.1 * cm, fill=0)
        # Линии: GK снизу, нападающие сверху.
        row_fy = [0.13, 0.37, 0.61, 0.85]
        for (_label, names), fy in zip(self.lines, row_fy, strict=False):
            y = h * fy
            count = len(names) or 1
            for i, nm in enumerate(names):
                x = w * (i + 1) / (count + 1)
                c.setFillColor(colors.white)
                c.circle(x, y + 0.32 * cm, 0.16 * cm, fill=1, stroke=0)
                c.setFont(main, 7.5)
                c.drawCentredString(x, y - 0.18 * cm, _short(nm, 16))


def render(data: ReportData) -> bytes:
    """Сформировать PDF-отчёт и вернуть его как байты."""
    st = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title="Прогноз ЧМ-2026",
    )
    story: list = [
        Paragraph("Прогноз Чемпионата мира 2026", st["title"]),
        Paragraph(f"Пользователь: {escape(str(data.username))} · {data.created}", st["subtitle"]),
        _podium(data),
        Paragraph("Групповой этап", st["h2"]),
        _two_column([_group_block(g, st) for g in data.groups]),
    ]

    story.append(Paragraph("Плей-офф", st["h2"]))
    if data.bracket:
        story.append(
            KeepTogether(
                [
                    Paragraph("Сетка (кто проходит дальше):", st["groupname"]),
                    Spacer(1, 3),
                    _bracket_table(data.bracket),
                    Spacer(1, 10),
                ]
            )
        )
    story.append(Paragraph("Результаты по раундам:", st["groupname"]))
    for round_name, matches in data.rounds:
        story.append(
            KeepTogether(
                [
                    Spacer(1, 4),
                    Paragraph(round_name, st["groupname"]),
                    Spacer(1, 2),
                    _round_table(matches),
                ]
            )
        )

    story.append(Paragraph("Награды", st["h2"]))
    story.append(_awards_table(data.awards))

    story.append(Paragraph("Символическая сборная (4-3-3)", st["h2"]))
    story.append(Pitch(data.tot, width=17.4 * cm, height=9.5 * cm))

    doc.build(story)
    return buf.getvalue()
