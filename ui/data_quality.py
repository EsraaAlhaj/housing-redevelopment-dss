from __future__ import annotations

import streamlit as st

from src.core.validation import data_quality_report
from src.services import project_service
from ui.common import active_indicators, load_projects, load_scores


def render(session, study) -> None:
    st.header("جودة البيانات")
    projects = load_projects(session, study.id, include_archived=True)
    if not projects:
        st.info("لا توجد مشروعات.")
        return

    indicators = active_indicators(session, study.id)
    report = data_quality_report(projects, [i.code for i in indicators])

    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي السجلات", len(report))
    c2.metric("سجلات بها ملاحظات", int((report["issue_count"] > 0).sum()))
    c3.metric("معرفات مكررة", int(report["has_duplicate_id"].sum()))

    st.subheader("تقرير جودة البيانات لكل سجل")
    show = report.rename(columns={
        "external_id": "المعرف", "site_name": "اسم المشروع", "district": "الحي",
        "issue_count": "عدد الملاحظات", "issues": "الملاحظات",
    }).drop(columns=["project_id", "has_duplicate_id"])
    st.dataframe(show, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("اكتمال المؤشرات عبر كل المشروعات")
    df = load_scores(session, study, include_archived=True)
    comp_rows = []
    for ind in indicators:
        status_col = f"status_{ind.code}"
        if status_col not in df.columns:
            continue
        counts = df[status_col].value_counts().to_dict()
        comp_rows.append({
            "المؤشر": ind.name_ar,
            "موثّق": counts.get("validated", 0),
            "مبدئي": counts.get("provisional", 0),
            "غير متاح": counts.get("insufficient", 0),
        })
    st.dataframe(comp_rows, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("إضافة تقييم ميداني موثّق (لمؤشرات بلا قياس في المصدر، مثل البيئة العمرانية)")
    with st.form("manual_assessment_form"):
        proj_options = {f"{p.site_name} ({p.external_id})": p.id for p in projects}
        proj_choice = st.selectbox("المشروع", list(proj_options.keys()))
        ind_options = {i.name_ar: i.code for i in indicators}
        ind_choice = st.selectbox("المؤشر", list(ind_options.keys()))
        score = st.slider("الدرجة (0-100)", 0, 100, 50)
        status = st.selectbox("حالة التوثيق", ["provisional", "validated"],
                              format_func=lambda s: "مبدئي" if s == "provisional" else "موثّق")
        source_note = st.text_area("مصدر التقييم والملاحظات (إلزامي)")
        submitted = st.form_submit_button("حفظ التقييم")
        if submitted:
            if not source_note.strip():
                st.error("يجب إدخال مصدر التقييم والملاحظات.")
            else:
                project_service.add_manual_assessment(
                    session, proj_options[proj_choice], ind_options[ind_choice],
                    float(score), status, source_note, assessed_by="مستخدم التطبيق",
                )
                st.success("تم حفظ التقييم اليدوي بنجاح. ستنعكس النتيجة في جميع صفحات التحليل.")
                st.rerun()
