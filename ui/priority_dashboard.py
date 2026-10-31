"""One ranking-first work surface with detail, comparison and export."""
from __future__ import annotations

import re
from html import escape

import pandas as pd
import streamlit as st

from src.services.export_service import to_csv_bytes
from ui.common import active_indicators, load_projects, load_scores
from ui.theme import STATUS_LABELS_AR, badge, render_kpi_row

# Matches source values that are date/timestamp artifacts rather than real names
# (Excel serial dates like "46157", or parsed timestamps like "2026-05-15 00:00:00").
# Display-only: never rewrites or infers a name, only swaps the rendered label.
_DATE_ARTIFACT_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}([ T]\d{1,2}:\d{2}:\d{2})?$|^\d{5}(\.0+)?$")

SAFETY_ICON = {"critical": "🔴", "warning": "🟠", "none": "⚪"}


def display_name(value) -> str:
    """Clean display artifacts without guessing names or rewriting the source."""
    cleaned = re.sub(r"\s+", " ", str(value or "").replace("_x000D_", " ")).strip()
    if not cleaned:
        return "اسم غير متوفر"
    if _DATE_ARTIFACT_RE.match(cleaned):
        return "اسم غير صالح في المصدر (قيمة تاريخ)"
    return cleaned


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
            "وزن الدراسة %": ind.weight,
            "الوزن المستخدم %": ind.weight if pd.notna(score) else None,
            "قيمة المصدر": row.get(f"raw_{ind.code}") or "غير متوفر",
            "الدرجة / 100": score,
            "المساهمة بالنقاط": row.get(f"contrib_{ind.code}"),
            "حالة القياس": STATUS_LABELS_AR.get(row.get(f"status_{ind.code}"), "غير متوفر"),
        })
    return pd.DataFrame(rows)


def ranking_table(scores, projects) -> pd.DataFrame:
    table = scores[["rank", "project_id", "priority_score", "completeness_pct", "classification", "safety_level"]].copy()
    table["المشروع"] = table.project_id.map(lambda pid: project_label(projects[pid]))
    table["الحي"] = table.project_id.map(lambda pid: projects[pid].district or "غير متوفر")
    table["الحالة العامة"] = table.project_id.map(lambda pid: projects[pid].general_condition or "غير متوفر")
    table["القرار المسجّل"] = table.project_id.map(lambda pid: projects[pid].building_decisions or "غير متوفر")
    table["حالة التقييم"] = table.classification.map(STATUS_LABELS_AR)
    table["حالة السلامة"] = table.safety_level.map(lambda lvl: f"{SAFETY_ICON.get(lvl, '⚪')} {STATUS_LABELS_AR.get(lvl, lvl)}")
    table = table.rename(columns={"rank": "الترتيب", "priority_score": "الأولوية / 100", "completeness_pct": "اكتمال البيانات %"})
    return table[["الترتيب", "المشروع", "الحي", "الأولوية / 100", "الحالة العامة", "حالة السلامة",
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
    st.markdown(f'<div class="scope-strip">نطاق الدراسة المعتمد <b>{len(projects)} مشروعًا</b><span>•</span>{len(indicators)} مؤشرات<span>•</span>أوزان الدراسة · النتيجة من 100</div>', unsafe_allow_html=True)
    search_col, district_col, condition_col = st.columns([2, 1, 1])
    with search_col:
        query = st.text_input("البحث عن مشروع", placeholder="اسم المشروع أو المعرّف", key=f"priority_search_{study.id}").strip()
    with district_col:
        districts = sorted({p.district for p in projects if p.district})
        district = st.selectbox("الحي", ["كل الأحياء"] + districts, key=f"priority_district_{study.id}")
    with condition_col:
        condition = st.selectbox("الحالة العامة", ["كل الحالات"] + sorted({p.general_condition for p in projects if p.general_condition}), key=f"priority_condition_{study.id}")
    visible_ids = {p.id for p in projects if (not query or query in project_label(p))
                   and (district == "كل الأحياء" or p.district == district)
                   and (condition == "كل الحالات" or p.general_condition == condition)}
    visible = scores[scores.project_id.isin(visible_ids)].copy()
    if visible.empty:
        st.info("لا توجد مشروعات تطابق البحث. عدّل الاسم أو الحي.")
        return

    status_counts = visible.classification.value_counts()
    critical_n = int((visible.safety_level == "critical").sum())
    flagged_n = critical_n + int((visible.safety_level == "warning").sum())
    with st.container(border=True):
        st.caption(f"نظرة عامة على {len(visible)} مشروعًا معروضًا")
        render_kpi_row([
            ("موثّق", str(int(status_counts.get("Validated", 0))), "بيانات كافية لاعتماد الدرجة", "neutral"),
            ("مبدئي", str(int(status_counts.get("Provisional", 0))), "درجة محسوبة من مؤشرات متاحة جزئيًا", "navy"),
            ("بيانات غير كافية", str(int(status_counts.get("Insufficient Data", 0))), "لا يمكن حساب درجة موثوقة", "neutral"),
            ("مشروعات بقرار يستدعي الانتباه", str(flagged_n), f"{critical_n} حرج وفق القرار المسجّل", "critical" if critical_n else ("warning" if flagged_n else "neutral")),
        ])

    list_col, detail_col = st.columns([1.45, 1], gap="large")
    with list_col:
        st.subheader("ترتيب أولوية المراجعة")
        st.caption(f"{len(visible)} من {len(projects)} سجلًا · الدرجة الأعلى تعني أولوية أكبر وفق النموذج الحالي. الترتيب محفوظ على مستوى الدراسة عند التصفية.")
        ranking = ranking_table(visible, by_id)
        selection = st.dataframe(ranking[["الترتيب", "المشروع", "الأولوية / 100", "الحالة العامة", "حالة السلامة", "اكتمال البيانات %"]], hide_index=True, use_container_width=True,
                     column_config={
                         "الترتيب": st.column_config.NumberColumn(width="small"),
                         "المشروع": st.column_config.TextColumn(width="medium"),
                         "الحالة العامة": st.column_config.TextColumn(width="small"),
                         "حالة السلامة": st.column_config.TextColumn(width="small"),
                         "الأولوية / 100": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
                         "اكتمال البيانات %": st.column_config.NumberColumn(format="%.1f%%", width="small"),
                     }, height=610, on_select="rerun", selection_mode="single-row", key=f"ranking_select_{study.id}_{query}_{district}_{condition}")
        st.caption("اضغط على صف لعرض ملف المشروع. الدرجة الجزئية تحتاج استكمال البيانات قبل المقارنة.")
    with detail_col:
        st.subheader("ملف المشروع")
        ids = list(visible.project_id)
        key = f"priority_project_{study.id}"
        if st.session_state.get(key) not in ids:
            st.session_state[key] = ids[0]
        if selection.selection.rows:
            selected_pid = int(visible.iloc[selection.selection.rows[0]].project_id)
            selection_token = (query, district, condition, selected_pid)
            if st.session_state.get(f"last_row_{study.id}") != selection_token:
                st.session_state[key] = selected_pid
                st.session_state[f"last_row_{study.id}"] = selection_token
        pid = st.selectbox("المشروع", ids, format_func=lambda value: project_label(by_id[value]), key=key)
        project = by_id[pid]
        row = scores[scores.project_id == pid].iloc[0]
        _detail(project, row, indicators, study)

    with st.expander("مقارنة مشروعين", expanded=False):
        ids = list(visible.project_id)
        compare_key = f"priority_compare_{study.id}"
        if compare_key in st.session_state:
            st.session_state[compare_key] = [pid for pid in st.session_state[compare_key] if pid in ids]
        picked = st.multiselect("المشروعات للمقارنة", ids, format_func=lambda pid: project_label(by_id[pid]),
                                max_selections=2, placeholder="اختر مشروعين للمقارنة", key=compare_key)
        if len(picked) == 2:
            _compare(scores, indicators, picked, by_id)
        else:
            st.caption("اختر مشروعين لعرض الدرجات وبيانات المصدر جنبًا إلى جنب.")

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
                                "الوزن النسبي %": [i.weight for i in indicators]})
        st.dataframe(weights, hide_index=True, use_container_width=True)
        if study.settings().get("preserve_original_weights"):
            st.write("درجة الأولوية = مجموع (درجة كل مؤشر × وزنه) ÷ 100. المؤشرات الناقصة لا تضيف نقاطًا، ولا يُعاد توزيع أوزانها على المؤشرات المتاحة.")
        else:
            st.write("درجة الأولوية = مجموع (درجة كل مؤشر × وزنه) ÷ مجموع أوزان المؤشرات المتاحة. عند نقص البيانات، تُعاد موازنة الأوزان المتاحة لحساب الدرجة؛ لذلك راجع نسبة اكتمال البيانات قبل المقارنة.")


def _detail(project, row, indicators, study) -> None:
    age = study.reference_year - project.construction_year if project.construction_year is not None else None
    st.markdown(f'<div class="project-card"><div class="project-kicker">{escape(project.district or "غير متوفر")} · {escape(project.general_condition or "غير متوفر")}</div><h3>{escape(project_label(project))}</h3><div class="score-number">{number(row.priority_score)}<small> / 100</small></div><div class="project-kicker">الترتيب {row["rank"]} · {STATUS_LABELS_AR.get(row.classification, row.classification)}</div><div class="project-facts"><span><b>{number(project.n_buildings, 0)}</b> عمارة</span><span><b>{number(project.n_units, 0)}</b> وحدة</span><span><b>{number(age, 0)}</b> سنة</span></div></div>', unsafe_allow_html=True)
    st.caption(f"اكتمال البيانات: {number(row.completeness_pct)}% · اكتمال البيانات لا يعني توثيق القياس")
    st.markdown(
        f'<div class="decision-note">{badge(row.safety_level)}'
        f'<div style="margin-top:8px;">القرار الرسمي المسجّل <strong>{escape(project.building_decisions or "غير متوفر")}</strong></div>'
        f'<div style="font-size:.7rem; color:#7C8C9C; margin-top:6px;">الشارة تعكس تصنيف القرار المسجّل حاليًا في النظام، ولا تمثل تقييم سلامة هندسي مستقل.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("**ما الذي يفسّر الدرجة؟**")
    bars = []
    for ind in indicators:
        points = row.get(f"contrib_{ind.code}")
        width = min(100, max(0, float(points) / ind.weight * 100)) if pd.notna(points) and ind.weight else 0
        bars.append(f'<div class="indicator-row"><div class="indicator-label"><span>{escape(ind.name_ar)}</span><b>{number(points)} <small>نقطة</small></b></div><div class="bar-track"><div style="width:{width}%"></div></div><div class="indicator-meta">الوزن {ind.weight:g}% · المساهمة القصوى {ind.weight:g} نقطة</div></div>')
    st.markdown("".join(bars), unsafe_allow_html=True)
    with st.expander("قيم المؤشرات وتفاصيل الحساب"):
        st.dataframe(indicator_table(row, indicators), hide_index=True, use_container_width=True)
    missing = [i.name_ar for i in indicators if pd.isna(row.get(f"score_{i.code}"))]
    if missing:
        st.info("يلزم استكمال: " + "، ".join(missing))



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
