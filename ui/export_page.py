from __future__ import annotations

import datetime as dt

import streamlit as st

from src.core.validation import data_quality_report
from src.services.export_service import to_csv_bytes, to_excel_bytes
from ui.common import active_indicators, load_projects, load_scores
from ui.styles import CLASSIFICATION_BADGE


def render(session, study) -> None:
    st.header("التصدير والتقارير")
    projects = load_projects(session, study.id, include_archived=False)
    if not projects:
        st.info("لا توجد مشروعات لتصديرها.")
        return

    df = load_scores(session, study)
    indicators = active_indicators(session, study.id)
    quality = data_quality_report(projects, [i.code for i in indicators])

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")

    st.subheader("تصدير شامل")
    ranking_cols = ["rank", "external_id", "site_name", "district", "priority_score",
                     "completeness_pct", "classification"]
    export_sheets = {
        "الترتيب": df[ranking_cols],
        "جودة البيانات": quality,
    }
    excel_bytes = to_excel_bytes(export_sheets)
    st.download_button("تنزيل تقرير Excel شامل", excel_bytes,
                       file_name=f"housing_dss_report_{stamp}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**الترتيب (CSV)**")
        st.download_button("تنزيل CSV", to_csv_bytes(df[ranking_cols]),
                           file_name=f"ranking_{stamp}.csv", mime="text/csv")
    with col2:
        st.markdown("**تقرير جودة البيانات (CSV)**")
        st.download_button("تنزيل CSV", to_csv_bytes(quality),
                           file_name=f"data_quality_{stamp}.csv", mime="text/csv")

    st.divider()
    st.subheader("عرض قابل للطباعة")
    st.caption("استخدم أمر الطباعة من المتصفح (Ctrl+P) لحفظ هذا العرض كملف PDF أو طباعته.")
    st.markdown(f"### تقرير أولوية إعادة التطوير — {study.name}")
    st.markdown(f"تاريخ التقرير: {dt.date.today().isoformat()} | عدد المشروعات: {len(df)}")
    print_table = df[ranking_cols].copy()
    print_table["classification"] = print_table["classification"].map(
        lambda c: CLASSIFICATION_BADGE.get(c, (None, c))[1])
    print_table.columns = ["الترتيب", "المعرف", "المشروع", "الحي", "درجة الأولوية", "اكتمال %", "التصنيف"]
    st.dataframe(print_table, use_container_width=True, hide_index=True)
