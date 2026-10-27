"""Covers two redesign-specific behaviors not exercised by test_workflow.py:

1. DecisionNote / decision_service — the human-authored recommendation record
   used by Dashboard 2's decision summary (never auto-derived from the score).
2. The dual-study bootstrap in ui/common.py — the 29-project study must become
   active while the original 30-project study (if present) is preserved
   untouched as a separate historical study; the two datasets must never merge.
"""
from __future__ import annotations

from src.services import decision_service, project_service, study_service


def test_save_and_update_decision_note(db_session):
    study = study_service.create_study(db_session, "Decision Study", reference_year=2026)
    proj = project_service.add_project(db_session, study, {"external_id": "D1", "site_name": "Site D1"})

    assert decision_service.get_decision_note(db_session, proj.id) is None

    note = decision_service.save_decision_note(
        db_session, proj.id, decision_service.RECOMMENDATION_OPTIONS[0], "سبب أولي", "مقيّم أ",
    )
    assert note.recommendation == decision_service.RECOMMENDATION_OPTIONS[0]
    assert note.rationale == "سبب أولي"

    # Saving again for the same project updates in place rather than duplicating.
    updated = decision_service.save_decision_note(
        db_session, proj.id, decision_service.RECOMMENDATION_OPTIONS[1], "سبب محدَّث", "مقيّم ب",
    )
    assert updated.id == note.id
    assert updated.recommendation == decision_service.RECOMMENDATION_OPTIONS[1]
    assert updated.rationale == "سبب محدَّث"

    fetched = decision_service.get_decision_note(db_session, proj.id)
    assert fetched.recommendation == decision_service.RECOMMENDATION_OPTIONS[1]


def test_notes_by_project_batches_lookup(db_session):
    study = study_service.create_study(db_session, "Decision Study 2", reference_year=2026)
    p1 = project_service.add_project(db_session, study, {"external_id": "D2", "site_name": "Site D2"})
    p2 = project_service.add_project(db_session, study, {"external_id": "D3", "site_name": "Site D3"})

    decision_service.save_decision_note(db_session, p1.id, decision_service.RECOMMENDATION_OPTIONS[0], "ملاحظة", "")

    notes = decision_service.notes_by_project(db_session, [p1.id, p2.id])
    assert set(notes.keys()) == {p1.id}
    assert decision_service.notes_by_project(db_session, []) == {}


def test_corrected_scope_bootstrap_preserves_old_studies(tmp_path, monkeypatch):
    import pytest
    import src.db.database as dbmod
    from ui import common as ui_common
    from src.core.scoring import composite_dataframe
    from src.core.indicators import OFFICIAL_INDICATORS

    monkeypatch.setattr(dbmod, "DB_URL", f"sqlite:///{tmp_path}/bootstrap_test.sqlite3")
    monkeypatch.setattr(dbmod, "_engine", None)
    monkeypatch.setattr(dbmod, "_SessionLocal", None)
    ui_common._db_ready.clear()
    session = ui_common.get_db()
    current = next(s for s in study_service.list_studies(session) if s.name == ui_common.SCOPE_STUDY_NAME)
    projects = project_service.list_projects(session, current.id)
    assert len(projects) == 30
    assert len({p.external_id for p in projects}) == 30
    assert next(p for p in projects if p.external_id == "989").general_condition == "متهالك"
    assert sum(p.n_units or 0 for p in projects) == 22160
    assert sum(p.n_buildings or 0 for p in projects) == 1289
    configs = study_service.list_indicators(session, current.id)
    active = [c for c in configs if c.is_active]
    assert len(active) == 6
    assert "urban_env" not in {c.code for c in active}
    assert sum(c.weight for c in active) == pytest.approx(100)
    assert sum(i["weight"] for i in OFFICIAL_INDICATORS) == 100
    scores = composite_dataframe(projects, active, current)
    full = scores[scores.completeness_pct == 100]
    assert len(full) > 0
    for row in scores.itertuples():
        contributions = [getattr(row, "contrib_" + c.code) for c in active]
        assert sum(v for v in contributions if v is not None and v == v) == pytest.approx(row.priority_score, abs=.04)
    # Upgrade never edits or combines an existing study.
    legacy = study_service.create_study(session, ui_common.STUDY_NAME_29, reference_year=2026)
    project_service.add_project(session, legacy, {"external_id": "legacy", "site_name": "untouched"})
    ui_common._bootstrap_initial_study(session)
    assert len(study_service.list_studies(session)) == 2
    assert len(project_service.list_projects(session, legacy.id)) == 1
    assert len(project_service.list_projects(session, current.id)) == 30
    session.close()
