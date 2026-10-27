"""Data-quality checks: missing values, duplicates, suspicious values, incomplete indicators.

Used both (a) before import, to validate incoming rows, and (b) in the Data Quality
dashboard page, to audit records already stored.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

import pandas as pd

REQUIRED_FOR_MINIMAL_RECORD = ["external_id", "site_name"]


def _is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    s = str(v).strip().lower()
    return s in ("", "<null>", "none", "nan")


def validate_import_rows(rows: list[dict]) -> list[dict]:
    """Validate rows *before* they are written to the DB. Returns a list of issues
    (empty list == no blocking issues). Each issue: {row_index, field, level, message}."""
    issues = []
    seen_ids = {}
    for i, row in enumerate(rows):
        for field in REQUIRED_FOR_MINIMAL_RECORD:
            if _is_blank(row.get(field)):
                issues.append({"row_index": i, "field": field, "level": "error",
                                "message": f"الحقل الإلزامي '{field}' فارغ."})
        ext_id = row.get("external_id")
        if not _is_blank(ext_id):
            if ext_id in seen_ids:
                issues.append({"row_index": i, "field": "external_id", "level": "warning",
                                "message": f"معرف مكرر داخل الملف نفسه: '{ext_id}' (الصف {seen_ids[ext_id]} و{i})."})
            else:
                seen_ids[ext_id] = i

        cy = row.get("construction_year")
        if not _is_blank(cy):
            try:
                cy_f = float(cy)
                if cy_f < 1800 or cy_f > dt.date.today().year:
                    issues.append({"row_index": i, "field": "construction_year", "level": "warning",
                                    "message": f"سنة إنشاء غير منطقية: {cy}."})
            except (TypeError, ValueError):
                issues.append({"row_index": i, "field": "construction_year", "level": "warning",
                                "message": f"سنة إنشاء غير رقمية: '{cy}'."})

        site_name = row.get("site_name")
        if not _is_blank(site_name) and re.fullmatch(r"\d{4,6}(\.\d+)?", str(site_name).strip()):
            issues.append({"row_index": i, "field": "site_name", "level": "warning",
                            "message": f"اسم الموقع '{site_name}' يبدو رقمًا قد يكون ناتج تحويل تاريخ Excel خاطئ — تحقق يدويًا."})
    return issues


def data_quality_report(projects: list, indicator_codes: list[str]) -> pd.DataFrame:
    """Row-level data quality audit for already-stored projects."""
    rows = []
    seen = {}
    for p in projects:
        if p.external_id in seen:
            seen[p.external_id].append(p.id)
        else:
            seen[p.external_id] = [p.id]

    numeric_fields = {
        "n_buildings": (0, 1000), "n_units": (0, 20000), "area_feddan": (0, 500),
        "construction_year": (1800, dt.date.today().year), "strategic_importance_raw": (0, 15),
    }

    for p in projects:
        flags = []
        for field, (lo, hi) in numeric_fields.items():
            v = getattr(p, field, None)
            if v is None:
                continue
            try:
                vf = float(v)
            except (TypeError, ValueError):
                flags.append(f"{field}: قيمة غير رقمية")
                continue
            if vf < lo or vf > hi:
                flags.append(f"{field}={vf} خارج النطاق المتوقع [{lo},{hi}]")

        if len(seen.get(p.external_id, [])) > 1:
            flags.append(f"معرف مكرر (external_id) مستخدم في {len(seen[p.external_id])} سجلات")

        if p.site_name and re.fullmatch(r"\d{4,6}(\.\d+)?", str(p.site_name).strip()):
            flags.append("اسم الموقع رقمي الشكل — احتمال تحويل تاريخ Excel غير مقصود")

        missing_core = [f for f in ("general_condition", "construction_year") if _is_blank(getattr(p, f, None))]
        if missing_core:
            flags.append("بيانات أساسية ناقصة: " + ", ".join(missing_core))

        rows.append({
            "project_id": p.id,
            "external_id": p.external_id,
            "site_name": p.site_name,
            "district": p.district,
            "issue_count": len(flags),
            "issues": " | ".join(flags) if flags else "لا توجد ملاحظات",
            "has_duplicate_id": len(seen.get(p.external_id, [])) > 1,
        })
    return pd.DataFrame(rows)
