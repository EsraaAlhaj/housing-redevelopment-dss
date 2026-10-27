from __future__ import annotations

import streamlit as st

from src.services import study_service


def render(session) -> None:
    st.header("إدارة الدراسات")
    st.caption("كل دراسة تحتفظ بمجموعة بيانات ومؤشرات وسيناريوهات مستقلة تمامًا عن الدراسات الأخرى.")

    studies = study_service.list_studies(session)
    if studies:
        st.subheader("الدراسات الحالية")
        st.dataframe([{
            "الاسم": s.name, "الوصف": s.description, "السنة المرجعية": s.reference_year,
            "تاريخ الإنشاء": s.created_at,
        } for s in studies], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("إنشاء دراسة جديدة")
    with st.form("new_study_form"):
        name = st.text_input("اسم الدراسة *", placeholder="مثال: بورسعيد - 108 مشروع")
        description = st.text_area("الوصف")
        reference_year = st.number_input("السنة المرجعية لحساب عمر المباني", min_value=1900, max_value=2100,
                                         value=2026, step=1)
        submitted = st.form_submit_button("إنشاء الدراسة", type="primary")
        if submitted:
            if not name.strip():
                st.error("اسم الدراسة إلزامي.")
            else:
                try:
                    study = study_service.create_study(session, name.strip(), description, int(reference_year))
                    st.session_state["active_study_id"] = study.id
                    st.success(f"تم إنشاء الدراسة: {study.name}")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    if studies:
        st.divider()
        st.subheader("إعدادات الدراسة النشطة")
        current = study_service.get_study(session, st.session_state.get("active_study_id", studies[0].id))
        if current:
            with st.form("study_settings_form"):
                ref_year = st.number_input("السنة المرجعية", min_value=1900, max_value=2100,
                                           value=current.reference_year, step=1)
                settings = current.settings()
                validated_th = st.slider("حد اكتمال التصنيف 'موثّق' (%)", 50, 100,
                                         int(settings.get("validated_completeness_threshold", 90)))
                provisional_th = st.slider("حد اكتمال التصنيف 'مبدئي' (الحد الأدنى %)", 0, 100,
                                           int(settings.get("provisional_completeness_threshold", 60)))
                dominant_w = st.slider("أدنى وزن يجعل المؤشر 'حاكمًا' (غيابه = بيانات غير كافية)", 0, 50,
                                       int(settings.get("dominant_indicator_min_weight", 30)))
                if st.form_submit_button("حفظ الإعدادات", type="primary"):
                    study_service.update_study_reference_year(session, current, int(ref_year))
                    study_service.update_study_settings(session, current, {
                        "validated_completeness_threshold": validated_th,
                        "provisional_completeness_threshold": provisional_th,
                        "dominant_indicator_min_weight": dominant_w,
                    })
                    st.success("تم حفظ الإعدادات.")
                    st.rerun()
