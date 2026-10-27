"""M5 불확실성·실물옵션: 기대 NPV, 최대 후회, 스위치포인트, 투자 시기, 토네이도, 몬테카를로."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import data as D
from . import cost as K
from . import network as N
from . import finance as F
from .cache import memo

NO_INVEST = "NO_INVEST"
HALF_NOW = ((0, 0.5),)
DELAY2 = ((2, 1.0),)
PHASED = ((0, 0.5), (2, 0.5))


def _compact(run: dict) -> dict:
    """캐시용: 레인표(20개 연도 DataFrame)를 빼고 손익·잠재가격만 남긴다."""
    return {k: run[k] for k in ("pl", "shadow", "solver", "factories", "plan")}


# ---------------------------------------------------------------- 시나리오별 후보지 평가
def evaluate_all(d: dict, sc: C.Scenario) -> dict:
    """한 시나리오에서 기존 네트워크와 후보지 8곳의 공장 NPV·증분 NPV."""
    def calc():
        base = N.run_network(d, sc, C.EXISTING)
        npv0, flows0 = F.network_npv(d, base)
        rows, runs = [], {}
        for f in C.CANDIDATES:
            e = F.evaluate_candidate(d, sc, f, base)
            rows.append({"factory": f, "plant_npv": e["plant_npv"], "plant_irr": e["plant_irr"],
                         "payback": e["payback"], "network_npv": e["network_npv"]})
            runs[f] = _compact(e["run"])
        t = pd.DataFrame(rows).set_index("factory")
        t["cannibalization"] = t["network_npv"] - t["plant_npv"]
        return {"existing_npv": npv0, "table": t, "base_run": _compact(base), "runs": runs}
    return memo("evaluate_all", sc, calc)


def npv_matrix(d: dict, scenarios: dict | None = None) -> pd.DataFrame:
    """행: 대안(투자 안 함 + 후보지 8곳), 열: 시나리오. 값: 네트워크 증분 NPV($M)."""
    scenarios = scenarios or C.SCENARIOS
    cols = {k: evaluate_all(d, sc)["table"]["network_npv"] for k, sc in scenarios.items()}
    m = pd.DataFrame(cols)
    m.loc[NO_INVEST] = 0.0
    return m.loc[[NO_INVEST] + C.CANDIDATES]


def expected_and_regret(m: pd.DataFrame, prob: dict) -> pd.DataFrame:
    """질문 5(a)(b): 확률 가중 기대 NPV와 최대 후회(minimax regret)."""
    p = pd.Series(prob).reindex(m.columns).fillna(0.0)
    regret = m.max(axis=0) - m
    out = pd.DataFrame({
        "expected_npv": m.mul(p, axis=1).sum(axis=1),
        "worst_npv": m.min(axis=1),
        "max_regret": regret.max(axis=1),
        "worst_regret_scenario": regret.idxmax(axis=1),
    })
    out["rank_expected"] = out["expected_npv"].rank(ascending=False, method="min").astype(int)
    out["rank_regret"] = out["max_regret"].rank(ascending=True, method="min").astype(int)
    return out


def prob_sensitivity(m: pd.DataFrame, prob: dict, delta: float = 0.10) -> pd.DataFrame:
    """가중치 ±10%p 민감도: 한 시나리오 확률을 올리고 나머지를 비례 축소했을 때 1위 대안."""
    rows = []
    for k in m.columns:
        for sgn in (+1, -1):
            q = dict(prob)
            new = min(max(q[k] + sgn * delta, 0.0), 1.0)
            rest = 1 - q[k]
            for j in q:
                q[j] = new if j == k else (q[j] * (1 - new) / rest if rest > 0 else (1 - new) / (len(q) - 1))
            e = expected_and_regret(m, q)
            rows.append({"scenario": k, "shift": sgn * delta, "best": e["expected_npv"].idxmax(),
                         "best_npv": e["expected_npv"].max()})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 스위치포인트
def switchpoint_curve(d: dict, base: C.Scenario, mults=None) -> pd.DataFrame:
    """수요 성장률 승수에 따른 후보지별 증분 NPV."""
    mults = tuple(mults or np.round(np.arange(0.3, 1.21, 0.1), 2))

    def calc():
        rows = {}
        for g in mults:
            rows[g] = evaluate_all(d, base.with_(growth_mult=float(g), key="sweep"))["table"]["network_npv"]
        return pd.DataFrame(rows).T
    return memo("switchpoint", (base, mults), calc)


def zero_crossings(curve: pd.Series) -> list[float]:
    """선형보간으로 NPV가 0을 지나는 승수."""
    x, y = curve.index.values.astype(float), curve.values
    out = []
    for i in range(len(x) - 1):
        if y[i] == 0:
            out.append(x[i])
        elif y[i] * y[i + 1] < 0:
            out.append(x[i] - y[i] * (x[i + 1] - x[i]) / (y[i + 1] - y[i]))
    return out


# ---------------------------------------------------------------- 투자 시기 (질문 5d)
def _npv_with(d: dict, sc: C.Scenario, f: str, stages) -> float:
    base = N.run_network(d, sc, C.EXISTING)
    return F.evaluate_candidate(d, sc, f, base, stages=stages)["network_npv"]


def timing_options(d: dict, f: str, prob: dict, scenarios: dict | None = None) -> pd.DataFrame:
    """즉시 전량 vs 2단계 분할(절반 즉시 + 절반 2년 후 조건부) vs 2년 연기(2028년 정보 확인 후 조건부).

    연기·2단계는 2028년에 시나리오가 판명된다고 보고, 그 시나리오에서 NPV가 더 나은 쪽을 고른다.
    """
    scenarios = scenarios or C.SCENARIOS

    def calc():
        rows = []
        for k, sc in scenarios.items():
            now = evaluate_all(d, sc)["table"].loc[f, "network_npv"]
            delay = _npv_with(d, sc, f, DELAY2)
            half = _npv_with(d, sc, f, HALF_NOW)
            phased = _npv_with(d, sc, f, PHASED)
            rows.append({"scenario": k, "now": now, "delay_full": delay, "delay": max(0.0, delay),
                         "half_only": half, "phased_full": phased, "phased": max(half, phased)})
        return pd.DataFrame(rows).set_index("scenario")
    t = memo("timing", (f, tuple(scenarios.items())), calc)
    p = pd.Series(prob).reindex(t.index).fillna(0.0)
    summary = pd.DataFrame({
        "expected_npv": [float((t[c] * p).sum()) for c in ("now", "phased", "delay")],
        "worst_npv": [t[c].min() for c in ("now", "phased", "delay")],
    }, index=["즉시 전량(2027 착공)", "2단계 분할(수요 연동)", "2년 연기(2029 착공)"])
    return {"by_scenario": t, "summary": summary}


# ---------------------------------------------------------------- 토네이도
TORNADO_VARS = [
    ("growth_mult", "수요 성장률 승수", 0.5, 1.2),
    ("price_mult", "판매단가 수준", 0.95, 1.05),
    ("eua_mult", "EU 탄소가격", 0.5, 2.0),
    ("subsidy_mult", "투자 보조금", 0.0, 2.0),
    ("cap", "탄소발자국 상한(위치기반)", "off", "on"),
]


def tornado(d: dict, f: str, base: C.Scenario) -> pd.DataFrame:
    def calc():
        mid = evaluate_all(d, base)["table"].loc[f, "network_npv"]
        rows = []
        for attr, label, lo, hi in TORNADO_VARS:
            vals = []
            for v in (lo, hi):
                if attr == "cap":
                    sc = base.with_(location_based=v == "on", cap_2030=65.0 if v == "on" else None,
                                    cap_2035=60.0 if v == "on" else None, key="tornado")
                else:
                    sc = base.with_(**{attr: v}, key="tornado")
                vals.append(evaluate_all(d, sc)["table"].loc[f, "network_npv"])
            rows.append({"variable": label, "low_label": lo, "high_label": hi, "low": vals[0], "high": vals[1],
                         "base": mid, "swing": abs(vals[1] - vals[0])})
        return pd.DataFrame(rows).sort_values("swing", ascending=False)
    return memo("tornado", (f, base), calc)


# ---------------------------------------------------------------- 수요 몬테카를로
def demand_paths(d: dict, sc: C.Scenario, n: int = 1000, sd_annual: float = 0.02,
                 sigma_mult: float | None = None, seed: int = 7) -> dict:
    """고객별 수요 경로 n개. 경로마다 성장률 승수 m~N(1, σm)과 연도별 성장률 잡음 N(0, sd)을 준다.

    σm은 공식 '수요 둔화'(×0.5)가 하위 10%에 오도록 σm = 0.5 / z(0.9) = 0.39로 보정한다.
    """
    sigma_mult = 0.5 / 1.2816 if sigma_mult is None else sigma_mult
    rng = np.random.default_rng(seed)
    dm = d["demand"]
    g1 = dm["growth_rate_2026_2030"].values * sc.growth_mult
    g2 = dm["growth_rate_2031_2045"].values * sc.growth_mult
    base = dm["annual_ev_battery_demand_GWh_2026"].values
    m = rng.normal(1.0, sigma_mult, size=(n, 1))
    eps = rng.normal(0.0, sd_annual, size=(n, len(C.YEARS) - 1))       # 연도 공통 충격
    paths = np.empty((n, len(dm), len(C.YEARS)))
    paths[:, :, 0] = base
    for i, t in enumerate(C.YEARS[1:], start=1):
        g = np.where(t <= 2030, g1, g2)[None, :] * m + eps[:, i - 1:i]
        paths[:, :, i] = paths[:, :, i - 1] * (1 + np.maximum(g, -0.5))
    shock = np.array([0.0 if t < 2027 else (1.0 if sc.shock_mode == "step" else min(1.0, (t - 2026) / 4))
                      for t in C.YEARS])
    paths = paths * (1 + sc.demand_shock * shock)[None, None, :]
    eu = (dm["region"] == "EU").values
    return {"customer": paths, "eu": paths[:, eu, :].sum(axis=1), "total": paths.sum(axis=1),
            "years": C.YEARS, "sigma_mult": sigma_mult}


def shortfall_prob(eu_paths: np.ndarray, year: int, capacity: float, share_cap: float = C.OEM_SHARE_CAP) -> float:
    """연도 year에 유럽 공략 가능 물량(수주 상한 적용)이 생산능력을 넘을 확률."""
    i = C.YEARS.index(year)
    return float((eu_paths[:, i] * share_cap > capacity).mean())


# ---------------------------------------------------------------- 공장 중단 스트레스 테스트
def disruption_mc(d: dict, sc: C.Scenario, factories: list[str], plan: dict | None = None,
                  target: str | None = None, p: float = 0.05, duration: int = 1, loss: float = 0.5,
                  n: int = 300, seed: int = 11) -> dict:
    """공장별로 매년 확률 p로 가동 중단(기간 duration년, 생산능력 loss 상실)이 생긴다고 보고 NPV 손실 분포를 낸다.

    target을 주면 그 공장만 중단 대상. 손실은 세전 EBITDA 감소의 현재가치($M).
    오창 완충률 = 중단 연도 오창 유럽 공급 증가분 / 중단 공장의 유럽 공급 감소분.
    """
    def calc():
        rng = np.random.default_rng(seed)
        dem = D.demand(d, sc)
        targets = [target] if target else list(factories)
        base = {t: N.allocate_year(d, sc, t, factories, dem[t], plan) for t in C.YEARS}
        base_sum = {t: pd.DataFrame(N.summarize_year(d, t, base[t], factories, plan, sc)).set_index("factory")
                    for t in C.YEARS}
        memo_year: dict = {}
        losses, buffers = [], []
        for _ in range(n):
            hit: dict[int, dict] = {}
            for f in targets:
                t = C.YEARS[0]
                while t <= C.YEARS[-1]:
                    if rng.random() < p:
                        for k in range(duration):
                            if t + k in base:
                                hit.setdefault(t + k, {})[f] = 1 - loss
                        t += duration
                    else:
                        t += 1
            total, lost_eu, och_gain = 0.0, 0.0, 0.0
            for t, cm in hit.items():
                key = (t, tuple(sorted(cm.items())))
                if key not in memo_year:
                    r = N.allocate_year(d, sc, t, factories, dem[t], plan, cm)
                    memo_year[key] = pd.DataFrame(N.summarize_year(d, t, r, factories, plan, sc)).set_index("factory")
                s, b = memo_year[key], base_sum[t]
                total += float((b["ebitda"].sum() - s["ebitda"].sum()) * F.discount(t, sc.wacc))
                lost_eu += float(sum(b.loc[f, "eu_volume"] - s.loc[f, "eu_volume"] for f in cm))
                if C.OCHANG not in cm:
                    och_gain += float(s.loc[C.OCHANG, "eu_volume"] - b.loc[C.OCHANG, "eu_volume"])
            losses.append(total)
            buffers.append(och_gain / lost_eu if lost_eu > 1e-6 else np.nan)
        return {"loss": np.array(losses), "ochang_buffer": np.array(buffers)}
    key = (sc, tuple(factories), tuple(sorted((plan or {}).items())), target, p, duration, loss, n, seed)
    return memo("disruption", key, calc)


# ---------------------------------------------------------------- 탄소·효율 지표
def carbon_table(d: dict) -> pd.DataFrame:
    """M3: 공장별 시장/위치기반 CF, 유럽 평균 운송 배출 포함 상한 판정, 필요 자가발전 비율."""
    cf = K.carbon_footprint(d, C.SCENARIOS["base"])
    eu = D.eu_customers(d)
    tr = d["lanes"]["transport_co2e_kg_per_kwh_finished_pack"].unstack()[eu].mean(axis=1).reindex(cf.index)
    out = cf.assign(eu_transport=tr)
    out["location_total"] = out["location"] + out["eu_transport"]
    out["market_total"] = out["market"] + out["eu_transport"]
    out["pass_2030"] = out["location_total"] <= 65
    out["pass_2035"] = out["location_total"] <= 60
    out["margin_2035"] = 60 - out["location_total"]
    out["selfgen_2030"] = [K.self_gen_needed(d, f, 65, tr[f]) for f in out.index]
    out["selfgen_2035"] = [K.self_gen_needed(d, f, 60, tr[f]) for f in out.index]
    lt = d["lanes"]["lead_time_days"].unstack()[eu].mean(axis=1)
    out["eu_lead_time"] = lt.reindex(out.index)
    return out


def capital_cost_per_kwh(d: dict, f: str, years: int = 17, wacc: float = C.WACC) -> float:
    """신규 공장 연간 자본비용($/kWh): 순 CAPEX × 자본회수계수(WACC 9%, 가동 17년) ÷ 생산능력."""
    if f in C.EXISTING:
        return 0.0
    net = d["factories"].loc[f, "capex_usd_million"] * (1 - C.SUBSIDY[f])
    r = wacc
    crf = r / (1 - (1 + r) ** -years)
    return net * crf / d["factories"].loc[f, "target_capacity_gwh_yr"]
