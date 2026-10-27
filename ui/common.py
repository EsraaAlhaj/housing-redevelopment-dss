"""Shared Streamlit helpers: DB session, active-study selection, cached lookups."""
from __future__ import annotations

import os

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
    """Seed the current 29-project study on first run (or on upgrade from an
    older install that only has the 30-project study). The two datasets are
    NEVER merged: the previous 30-project study (if present) is left completely
    untouched as an independent historical study; the 29-project study is a
    separate, newly created study and becomes the active one."""
    existing_names = {s.name for s in study_service.list_studies(session)}

    if STUDY_NAME_29 in existing_names:
        return  # already bootstrapped — never re-run

    try:
        if not existing_names and os.path.exists(SAMPLE_FILE_30):
            # Totally fresh install: keep the original 30-project case study available
            # too, purely for historical continuity, but it is NOT the active study.
            _seed_study_from_file(
                session, STUDY_NAME_30,
                "دراسة الحالة الأولى (30 مشروعًا) — محفوظة كمرجع تاريخي مستقل.",
                SAMPLE_FILE_30, "Projects_30", "استيراد أولي — 30 مشروع",
            )
        if os.path.exists(SAMPLE_FILE_29):
            _seed_study_from_file(
                session, STUDY_NAME_29,
                "مجموعة البيانات المعتمدة حاليًا: 29 مشروعًا (متوسط 25، ردئ 1، ردئ ومتهالك 3).",
                SAMPLE_FILE_29, "Projects_29", "استيراد أولي — 29 مشروعًا",
            )
    except Exception:
        pass  # non-fatal: user can still import manually from لوحة الإدارة


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
        st.session_state["active_study_id"] = studies[0].id
    study = study_service.get_study(session, st.session_state["active_study_id"])
    if study is None:
        st.session_state["active_study_id"] = studies[0].id
        study = studies[0]
    return study


def study_switcher(session) -> None:
    studies = study_service.list_studies(session)
    if not studies:
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
