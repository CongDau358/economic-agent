from __future__ import annotations

from typing import Dict, Tuple

SUPPORTED_DATA_TYPES = (
    "balance_sheet",
    "revenue_table",
    "quarterly_report",
    "trade_statistics",
    "general_spreadsheet",
)

COLUMN_ALIASES: Dict[str, Tuple[str, ...]] = {
    "date": ("date", "period", "quarter", "year", "ngày", "kỳ", "thời gian"),
    "revenue": ("revenue", "sales", "turnover", "doanh thu", "net sales", "doanh số"),
    "profit": ("profit", "net income", "earnings", "lợi nhuận", "ebit", "ebitda"),
    "assets": ("assets", "total assets", "tài sản"),
    "liabilities": ("liabilities", "debt", "nợ", "total liabilities"),
    "equity": ("equity", "shareholders equity", "vốn chủ"),
    "cash_flow": ("cash flow", "operating cash", "fcf", "dòng tiền"),
    "exports": ("exports", "export value", "xuất khẩu"),
    "imports": ("imports", "import value", "nhập khẩu"),
    "growth": ("growth", "yoy", "change", "tăng trưởng", "%"),
}

METRIC_FIELDS: Dict[str, Tuple[str, ...]] = {
    "revenue": ("revenue",),
    "profit": ("profit",),
    "debt": ("liabilities",),
    "cash_flow": ("cash_flow",),
    "growth": ("growth",),
    "trade": ("exports", "imports"),
}

DATA_TYPE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "balance_sheet": ("balance sheet", "assets", "liabilities", "equity", "bảng cân đối"),
    "revenue_table": ("revenue", "sales", "doanh thu", "income statement"),
    "quarterly_report": ("quarter", "q1", "q2", "q3", "q4", "quarterly"),
    "trade_statistics": ("export", "import", "trade", "xuất khẩu", "nhập khẩu"),
}

MAX_ROWS_PER_CHUNK = 25
