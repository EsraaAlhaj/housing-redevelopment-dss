"""Integration tests covering the 10 scenarios required by the spec (section 12)."""
from __future__ import annotations

import io

import pandas as pd

from src.core.scoring import composite_dataframe
from src.core.validation import data_quality_report
from src.importers.excel_import import apply_mapping, load_tabular_file, suggest_mapping
from src.services import export_service, project_service, scenario_service, study_service
from tests.conftest import SAMPLE_XLSX, reopen_file_session


def _import_sample(session, study):
    with open(SAMPLE_XLSX, "rb") as f:
        file_bytes = f.read()
    loaded = load_tabular_file(file_bytes, "PortSaid_30_Projects_for_Claude.xlsx")
    df = loaded["sheets"]["Projects_30"]
    mapping = suggest_mapping(list(df.columns))
    records = apply_mapping(df, mapping)
    return project_service.import_records(session, study, records, "sample.xlsx", "initial", "merge")


# 1. Importing the initial 30 records.
def test_import_initial_30_records(db_session):
    study = study_service.create_study(db_session, "Port Said 30", reference_year=2026)
    result = _import_sample(db_session, study)
    assert result["ok"] is True
    assert result["created"] == 30
    projects = project_service.list_projects(db_session, study.id)
    assert len(projects) == 30
    ext_ids = {p.external_id for p in projects}
    assert len(ext_ids) == 30  # original identifiers preserved, no accidental merge


# 2. Uploading a different dataset (different size/columns — proves no hardcoding).
def test_upload_different_dataset(db_session):
    study = study_service.create_study(db_session, "Generic Study", reference_year=2024)
    csv_content = (
        "ProjectID,Name,Condition,YearBuilt\n"
        "A1,Test Site One,Poor,1990\n"
        "A2,Test Site Two,Medium,2005\n"
        "A3,Test Site Three,Deteriorated,1970\n"
    )
    df = pd.read_csv(io.BytesIO(csv_content.encode()))
    mapping = {"ProjectID": "external_id", "Name": "site_name", "Condition": None, "YearBuilt": "construction_year"}
    records = apply_mapping(df, mapping)
    result = project_service.import_records(db_session, study, records, "generic.csv", "generic import", "merge")
    assert result["ok"] is True
    assert result["created"] == 3
    projects = project_service.list_projects(db_session, study.id)
    assert {p.external_id for p in projects} == {"A1", "A2", "A3"}


# 3. Adding a project.
def test_add_project(db_session):
    study = study_service.create_study(db_session, "S1")
    proj = project_service.add_project(db_session, study, {
        "external_id": "NEW1", "site_name": "New Site", "general_condition": "متوسط",
        "construction_year": 1995,
    })
    assert proj.id is not None
    assert len(project_service.list_projects(db_session, study.id)) == 1


# 4. Editing a project.
def test_edit_project(db_session):
    study = study_service.create_study(db_session, "S1")
    proj = project_service.add_project(db_session, study, {"external_id": "E1", "site_name": "Old Name"})
    project_service.update_project(db_session, proj.id, {"site_name": "Updated Name"})
    updated = project_service.get_project(db_session, proj.id)
    assert updated.site_name == "Updated Name"


# 5. Saving data after application restart (simulated: close + reopen file-backed DB).
def test_data_persists_after_restart(file_db_session):
    session, db_path = file_db_session
    study = study_service.create_study(session, "Persistent Study")
    project_service.add_project(session, study, {"external_id": "P1", "site_name": "Persisted Project"})
    session.close()

    reopened = reopen_file_session(db_path)
    studies = study_service.list_studies(reopened)
    assert len(studies) == 1
    projects = project_service.list_projects(reopened, studies[0].id)
    assert len(projects) == 1
    assert projects[0].external_id == "P1"


# 6 & 7. Changing weights + recalculating scores automatically.
def test_changing_weights_recalculates_scores(db_session):
    study = study_service.create_study(db_session, "Weighted Study", reference_year=2026)
    _import_sample(db_session, study)
    indicators = study_service.list_indicators(db_session, study.id)
    projects = project_service.list_projects(db_session, study.id)

    baseline_weights = {i.code: i.weight for i in indicators}
    baseline_df = composite_dataframe(projects, indicators, study, baseline_weights)

    alt_weights = dict(baseline_weights)
    alt_weights["structural"] = 5.0
    alt_weights["age"] = 45.0  # redistribute weight away from structural condition
    alt_df = composite_dataframe(projects, indicators, study, alt_weights)

    baseline_scores = dict(zip(baseline_df["external_id"], baseline_df["priority_score"]))
    alt_scores = dict(zip(alt_df["external_id"], alt_df["priority_score"]))
    assert baseline_scores != alt_scores  # scores actually changed
    assert any(abs((baseline_scores[k] or 0) - (alt_scores[k] or 0)) > 0.01 for k in baseline_scores)


# 8. Creating a separate study (data isolation).
def test_separate_studies_are_isolated(db_session):
    study1 = study_service.create_study(db_session, "Study A")
    study2 = study_service.create_study(db_session, "Study B")
    project_service.add_project(db_session, study1, {"external_id": "X1", "site_name": "Only in A"})

    assert len(project_service.list_projects(db_session, study1.id)) == 1
    assert len(project_service.list_projects(db_session, study2.id)) == 0

    scenario_service.save_scenario(db_session, study1, "Alt A", {"structural": 50, "age": 50})
    assert len(scenario_service.list_scenarios(db_session, study1.id)) == 2  # baseline + alt
    assert len(scenario_service.list_scenarios(db_session, study2.id)) == 1  # only its own baseline


# 9. Handling missing values (never silently fabricated as zero).
def test_missing_values_not_fabricated(db_session):
    study = study_service.create_study(db_session, "Missing Data Study", reference_year=2026)
    _import_sample(db_session, study)
    indicators = study_service.list_indicators(db_session, study.id)
    projects = project_service.list_projects(db_session, study.id)
    df = composite_dataframe(projects, indicators, study)

    missing_strategic = df[df["status_strategic"] == "insufficient"]
    assert len(missing_strategic) == 5  # matches known source data quality notes
    assert missing_strategic["score_strategic"].isna().all()  # None, not 0

    quality = data_quality_report(projects, [i.code for i in indicators])
    assert len(quality) == 30


# 10. Exporting results.
def test_export_excel_and_csv(db_session):
    study = study_service.create_study(db_session, "Export Study", reference_year=2026)
    _import_sample(db_session, study)
    indicators = study_service.list_indicators(db_session, study.id)
    projects = project_service.list_projects(db_session, study.id)
    df = composite_dataframe(projects, indicators, study)

    excel_bytes = export_service.to_excel_bytes({"Ranking": df[["rank", "external_id", "priority_score"]]})
    assert excel_bytes[:2] == b"PK"  # valid xlsx (zip) signature

    csv_bytes = export_service.to_csv_bytes(df[["external_id", "priority_score"]])
    assert b"external_id" in csv_bytes
    assert len(csv_bytes) > 0
