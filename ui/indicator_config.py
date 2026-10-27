from __future__ import annotations

import json

import streamlit as st

from src.services import study_service

SUPPORTED_METHODS = {
    "category_map": "تصنيف فئوي (قيمة نصية ← درجة من جدول)",
    "linear_scale": "تحويل خطي (قيمة رقمية / الحد الأقصى × 100)",
    "threshold_bands": "نطاقات حدية (مثال: نطاقات العمر)",
    "density_ratio": "نسبة كثافة مع تطبيع نسبي داخل الدراسة",
    "modification_extent": "مدى التعديل/الامتداد (دائمًا مبدئي)",
    "infrastructure_ratio": "نسبة اتصال المرافق (دائمًا مبدئي)",
    "manual_assessment_only": "تقييم يدوي فقط (لا يوجد عمود مصدر)",
}


def render(session, study) -> None:
    st.header("إعداد المؤشرات")
    st.caption("الأوزان الرسمية السبعة تبقى متاحة كأساس ثابت دائمًا. أي تعديل هنا يخص الدراسة الحالية فقط.")

    indicators = study_service.list_indicators(session, study.id)

    st.subheader("المؤشرات الحالية")
    for ind in indicators:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{ind.name_ar}**" + ("" if ind.is_official else " _(مخصص)_"))
            c1.caption(ind.description)
            c1.caption("الأعمدة المصدر: " + (", ".join(json.loads(ind.source_columns_json or "[]")) or "—"))
            new_weight = c2.number_input("الوزن %", min_value=0.0, max_value=100.0, value=float(ind.weight),
                                          step=0.5, key=f"w_{ind.id}")
            if new_weight != ind.weight:
                study_service.update_indicator_weight(session, ind.id, new_weight)
                st.rerun()
            active = c3.checkbox("مُفعّل", value=ind.is_active, key=f"active_{ind.id}")
            if active != ind.is_active:
                ind.is_active = active
                session.commit()
                st.rerun()
            if not ind.supported:
                st.error("⚠️ طريقة حساب غير مدعومة لهذا المؤشر — لن يتم اختراع صيغة بديلة. "
                         "أدخل تقييمًا يدويًا موثقًا بدلًا من ذلك، أو عدّل طريقة الحساب.")
            elif ind.always_provisional:
                st.warning("هذا المؤشر يُصنَّف دائمًا 'مبدئي' لأن البيانات المتاحة لا تكفي لإثبات الجودة/الشرعية بشكل قاطع.")

    total = sum(i.weight for i in indicators if i.is_active)
    if abs(total - 100) > 0.5:
        st.warning(f"مجموع أوزان المؤشرات المُفعّلة = {total:.1f}% (يُفضَّل أن يكون 100%).")
    else:
        st.success(f"مجموع أوزان المؤشرات المُفعّلة = {total:.1f}% ✓")

    if st.button("استعادة الأوزان الرسمية لكل المؤشرات"):
        study_service.restore_official_weights(session, study.id)
        st.success("تمت استعادة الأوزان الرسمية.")
        st.rerun()

    st.divider()
    st.subheader("إضافة مؤشر مخصص جديد")
    with st.form("add_indicator_form"):
        code = st.text_input("رمز المؤشر (بالإنجليزية، بدون مسافات)")
        name_ar = st.text_input("اسم المؤشر بالعربية")
        weight = st.number_input("الوزن %", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
        method = st.selectbox("طريقة الحساب", list(SUPPORTED_METHODS.keys()),
                              format_func=lambda m: SUPPORTED_METHODS[m])
        description = st.text_area("وصف المؤشر وكيفية احتسابه")
        submitted = st.form_submit_button("إضافة المؤشر", type="primary")
        if submitted:
            if not code or not name_ar:
                st.error("رمز المؤشر واسمه إلزاميان.")
            else:
                rubric = {} if method != "linear_scale" else {"max_raw": 100}
                cfg = study_service.add_custom_indicator(
                    session, study, code.strip(), name_ar.strip(), weight, method, rubric, [], description)
                if not cfg.supported:
                    st.warning("تمت إضافة المؤشر، لكن طريقة الحساب تتطلب بيانات يدوية موثقة فقط "
                               "(سيظهر كـ'بيانات غير كافية' حتى إدخال تقييم يدوي).")
                st.success("تمت الإضافة.")
                st.rerun()
