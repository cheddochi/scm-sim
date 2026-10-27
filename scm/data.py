"""M0 데이터: 엑셀 로드와 연도별 수요·가격·용량 경로."""
from __future__ import annotations
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as C


@lru_cache(maxsize=1)
def load(path: str | None = None) -> dict:
    xl = pd.read_excel(path or C.EXCEL_PATH, sheet_name=None)
    fac = xl["Factories"].rename(columns={"fixed_opex_usd_million_per_yearr": "fixed_opex_usd_million_per_year"})
    fac = fac.set_index("factory_id")
    dem = xl["Demand_Nodes"].set_index("demand_id")
    dem["region"] = dem.index.str.split("_").str[1]          # EU / AS / ME / SA
    lanes = xl["Factory_Demand_Lanes"].set_index(["factory_id", "demand_id"])
    annual = xl["Annual_Assumptions"].set_index("year")
    return {"factories": fac, "demand": dem, "lanes": lanes, "annual": annual,
            "transport": xl["Transport_Params"].set_index("mode")}


def eu_customers(d: dict) -> list[str]:
    return d["demand"].index[d["demand"]["region"] == "EU"].tolist()


def demand(d: dict, sc: C.Scenario) -> pd.DataFrame:
    """고객 × 연도 수요(GWh). 성장률 승수와 일괄 충격을 반영."""
    dm = d["demand"]
    g1 = dm["growth_rate_2026_2030"].values * sc.growth_mult
    g2 = dm["growth_rate_2031_2045"].values * sc.growth_mult
    base = dm["annual_ev_battery_demand_GWh_2026"].values
    out = {}
    for t in C.YEARS:
        n1 = min(t, 2030) - 2026
        n2 = max(t - 2030, 0)
        out[t] = base * (1 + g1) ** n1 * (1 + g2) ** n2 * (1 + sc.demand_shock)
    return pd.DataFrame(out, index=dm.index)


def _two_phase(t: int, r1: float, r2: float, switch: int) -> float:
    n1 = min(t, switch) - C.BASE_YEAR
    n2 = max(t - switch, 0)
    return (1 + r1) ** n1 * (1 + r2) ** n2


def material(t: int) -> float:
    return C.MATERIAL_2026 * _two_phase(t, -0.015, -0.005, 2030)


def price_index(t: int) -> float:
    return _two_phase(t, -0.015, -0.005, 2030)


def conversion_index(t: int) -> float:
    return _two_phase(t, -0.01, 0.0, 2035)


def eua_eur(d: dict, t: int, sc: C.Scenario) -> float:
    return float(d["annual"].loc[t, "carbon_price_eur_per_tco2"]) * sc.eua_mult


def capacity_share(f: str, t: int) -> float:
    """연도별 가동 상한 비율 (생산능력 대비)."""
    if f in C.EXISTING:
        return 1.0
    if f == C.WROCLAW_EXP:
        start, ramp = C.START_EXP, C.RAMP_EXP
    else:
        start, ramp = C.START_GREEN, C.RAMP_GREEN
    if t < start:
        return 0.0
    return ramp.get(t, 1.0)


def capacity(d: dict, f: str, t: int) -> float:
    fac = d["factories"].loc[f]
    if f == C.WROCLAW:
        return C.WROCLAW_CAP.get(t, fac["target_capacity_gwh_yr"])
    return fac["target_capacity_gwh_yr"] * capacity_share(f, t)


def fixed_opex(d: dict, f: str, t: int) -> float:
    """고정운영비($M). 신규 공장은 램프업 중 가동 상한 비례(최소 60%), 가동 전 0."""
    base = d["factories"].loc[f, "fixed_opex_usd_million_per_year"] * (1 + C.FIXED_OPEX_GROWTH) ** (t - C.BASE_YEAR)
    if f in C.EXISTING:
        return base
    s = capacity_share(f, t)
    return 0.0 if s == 0 else base * max(s, C.RAMP_FIXED_MIN)


def capex_flows(d: dict, f: str) -> dict[int, float]:
    """연도별 순 CAPEX 집행액($M, 보조금 차감)."""
    if f in C.EXISTING:
        return {}
    gross = d["factories"].loc[f, "capex_usd_million"]
    net = gross * (1 - C.SUBSIDY[f])
    sched = C.CAPEX_SCHEDULE_EXP if f == C.WROCLAW_EXP else C.CAPEX_SCHEDULE_GREEN
    return {t: net * s for t, s in sched.items()}


def start_year(f: str) -> int | None:
    if f in C.EXISTING:
        return None
    return C.START_EXP if f == C.WROCLAW_EXP else C.START_GREEN
