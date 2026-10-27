"""M1 도착원가와 M3 탄소회계: 레인(공장×고객)별 연도 원가·탄소발자국 표."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import data as D

COST_ITEMS = ["material", "conversion", "power", "transport", "tariff", "inventory", "cbam"]
COST_KO = {"material": "소재비", "conversion": "가공비", "power": "전력비", "transport": "운송·하역비",
           "tariff": "관세", "inventory": "재고유지비", "cbam": "CBAM 추정비용",
           "iaa": "역내생산 페널티", "internal_carbon": "내부 탄소가격 조정"}


def carbon_footprint(d: dict, sc: C.Scenario) -> pd.DataFrame:
    """공장별 셀 탄소발자국(kg/kWh): 시장기반은 엑셀 고정값, 위치기반은 <자료 6> 주석 공식."""
    fac = d["factories"]
    market = d["lanes"]["product_embedded_co2e_kg_per_kwh_proxy"].groupby(level=0).first().reindex(fac.index)
    selfgen = pd.Series(sc.self_gen, dtype=float).reindex(fac.index).fillna(0.0)
    green = (fac["renewable_share"] - selfgen).clip(lower=0)
    location = market + C.POWER_KWH_PER_KWH * fac["grid_intensity_kgco2_per_kwh"] * green
    return pd.DataFrame({"market": market, "location": location})


def self_gen_needed(d: dict, f: str, cap: float, transport: float = 0.0) -> float:
    """위치기반 상한 통과에 필요한 직접 저탄소 자가발전 비율(전력 사용량 대비)."""
    cf = carbon_footprint(d, C.SCENARIOS["base"]).loc[f, "location"]
    g = d["factories"].loc[f, "grid_intensity_kgco2_per_kwh"]
    return max(0.0, (cf + transport - cap) / (C.POWER_KWH_PER_KWH * g))


def cap_for_year(sc: C.Scenario, t: int) -> float | None:
    if t >= 2035 and sc.cap_2035 is not None:
        return sc.cap_2035
    if t >= 2030 and sc.cap_2030 is not None:
        return sc.cap_2030
    return None


def lane_table(d: dict, sc: C.Scenario, t: int, factories: list[str] | None = None) -> pd.DataFrame:
    """연도 t 레인별 원가 분해, 판매가, 공헌이익, 탄소발자국, 공급 자격."""
    L = d["lanes"]
    if factories is not None:
        L = L.loc[L.index.get_level_values(0).isin(factories)]
    f_ids = L.index.get_level_values(0)
    c_ids = L.index.get_level_values(1)
    fac = d["factories"].loc[f_ids]
    dem = d["demand"].loc[c_ids]
    is_eu = (dem["region"] == "EU").values
    from_kr = (f_ids == C.OCHANG)

    price = dem["purchase_price_usd_per_kwh_2026"].values * D.price_index(t)
    out = pd.DataFrame(index=L.index)
    out["material"] = D.material(t) / fac["yield_rate"].values
    out["conversion"] = fac["conversion_cost_usd_per_kwh_ex_material"].values * D.conversion_index(t)
    out["power"] = C.POWER_KWH_PER_KWH * fac["electricity_price_usd_per_kwh"].values
    out["transport"] = L["freight_cost_usd_per_kwh_finished_pack"].values
    out["tariff"] = price * L["tariff_pct_of_customs_value"].values / 100
    out["inventory"] = (C.INVENTORY_RATE * (L["lead_time_days"].values + C.SAFETY_DAYS) / 365
                        * (out["material"] + out["conversion"]))
    eua_usd_per_kg = D.eua_eur(d, t, sc) * C.FX / 1000
    share = sc.cbam_share_2030 if t >= 2030 else sc.cbam_share
    emb = L["product_embedded_co2e_kg_per_kwh_proxy"].values
    out["cbam"] = np.where(from_kr & is_eu, emb * share * eua_usd_per_kg, 0.0)
    out["iaa"] = np.where(from_kr & is_eu & (t >= sc.iaa_from), sc.iaa_penalty, 0.0)

    cf = carbon_footprint(d, sc).loc[f_ids]
    trans_co2 = L["transport_co2e_kg_per_kwh_finished_pack"].values
    out["cf_market"] = cf["market"].values + trans_co2
    out["cf_location"] = cf["location"].values + trans_co2
    if sc.internal_carbon and t >= sc.internal_carbon_from:
        out["internal_carbon"] = np.where(is_eu, (out["cf_market"] - sc.internal_carbon_base) * eua_usd_per_kg, 0.0)
    else:
        out["internal_carbon"] = 0.0

    out["landed"] = out[COST_ITEMS].sum(axis=1)
    out["price"] = price
    out["margin"] = price - out["landed"] - out["iaa"] - out["internal_carbon"]
    out["lead_time"] = L["lead_time_days"].values
    out["is_eu"] = is_eu
    cap = cap_for_year(sc, t)
    cf_used = out["cf_location"] if sc.location_based else out["cf_market"]
    out["eligible"] = ~(is_eu & (cap is not None) & (cf_used > (cap if cap is not None else np.inf)))
    return out
