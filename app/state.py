"""세션 상태: 시나리오 프리셋 ↔ 입력값, 현재 시나리오 구성, 계산 캐시 래퍼."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from scm import config as C, data as D, analysis as A, board as B, network as N

SCEN_LABELS = {k: v.name for k, v in C.SCENARIOS.items()} | {"custom": "6. 직접입력"}
SCEN_SHORT = {"base": "기준", "high_carbon": "고탄소", "carbon_cap": "탄소상한", "slow_demand": "수요둔화",
              "iaa": "역내생산", "custom": "직접입력"}

UI_DEFAULTS = {
    "cust": "유럽 12개 OEM 합계", "year_dist": 2035, "compare": ["base", "slow_demand"], "cand": "F_EU_HU_DEBRECEN",
    "year_sel": 2035, "lane_cust": "D_EU_DE_VW_WOLFSBURG", "mc_n": 1000, "mc_sd": 2.0, "dis_p": 5.0, "dis_dur": 1,
    "dis_loss": 50, "dis_target": "전체", "board_base": "base",
}
PROB_KEYS = {k: f"prob_{k}" for k in C.SCENARIOS}


def preset_values(sc: C.Scenario) -> dict:
    return {
        "growth_mult": sc.growth_mult, "demand_shock": int(round(sc.demand_shock * 100)), "shock_mode": sc.shock_mode,
        "share_cap": int(round(sc.share_cap * 100)), "eua_mult": sc.eua_mult,
        "cbam_2030": int(round(sc.cbam_share_2030 * 100)), "internal_carbon": sc.internal_carbon,
        "location_based": sc.location_based, "cap_on": sc.cap_2030 is not None,
        "cap_2030": sc.cap_2030 or 65.0, "cap_2035": sc.cap_2035 or 60.0, "iaa_penalty": sc.iaa_penalty,
        "selfgen_wro": int(round(dict(sc.self_gen).get(C.WROCLAW, 0.0) * 100)),
    }


BASE_VALUES = preset_values(C.SCENARIOS["base"])


def init():
    ss = st.session_state
    if "scenario" in ss:
        return
    ss["scenario"] = "base"
    ss.update(preset_values(C.SCENARIOS["base"]))
    ss.update(UI_DEFAULTS)
    for k, key in PROB_KEYS.items():
        ss[key] = int(C.DEFAULT_PROB[k] * 100)
    ss["applied_custom"] = None
    ss["calc_time"] = dt.datetime.now().strftime("%m-%d %H:%M")


def on_scenario_change():
    ss = st.session_state
    k = ss.get("_w_scenario") or ss["scenario"]
    ss["scenario"] = k
    if k != "custom":
        ss.update(preset_values(C.SCENARIOS[k]))
    else:
        ss["applied_custom"] = ss.get("applied_custom") or live_scenario()


def live_scenario() -> C.Scenario:
    """입력 패널 현재 값으로 만든 시나리오 (직접입력)."""
    ss = st.session_state
    sg = ss["selfgen_wro"] / 100
    return C.Scenario(
        "custom", "6. 직접입력", growth_mult=float(ss["growth_mult"]), demand_shock=ss["demand_shock"] / 100,
        shock_mode=ss["shock_mode"], share_cap=ss["share_cap"] / 100, eua_mult=float(ss["eua_mult"]),
        cbam_share_2030=ss["cbam_2030"] / 100, internal_carbon=bool(ss["internal_carbon"]),
        location_based=bool(ss["location_based"]), cap_2030=float(ss["cap_2030"]) if ss["cap_on"] else None,
        cap_2035=float(ss["cap_2035"]) if ss["cap_on"] else None, iaa_penalty=float(ss["iaa_penalty"]),
        self_gen=((C.WROCLAW, sg),) if sg > 0 else (),
    )


def scenario() -> C.Scenario:
    """무거운 계산에 쓰는 시나리오: 프리셋 또는 [재계산]으로 확정한 직접입력."""
    ss = st.session_state
    if ss["scenario"] == "custom":
        return ss.get("applied_custom") or live_scenario()
    return C.SCENARIOS[ss["scenario"]]


def light_scenario() -> C.Scenario:
    """가벼운 계산(원가·탄소·표)은 입력값을 실시간 반영."""
    return live_scenario() if st.session_state["scenario"] == "custom" else scenario()


def needs_recalc() -> bool:
    ss = st.session_state
    return ss["scenario"] == "custom" and ss.get("applied_custom") != live_scenario()


def probs() -> dict:
    return {k: st.session_state[key] / 100 for k, key in PROB_KEYS.items()}


def prob_ok() -> bool:
    return abs(sum(st.session_state[key] for key in PROB_KEYS.values()) - 100) < 1e-6


def badges(sc: C.Scenario) -> list[str]:
    cap = f"상한 {sc.cap_2030:.0f}/{sc.cap_2035:.0f}kg" if sc.cap_2030 else "상한 없음"
    return [f"성장률 ×{sc.growth_mult:.2f}" + (f" 충격 {sc.demand_shock * 100:.0f}%" if sc.demand_shock else ""),
            f"EUA ×{sc.eua_mult:.1f}", f"{'위치기반' if sc.location_based else '시장기반'}({cap})",
            f"CBAM {sc.cbam_share * 100:.0f}%→{sc.cbam_share_2030 * 100:.0f}%",
            f"역내페널티 ${sc.iaa_penalty:.0f}"]


def context(sc: C.Scenario) -> str:
    return f"시나리오: {SCEN_LABELS[st.session_state['scenario']]} | " + " | ".join(badges(sc)[:4])


def subtitle(unit: str, sc: C.Scenario | None = None, src: str = "시뮬레이터", extra: str = "") -> str:
    name = SCEN_LABELS[st.session_state["scenario"]] if sc is None else (sc.name if sc.key in SCEN_LABELS else sc.name)
    parts = [f"단위: {unit}", extra, f"시나리오: {name}", f"출처: {src}"]
    return "[" + " | ".join(p for p in parts if p) + "]"


# ---------------------------------------------------------------- 캐시 래퍼 (d는 해시 제외)
@st.cache_resource(show_spinner=False)
def data():
    return D.load()


@st.cache_data(show_spinner="네트워크 LP 20개 연도 × 9개 네트워크 계산 중…", max_entries=64)
def evaluate_all(sc: C.Scenario) -> dict:
    return A.evaluate_all(data(), sc)


@st.cache_data(show_spinner="5대 시나리오 결과 불러오는 중…")
def npv_matrix():
    return A.npv_matrix(data())


@st.cache_data(show_spinner=False, max_entries=32)
def network_run(sc: C.Scenario, factories: tuple, plan: tuple = ()) -> dict:
    return N.run_network(data(), sc, list(factories), dict(plan) or None)


@st.cache_data(show_spinner="스위치포인트 스윕(성장률 승수 0.3~1.2) 계산 중…", max_entries=8)
def switchpoint(sc: C.Scenario):
    return A.switchpoint_curve(data(), sc)


@st.cache_data(show_spinner="토네이도 민감도 계산 중…", max_entries=32)
def tornado(f: str, sc: C.Scenario):
    return A.tornado(data(), f, sc)


@st.cache_data(show_spinner="투자 시기 옵션 계산 중…", max_entries=32)
def timing(f: str, prob: tuple):
    return A.timing_options(data(), f, dict(prob))


@st.cache_data(show_spinner="수요 몬테카를로 경로 생성 중…", max_entries=16)
def demand_mc(sc: C.Scenario, n: int, sd: float):
    return A.demand_paths(data(), sc, n=n, sd_annual=sd)


@st.cache_data(show_spinner="공장 중단 스트레스 테스트 중…", max_entries=16)
def disruption(sc: C.Scenario, factories: tuple, target, p, dur, loss):
    return A.disruption_mc(data(), sc, list(factories), target=target, p=p, duration=dur, loss=loss)


@st.cache_data(show_spinner="권고안 계산 중…", max_entries=16)
def recommendation(prob: tuple, sc: C.Scenario):
    return B.recommendation(data(), dict(prob), sc)
