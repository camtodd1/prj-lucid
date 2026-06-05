"""CASA Part 139 MOS 2019 profile metadata."""

from typing import Optional

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
