"""M5·M6 정합성 점검 (케이스에 목표값이 없으므로 산식·보정 조건을 확인한다)."""
import numpy as np
import pytest

from scm import config as C, data as D, analysis as A, board as B, finance as F, network as N


@pytest.fixture(scope="session")
def d():
    return D.load()


@pytest.fixture(scope="session")
def m(d):
    return A.npv_matrix(d)


def test_expected_and_regret(m):
    er = A.expected_and_regret(m, C.DEFAULT_PROB)
    p = np.array([C.DEFAULT_PROB[k] for k in m.columns])
    assert er.loc["F_EU_HU_DEBRECEN", "expected_npv"] == pytest.approx(float(m.loc["F_EU_HU_DEBRECEN"].values @ p))
    assert er.loc[A.NO_INVEST, "expected_npv"] == 0
    # 후회 = 시나리오별 최댓값 − 자기 값, 최소 후회 대안은 0 이상
    assert (er["max_regret"] >= 0).all()


def test_phasing_stages_sum_to_full(d):
    """2단계(0.5+0.5, 지연 0)는 즉시 전량 투자와 같은 결과여야 한다."""
    sc = C.SCENARIOS["base"]
    f = "F_EU_HU_DEBRECEN"
    full = F.evaluate_candidate(d, sc, f)["network_npv"]
    split = F.evaluate_candidate(d, sc, f, stages=((0, 0.5), (0, 0.5)))["network_npv"]
    assert split == pytest.approx(full, abs=0.5)


def test_delay_shifts_capex(d):
    f = "F_EU_HU_DEBRECEN"
    assert set(D.capex_flows(d, f, A.DELAY2)) == {2029, 2030}
    assert D.capacity(d, f, 2030, A.DELAY2) == 0 and D.capacity(d, f, 2031, A.DELAY2) == pytest.approx(20)


def test_demand_mc_calibration(d):
    """공식 수요 둔화(×0.5)가 기준 MC 분포의 하위 10% 부근(5~20%)에 위치."""
    mc = A.demand_paths(d, C.SCENARIOS["base"], n=2000)
    slow = D.demand(d, C.SCENARIOS["slow_demand"]).sum()
    for y in (2030, 2035, 2045):
        pct = (mc["total"][:, C.YEARS.index(y)] < slow[y]).mean()
        assert 0.05 <= pct <= 0.20


def test_switchpoint_crossing():
    import pandas as pd
    assert A.zero_crossings(pd.Series([-100.0, 100.0], index=[0.8, 1.0])) == [pytest.approx(0.9)]


def test_disruption_nonnegative_loss(d):
    r = A.disruption_mc(d, C.SCENARIOS["base"], C.EXISTING, p=0.1, n=50)
    assert (r["loss"] >= -1e-6).all()


def test_board_triggers(d):
    rec = B.recommendation(d, C.DEFAULT_PROB, C.SCENARIOS["base"])
    tg = B.triggers(d, rec)
    assert len(tg) >= 4 and rec["best"] in C.CANDIDATES + [A.NO_INVEST]
