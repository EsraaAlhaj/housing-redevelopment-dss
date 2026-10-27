from __future__ import annotations

from src.core.sensitivity import monte_carlo_stability, oat_sensitivity
from src.services import project_service, study_service
from tests.test_workflow import _import_sample


def test_sensitivity_analysis_runs_and_returns_stability_labels(db_session):
    study = study_service.create_study(db_session, "Sensitivity Study", reference_year=2026)
    _import_sample(db_session, study)
    indicators = study_service.list_indicators(db_session, study.id)
    projects = project_service.list_projects(db_session, study.id)
    weights = {i.code: i.weight for i in indicators}

    mc_df = monte_carlo_stability(projects, indicators, study, weights, trials=10, jitter_pct=15)
    assert not mc_df.empty
    assert set(mc_df["stability"].unique()).issubset(
        {"مستقر جدًا", "مستقر", "متوسط الحساسية", "شديد الحساسية"})

    oat_df = oat_sensitivity(projects, indicators, study, weights, delta_pct=10, steps=1)
    assert not oat_df.empty
    assert "rank_shift" in oat_df.columns
