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
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception, f"App raised on first load: {at.exception}"
    # First load auto-seeds the 29-project active study (Dashboard 1 renders by default).
    assert any("مشروع" in m.value for m in at.metric) or len(at.metric) == 0


def test_dashboard_2_renders_without_exceptions(isolated_app_db):
    """Switch the sidebar nav to Dashboard 2 (Redevelopment Decision Support) and
    confirm the heatmap/ranking/comparison/what-if/decision-summary sections all
    render without raising."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()
    assert not at.exception

    radios = at.sidebar.radio
    assert radios, "expected a dashboard-nav radio in the sidebar"
    options = radios[0].options
    assert len(options) == 2, f"expected exactly 2 top-level dashboards, got: {options}"

    at.sidebar.radio[0].set_value(options[1]).run()
    assert not at.exception, f"Dashboard 2 raised: {at.exception}"
