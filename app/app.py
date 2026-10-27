"""한누리에너지솔루션 유럽 공급망 전략 시뮬레이터 (2026–2045). 실행: ./py -m streamlit run app/app.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

import streamlit as st

st.set_page_config(page_title="유럽 공급망 전략 시뮬레이터", layout="wide", initial_sidebar_state="expanded")

import state as S  # noqa: E402
import screens as SC  # noqa: E402
import ui as U  # noqa: E402
from scm import network as N  # noqa: E402

U.inject_css()
S.init()

SCREENS = {"① 가정 입력 (M0)": SC.screen_inputs, "② 수요 분석 (M0·M5)": SC.screen_demand,
           "③ 배정·투자·탄소 (M1~M4)": SC.screen_network, "④ 의사결정 보드 (M5·M6)": SC.screen_board}

with st.sidebar:
    st.markdown('<div class="ptitle">화면</div>', unsafe_allow_html=True)
    page = st.radio("화면", list(SCREENS), key="page", label_visibility="collapsed")
    st.markdown('<div class="note" style="margin-top:12px">시나리오·입력값은 네 화면에 공통 적용되며 메뉴를 옮겨도 유지됩니다.</div>',
                unsafe_allow_html=True)

# 공식 시나리오 5종은 시작 시 한 번 계산(디스크 캐시)
S.npv_matrix(S.macro_key())

sc = S.scenario()
badges = "".join(f"<span>{b}</span>" for b in S.badges(S.light_scenario()))
solver = N.SOLVER["name"] or "Gurobi"
st.markdown(f'<div class="gbar"><span class="title">한누리에너지솔루션 유럽 공급망 전략 시뮬레이터 (2026–2045)</span>'
            f'<span class="badges">{badges}<span class="solver">Solver: {solver}</span>'
            f'<span>계산 {st.session_state["calc_time"]}</span></span></div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns([7, 1, 1])
with c1:
    st.session_state["_w_scenario"] = st.session_state["scenario"]
    st.segmented_control("시나리오", list(S.SCEN_LABELS), key="_w_scenario", format_func=lambda k: S.SCEN_LABELS[k].replace(". ", "\\. ", 1),
                         on_change=S.on_scenario_change, label_visibility="collapsed")
with c2:
    if st.button("프리셋 초기화", use_container_width=True):
        st.session_state["scenario"] = "base"
        st.session_state.update(S.preset_values(S.C.SCENARIOS["base"]))
        st.session_state.update(S.MACRO_DEFAULTS)
        st.session_state["applied_macro"] = None
        st.rerun()
with c3:
    keys = list(S.preset_values(S.C.SCENARIOS["base"])) + list(S.PROB_KEYS.values()) + list(S.MACRO)
    st.download_button("저장(JSON)", json.dumps({k: st.session_state[k] for k in keys}, ensure_ascii=False, indent=1),
                       file_name="시나리오_입력값.json", use_container_width=True)

if S.needs_recalc():
    st.markdown('<div class="warnbar">입력이 바뀌었으니 재계산이 필요합니다. 원가·탄소·표는 실시간 반영, '
                'LP·NPV·몬테카를로는 왼쪽 패널 하단 [재계산] 후 갱신됩니다.</div>', unsafe_allow_html=True)

S.HEADER["page"] = page
S.HEADER["slot"] = st.empty()
S.header("계산 중…")
SCREENS[page]()
