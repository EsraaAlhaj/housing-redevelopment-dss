"""Unit tests for the MCDA scoring engine: correctness + 'never fabricate missing data'."""
from __future__ import annotations

from src.core.indicators import OFFICIAL_INDICATORS
from src.core.scoring import (
    safety_flag, score_category_map, score_density_ratio, score_infrastructure_ratio,
    score_linear_scale, score_modification_extent, score_threshold_bands,
)


def test_category_map_known_value():
    rubric = {"map": {"متوسط": 50, "متهالك": 90}}
    r = score_category_map("متوسط", rubric)
    assert r.score == 50
    assert r.status == "validated"


def test_category_map_missing_value_not_fabricated():
    rubric = {"map": {"متوسط": 50}}
    r = score_category_map(None, rubric)
    assert r.score is None
    assert r.status == "insufficient"


def test_category_map_unmapped_value_not_fabricated():
    rubric = {"map": {"متوسط": 50}}
    r = score_category_map("قيمة غريبة", rubric)
    assert r.score is None
    assert r.status == "insufficient"


def test_linear_scale_strategic_importance():
    r = score_linear_scale(10.5, {"max_raw": 15})
    assert abs(r.score - 70.0) < 0.01
    assert r.status == "validated"


def test_linear_scale_missing_not_zero():
    r = score_linear_scale(None, {"max_raw": 15})
    assert r.score is None  # must NOT silently become 0
    assert r.status == "insufficient"


def test_threshold_bands_age():
    bands = {"bands": [{"min": 0, "max": 20, "score": 20}, {"min": 20, "max": 40, "score": 50},
                        {"min": 40, "max": 60, "score": 75}, {"min": 60, "max": 1000, "score": 100}]}
    assert score_threshold_bands(10, bands).score == 20
    assert score_threshold_bands(45, bands).score == 75
    assert score_threshold_bands(80, bands).score == 100
    r = score_threshold_bands(None, bands)
    assert r.score is None and r.status == "insufficient"


def test_threshold_bands_rejects_negative_age():
    bands = {"bands": [{"min": 0, "max": 20, "score": 20}, {"min": 20, "max": 1000, "score": 100}]}
    r = score_threshold_bands(-2, bands)
    assert r.score is None
    assert r.status == "insufficient"
    assert "سالب" in r.explanation


def test_threshold_bands_rejects_age_outside_configured_ranges():
    r = score_threshold_bands(120, {"bands": [{"min": 0, "max": 100, "score": 100}]})
    assert r.score is None
    assert r.status == "insufficient"


def test_structural_condition_accepts_common_arabic_spelling_variants():
    rubric = next(item["rubric"] for item in OFFICIAL_INDICATORS if item["code"] == "structural")
    assert score_category_map("رديء", rubric).score == 75
    assert score_category_map("رديء ومتهالك", rubric).score == 100


def test_density_ratio_relative_normalization():
    rubric = {"ratio": "units_per_feddan", "mode": "minmax"}
    ctx = {"density_units": {"min": 10, "max": 110}}
    r = score_density_ratio(60, None, 1.0, rubric, ctx)
    assert abs(r.score - 50.0) < 0.01  # midpoint of [10,110]


def test_density_ratio_missing_area_not_fabricated():
    r = score_density_ratio(60, 5, None, {}, {})
    assert r.score is None and r.status == "insufficient"


def test_modification_extent_presence_only_and_not_illegal_by_default():
    rubric = {}
    r = score_modification_extent("يوجد", "افقي ورأسي", "لا يوجد", rubric)
    assert r.score == 100
    assert r.status == "provisional"
    assert "لا يثبت" in r.explanation


def test_modification_extent_absence_scores_zero():
    r = score_modification_extent("لا يوجد", None, None, {})
    assert r.score == 0
    assert r.status == "provisional"


def test_modification_extent_missing_is_not_zero():
    r = score_modification_extent(None, None, None, {})
    assert r.score is None and r.status == "insufficient"


def test_infrastructure_connection_not_quality():
    rubric = {"connected_values": ["متصل"], "utilities": 4}
    r = score_infrastructure_ratio("متصل", "متصل", "متصل", "متصل", rubric)
    assert r.score == 100
    assert r.status == "provisional"  # connection presence only, not verified service quality
    assert "جودة" in r.explanation or "كفاءة" in r.explanation


def test_safety_flag_critical_for_removal_decision():
    assert safety_flag("ازالة ")["level"] == "critical"
    assert safety_flag("ترميم وإزالة")["level"] == "critical"


def test_safety_flag_warning_for_renovation_only():
    assert safety_flag("ترميم")["level"] == "warning"


def test_safety_flag_none_when_blank():
    assert safety_flag(None)["level"] == "none"
    assert safety_flag("لا يوجد")["level"] == "none"


def test_infrastructure_missing_one_field_is_not_assumed_disconnected():
    r = score_infrastructure_ratio("متصل", "متصل", None, "متصل", {"connected_values": ["متصل"], "utilities": 4})
    assert r.score is None
    assert r.status == "insufficient"
