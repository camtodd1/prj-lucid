"""CASA Part 139 MOS 2019 profile metadata."""

from typing import List, Optional, Tuple

from ..base import RulesetProfile, capability_map

try:
    from ...dimensions import ols_dimensions
except ImportError:
    from dimensions import ols_dimensions  # type: ignore


class Mos139RulesetProfile(RulesetProfile):
    """Compatibility adapter around the existing MOS139 dimension helpers."""

    def classify_runway_type(self, runway_type: Optional[str]) -> str:
        return ols_dimensions.get_runway_type_abbr(runway_type)

    def precision_type_codes(self) -> set[str]:
        return set(ols_dimensions.PRECISION_APPROACH_TYPES)

    def physical_refs(self) -> dict:
        return ols_dimensions.get_physical_refs()

    def strip_parameters(self, arc_num: int, type_abbr: str, runway_width: Optional[float]):
        return ols_dimensions.get_strip_params(arc_num, type_abbr, runway_width)

    def resa_parameters(self, arc_num: int, type1_abbr: str, type2_abbr: str):
        return ols_dimensions.get_resa_params(arc_num, type1_abbr, type2_abbr)

    def ihs_base_height(self):
        return ols_dimensions.get_ihs_base_height()

    def ols_parameters(self, arc_num: int, runway_type: Optional[str], surface_type: str):
        return ols_dimensions.get_ols_params(arc_num, runway_type, surface_type)

    def taxiway_separation_offset(self, arc_num: int, arc_let: Optional[str], runway_type: Optional[str]):
        return ols_dimensions.get_taxiway_separation_offset(arc_num, arc_let, runway_type)

    def threshold_marking_params(self, runway_width: float) -> Optional[Tuple[int, float]]:
        table = {
            18.0: (4, 1.5),
            23.0: (6, 1.5),
            30.0: (8, 1.5),
            45.0: (12, 1.7),
            60.0: (16, 1.7),
        }
        for width_m, params in table.items():
            if abs(float(runway_width) - width_m) <= 0.01:
                return params
        return None

    def centreline_marking_width(self, arc_num: int, type_primary: str, type_reciprocal: str) -> float:
        widths = []
        for runway_type in (type_primary, type_reciprocal):
            type_abbr = self.classify_runway_type(runway_type)
            if type_abbr == "PA_II_III":
                widths.append(0.9)
            elif type_abbr == "PA_I" or (type_abbr == "NPA" and arc_num in (3, 4)):
                widths.append(0.45)
            else:
                widths.append(0.3)
        return max(widths) if widths else 0.3

    def aiming_point_rule(
        self, runway_width: float, lda_m: float, runway_type: str
    ) -> Optional[Tuple[float, float, float, float, str]]:
        type_abbr = self.classify_runway_type(runway_type)
        if type_abbr in {"PA_I", "PA_II_III"}:
            if lda_m < 800.0:
                return 150.0, 30.0, 4.0, 6.0, "MOS 8.22(3)"
            if lda_m < 1200.0:
                return 250.0, 30.0, 6.0, 9.0, "MOS 8.22(3)"
            if lda_m < 2400.0:
                return 300.0, 45.0, 9.0, 23.0, "MOS 8.22(3)"
            return 400.0, 45.0, 9.0, 23.0, "MOS 8.22(3)"

        if abs(runway_width - 30.0) <= 0.01:
            return 300.0, 45.0, 6.0, 17.0, "MOS 8.22(8)"
        if runway_width >= 45.0:
            return 300.0, 45.0, 9.0, 23.0, "MOS 8.22(8)"
        return None

    def touchdown_zone_offsets(self, lda_m: float) -> List[float]:
        if lda_m < 900.0:
            return [300.0]
        if lda_m < 1200.0:
            return [150.0, 450.0]
        if lda_m < 1500.0:
            return [150.0, 300.0, 450.0, 600.0]
        if lda_m < 2400.0:
            return [150.0, 300.0, 450.0, 600.0, 750.0]
        return [150.0, 300.0, 450.0, 600.0, 750.0, 900.0]

    def runway_holding_position_rule(
        self, runway_code_num: int, runway_type: str
    ) -> Optional[Tuple[float, str]]:
        type_abbr = self.classify_runway_type(runway_type)
        table = {
            1: {"NI": 30.0, "NPA": 40.0, "PA_I": 60.0, "PA_II_III": None},
            2: {"NI": 40.0, "NPA": 40.0, "PA_I": 60.0, "PA_II_III": None},
            3: {"NI": 75.0, "NPA": 75.0, "PA_I": 90.0, "PA_II_III": 90.0},
            4: {"NI": 75.0, "NPA": 75.0, "PA_I": 90.0, "PA_II_III": 90.0},
        }
        if runway_code_num not in table or type_abbr not in table[runway_code_num]:
            return None
        distance = table[runway_code_num][type_abbr]
        if distance is None:
            return None
        return distance, "MOS 8.39(7); Table 6.56(1)"


MOS139_PROFILE = Mos139RulesetProfile(
    id="mos139_2019",
    display_name="MOS139 (current)",
    edition="Part 139 MOS 2019",
    status="stable",
    description="Current CASA Part 139 MOS behaviour implemented by the plugin.",
    aliases=("MOS139", "mos139", "CASA_MOS139", "casa_part139_mos_2019"),
    capabilities=capability_map(
        {
            "classification.runway_type_mapping": "supported",
            "physical.pavement": "supported",
            "physical.shoulder": "supported",
            "physical.strip": "supported",
            "physical.resa": "supported",
            "physical.clearway": "supported",
            "physical.stopway": "partial",
            "physical.taxiway_separation": "partial",
            "ols.airport_wide": "supported",
            "ols.runway_approach": "supported",
            "ols.takeoff_climb": "supported",
            "ols.ofz": "supported",
            "ols.controlling_lower_envelope": "experimental",
            "markings.runway": "supported",
            "lighting.runway": "supported",
            "lighting.approach": "supported",
            "declared_distances.calculated": "supported",
        }
    ),
)
