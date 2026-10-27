"""Reusable design system: color palette, typography, Plotly chart template,
and small HTML component builders (KPI cards, badges). One source of truth so
every page looks consistent — no per-page ad-hoc styling.

Palette follows the brief: navy for headings/nav, teal as the primary
analytical accent, amber/red reserved exclusively for meaningful warnings
(never used decoratively).
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
NAVY = "#142D4E"
NAVY_SOFT = "#2A4A73"
TEAL = "#0F766E"
TEAL_SOFT = "#5EAAA3"
AMBER = "#D97706"
RED = "#B91C1C"
BG = "#FFFFFF"
BG_SOFT = "#F6F8FA"
BORDER = "#E2E8F0"
TEXT = "#1F2937"
TEXT_MUTED = "#5B6472"
GRAY_MISSING = "#CBD5E1"

# Status semantics used across both dashboards (classification + safety).
STATUS_COLORS = {
    "Validated": TEAL,
    "Provisional": AMBER,
    "Insufficient Data": GRAY_MISSING,
    "validated": TEAL,
    "provisional": AMBER,
    "insufficient": GRAY_MISSING,
    "critical": RED,
    "warning": AMBER,
    "none": "#94A3B8",
}

STATUS_LABELS_AR = {
    "Validated": "موثّق", "Provisional": "مبدئي", "Insufficient Data": "بيانات غير كافية",
    "validated": "موثّق", "provisional": "مبدئي", "insufficient": "غير كافٍ",
    "critical": "حرج", "warning": "تنبيه", "none": "لا يوجد",
}

# Color-blind-friendlier categorical sequence for charts with many categories.
CATEGORICAL_SEQUENCE = [TEAL, NAVY, AMBER, "#6D28D9", "#0369A1", RED, "#4D7C0F", "#9D174D"]

FONT_STACK = "'Cairo', 'Segoe UI', Tahoma, Arial, sans-serif"


def apply_chart_theme(fig: go.Figure, height: int | None = None, rtl: bool = True) -> go.Figure:
    """Apply the shared visual theme to any Plotly figure. Call right before st.plotly_chart."""
    fig.update_layout(
        font=dict(family=FONT_STACK, size=13, color=TEXT),
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        colorway=CATEGORICAL_SEQUENCE,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=NAVY, font_color="white", font_family=FONT_STACK),
    )
    # Only style layout.title if the figure already carries real title text.
    # IMPORTANT: title_font=... is just shorthand for title=dict(font=...) —
    # both make Plotly materialize a layout.title object. If that object is
    # created with a "font" key but no "text" key (i.e. no title was ever
    # set), the frontend reads title.text as JS `undefined` and renders the
    # literal word "undefined" above the chart. None of our charts currently
    # rely on Plotly's native title (headers are separate st.markdown
    # elements above the chart), so we must never create that object except
    # for the few charts that explicitly pass title="..." themselves.
    if fig.layout.title and fig.layout.title.text:
        fig.update_layout(title_font=dict(size=15, color=NAVY, family=FONT_STACK))
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    if rtl:
        fig.update_layout(xaxis=dict(autorange=True))
    return fig


def section_header(title: str, subtitle: str = "", icon: str = "") -> None:
    # Built as ONE single-line string deliberately: a multi-line f-string whose
    # subtitle line goes empty leaves a whitespace-only line in the markup,
    # which Streamlit's markdown parser treats as a blank line that ends the
    # HTML block early — the trailing "</div>" then renders as visible literal
    # text instead of being parsed as HTML. A single line has no blank-line
    # risk regardless of which parts are empty.
    icon_html = f"<span style='margin-left:8px'>{icon}</span>" if icon else ""
    subtitle_html = (f"<div style='font-size:0.88rem; color:{TEXT_MUTED}; margin-top:2px;'>{subtitle}</div>"
                      if subtitle else "")
    html = (f'<div style="border-right:4px solid {TEAL}; padding:2px 14px; margin:18px 0 10px 0;">'
            f'<div style="font-size:1.25rem; font-weight:700; color:{NAVY};">{icon_html}{title}</div>'
            f'{subtitle_html}</div>')
    st.markdown(html, unsafe_allow_html=True)


def kpi_card(label: str, value: str, caption: str = "", tone: str = "neutral") -> str:
    # Single-line construction — see section_header() for why (avoids a
    # blank-line HTML block termination when caption is empty).
    accent = {"neutral": TEAL, "warning": AMBER, "critical": RED, "navy": NAVY}.get(tone, TEAL)
    cap_html = f"<div style='font-size:0.78rem; color:{TEXT_MUTED}; margin-top:4px;'>{caption}</div>" if caption else ""
    return (f'<div style="background:{BG_SOFT}; border:1px solid {BORDER}; border-top:3px solid {accent}; '
            f'border-radius:10px; padding:16px 18px; height:100%;">'
            f'<div style="font-size:0.82rem; color:{TEXT_MUTED}; font-weight:600;">{label}</div>'
            f'<div style="font-size:1.9rem; font-weight:700; color:{NAVY}; margin-top:4px; direction:ltr; '
            f'text-align:right;">{value}</div>{cap_html}</div>')


def render_kpi_row(items: list[tuple[str, str, str, str]]) -> None:
    """items: list of (label, value, caption, tone)."""
    cols = st.columns(len(items))
    for col, (label, value, caption, tone) in zip(cols, items):
        with col:
            st.markdown(kpi_card(label, value, caption, tone), unsafe_allow_html=True)


def badge(level_key: str, custom_label: str | None = None) -> str:
    color = STATUS_COLORS.get(level_key, GRAY_MISSING)
    label = custom_label or STATUS_LABELS_AR.get(level_key, level_key)
    text_color = "white" if level_key in ("critical",) else NAVY if color == GRAY_MISSING else "white"
    return (f'<span style="background:{color}; color:{text_color}; padding:3px 11px; '
            f'border-radius:12px; font-size:0.8rem; font-weight:600; white-space:nowrap;">{label}</span>')


def missing_cell_html() -> str:
    return (f'<span style="color:{TEXT_MUTED}; font-size:0.85rem;" title="بيانات غير متوفرة">— '
            f'<span style="color:{GRAY_MISSING};">●</span></span>')
