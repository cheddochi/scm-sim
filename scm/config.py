"""M0 상수: 엑셀에 없는 <자료 10> 가정과 공식 시나리오 5종 정의."""
from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import os

DATA_DIR = Path(os.environ.get("SCM_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
EXCEL_PATH = DATA_DIR / "battery_supply_chain(SIMPLE).xlsx"

YEARS = list(range(2026, 2046))
BASE_YEAR = 2026

OCHANG = "F_KR_LGES_OCHANG"
WROCLAW = "F_EU_PL_LGES_WROCLAW"
WROCLAW_EXP = "F_EU_PL_WROCLAW_EXP"
EXISTING = [OCHANG, WROCLAW]
CANDIDATES = [
    "F_EU_PL_WROCLAW_EXP", "F_EU_HU_DEBRECEN", "F_EU_DE_BRANDENBURG", "F_EU_FR_DOUVRIN",
    "F_EU_ES_ZARAGOZA", "F_EU_SE_SKELLEFTEA", "F_EU_PT_SINES", "F_EU_CZ_OSTRAVA",
]
FACTORY_KO = {
    OCHANG: "오창", WROCLAW: "브로츠와프", WROCLAW_EXP: "브로츠와프 증설",
    "F_EU_HU_DEBRECEN": "데브레첸", "F_EU_DE_BRANDENBURG": "브란덴부르크", "F_EU_FR_DOUVRIN": "두브랭",
    "F_EU_ES_ZARAGOZA": "사라고사", "F_EU_SE_SKELLEFTEA": "셀레프테오", "F_EU_PT_SINES": "시네스",
    "F_EU_CZ_OSTRAVA": "오스트라바",
}

# <자료 10> 투자 보조금율 (CAPEX 대비)
SUBSIDY = {
    "F_EU_PL_WROCLAW_EXP": 0.10, "F_EU_HU_DEBRECEN": 0.15, "F_EU_DE_BRANDENBURG": 0.15,
    "F_EU_FR_DOUVRIN": 0.25, "F_EU_ES_ZARAGOZA": 0.15, "F_EU_SE_SKELLEFTEA": 0.10,
    "F_EU_PT_SINES": 0.15, "F_EU_CZ_OSTRAVA": 0.12,
}
# <자료 10> 법인세율 (공장 소재국)
TAX = {
    OCHANG: 0.24, WROCLAW: 0.19, "F_EU_PL_WROCLAW_EXP": 0.19, "F_EU_HU_DEBRECEN": 0.09,
    "F_EU_DE_BRANDENBURG": 0.30, "F_EU_FR_DOUVRIN": 0.25, "F_EU_ES_ZARAGOZA": 0.25,
    "F_EU_SE_SKELLEFTEA": 0.206, "F_EU_PT_SINES": 0.21, "F_EU_CZ_OSTRAVA": 0.21,
}
DEPRECIATION_YEARS = 10

# 투자 일정: CAPEX 집행 비율과 연도별 가동 상한
CAPEX_SCHEDULE_EXP = {2027: 0.70, 2028: 0.30}
RAMP_EXP = {2028: 0.50}                     # 2029년부터 100%
START_EXP = 2028
CAPEX_SCHEDULE_GREEN = {2027: 0.40, 2028: 0.60}
RAMP_GREEN = {2029: 0.50, 2030: 0.85}       # 2031년부터 100%
START_GREEN = 2029

WROCLAW_CAP = {2026: 86, 2027: 88}          # 2028년부터 90 (2027년 88은 <자료 14> 기존 NPV 역산)

MATERIAL_2026 = 50.0          # $/kWh (양품 기준, 수율로 나눔)
POWER_KWH_PER_KWH = 38.8      # 셀 1kWh당 전력 사용량
MATERIAL_EMB_KG = 45.6        # 소재 내재배출
CBAM_EU_IMPORT_ORIGIN = OCHANG
OEM_SHARE_CAP = 0.70
WACC = 0.09
FX = 1.10                     # $/€
INVENTORY_RATE = 0.12
SAFETY_DAYS = 7
FIXED_OPEX_GROWTH = 0.015
RAMP_FIXED_MIN = 0.60


@dataclass(frozen=True)
class Scenario:
    key: str
    name: str
    growth_mult: float = 1.0          # 수요 성장률 승수
    demand_shock: float = 0.0         # 총수요 추가 일괄 충격 (예: -0.4), 2027년부터
    shock_mode: str = "step"          # step: 2027년 급락 / gradual: 2027→2030 선형 확대
    share_cap: float = 0.70           # 고객별 이원화 수주 상한
    eua_mult: float = 1.0             # EU 탄소가격 배율
    cbam_share: float = 0.25          # 한국→EU 내재배출 과금 비중
    cbam_share_2030: float = 0.25     # 2030년 이후 과금 비중
    internal_carbon: bool = False     # 고객 내부 탄소가격(50kg 기준선) 정산
    internal_carbon_base: float = 50.0
    internal_carbon_from: int = 2030
    location_based: bool = False      # 위치기반 탄소발자국
    cap_2030: float | None = None     # 유럽 공급 탄소발자국 상한 (2030~2034)
    cap_2035: float | None = None     # (2035~)
    iaa_penalty: float = 0.0          # 한국산 유럽 공급 페널티 $/kWh
    iaa_from: int = 2030
    self_gen: tuple = ()              # ((공장, 저탄소 자가발전 비율), ...) 위치기반 인정분
    price_mult: float = 1.0           # 판매가격 수준 배율 (민감도용)
    subsidy_mult: float = 1.0         # 투자 보조금 배율 (민감도용)

    def with_(self, **kw):
        return replace(self, **kw)


SCENARIOS = {
    "base": Scenario("base", "1. 기준"),
    "high_carbon": Scenario("high_carbon", "2. 고탄소", eua_mult=1.5, cbam_share_2030=1.0, internal_carbon=True),
    "carbon_cap": Scenario("carbon_cap", "3. 탄소발자국 상한", location_based=True, cap_2030=65.0, cap_2035=60.0),
    "slow_demand": Scenario("slow_demand", "4. 수요 둔화", growth_mult=0.5),
    "iaa": Scenario("iaa", "5. 역내생산 요건", iaa_penalty=6.0),
}
# 질문 5(a) 시나리오 발생 확률 기본값 (근거 없는 임시값, 화면에서 수정)
DEFAULT_PROB = {"base": 0.25, "high_carbon": 0.25, "carbon_cap": 0.20, "slow_demand": 0.15, "iaa": 0.15}
