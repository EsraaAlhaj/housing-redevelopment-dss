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


def test_dual_study_bootstrap_keeps_datasets_separate(tmp_path, monkeypatch):
    """Fresh install: both the historical 30-project study and the active
    29-project study get seeded, but as fully independent Study rows — never
    merged into one project list."""
    import src.db.database as dbmod
    from ui import common as ui_common

    db_path = tmp_path / "bootstrap_test.sqlite3"
    monkeypatch.setattr(dbmod, "DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setattr(dbmod, "_engine", None)
    monkeypatch.setattr(dbmod, "_SessionLocal", None)

    ui_common._db_ready.clear()
    session = ui_common.get_db()

    studies = study_service.list_studies(session)
    names = {s.name for s in studies}
    assert ui_common.STUDY_NAME_29 in names
    assert ui_common.STUDY_NAME_30 in names

    study_29 = next(s for s in studies if s.name == ui_common.STUDY_NAME_29)
    study_30 = next(s for s in studies if s.name == ui_common.STUDY_NAME_30)
    assert study_29.id != study_30.id

    projects_29 = project_service.list_projects(session, study_29.id)
    projects_30 = project_service.list_projects(session, study_30.id)
    assert len(projects_29) == 29
    assert len(projects_30) == 30
    # Disjoint project rows — confirms the two datasets were never merged.
    assert set(p.id for p in projects_29).isdisjoint(p.id for p in projects_30)

    # Re-running the bootstrap (e.g. app reload) must not duplicate studies.
    ui_common._bootstrap_initial_study(session)
    assert len(study_service.list_studies(session)) == 2
