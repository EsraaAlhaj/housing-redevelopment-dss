"""Single-page housing redevelopment priority dashboard."""
from __future__ import annotations

import streamlit as st

from ui import priority_dashboard, management, study_management
from ui.common import ensure_active_study, get_db, study_switcher
from ui.styles import RTL_CSS
from ui.theme import NAVY, TEAL, TEXT_MUTED

st.set_page_config(page_title="نظام دعم قرار إعادة تطوير الإسكان", layout="wide", initial_sidebar_state="collapsed", page_icon="🏘️")
st.markdown(RTL_CSS, unsafe_allow_html=True)

def main() -> None:
    session = get_db()

    st.sidebar.markdown(
        f"""<div style="padding:6px 2px 12px 2px; border-bottom:2px solid {TEAL}; margin-bottom:8px;">
        <div style="font-size:1.18rem; font-weight:700; color:{NAVY};">🏘️ نظام دعم القرار</div>
        <div style="font-size:0.82rem; color:{TEXT_MUTED};">إعادة تطوير الإسكان — بورسعيد</div>
        <div style="font-size:0.72rem; color:{TEXT_MUTED}; margin-top:6px; line-height:1.5;">
        نموذج دعم قرار معدّل للدراسة؛ نتائج التقييم مبدئية وقابلة للمراجعة.
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

    priority_dashboard.render(session, study)
    session.close()


if __name__ == "__main__":
    main()

