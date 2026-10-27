"""Housing Redevelopment Decision Support System — entry point.

Run locally with:  streamlit run app.py
No API keys, no paid services, no internet connection required after install.

Exactly two main dashboards (per redesign brief): Housing Conditions Assessment
and Redevelopment Decision Support. Study/data/indicator/export management is
still fully functional, reachable from the sidebar "الإدارة والبيانات" panel.
"""
from __future__ import annotations

import streamlit as st

from ui import dashboard_conditions, dashboard_decision, management, study_management
from ui.common import ensure_active_study, get_db, study_switcher
from ui.styles import RTL_CSS
from ui.theme import NAVY, TEAL, TEXT_MUTED

st.set_page_config(page_title="نظام دعم قرار إعادة تطوير الإسكان", layout="wide", page_icon="🏘️")
st.markdown(RTL_CSS, unsafe_allow_html=True)

PAGES = {
    "① تقييم حالة الإسكان": dashboard_conditions.render,
    "② دعم قرار إعادة التأهيل": dashboard_decision.render,
}


def main() -> None:
    session = get_db()

    st.sidebar.markdown(
        f"""<div style="padding:6px 2px 12px 2px; border-bottom:2px solid {TEAL}; margin-bottom:8px;">
        <div style="font-size:1.18rem; font-weight:700; color:{NAVY};">🏘️ نظام دعم القرار</div>
        <div style="font-size:0.82rem; color:{TEXT_MUTED};">إعادة تطوير الإسكان — بورسعيد</div>
        <div style="font-size:0.72rem; color:{TEXT_MUTED}; margin-top:6px; line-height:1.5;">
        المنهجية ومؤشرات التقييم مطابقة لمؤشر أولوية إعادة تطوير الإسكان الصادر عن صندوق التنمية العمرانية.
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    study = ensure_active_study(session)

    if study is None:
        st.warning("لا توجد دراسات بعد. يرجى إنشاء دراسة أولًا.")
        study_management.render(session)
        return

    study_switcher(session)
    study = ensure_active_study(session)

    management.render_sidebar(session, study)

    st.sidebar.markdown("---")
    st.sidebar.caption("لوحة المعلومات")
    nav_choice = st.sidebar.radio("لوحة المعلومات", list(PAGES.keys()), label_visibility="collapsed")

    PAGES[nav_choice](session, study)


if __name__ == "__main__":
    main()
