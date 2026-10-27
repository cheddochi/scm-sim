"""M4 투자평가: 공장 단위 NPV(<자료 13>) 대 네트워크 증분 NPV(<자료 14>)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C
from . import data as D
from . import network as N


@dataclass
class FinanceRules:
    tax_losses: str = "none"      # none: 손실연도 세금 0 / shield: 음(-)의 세금 인정
    capex_net_of_subsidy: bool = True


RULES = FinanceRules()


def discount(t) -> np.ndarray:
    return 1 / (1 + C.WACC) ** (np.asarray(t) - C.BASE_YEAR)


def factory_cashflow(d: dict, pl: pd.DataFrame, f: str, rules: FinanceRules = RULES,
                     stages=D.FULL_NOW, subsidy_mult: float = 1.0) -> pd.DataFrame:
    """공장 하나의 연도별 세후 현금흐름($M)."""
    p = pl[pl.factory == f].set_index("year").reindex(C.YEARS).fillna(0.0)
    capex = pd.Series(D.capex_flows(d, f, stages, subsidy_mult), dtype=float).reindex(C.YEARS).fillna(0.0)
    dep = pd.Series(D.depreciation(d, f, stages, subsidy_mult), dtype=float).reindex(C.YEARS).fillna(0.0)
    taxable = p["ebitda"] - dep
    if rules.tax_losses == "none":
        taxable = taxable.clip(lower=0)
    tax = taxable * C.TAX[f]
    cf = p["ebitda"] - tax - capex
    return pd.DataFrame({"ebitda": p["ebitda"], "dep": dep, "tax": tax, "capex": capex, "cf": cf})


def npv(cf: pd.Series) -> float:
    return float((cf.values * discount(cf.index)).sum())


def irr(cf: pd.Series) -> float | None:
    v = cf.values
    if not (v.min() < 0 < v.max()):
        return None
    lo, hi = -0.99, 1.0
    f = lambda r: (v / (1 + r) ** np.arange(len(v))).sum()
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return mid


def payback_year(cf: pd.Series) -> int | None:
    cum = cf.cumsum()
    pos = cum[cum >= 0]
    after_neg = cum.index[cum < 0]
    if len(after_neg) == 0 or pos.empty:
        return None
    last_neg = after_neg.max()
    nxt = pos[pos.index > last_neg]
    return int(nxt.index[0]) if not nxt.empty else None


def network_npv(d: dict, run: dict, rules: FinanceRules = RULES) -> tuple[float, dict]:
    sm = run["scenario"].subsidy_mult
    flows = {f: factory_cashflow(d, run["pl"], f, rules, run["plan"].get(f, D.FULL_NOW), sm)
             for f in run["pl"].factory.unique()}
    return sum(npv(v["cf"]) for v in flows.values()), flows


def evaluate_candidate(d: dict, sc: C.Scenario, f: str, base_run: dict | None = None,
                       rules: FinanceRules = RULES, stages=D.FULL_NOW) -> dict:
    base_run = base_run or N.run_network(d, sc, C.EXISTING)
    with_run = N.run_network(d, sc, C.EXISTING + [f], {f: stages})
    npv0, _ = network_npv(d, base_run, rules)
    npv1, flows = network_npv(d, with_run, rules)
    own = flows[f]["cf"]
    return {"factory": f, "plant_npv": npv(own), "plant_irr": irr(own), "payback": payback_year(own),
            "network_npv": npv1 - npv0, "base_npv": npv0, "run": with_run, "flows": flows}


def scenario_table(d: dict, rules: FinanceRules = RULES) -> pd.DataFrame:
    """<자료 14> B표: 시나리오 × 후보지 네트워크 증분 NPV, 첫 행은 기존 네트워크 NPV."""
    out = {}
    for k, sc in C.SCENARIOS.items():
        base = N.run_network(d, sc, C.EXISTING)
        col = {"existing": network_npv(d, base, rules)[0]}
        for f in C.CANDIDATES:
            col[f] = evaluate_candidate(d, sc, f, base, rules)["network_npv"]
        out[k] = col
    return pd.DataFrame(out)
