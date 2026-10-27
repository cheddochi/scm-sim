"""M6 이사회 의사결정 보드: 권고안, KPI, 스위치포인트 trigger 규칙, 파레토 지표."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import data as D
from . import analysis as A


FORMS = {"now": "즉시 전량", "phased": "2단계 분할", "delay": "2년 연기"}


def ko(f: str) -> str:
    if f == A.NO_INVEST:
        return "투자 안 함"
    if "|" in f:
        site, form = f.split("|")
        return f"{C.FACTORY_KO.get(site, site)} · {FORMS[form]}"
    return C.FACTORY_KO.get(f, f)


def extended_matrix(d: dict) -> pd.DataFrame:
    """대안 = 투자 안 함 + 후보지 8곳 × 투자 형태 3종. 값은 시나리오별 증분 NPV.

    2단계·연기는 2028년에 시나리오가 판명된다는 전제의 조건부 선택 가치(analysis.timing_options).
    """
    m = A.npv_matrix(d)
    rows = {A.NO_INVEST: m.loc[A.NO_INVEST]}
    for f in C.CANDIDATES:
        bs = A.timing_options(d, f, C.DEFAULT_PROB)["by_scenario"]
        rows[f"{f}|now"] = m.loc[f]
        rows[f"{f}|phased"] = bs["phased"].reindex(m.columns)
        rows[f"{f}|delay"] = bs["delay"].reindex(m.columns)
    return pd.DataFrame(rows).T[m.columns]


def fmt_m(x: float, sign: bool = True) -> str:
    """$M 표기: 천 단위 쉼표, 음수는 유니코드 마이너스."""
    s = f"{abs(x):,.0f}"
    if x < -0.5:
        return "−" + s
    return ("+" if sign and x > 0.5 else "") + s


def recommendation(d: dict, prob: dict, base: C.Scenario) -> dict:
    """권고 = 투자 형태까지 포함한 25개 대안 중 기대 NPV 최대. 최대 후회도 같은 대안 집합에서 계산."""
    m = A.npv_matrix(d)
    er = A.expected_and_regret(m, prob)                 # 후보지 단위(즉시 전량) 비교
    ext = extended_matrix(d)
    er_ext = A.expected_and_regret(ext, prob)
    best_key = er_ext["expected_npv"].idxmax()
    minimax_key = er_ext["max_regret"].idxmin()
    best = best_key.split("|")[0]
    out = {"matrix": m, "er": er, "ext": ext, "er_ext": er_ext, "best_key": best_key, "best": best,
           "minimax_key": minimax_key, "minimax": minimax_key.split("|")[0]}
    if best == A.NO_INVEST:
        out.update(timing=None, form="투자 보류", form_npv=0.0, form_worst=0.0, form_regret=0.0)
        return out
    out.update(timing=A.timing_options(d, best, prob), form=FORMS[best_key.split("|")[1]],
               form_npv=float(er_ext.loc[best_key, "expected_npv"]), form_worst=float(er_ext.loc[best_key, "worst_npv"]),
               form_regret=float(er_ext.loc[best_key, "max_regret"]),
               now_regret=float(er_ext.loc[f"{best}|now", "max_regret"]))
    sw = A.switchpoint_curve(d, base)
    out["switch_curve"] = sw
    zc = A.zero_crossings(sw[best])
    out["switch_growth"] = zc[0] if zc else None
    out["tornado"] = A.tornado(d, best, base)
    return out


def carbon_kpi(d: dict) -> dict:
    ct = A.carbon_table(d)
    cands = ct.loc[C.CANDIDATES]
    return {"table": ct, "pass_2035": int(cands["pass_2035"].sum()), "pass_2030": int(cands["pass_2030"].sum()),
            "n": len(cands)}


def _price_breakeven(tor: pd.DataFrame) -> float | None:
    r = tor[tor["variable"] == "판매단가 수준"]
    if r.empty:
        return None
    r = r.iloc[0]
    lo, hi, vlo, vhi = float(r["low_label"]), float(r["high_label"]), r["low"], r["high"]
    if vlo * vhi >= 0:
        return None
    return lo + (0 - vlo) * (hi - lo) / (vhi - vlo)


def triggers(d: dict, rec: dict) -> pd.DataFrame:
    """이사회 분기 점검 지표와 행동 전환 조건. 임계값은 시뮬레이터 산출값."""
    best = rec["best"]
    name = ko(best)
    rows = []
    sg = rec.get("switch_growth")
    if sg is not None:
        rows.append({"지표": "유럽 OEM 발주 성장률 (기준 예측 대비)", "경고": f"{(1 + sg) / 2 * 100:.0f}% 미만",
                     "행동 전환": f"{sg * 100:.0f}% 미만 2분기 연속",
                     "행동": f"{name} 2단계 증설 보류, 1단계 물량은 오창·브로츠와프와 재배분",
                     "근거": f"성장률 승수 ×{sg:.2f}에서 {name} 증분 NPV = 0"})
    ct = A.carbon_table(d)
    sgw = ct.loc[C.WROCLAW, "selfgen_2035"]
    rows.append({"지표": "EU 배터리 탄소발자국 위임법 산정 방식", "경고": "위치기반 초안 유지",
                 "행동 전환": "위치기반 60kg 상한 유예 없이 확정",
                 "행동": f"브로츠와프 직접 연결 저탄소 전력 {sgw * 100:.1f}% 확보, 저탄소 거점 착공 가속",
                 "근거": f"브로츠와프 위치기반 {ct.loc[C.WROCLAW, 'location_total']:.2f}kg > 60kg"})
    pb = _price_breakeven(rec["tornado"]) if rec.get("tornado") is not None else None
    if pb is not None:
        rows.append({"지표": "유럽 셀 판매단가 (계획 경로 대비)", "경고": f"{(1 + pb) / 2 * 100:.1f}% 미만",
                     "행동 전환": f"{pb * 100:.1f}% 미만", "행동": "신규 착공 보류, 고객 Take-or-Pay 계약 선행",
                     "근거": f"단가 수준 ×{pb:.3f}에서 {name} 증분 NPV = 0"})
    m = rec["matrix"]
    rows.append({"지표": "산업가속화법(IAA) 한국산 셀 요건", "경고": "역내 조립만 인정 유지",
                 "행동 전환": "2030년 한국산 셀 불이익 확정",
                 "행동": "오창을 아시아·중동·남미 스윙 공장으로 고정, 유럽 물량 전량 역내 생산",
                 "근거": f"역내생산 요건 시 {name} 증분 NPV {fmt_m(m.loc[best, 'iaa'])}"})
    rows.append({"지표": "투자 보조금 확정 여부 (투자국 정부)", "경고": "협상 지연",
                 "행동 전환": "보조금 철회 또는 인허가 재검토",
                 "행동": "차순위 후보지로 전환 검토 (최대 후회 최소안)",
                 "근거": f"보조금 0% 시 {name} 증분 NPV "
                         f"{fmt_m(rec['tornado'].set_index('variable').loc['투자 보조금', 'low'])}"
                 if rec.get("tornado") is not None else ""})
    return pd.DataFrame(rows)


def pareto_table(d: dict, prob: dict) -> pd.DataFrame:
    """효율(기대 증분 NPV) 대 회복탄력성(2035 탄소 안전마진, 유럽 평균 리드타임, 최대 거점 의존도)."""
    er = A.expected_and_regret(A.npv_matrix(d), prob)
    ct = A.carbon_table(d)
    base_eval = A.evaluate_all(d, C.SCENARIOS["base"])
    rows = []
    for f in C.CANDIDATES:
        pl = base_eval["runs"][f]["pl"]
        p35 = pl[pl.year == 2035].set_index("factory")
        dep = p35["eu_volume"].max() / p35["eu_volume"].sum()
        rows.append({"factory": f, "expected_npv": er.loc[f, "expected_npv"], "carbon_margin": ct.loc[f, "margin_2035"],
                     "eu_lead_time": ct.loc[f, "eu_lead_time"], "max_site_share": dep})
    t = pd.DataFrame(rows).set_index("factory")
    # 파레토 효율: 기대 NPV↑, 탄소 마진↑ 둘 다에서 지배되지 않는 후보
    eff = []
    for f in t.index:
        dominated = ((t["expected_npv"] >= t.loc[f, "expected_npv"]) & (t["carbon_margin"] >= t.loc[f, "carbon_margin"])
                     & ((t["expected_npv"] > t.loc[f, "expected_npv"]) | (t["carbon_margin"] > t.loc[f, "carbon_margin"]))).any()
        eff.append(not dominated)
    t["pareto"] = eff
    return t
