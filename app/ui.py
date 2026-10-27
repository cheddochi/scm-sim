"""공통 UI: 디자인.md 규격 CSS, 고밀도 HTML 표, 화면 간 값이 유지되는 입력 위젯."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

NAVY, BLUE, SLATE, GREY, LINE = "#0F172A", "#1E3A8A", "#475569", "#94A3B8", "#E2E8F0"
ORANGE, RED, AMBER, GREEN = "#EA580C", "#DC2626", "#D97706", "#16A34A"
FONT = "Pretendard, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"

CSS = f"""
<style>
html, body, [class*="css"], .stApp {{ font-family: {FONT}; font-size: 12.5px; color: {NAVY}; }}
.stApp {{ background: #F8FAFC; }}
header[data-testid="stHeader"] {{ display: none; }}
.block-container {{ padding: 0.5rem 1rem 1rem 1rem !important; max-width: 100% !important; }}
section[data-testid="stSidebar"] {{ width: 180px !important; min-width: 180px !important; background: #FFFFFF;
  border-right: 1px solid {LINE}; }}
section[data-testid="stSidebar"] > div {{ padding: 0.5rem 0.5rem; }}
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarHeader"] {{ display: none; }}
div[data-testid="stVerticalBlock"] {{ gap: 0.35rem; }}
div[data-testid="stHorizontalBlock"] {{ gap: 0.6rem; }}
p, label, .stMarkdown {{ font-size: 12.5px !important; }}
div[data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
div[data-testid="stWidgetLabel"] p {{ font-size: 12px !important; color: {SLATE}; margin-bottom: 0; }}
div[data-baseweb="select"] > div, input, textarea {{ border-radius: 2px !important; min-height: 28px; font-size: 12.5px; }}
.stSlider {{ padding-top: 0; padding-bottom: 0; }}
.stButton button, .stDownloadButton button {{ border-radius: 2px; padding: 2px 10px; min-height: 28px; font-size: 12px;
  border: 1px solid {LINE}; box-shadow: none; }}
.stButton button[kind="primary"] {{ background: {BLUE}; border-color: {BLUE}; }}
details {{ border-radius: 2px !important; border: 1px solid {LINE} !important; background: #FFFFFF; }}
details summary p {{ font-size: 12.5px !important; font-weight: 600; }}
div[data-testid="stExpanderDetails"] {{ padding: 0.3rem 0.6rem 0.5rem 0.6rem; }}
.stTabs [data-baseweb="tab"] {{ height: 28px; font-size: 12px; padding: 0 10px; }}
div[data-testid="stPlotlyChart"] {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 2px; padding: 2px; }}
/* 상단 글로벌 바 */
.gbar {{ display:flex; align-items:center; justify-content:space-between; height:40px; background:{NAVY};
  color:#FFFFFF; padding:0 12px; margin:-0.5rem -1rem 0.4rem -1rem; border-bottom:1px solid {NAVY}; }}
.gbar .title {{ font-weight:700; font-size:13.5px; letter-spacing:-0.2px; }}
.gbar .badges span {{ display:inline-block; border:1px solid #334155; padding:1px 6px; margin-left:4px; font-size:11px;
  color:#CBD5E1; border-radius:2px; font-variant-numeric: tabular-nums; }}
.gbar .badges span.solver {{ color:#FFFFFF; border-color:{ORANGE}; }}
/* 화면 제목줄 */
.shead {{ display:flex; justify-content:space-between; align-items:baseline; border-bottom:1px solid {LINE};
  padding:2px 0 4px 0; margin-bottom:4px; }}
.shead .h {{ font-size:14px; font-weight:700; }}
.shead .ctx {{ font-size:11px; color:{SLATE}; }}
.ptitle {{ font-size:12.5px; font-weight:700; margin:6px 0 2px 0; border-left:3px solid {BLUE}; padding-left:6px; }}
.note {{ font-size:11px; color:{SLATE}; }}
.warnbar {{ background:#FEF9C3; border:1px solid #FDE68A; color:#713F12; padding:4px 8px; font-size:12px; border-radius:2px; }}
.errtxt {{ color:{RED}; font-size:11.5px; }}
/* 고밀도 표 */
table.dt {{ border-collapse:collapse; width:100%; background:#FFFFFF; font-size:12px; font-variant-numeric: tabular-nums;
  border:1px solid {LINE}; }}
table.dt th {{ background:#F1F5F9; color:{SLATE}; font-weight:600; font-size:11.5px; text-align:right; padding:3px 6px;
  border-bottom:1px solid {LINE}; white-space:nowrap; }}
table.dt td {{ padding:0 6px; height:26px; text-align:right; border-bottom:1px solid #F1F5F9; white-space:nowrap; }}
table.dt th:first-child, table.dt td:first-child {{ text-align:left; }}
table.dt td.l, table.dt th.l {{ text-align:left; white-space:normal; }}
table.dt tr.hl td {{ font-weight:700; background:#EFF6FF; }}
table.dt tr.acc td {{ font-weight:700; color:{ORANGE}; }}
table.dt td.neg {{ color:{RED}; }}
table.dt td.chg {{ color:{ORANGE}; font-weight:700; }}
.b {{ display:inline-block; padding:0 5px; font-size:11px; border-radius:2px; line-height:16px; color:#FFFFFF; }}
.b.g {{ background:{GREEN}; }} .b.y {{ background:{AMBER}; }} .b.r {{ background:{RED}; }} .b.n {{ background:{GREY}; }}
.b.fact {{ background:{SLATE}; }} .b.asm {{ background:{AMBER}; }}
/* KPI 카드 */
.kpis {{ display:grid; grid-template-columns: repeat(5, 1fr); gap:6px; margin-bottom:4px; }}
.kpi {{ background:#FFFFFF; border:1px solid {LINE}; border-radius:2px; padding:5px 8px; min-height:64px; }}
.kpi .k {{ font-size:11px; color:{SLATE}; }}
.kpi .v {{ font-size:17px; font-weight:700; font-variant-numeric: tabular-nums; line-height:1.25; }}
.kpi .s {{ font-size:11px; color:{SLATE}; }}
.kpi.acc {{ border-top:3px solid {ORANGE}; }}
/* 입력값 구분: 기준값 회색, 변경값 노랑 */
div[class*="st-key-in_"] {{ padding:2px 6px; border-radius:2px; }}
div[class*="st-key-in_"][class*="_def"] {{ background:#F1F5F9; }}
div[class*="st-key-in_"][class*="_chg"] {{ background:#FEF9C3; }}
/* 시나리오 선택기 */
div[class*="st-key-_w_scenario"] button {{ border-radius:2px !important; font-size:12px; padding:0 8px; min-height:26px; }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- 화면 간 값 유지 입력
def _sync(key: str, scenario_param: bool):
    val = st.session_state["_w_" + key]
    if val is None:                      # 세그먼트 선택 해제는 무시하고 이전 값 유지
        st.session_state["_w_" + key] = st.session_state[key]
        return
    st.session_state[key] = val
    if scenario_param:
        prev = st.session_state["scenario"]
        if prev != "custom":             # [재계산] 전까지는 직전 프리셋의 LP 결과를 유지
            from scm import config as C
            st.session_state["applied_custom"] = C.SCENARIOS[prev]
        st.session_state["scenario"] = "custom"
        st.session_state["_w_scenario"] = "custom"


def _box(key: str, default):
    changed = default is not None and st.session_state.get(key) != default
    return st.container(key=f"in_{key}_{'chg' if changed else 'def'}")


def num(label, key, *, kind="slider", default=None, scenario_param=False, **kw):
    """session_state[key]에 값을 보관해 화면을 옮겨도 유지되는 입력 위젯."""
    st.session_state["_w_" + key] = st.session_state[key]
    with _box(key, default):
        fn = {"slider": st.slider, "number": st.number_input, "select": st.selectbox, "radio": st.radio,
              "toggle": st.toggle, "segmented": st.segmented_control}[kind]
        return fn(label, key="_w_" + key, on_change=_sync, args=(key, scenario_param), **kw)


# ---------------------------------------------------------------- 표와 제목
def screen_header(title: str, ctx: str):
    st.markdown(f'<div class="shead"><span class="h">{html.escape(title)}</span>'
                f'<span class="ctx">{html.escape(ctx)}</span></div>', unsafe_allow_html=True)


def panel_title(text: str):
    st.markdown(f'<div class="ptitle">{html.escape(text)}</div>', unsafe_allow_html=True)


def badge(text: str, cls: str) -> str:
    return f'<span class="b {cls}">{html.escape(text)}</span>'


def fmt_num(x, digits=0, sign=False, pct=False):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "–"
    if isinstance(x, str):
        return html.escape(x)
    v = x * 100 if pct else x
    s = f"{abs(v):,.{digits}f}"
    if v < 0 and round(abs(v), digits) != 0:
        s = "−" + s
    elif sign and v > 0 and round(v, digits) != 0:
        s = "+" + s
    return s + ("%" if pct else "")


def html_table(df: pd.DataFrame, fmt: dict | None = None, raw: set | None = None, left: set | None = None,
               row_class: dict | None = None, neg_red: set | None = None, chg: dict | None = None,
               index: bool = True, index_label: str = "") -> str:
    """fmt: 열 → (자릿수, 부호표시, 퍼센트). raw: HTML 그대로 출력할 열."""
    fmt, raw, left, neg_red = fmt or {}, raw or set(), left or set(), neg_red or set()
    row_class, chg = row_class or {}, chg or {}
    cols = list(df.columns)
    h = ['<table class="dt"><thead><tr>']
    if index:
        h.append(f'<th class="l">{html.escape(index_label)}</th>')
    for c in cols:
        h.append(f'<th class="{"l" if c in left else ""}">{html.escape(str(c))}</th>')
    h.append("</tr></thead><tbody>")
    for idx, row in df.iterrows():
        h.append(f'<tr class="{row_class.get(idx, "")}">')
        if index:
            h.append(f'<td class="l">{html.escape(str(idx))}</td>')
        for c in cols:
            v = row[c]
            cls = []
            if c in left:
                cls.append("l")
            if c in raw:
                txt = "" if v is None else str(v)
            elif c in fmt:
                d, sg, pc = (list(fmt[c]) + [False, False])[:3]
                txt = fmt_num(v, d, sg, pc)
                if c in neg_red and isinstance(v, (int, float)) and v < 0:
                    cls.append("neg")
            else:
                txt = html.escape("" if v is None else str(v))
            if chg.get((idx, c)):
                cls.append("chg")
            h.append(f'<td class="{" ".join(cls)}">{txt}</td>')
        h.append("</tr>")
    h.append("</tbody></table>")
    return "".join(h)


def show_table(df, **kw):
    st.markdown(html_table(df, **kw), unsafe_allow_html=True)


def csv_button(df: pd.DataFrame, name: str, label: str = "CSV 내보내기"):
    st.download_button(label, df.to_csv(encoding="utf-8-sig").encode("utf-8-sig"), file_name=name,
                       mime="text/csv", key=f"dl_{name}")
