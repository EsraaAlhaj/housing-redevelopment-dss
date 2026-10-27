"""Dashboard 1 — Housing Conditions Assessment.

Main question: What is the current condition of the selected housing projects?
Sections A-D per the redesign brief, plus a transparent GIS-limitation note
(no fabricated coordinates — district-level charts stand in for a real map).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

from src.db.models import DatasetVersion
from ui.common import load_projects, load_scores
from ui.theme import CATEGORICAL_SEQUENCE, apply_chart_theme, badge, render_kpi_row, section_header


def _age(construction_year, reference_year) -> float | None:
    try:
        cy = float(construction_year)
    except (TypeError, ValueError):
        return None
    if not reference_year:
        return None
    return reference_year - cy


def _last_update(session, study) -> str:
    latest = (session.query(DatasetVersion).filter(DatasetVersion.study_id == study.id)
              .order_by(DatasetVersion.created_at.desc()).first())
    if latest:
        return latest.created_at.strftime("%Y-%m-%d")
    return "—"


def render(session, study) -> None:
    projects = load_projects(session, study.id, include_archived=False)

    st.markdown(
        f"""<div class="app-header">
        <div class="title">① تقييم حالة الإسكان — Housing Conditions Assessment</div>
        <div class="subtitle">الدراسة النشطة: {study.name} &nbsp;|&nbsp; آخر تحديث للبيانات: {_last_update(session, study)}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    if not projects:
        st.info("لا توجد مشروعات في هذه الدراسة بعد. استخدم «⚙️ الإدارة والبيانات» في الشريط الجانبي للاستيراد.")
        return

    df = load_scores(session, study)

    # --- Section A: filters -------------------------------------------------
    with st.expander("🔎 عوامل التصفية", expanded=False):
        fc1, fc2 = st.columns(2)
        districts = sorted([d for d in df["district"].dropna().unique() if d])
        sel_districts = fc1.multiselect("الحي", districts, default=districts)
        conditions = sorted({p.general_condition for p in projects if p.general_condition})
        sel_conditions = fc2.multiselect("الحالة العامة للمبنى", conditions, default=conditions)

    cond_by_pid = {p.id: (p.general_condition or "") for p in projects}
    mask = df["district"].isin(sel_districts) if sel_districts else pd.Series(True, index=df.index)
    if sel_conditions:
        mask &= df["project_id"].map(cond_by_pid).isin(sel_conditions)
    view = df[mask]
    ids = set(view["project_id"])
    fproj = [p for p in projects if p.id in ids]

    # --- Section B: KPI cards -----------------------------------------------
    section_header("مؤشرات الحجم والإنجاز", f"{len(fproj)} سجل من أصل {len(projects)} ضمن عوامل التصفية الحالية", "📊")
    from src.core.scoring import safety_flag
    with_decisions = sum(1 for p in fproj if safety_flag(p.building_decisions)["level"] != "none")
    avg_completeness = view["completeness_pct"].mean() if not view.empty else 0
    render_kpi_row([
        ("عدد السجلات المختارة", f"{len(fproj):,}", "إجمالي مشروعات/تجمعات المباني", "navy"),
        ("إجمالي عدد العمارات", f"{sum(p.n_buildings or 0 for p in fproj):,.0f}", "مجموع عدد العمارات المسجل", "neutral"),
        ("إجمالي عدد الوحدات السكنية", f"{sum(p.n_units or 0 for p in fproj):,.0f}", "مجموع عدد الوحدات المسجل", "neutral"),
        ("سجلات بقرارات تدخل رسمية", f"{with_decisions:,}", "ترميم / إزالة / قرار آخر مسجل", "warning" if with_decisions else "neutral"),
        ("اكتمال التقييم (متوسط)", f"{avg_completeness:.0f}%", "نسبة وزن المؤشرات القابلة للحساب فعليًا", "navy"),
    ])

    # --- Section C: analytical charts ---------------------------------------
    section_header("التوزيعات التحليلية", icon="📈")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**توزيع الحالة العامة للمباني**")
        cond_counts = pd.Series([p.general_condition or "غير محدد" for p in fproj]).value_counts().reset_index()
        cond_counts.columns = ["الحالة", "العدد"]
        fig = px.pie(cond_counts, names="الحالة", values="العدد", hole=0.42,
                     color_discrete_sequence=CATEGORICAL_SEQUENCE)
        fig.update_traces(textinfo="value+percent")
        st.plotly_chart(apply_chart_theme(fig, height=340), use_container_width=True)

    with col2:
        st.markdown("**توزيع المشروعات حسب الحي**")
        geo = pd.Series([p.district or "غير محدد" for p in fproj]).value_counts().reset_index()
        geo.columns = ["الحي", "عدد المشروعات"]
        fig2 = px.bar(geo, x="الحي", y="عدد المشروعات", color_discrete_sequence=CATEGORICAL_SEQUENCE, text="عدد المشروعات")
        st.plotly_chart(apply_chart_theme(fig2, height=340), use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**توزيع عمر المباني** (نسبةً للسنة المرجعية "
                     f"{study.reference_year})")
        ages = [a for a in (_age(p.construction_year, study.reference_year) for p in fproj) if a is not None]
        if ages:
            age_df = pd.DataFrame({"العمر (سنة)": ages})
            fig3 = px.histogram(age_df, x="العمر (سنة)", nbins=12, color_discrete_sequence=[CATEGORICAL_SEQUENCE[0]])
            fig3.update_layout(yaxis_title="عدد المشروعات")
            st.plotly_chart(apply_chart_theme(fig3, height=340), use_container_width=True)
        else:
            st.caption("لا تتوفر بيانات سنة إنشاء كافية لعرض توزيع العمر.")
        missing_age = len(fproj) - len(ages)
        if missing_age:
            st.caption(f"⚠️ {missing_age} سجلًا بدون سنة إنشاء — غير مُدرَج في هذا التوزيع (لا يُفترض له عمر افتراضي).")

    with col4:
        st.markdown("**تحليل الكثافة السكنية** (وحدة / فدان)")
        dens_rows = []
        for p in fproj:
            try:
                area = float(p.area_feddan) if p.area_feddan else None
                units = float(p.n_units) if p.n_units else None
            except (TypeError, ValueError):
                area, units = None, None
            if area and units and area > 0:
                dens_rows.append({"المشروع": p.site_name, "وحدة/فدان": round(units / area, 1)})
        if dens_rows:
            dens_df = pd.DataFrame(dens_rows).sort_values("وحدة/فدان", ascending=False).head(15)
            fig4 = px.bar(dens_df, x="وحدة/فدان", y="المشروع", orientation="h",
                          color_discrete_sequence=[CATEGORICAL_SEQUENCE[1]])
            st.plotly_chart(apply_chart_theme(fig4, height=340), use_container_width=True)
            st.caption(f"يُعرض أعلى {len(dens_df)} سجلًا كثافةً من أصل {len(dens_rows)} سجلًا تتوفر له مساحة وعدد وحدات صالحين.")
        else:
            st.caption("لا تتوفر بيانات مساحة/وحدات كافية لحساب الكثافة لأي سجل ضمن عامل التصفية الحالي.")

    # --- Section D: project data explorer -----------------------------------
    section_header("مستكشف بيانات المشروعات", "جدول قابل للبحث والفرز — اختر مشروعًا لعرض ملفه الكامل", "🗂️")
    search = st.text_input("🔍 بحث بالاسم أو المعرف أو الحي", "")
    table = view.copy()
    if search.strip():
        s = search.strip().lower()
        table = table[
            table["site_name"].astype(str).str.lower().str.contains(s, na=False)
            | table["external_id"].astype(str).str.lower().str.contains(s, na=False)
            | table["district"].astype(str).str.lower().str.contains(s, na=False)
        ]

    proj_by_id = {p.id: p for p in fproj}
    explorer_rows = []
    for _, r in table.iterrows():
        p = proj_by_id.get(r["project_id"])
        if p is None:
            continue
        explorer_rows.append({
            "المعرف": p.external_id, "اسم المشروع": p.site_name, "الحي": p.district or "—",
            "الحالة العامة": p.general_condition or "—",
            "سنة الإنشاء": int(p.construction_year) if p.construction_year else None,
            "العمر (سنة)": _age(p.construction_year, study.reference_year),
            "عدد العمارات": p.n_buildings, "عدد الوحدات": p.n_units,
            "القرارات الرسمية": p.building_decisions or "لا يوجد",
            "project_id": p.id,
        })
    explorer_df = pd.DataFrame(explorer_rows)
    st.dataframe(explorer_df.drop(columns=["project_id"]) if not explorer_df.empty else explorer_df,
                 use_container_width=True, hide_index=True)
    st.caption(f"عدد السجلات المعروضة: {len(explorer_df)}")

    if not explorer_df.empty:
        options = {f"{row['اسم المشروع']} ({row['المعرف']})": row["project_id"] for _, row in explorer_df.iterrows()}
        choice = st.selectbox("عرض تفصيلي لمشروع", ["—"] + list(options.keys()))
        if choice != "—":
            _project_detail_panel(options[choice], proj_by_id, view, study)

    # --- GIS-ready component (transparent about data limitation) -----------
    with st.expander("📍 الموقع الجغرافي (GIS)", expanded=False):
        st.info(
            "لا تتوفر في مصدر البيانات إحداثيات موقع موثّقة (عمود 'SHAPE *' في الملف الأصلي "
            "هو تصنيف هندسي عام 'Polygon' وليس هندسة فعلية/إحداثيات). عرض خريطة بإحداثيات "
            "مُفترضة يُعد تلفيقًا للبيانات وغير مسموح به — بدلاً من ذلك، يُستخدم التوزيع حسب "
            "الحي أعلاه كبديل تحليلي موثوق. عند توفر بيانات مساحية (GeoJSON لحدود الأحياء أو "
            "إحداثيات مشروعات موثّقة)، يمكن تفعيل خريطة فعلية دون أي تعديل في منطق النظام."
        )


def _project_detail_panel(pid: int, proj_by_id: dict, df: pd.DataFrame, study) -> None:
    p = proj_by_id.get(pid)
    if p is None:
        return
    row = df[df["project_id"] == pid]
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**{p.site_name}**  \nمعرف: {p.external_id}")
        c2.markdown(f"الحي: {p.district or '—'}  \nسنة الإنشاء: {int(p.construction_year) if p.construction_year else '—'}")
        if not row.empty:
            r = row.iloc[0]
            c3.markdown(badge(r["classification"]) + " " + badge(r["safety_level"]), unsafe_allow_html=True)
        tabs = st.tabs(["البيانات الأساسية", "بيانات إضافية من المصدر"])
        with tabs[0]:
            basic = {
                "المحافظة": p.governorate, "المدينة/المركز": p.city_center, "الجهة المالكة": p.owner_entity,
                "اسم الشارع": p.street_name, "نوع الإسكان": p.housing_type, "عدد الأدوار": p.n_floors,
                "عدد الغرف بالوحدة": p.n_rooms_per_unit, "مساحة الوحدة": p.unit_area,
                "المساحة بالفدان": p.area_feddan, "وجود امتدادات": p.has_extensions,
                "نوع الامتدادات": p.extension_type, "القرارات الرسمية": p.building_decisions,
                "اتصال الكهرباء": p.elec_connected, "اتصال المياه": p.water_connected,
                "اتصال الصرف الصحي": p.sewage_connected, "اتصال الغاز": p.gas_connected,
            }
            st.dataframe([{"الحقل": k, "القيمة": v or "—"} for k, v in basic.items()],
                         use_container_width=True, hide_index=True)
        with tabs[1]:
            raw = p.raw()
            if raw:
                st.dataframe([{"العمود الأصلي": k, "القيمة": v} for k, v in raw.items()],
                             use_container_width=True, hide_index=True)
            else:
                st.caption("لا توجد بيانات أصلية إضافية محفوظة لهذا السجل.")
