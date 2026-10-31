"""Six-indicator framework aligned with the latest reviewed scoring workbook (Port Said housing redevelopment priority).

This module defines the immutable BASELINE weights/rubrics. They are copied into
each new Study's IndicatorConfig rows, where they may be freely edited per-study
(scenario weights, rubric tuning) without ever changing this baseline definition
("the original official indicator weights must remain available as an unchanged
baseline" per the spec).

Rubrics are intentionally conservative: where the source data cannot support a
measurement (e.g. urban environment / public space quality has no column in the
dataset), the indicator is marked manual_assessment_only -> Insufficient Data
until a user supplies a verified manual assessment.
"""
from __future__ import annotations

OFFICIAL_INDICATORS = [
    {
        "code": "structural",
        "name_ar": "الحالة الإنشائية والعامة للمباني",
        "name_en": "Structural and General Building Condition",
        "weight": 35,
        "normalization_method": "category_map",
        "always_provisional": False,
        "source_columns": ["الحالة_العامة_للمبني"],
        "rubric": {
            "map": {
                "جيد": 20,
                "متوسط": 50,
                "ردئ": 75,
                "ردىء": 75,
                "متهالك": 90,
                "ردئ ومتهالك": 100,
                "ردىء ومتهالك": 100,
            },
            "default_if_unmapped": None,
        },
        "description": (
            "مبني على تصنيف الحالة العامة للمبنى (متوسط/ردئ/متهالك/ردئ ومتهالك). "
            "قرارات الترميم/الإزالة الرسمية تُعرض كتنبيه سلامة منفصل ولا تُدمج في هذا المؤشر."
        ),
    },
    {
        "code": "strategic",
        "name_ar": "الأهمية الاستراتيجية للموقع",
        "name_en": "Strategic Importance",
        "weight": 20,
        "normalization_method": "linear_scale",
        "always_provisional": False,
        "source_columns": ["الأهميه الأستراتيجيه"],
        "rubric": {"max_raw": 15},
        "description": (
            "قيمة خام من 0 إلى 15 كما وردت في المصدر، تُحوَّل خطيًا إلى 0-100. "
            "السجلات بلا قيمة تُعرض كبيانات ناقصة ولا تُستبدل بصفر."
        ),
    },
    {
        "code": "age",
        "name_ar": "العمر الزمني للمباني",
        "name_en": "Building Age",
        "weight": 15,
        "normalization_method": "threshold_bands",
        "always_provisional": False,
        "source_columns": ["سنة_الانشاء"],
        "rubric": {
            "reference_year_source": "study.reference_year",
            "bands": [
                {"min": 0, "max": 20, "score": 20},
                {"min": 20, "max": 40, "score": 50},
                {"min": 40, "max": 60, "score": 75},
                {"min": 60, "max": 1000, "score": 100},
            ],
        },
        "description": (
            "العمر = سنة مرجعية (قابلة للتعديل في إعدادات الدراسة) - سنة الإنشاء. "
            "يُحوَّل إلى درجة عبر نطاقات عمرية قابلة للتهيئة، ولا يُفترض أن العمر وحده يعني التدهور."
        ),
    },
    {
        "code": "density",
        "name_ar": "حجم المخزون السكني والكثافة العمرانية",
        "name_en": "Housing Stock and Urban Density",
        "weight": 10,
        "normalization_method": "density_ratio",
        "always_provisional": False,
        "source_columns": ["عدد_الوحدات", "عدد_العمارات", "المساحة_بالفدان"],
        "rubric": {"ratio": "units_per_feddan", "mode": "minmax"},
        "description": (
            "كثافة = عدد الوحدات / المساحة بالفدان (أو عدد العمارات إذا تعذر). "
            "تُطبَّع بمقياس أدنى-أعلى داخل مجموعة بيانات الدراسة الحالية (نسبي وليس مطلقًا)."
        ),
    },
    {
        "code": "modifications",
        "name_ar": "التعديلات والإضافات غير المعتمدة",
        "name_en": "Modifications & Extensions (extent, authorization unverified)",
        "weight": 10,
        "normalization_method": "modification_extent",
        "always_provisional": True,
        "source_columns": ["الامتدادات_بالعمارات", "نوع_الامتدادات", "هل_حدث_تغيير_في_استخدام_الدور_الارضي"],
        "rubric": {
            "extension_type_map": {"لا يوجد": 0, "بلكونة": 30, "افقي ورأسي": 70},
            "reconciliation_bonus": 15,
            "reconciliation_keyword": "تصالح",
        },
        "description": (
            "يقيس مدى وجود امتدادات/تعديلات على التصميم الأصلي فقط، وليس شرعيتها. "
            "وجود امتداد لا يثبت أنه غير معتمد؛ يلزم تقييم سند الموافقة. دائمًا 'مبدئي'."
        ),
    },
    {
        "code": "infrastructure",
        "name_ar": "حالة المرافق والبنية الأساسية",
        "name_en": "Infrastructure and Basic Services",
        "weight": 10,
        "normalization_method": "infrastructure_ratio",
        "always_provisional": True,
        "source_columns": [
            "اتصال_المشروع_بالكهرباء", "اتصال_المشروع_بالمياه",
            "اتصال_المشروع_بالصرف_الصحي", "اتصال_المشروع_بالغاز",
        ],
        "rubric": {"connected_values": ["متصل"], "utilities": 4},
        "description": (
            "نسبة المرافق المتصلة (كهرباء/مياه/صرف/غاز) من أصل 4. "
            "الاتصال لا يعادل جودة الخدمة أو كفاءتها؛ دائمًا 'مبدئي'."
        ),
    },
]

TOTAL_OFFICIAL_WEIGHT = sum(i["weight"] for i in OFFICIAL_INDICATORS)
assert len(OFFICIAL_INDICATORS) == 6
assert TOTAL_OFFICIAL_WEIGHT == 100

CRITICAL_DECISION_KEYWORDS = {
    "ازالة": "critical",
    "إزالة": "critical",
    "ترميم وإزالة": "critical",
    "ترميم وازالة": "critical",
    "ترميم": "warning",
}

DEFAULT_STUDY_SETTINGS = {
    "dominant_indicator_min_weight": 30,  # indicator at/above this weight is "dominant"; missing it -> Insufficient Data
    "validated_completeness_threshold": 90,
    "provisional_completeness_threshold": 60,
}
