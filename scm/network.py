"""M2 네트워크 배정: 연도별 공헌이익 극대화 LP (Gurobi 기본, 실패 시 HiGHS 폴백)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import data as D
from . import cost as K

SOLVER = {"name": None}


def _solve_gurobi(margin, ub_rows, cap_rows, caps, dem_rows, dems):
    import gurobipy as gp
    env = _gurobi_env()
    m = gp.Model(env=env)
    x = m.addMVar(len(margin), lb=0.0, ub=ub_rows, obj=margin)
    m.ModelSense = gp.GRB.MAXIMIZE
    cap_c = m.addConstr(cap_rows @ x <= caps)
    m.addConstr(dem_rows @ x <= dems)
    m.optimize()
    if m.Status != gp.GRB.OPTIMAL:
        raise RuntimeError(f"Gurobi status {m.Status}")
    return x.X, np.asarray(cap_c.Pi)


_ENV = {}


def _gurobi_env():
    if "env" not in _ENV:
        import gurobipy as gp
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()
        _ENV["env"] = env
    return _ENV["env"]


def _solve_highs(margin, ub_rows, cap_rows, caps, dem_rows, dems):
    from scipy.optimize import linprog
    from scipy.sparse import vstack
    A = vstack([cap_rows, dem_rows]).tocsr()
    b = np.concatenate([caps, dems])
    r = linprog(-margin, A_ub=A, b_ub=b, bounds=list(zip(np.zeros_like(ub_rows), ub_rows)), method="highs")
    if r.status != 0:
        raise RuntimeError(r.message)
    return r.x, -np.asarray(r.ineqlin.marginals[: len(caps)])


def solve_lp(*args):
    if SOLVER["name"] in (None, "Gurobi"):
        try:
            res = _solve_gurobi(*args)
            SOLVER["name"] = "Gurobi"
            return res
        except Exception:
            SOLVER["name"] = "HiGHS (폴백)"
    return _solve_highs(*args)


def _stages(plan: dict | None, f: str):
    return (plan or {}).get(f, D.FULL_NOW)


def allocate_year(d: dict, sc: C.Scenario, t: int, factories: list[str], dem_t: pd.Series,
                  plan: dict | None = None, cap_mult: dict | None = None) -> dict:
    """연도 t 배정 LP. plan: 공장별 투자 단계, cap_mult: 공장별 가동 가능 비율(중단 시나리오)."""
    from scipy.sparse import csr_matrix
    lt = K.lane_table(d, sc, t, factories)
    f_ids = lt.index.get_level_values(0)
    c_ids = lt.index.get_level_values(1)
    caps = np.array([D.capacity(d, f, t, _stages(plan, f)) * (cap_mult or {}).get(f, 1.0) for f in factories])
    ub = np.where(lt["eligible"].values, np.inf, 0.0)
    n = len(lt)
    f_pos = pd.Index(factories).get_indexer(f_ids)
    customers = dem_t.index
    c_pos = customers.get_indexer(c_ids)
    cap_rows = csr_matrix((np.ones(n), (f_pos, np.arange(n))), shape=(len(factories), n))
    dem_rows = csr_matrix((np.ones(n), (c_pos, np.arange(n))), shape=(len(customers), n))
    dems = dem_t.values * sc.share_cap
    # 음(-)의 공헌이익 레인은 공급하지 않는다 (상한이 '이하' 제약이므로 자연히 0)
    x, pi = solve_lp(lt["margin"].values.astype(float), ub, cap_rows, caps, dem_rows, dems)
    lt = lt.assign(flow=np.where(np.abs(x) < 1e-9, 0.0, x))
    return {"lanes": lt, "shadow": pd.Series(pi, index=factories), "capacity": pd.Series(caps, index=factories)}


def summarize_year(d: dict, t: int, r: dict, factories: list[str], plan: dict | None = None,
                   sc: C.Scenario | None = None) -> list[dict]:
    lt = r["lanes"]
    g = lt.assign(rev=lt["flow"] * lt["price"], contrib=lt["flow"] * lt["margin"],
                  eu=lt["flow"] * lt["is_eu"]).groupby(level=0)[["flow", "rev", "contrib", "eu"]].sum()
    rows = []
    for f in factories:
        fo = D.fixed_opex(d, f, t, _stages(plan, f), sc)
        rows.append({"year": t, "factory": f, "volume": g.loc[f, "flow"], "eu_volume": g.loc[f, "eu"],
                     "capacity": r["capacity"][f], "revenue": g.loc[f, "rev"], "contribution": g.loc[f, "contrib"],
                     "fixed_opex": fo, "ebitda": g.loc[f, "contrib"] - fo})
    return rows


def run_network(d: dict, sc: C.Scenario, factories: list[str], plan: dict | None = None) -> dict:
    """20개 연도 LP를 연도별로 분리해 풀고 공장별 연도 손익을 집계."""
    dem = D.demand(d, sc)
    rows, shadow, lanes = [], {}, {}
    for t in C.YEARS:
        r = allocate_year(d, sc, t, factories, dem[t], plan)
        lanes[t] = r["lanes"]
        shadow[t] = r["shadow"]
        rows += summarize_year(d, t, r, factories, plan, sc)
    pl = pd.DataFrame(rows)
    return {"pl": pl, "shadow": pd.DataFrame(shadow), "lanes": lanes, "demand": dem, "solver": SOLVER["name"],
            "scenario": sc, "factories": list(factories), "plan": plan or {}}


def capacity_gap(d: dict, sc: C.Scenario) -> pd.DataFrame:
    """<자료 2> B표: 유럽 OEM 수요, 70% 공략 가능 물량, 브로츠와프 대비 격차."""
    dem = D.demand(d, sc)
    eu = D.eu_customers(d)
    out = pd.DataFrame({
        "eu_demand": dem.loc[eu].sum(),
        "eu_addressable": dem.loc[eu].sum() * sc.share_cap,
        "wroclaw_cap": [D.capacity(d, C.WROCLAW, t) for t in C.YEARS],
        "global_addressable": dem.sum() * sc.share_cap,
        "existing_cap": [D.capacity(d, C.WROCLAW, t) + D.capacity(d, C.OCHANG, t) for t in C.YEARS],
    })
    out["eu_gap"] = out["eu_addressable"] - out["wroclaw_cap"]
    return out
