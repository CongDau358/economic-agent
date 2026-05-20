from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .constants import METRIC_FIELDS
from .normalizer import NormalizedTable


@dataclass
class MappedRow:
    row_index: int
    date_value: str
    metrics: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, str] = field(default_factory=dict)


@dataclass
class MappedTable:
    sheet_name: str
    data_type: str
    date_column: str | None
    metric_columns: Dict[str, str]
    rows: List[MappedRow] = field(default_factory=list)
    financial_priorities: List[str] = field(default_factory=list)


def _detect_data_type(sheet_name: str, canonical: Dict[str, str]) -> str:
    haystack = f"{sheet_name} {' '.join(canonical.values())}".lower()
    from .constants import DATA_TYPE_KEYWORDS

    for data_type, keywords in DATA_TYPE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return data_type
    if "exports" in canonical.values() or "imports" in canonical.values():
        return "trade_statistics"
    if "assets" in canonical.values() or "liabilities" in canonical.values():
        return "balance_sheet"
    if "revenue" in canonical.values():
        return "revenue_table"
    return "general_spreadsheet"


def _detect_priorities(metric_columns: Dict[str, str]) -> List[str]:
    canon_values = set(metric_columns.values())
    found: List[str] = []
    for priority, fields in METRIC_FIELDS.items():
        if any(f in canon_values for f in fields):
            found.append(priority)
    return found


def map_metrics(table: NormalizedTable) -> MappedTable:
    metric_columns = {
        col_id: canon for col_id, canon in table.canonical_columns.items() if canon != "date"
    }
    data_type = _detect_data_type(table.sheet_name, table.canonical_columns)
    mapped_rows: List[MappedRow] = []

    for idx, row in enumerate(table.rows):
        metrics: Dict[str, str] = {}
        date_value = ""
        if table.date_column:
            date_value = row.get(table.date_column, "")
        for col_id, canon in metric_columns.items():
            val = row.get(col_id, "")
            if val:
                metrics[canon] = val
        if metrics or date_value:
            mapped_rows.append(
                MappedRow(
                    row_index=table.row_start + idx,
                    date_value=date_value,
                    metrics=metrics,
                    raw=row,
                )
            )

    return MappedTable(
        sheet_name=table.sheet_name,
        data_type=data_type,
        date_column=table.date_column,
        metric_columns=metric_columns,
        rows=mapped_rows,
        financial_priorities=_detect_priorities(metric_columns),
    )
