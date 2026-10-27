"""화면 4종: ① 가정 입력 ② 수요 분석 ③ 배정·투자·탄소 ④ 의사결정 보드."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from scm import config as C, data as D, cost as K, analysis as A, board as B
import charts as CH
import state as S
import ui as U
from ui import num

KO = C.FACTORY_KO
SITES = C.EXISTING + C.CANDIDATES
FACTORY_COLORS = {"오창": U.SLATE, "브로츠와프": U.BLUE}


def ko(f):
    return B.ko(f)


# ---------------------------------------------------------------- 입력 패널 조각
def recalc_box():
    """직접입력일 때 무거운 계산(LP 재풀이) 실행 버튼."""
    if st.session_state["scenario"] != "custom":
        st.markdown('<div class="note">공식 시나리오는 앱 시작 시 계산해 둔 결과를 씁니다. '
                    '값을 바꾸면 [6. 직접입력]으로 전환됩니다.</div>', unsafe_allow_html=True)
        return
    if S.needs_recalc():
        st.markdown('<div class="errtxt">입력이 바뀌었습니다. LP 20개 연도 재풀이가 필요합니다.</div>',
                    unsafe_allow_html=True)
    if st.button("재계산", type="primary", use_container_width=True, key="recalc"):
        st.session_state["applied_custom"] = S.live_scenario()
        st.session_state["calc_time"] = pd.Timestamp.now().strftime("%m-%d %H:%M")
        st.rerun()


def demand_inputs():
    bv = S.BASE_VALUES
    num("전체 수요 성장률 승수 (수요 둔화 0.5)", "growth_mult", default=bv["growth_mult"], scenario_param=True,
        min_value=0.0, max_value=1.5, step=0.05, format="×%.2f")
    num("추가 일괄 수요 충격 (%)", "demand_shock", default=0, scenario_param=True, min_value=-40, max_value=0, step=5,
        format="%d%%")
    num("충격 형태", "shock_mode", kind="segmented", default="step", scenario_param=True, options=["step", "gradual"],
        format_func=lambda v: "급락(2027)" if v == "step" else "점진(2027→30)")
    num("고객별 이원화 수주 상한 (%)", "share_cap", default=70, scenario_param=True, min_value=50, max_value=100, step=5,
        format="%d%%")


def carbon_inputs():
    num("탄소발자국 산정 방식: 위치기반(PPA·GO 불인정)", "location_based", kind="toggle", default=False,
        scenario_param=True)
    num("EU 탄소가격(EUA) 배율 (고탄소 1.5)", "eua_mult", default=1.0, scenario_param=True, min_value=0.5,
        max_value=2.0, step=0.1, format="×%.1f")
    num("CBAM 한국산 과금 범위 (2030년~)", "cbam_2030", kind="segmented", default=25, scenario_param=True,
        options=[25, 100], format_func=lambda v: f"{v}%")
    num("고객 내부 탄소가격 (50kg 기준 초과·미달 정산, 2030~)", "internal_carbon", kind="toggle", default=False,
        scenario_param=True)
    num("유럽 공급 탄소발자국 상한", "cap_on", kind="toggle", default=False, scenario_param=True)
    if st.session_state["cap_on"]:
        c1, c2 = st.columns(2)
        with c1:
            num("2030~34 (kg)", "cap_2030", kind="number", default=65.0, scenario_param=True, min_value=40.0,
                max_value=80.0, step=1.0)
        with c2:
            num("2035~ (kg)", "cap_2035", kind="number", default=60.0, scenario_param=True, min_value=40.0,
                max_value=80.0, step=1.0)
        if st.session_state["cap_2035"] > st.session_state["cap_2030"]:
            st.markdown('<div class="errtxt">2035년 상한이 2030년보다 높습니다.</div>', unsafe_allow_html=True)
    num("역내생산 요건(IAA) 한국산 페널티 ($/kWh, 2030~)", "iaa_penalty", default=0.0, scenario_param=True,
        min_value=0.0, max_value=10.0, step=0.5, format="$%.1f")


def prob_inputs():
    cols = st.columns(5)
    for (k, key), col in zip(S.PROB_KEYS.items(), cols):
        with col:
            num(S.SCEN_SHORT[k], key, kind="number", default=int(C.DEFAULT_PROB[k] * 100), min_value=0, max_value=100,
                step=5)
    total = sum(st.session_state[k] for k in S.PROB_KEYS.values())
    if not S.prob_ok():
        st.markdown(f'<div class="errtxt">확률 합계 {total}% ≠ 100% — 기대 NPV 계산을 막습니다.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="note">합계 100% · 근거 없는 임시값이므로 ±10%p 민감도를 함께 봅니다.</div>',
                    unsafe_allow_html=True)


def mc_inputs(disruption=True):
    num("몬테카를로 경로 수", "mc_n", kind="select", default=1000, options=[200, 500, 1000, 2000])
    num("연간 수요 성장률 표준편차 (%p)", "mc_sd", default=2.0, min_value=0.5, max_value=5.0, step=0.5,
        format="%.1f%%p")
    if disruption:
        num("공장 가동 중단 확률 (공장·연)", "dis_p", default=5.0, min_value=0.0, max_value=20.0, step=1.0,
            format="%.0f%%")
        num("중단 기간 (년)", "dis_dur", kind="segmented", default=1, options=[1, 2, 3])
        num("중단 시 생산능력 손실 (%)", "dis_loss", default=50, min_value=10, max_value=100, step=10, format="%d%%")


# ---------------------------------------------------------------- ① 가정 입력
def screen_inputs():
    sc_live = S.light_scenario()
    left, right = st.columns([1, 3])
    with left:
        with st.expander("1. 수요 파라미터", expanded=True):
            demand_inputs()
        with st.expander("2. 비용·거시·세율 (<자료 10>)", expanded=False):
            consts = pd.DataFrame({
                "값": ["$50/kWh, 2030까지 −1.5%/년 → −0.5%", "2030까지 −1.5%/년 → −0.5%", "2035까지 −1%/년",
                      "9% (2026 시점, 20년, 잔존 0)", "1.10 $/€", "12% × (리드타임+7일)/365",
                      "공장별 9~30%", "순CAPEX 10년 정액"]},
                index=["소재비", "판매가격", "가공비 학습", "WACC", "환율", "재고유지비", "법인세", "감가상각"])
            U.show_table(consts, left={"값"})
            st.markdown('<div class="note">엔진 상수(케이스 고정값). 화면 조절은 다음 단계에서 지원.</div>',
                        unsafe_allow_html=True)
        with st.expander("3. 탄소 규제 및 통상 정책 (<자료 14>)", expanded=True):
            carbon_inputs()
        with st.expander("4. 시나리오 확률 가중치 (질문 5a)", expanded=False):
            prob_inputs()
        with st.expander("5. 몬테카를로 설정", expanded=False):
            mc_inputs()
        recalc_box()
    with right:
        U.panel_title("공식 시나리오 5종 정의 (<자료 14> A표)")
        rows = []
        for k, sc in C.SCENARIOS.items():
            rows.append({"시나리오": sc.name, "성장률": f"×{sc.growth_mult:.1f}", "EUA": f"×{sc.eua_mult:.1f}",
                         "CF 산정": "위치기반" if sc.location_based else "시장기반",
                         "탄소 상한": f"{sc.cap_2030:.0f}/{sc.cap_2035:.0f}kg" if sc.cap_2030 else "없음",
                         "CBAM(2030~)": f"{sc.cbam_share_2030 * 100:.0f}%",
                         "내부 탄소가격": "50kg 기준 정산" if sc.internal_carbon else "–",
                         "IAA 페널티": f"${sc.iaa_penalty:.0f}" if sc.iaa_penalty else "–",
                         "확률": f"{st.session_state[S.PROB_KEYS[k]]}%"})
        mt = pd.DataFrame(rows).set_index("시나리오")
        cur = st.session_state["scenario"]
        U.show_table(mt, row_class={C.SCENARIOS[cur].name: "hl"} if cur != "custom" else {})

        U.panel_title("현재 적용 가정 명세표 (슬라이드 주석용 · 변경값 주황)")
        spec = assumption_spec(sc_live)
        chg = {(i, "값"): r["_chg"] for i, r in spec.iterrows()}
        U.show_table(spec[["구분", "값", "출처"]], raw={"구분"}, left={"값", "출처"}, chg=chg, index_label="항목")
        U.csv_button(spec.drop(columns=["_chg"]).assign(구분=spec["_kind"]).drop(columns=["_kind"]), "가정명세표.csv")

        U.panel_title("엑셀 원자료 (battery_supply_chain(SIMPLE).xlsx)")
        d = S.data()
        t1, t2, t3, t4 = st.tabs(["Demand_Nodes 21곳", "Factories 10곳", "Transport_Params", "Annual_Assumptions"])
        with t1:
            dm = d["demand"][["oem_site", "region", "annual_ev_battery_demand_GWh_2026", "growth_rate_2026_2030",
                              "growth_rate_2031_2045", "purchase_price_usd_per_kwh_2026"]]
            dm.columns = ["OEM 거점", "지역", "2026 수요", "성장률 26-30", "성장률 31-45", "구매가격"]
            U.show_table(dm.set_index("OEM 거점"), fmt={"2026 수요": (1,), "성장률 26-30": (1, False, True),
                                                       "성장률 31-45": (1, False, True), "구매가격": (0,)})
        with t2:
            fc = d["factories"][["status", "target_capacity_gwh_yr", "capex_usd_million",
                                 "conversion_cost_usd_per_kwh_ex_material", "electricity_price_usd_per_kwh",
                                 "grid_intensity_kgco2_per_kwh", "renewable_share", "fixed_opex_usd_million_per_year",
                                 "yield_rate"]].copy()
            fc.index = [KO[i] for i in fc.index]
            fc.columns = ["구분", "용량", "CAPEX", "가공비", "전력단가", "전력집약도", "재생비중", "고정운영비", "수율"]
            U.show_table(fc, fmt={"용량": (0,), "CAPEX": (0,), "가공비": (1,), "전력단가": (2,), "전력집약도": (2,),
                                  "재생비중": (0, False, True), "고정운영비": (0,), "수율": (0, False, True)})
        with t3:
            U.show_table(d["transport"][["cost_per_tonne_km_usd", "co2e_kg_per_tonne_km", "speed_km_per_day",
                                          "handling_days", "handling_cost_usd_per_kwh_finished"]],
                         fmt={"cost_per_tonne_km_usd": (2,), "co2e_kg_per_tonne_km": (3,), "speed_km_per_day": (0,),
                              "handling_days": (0,), "handling_cost_usd_per_kwh_finished": (2,)})
        with t4:
            an = d["annual"].T.round(1)
            an.index = ["총수요(GWh)", "EUA(€/t)"]
            an.columns = [str(c) for c in an.columns]
            U.show_table(an, fmt={c: (0,) for c in an.columns})


def assumption_spec(sc: C.Scenario) -> pd.DataFrame:
    base = C.SCENARIOS["base"]
    fact, asm = U.badge("사실", "fact"), U.badge("가정", "asm")
    rows = [
        ("수요 성장률 승수", fact if sc.growth_mult == 1 else asm, f"×{sc.growth_mult:.2f}", "<자료 5> 구간 성장률",
         sc.growth_mult != base.growth_mult),
        ("추가 수요 충격", asm, f"{sc.demand_shock * 100:.0f}% ({'급락' if sc.shock_mode == 'step' else '점진'})",
         "사용자 입력", sc.demand_shock != 0),
        ("고객별 수주 상한", fact, f"{sc.share_cap * 100:.0f}%", "<자료 5> 주", sc.share_cap != base.share_cap),
        ("탄소발자국 산정", asm, "위치기반" if sc.location_based else "시장기반 (엑셀 고정값)", "<자료 6> 주",
         sc.location_based != base.location_based),
        ("EUA 경로", fact if sc.eua_mult == 1 else asm, f"2026년 {75 * sc.eua_mult:.1f}€, 연 3% × {sc.eua_mult:.1f}",
         "<자료 9>", sc.eua_mult != 1),
        ("CBAM 과금 범위", asm, f"2026~29 {sc.cbam_share * 100:.0f}% → 2030~ {sc.cbam_share_2030 * 100:.0f}%",
         "<자료 7>·<자료 14>", sc.cbam_share_2030 != base.cbam_share_2030),
        ("고객 내부 탄소가격", asm, "50kg 기준 초과·미달 정산" if sc.internal_carbon else "없음", "<자료 14>",
         sc.internal_carbon),
        ("유럽 탄소발자국 상한", asm, f"{sc.cap_2030:.0f} / {sc.cap_2035:.0f} kg" if sc.cap_2030 else "없음", "<자료 14>",
         sc.cap_2030 is not None),
        ("IAA 한국산 페널티", asm, f"${sc.iaa_penalty:.1f}/kWh (2030~)", "<자료 14>", sc.iaa_penalty != 0),
        ("브로츠와프 직접 자가발전", asm, f"{dict(sc.self_gen).get(C.WROCLAW, 0) * 100:.0f}%", "사용자 입력",
         bool(sc.self_gen)),
        ("소재비·판매가·가공비 추세", fact, "<자료 10> 기본값", "<자료 10>", False),
        ("투자 일정·보조금·세율", fact, "그린필드 2027·28 집행, 2029 가동", "<자료 10>", False),
        ("브로츠와프 생산능력", asm, "86 → 88(2027) → 90GWh", "<자료 14> 기존 NPV 역산", False),
        ("손실연도 법인세", asm, "0 (이월결손 없음)", "<자료 13> 역산", False),
        ("시나리오 확률", asm, " / ".join(f"{S.SCEN_SHORT[k]} {st.session_state[v]}%" for k, v in S.PROB_KEYS.items()),
         "사용자 입력 (근거 없음)", not all(st.session_state[v] == int(C.DEFAULT_PROB[k] * 100)
                                    for k, v in S.PROB_KEYS.items())),
    ]
    df = pd.DataFrame(rows, columns=["항목", "구분", "값", "출처", "_chg"]).set_index("항목")
    df["_kind"] = df["구분"].str.contains("사실").map({True: "사실", False: "가정"})
    return df


# ---------------------------------------------------------------- ② 수요 분석
def screen_demand():
    sc_heavy = S.scenario()
    sc = S.light_scenario()
    d = S.data()
    left, right = st.columns([1, 3])
    with left:
        U.panel_title("수요 파라미터")
        demand_inputs()
        U.panel_title("몬테카를로")
        mc_inputs(disruption=False)
        num("분포 비교 연도", "year_dist", kind="segmented", options=[2030, 2035, 2045])
        recalc_box()
    with right:
        dm = d["demand"]
        groups = {"전체 21개 OEM 합계": list(dm.index), "유럽 12개 OEM 합계": D.eu_customers(d)}
        groups |= {f"{r.oem_site}": [i] for i, r in dm.iterrows()}
        c1, c2 = st.columns([1, 2])
        with c1:
            num("분석 대상 고객", "cust", kind="select", options=list(groups))
        with c2:
            num("공식 시나리오 겹쳐보기", "compare", kind="segmented", options=list(C.SCENARIOS),
                selection_mode="multi", format_func=lambda k: S.SCEN_SHORT[k])
        ids = groups[st.session_state["cust"]]
        idx = [list(dm.index).index(i) for i in ids]
        is_eu = st.session_state["cust"] == "유럽 12개 OEM 합계"
        share = sc.share_cap
        mc = S.demand_mc(sc, int(st.session_state["mc_n"]), st.session_state["mc_sd"] / 100)
        paths = mc["customer"][:, idx, :].sum(axis=1) * share
        years = C.YEARS
        p10, p50, p90 = np.percentile(paths, [10, 50, 90], axis=0)
        lines = {}
        cur_key = st.session_state["scenario"]
        for k in st.session_state["compare"] or []:
            lines[C.SCENARIOS[k].name] = (D.demand(d, C.SCENARIOS[k]).loc[ids].sum().values * share, k == cur_key)
        if cur_key == "custom" or cur_key not in (st.session_state["compare"] or []):
            lines[f"선택: {sc.name}"] = (D.demand(d, sc).loc[ids].sum().values * share, True)
        yd = int(st.session_state["year_dist"])
        iy = years.index(yd)
        cap_new = 40.0
        cand = st.session_state["cand"]
        if cand in d["factories"].index:
            cap_new = float(d["factories"].loc[cand, "target_capacity_gwh_yr"])
        eu_paths = mc["eu"]
        p_short = A.shortfall_prob(eu_paths, yd, 90, share)
        p_short2 = A.shortfall_prob(eu_paths, yd, 90 + cap_new, share)
        gap_y = (D.demand(d, sc).loc[D.eu_customers(d), yd].sum() * share) - 90
        cl, cr = st.columns([7, 3])
        with cl:
            if is_eu:
                title = (f"유럽 공략 가능 물량은 {yd}년 브로츠와프 90GWh를 {gap_y:,.1f}GWh 넘으며, "
                         f"MC 경로의 {p_short:.0%}가 공급 부족")
            else:
                title = f"{st.session_state['cust']} 공략 가능 물량: {yd}년 중앙값 {p50[iy]:,.1f}GWh (10~90% {p10[iy]:,.0f}~{p90[iy]:,.0f})"
            fig = CH.spaghetti(years, paths[:50], p10, p50, p90, lines, 90 if is_eu else 0, title,
                               S.subtitle(f"GWh/년, 수요×수주상한 {share:.0%}", sc,
                                          extra=f"MC {len(paths):,}경로 · σ승수 {mc['sigma_mult']:.2f} · σ연 {st.session_state['mc_sd']:.1f}%p"))
            st.plotly_chart(fig, use_container_width=True, config=CH.config("수요_스파게티"))
        with cr:
            title2 = (f"{yd}년 90GWh 초과 {p_short:.0%}, {90 + cap_new:.0f}GWh 초과 {p_short2:.0%}")
            fig2 = CH.distribution(eu_paths[:, iy] * share,
                                   {f"브로츠와프 단독 90": (90, U.NAVY),
                                    f"+{ko(cand)} {90 + cap_new:.0f}": (90 + cap_new, U.ORANGE)},
                                   title2, S.subtitle("GWh", sc, extra="유럽 12개 OEM"))
            st.plotly_chart(fig2, use_container_width=True, config=CH.config("수요_분포"))
        bl, br = st.columns([3, 2])
        with bl:
            U.panel_title("OEM 고객별 수요와 수주 상한 물량 (GWh)")
            dem_sc = D.demand(d, sc)
            t = pd.DataFrame({
                "지역": dm["region"], "2026": dm["annual_ev_battery_demand_GWh_2026"],
                "성장률 26-30": dm["growth_rate_2026_2030"] * sc.growth_mult,
                "성장률 31-45": dm["growth_rate_2031_2045"] * sc.growth_mult,
                "감속비": dm["growth_rate_2031_2045"] / dm["growth_rate_2026_2030"],
                "2035": dem_sc[2035], "2045": dem_sc[2045], "2035 상한물량": dem_sc[2035] * share,
                "2045 상한물량": dem_sc[2045] * share})
            t.index = dm["oem_site"]
            U.show_table(t, fmt={"2026": (1,), "성장률 26-30": (1, False, True), "성장률 31-45": (1, False, True),
                                 "감속비": (2,), "2035": (1,), "2045": (1,), "2035 상한물량": (1,), "2045 상한물량": (1,)},
                         index_label="OEM 거점")
        with br:
            U.panel_title("유럽·글로벌 생산능력 격차 (<자료 2> B표 동적 재현)")
            from scm import network as N
            g = N.capacity_gap(d, sc).loc[[2026, 2028, 2030, 2035, 2040, 2045]]
            gt = pd.DataFrame({
                "유럽 OEM 수요": g["eu_demand"], f"공략 가능(×{share:.0%})": g["eu_addressable"],
                "브로츠와프": g["wroclaw_cap"], "유럽 격차": g["eu_gap"],
                f"세계 공략 가능": g["global_addressable"], "기존 2개 공장": g["existing_cap"],
                "세계 격차": g["global_addressable"] - g["existing_cap"]}).T
            gt.columns = [str(c) for c in gt.columns]
            U.show_table(gt, fmt={c: (1,) for c in gt.columns}, row_class={"유럽 격차": "acc"})
            s_ = A.demand_paths(d, C.SCENARIOS["base"], n=int(st.session_state["mc_n"]),
                                sd_annual=st.session_state["mc_sd"] / 100)
            slow = D.demand(d, C.SCENARIOS["slow_demand"]).sum()
            pct = {y: (s_["total"][:, C.YEARS.index(y)] < slow[y]).mean() for y in (2030, 2035, 2045)}
            st.markdown(f'<div class="note">보정: 경로별 성장률 승수 m~N(1, {mc["sigma_mult"]:.2f}) — 공식 수요 둔화(×0.5)가 '
                        f'기준 MC 분포의 하위 {pct[2030]:.0%}(2030) · {pct[2035]:.0%}(2035) · {pct[2045]:.0%}(2045)에 위치.</div>',
                        unsafe_allow_html=True)


# ---------------------------------------------------------------- ③ 배정·투자·탄소
def screen_network():
    sc = S.scenario()
    sc_live = S.light_scenario()
    d = S.data()
    left, right = st.columns([1, 3])
    with left:
        U.panel_title("후보지·연도")
        num("신규 후보지 (기존 2곳 + 1곳)", "cand", kind="select", options=C.CANDIDATES, format_func=ko)
        num("기준 연도", "year_sel", kind="select", options=C.YEARS)
        num("도착원가 비교 고객", "lane_cust", kind="select", options=D.eu_customers(d) + [
            i for i in d["demand"].index if i not in D.eu_customers(d)],
            format_func=lambda i: d["demand"].loc[i, "oem_site"])
        U.panel_title("공급·탄소 레버")
        num("브로츠와프 직접 저탄소 자가발전 비율 (%)", "selfgen_wro", default=0, scenario_param=True, min_value=0,
            max_value=80, step=1, format="%d%%")
        num("고객별 이원화 수주 상한 (%)", "share_cap", default=70, scenario_param=True, min_value=50, max_value=100,
            step=5, format="%d%%")
        ct = A.carbon_table(d)
        st.markdown(f'<div class="note">브로츠와프 위치기반 {ct.loc[C.WROCLAW, "location_total"]:.2f}kg(운송 포함) — '
                    f'상한 통과 필요 자가발전 2030년 {ct.loc[C.WROCLAW, "selfgen_2030"]:.1%}, '
                    f'2035년 {ct.loc[C.WROCLAW, "selfgen_2035"]:.1%}</div>', unsafe_allow_html=True)
        U.panel_title("탄소 규제")
        carbon_inputs()
        recalc_box()
    cand = st.session_state["cand"]
    ys = int(st.session_state["year_sel"])
    with right:
        ev = S.evaluate_all(sc)
        run = ev["runs"][cand]
        pl = run["pl"]
        util = pl.pivot(index="factory", columns="year", values="volume") / \
            pl.pivot(index="factory", columns="year", values="capacity").replace(0, np.nan)
        util = util.fillna(0.0).reindex(C.EXISTING + [cand])
        shadow = run["shadow"].reindex(C.EXISTING + [cand]).fillna(0.0)
        util.index = shadow.index = [ko(f) for f in util.index]
        cl, cr = st.columns(2)
        with cl:
            sp = shadow[2035].to_dict() if 2035 in shadow else {}
            cc = A.capital_cost_per_kwh(d, cand)
            nm = ko(cand)
            title = (f"{nm} 2035년 생산능력 잠재가격 ${sp.get(nm, 0):.1f}/kWh는 "
                     f"연간 자본비용 ${cc:.1f}/kWh {'초과' if sp.get(nm, 0) > cc else '미달'}")
            st.plotly_chart(CH.util_heatmap(util, shadow, title, S.subtitle("% · $/kWh", sc, src="시뮬레이터 M2 LP")),
                            use_container_width=True, config=CH.config("가동률_잠재가격"))
        with cr:
            tab1, tab2 = st.tabs([f"고객별 공급 비중 ({ys})", "레인별 도착원가 분해 (M1)"])
            with tab1:
                rr = S.network_run(sc, tuple(C.EXISTING + [cand]))
                lt = rr["lanes"][ys]
                flows = lt["flow"].unstack(0).fillna(0.0)
                tot = flows.sum(axis=1)
                share = flows.div(tot.replace(0, np.nan), axis=0).fillna(0.0)
                share = share.loc[tot.sort_values(ascending=False).index]
                share = share[[c for c in C.EXISTING + [cand] if c in share]]
                share.columns = [ko(c) for c in share.columns]
                share.index = [d["demand"].loc[i, "oem_site"] for i in share.index]
                eu_share_new = (lt.xs(cand, level=0)["flow"] * lt.xs(cand, level=0)["is_eu"]).sum() / max(
                    (lt["flow"] * lt["is_eu"]).sum(), 1e-9)
                colors = dict(FACTORY_COLORS, **{nm: U.ORANGE})
                st.plotly_chart(CH.stacked_share(share, colors, f"{ys}년 {nm}이 유럽 공급의 {eu_share_new:.0%}를 담당",
                                                 S.subtitle("공급 비중 %", sc)),
                                use_container_width=True, config=CH.config("고객별_공급비중"))
            with tab2:
                cust = st.session_state["lane_cust"]
                rows = {}
                for y in sorted({2026, ys}):
                    ltab = K.lane_table(d, sc_live, y, C.EXISTING + [cand]).xs(cust, level=1)
                    for f in C.EXISTING + [cand]:
                        r = ltab.loc[f]
                        # 정상 가동 기준 kWh당 고정비 (<자료 11> 참고행: 오창 12.00, 브로츠와프 7.56)
                        fixed = d["factories"].loc[f, "fixed_opex_usd_million_per_year"] * (1 + C.FIXED_OPEX_GROWTH) ** (y - C.BASE_YEAR)
                        cap_f = D.capacity(d, f, y) if f in C.EXISTING else d["factories"].loc[f, "target_capacity_gwh_yr"]
                        fo = fixed / cap_f
                        rows[(y, f)] = {**{K.COST_KO[c]: r[c] for c in K.COST_ITEMS},
                                        "역내생산 페널티": r["iaa"], "내부 탄소가격 조정": r["internal_carbon"],
                                        "도착원가(고정비 제외)": r["landed"] + r["iaa"] + r["internal_carbon"],
                                        "고정운영비/생산능력": fo,
                                        "총원가(고정비 포함)": r["landed"] + r["iaa"] + r["internal_carbon"] + fo,
                                        "판매가격": r["price"], "탄소발자국(시장+운송)": r["cf_market"],
                                        "리드타임(일)": r["lead_time"]}
                cb = pd.DataFrame({k: rows[(ys, k)] for k in C.EXISTING + [cand]}).T
                cb.index = [ko(i) for i in cb.index]
                items = {c: c for c in list(K.COST_KO.values())}
                cheapest = cb["총원가(고정비 포함)"].idxmin()
                var_cheap = cb["도착원가(고정비 제외)"].idxmin()
                cname = d["demand"].loc[cust, "oem_site"]
                title = (f"{ys}년 {cname} 공급: 변동원가 최저 {var_cheap}, 고정비 포함 최저 {cheapest}"
                         + (" (역전)" if cheapest != var_cheap else ""))
                st.plotly_chart(CH.cost_breakdown(cb[list(items)], items, cheapest, title,
                                                  S.subtitle("$/kWh", sc_live, src="시뮬레이터 M1")),
                                use_container_width=True, config=CH.config("도착원가"))
                tbl = pd.DataFrame({f"{ko(f)} {y}": rows[(y, f)] for y in sorted({2026, ys}) for f in C.EXISTING + [cand]})
                U.show_table(tbl, fmt={c: (2,) for c in tbl.columns},
                             row_class={"도착원가(고정비 제외)": "hl", "총원가(고정비 포함)": "acc"})
        U.panel_title(f"후보지 8곳 + 기존 2곳 종합 비교 (M2·M3·M4) · {sc.name}")
        mt = master_table(d, sc, ev)
        U.show_table(mt, raw={"잠식 효과", "2030 65kg", "2035 60kg"},
                     fmt={"용량": (0,), "순CAPEX": (0,), "공장 NPV": (0, True), "증분 NPV": (0, True),
                          "IRR": (1, False, True), "시장 CF": (2,), "위치 CF": (2,), "필요 자가발전": (1, False, True),
                          "2035 잠재가격": (1,), "자본비용": (1,)},
                     neg_red={"공장 NPV", "증분 NPV"}, row_class={ko(cand): "hl"}, index_label="거점")
        U.csv_button(mt.drop(columns=["잠식 효과", "2030 65kg", "2035 60kg"]), f"종합비교_{sc.key}.csv")
        st.markdown('<div class="note">잠식 효과 = 증분 NPV − 공장 NPV (빨강 < −1,000, 노랑 < −300). CF는 유럽 12개 고객 평균 운송 배출 포함. '
                    '자본비용 = 순CAPEX × CRF(9%, 17년) ÷ 용량. 잠재가격은 해당 공장 생산능력 1kWh 추가 시 공헌이익 증가.</div>',
                    unsafe_allow_html=True)
        if S.prob_ok():
            tm = S.timing(cand, tuple(S.probs().items()))
            s = tm["summary"]
            best = s["expected_npv"].idxmax()
            title = (f"{ko(cand)}: '{best}'가 기대 NPV {s.loc[best, 'expected_npv']:,.0f}로 최고, "
                     f"최악 손실은 {s.loc[best, 'worst_npv']:,.0f}".replace("-", "−"))
            st.plotly_chart(CH.timing_bars(s, best, title, S.subtitle("$M, 2026 현가(WACC 9%)", None,
                                                                    extra="5대 시나리오 확률 가중", src="시뮬레이터 M5")),
                            use_container_width=True, config=CH.config("투자시기"))
            bt = tm["by_scenario"][["now", "half_only", "phased_full", "phased", "delay_full", "delay"]]
            bt.columns = ["즉시 전량", "1단계만", "1+2단계", "분할(선택)", "연기 실행", "연기(선택)"]
            bt.index = [S.SCEN_SHORT[k] for k in bt.index]
            U.show_table(bt, fmt={c: (0, True) for c in bt.columns}, neg_red=set(bt.columns), index_label="시나리오")
            st.markdown('<div class="note">2단계 분할 = 절반(1단계) 2027 착공 + 2028년 시나리오 판명 후 나머지 절반 2029 착공 여부 선택. '
                        '연기 = 2028년 판명 후 2029 착공 또는 포기(0). 시나리오는 2028년에 판명된다고 가정.</div>',
                        unsafe_allow_html=True)


def master_table(d, sc, ev) -> pd.DataFrame:
    ct = A.carbon_table(d)
    fac = d["factories"]
    tb = ev["table"]
    rows = []

    def light(ok):
        return U.badge("통과", "g") if ok else U.badge("초과", "r")

    for f in SITES:
        is_new = f in C.CANDIDATES
        run = ev["runs"][f] if is_new else ev["base_run"]
        sh = run["shadow"]
        sp35 = float(sh.loc[f, 2035]) if f in sh.index else np.nan
        cann = tb.loc[f, "cannibalization"] if is_new else np.nan
        cb = "–" if not is_new else U.badge(U.fmt_num(cann, 0, True),
                                            "r" if cann < -1000 else ("y" if cann < -300 else "g"))
        rows.append({
            "거점": ko(f), "구분": "기존" if not is_new else ("증설" if f == C.WROCLAW_EXP else "그린필드"),
            "용량": fac.loc[f, "target_capacity_gwh_yr"],
            "순CAPEX": fac.loc[f, "capex_usd_million"] * (1 - C.SUBSIDY.get(f, 0)) if is_new else np.nan,
            "공장 NPV": tb.loc[f, "plant_npv"] if is_new else np.nan,
            "증분 NPV": tb.loc[f, "network_npv"] if is_new else np.nan,
            "잠식 효과": cb, "IRR": tb.loc[f, "plant_irr"] if is_new else np.nan,
            "회수": str(tb.loc[f, "payback"]) if is_new and tb.loc[f, "payback"] else "–",
            "시장 CF": ct.loc[f, "market_total"], "위치 CF": ct.loc[f, "location_total"],
            "2030 65kg": light(ct.loc[f, "pass_2030"]), "2035 60kg": light(ct.loc[f, "pass_2035"]),
            "필요 자가발전": ct.loc[f, "selfgen_2035"], "2035 잠재가격": sp35,
            "자본비용": A.capital_cost_per_kwh(d, f) if is_new else np.nan,
        })
    return pd.DataFrame(rows).set_index("거점")


# ---------------------------------------------------------------- ④ 의사결정 보드
def screen_board():
    sc = S.scenario()
    d = S.data()
    left, right = st.columns([1, 3])
    with left:
        U.panel_title("시나리오 확률 가중치")
        prob_inputs()
        U.panel_title("공장 중단 스트레스 테스트")
        num("중단 대상", "dis_target", kind="select", options=["전체"] + C.EXISTING + C.CANDIDATES, format_func=lambda f: "전체 공장" if f == "전체" else ko(f))
        mc_inputs()
        U.panel_title("모니터링")
        st.markdown('<div class="note">Trigger 임계값은 스위치포인트·토네이도에서 자동 산출. '
                    '라인 전환(ESS)·착공 보류 비용은 엑셀 근거가 없어 반영하지 않음.</div>', unsafe_allow_html=True)
        recalc_box()
    with right:
        if not S.prob_ok():
            st.markdown('<div class="warnbar">확률 합계가 100%가 아니어서 보드 계산을 멈췄습니다. 왼쪽 패널을 고쳐 주세요.</div>',
                        unsafe_allow_html=True)
            return
        prob = S.probs()
        rec = S.recommendation(tuple(prob.items()), sc)
        best, er, m = rec["best"], rec["er"], rec["matrix"]
        ck = B.carbon_kpi(d)
        nm = ko(best)
        cap = d["factories"].loc[best, "target_capacity_gwh_yr"] if best in d["factories"].index else 0
        sg = rec.get("switch_growth")
        regret_rank = int(er.loc[best, "rank_regret"])
        ct = ck["table"]
        best_cf = (U.badge("2035 통과", "g") if best in ct.index and ct.loc[best, "pass_2035"] else U.badge("2035 초과", "r"))
        kpis = [
            ("권고 거점·투자안", f"{nm} {cap:.0f}GWh", f"{rec['form']} · 차선 {ko(rec['minimax'])}(최소 후회)", True),
            ("5대 시나리오 기대 증분 NPV", f"{B.fmt_m(rec['form_npv'])} $M",
             f"즉시 전량 {B.fmt_m(er.loc[best, 'expected_npv'])} · 최악 {B.fmt_m(rec['form_worst'])}", False),
            ("최대 후회 (Maximum Regret)", f"{er.loc[best, 'max_regret']:,.0f} $M",
             f"후회 최소 순위 {regret_rank}위 · 최악 {S.SCEN_SHORT.get(er.loc[best, 'worst_regret_scenario'], '')}", False),
            ("유럽 탄소 상한(위치기반) 적합성", f"{ck['pass_2035']}/{ck['n']} 곳",
             f"2035 60kg 통과 후보지 · 권고안 {best_cf}", False),
            ("이사회 전환 임계값", f"성장률 ×{sg:.2f}" if sg else "전 구간 양(+)",
             "이하로 하회 시 2단계 보류 / 위치기반 60kg 확정 여부", False),
        ]
        st.markdown('<div class="kpis">' + "".join(
            f'<div class="kpi{" acc" if a else ""}"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s_}</div></div>'
            for k, v, s_, a in kpis) + "</div>", unsafe_allow_html=True)

        cl, cr = st.columns(2)
        with cl:
            mm = m.copy()
            mm["기대 NPV"] = er["expected_npv"]
            mm.index = [ko(i) for i in mm.index]
            mm.columns = [S.SCEN_SHORT.get(c, c) for c in mm.columns]
            cur = S.SCEN_SHORT.get(st.session_state["scenario"])
            top2 = er["expected_npv"].sort_values(ascending=False)
            title = (f"{nm}만 5대 시나리오 중 {int((m.loc[best] > 0).sum())}개에서 양(+), "
                     f"확률 가중 {B.fmt_m(top2.iloc[0])}로 1위")
            st.plotly_chart(CH.scenario_heatmap(mm, nm, cur, title,
                                                S.subtitle("$M, 2026 현가(WACC 9%)", C.SCENARIOS['base'],
                                                           src="시뮬레이터 M4·M5", extra="네트워크 증분 NPV").replace(
                                                    "시나리오: 1. 기준", "시나리오: 5종 비교")),
                            use_container_width=True, config=CH.config("시나리오별_증분NPV"))
            tor = rec["tornado"]
            top = tor.iloc[0]
            title = f"{nm} 증분 NPV를 가장 크게 흔드는 변수는 {top['variable']} (변동폭 {top['swing']:,.0f})"
            st.plotly_chart(CH.tornado(tor, title, S.subtitle("$M", sc, src="시뮬레이터 M5")),
                            use_container_width=True, config=CH.config("토네이도"))
        with cr:
            sw = rec["switch_curve"]
            labels = {f: ko(f) for f in sw.columns}
            title = (f"수요 성장률이 기준의 {sg:.0%} 아래로 떨어지면 {nm} 증분 NPV가 음(−)으로 전환"
                     if sg else f"{nm} 증분 NPV는 성장률 승수 0.3~1.2 전 구간에서 부호 유지")
            st.plotly_chart(CH.switchpoint(sw, labels, best, sg, title, S.subtitle("$M", sc, src="시뮬레이터 M5")),
                            use_container_width=True, config=CH.config("스위치포인트"))
        U.panel_title("이사회 분기 점검 지표와 행동 전환 조건 (Trigger, 질문 6-v)")
        tg = B.triggers(d, rec).set_index("지표")
        U.show_table(tg, left=set(tg.columns), index_label="지표")
        bl, br = st.columns(2)
        with bl:
            pt = B.pareto_table(d, prob)
            front = [ko(f) for f in pt.index[pt["pareto"]]]
            title = f"효율·탄소마진 파레토 경계: {', '.join(front[:4])} — {nm}은 기대 NPV 최고점"
            st.plotly_chart(CH.pareto(pt, {f: ko(f) for f in pt.index}, best, title,
                                      S.subtitle("$M · kg/kWh", None, extra="원 크기 = 최대 거점 의존도 낮을수록 큼",
                                                 src="시뮬레이터 M3·M5")),
                            use_container_width=True, config=CH.config("파레토"))
        with br:
            tgt = st.session_state["dis_target"]
            net = tuple(C.EXISTING + ([best] if best in C.CANDIDATES else []))
            res = S.disruption(sc, net, None if tgt == "전체" else tgt, st.session_state["dis_p"] / 100,
                               int(st.session_state["dis_dur"]), st.session_state["dis_loss"] / 100)
            loss = res["loss"]
            buf = np.nanmean(res["ochang_buffer"])
            title = (f"공장 중단 시 20년 손실 중앙값 {np.median(loss):,.0f}, 상위 10% {np.percentile(loss, 90):,.0f} — "
                     f"오창이 유럽 손실 물량의 {buf:.0%} 완충")
            st.plotly_chart(CH.loss_hist(loss, title, S.subtitle(
                "$M 현가", sc, src="시뮬레이터 M5",
                extra=f"{len(loss)}회 · 중단확률 {st.session_state['dis_p']:.0f}%/공장·연 · {st.session_state['dis_dur']}년 · 용량 {st.session_state['dis_loss']}% 손실")),
                use_container_width=True, config=CH.config("공장중단"))
        out = m.copy()
        out.index = [ko(i) for i in out.index]
        out = out.join(er.set_index(out.index)[["expected_npv", "worst_npv", "max_regret"]])
        c1, c2 = st.columns([1, 6])
        with c1:
            U.csv_button(out.round(1), "의사결정보드_시나리오별NPV.csv", "결과 CSV")
        with c2:
            ps = A.prob_sensitivity(m, prob)
            stable = (ps["best"] == best).all()
            st.markdown(f'<div class="note">가중치 ±10%p 민감도: 10개 조합 중 {int((ps["best"] == best).sum())}개에서 {nm} 1위'
                        f'{" — 권고 결론이 확률 가정에 강건" if stable else " — 확률 가정에 따라 권고가 바뀜"}. '
                        f'차트 PNG는 각 차트 우상단 카메라 아이콘(3배 해상도).</div>', unsafe_allow_html=True)
