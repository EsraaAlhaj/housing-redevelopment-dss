"""Planning-recommendation records (Dashboard 2, decision summary).

Deliberately a human-authored record, not a derived field: the composite
priority score is evidence to consider, never an automatic verdict. The system
must never auto-prescribe demolition/renovation (spec section 3).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from src.db.models import DecisionNote

RECOMMENDATION_OPTIONS = [
    "معاينة ميدانية عاجلة",
    "دراسة تفصيلية للتدخل",
    "استكمال بيانات ناقصة",
    "إعادة تقييم لاحقًا",
    "لا يوجد إجراء مطلوب حاليًا",
]


def get_decision_note(session: Session, project_id: int) -> DecisionNote | None:
    return session.query(DecisionNote).filter(DecisionNote.project_id == project_id).first()


def save_decision_note(session: Session, project_id: int, recommendation: str,
                        rationale: str, created_by: str = "") -> DecisionNote:
    note = get_decision_note(session, project_id)
    if note:
        note.recommendation = recommendation
        note.rationale = rationale
        note.created_by = created_by or note.created_by
        note.updated_at = dt.datetime.utcnow()
        session.commit()
        return note
    note = DecisionNote(project_id=project_id, recommendation=recommendation,
                         rationale=rationale, created_by=created_by)
    session.add(note)
    session.commit()
    return note


def notes_by_project(session: Session, project_ids: list[int]) -> dict[int, DecisionNote]:
    if not project_ids:
        return {}
    rows = session.query(DecisionNote).filter(DecisionNote.project_id.in_(project_ids)).all()
    return {n.project_id: n for n in rows}
