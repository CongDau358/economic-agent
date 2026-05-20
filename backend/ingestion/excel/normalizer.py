from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

from .constants import COLUMN_ALIASES
from .extractor import ExtractedTable


_DATE_RE = re.compile(
    r"^(\d{4})(?:[-/\.](\d{1,2}))?(?:[-/\.](\d{1,2}))?$|"
    r"^(q[1-4])\s*(\d{4})$|"
    r"^(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})$",
    re.IGNORECASE,
)


@dataclass
class NormalizedTable:
    sheet_name: str
    columns: List[str]
    canonical_columns: Dict[str, str]
    rows: List[Dict[str, str]]
    row_start: int
    row_end: int
    date_column: str | None


def _canonical_name(header: str) -> str | None:
    h = header.strip().lower()
    if not h:
        return None
    for canonical, aliases in COLUMN_ALIASES.items():
        if h == canonical or any(a in h or h in a for a in aliases):
            return canonical
    return None


def _normalize_date(value: str) -> str:
    v = value.strip()
    if not v:
        return v
    m = _DATE_RE.match(v)
    if not m:
        return v
    if m.group(1) and m.group(1).isdigit() and len(m.group(1)) == 4:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        if mo:
            return f"{y}-{int(mo):02d}" + (f"-{int(d):02d}" if d else "")
        return y
    if m.group(4):
        return f"{m.group(4).upper()}-{m.group(5)}"
    if m.group(6):
        return f"{m.group(8)}-{int(m.group(6)):02d}-{int(m.group(7)):02d}"
    return v


def normalize_table(table: ExtractedTable) -> NormalizedTable:
    canonical: Dict[str, str] = {}
    columns: List[str] = []
    for idx, header in enumerate(table.headers):
        col_id = f"col_{idx}"
        columns.append(col_id)
        canon = _canonical_name(header)
        if canon:
            canonical[col_id] = canon

    date_column: str | None = None
    for col_id, canon in canonical.items():
        if canon == "date":
            date_column = col_id
            break

    normalized_rows: List[Dict[str, str]] = []
    for row in table.rows:
        padded = list(row) + [""] * max(0, len(columns) - len(row))
        record: Dict[str, str] = {}
        for col_id, value in zip(columns, padded):
            v = value.strip()
            if canonical.get(col_id) == "date":
                v = _normalize_date(v)
            record[col_id] = v
        if any(record.values()):
            normalized_rows.append(record)

    return NormalizedTable(
        sheet_name=table.sheet_name,
        columns=columns,
        canonical_columns=canonical,
        rows=normalized_rows,
        row_start=table.row_start,
        row_end=table.row_end,
        date_column=date_column,
    )
