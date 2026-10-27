"""Dashboard 2 — Redevelopment Decision Support.

Main question: which housing projects should be prioritized for intervention,
and what is the evidence behind that priority? Sections A-F per the redesign
brief. The composite priority score is decision SUPPORT, not a verdict — the
system never auto-prescribes demolition/renovation. Section F always requires
a human-authored recommendation (src.services.decision_service).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.core.sensitivity import monte_carlo_stability
from src.core.scoring import composite_dataframe
from src.services import decision_service, scenario_service, study_service
from src.services.export_service import to_csv_bytes, to_excel_bytes
from ui.common import active_indicators, load_projects, load_scores
from ui.theme import (
    CATEGORICAL_SEQUENCE, GRAY_MISSING, NAVY, TEAL,
    apply_chart_theme, badge, render_kpi_row, section_header,
)

BUILDING_FIELDS = [
    ("district", "الحي"), ("general_condition", "الحالة العامة"), ("construction_year", "سنة الإنشاء"),
    ("n_buildings", "عدد العمارات"), ("n_units", "عدد الوحدات"), ("area_feddan", "المساحة (فدان)"),
    ("housing_type", "نوع الإسكان"), ("building_decisions", "القرارات الرسمية"),
]

HEATMAP_COLORSCALE = [[0.0, "#E6F2F1"], [0.5, TEAL], [1.0, NAVY]]


def _last_update_label(study) -> str:
    return f"السنة المرجعية لحساب العمر: {study.reference_year}"


def render(session, study) -> None:
    projects = load_projects(session, study.id, include_archived=False)

    st.markdown(
        f"""<div class="app-header">
        <div class="title">② دعم قرار إعادة التأهيل — Redevelopment Decision Support</div>
        <div class="subtitle">الدراسة النشطة: {study.name} &nbsp;|&nbsp; {_last_update_label(study)}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    if not projects:
        st.info("لا توجد مشروعات في هذه الدراسة بعد. استخدم «⚙️ الإدارة والبيانات» في الشريط الجانبي للاستيراد.")
        return

    indicators = active_indicators(session, study.id)
    df = load_scores(session, study)
    if df.empty:
        st.warning("تعذر حساب أي درجات أولوية — تحقق من إعداد المؤشرات.")
        return

    proj_by_id = {p.id: p for p in projects}

    # --- Section A: decision overview KPIs ----------------------------------
    section_header("نظرة عامة على حالة القرار", "ملخص حالة التقييم عبر كل المشروعات النشطة", "🧭")
    validated = int((df["classification"] == "Validated").sum())
    provisional = int((df["classification"] == "Provisional").sum())
    insufficient = int((df["classification"] == "Insufficient Data").sum())
    critical = int((df["safety_level"] == "critical").sum())
    render_kpi_row([
        ("إجمالي المشروعات المقيَّمة", f"{len(df):,}", "عدد السجلات التي لها درجة أولوية قابلة للحساب", "navy"),
        ("موثّق", f"{validated:,}", "اكتمال تقييم عالٍ وبدون مؤشرات مبدئية", "neutral"),
        ("مبدئي", f"{provisional:,}", "يحتاج توثيقًا إضافيًا لبعض المؤشرات", "warning" if provisional else "neutral"),
        ("بيانات غير كافية", f"{insufficient:,}", "مؤشر أساسي ناقص — لا يمكن الاعتماد على درجته", "critical" if insufficient else "neutral"),
        ("أعلام سلامة حرجة", f"{critical:,}", "قرار إزالة رسمي مسجل", "critical" if critical else "neutral"),
    ])

    # --- Section B: 29 x 7 indicator heatmap ---------------------------------
    section_header("الخريطة الحرارية للمؤشرات", "كل صف مشروع، كل عمود مؤشر رسمي — الخلايا الرمادية تعني بيانات غير متوفرة (وليست صفرًا)", "🗺️")
    ordered = df.sort_values("rank")
    row_labels = [f"{r.site_name} ({r.external_id})" for r in ordered.itertuples()]
    col_codes = [i.code for i in indicators]
    col_labels = [i.name_ar for i in indicators]
    pid_by_row = dict(zip(row_labels, ordered["project_id"]))
    code_by_col = dict(zip(col_labels, col_codes))

    z_real = ordered[[f"score_{c}" for c in col_codes]].to_numpy(dtype=float)
    z_missing = np.where(np.isnan(z_real), 1.0, np.nan)

    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=z_real, x=col_labels, y=row_labels, colorscale=HEATMAP_COLORSCALE, zmin=0, zmax=100,
        showscale=True, colorbar=dict(title="الدرجة"), hovertemplate="المشروع: %{y}<br>المؤشر: %{x}<br>الدرجة: %{z:.0f}<extra></extra>",
        name="الدرجات",
    ))
    fig.add_trace(go.Heatmap(
        z=z_missing, x=col_labels, y=row_labels, colorscale=[[0, GRAY_MISSING], [1, GRAY_MISSING]],
        zmin=0, zmax=1, showscale=False, hovertemplate="المشروع: %{y}<br>المؤشر: %{x}<br>بيانات غير متوفرة<extra></extra>",
        name="غير متوفر",
    ))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    apply_chart_theme(fig, height=max(480, 24 * len(row_labels)))
    event = st.plotly_chart(fig, key="decision_heatmap", on_select="rerun", selection_mode="points",
                             use_container_width=True)

    points = (event or {}).get("selection", {}).get("points", []) if hasattr(event, "get") else []
    real_points = [pt for pt in points if pt.get("curve_number", pt.get("curveNumber", 0)) == 0]
    if real_points:
        pt = real_points[0]
        pid = pid_by_row.get(pt.get("y"))
        code = code_by_col.get(pt.get("x"))
        if pid is not None and code is not None:
            row = df[df["project_id"] == pid].iloc[0]
            p = proj_by_id.get(pid)
            with st.container(border=True):
                st.markdown(f"**{p.site_name if p else pid}** — {pt.get('x')}")
                score, status, raw, explain = (row.get(f"score_{code}"), row.get(f"status_{code}"),
                                                row.get(f"raw_{code}"), row.get(f"explain_{code}"))
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"الدرجة: **{score:.0f}/100**" if score is not None else "الدرجة: —")
                c2.markdown(f"القيمة الخام: {raw or '—'}")
                c3.markdown(badge(status), unsafe_allow_html=True)
                st.caption(explain or "")
    else:
        st.caption("انقر على أي خلية في الخريطة لعرض القيمة الخام وتفسيرها.")

    # --- Section C: priority ranking -----------------------------------------
    section_header("ترتيب أولوية التدخل", "مرتَّب تنازليًا حسب درجة الأولوية المركّبة (WSM)", "📋")
    chart_df = df.dropna(subset=["priority_score"])
    if not chart_df.empty:
        fig_r = px.bar(
            chart_df.sort_values("priority_score"), x="priority_score", y="site_name", orientation="h",
            color="classification",
            color_discrete_map={"Validated": TEAL, "Provisional": "#D97706", "Insufficient Data": GRAY_MISSING},
            labels={"priority_score": "درجة الأولوية", "site_name": "المشروع", "classification": "التصنيف"},
        )
        st.plotly_chart(apply_chart_theme(fig_r, height=max(420, 22 * len(chart_df))), use_container_width=True)
    else:
        st.warning("لا توجد درجات أولوية قابلة للحساب حاليًا.")

    rank_table = df[["rank", "external_id", "site_name", "district", "priority_score",
                      "completeness_pct", "classification", "safety_level"]].copy()
    rank_table["classification"] = rank_table["classification"].map(lambda c: badge(c))
    rank_table["safety_level"] = rank_table["safety_level"].map(lambda s: badge(s))
    rank_table.columns = ["الترتيب", "المعرف", "اسم المشروع", "الحي", "درجة الأولوية",
                           "اكتمال التقييم %", "حالة التقييم", "علم السلامة"]
    st.markdown(rank_table.to_html(escape=False, index=False), unsafe_allow_html=True)

    st.markdown("**لماذا هذا الترتيب؟ — تفصيل المساهمات**")
    rank_options = {f"#{r.rank} — {r.site_name} ({r.external_id})": r.project_id for r in df.itertuples()}
    rank_choice = st.selectbox("اختر مشروعًا لعرض تفصيل مساهمة كل مؤشر", list(rank_options.keys()), key="rank_detail")
    _contribution_breakdown(df, indicators, rank_options[rank_choice])

    # --- Section D: compare 2-3 projects -------------------------------------
    section_header("مقارنة المشروعات", "اختر مشروعين إلى ثلاثة لعرض مقارنة تفصيلية", "⚖️")
    compare_options = {f"{r.site_name} ({r.external_id})": r.project_id for r in df.itertuples()}
    selected = st.multiselect("اختر المشروعات للمقارنة", list(compare_options.keys()), max_selections=3, key="compare_pick")
    if len(selected) < 2:
        st.caption("اختر مشروعين على الأقل لبدء المقارنة.")
    else:
        _comparison_panel(session, study, df, indicators, [compare_options[s] for s in selected], proj_by_id)

    # --- Section E: what-if scenario analysis (expander) ---------------------
    with st.expander("🧪 تحليل ماذا-لو (أوزان بديلة للمؤشرات)", expanded=False):
        _what_if_panel(session, study, indicators, projects)

    # --- Section F: decision summary -----------------------------------------
    section_header("ملخص القرار والتوصية", "لا يُصدر النظام قرار إزالة/ترميم تلقائيًا — القرار النهائي بشري وموثّق", "🧾")
    _decision_summary_panel(session, df, indicators, proj_by_id)

    st.divider()
    st.markdown("**تصدير سريع**")
    ecol1, ecol2 = st.columns(2)
    export_df = df.drop(columns=[c for c in df.columns if c.startswith("explain_")])
    with ecol1:
        st.download_button("⬇️ تصدير الترتيب الكامل (Excel)", to_excel_bytes({"الترتيب": export_df}),
                            file_name=f"ترتيب_الأولوية_{study.id}.xlsx", use_container_width=True)
    with ecol2:
        st.download_button("⬇️ تصدير الترتيب الكامل (CSV)", to_csv_bytes(export_df),
                            file_name=f"ترتيب_الأولوية_{study.id}.csv", use_container_width=True)


def _contribution_breakdown(df: pd.DataFrame, indicators: list, pid: int) -> None:
    row = df[df["project_id"] == pid].iloc[0]
    st.markdown(
        f"**درجة الأولوية:** {row['priority_score']}  |  **اكتمال التقييم:** {row['completeness_pct']}%  |  "
        f"**التصنيف:** {badge(row['classification'])}  |  **علم السلامة:** {badge(row['safety_level'])} — {row['safety_label']}",
        unsafe_allow_html=True,
    )
    contrib_rows = []
    for ind in indicators:
        score, status, contrib, explain = (row.get(f"score_{ind.code}"), row.get(f"status_{ind.code}"),
                                             row.get(f"contrib_{ind.code}"), row.get(f"explain_{ind.code}"))
        contrib_rows.append({
            "المؤشر": ind.name_ar, "الدرجة (0-100)": score, "المساهمة بالنقاط": contrib,
            "حالة التقييم": badge(status), "التفسير": explain,
        })
    table = pd.DataFrame(contrib_rows)
    st.markdown(table.to_html(escape=False, index=False), unsafe_allow_html=True)
    plot_rows = [r for r in contrib_rows if r["المساهمة بالنقاط"] is not None]
    if plot_rows:
        fig2 = px.bar(plot_rows, x="المؤشر", y="المساهمة بالنقاط", color_discrete_sequence=[TEAL],
                      title="مساهمة كل مؤشر في درجة الأولوية النهائية")
        st.plotly_chart(apply_chart_theme(fig2, height=320), use_container_width=True)


def _comparison_panel(session, study, df: pd.DataFrame, indicators: list, ids: list[int], proj_by_id: dict) -> None:
    sub = df[df["project_id"].isin(ids)].set_index("project_id").loc[ids]

    cols = st.columns(len(sub))
    for col, (_, row) in zip(cols, sub.iterrows()):
        with col:
            st.markdown(f"**{row['site_name']}**")
            st.metric("درجة الأولوية", row["priority_score"] if row["priority_score"] is not None else "—")
            st.markdown(badge(row["classification"]), unsafe_allow_html=True)
            st.caption(f"اكتمال التقييم: {row['completeness_pct']}%")
            st.markdown(badge(row["safety_level"]), unsafe_allow_html=True)

    ind_codes = [i.code for i in indicators]
    ind_labels = [i.name_ar for i in indicators]
    fig = go.Figure()
    for pid, row in sub.iterrows():
        values = [row.get(f"score_{c}") or 0 for c in ind_codes]
        fig.add_trace(go.Scatterpolar(r=values + [values[0]], theta=ind_labels + [ind_labels[0]],
                                       fill="toself", name=row["site_name"]))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=True)
    st.plotly_chart(apply_chart_theme(fig, height=420), use_container_width=True)

    st.markdown("**خصائص المباني**")
    build_table = []
    for field, label in BUILDING_FIELDS:
        row = {"الخاصية": label}
        for pid in ids:
            p = proj_by_id.get(pid)
            row[p.site_name if p else pid] = getattr(p, field, "") if p else ""
        build_table.append(row)
    st.dataframe(build_table, use_container_width=True, hide_index=True)

    st.markdown("**درجات المؤشرات وحالتها**")
    ind_table = []
    for ind in indicators:
        row = {"المؤشر": ind.name_ar, "الوزن %": ind.weight}
        for pid in ids:
            r = sub.loc[pid]
            score, status = r.get(f"score_{ind.code}"), r.get(f"status_{ind.code}")
            row[proj_by_id[pid].site_name] = f"{score:.0f} ({status})" if score is not None else "غير متاح"
        ind_table.append(row)
    st.dataframe(ind_table, use_container_width=True, hide_index=True)

    st.markdown("**أسباب فروق الأولوية**")
    valid_scores = sub["priority_score"].dropna()
    best_pid = valid_scores.astype(float).idxmax() if not valid_scores.empty else None
    if best_pid is not None:
        best_row = sub.loc[best_pid]
        st.markdown(f"**{proj_by_id[best_pid].site_name}** يحمل أعلى درجة أولوية ({best_row['priority_score']}).")
        for pid in ids:
            if pid == best_pid:
                continue
            r = sub.loc[pid]
            if r["priority_score"] is None:
                st.markdown(f"- {proj_by_id[pid].site_name}: لا يمكن حساب درجته (بيانات غير كافية).")
                continue
            diffs = []
            for ind in indicators:
                s1, s2 = best_row.get(f"score_{ind.code}"), r.get(f"score_{ind.code}")
                if s1 is not None and s2 is not None and abs(s1 - s2) >= 15:
                    diffs.append(f"{ind.name_ar} ({s1:.0f} مقابل {s2:.0f})")
            reason = "، ".join(diffs) if diffs else "فروق موزعة بالتساوي بين المؤشرات"
            st.markdown(f"- {proj_by_id[pid].site_name}: الفارق الرئيسي في — {reason}.")


def _what_if_panel(session, study, indicators: list, projects: list) -> None:
    wkey = f"decision_weights_{study.id}"
    if wkey not in st.session_state:
        st.session_state[wkey] = {i.code: i.weight for i in indicators}

    scenarios = scenario_service.list_scenarios(session, study.id)
    scenario_names = {s.name: s for s in scenarios}

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        load_choice = st.selectbox("تحميل سيناريو محفوظ", ["— جديد —"] + list(scenario_names.keys()), key="wi_load")
    with col_b:
        if st.button("تحميل", use_container_width=True, key="wi_load_btn") and load_choice != "— جديد —":
            st.session_state[wkey] = scenario_names[load_choice].weights()
            st.rerun()
    with col_c:
        if st.button("استعادة الأوزان الرسمية", use_container_width=True, key="wi_restore_btn"):
            study_service.restore_official_weights(session, study.id)
            st.session_state[wkey] = {i.code: i.weight for i in study_service.list_indicators(session, study.id) if i.is_active}
            st.rerun()

    weights = dict(st.session_state[wkey])
    cols = st.columns(2)
    for idx, ind in enumerate(indicators):
        with cols[idx % 2]:
            weights[ind.code] = st.slider(
                ind.name_ar, 0.0, 100.0, float(weights.get(ind.code, ind.weight)), 0.5,
                help=ind.description, key=f"wi_slider_{study.id}_{ind.code}",
            )
    st.session_state[wkey] = weights

    total = sum(weights.values())
    c1, c2 = st.columns([3, 1])
    with c1:
        if abs(total - 100) < 0.01:
            st.success(f"إجمالي الأوزان = {total:.1f}% ✓")
        else:
            st.warning(f"إجمالي الأوزان = {total:.1f}% — يجب أن يساوي 100% لحساب دقيق.")
    with c2:
        if st.button("توحيد تلقائي إلى 100%", use_container_width=True, key="wi_normalize") and total > 0:
            st.session_state[wkey] = {k: v / total * 100 for k, v in weights.items()}
            st.rerun()

    save_col1, save_col2, save_col3 = st.columns([2, 1, 1])
    with save_col1:
        new_name = st.text_input("اسم السيناريو الجديد للحفظ", key="wi_new_name")
    with save_col2:
        if st.button("حفظ السيناريو", use_container_width=True, key="wi_save") and new_name:
            try:
                scenario_service.save_scenario(session, study, new_name, weights)
                st.success(f"تم حفظ السيناريو: {new_name}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    with save_col3:
        if st.button("تطبيق كافتراضي للدراسة", use_container_width=True, key="wi_apply_default",
                     help="يجعل هذه الأوزان هي الافتراضية في كل لوحات المعلومات"):
            for ind in indicators:
                if ind.code in weights:
                    study_service.update_indicator_weight(session, ind.id, weights[ind.code])
            st.success("تم تطبيق الأوزان كافتراضي للدراسة.")
            st.rerun()

    scenario_df = composite_dataframe(projects, indicators, study, weights)
    st.markdown("**النتائج بالأوزان الحالية (ماذا-لو)**")
    cols_show = ["rank", "external_id", "site_name", "priority_score", "classification"]
    st.dataframe(
        scenario_df[cols_show].rename(columns={"rank": "الترتيب", "external_id": "المعرف", "site_name": "المشروع",
                                                 "priority_score": "درجة الأولوية", "classification": "التصنيف"}),
        use_container_width=True, hide_index=True,
    )

    with st.expander("📐 تحليل الحساسية (Monte Carlo) — مدى استقرار الترتيب", expanded=False):
        trials = st.slider("عدد المحاولات", 20, 150, 60, step=10, key="wi_mc_trials")
        jitter = st.slider("نسبة التذبذب العشوائي للأوزان (%)", 5, 30, 15, key="wi_mc_jitter")
        with st.spinner("جارٍ حساب الحساسية..."):
            mc_df = monte_carlo_stability(projects, indicators, study, weights, trials=trials, jitter_pct=jitter)
        if mc_df.empty:
            st.warning("تعذر حساب الحساسية — تأكد من وجود درجات أولوية قابلة للحساب.")
        else:
            show = mc_df.rename(columns={
                "base_rank": "الترتيب الأساسي", "site_name": "المشروع", "rank_min": "أفضل ترتيب",
                "rank_max": "أسوأ ترتيب", "rank_std": "الانحراف المعياري", "stability": "درجة الاستقرار",
            }).drop(columns=["project_id"])
            st.dataframe(show, use_container_width=True, hide_index=True)
            fig = px.bar(mc_df, x="site_name", y="rank_std", color="stability",
                         color_discrete_map={"مستقر جدًا": TEAL, "مستقر": "#5EAAA3",
                                              "متوسط الحساسية": "#D97706", "شديد الحساسية": "#B91C1C"},
                         labels={"site_name": "المشروع", "rank_std": "الانحراف المعياري للترتيب", "stability": "الاستقرار"})
            st.plotly_chart(apply_chart_theme(fig, height=360), use_container_width=True)


def _decision_summary_panel(session, df: pd.DataFrame, indicators: list, proj_by_id: dict) -> None:
    options = {f"{r.site_name} ({r.external_id})": r.project_id for r in df.itertuples()}
    choice = st.selectbox("اختر مشروعًا لإعداد ملخص القرار", list(options.keys()), key="summary_pick")
    pid = options[choice]
    p = proj_by_id.get(pid)
    row = df[df["project_id"] == pid].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**{p.site_name}**  \nمعرف: {p.external_id}  \nالحي: {p.district or '—'}")
    c2.metric("درجة الأولوية", row["priority_score"] if row["priority_score"] is not None else "—")
    c3.markdown(badge(row["classification"]) + " " + badge(row["safety_level"]), unsafe_allow_html=True)

    st.markdown("**جدول الأدلة (المؤشرات السبعة)**")
    evidence_rows = []
    contributions = {}
    missing = []
    for ind in indicators:
        score, status, raw, explain = (row.get(f"score_{ind.code}"), row.get(f"status_{ind.code}"),
                                         row.get(f"raw_{ind.code}"), row.get(f"explain_{ind.code}"))
        contrib = row.get(f"contrib_{ind.code}")
        if score is not None:
            contributions[ind.name_ar] = contrib or 0
        else:
            missing.append(ind.name_ar)
        evidence_rows.append({
            "المؤشر": ind.name_ar, "الوزن %": ind.weight, "القيمة الخام": raw or "—",
            "الدرجة": f"{score:.0f}" if score is not None else "—", "الحالة": badge(status), "التفسير": explain,
        })
    st.markdown(pd.DataFrame(evidence_rows).to_html(escape=False, index=False), unsafe_allow_html=True)

    st.markdown("**العوامل الرئيسية المؤثرة في الأولوية**")
    if contributions:
        top = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)[:3]
        for name, pts in top:
            st.markdown(f"- {name}: ساهم بـ {pts:.1f} نقطة في درجة الأولوية النهائية.")
    else:
        st.caption("لا تتوفر مساهمات قابلة للحساب.")

    st.markdown("**أعلام السلامة الحرجة**")
    if row["safety_level"] == "critical":
        st.error(row["safety_label"])
    elif row["safety_level"] == "warning":
        st.warning(row["safety_label"])
    else:
        st.success("لا توجد أعلام سلامة حرجة مسجلة لهذا المشروع.")

    st.markdown("**معايير ناقصة**")
    st.caption(", ".join(missing) if missing else "لا توجد معايير ناقصة — جميع المؤشرات لها قيم قابلة للحساب.")

    st.divider()
    st.markdown("**التوصية والقرار النهائي (بشري وموثّق)**")
    st.caption("النظام يعرض الأدلة فقط؛ لا يُصدر توصية إزالة أو ترميم تلقائية. يجب على المقيّم اختيار التوصية وتوثيق السبب.")
    existing = decision_service.get_decision_note(session, pid)
    rec_options = ["— اختر توصية —"] + decision_service.RECOMMENDATION_OPTIONS
    default_idx = rec_options.index(existing.recommendation) if existing and existing.recommendation in rec_options else 0
    recommendation = st.selectbox("التوصية", rec_options, index=default_idx, key=f"rec_{pid}")
    rationale = st.text_area("السبب / الأساس الفني للتوصية", value=existing.rationale if existing else "", key=f"rationale_{pid}")
    author = st.text_input("اسم المقيّم", value=existing.created_by if existing else "", key=f"author_{pid}")
    if st.button("💾 حفظ التوصية", key=f"save_{pid}"):
        if recommendation == "— اختر توصية —":
            st.error("يجب اختيار توصية قبل الحفظ.")
        elif not rationale.strip():
            st.error("يجب كتابة السبب/الأساس الفني للتوصية قبل الحفظ.")
        else:
            decision_service.save_decision_note(session, pid, recommendation, rationale.strip(), author.strip())
            st.success("تم حفظ التوصية.")
            st.rerun()
    if existing:
        st.caption(f"آخر حفظ: {existing.updated_at.strftime('%Y-%m-%d %H:%M')} بواسطة {existing.created_by or '—'}")
