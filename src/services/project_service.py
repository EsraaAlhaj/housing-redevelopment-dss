"""Project CRUD + dataset import/merge/replace, with full audit trail (ImportLog,
DatasetVersion) so data history is never silently lost (spec section 6)."""
from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy.orm import Session

from src.core.validation import validate_import_rows
from src.db.models import Assessment, DatasetVersion, ImportLog, Project, Study

PROJECT_FIELDS = [
    "external_id", "site_name", "governorate", "city_center", "district", "owner_entity",
    "street_name", "n_buildings", "n_units", "unit_area", "area_feddan", "n_floors",
    "n_rooms_per_unit", "housing_type", "general_condition", "building_decisions",
    "construction_year", "strategic_importance_raw", "has_extensions", "extension_type",
    "ground_floor_use_change", "repeated_floor_use_change", "elec_connected", "water_connected",
    "sewage_connected", "gas_connected", "source_excel_row", "data_quality_notes_source",
    "raw_data",
]


def list_projects(session: Session, study_id: int, include_archived: bool = False) -> list[Project]:
    q = session.query(Project).filter(Project.study_id == study_id)
    if not include_archived:
        q = q.filter(Project.is_archived.is_(False))
    return q.order_by(Project.external_id).all()


def get_project(session: Session, project_id: int) -> Project | None:
    return session.get(Project, project_id)


def import_records(session: Session, study: Study, records: list[dict], source_filename: str,
                    dataset_label: str, mode: str = "merge") -> dict:
    """mode: 'merge' (upsert by external_id) or 'replace_all' (archive existing, insert fresh)."""
    issues = validate_import_rows(records)
    blocking = [i for i in issues if i["level"] == "error"]
    if blocking:
        return {"ok": False, "issues": issues, "created": 0, "updated": 0}

    version = DatasetVersion(
        study_id=study.id, label=dataset_label, source_filename=source_filename,
        row_count=len(records), is_active=True,
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    if mode == "replace_all":
        for p in list_projects(session, study.id, include_archived=True):
            if not p.is_archived:
                p.is_archived = True
                p.updated_at = dt.datetime.utcnow()
        session.commit()

    existing_by_ext = {p.external_id: p for p in list_projects(session, study.id, include_archived=True)}
    created, updated = 0, 0
    for rec in records:
        ext_id = str(rec.get("external_id", "")).strip()
        if not ext_id:
            continue
        payload = {k: rec.get(k) for k in PROJECT_FIELDS}
        existing = existing_by_ext.get(ext_id)
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            existing.is_archived = False
            existing.dataset_version_id = version.id
            existing.updated_at = dt.datetime.utcnow()
            updated += 1
        else:
            proj = Project(study_id=study.id, dataset_version_id=version.id, **payload)
            session.add(proj)
            existing_by_ext[ext_id] = proj
            created += 1
    session.commit()

    session.add(ImportLog(
        study_id=study.id, action="import",
        detail=f"ملف: {source_filename} | وضع: {mode} | تصنيف: {dataset_label}",
        row_count=len(records),
    ))
    session.commit()
    return {"ok": True, "issues": issues, "created": created, "updated": updated, "version_id": version.id}


def add_project(session: Session, study: Study, fields: dict) -> Project:
    payload = {k: fields.get(k) for k in PROJECT_FIELDS if k in fields}
    proj = Project(study_id=study.id, **payload)
    session.add(proj)
    session.commit()
    session.refresh(proj)
    session.add(ImportLog(study_id=study.id, action="add",
                           detail=f"إضافة مشروع يدويًا: {proj.external_id} / {proj.site_name}", row_count=1))
    session.commit()
    return proj


def update_project(session: Session, project_id: int, fields: dict) -> Project:
    proj = session.get(Project, project_id)
    for k, v in fields.items():
        if k in PROJECT_FIELDS:
            setattr(proj, k, v)
    proj.updated_at = dt.datetime.utcnow()
    session.commit()
    session.add(ImportLog(study_id=proj.study_id, action="edit",
                           detail=f"تعديل مشروع: {proj.external_id} / {proj.site_name}", row_count=1))
    session.commit()
    return proj


def archive_project(session: Session, project_id: int, archived: bool = True) -> Project:
    proj = session.get(Project, project_id)
    proj.is_archived = archived
    proj.updated_at = dt.datetime.utcnow()
    session.commit()
    session.add(ImportLog(study_id=proj.study_id, action="archive" if archived else "restore",
                           detail=f"{'أرشفة' if archived else 'استعادة'} مشروع: {proj.external_id}", row_count=1))
    session.commit()
    return proj


def manual_assessments_by_project(session: Session, study_id: int) -> dict:
    projects = list_projects(session, study_id, include_archived=True)
    pid_list = [p.id for p in projects]
    if not pid_list:
        return {}
    rows = session.query(Assessment).filter(Assessment.project_id.in_(pid_list)).all()
    out: dict[int, dict] = {}
    for a in rows:
        out.setdefault(a.project_id, {})[a.indicator_code] = a
    return out


def add_manual_assessment(session: Session, project_id: int, indicator_code: str, score: float | None,
                           status: str, source_note: str, assessed_by: str) -> Assessment:
    existing = (session.query(Assessment)
                .filter(Assessment.project_id == project_id, Assessment.indicator_code == indicator_code)
                .first())
    if existing:
        existing.score = score
        existing.status = status
        existing.source_note = source_note
        existing.assessed_by = assessed_by
        existing.is_manual = True
        existing.assessed_at = dt.datetime.utcnow()
        session.commit()
        return existing
    a = Assessment(project_id=project_id, indicator_code=indicator_code, score=score, status=status,
                    source_note=source_note, assessed_by=assessed_by, is_manual=True)
    session.add(a)
    session.commit()
    return a


def projects_to_dataframe(projects: list[Project]) -> pd.DataFrame:
    rows = []
    for p in projects:
        rows.append({f: getattr(p, f) for f in PROJECT_FIELDS if f != "raw_data"} | {
            "id": p.id, "is_archived": p.is_archived,
        })
    return pd.DataFrame(rows)
