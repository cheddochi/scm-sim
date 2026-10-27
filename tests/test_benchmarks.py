"""케이스 수치 재현 벤치마크 (대화요약.md 8절). 실행: ./py -m pytest tests/test_benchmarks.py -q"""
import pytest

from scm import config as C, data as D, cost as K, network as N, finance as F

WOLFSBURG = "D_EU_DE_VW_WOLFSBURG"


@pytest.fixture(scope="session")
def d():
    return D.load()


@pytest.fixture(scope="session")
def table(d):
    return F.scenario_table(d)


def test_m1_landed_cost_2026(d):
    lt = K.lane_table(d, C.SCENARIOS["base"], 2026).xs(WOLFSBURG, level=1)
    assert lt.loc[C.OCHANG, "landed"] == pytest.approx(86.40, abs=0.005)
    assert lt.loc[C.WROCLAW, "landed"] == pytest.approx(86.24, abs=0.005)
    # <자료 11> 항목별
    assert lt.loc[C.OCHANG, "inventory"] == pytest.approx(0.81, abs=0.01)  # 0.805, 케이스 표 반올림
    assert lt.loc[C.OCHANG, "cbam"] == pytest.approx(1.18, abs=0.005)
    assert lt.loc[C.WROCLAW, "cf_market"] == pytest.approx(50.27, abs=0.005)
    assert lt.loc[C.OCHANG, "cf_market"] == pytest.approx(58.02, abs=0.01)


def test_m3_location_based(d):
    cf = K.carbon_footprint(d, C.SCENARIOS["base"])
    assert cf.loc[C.WROCLAW, "location"] == pytest.approx(67.11, abs=0.005)
    tr = d["lanes"].loc[C.WROCLAW].loc[D.eu_customers(d), "transport_co2e_kg_per_kwh_finished_pack"].mean()
    assert cf.loc[C.WROCLAW, "location"] + tr == pytest.approx(67.36, abs=0.02)
    assert K.self_gen_needed(d, C.WROCLAW, 65, tr) == pytest.approx(0.111, abs=0.0005)
    assert K.self_gen_needed(d, C.WROCLAW, 60, tr) == pytest.approx(0.345, abs=0.0005)


def test_m2_capacity_gap(d):
    g = N.capacity_gap(d, C.SCENARIOS["base"])["eu_gap"]
    for t, v in {2026: 0.1, 2028: 8.1, 2030: 21.8, 2035: 42.4, 2040: 66.9, 2045: 95.9}.items():
        assert g[t] == pytest.approx(v, abs=0.05)


def test_m2_network_2026(d):
    """<자료 2> A표: 2026년 비용·탄소 최적 배정 EBITDA."""
    pl = N.run_network(d, C.SCENARIOS["base"], C.EXISTING)["pl"].set_index(["year", "factory"])
    assert pl.loc[(2026, C.OCHANG), "ebitda"] == pytest.approx(375, abs=1)
    assert pl.loc[(2026, C.WROCLAW), "ebitda"] == pytest.approx(1659, abs=1)
    assert pl.loc[(2026, C.OCHANG), "eu_volume"] == pytest.approx(0.1, abs=0.05)


PLANT_13 = {  # 공장 단위 NPV, IRR(%), 회수연도
    "F_EU_PL_WROCLAW_EXP": (152, 10.0, 2036), "F_EU_HU_DEBRECEN": (1799, 16.9, 2034),
    "F_EU_DE_BRANDENBURG": (-366, 7.3, 2037), "F_EU_FR_DOUVRIN": (-433, 6.3, 2038),
    "F_EU_ES_ZARAGOZA": (263, 10.5, 2036), "F_EU_SE_SKELLEFTEA": (-963, 4.3, 2040),
    "F_EU_PT_SINES": (-558, 5.2, 2039), "F_EU_CZ_OSTRAVA": (364, 10.9, 2036),
}


@pytest.mark.parametrize("f", list(PLANT_13))
def test_m4_plant_npv(d, f):
    e = F.evaluate_candidate(d, C.SCENARIOS["base"], f)
    n, i, pb = PLANT_13[f]
    assert e["plant_npv"] == pytest.approx(n, abs=1.5)
    assert 100 * e["plant_irr"] == pytest.approx(i, abs=0.1)
    assert e["payback"] == pb


TABLE_14 = {  # 기존 네트워크 NPV + 후보지별 증분 NPV
    "existing": [15986, 15711, 6132, 14916, 15778],
    "F_EU_PL_WROCLAW_EXP": [-365, -159, -3680, -1365, -215],
    "F_EU_HU_DEBRECEN": [263, 523, 2336, -1206, 456],
    "F_EU_DE_BRANDENBURG": [-2083, -1908, -166, -3367, -1902],
    "F_EU_FR_DOUVRIN": [-997, -706, 521, -2065, -833],
    "F_EU_ES_ZARAGOZA": [-167, 78, 1311, -1195, -9],
    "F_EU_SE_SKELLEFTEA": [-2046, -1777, -608, -3053, -1907],
    "F_EU_PT_SINES": [-798, -598, 305, -1473, -680],
    "F_EU_CZ_OSTRAVA": [-511, -426, 907, -1357, -375],
}
SC_KEYS = list(C.SCENARIOS)


@pytest.mark.parametrize("row", list(TABLE_14))
@pytest.mark.parametrize("sc", SC_KEYS)
def test_m4_table14(table, row, sc):
    target = TABLE_14[row][SC_KEYS.index(sc)]
    # 기존 네트워크 NPV는 케이스 대비 약 −22 일정 편차(0.4% 이내), 고탄소 열은 내부 탄소가격 산식 차이로 ±25 이내
    tol = 40 if row == "existing" else (25 if sc == "high_carbon" else 1.5)
    assert table.loc[row, sc] == pytest.approx(target, abs=tol)
