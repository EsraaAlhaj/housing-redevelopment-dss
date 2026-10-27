"""Scenario (alternative weight-set) persistence for what-if analysis."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from src.db.models import Scenario, Study


def list_scenarios(session: Session, study_id: int) -> list[Scenario]:
    return (session.query(Scenario).filter(Scenario.study_id == study_id)
            .order_by(Scenario.is_baseline.desc(), Scenario.created_at).all())


def get_baseline_scenario(session: Session, study_id: int) -> Scenario | None:
    return (session.query(Scenario)
            .filter(Scenario.study_id == study_id, Scenario.is_baseline.is_(True)).first())


def save_scenario(session: Session, study: Study, name: str, weights: dict, description: str = "") -> Scenario:
    existing = (session.query(Scenario)
                .filter(Scenario.study_id == study.id, Scenario.name == name).first())
    if existing and existing.is_baseline:
        raise ValueError("لا يمكن الكتابة فوق سيناريو الأساس الرسمي.")
    if existing:
        existing.weights_json = json.dumps(weights, ensure_ascii=False)
        existing.description = description
        session.commit()
        return existing
    sc = Scenario(study_id=study.id, name=name, description=description, is_baseline=False,
                   weights_json=json.dumps(weights, ensure_ascii=False))
    session.add(sc)
    session.commit()
    return sc


def delete_scenario(session: Session, scenario_id: int) -> None:
    sc = session.get(Scenario, scenario_id)
    if sc and not sc.is_baseline:
        session.delete(sc)
        session.commit()
