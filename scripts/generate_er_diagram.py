#!/usr/bin/env python3

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path


FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}

BG = (247, 249, 252)
TABLE_BG = (255, 255, 255)
TABLE_ALT = (247, 250, 255)
HEADER_BG = (24, 61, 104)
HEADER_TEXT = (255, 255, 255)
BORDER = (38, 57, 77)
TEXT = (33, 42, 56)
SUBTLE = (107, 124, 145)
SHADOW = (226, 232, 240)
LINE_COLORS = [
    (52, 152, 219),
    (46, 204, 113),
    (230, 126, 34),
    (155, 89, 182),
    (231, 76, 60),
    (22, 160, 133),
    (52, 73, 94),
]

FONT_SCALE = 2
CHAR_WIDTH = 5
CHAR_HEIGHT = 7
CHAR_SPACING = 1
TEXT_HEIGHT = CHAR_HEIGHT * FONT_SCALE
ROW_HEIGHT = 24
HEADER_HEIGHT = 34
PADDING_X = 16
TOP_MARGIN = 160
LEFT_MARGIN = 70
COLUMN_GAP = 260
STACK_GAP = 90
CANVAS_RIGHT_MARGIN = 180
CANVAS_BOTTOM_MARGIN = 120

LEFT_COLUMN = ["users", "alerts", "notifications"]
CENTER_COLUMN = ["items", "bids", "autobids"]
RIGHT_COLUMN = ["categories", "questions", "answers"]
TABLE_ORDER = LEFT_COLUMN + CENTER_COLUMN + RIGHT_COLUMN


@dataclass
class Column:
    name: str
    sql_type: str
    is_primary: bool = False
    foreign_key: tuple[str, str] | None = None


@dataclass
class Table:
    name: str
    columns: list[Column]


@dataclass
class TableLayout:
    table: Table
    labels: list[str]
    x: int
    y: int
    width: int
    height: int
    row_lookup: dict[str, int]


class Canvas:
    def __init__(self, width: int, height: int, background: tuple[int, int, int]) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(width * height * 3)
        r, g, b = background
        for index in range(0, len(self.pixels), 3):
            self.pixels[index] = r
            self.pixels[index + 1] = g
            self.pixels[index + 2] = b

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = (y * self.width + x) * 3
            self.pixels[index:index + 3] = bytes(color)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
        start_x = max(x, 0)
        start_y = max(y, 0)
        end_x = min(x + width, self.width)
        end_y = min(y + height, self.height)
        if start_x >= end_x or start_y >= end_y:
            return
        row = bytes(color) * (end_x - start_x)
        for py in range(start_y, end_y):
            index = (py * self.width + start_x) * 3
            self.pixels[index:index + len(row)] = row

    def draw_rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int], thickness: int = 1) -> None:
        self.fill_rect(x, y, width, thickness, color)
        self.fill_rect(x, y + height - thickness, width, thickness, color)
        self.fill_rect(x, y, thickness, height, color)
        self.fill_rect(x + width - thickness, y, thickness, height, color)

    def draw_segment(self, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int], thickness: int = 4) -> None:
        x1, y1 = start
        x2, y2 = end
        if x1 == x2:
            top = min(y1, y2)
            self.fill_rect(x1 - thickness // 2, top, thickness, abs(y2 - y1) + 1, color)
            return
        if y1 == y2:
            left = min(x1, x2)
            self.fill_rect(left, y1 - thickness // 2, abs(x2 - x1) + 1, thickness, color)
            return
        steps = max(abs(x2 - x1), abs(y2 - y1))
        for step in range(steps + 1):
            x = round(x1 + (x2 - x1) * step / steps)
            y = round(y1 + (y2 - y1) * step / steps)
            self.fill_rect(x - thickness // 2, y - thickness // 2, thickness, thickness, color)

    def draw_path(self, points: list[tuple[int, int]], color: tuple[int, int, int], thickness: int = 4) -> None:
        for start, end in zip(points, points[1:]):
            self.draw_segment(start, end, color, thickness)

    def draw_circle(self, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    self.set_pixel(cx + dx, cy + dy, color)

    def draw_text(self, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = FONT_SCALE) -> None:
        cursor = x
        for char in text:
            glyph = FONT.get(char, FONT[" "])
            for row_index, row in enumerate(glyph):
                for col_index, value in enumerate(row):
                    if value == "1":
                        self.fill_rect(
                            cursor + col_index * scale,
                            y + row_index * scale,
                            scale,
                            scale,
                            color,
                        )
            cursor += (CHAR_WIDTH + CHAR_SPACING) * scale

    def save_png(self, path: Path) -> None:
        raw = bytearray()
        row_bytes = self.width * 3
        for row in range(self.height):
            raw.append(0)
            start = row * row_bytes
            raw.extend(self.pixels[start:start + row_bytes])

        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + chunk_type
                + data
                + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
            )

        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        payload = [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", ihdr),
            chunk(b"IDAT", zlib.compress(bytes(raw), level=9)),
            chunk(b"IEND", b""),
        ]
        path.write_bytes(b"".join(payload))


def normalize_type(sql_type: str) -> str:
    sql_type = sql_type.lower()
    if sql_type.startswith("varchar"):
        return "VARCHAR"
    if sql_type.startswith("datetime"):
        return "DATETIME"
    if sql_type.startswith("tinyint"):
        return "BOOLEAN"
    if sql_type.startswith("float"):
        return "FLOAT"
    if sql_type.startswith("int"):
        return "INT"
    if sql_type.startswith("text"):
        return "TEXT"
    return sql_type.upper()


def normalize_label(name: str) -> str:
    return name.replace("_", " ").upper()


def text_width(text: str, scale: int = FONT_SCALE) -> int:
    if not text:
        return 0
    return len(text) * (CHAR_WIDTH + CHAR_SPACING) * scale - CHAR_SPACING * scale


def column_label(column: Column) -> str:
    parts: list[str] = []
    if column.is_primary:
        parts.append("PK")
    if column.foreign_key:
        parts.append("FK")
    parts.append(normalize_label(column.name))
    parts.append(normalize_type(column.sql_type))
    return " ".join(parts)


def parse_schema(path: Path) -> list[Table]:
    schema = path.read_text()
    blocks = re.finditer(r"CREATE TABLE `([^`]+)` \((.*?)\) ENGINE=", schema, re.S)
    tables: list[Table] = []

    for block in blocks:
        table_name = block.group(1)
        body = block.group(2)
        columns: list[Column] = []
        primary_keys: set[str] = set()
        foreign_keys: dict[str, tuple[str, str]] = {}

        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            if line.startswith("`"):
                match = re.match(r"`([^`]+)`\s+([a-zA-Z]+(?:\(\d+\))?)", line)
                if match:
                    columns.append(Column(name=match.group(1), sql_type=match.group(2)))
            elif line.startswith("PRIMARY KEY"):
                primary_keys.update(re.findall(r"`([^`]+)`", line))
            elif "FOREIGN KEY" in line and "REFERENCES" in line:
                match = re.search(
                    r"FOREIGN KEY \(`([^`]+)`\) REFERENCES `([^`]+)` \(`([^`]+)`\)",
                    line,
                )
                if match:
                    foreign_keys[match.group(1)] = (match.group(2), match.group(3))

        for column in columns:
            column.is_primary = column.name in primary_keys
            column.foreign_key = foreign_keys.get(column.name)

        tables.append(Table(name=table_name, columns=columns))

    return tables


def build_layout(tables: list[Table]) -> tuple[dict[str, TableLayout], int, int]:
    metrics: dict[str, tuple[Table, list[str], int, int]] = {}

    for table in tables:
        labels = [column_label(column) for column in table.columns]
        width = max(text_width(normalize_label(table.name)), *(text_width(label) for label in labels)) + PADDING_X * 2
        height = HEADER_HEIGHT + len(labels) * ROW_HEIGHT
        metrics[table.name] = (table, labels, width, height)

    left_width = max(metrics[name][2] for name in LEFT_COLUMN)
    center_width = max(metrics[name][2] for name in CENTER_COLUMN)
    right_width = max(metrics[name][2] for name in RIGHT_COLUMN)

    column_x = {
        "left": LEFT_MARGIN,
        "center": LEFT_MARGIN + left_width + COLUMN_GAP,
        "right": LEFT_MARGIN + left_width + COLUMN_GAP + center_width + COLUMN_GAP,
    }

    positions: dict[str, tuple[int, int]] = {}

    def stack(names: list[str], x: int, start_y: int, custom_gaps: dict[str, int] | None = None) -> None:
        y = start_y
        for name in names:
            positions[name] = (x, y)
            _, _, _, height = metrics[name]
            y += height + (custom_gaps.get(name, STACK_GAP) if custom_gaps else STACK_GAP)

    stack(LEFT_COLUMN, column_x["left"], TOP_MARGIN)
    stack(CENTER_COLUMN, column_x["center"], TOP_MARGIN)
    stack(RIGHT_COLUMN, column_x["right"], TOP_MARGIN, {"categories": 120})

    layouts: dict[str, TableLayout] = {}
    max_right = 0
    max_bottom = 0

    for table_name in TABLE_ORDER:
        table, labels, width, height = metrics[table_name]
        x, y = positions[table_name]
        layout = TableLayout(
            table=table,
            labels=labels,
            x=x,
            y=y,
            width=width,
            height=height,
            row_lookup={column.name: index for index, column in enumerate(table.columns)},
        )
        layouts[table.name] = layout
        max_right = max(max_right, x + width)
        max_bottom = max(max_bottom, y + height)

    return layouts, max_right + CANVAS_RIGHT_MARGIN, max_bottom + CANVAS_BOTTOM_MARGIN


def anchor(layouts: dict[str, TableLayout], table_name: str, column_name: str, side: str) -> tuple[int, int]:
    layout = layouts[table_name]
    row_index = layout.row_lookup[column_name]
    y = layout.y + HEADER_HEIGHT + row_index * ROW_HEIGHT + ROW_HEIGHT // 2
    if side == "left":
        return (layout.x, y)
    if side == "right":
        return (layout.x + layout.width, y)
    raise ValueError(f"Unsupported side: {side}")


def draw_table(canvas: Canvas, layout: TableLayout) -> None:
    canvas.fill_rect(layout.x + 6, layout.y + 6, layout.width, layout.height, SHADOW)
    canvas.fill_rect(layout.x, layout.y, layout.width, layout.height, TABLE_BG)
    canvas.fill_rect(layout.x, layout.y, layout.width, HEADER_HEIGHT, HEADER_BG)
    canvas.draw_rect(layout.x, layout.y, layout.width, layout.height, BORDER, thickness=2)

    for row_index, label in enumerate(layout.labels):
        row_y = layout.y + HEADER_HEIGHT + row_index * ROW_HEIGHT
        if row_index % 2 == 0:
            canvas.fill_rect(layout.x + 2, row_y, layout.width - 4, ROW_HEIGHT, TABLE_ALT)
        canvas.fill_rect(layout.x + 2, row_y, layout.width - 4, 1, SHADOW)
        canvas.draw_text(layout.x + PADDING_X, row_y + 6, label, TEXT)

    title = normalize_label(layout.table.name)
    canvas.draw_text(layout.x + PADDING_X, layout.y + 10, title, HEADER_TEXT)


def draw_relationships(canvas: Canvas, layouts: dict[str, TableLayout]) -> None:
    left_column_right = max(layouts[name].x + layouts[name].width for name in LEFT_COLUMN)
    center_right = max(layouts[name].x + layouts[name].width for name in CENTER_COLUMN)
    right_column_right = max(layouts[name].x + layouts[name].width for name in RIGHT_COLUMN)
    top_edge = min(layout.y for layout in layouts.values())

    west_lanes = [left_column_right + 30 + index * 22 for index in range(10)]
    east_lanes = [center_right + 30 + index * 24 for index in range(6)]
    far_right_lanes = [right_column_right + 32 + index * 30 for index in range(3)]
    top_lanes = [top_edge - 52, top_edge - 24]
    items_bottom = layouts["items"].y + layouts["items"].height
    bids_top = layouts["bids"].y
    center_bridge_y = (items_bottom + bids_top) // 2

    relationships = [
        (
            ("alerts", "user_id", "right"),
            ("users", "id", "right"),
            [
                (west_lanes[0], anchor(layouts, "alerts", "user_id", "right")[1]),
                (west_lanes[0], anchor(layouts, "users", "id", "right")[1]),
            ],
        ),
        (
            ("notifications", "user_id", "right"),
            ("users", "id", "right"),
            [
                (west_lanes[1], anchor(layouts, "notifications", "user_id", "right")[1]),
                (west_lanes[1], anchor(layouts, "users", "id", "right")[1]),
            ],
        ),
        (
            ("alerts", "category_id", "right"),
            ("categories", "id", "left"),
            [
                (west_lanes[2], anchor(layouts, "alerts", "category_id", "right")[1]),
                (west_lanes[2], center_bridge_y),
                (east_lanes[2], center_bridge_y),
                (east_lanes[2], anchor(layouts, "categories", "id", "left")[1]),
            ],
        ),
        (
            ("items", "seller_id", "left"),
            ("users", "id", "right"),
            [
                (west_lanes[3], anchor(layouts, "items", "seller_id", "left")[1]),
                (west_lanes[3], anchor(layouts, "users", "id", "right")[1]),
            ],
        ),
        (
            ("bids", "item_id", "left"),
            ("items", "id", "left"),
            [
                (west_lanes[4], anchor(layouts, "bids", "item_id", "left")[1]),
                (west_lanes[4], anchor(layouts, "items", "id", "left")[1]),
            ],
        ),
        (
            ("bids", "bidder_id", "left"),
            ("users", "id", "right"),
            [
                (west_lanes[5], anchor(layouts, "bids", "bidder_id", "left")[1]),
                (west_lanes[5], anchor(layouts, "users", "id", "right")[1]),
            ],
        ),
        (
            ("autobids", "item_id", "left"),
            ("items", "id", "left"),
            [
                (west_lanes[6], anchor(layouts, "autobids", "item_id", "left")[1]),
                (west_lanes[6], anchor(layouts, "items", "id", "left")[1]),
            ],
        ),
        (
            ("autobids", "bidder_id", "left"),
            ("users", "id", "right"),
            [
                (west_lanes[7], anchor(layouts, "autobids", "bidder_id", "left")[1]),
                (west_lanes[7], anchor(layouts, "users", "id", "right")[1]),
            ],
        ),
        (
            ("categories", "parent_id", "right"),
            ("categories", "id", "right"),
            [
                (far_right_lanes[1], anchor(layouts, "categories", "parent_id", "right")[1]),
                (far_right_lanes[1], anchor(layouts, "categories", "id", "right")[1]),
            ],
        ),
        (
            ("items", "category_id", "right"),
            ("categories", "id", "left"),
            [
                (east_lanes[0], anchor(layouts, "items", "category_id", "right")[1]),
                (east_lanes[0], anchor(layouts, "categories", "id", "left")[1]),
            ],
        ),
        (
            ("questions", "item_id", "left"),
            ("items", "id", "right"),
            [
                (east_lanes[1], anchor(layouts, "questions", "item_id", "left")[1]),
                (east_lanes[1], anchor(layouts, "items", "id", "right")[1]),
            ],
        ),
        (
            ("questions", "user_id", "left"),
            ("users", "id", "right"),
            [
                (east_lanes[3], anchor(layouts, "questions", "user_id", "left")[1]),
                (east_lanes[3], top_lanes[0]),
                (west_lanes[8], top_lanes[0]),
                (west_lanes[8], anchor(layouts, "users", "id", "right")[1]),
            ],
        ),
        (
            ("answers", "question_id", "right"),
            ("questions", "id", "right"),
            [
                (far_right_lanes[0], anchor(layouts, "answers", "question_id", "right")[1]),
                (far_right_lanes[0], anchor(layouts, "questions", "id", "right")[1]),
            ],
        ),
        (
            ("answers", "rep_id", "right"),
            ("users", "id", "right"),
            [
                (far_right_lanes[2], anchor(layouts, "answers", "rep_id", "right")[1]),
                (far_right_lanes[2], top_lanes[1]),
                (west_lanes[9], top_lanes[1]),
                (west_lanes[9], anchor(layouts, "users", "id", "right")[1]),
            ],
        ),
    ]

    for index, (source, target, bends) in enumerate(relationships):
        color = LINE_COLORS[index % len(LINE_COLORS)]
        source_point = anchor(layouts, source[0], source[1], source[2])
        target_point = anchor(layouts, target[0], target[1], target[2])
        path = [source_point, *bends, target_point]
        canvas.draw_path(path, color, thickness=4)
        canvas.draw_circle(source_point[0], source_point[1], 5, color)
        canvas.draw_circle(target_point[0], target_point[1], 5, color)


def draw_header(canvas: Canvas, width: int) -> None:
    title = "KICKSBID ER DIAGRAM"
    subtitle = "PK PRIMARY KEY FK FOREIGN KEY"
    title_x = (width - text_width(title, scale=3)) // 2
    subtitle_x = (width - text_width(subtitle)) // 2
    canvas.draw_text(title_x, 26, title, HEADER_BG, scale=3)
    canvas.draw_text(subtitle_x, 66, subtitle, SUBTLE)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    schema_path = repo_root / "schema.sql"
    output_dir = repo_root / "docs"
    output_path = output_dir / "kicksbid-er-diagram.png"
    pdf_path = output_dir / "kicksbid-er-diagram.pdf"

    tables = parse_schema(schema_path)
    layouts, width, height = build_layout(tables)
    canvas = Canvas(width, height, BG)

    draw_header(canvas, width)
    draw_relationships(canvas, layouts)
    for table_name in TABLE_ORDER:
        draw_table(canvas, layouts[table_name])

    output_dir.mkdir(parents=True, exist_ok=True)
    canvas.save_png(output_path)
    print(f"Wrote {output_path}")

    if shutil.which("sips"):
        subprocess.run(
            ["sips", "-s", "format", "pdf", str(output_path), "--out", str(pdf_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
