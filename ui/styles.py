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
.block-container {{ direction: rtl; padding-top: 2rem; max-width: 1600px; padding-bottom: 3rem; }}
.decision-heading {{ padding: 12px 0 20px; border-bottom: 1px solid {BORDER}; margin-bottom: 16px; }}
.decision-heading h1 {{ font-size: 1.85rem; margin: 3px 0 8px; font-weight: 600; }}
.decision-heading p {{ color: {TEXT_MUTED}; font-size: .95rem; margin: 0; }}
.decision-eyebrow {{ color: {TEAL}; font-size: .85rem; font-weight: 600; }}
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 8px; }}
[data-testid="stExpander"] {{ border-color: {BORDER}; }}
@media (max-width: 700px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  .decision-heading h1 {{ font-size: 1.5rem; }}
}}
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
  border-bottom: 3px solid {TEAL};
}}
.app-header .title {{ font-size: 1.35rem; font-weight: 700; color: white; }}
.app-header .subtitle {{ font-size: 0.9rem; color: #CBD5E1; margin-top: 2px; }}

hr {{ border-color: {BORDER}; }}

/* Hide Streamlit's default chrome (hamburger menu, "Deploy" button, the
   rainbow top decoration strip, footer) so the app reads as a finished,
   purpose-built product rather than a generic prototype. The header bar
   element itself is kept (not display:none) so the sidebar-collapse control
   on narrow/mobile screens keeps working — only its menu/toolbar contents
   are hidden. */
#MainMenu {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ visibility: hidden; height: 0; }}
[data-testid="stDecoration"] {{ visibility: hidden; height: 0; }}
footer {{ visibility: hidden; height: 0; }}

@media print {{
  section[data-testid="stSidebar"] {{ display:none !important; }}
  header[data-testid="stHeader"] {{ display:none !important; }}
  .stButton, .stDownloadButton {{ display:none !important; }}
}}

h1, h2, h3, h4 {{ text-align:right; }}
/* Decision workspace */
.stApp {{ background:#F5F7FA; }}
html, body, [data-testid="stApp"] p, [data-testid="stApp"] label, [data-testid="stApp"] input, [data-testid="stApp"] button {{ font-family: {FONT_STACK}; }}
.decision-heading {{ background:#fff; border:1px solid #E2E8F0; border-right:5px solid {TEAL}; border-radius:14px; padding:22px 26px; margin-bottom:4px; }}
.decision-heading h1 {{ font-size:2rem; font-weight:700; }}
.scope-strip {{ display:flex; align-items:center; gap:12px; color:#64748B; font-size:.86rem; padding:10px 4px 18px; flex-wrap:wrap; }}
.scope-strip b {{ color:{NAVY}; }}
[data-testid="stDataFrame"] {{ background:white; border-radius:12px; }}
[data-testid="stTextInput"] input {{ direction:rtl; }}
[data-baseweb="input"], [data-baseweb="select"] > div {{ background:#fff; border-radius:10px; }}
.project-card {{ background:#fff; border:1px solid #DFE7EC; border-radius:14px; padding:22px; box-shadow:0 3px 14px #142D4E06; }}
.project-card h3 {{ margin:8px 0; font-size:1.2rem; line-height:1.8; }}
.project-kicker {{ color:#64748B; font-size:.82rem; }}
.score-number {{ color:{TEAL}; font-size:2.8rem; font-weight:700; line-height:1.5; }}
.score-number small {{ font-size:1rem; color:#94A3B8; font-weight:400; }}
.project-facts {{ display:flex; justify-content:space-between; gap:10px; margin-top:16px; padding-top:14px; border-top:1px solid #E8EDF2; font-size:.8rem; color:#64748B; }}
.project-facts b {{ display:block; font-size:1.2rem; color:{NAVY}; }}
.decision-note {{ background:#EDF4F6; border-right:3px solid {TEAL}; padding:12px 16px; border-radius:8px; font-size:.85rem; margin:8px 0 20px; }}
.decision-note strong {{ display:block; margin-top:4px; color:{NAVY}; }}
.indicator-row {{ margin:0 0 14px; }}
.indicator-label {{ display:flex; justify-content:space-between; align-items:center; gap:12px; font-size:.8rem; margin-bottom:6px; }}
.indicator-label span {{ max-width:78%; }}
.indicator-label b {{ color:{TEAL}; white-space:nowrap; }}
.indicator-label small {{ font-size:.65rem; font-weight:400; }}
.bar-track {{ background:#E3EBEF; height:6px; border-radius:10px; overflow:hidden; }}
.bar-track div {{ background:{TEAL}; height:100%; border-radius:10px; }}
.indicator-meta {{ color:#7C8C9C; font-size:.68rem; margin-top:4px; }}
[data-testid="stExpander"] {{ background:#fff; border-radius:12px; }}
@media (max-width: 900px) {{ [data-testid="stHorizontalBlock"] {{ flex-wrap:wrap; }} [data-testid="stColumn"] {{ min-width:min(100%, 340px); }} }}
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

