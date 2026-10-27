"""Shared Streamlit helpers: DB session, active-study selection, cached lookups."""
from __future__ import annotations

import os
import json

import streamlit as st

from src.core.scoring import composite_dataframe
from src.db.database import get_session, init_db
from src.importers.excel_import import apply_mapping, load_tabular_file, suggest_mapping
from src.services import project_service, study_service

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sample")
SAMPLE_FILE_29 = os.path.join(DATA_DIR, "PortSaid_29_Selected_Projects.xlsx")
SAMPLE_FILE_30 = os.path.join(DATA_DIR, "PortSaid_30_Projects_for_Claude.xlsx")

STUDY_NAME_29 = "بورسعيد - 29 مشروعًا (الدراسة النشطة)"
STUDY_NAME_30 = "بورسعيد - 30 مشروع (دراسة الحالة الأولى)"
SCOPE_FILE = os.path.join(DATA_DIR, "PortSaid_Scope_2026-10-27.xlsx")
SCOPE_STUDY_NAME = "بورسعيد — نطاق الدراسة المعتمد (30 مشروعًا)"
SCOPE_CONDITIONS = {"متوسط", "ردئ", "متهالك", "ردئ ومتهالك"}


@st.cache_resource
def _db_ready() -> bool:
    init_db()
    return True


def _seed_study_from_file(session, name: str, description: str, sample_file: str,
                           sheet_hint: str, dataset_label: str) -> None:
    study = study_service.create_study(session, name, description, 2026)
    with open(sample_file, "rb") as f:
        file_bytes = f.read()
    loaded = load_tabular_file(file_bytes, os.path.basename(sample_file))
    sheet = sheet_hint if sheet_hint in loaded["sheets"] else loaded["default_sheet"]
    df = loaded["sheets"][sheet]
    mapping = suggest_mapping(list(df.columns))
    records = apply_mapping(df, mapping)
    project_service.import_records(session, study, records, os.path.basename(sample_file),
                                    dataset_label, "merge")


def _bootstrap_initial_study(session) -> None:
    """Import the corrected 30-record scope as a separate, non-destructive study.

    Sheet1 contains 108 records. Sheet2 is a pivot and is never imported.
    The immutable official baseline remains available for comparison.
    """
    if any(s.name == SCOPE_STUDY_NAME for s in study_service.list_studies(session)):
        return
    if not os.path.exists(SCOPE_FILE):
        raise FileNotFoundError("ملف نطاق الدراسة المعتمد غير موجود: " + SCOPE_FILE)
    with open(SCOPE_FILE, "rb") as f:
        loaded = load_tabular_file(f.read(), os.path.basename(SCOPE_FILE))
    df = loaded["sheets"]["Sheet1"]
    df = df[df["الحالة_العامة_للمبني"].astype(str).str.strip().isin(SCOPE_CONDITIONS)]
    records = apply_mapping(df, suggest_mapping(list(df.columns)))
    if len(records) != 30 or len({r["external_id"] for r in records}) != 30:
        raise ValueError("ملف المصدر لا يطابق نطاق الدراسة المتوقع: 30 معرفًا فريدًا.")
    study = study_service.create_study(
        session, SCOPE_STUDY_NAME,
        "نطاق الدراسة: متوسط، ردئ، متهالك، وردئ ومتهالك. المصدر المعتمد بتاريخ 27 أكتوبر 2026.",
        2026,
    )
    try:
        project_service.import_records(
            session, study, records, os.path.basename(SCOPE_FILE),
            "نطاق الدراسة المعتمد — 30 مشروعًا", "merge",
        )
        for cfg in study_service.list_indicators(session, study.id):
            if cfg.code == "urban_env":
                cfg.is_active = False
            else:
                cfg.weight = cfg.weight / 95 * 100
        settings = study.settings()
        settings.update({"excluded_indicator_codes": ["urban_env"], "scope_model_version": "six-indicators-v1"})
        study.settings_json = json.dumps(settings, ensure_ascii=False)
        session.commit()
    except Exception:
        session.rollback()
        session.delete(study)
        session.commit()
        raise


def get_db():
    _db_ready()
    session = get_session()
    _bootstrap_initial_study(session)
    return session


def ensure_active_study(session) -> "Study | None":
    studies = study_service.list_studies(session)
    if not studies:
        return None
    if "active_study_id" not in st.session_state:
        preferred = next((s for s in studies if s.name == SCOPE_STUDY_NAME), studies[0])
        st.session_state["active_study_id"] = preferred.id
    study = study_service.get_study(session, st.session_state["active_study_id"])
    if study is None:
        st.session_state["active_study_id"] = studies[0].id
        study = studies[0]
    return study


def study_switcher(session) -> None:
    studies = study_service.list_studies(session)
    if not studies:
        return
    if len(studies) == 1:
        st.sidebar.caption(studies[0].name)
        st.session_state["active_study_id"] = studies[0].id
        return
    names = {s.id: s.name for s in studies}
    current = st.session_state.get("active_study_id", studies[0].id)
    selected = st.sidebar.selectbox(
        "الدراسة النشطة", options=list(names.keys()),
        format_func=lambda i: names[i],
        index=list(names.keys()).index(current) if current in names else 0,
    )
    st.session_state["active_study_id"] = selected


def load_projects(session, study_id: int, include_archived: bool = False):
    return project_service.list_projects(session, study_id, include_archived)


def load_scores(session, study, weights_override: dict | None = None, include_archived: bool = False):
    projects = load_projects(session, study.id, include_archived=include_archived)
    indicators = study_service.list_indicators(session, study.id)
    indicators = [i for i in indicators if i.is_active]
    manual = project_service.manual_assessments_by_project(session, study.id)
    return composite_dataframe(projects, indicators, study, weights_override, manual)


def active_indicators(session, study_id: int):
    return [i for i in study_service.list_indicators(session, study_id) if i.is_active]

