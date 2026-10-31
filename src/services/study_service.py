"""Study + indicator-configuration lifecycle. Each study is a fully isolated
project/assessment/scenario space (spec section 7)."""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy.orm import Session

from src.core.indicators import OFFICIAL_INDICATORS, DEFAULT_STUDY_SETTINGS
from src.db.models import IndicatorConfig, Scenario, Study


def seed_official_indicators(session: Session, study: Study) -> None:
    for order, ind in enumerate(OFFICIAL_INDICATORS):
        cfg = IndicatorConfig(
            study_id=study.id,
            code=ind["code"],
            name_ar=ind["name_ar"],
            name_en=ind["name_en"],
            weight=ind["weight"],
            is_official=True,
            is_active=True,
            normalization_method=ind["normalization_method"],
            rubric_json=json.dumps(ind["rubric"], ensure_ascii=False),
            source_columns_json=json.dumps(ind["source_columns"], ensure_ascii=False),
            description=ind["description"],
            supported=True,
            always_provisional=ind["always_provisional"],
            sort_order=order,
        )
        session.add(cfg)
    session.commit()


def create_study(session: Session, name: str, description: str = "",
                  reference_year: int | None = None) -> Study:
    existing = session.query(Study).filter(Study.name == name).first()
    if existing:
        raise ValueError(f"توجد دراسة بنفس الاسم بالفعل: {name}")
    study = Study(
        name=name,
        description=description,
        reference_year=reference_year or dt.date.today().year,
        is_active=True,
        settings_json=json.dumps(DEFAULT_STUDY_SETTINGS, ensure_ascii=False),
    )
    session.add(study)
    session.commit()
    session.refresh(study)
    seed_official_indicators(session, study)

    baseline_weights = {i["code"]: i["weight"] for i in OFFICIAL_INDICATORS}
    scenario = Scenario(
        study_id=study.id, name="الأوزان الرسمية (أساس)",
        description="الأوزان الرسمية المعتمدة من إطار التقييم — لا تُعدَّل.",
        is_baseline=True, weights_json=json.dumps(baseline_weights, ensure_ascii=False),
    )
    session.add(scenario)
    session.commit()
    return study


def list_studies(session: Session) -> list[Study]:
    return session.query(Study).order_by(Study.created_at.desc()).all()


def get_study(session: Session, study_id: int) -> Study | None:
    return session.get(Study, study_id)


def update_study_settings(session: Session, study: Study, settings: dict) -> Study:
    merged = {**study.settings(), **settings}
    study.settings_json = json.dumps(merged, ensure_ascii=False)
    study.updated_at = dt.datetime.utcnow()
    session.commit()
    return study


def update_study_reference_year(session: Session, study: Study, year: int) -> Study:
    study.reference_year = year
    study.updated_at = dt.datetime.utcnow()
    session.commit()
    return study


def list_indicators(session: Session, study_id: int) -> list[IndicatorConfig]:
    return (session.query(IndicatorConfig)
            .filter(IndicatorConfig.study_id == study_id)
            .order_by(IndicatorConfig.sort_order).all())


def update_indicator_weight(session: Session, indicator_id: int, weight: float) -> IndicatorConfig:
    cfg = session.get(IndicatorConfig, indicator_id)
    cfg.weight = weight
    session.commit()
    return cfg


def add_custom_indicator(session: Session, study: Study, code: str, name_ar: str, weight: float,
                          normalization_method: str, rubric: dict, source_columns: list[str],
                          description: str = "") -> IndicatorConfig:
    supported_methods = {
        "category_map", "linear_scale", "threshold_bands", "density_ratio",
        "modification_extent", "infrastructure_ratio", "manual_assessment_only",
    }
    supported = normalization_method in supported_methods
    cfg = IndicatorConfig(
        study_id=study.id, code=code, name_ar=name_ar, name_en="", weight=weight,
        is_official=False, is_active=True, normalization_method=normalization_method,
        rubric_json=json.dumps(rubric, ensure_ascii=False),
        source_columns_json=json.dumps(source_columns, ensure_ascii=False),
        description=description, supported=supported,
        always_provisional=not supported,
        sort_order=999,
    )
    session.add(cfg)
    session.commit()
    return cfg


def restore_official_weights(session: Session, study_id: int) -> None:
    official_by_code = {i["code"]: i["weight"] for i in OFFICIAL_INDICATORS}
    for cfg in list_indicators(session, study_id):
        if cfg.code == "urban_env":
            cfg.is_active = False
        elif cfg.code in official_by_code:
            cfg.weight = official_by_code[cfg.code]
            cfg.is_active = True

    # Keep the baseline scenario aligned with the current six-indicator framework.
    baseline = (session.query(Scenario)
                .filter(Scenario.study_id == study_id, Scenario.is_baseline.is_(True)).first())
    if baseline:
        baseline.weights_json = json.dumps(official_by_code, ensure_ascii=False)
        baseline.description = "الأوزان الأساسية للمؤشرات الستة وفق ملف التقييم الأخير."
    session.commit()
