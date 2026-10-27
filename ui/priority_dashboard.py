"""One ranking-first work surface with detail, comparison and export."""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from src.services.export_service import to_csv_bytes
from ui.common import active_indicators, load_projects, load_scores
from ui.theme import STATUS_LABELS_AR


def display_name(value) -> str:
    """Clean display artifacts without guessing names or rewriting the source."""
    return re.sub(r"\s+", " ", str(value or "").replace("_x000D_", " ")).strip() or "اسم غير متوفر"


def number(value, decimals=1) -> str:
    return "غير متوفر" if value is None or pd.isna(value) else f"{value:,.{decimals}f}"


def project_label(project) -> str:
    return f"{display_name(project.site_name)} — {project.external_id}"


def indicator_table(row, indicators) -> pd.DataFrame:
    """Expose configured and effective weights; leave absent scores missing."""
    total = sum(i.weight for i in indicators if i.weight > 0)
    available = sum(i.weight for i in indicators if i.weight > 0 and pd.notna(row.get(f"score_{i.code}")))
    rows = []
    for ind in indicators:
        score = row.get(f"score_{ind.code}")
        rows.append({
            "المؤشر": ind.name_ar,
            "وزن الدراسة %": ind.weight / total * 100 if total else 0,
            "الوزن المستخدم %": ind.weight / available * 100 if available and pd.notna(score) else None,
            "قيمة المصدر": row.get(f"raw_{ind.code}") or "غير متوفر",
            "الدرجة / 100": score,
            "المساهمة بالنقاط": row.get(f"contrib_{ind.code}"),
            "حالة القياس": STATUS_LABELS_AR.get(row.get(f"status_{ind.code}"), "غير متوفر"),
        })
    return pd.DataFrame(rows)


def ranking_table(scores, projects) -> pd.DataFrame:
    table = scores[["rank", "project_id", "priority_score", "completeness_pct", "classification"]].copy()
    table["المشروع"] = table.project_id.map(lambda pid: project_label(projects[pid]))
    table["الحي"] = table.project_id.map(lambda pid: projects[pid].district or "غير متوفر")
    table["الحالة العامة"] = table.project_id.map(lambda pid: projects[pid].general_condition or "غير متوفر")
    table["القرار المسجّل"] = table.project_id.map(lambda pid: projects[pid].building_decisions or "غير متوفر")
    table["حالة التقييم"] = table.classification.map(STATUS_LABELS_AR)
    table = table.rename(columns={"rank": "الترتيب", "priority_score": "الأولوية / 100", "completeness_pct": "اكتمال البيانات %"})
    return table[["الترتيب", "المشروع", "الحي", "الأولوية / 100", "الحالة العامة",
                  "القرار المسجّل", "اكتمال البيانات %", "حالة التقييم"]]


def render(session, study) -> None:
    projects = load_projects(session, study.id)
    by_id = {p.id: p for p in projects}
    st.markdown(
        '<div class="decision-heading"><div class="decision-eyebrow">بورسعيد · دعم القرار</div>'
        '<h1>أولويات تطوير الإسكان</h1>'
        '<p>راجع ترتيب المشروعات، وافهم مساهمة كل مؤشر، وقارن قبل تحديد الإجراء.</p></div>',
        unsafe_allow_html=True,
    )
    if not projects:
        st.info("لا توجد مشروعات. يمكن استيرادها من الإدارة والبيانات.")
        return
    indicators = active_indicators(session, study.id)
    scores = load_scores(session, study)
    if scores.empty or not indicators or sum(i.weight for i in indicators) <= 0:
        st.warning("لا توجد نتائج قابلة للعرض. راجع إعدادات المؤشرات.")
        return
    st.caption(f"{study.name} · السنة المرجعية: {study.reference_year} · {len(projects)} سجلًا · {len(indicators)} مؤشرات نشطة")
    search_col, district_col = st.columns([2, 1])
    with search_col:
        query = st.text_input("البحث عن مشروع", placeholder="اسم المشروع أو المعرّف", key=f"priority_search_{study.id}").strip()
    with district_col:
        districts = sorted({p.district for p in projects if p.district})
        district = st.selectbox("الحي", ["كل الأحياء"] + districts, key=f"priority_district_{study.id}")
    visible_ids = {p.id for p in projects if (not query or query in project_label(p))
                   and (district == "كل الأحياء" or p.district == district)}
    visible = scores[scores.project_id.isin(visible_ids)].copy()
    if visible.empty:
        st.info("لا توجد مشروعات تطابق البحث. عدّل الاسم أو الحي.")
        return

    st.subheader("ترتيب أولوية المراجعة")
    st.caption(f"{len(visible)} من {len(projects)} سجلًا · الدرجة الأعلى تعني أولوية أكبر وفق النموذج الحالي. الترتيب محفوظ على مستوى الدراسة عند التصفية.")
    ranking = ranking_table(visible, by_id)
    st.dataframe(ranking, hide_index=True, use_container_width=True,
                 column_config={
                     "الأولوية / 100": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                     "اكتمال البيانات %": st.column_config.NumberColumn(format="%.1f%%"),
                 }, height=min(520, 40 + 36 * len(ranking)))
    st.caption("النتائج مبدئية: اتصال المرافق لا يقيس كفاءتها، ووجود تعديل لا يثبت أنه غير معتمد. اكتمال البيانات لا يعني توثيق القياس.")

    with st.expander("مقارنة مشروعين", expanded=False):
        ids = list(visible.project_id)
        compare_key = f"priority_compare_{study.id}"
        if compare_key in st.session_state:
            st.session_state[compare_key] = [pid for pid in st.session_state[compare_key] if pid in ids]
        picked = st.multiselect("المشروعات للمقارنة", ids, format_func=lambda pid: project_label(by_id[pid]),
                                max_selections=2, key=compare_key)
        if len(picked) == 2:
            _compare(scores, indicators, picked, by_id)
        else:
            st.caption("اختر مشروعين لعرض الدرجات وبيانات المصدر جنبًا إلى جنب.")

    st.divider()
    st.subheader("لماذا حصل المشروع على هذه الدرجة؟")
    ids = list(visible.project_id)
    key = f"priority_project_{study.id}"
    if st.session_state.get(key) not in ids:
        st.session_state[key] = ids[0]
    pid = st.selectbox("المشروع", ids, format_func=lambda value: project_label(by_id[value]), key=key)
    project = by_id[pid]
    row = scores[scores.project_id == pid].iloc[0]
    _detail(project, row, indicators, study)

    st.divider()
    export_left, export_right = st.columns(2)
    export_left.download_button("تصدير قائمة المشروعات الحالية", to_csv_bytes(ranking),
                                file_name=f"priority-ranking-{study.id}.csv", mime="text/csv", use_container_width=True)
    export_right.download_button("تصدير تفاصيل المشروع", to_csv_bytes(indicator_table(row, indicators).assign(
        معرف_المشروع=project.external_id, اسم_المشروع=display_name(project.site_name),
        درجة_الأولوية=row.priority_score, اكتمال_البيانات=row.completeness_pct,
    )), file_name=f"project-{project.external_id}-indicators.csv", mime="text/csv", use_container_width=True)

    with st.expander("الأوزان وطريقة احتساب النتيجة", expanded=False):
        weights = pd.DataFrame({"المؤشر": [i.name_ar for i in indicators],
                                "الوزن النسبي %": [i.weight / sum(j.weight for j in indicators) * 100 for i in indicators]})
        st.dataframe(weights, hide_index=True, use_container_width=True)
        st.write("درجة الأولوية = مجموع (درجة المؤشر × وزنه) ÷ مجموع أوزان المؤشرات ذات البيانات المتاحة.")
        if "urban_env" in study.settings().get("excluded_indicator_codes", []):
            st.caption("جودة البيئة العمرانية مستبعدة من النطاق، ولا تُحتسب كبيانات ناقصة. الأوزان الستة مطبّعة من 95 إلى 100؛ النموذج معدّل عن الإطار الأصلي.")
        st.caption("عند فقد قيمة، يعيد المحرك الحالي توزيع وزنها على المؤشرات المتاحة؛ يظهر الوزن المستخدم لكل مشروع في تفاصيله. التصفية لا تعيد حساب الأوزان أو الكثافة أو ترتيب الدراسة.")


def _detail(project, row, indicators, study) -> None:
    left, right = st.columns([1, 2])
    with left:
        st.metric("درجة الأولوية / 100", number(row.priority_score))
        st.caption(f"الترتيب في الدراسة: {row['rank']} · {STATUS_LABELS_AR.get(row.classification, row.classification)}")
    with right:
        st.markdown("**" + project_label(project) + "**")
        st.write(f"{project.district or 'الحي غير متوفر'} · {project.general_condition or 'الحالة غير متوفرة'}")
        st.write(f"{number(project.n_buildings, 0)} عمارة · {number(project.n_units, 0)} وحدة")
        age = study.reference_year - project.construction_year if project.construction_year is not None else None
        st.caption(f"العمر: {number(age, 0)} سنة · اكتمال البيانات: {number(row.completeness_pct)}%")
    decision = project.building_decisions or "غير متوفر"
    if row.safety_level == "critical":
        st.warning(f"القرار المسجّل: {decision}. راجع نص القرار ونطاق العمارات المشمولة به.")
    else:
        st.write(f"القرار المسجّل: {decision}")
    st.dataframe(indicator_table(row, indicators), hide_index=True, use_container_width=True,
                 column_config={label: st.column_config.NumberColumn(format="%.2f") for label in
                                ["وزن الدراسة %", "الوزن المستخدم %", "الدرجة / 100", "المساهمة بالنقاط"]})
    st.caption("المساهمة بالنقاط توضّح نصيب المؤشر من الدرجة النهائية؛ قد يوجد فرق طفيف بسبب التقريب. الخانة الفارغة تعني بيانات غير متوفرة.")
    missing = [i.name_ar for i in indicators if pd.isna(row.get(f"score_{i.code}"))]
    if missing:
        st.info("يلزم استكمال: " + "، ".join(missing))
    with st.expander("تفسير درجات المؤشرات", expanded=False):
        for ind in indicators:
            st.markdown(f"**{ind.name_ar}**")
            st.write(row.get(f"explain_{ind.code}") or "لا يتوفر تفسير مسجّل.")
    st.caption("درجة الأولوية توجه المراجعة والدراسات؛ تحديد الترميم أو الإزالة يحتاج تقييمًا هندسيًا ومراجعة القرار الرسمي.")


def _compare(scores, indicators, ids, by_id) -> None:
    rows = []
    selected = [scores[scores.project_id == pid].iloc[0] for pid in ids]
    labels = [project_label(by_id[pid]) for pid in ids]
    for field, label in [("priority_score", "درجة الأولوية / 100"), ("completeness_pct", "اكتمال البيانات %")]:
        rows.append({"البند": label, **{name: number(row[field]) for name, row in zip(labels, selected)}})
    for field, label in [("n_buildings", "عدد العمارات"), ("n_units", "عدد الوحدات"), ("building_decisions", "القرار المسجّل")]:
        rows.append({"البند": label, **{name: (str(getattr(by_id[pid], field)) if getattr(by_id[pid], field) is not None else "غير متوفر") for name, pid in zip(labels, ids)}})
    for ind in indicators:
        rows.append({"البند": ind.name_ar + " — الدرجة / 100",
                     **{name: number(row.get(f"score_{ind.code}")) for name, row in zip(labels, selected)}})
        rows.append({"البند": ind.name_ar + " — قيمة المصدر",
                     **{name: row.get(f"raw_{ind.code}") or "غير متوفر" for name, row in zip(labels, selected)}})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("تظهر البيانات الناقصة صراحةً؛ راجع اكتمال التقييم والأوزان المستخدمة قبل المفاضلة.")
