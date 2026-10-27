"""Export helpers: Excel/CSV bytes generation, no paid reporting service."""
from __future__ import annotations

import io

import pandas as pd


def to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            safe_name = name[:31] if name else "Sheet1"
            df.to_excel(writer, sheet_name=safe_name, index=False)
    return buf.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")
