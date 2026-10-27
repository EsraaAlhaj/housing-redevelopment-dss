"""Arabic RTL styling — professional, minimal, no decorative animation.
Colors/fonts are centralized in ui/theme.py; this module only wires global CSS.
"""
from ui.theme import AMBER, BG, BG_SOFT, BORDER, FONT_STACK, NAVY, RED, TEAL, TEXT, TEXT_MUTED

RTL_CSS = f"""
<style>
/* Cairo is loaded as a progressive enhancement only — the stack already falls
   back to Tahoma/Segoe UI (both ship with Windows), so the UI remains fully
   readable with correct Arabic shaping when offline and this import fails. */
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

html, body, [class*="css"] {{ direction: rtl; font-family: {FONT_STACK}; color: {TEXT}; }}
.block-container {{ direction: rtl; padding-top: 1.4rem; max-width: 1400px; }}
section[data-testid="stSidebar"] {{ direction: rtl; background: {BG_SOFT}; border-left: 1px solid {BORDER}; }}
div[data-testid="stMetricValue"] {{ direction: ltr; text-align: center; color: {NAVY}; }}
div[data-testid="stMetricLabel"] {{ justify-content: center; }}
table {{ direction: rtl; }}
thead tr th {{ text-align: right !important; background: {BG_SOFT} !important; color: {NAVY} !important; }}
tbody tr td {{ text-align: right !important; }}

h1, h2, h3, h4 {{ font-weight: 700; color: {NAVY}; }}
h1 {{ font-size: 1.6rem; }}
p, label, span {{ color: {TEXT}; }}

/* Primary buttons -> teal accent, not default red/purple */
button[kind="primary"], .stButton>button[kind="primary"] {{
  background: {TEAL} !important; border-color: {TEAL} !important; color: white !important;
}}
.stButton>button {{ border-radius: 8px; font-weight: 600; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 8px 8px 0 0; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ color: {TEAL} !important; border-bottom-color: {TEAL} !important; }}

/* Status badges (legacy helper, kept for pages not yet migrated to ui.theme.badge) */
.badge {{ display:inline-block; padding: 3px 11px; border-radius: 12px; font-size: 0.8em; font-weight:600; }}
.badge-validated {{ background:{TEAL}; color:#fff; }}
.badge-provisional {{ background:{AMBER}; color:#fff; }}
.badge-insufficient {{ background:#CBD5E1; color:{NAVY}; }}
.badge-critical {{ background:{RED}; color:#fff; }}
.badge-warning {{ background:{AMBER}; color:#fff; }}
.badge-none {{ background:#E2E8F0; color:{TEXT_MUTED}; }}

.kpi-card {{ background:{BG_SOFT}; border:1px solid {BORDER}; border-radius:10px; padding:14px 18px; }}

.app-header {{
  background: linear-gradient(90deg, {NAVY} 0%, {NAVY}E6 100%);
  color: white; padding: 18px 26px; border-radius: 12px; margin-bottom: 14px;
}}
.app-header .title {{ font-size: 1.35rem; font-weight: 700; color: white; }}
.app-header .subtitle {{ font-size: 0.9rem; color: #CBD5E1; margin-top: 2px; }}

hr {{ border-color: {BORDER}; }}

@media print {{
  section[data-testid="stSidebar"] {{ display:none !important; }}
  header[data-testid="stHeader"] {{ display:none !important; }}
  .stButton, .stDownloadButton {{ display:none !important; }}
}}
</style>
"""

CLASSIFICATION_BADGE = {
    "Validated": ("badge-validated", "موثّق"),
    "Provisional": ("badge-provisional", "مبدئي"),
    "Insufficient Data": ("badge-insufficient", "بيانات غير كافية"),
}

SAFETY_BADGE = {
    "critical": ("badge-critical", "حرج"),
    "warning": ("badge-warning", "تنبيه"),
    "none": ("badge-none", "لا يوجد"),
}


def badge_html(level_key: str, mapping: dict) -> str:
    css_class, label = mapping.get(level_key, ("badge-none", level_key))
    return f'<span class="badge {css_class}">{label}</span>'
