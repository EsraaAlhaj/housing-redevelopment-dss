"""Unit tests for display-only name cleanup in ui.priority_dashboard.

display_name() must never invent or guess a project name — it only ever
substitutes a clear placeholder for known date/timestamp artifacts, and
otherwise returns the cleaned source value unchanged.
"""
from __future__ import annotations

from ui.priority_dashboard import display_name


def test_excel_serial_date_artifact_gets_placeholder():
    assert display_name("46157") == "اسم غير صالح في المصدر (قيمة تاريخ)"


def test_parsed_timestamp_artifact_gets_placeholder():
    assert display_name("2026-05-15 00:00:00") == "اسم غير صالح في المصدر (قيمة تاريخ)"


def test_date_only_artifact_gets_placeholder():
    assert display_name("2026-05-15") == "اسم غير صالح في المصدر (قيمة تاريخ)"


def test_real_project_name_is_preserved_unchanged():
    assert display_name("مجمع الزهور") == "مجمع الزهور"


def test_real_name_with_carriage_return_artifact_is_cleaned_not_flagged():
    assert display_name("مبنى الأمل_x000D_ الحي الأول") == "مبنى الأمل الحي الأول"


def test_none_value_returns_missing_placeholder():
    assert display_name(None) == "اسم غير متوفر"


def test_empty_string_returns_missing_placeholder():
    assert display_name("") == "اسم غير متوفر"


def test_whitespace_only_returns_missing_placeholder():
    assert display_name("   ") == "اسم غير متوفر"


def test_short_numeric_name_is_not_misflagged_as_date():
    # Only 5-digit (or longer, via the date pattern) values are treated as
    # artifacts; shorter numeric strings are left as-is.
    assert display_name("123") == "123"
