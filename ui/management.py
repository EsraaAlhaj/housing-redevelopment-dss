"""Optional management dialogs, separate from the ranking work surface."""
from __future__ import annotations

import streamlit as st

from ui import data_management, data_quality, export_page, indicator_config, study_management


@st.dialog("استيراد / إضافة / تعديل / أرشفة المشروعات", width="large")
def _data_management_dialog(session, study) -> None:
    data_management.render(session, study)


@st.dialog("إعداد المؤشرات والأوزان الرسمية", width="large")
def _indicator_config_dialog(session, study) -> None:
    indicator_config.render(session, study)


@st.dialog("إدارة الدراسات", width="large")
def _study_management_dialog(session) -> None:
    study_management.render(session)


@st.dialog("التصدير والتقارير القابلة للطباعة", width="large")
def _export_dialog(session, study) -> None:
    export_page.render(session, study)


@st.dialog("جودة البيانات والتقييمات اليدوية", width="large")
def _data_quality_dialog(session, study) -> None:
    data_quality.render(session, study)


def render_sidebar(session, study) -> None:
    """Call once per page, after the study switcher, from app.py."""
    st.sidebar.markdown("---")
    with st.sidebar.expander("⚙️ الإدارة والبيانات", expanded=False):
        if st.button("📥 استيراد / إضافة / أرشفة مشروعات", use_container_width=True, key="mgmt_data"):
            _data_management_dialog(session, study)
        if st.button("🧮 إعداد المؤشرات والأوزان", use_container_width=True, key="mgmt_indicators"):
            _indicator_config_dialog(session, study)
        if st.button("🔍 جودة البيانات وتقييم يدوي", use_container_width=True, key="mgmt_quality"):
            _data_quality_dialog(session, study)
        if st.button("📤 تصدير وتقارير", use_container_width=True, key="mgmt_export"):
            _export_dialog(session, study)
        if st.button("🏛️ إنشاء / تبديل الدراسات", use_container_width=True, key="mgmt_studies"):
            _study_management_dialog(session)

