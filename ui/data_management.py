from __future__ import annotations

import streamlit as st

from src.core.validation import validate_import_rows
from src.db.models import DatasetVersion, ImportLog
from src.importers.excel_import import (
    STANDARD_FIELD_DEFS, apply_mapping, load_tabular_file, suggest_mapping,
)
from src.services import project_service
from ui.common import load_projects


def _import_tab(session, study) -> None:
    st.subheader("استيراد ملف Excel أو CSV")
    uploaded = st.file_uploader("اختر ملفًا", type=["xlsx", "xls", "csv"])
    if not uploaded:
        st.caption("يدعم النظام أي عدد من السجلات وأي أعمدة إضافية دون تعديل الكود.")
        return

    file_bytes = uploaded.getvalue()
    try:
        loaded = load_tabular_file(file_bytes, uploaded.name)
    except ValueError as e:
        st.error(str(e))
        return

    sheet_names = list(loaded["sheets"].keys())
    sheet = st.selectbox("الورقة (Sheet)", sheet_names,
                          index=sheet_names.index(loaded["default_sheet"]) if loaded["default_sheet"] in sheet_names else 0)
    df = loaded["sheets"][sheet]
    st.dataframe(df.head(5), use_container_width=True)
    st.caption(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")

    st.markdown("#### تخطيط الأعمدة إلى الحقول القياسية")
    suggestion = suggest_mapping(list(df.columns))
    field_labels = {f: f"{label}" + (" *" if req else "") for f, label, req, _ in STANDARD_FIELD_DEFS}
    field_options = ["— بدون تعيين —"] + [f for f, *_ in STANDARD_FIELD_DEFS]

    mapping = {}
    with st.form("mapping_form"):
        for col in df.columns:
            default = suggestion.get(col)
            default_idx = field_options.index(default) if default in field_options else 0
            chosen = st.selectbox(
                f"{col}", field_options, index=default_idx,
                format_func=lambda f: "— بدون تعيين —" if f == "— بدون تعيين —" else field_labels[f],
                key=f"map_{sheet}_{col}",
            )
            mapping[col] = None if chosen == "— بدون تعيين —" else chosen

        dataset_label = st.text_input("تصنيف مجموعة البيانات (مثال: استيراد أولي 30 مشروع)", value=uploaded.name)
        mode = st.radio("طريقة الدمج", ["merge", "replace_all"],
                        format_func=lambda m: "دمج/تحديث حسب المعرف الأصلي" if m == "merge"
                        else "استبدال كل المجموعة النشطة (أرشفة القديم)")
        confirm = st.form_submit_button("معاينة والتحقق")

    if confirm:
        mapped_targets = [v for v in mapping.values() if v]
        required = [f for f, _, req, _ in STANDARD_FIELD_DEFS if req]
        missing_required = [r for r in required if r not in mapped_targets]
        if missing_required:
            st.error(f"يجب تعيين الحقول الإلزامية: {', '.join(missing_required)}")
            return
        records = apply_mapping(df, mapping)
        issues = validate_import_rows(records)
        errors = [i for i in issues if i["level"] == "error"]
        warnings = [i for i in issues if i["level"] == "warning"]
        if errors:
            st.error(f"توجد {len(errors)} أخطاء تمنع الاستيراد:")
            st.dataframe(errors, use_container_width=True, hide_index=True)
        else:
            st.success(f"التحقق ناجح. {len(records)} سجل جاهز للاستيراد.")
            if warnings:
                st.warning(f"{len(warnings)} ملاحظة تحقق (لن تمنع الاستيراد):")
                st.dataframe(warnings, use_container_width=True, hide_index=True)
            st.session_state["pending_import"] = {
                "records": records, "filename": uploaded.name, "label": dataset_label, "mode": mode,
            }

    pending = st.session_state.get("pending_import")
    if pending:
        st.info(f"جاهز لاستيراد {len(pending['records'])} سجل بوضع: "
                f"{'دمج' if pending['mode']=='merge' else 'استبدال'}")
        if st.button("تأكيد الاستيراد الآن", type="primary"):
            result = project_service.import_records(
                session, study, pending["records"], pending["filename"], pending["label"], pending["mode"])
            if result["ok"]:
                st.success(f"تم الاستيراد: {result['created']} جديد، {result['updated']} محدَّث.")
                del st.session_state["pending_import"]
                st.rerun()
            else:
                st.error("فشل الاستيراد بسبب أخطاء تحقق.")


def _add_project_tab(session, study) -> None:
    st.subheader("إضافة مشروع جديد يدويًا")
    with st.form("add_project_form"):
        c1, c2 = st.columns(2)
        external_id = c1.text_input("المعرف الأصلي *")
        site_name = c2.text_input("اسم المشروع *")
        district = c1.text_input("الحي")
        general_condition = c2.selectbox("الحالة العامة للمبنى",
                                          ["", "متوسط", "ردئ", "متهالك", "ردئ ومتهالك", "جيد"])
        construction_year = c1.number_input("سنة الإنشاء", min_value=1800, max_value=2100, value=2000, step=1)
        strategic = c2.number_input("الأهمية الاستراتيجية (0-15)", min_value=0.0, max_value=15.0, value=0.0, step=0.5)
        n_buildings = c1.number_input("عدد العمارات", min_value=0.0, value=0.0, step=1.0)
        n_units = c2.number_input("عدد الوحدات", min_value=0.0, value=0.0, step=1.0)
        area_feddan = c1.number_input("المساحة بالفدان", min_value=0.0, value=0.0, step=0.1)
        building_decisions = c2.text_input("القرارات الصادرة للمبنى")
        submitted = st.form_submit_button("إضافة المشروع", type="primary")
        if submitted:
            if not external_id or not site_name:
                st.error("المعرف الأصلي واسم المشروع إلزاميان.")
            else:
                try:
                    project_service.add_project(session, study, {
                        "external_id": external_id, "site_name": site_name, "district": district,
                        "general_condition": general_condition, "construction_year": construction_year,
                        "strategic_importance_raw": strategic or None, "n_buildings": n_buildings or None,
                        "n_units": n_units or None, "area_feddan": area_feddan or None,
                        "building_decisions": building_decisions, "raw_data": "{}",
                    })
                    st.success("تمت الإضافة بنجاح.")
                    st.rerun()
                except Exception as e:  # noqa: BLE001 - surfaced to user, e.g. unique constraint
                    st.error(f"تعذرت الإضافة: {e}")


def _edit_archive_tab(session, study) -> None:
    st.subheader("تعديل / أرشفة المشروعات")
    projects = load_projects(session, study.id, include_archived=True)
    if not projects:
        st.caption("لا توجد مشروعات.")
        return
    options = {f"{p.site_name} ({p.external_id})" + (" [مؤرشف]" if p.is_archived else ""): p.id for p in projects}
    choice = st.selectbox("اختر مشروعًا للتعديل", list(options.keys()))
    project = next(p for p in projects if p.id == options[choice])

    with st.form("edit_project_form"):
        c1, c2 = st.columns(2)
        site_name = c1.text_input("اسم المشروع", value=project.site_name or "")
        district = c2.text_input("الحي", value=project.district or "")
        general_condition = c1.text_input("الحالة العامة للمبنى", value=project.general_condition or "")
        building_decisions = c2.text_input("القرارات الصادرة للمبنى", value=project.building_decisions or "")
        construction_year = c1.number_input("سنة الإنشاء", min_value=1800, max_value=2100,
                                             value=int(project.construction_year) if project.construction_year else 2000)
        strategic = c2.number_input("الأهمية الاستراتيجية (0-15)", min_value=0.0, max_value=15.0,
                                     value=float(project.strategic_importance_raw or 0))
        submitted = st.form_submit_button("حفظ التعديلات", type="primary")
        if submitted:
            project_service.update_project(session, project.id, {
                "site_name": site_name, "district": district, "general_condition": general_condition,
                "building_decisions": building_decisions, "construction_year": construction_year,
                "strategic_importance_raw": strategic,
            })
            st.success("تم حفظ التعديلات.")
            st.rerun()

    st.divider()
    col1, col2 = st.columns(2)
    if not project.is_archived:
        if col1.button("أرشفة هذا المشروع"):
            project_service.archive_project(session, project.id, True)
            st.success("تمت الأرشفة.")
            st.rerun()
    else:
        if col1.button("استعادة هذا المشروع"):
            project_service.archive_project(session, project.id, False)
            st.success("تمت الاستعادة.")
            st.rerun()


def _history_tab(session, study) -> None:
    st.subheader("سجل الإصدارات وتاريخ البيانات")
    versions = (session.query(DatasetVersion).filter(DatasetVersion.study_id == study.id)
                .order_by(DatasetVersion.created_at.desc()).all())
    if versions:
        st.dataframe([{
            "التصنيف": v.label, "الملف المصدر": v.source_filename, "عدد السجلات": v.row_count,
            "تاريخ الاستيراد": v.created_at,
        } for v in versions], use_container_width=True, hide_index=True)
    else:
        st.caption("لا يوجد سجل استيراد بعد.")

    logs = (session.query(ImportLog).filter(ImportLog.study_id == study.id)
            .order_by(ImportLog.created_at.desc()).limit(200).all())
    st.markdown("##### سجل العمليات (تدقيق)")
    if logs:
        st.dataframe([{"الإجراء": l.action, "التفاصيل": l.detail, "عدد السجلات": l.row_count,
                       "التاريخ": l.created_at} for l in logs], use_container_width=True, hide_index=True)
    else:
        st.caption("لا يوجد سجل عمليات بعد.")


def render(session, study) -> None:
    st.header("إدارة البيانات")
    tabs = st.tabs(["استيراد ملف", "إضافة مشروع", "تعديل / أرشفة", "سجل الإصدارات"])
    with tabs[0]:
        _import_tab(session, study)
    with tabs[1]:
        _add_project_tab(session, study)
    with tabs[2]:
        _edit_archive_tab(session, study)
    with tabs[3]:
        _history_tab(session, study)
