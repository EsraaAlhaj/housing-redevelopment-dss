"""End-to-end smoke test: boots the real Streamlit app in-process (no browser needed)
via Streamlit's official AppTest framework, and checks it renders without exceptions."""
from __future__ import annotations

import os

import pytest

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


@pytest.fixture()
def isolated_app_db(tmp_path, monkeypatch):
    import src.db.database as dbmod
    from ui import common as ui_common
    monkeypatch.setattr(dbmod, "DB_URL", f"sqlite:///{tmp_path}/smoke_test.sqlite3")
    monkeypatch.setattr(dbmod, "_engine", None)
    monkeypatch.setattr(dbmod, "_SessionLocal", None)
    # ui.common.get_db() guards init_db() behind @st.cache_resource, which is
    # process-wide — without clearing it here, the 2nd test in this file would
    # reuse the 1st test's "already initialized" cache entry against a brand
    # new (tableless) tmp_path DB and fail with "no such table: studies".
    ui_common._db_ready.clear()
    yield


def test_app_boots_without_exceptions(isolated_app_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    assert not at.sidebar.radio
    assert len(at.dataframe[0].value) == 30
    assert len(at.dataframe[1].value) == 6
    assert "جودة البيئة العمرانية والفراغات العامة" not in set(at.dataframe[1].value["المؤشر"])


def test_search_and_empty_state(isolated_app_db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    original = at.dataframe[0].value.copy()
    at.text_input[0].set_value("989").run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 1
    assert "989" in at.dataframe[0].value.iloc[0]["المشروع"]
    expected = original[original["المشروع"].str.contains("989")].iloc[0]
    assert at.dataframe[0].value.iloc[0]["الترتيب"] == expected["الترتيب"]
    assert at.dataframe[0].value.iloc[0]["الأولوية / 95"] == expected["الأولوية / 95"]
    at.text_input[0].set_value("no-matching-project").run()
    assert not at.exception
    assert not at.dataframe
    assert at.info


def test_comparison_distinguishes_repeated_names(isolated_app_db):
    from streamlit.testing.v1 import AppTest
    from src.db.database import get_session
    from src.db.models import Project
    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    session = get_session()
    ids = [p.id for p in session.query(Project).filter(Project.external_id.in_(["1022", "1023"])).all()]
    session.close()
    at.multiselect[0].set_value(ids).run()
    assert not at.exception
    compared = next(d.value for d in at.dataframe if "البند" in d.value.columns)
    assert len(compared.columns) == 3
    assert any("1022" in c for c in compared.columns)
    assert any("1023" in c for c in compared.columns)
    # Changing the scope clears hidden selections and does not change ranking.
    at.text_input[0].set_value("989").run()
    assert not at.exception
    assert at.multiselect[0].value == []
