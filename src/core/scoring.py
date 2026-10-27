"""MCDA / Weighted Sum Model scoring engine. Pure local computation, no network/API calls.

All functions are deterministic and side-effect free (except persistence helpers in
services/), so they can be unit tested directly and reused across any dataset shape.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from src.core.indicators import CRITICAL_DECISION_KEYWORDS, DEFAULT_STUDY_SETTINGS

MISSING_TOKENS = {"", "<null>", "null", "none", "nan", "n/a", "غير متاح", "لا يوجد بيانات"}


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    s = str(value).strip()
    if s.lower() in MISSING_TOKENS:
        return None
    return s


def _to_float(value: Any) -> Optional[float]:
    s = _clean(value)
    if s is None:
        return None
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class IndicatorResult:
    code: str
    score: Optional[float]
    status: str  # validated | provisional | insufficient
    raw_value: str
    explanation: str


@dataclass
class CompositeResult:
    project_id: int
    priority_score: Optional[float]
    completeness_pct: float
    classification: str  # Validated | Provisional | Insufficient Data
    indicator_results: dict = field(default_factory=dict)
    contributions: dict = field(default_factory=dict)  # code -> weighted points contributed
    safety_flag: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Safety flag (independent of composite score, per spec section 3)
# ---------------------------------------------------------------------------

def safety_flag(building_decisions: Any) -> dict:
    normalized = _clean(building_decisions)
    if not normalized or normalized in {"لا يوجد", "لا يوجد قرار"}:
        return {"level": "none", "label": "لا توجد قرارات مسجلة"}
    if "إزالة" in normalized or "ازالة" in normalized:
        return {"level": "critical", "label": f"قرار رسمي: {normalized}"}
    if "ترميم" in normalized:
        return {"level": "warning", "label": f"قرار رسمي: {normalized}"}
    return {"level": "warning", "label": f"قرار آخر يستدعي المراجعة: {normalized}"}


# ---------------------------------------------------------------------------
# Per-indicator scoring functions
# ---------------------------------------------------------------------------

def score_category_map(raw: Any, rubric: dict) -> IndicatorResult:
    val = _clean(raw)
    mapping = rubric.get("map", {})
    if val is None:
        return IndicatorResult("", None, "insufficient", "", "القيمة غير متوفرة في السجل المصدر.")
    score = mapping.get(val)
    if score is None:
        return IndicatorResult("", None, "insufficient", val, f"قيمة غير معروفة في قاموس التقييم: '{val}'.")
    return IndicatorResult("", float(score), "validated", val, f"تصنيف '{val}' يقابل {score}/100 حسب جدول التقييم الرسمي.")


def score_linear_scale(raw: Any, rubric: dict) -> IndicatorResult:
    v = _to_float(raw)
    max_raw = rubric.get("max_raw", 100)
    if v is None:
        return IndicatorResult("", None, "insufficient", "", "لا توجد قيمة أهمية استراتيجية مسجلة لهذا المشروع.")
    score = max(0.0, min(100.0, (v / max_raw) * 100))
    return IndicatorResult("", score, "validated", str(v), f"القيمة الخام {v} من {max_raw} → {score:.1f}/100.")


def score_threshold_bands(age_years: Optional[float], rubric: dict) -> IndicatorResult:
    if age_years is None:
        return IndicatorResult("", None, "insufficient", "", "سنة الإنشاء غير متوفرة؛ تعذر حساب العمر.")
    for band in rubric.get("bands", []):
        if band["min"] <= age_years < band["max"]:
            return IndicatorResult(
                "", float(band["score"]), "validated", f"{age_years:.0f} سنة",
                f"العمر {age_years:.0f} سنة يقع ضمن نطاق [{band['min']}-{band['max']}) → {band['score']}/100.",
            )
    return IndicatorResult("", 100.0, "validated", f"{age_years:.0f} سنة", "العمر يتجاوز كل النطاقات المعرفة → 100/100.")


def score_density_ratio(n_units, n_buildings, area_feddan, rubric: dict, dataset_ctx: dict) -> IndicatorResult:
    units = _to_float(n_units)
    buildings = _to_float(n_buildings)
    area = _to_float(area_feddan)
    if not area or area <= 0:
        return IndicatorResult("", None, "insufficient", "", "المساحة بالفدان غير متوفرة أو صفر؛ تعذر حساب الكثافة.")
    if units is not None:
        ratio = units / area
        pool = dataset_ctx.get("density_units", {})
        metric_label = "وحدة/فدان"
    elif buildings is not None:
        ratio = buildings / area
        pool = dataset_ctx.get("density_buildings", {})
        metric_label = "عمارة/فدان"
    else:
        return IndicatorResult("", None, "insufficient", "", "عدد الوحدات وعدد العمارات غير متوفرين.")
    lo, hi = pool.get("min"), pool.get("max")
    if lo is None or hi is None or hi <= lo:
        score = 50.0
        note = " (قيمة وحيدة في المجموعة، تُسند درجة وسطى 50)"
    else:
        score = max(0.0, min(100.0, (ratio - lo) / (hi - lo) * 100))
        note = ""
    return IndicatorResult(
        "", score, "validated", f"{ratio:.1f} {metric_label}",
        f"كثافة {ratio:.1f} {metric_label}، طُبِّعت نسبيًا ضمن مدى الدراسة الحالية [{lo}-{hi}]{note}.",
    )


def score_modification_extent(has_ext, ext_type, floor_change, rubric: dict) -> IndicatorResult:
    ext_val = _clean(has_ext)
    type_val = _clean(ext_type) or "لا يوجد"
    floor_val = _clean(floor_change) or ""
    type_map = rubric.get("extension_type_map", {})
    if ext_val is None and type_val == "لا يوجد" and not floor_val:
        return IndicatorResult("", None, "insufficient", "", "لا توجد بيانات عن الامتدادات أو التعديلات.")
    score = float(type_map.get(type_val, 0))
    explanation = f"نوع الامتداد: '{type_val}' → {score:.0f}/100 (مدى التعديل، وليس حكمًا بعدم الشرعية)."
    kw = rubric.get("reconciliation_keyword", "تصالح")
    if kw in floor_val:
        bonus = rubric.get("reconciliation_bonus", 0)
        score = min(100.0, score + bonus)
        explanation += f" + تعديل مسجل بالدور الأرضي ({floor_val}) أضاف {bonus} نقطة."
    return IndicatorResult("", score, "provisional", f"{type_val} | {floor_val or '—'}", explanation)


def score_infrastructure_ratio(elec, water, sewage, gas, rubric: dict) -> IndicatorResult:
    fields = [elec, water, sewage, gas]
    connected_values = set(rubric.get("connected_values", ["متصل"]))
    cleaned = [_clean(f) for f in fields]
    if all(c is None for c in cleaned):
        return IndicatorResult("", None, "insufficient", "", "لا توجد بيانات اتصال بالمرافق.")
    total = rubric.get("utilities", 4)
    connected = sum(1 for c in cleaned if c in connected_values)
    score = (connected / total) * 100
    return IndicatorResult(
        "", score, "provisional", f"{connected}/{total} متصل",
        f"{connected} من {total} مرافق متصلة. يعكس وجود الاتصال فقط وليس جودة أو كفاءة الخدمة.",
    )


def score_manual_assessment_only(manual_score: Optional[float], manual_status: Optional[str], note: str) -> IndicatorResult:
    if manual_score is None:
        return IndicatorResult("", None, "insufficient", "", "لا يوجد عمود قياس في المصدر؛ بانتظار تقييم ميداني موثق.")
    status = manual_status or "provisional"
    return IndicatorResult("", float(manual_score), status, str(manual_score), note or "تقييم يدوي أُدخل من مستخدم.")


# ---------------------------------------------------------------------------
# Dataset-wide context (needed for relative normalization like density)
# ---------------------------------------------------------------------------

def compute_dataset_context(projects: list) -> dict:
    units_ratios, bld_ratios = [], []
    for p in projects:
        if p.is_archived:
            continue
        area = _to_float(p.area_feddan)
        if not area or area <= 0:
            continue
        units = _to_float(p.n_units)
        bld = _to_float(p.n_buildings)
        if units is not None:
            units_ratios.append(units / area)
        elif bld is not None:
            bld_ratios.append(bld / area)
    ctx = {
        "density_units": {"min": min(units_ratios), "max": max(units_ratios)} if units_ratios else {},
        "density_buildings": {"min": min(bld_ratios), "max": max(bld_ratios)} if bld_ratios else {},
    }
    return ctx


# ---------------------------------------------------------------------------
# Orchestration: one project x one indicator
# ---------------------------------------------------------------------------

def compute_indicator_result(project, indicator_cfg, study, dataset_ctx: dict,
                              manual_assessment=None) -> IndicatorResult:
    method = indicator_cfg.normalization_method
    rubric = indicator_cfg.rubric()
    code = indicator_cfg.code

    if method == "category_map":
        r = score_category_map(project.general_condition, rubric)
    elif method == "linear_scale":
        r = score_linear_scale(project.strategic_importance_raw, rubric)
    elif method == "threshold_bands":
        cy = _to_float(project.construction_year)
        ref_year = study.reference_year
        age = (ref_year - cy) if (cy is not None and ref_year) else None
        r = score_threshold_bands(age, rubric)
    elif method == "density_ratio":
        r = score_density_ratio(project.n_units, project.n_buildings, project.area_feddan, rubric, dataset_ctx)
    elif method == "modification_extent":
        r = score_modification_extent(project.has_extensions, project.extension_type,
                                        project.ground_floor_use_change, rubric)
    elif method == "infrastructure_ratio":
        r = score_infrastructure_ratio(project.elec_connected, project.water_connected,
                                         project.sewage_connected, project.gas_connected, rubric)
    elif method == "manual_assessment_only":
        if manual_assessment is not None:
            r = score_manual_assessment_only(manual_assessment.score, manual_assessment.status,
                                              manual_assessment.source_note)
        else:
            r = score_manual_assessment_only(None, None, "")
    else:
        r = IndicatorResult("", None, "insufficient", "", f"طريقة حساب غير مدعومة: {method}")

    r.code = code
    if indicator_cfg.always_provisional and r.status == "validated":
        r.status = "provisional"
    return r


# ---------------------------------------------------------------------------
# Composite priority score (WSM with renormalization over available weight)
# ---------------------------------------------------------------------------

def compute_composite(project, indicator_cfgs: list, study, dataset_ctx: dict,
                       weights_override: Optional[dict] = None,
                       manual_assessments: Optional[dict] = None) -> CompositeResult:
    settings = {**DEFAULT_STUDY_SETTINGS, **study.settings()}
    active_cfgs = [c for c in indicator_cfgs if c.is_active]
    weights = weights_override or {c.code: c.weight for c in active_cfgs}

    results, contributions = {}, {}
    available_weight, weighted_sum = 0.0, 0.0
    dominant_missing = False
    any_provisional = False

    for cfg in active_cfgs:
        w = weights.get(cfg.code, 0.0)
        if w <= 0:
            continue
        manual = (manual_assessments or {}).get(cfg.code)
        r = compute_indicator_result(project, cfg, study, dataset_ctx, manual)
        results[cfg.code] = r
        if r.score is not None:
            available_weight += w
            weighted_sum += r.score * w
            contributions[cfg.code] = round(r.score * w / 100, 2)
            if r.status == "provisional":
                any_provisional = True
        else:
            contributions[cfg.code] = None
            if w >= settings["dominant_indicator_min_weight"]:
                dominant_missing = True

    total_weight = sum(w for w in weights.values() if w > 0) or 1.0
    completeness_pct = round(available_weight / total_weight * 100, 1)
    denominator = 100.0 if settings.get("preserve_original_weights") else available_weight
    priority_score = round(weighted_sum / denominator, 2) if available_weight > 0 else None

    # Reconcile contributions with the same denominator used by the composite.
    # The previous /100 denominator understated contributions with missing data.
    if available_weight > 0:
        contributions = {
            code: round(result.score * weights.get(code, 0.0) / denominator, 2)
            if result.score is not None else None
            for code, result in results.items()
        }

    if dominant_missing or priority_score is None:
        classification = "Insufficient Data"
    elif completeness_pct < settings["provisional_completeness_threshold"]:
        classification = "Insufficient Data"
    elif completeness_pct < settings["validated_completeness_threshold"] or any_provisional:
        classification = "Provisional"
    else:
        classification = "Validated"

    return CompositeResult(
        project_id=project.id,
        priority_score=priority_score,
        completeness_pct=completeness_pct,
        classification=classification,
        indicator_results=results,
        contributions=contributions,
        safety_flag=safety_flag(project.building_decisions),
    )


def composite_dataframe(projects: list, indicator_cfgs: list, study, weights_override=None,
                         manual_assessments_by_project: Optional[dict] = None) -> pd.DataFrame:
    """Compute composite results for every (non-archived) project; return as a tidy DataFrame."""
    dataset_ctx = compute_dataset_context(projects)
    rows = []
    for p in projects:
        if p.is_archived:
            continue
        manual = (manual_assessments_by_project or {}).get(p.id)
        cr = compute_composite(p, indicator_cfgs, study, dataset_ctx, weights_override, manual)
        row = {
            "project_id": p.id,
            "external_id": p.external_id,
            "site_name": p.site_name,
            "district": p.district,
            "priority_score": cr.priority_score,
            "completeness_pct": cr.completeness_pct,
            "classification": cr.classification,
            "safety_level": cr.safety_flag["level"],
            "safety_label": cr.safety_flag["label"],
        }
        for code, r in cr.indicator_results.items():
            row[f"score_{code}"] = r.score
            row[f"status_{code}"] = r.status
            row[f"raw_{code}"] = r.raw_value
            row[f"explain_{code}"] = r.explanation
            row[f"contrib_{code}"] = cr.contributions.get(code)
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by="priority_score", ascending=False, na_position="last").reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
    return df

