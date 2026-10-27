"""Generic Excel/CSV import with user-confirmed column mapping.

Design goal (spec section 6): the app must work with any dataset shape without
code changes. This module never silently invents or merges data — it only ever
suggests a mapping, which a human confirms in the UI before anything is saved.
"""
from __future__ import annotations

import io
import json
import math
import re
from typing import Any

import pandas as pd

# (field_name, Arabic label, required, dtype) — targets a user can map a source column to.
STANDARD_FIELD_DEFS = [
    ("external_id", "المعرف الأصلي (External ID)", True, "text"),
    ("site_name", "اسم المشروع/الموقع", True, "text"),
    ("governorate", "المحافظة", False, "text"),
    ("city_center", "المدينة/المركز", False, "text"),
    ("owner_entity", "الجهة المالكة", False, "text"),
    ("street_name", "اسم الشارع", False, "text"),
    ("n_buildings", "عدد العمارات", False, "number"),
    ("n_units", "عدد الوحدات", False, "number"),
    ("unit_area", "مساحة الوحدة", False, "number"),
    ("area_feddan", "المساحة بالفدان", False, "number"),
    ("n_floors", "عدد الأدوار", False, "number"),
    ("n_rooms_per_unit", "عدد الغرف بالوحدة", False, "number"),
    ("housing_type", "نوع الإسكان", False, "text"),
    ("general_condition", "الحالة العامة للمبنى", False, "text"),
    ("building_decisions", "القرارات الصادرة للمبنى", False, "text"),
    ("construction_year", "سنة الإنشاء", False, "number"),
    ("strategic_importance_raw", "الأهمية الاستراتيجية (من 15)", False, "number"),
    ("has_extensions", "وجود امتدادات", False, "text"),
    ("extension_type", "نوع الامتدادات", False, "text"),
    ("ground_floor_use_change", "تغيير استخدام الدور الأرضي", False, "text"),
    ("repeated_floor_use_change", "تغيير استخدام الأدوار المتكررة", False, "text"),
    ("elec_connected", "اتصال الكهرباء", False, "text"),
    ("water_connected", "اتصال المياه", False, "text"),
    ("sewage_connected", "اتصال الصرف الصحي", False, "text"),
    ("gas_connected", "اتصال الغاز", False, "text"),
    ("source_excel_row", "رقم الصف بالملف الأصلي", False, "text"),
    ("data_quality_notes_source", "ملاحظات جودة البيانات (المصدر)", False, "text"),
]
STANDARD_FIELD_NAMES = [f[0] for f in STANDARD_FIELD_DEFS]
REQUIRED_FIELDS = [f[0] for f in STANDARD_FIELD_DEFS if f[2]]

# Exact-match mapping for the official Port Said export this system ships with.
PORTSAID_DEFAULT_MAPPING = {
    "OBJECTID *": "external_id",
    "اسم_الموقع": "site_name",
    "المحافظة": "governorate",
    "المدينة/المركز": "city_center",
    "الجهة_المالكة": "owner_entity",
    "اسم_الشارع": "street_name",
    "عدد_العمارات": "n_buildings",
    "عدد_الوحدات": "n_units",
    "مساحة_الوحدة": "unit_area",
    "المساحة_بالفدان": "area_feddan",
    "عدد_الأدوار": "n_floors",
    "عدد_الغرف_الوحدة": "n_rooms_per_unit",
    "نوع_الاسكان": "housing_type",
    "الحالة_العامة_للمبني": "general_condition",
    "القرارات_الصادرة_للمبني": "building_decisions",
    "سنة_الانشاء": "construction_year",
    "الأهميه الأستراتيجيه": "strategic_importance_raw",
    "الامتدادات_بالعمارات": "has_extensions",
    "نوع_الامتدادات": "extension_type",
    "هل_حدث_تغيير_في_استخدام_الدور_الارضي": "ground_floor_use_change",
    "هل_حدث_تغيير_في_استخدام_الادوار_المتكررة": "repeated_floor_use_change",
    "اتصال_المشروع_بالكهرباء": "elec_connected",
    "اتصال_المشروع_بالمياه": "water_connected",
    "اتصال_المشروع_بالصرف_الصحي": "sewage_connected",
    "اتصال_المشروع_بالغاز": "gas_connected",
    "Source_Excel_Row": "source_excel_row",
    "Data_Quality_Notes": "data_quality_notes_source",
}


def load_tabular_file(file_bytes: bytes, filename: str, sheet_name: Any = 0) -> dict:
    """Returns {'sheets': {name: df}} for xlsx, or {'sheets': {'data': df}} for csv."""
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        sheets = {name: xls.parse(name) for name in xls.sheet_names}
        return {"sheets": sheets, "default_sheet": xls.sheet_names[0]}
    elif lower.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
        return {"sheets": {"data": df}, "default_sheet": "data"}
    raise ValueError(f"صيغة ملف غير مدعومة: {filename} (مدعوم: xlsx, xls, csv)")


def suggest_mapping(columns: list[str]) -> dict:
    """Best-effort mapping suggestion. Exact Port Said columns match directly;
    everything else gets light keyword matching. Always shown to the user to confirm."""
    mapping = {}
    for col in columns:
        if col in PORTSAID_DEFAULT_MAPPING:
            mapping[col] = PORTSAID_DEFAULT_MAPPING[col]
            continue
        norm = str(col).strip().lower()
        guess = None
        for field, label, *_ in STANDARD_FIELD_DEFS:
            if field.replace("_", " ") in norm or norm in field:
                guess = field
                break
        mapping[col] = guess
    return mapping


DISTRICT_PATTERN = re.compile(r"\(([^)]+)\)")


def parse_district(city_center: Any) -> str:
    """Extract district from strings like 'بورسعيد(حي المناخ)'. Never invents a value."""
    if city_center is None:
        return ""
    s = str(city_center).strip()
    m = DISTRICT_PATTERN.search(s)
    return m.group(1).strip() if m else ""


def _json_safe(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp,)):
        return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def _clean_text(v: Any) -> str:
    sv = _json_safe(v)
    return "" if sv is None else str(sv).strip()


def _clean_number(v: Any):
    sv = _json_safe(v)
    if sv is None or sv == "":
        return None
    try:
        return float(sv)
    except (TypeError, ValueError):
        s = str(sv).strip()
        if s.lower() in ("<null>", "null", "none"):
            return None
        try:
            return float(s)
        except (TypeError, ValueError):
            return None


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> list[dict]:
    """mapping: {source_column: standard_field_or_None}. Returns list of row dicts
    with standard fields + raw_data (full original row, JSON-safe)."""
    field_types = {f: t for f, _, _, t in STANDARD_FIELD_DEFS}
    records = []
    for _, row in df.iterrows():
        raw = {str(col): _json_safe(row[col]) for col in df.columns}
        rec = {f: ("" if t == "text" else None) for f, _, _, t in STANDARD_FIELD_DEFS}
        for src_col, field in mapping.items():
            if not field or src_col not in df.columns or field not in field_types:
                continue
            val = row.get(src_col)
            rec[field] = _clean_number(val) if field_types[field] == "number" else _clean_text(val)
        rec["district"] = parse_district(rec.get("city_center", ""))
        rec["raw_data"] = json.dumps(raw, ensure_ascii=False)
        records.append(rec)
    return records
