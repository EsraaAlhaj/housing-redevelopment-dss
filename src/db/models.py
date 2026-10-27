"""SQLAlchemy ORM models for the Housing Redevelopment DSS.

Schema is generic by design: Project stores a fixed set of common fields used by
the scoring engine plus a raw_data JSON blob preserving every original column,
so new datasets with different/extra columns never require a schema change.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


class Study(Base):
    __tablename__ = "studies"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, default="")
    reference_year = Column(Integer, default=lambda: dt.date.today().year)
    is_active = Column(Boolean, default=True)
    settings_json = Column(Text, default="{}")  # classification thresholds, etc.
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    def settings(self) -> dict:
        try:
            return json.loads(self.settings_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    projects = relationship("Project", back_populates="study", cascade="all, delete-orphan")
    indicators = relationship("IndicatorConfig", back_populates="study", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="study", cascade="all, delete-orphan")
    dataset_versions = relationship("DatasetVersion", back_populates="study", cascade="all, delete-orphan")
    import_logs = relationship("ImportLog", back_populates="study", cascade="all, delete-orphan")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    label = Column(String(200), nullable=False)
    source_filename = Column(String(400), default="")
    row_count = Column(Integer, default=0)
    notes = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)

    study = relationship("Study", back_populates="dataset_versions")


class Project(Base):
    """One redevelopment project / building-cluster record."""
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("study_id", "external_id", name="uq_study_external_id"),)

    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    dataset_version_id = Column(Integer, ForeignKey("dataset_versions.id"), nullable=True)

    external_id = Column(String(100), nullable=False)  # original OBJECTID, preserved
    site_name = Column(String(400), default="")
    governorate = Column(String(200), default="")
    city_center = Column(String(200), default="")
    district = Column(String(200), default="")  # parsed/derived, never invented
    owner_entity = Column(String(300), default="")
    street_name = Column(String(300), default="")

    n_buildings = Column(Float, nullable=True)
    n_units = Column(Float, nullable=True)
    unit_area = Column(Float, nullable=True)
    area_feddan = Column(Float, nullable=True)
    n_floors = Column(Float, nullable=True)
    n_rooms_per_unit = Column(Float, nullable=True)

    housing_type = Column(String(200), default="")
    general_condition = Column(String(100), default="")  # الحالة_العامة_للمبني
    building_decisions = Column(String(200), default="")  # القرارات_الصادرة_للمبني (safety flag)
    construction_year = Column(Float, nullable=True)

    strategic_importance_raw = Column(Float, nullable=True)  # out of 15, can be missing

    has_extensions = Column(String(50), default="")
    extension_type = Column(String(100), default="")
    ground_floor_use_change = Column(String(200), default="")
    repeated_floor_use_change = Column(String(200), default="")

    elec_connected = Column(String(50), default="")
    water_connected = Column(String(50), default="")
    sewage_connected = Column(String(50), default="")
    gas_connected = Column(String(50), default="")

    is_archived = Column(Boolean, default=False)
    source_excel_row = Column(String(50), default="")
    data_quality_notes_source = Column(Text, default="")

    raw_data = Column(Text, default="{}")  # full original row as JSON (every column, any dataset)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    study = relationship("Study", back_populates="projects")
    assessments = relationship("Assessment", back_populates="project", cascade="all, delete-orphan")

    def raw(self) -> dict:
        try:
            return json.loads(self.raw_data or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}


class IndicatorConfig(Base):
    """One of the 7 official indicators, or a user-added custom indicator."""
    __tablename__ = "indicator_configs"
    __table_args__ = (UniqueConstraint("study_id", "code", name="uq_study_indicator_code"),)

    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)

    code = Column(String(60), nullable=False)
    name_ar = Column(String(300), nullable=False)
    name_en = Column(String(300), default="")
    weight = Column(Float, nullable=False)  # baseline/current weight, 0-100
    is_official = Column(Boolean, default=True)  # one of the 7 official indicators
    is_active = Column(Boolean, default=True)
    normalization_method = Column(String(50), nullable=False)
    # one of: category_map, threshold_bands, linear_scale, density_ratio,
    #         modification_extent, infrastructure_ratio, manual_assessment_only
    rubric_json = Column(Text, default="{}")
    source_columns_json = Column(Text, default="[]")
    description = Column(Text, default="")
    supported = Column(Boolean, default=True)  # False => flagged as unsupported calculation
    always_provisional = Column(Boolean, default=False)  # e.g. infra/modifications: inherently unverifiable
    sort_order = Column(Integer, default=0)

    study = relationship("Study", back_populates="indicators")

    def rubric(self) -> dict:
        try:
            return json.loads(self.rubric_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}


class Assessment(Base):
    """Per-project, per-indicator computed or manually-entered evaluation."""
    __tablename__ = "assessments"
    __table_args__ = (UniqueConstraint("project_id", "indicator_code", name="uq_project_indicator"),)

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    indicator_code = Column(String(60), nullable=False)

    score = Column(Float, nullable=True)  # 0-100, None if not computable
    raw_value = Column(String(300), default="")
    status = Column(String(30), default="insufficient")  # validated | provisional | insufficient
    explanation = Column(Text, default="")

    is_manual = Column(Boolean, default=False)
    source_note = Column(Text, default="")
    assessed_by = Column(String(200), default="")
    assessed_at = Column(DateTime, default=_now)

    project = relationship("Project", back_populates="assessments")


class Scenario(Base):
    """A saved alternative weight-set for what-if analysis."""
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("study_id", "name", name="uq_study_scenario_name"),)

    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    is_baseline = Column(Boolean, default=False)
    weights_json = Column(Text, nullable=False)  # {indicator_code: weight}
    created_at = Column(DateTime, default=_now)

    study = relationship("Study", back_populates="scenarios")

    def weights(self) -> dict:
        try:
            return json.loads(self.weights_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}


class ImportLog(Base):
    """Audit trail for data history preservation (section 6)."""
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True)
    study_id = Column(Integer, ForeignKey("studies.id"), nullable=False)
    action = Column(String(100), nullable=False)  # import | add | edit | archive | merge
    detail = Column(Text, default="")
    row_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)

    study = relationship("Study", back_populates="import_logs")


class DecisionNote(Base):
    """Researcher-recorded planning recommendation for a project (Dashboard 2 /
    decision summary). Deliberately free-text + a bounded recommendation choice —
    the system never auto-prescribes demolition/renovation from the composite score."""
    __tablename__ = "decision_notes"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    recommendation = Column(String(100), default="")  # e.g. معاينة ميدانية / دراسة تفصيلية / استكمال بيانات
    rationale = Column(Text, default="")
    created_by = Column(String(200), default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project")
