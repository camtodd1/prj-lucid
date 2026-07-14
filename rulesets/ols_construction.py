"""Ruleset-owned inputs and policy for conventional OLS construction.

The geometry engine remains in :mod:`guidelines.ols_guideline`.  This module
owns the regulatory decisions which must not leak between a selected design
standard and an independently selected baseline/comparison OLS ruleset.
It intentionally has no QGIS imports so its policy can be unit tested with
ordinary Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple


CAP168_RULESET_ID = "uk_caa_cap168_edition_13"
EASA_RULESET_ID = "easa_cs_adr_dsn_issue_7"
MOS139_RULESET_ID = "mos139_2019"
ANNEX14_CURRENT_RULESET_ID = "icao_annex14_vol1_current_ols"

ALIGNED_TRACK = "aligned"
OFFSET_TRACK = "offset"
CURVED_TRACK = "curved"
CURVED_OVER_15_TRACK = "curved_gt_15"
SUPPORTED_TRACK_TYPES = {
    ALIGNED_TRACK,
    OFFSET_TRACK,
    CURVED_TRACK,
    CURVED_OVER_15_TRACK,
}


@dataclass(frozen=True)
class OlsRunwayEndContext:
    """Ruleset-specific inputs for one landing/departure direction."""

    direction: str
    designator: str
    threshold_point: Any
    threshold_elevation_m: Optional[float]
    runway_end_elevation_m: Optional[float]
    approach_type: str
    classified_type: str
    clearway_length_m: float = 0.0
    stopway_length_m: float = 0.0
    tora_m: Optional[float] = None
    toda_m: Optional[float] = None
    asda_m: Optional[float] = None
    lda_m: Optional[float] = None
    approach_track_type: str = ALIGNED_TRACK
    approach_track_wkt: str = ""
    takeoff_track_type: str = ALIGNED_TRACK
    takeoff_track_wkt: str = ""

    @property
    def takeoff_track_changes_over_15_degrees(self) -> bool:
        return self.takeoff_track_type == CURVED_OVER_15_TRACK


@dataclass(frozen=True)
class OlsRunwayContext:
    """A runway normalised under the selected OLS ruleset."""

    runway_id: str
    original_index: int
    arc_number: int
    arc_letter: str
    width_m: float
    physical_length_m: float
    threshold_length_m: float
    primary_threshold_point: Any
    reciprocal_threshold_point: Any
    primary_physical_end_point: Any
    reciprocal_physical_end_point: Any
    strip_parameters: Mapping[str, Any]
    ends: Tuple[OlsRunwayEndContext, OlsRunwayEndContext]
    is_wide_runway: bool = False
    generation_data: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def end(self, direction: str) -> Optional[OlsRunwayEndContext]:
        normalized = str(direction or "").strip().lower()
        for end in self.ends:
            if end.direction == normalized:
                return end
        return None

    @property
    def governing_type(self) -> str:
        order = {"NI": 0, "NPA": 1, "PA_I": 2, "PA_II_III": 3}
        return max(self.ends, key=lambda item: order.get(item.classified_type, -1)).classified_type


@dataclass(frozen=True)
class OlsConstructionContext:
    """Complete, ruleset-specific conventional OLS construction input."""

    ruleset_id: str
    runways: Tuple[OlsRunwayContext, ...]
    arp_point: Any = None
    arp_elevation_m: Optional[float] = None
    reference_elevation_datum_m: Optional[float] = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def runway(self, original_index: int) -> Optional[OlsRunwayContext]:
        for runway in self.runways:
            if runway.original_index == original_index:
                return runway
        return None

    @property
    def main_runway(self) -> Optional[OlsRunwayContext]:
        """Return the longest physical runway, with a stable index tie-break."""

        if not self.runways:
            return None
        return max(
            self.runways,
            key=lambda runway: (runway.physical_length_m, -runway.original_index),
        )

    @property
    def lowest_threshold_elevation_m(self) -> Optional[float]:
        elevations = [
            end.threshold_elevation_m
            for runway in self.runways
            for end in runway.ends
            if end.threshold_elevation_m is not None
        ]
        return min(elevations) if elevations else None

    def generation_runways(self) -> list[dict]:
        return [dict(runway.generation_data) for runway in self.runways]


class ConventionalOlsConstructionPolicy:
    """Default adapter which preserves the established MOS-style contract."""

    key = "conventional"
    source_ready = True

    def validate(self, context: OlsConstructionContext) -> Tuple[str, ...]:
        errors = []
        if not context.runways:
            errors.append("At least one runway is required for OLS construction.")
        for runway in context.runways:
            if runway.physical_length_m <= 0:
                errors.append(f"{runway.runway_id}: physical runway length is required.")
            for end in runway.ends:
                if end.threshold_elevation_m is None:
                    errors.append(f"{runway.runway_id} {end.designator}: threshold elevation is required.")
                errors.extend(self._validate_track(runway, end, "approach"))
                errors.extend(self._validate_track(runway, end, "takeoff"))
        return tuple(errors)

    @staticmethod
    def _validate_track(
        runway: OlsRunwayContext,
        end: OlsRunwayEndContext,
        family: str,
    ) -> Sequence[str]:
        track_type = getattr(end, f"{family}_track_type")
        track_wkt = getattr(end, f"{family}_track_wkt")
        if track_type not in SUPPORTED_TRACK_TYPES:
            return (f"{runway.runway_id} {end.designator}: unknown {family} track type '{track_type}'.",)
        if track_type != ALIGNED_TRACK and not str(track_wkt or "").strip():
            return (
                f"{runway.runway_id} {end.designator}: {family} track geometry is required for {track_type} construction.",
            )
        return ()

    def ihs_plan(self, context: OlsConstructionContext, runway: OlsRunwayContext) -> Mapping[str, Any]:
        return {"shape": "strip_end_racetrack", "use_parameter_radius": True, "combine": "convex_hull"}

    def airport_wide_spec(self, profile, context: OlsConstructionContext) -> Mapping[str, Any]:
        governing = self._governing_runway(context)
        if governing is None:
            return {}
        type_order = {"NI": 0, "NPA": 1, "PA_I": 2, "PA_II_III": 3}
        governing_end = max(
            governing.ends,
            key=lambda item: type_order.get(item.classified_type, -1),
        )
        lookup_type = governing_end.approach_type or governing_end.classified_type
        ihs = profile.ols_parameters(governing.arc_number, lookup_type, "IHS")
        conical = profile.ols_parameters(governing.arc_number, lookup_type, "CONICAL")
        ohs = profile.ols_parameters(governing.arc_number, lookup_type, "OHS")
        ihs_height = profile.ihs_base_height()
        datum = context.reference_elevation_datum_m
        ihs_elevation = (
            float(datum) + float(ihs_height)
            if datum is not None and ihs_height is not None
            else None
        )
        ohs_spec = dict(ohs) if ohs else None
        if ohs_spec and datum is not None and ohs_spec.get("height_agl") is not None:
            ohs_spec["elevation_amsl"] = float(datum) + float(ohs_spec["height_agl"])
        return {
            "datum_name": "reference_elevation_datum",
            "datum_elevation_m": datum,
            "ihs_height_m": ihs_height,
            "ihs_elevation_amsl": ihs_elevation,
            "ihs_ref": (ihs or {}).get("ref"),
            "conical": dict(conical) if conical else None,
            "ohs": ohs_spec,
            "extend_conical_to_ohs": context.ruleset_id == MOS139_RULESET_ID,
            "governing_runway_id": governing.runway_id,
        }

    def parameters(
        self,
        profile,
        context: Optional[OlsConstructionContext],
        runway: Optional[OlsRunwayContext],
        end: Optional[OlsRunwayEndContext],
        arc_number: int,
        runway_type: Optional[str],
        surface_type: str,
    ):
        del context, runway, end
        return profile.ols_parameters(arc_number, runway_type, surface_type)

    @staticmethod
    def _governing_runway(context: OlsConstructionContext) -> Optional[OlsRunwayContext]:
        order = {"NI": 0, "NPA": 1, "PA_I": 2, "PA_II_III": 3}
        if not context.runways:
            return None
        return max(
            context.runways,
            key=lambda runway: (
                runway.arc_number,
                order.get(runway.governing_type, -1),
                runway.physical_length_m,
                -runway.original_index,
            ),
        )


class Mos139OlsConstructionPolicy(ConventionalOlsConstructionPolicy):
    """Named compatibility adapter for the locked MOS139 geometry path."""

    key = "mos139_compatibility"

    def validate(self, context: OlsConstructionContext) -> Tuple[str, ...]:
        errors = list(super().validate(context))
        if context.reference_elevation_datum_m is None:
            errors.append("MOS139 airport-wide OLS requires a reference elevation datum (RED).")
        return tuple(errors)


class EasaOlsConstructionPolicy(ConventionalOlsConstructionPolicy):
    """EASA J-1/J-2 construction decisions layered over shared geometry."""

    key = "easa_issue_7"

    def validate(self, context: OlsConstructionContext) -> Tuple[str, ...]:
        errors = list(super().validate(context))
        if context.reference_elevation_datum_m is None:
            errors.append("EASA airport-wide OLS requires a reference elevation datum.")
        return tuple(errors)

    def parameters(
        self,
        profile,
        context: Optional[OlsConstructionContext],
        runway: Optional[OlsRunwayContext],
        end: Optional[OlsRunwayEndContext],
        arc_number: int,
        runway_type: Optional[str],
        surface_type: str,
    ):
        params = super().parameters(profile, context, runway, end, arc_number, runway_type, surface_type)
        if not params:
            return params
        normalized = "".join(character for character in str(surface_type).upper() if character.isalnum())
        if normalized in {"APPROACH", "APPROACHSURFACE"}:
            return self._resolve_variable_approach(profile, context, end, params)
        if normalized not in {"TOCS", "TAKEOFFCLIMB", "TAKEOFFCLIMBSURFACE"}:
            return params
        resolved = dict(params)
        if end is not None:
            if end.clearway_length_m > 0:
                resolved["inner_edge_width"] = resolved.get(
                    "inner_edge_width_clearway", resolved.get("inner_edge_width")
                )
            if end.takeoff_track_changes_over_15_degrees:
                resolved["final_width"] = resolved.get("final_width_turning", resolved.get("final_width"))
            resolved["origin_station_from_pavement_end"] = max(
                float(resolved.get("origin_offset") or 0.0),
                end.clearway_length_m,
            )
        return resolved

    def _resolve_variable_approach(self, profile, context, end, params):
        sections = [dict(section) for section in params]
        if context is None or end is None or not any(section.get("variable_length") for section in sections):
            return sections
        airport_spec = self.airport_wide_spec(profile, context)
        horizontal_elevation = airport_spec.get("ihs_elevation_amsl")
        if horizontal_elevation is None or end.threshold_elevation_m is None:
            return sections
        total_length = max(
            (float(section.get("total_length")) for section in sections if section.get("total_length") is not None),
            default=sum(float(section.get("length") or 0.0) for section in sections),
        )
        elevation = float(end.threshold_elevation_m)
        consumed = 0.0
        for section in sections:
            slope = float(section.get("slope") or 0.0)
            length = float(section.get("length") or 0.0)
            if section.get("variable_length") and slope > 0:
                length = max(0.0, (float(horizontal_elevation) - elevation) / slope)
                section["length"] = length
                section["resolved_against"] = "inner_horizontal_surface"
            elif section.get("variable_length") and abs(slope) <= 1e-12:
                length = max(0.0, total_length - consumed)
                section["length"] = length
                section["resolved_against"] = "remaining_total_approach_length"
            consumed += length
            elevation += length * slope
        return sections

    def airport_wide_spec(self, profile, context: OlsConstructionContext) -> Mapping[str, Any]:
        spec = dict(super().airport_wide_spec(profile, context))
        spec["extend_conical_to_ohs"] = False
        if spec.get("ohs"):
            spec["ohs"] = {**spec["ohs"], "applicability": "guidance_only"}
        return spec


class Cap168OlsConstructionPolicy(ConventionalOlsConstructionPolicy):
    """CAP168 Chapter 4 policy using actual runway length and threshold datum."""

    key = "cap168_edition_13"

    def validate(self, context: OlsConstructionContext) -> Tuple[str, ...]:
        errors = list(super().validate(context))
        if context.lowest_threshold_elevation_m is None:
            errors.append("CAP168 requires an elevation for every runway threshold.")
        if context.main_runway is not None and context.main_runway.physical_length_m >= 1100 and context.arp_point is None:
            errors.append("CAP168 outer horizontal construction requires ARP coordinates.")
        return tuple(errors)

    def ihs_plan(self, context: OlsConstructionContext, runway: OlsRunwayContext) -> Mapping[str, Any]:
        from .cap168 import ols_surfaces

        main = context.main_runway
        if main is None:
            return {}
        if runway.original_index == main.original_index:
            if runway.physical_length_m >= 1800.0:
                return {
                    **ols_surfaces.IHS_PLAN_RULES["main_runway_at_least_1800_m"],
                    "combine": "convex_hull",
                }
            key = "main_runway_below_1800_m_default"
            if runway.governing_type == "NI" and runway.arc_number == 1:
                key = "main_runway_below_1800_m_ni_code_1"
            elif runway.governing_type == "NI" and runway.arc_number == 2:
                key = "main_runway_below_1800_m_ni_code_2"
            return {**ols_surfaces.IHS_PLAN_RULES[key], "combine": "convex_hull"}

        subsidiary = ols_surfaces.IHS_PLAN_RULES["subsidiary_runway_over_1800_m"]
        if runway.physical_length_m < 1800.0:
            return {"shape": "not_applicable", "ref": subsidiary["ref"]}
        if self._runway_proximity_m(main, runway) > float(subsidiary["proximity_trigger_m"]):
            return {"shape": "not_applicable", "ref": subsidiary["ref"]}
        return {**subsidiary, "shape": "strip_end_racetrack", "combine": "convex_hull"}

    def airport_wide_spec(self, profile, context: OlsConstructionContext) -> Mapping[str, Any]:
        from .cap168 import ols_surfaces

        del profile
        main = context.main_runway
        datum = context.lowest_threshold_elevation_m
        if main is None or datum is None:
            return {}
        height_extent = float(ols_surfaces.CONICAL_RULES["default_height_extent_above_ihs_m"])
        if main.governing_type == "NI" and main.arc_number == 1:
            height_extent = float(ols_surfaces.CONICAL_RULES["ni_code_1_height_extent_above_ihs_m"])
        elif main.governing_type == "NI" and main.arc_number == 2:
            height_extent = float(ols_surfaces.CONICAL_RULES["ni_code_2_height_extent_above_ihs_m"])
        conical = {
            "slope": float(ols_surfaces.CONICAL_RULES["slope"]),
            "height_extent_agl": height_extent,
            "ref": ols_surfaces.CONICAL_RULES["ref"],
        }
        ohs = None
        length = main.physical_length_m
        rules = ols_surfaces.OUTER_HORIZONTAL_RULES
        if length >= float(rules["minimum_main_runway_length_m"]):
            radius = (
                float(rules["radius_if_main_runway_at_least_1860_m"])
                if length >= 1860.0
                else float(rules["radius_if_main_runway_1100_to_below_1860_m"])
            )
            ohs = {
                "radius": radius,
                "height_agl": 150.0,
                "elevation_amsl": datum + 150.0,
                "ref": rules["ref"],
            }
        return {
            "datum_name": "lowest_runway_threshold",
            "datum_elevation_m": datum,
            "ihs_height_m": float(ols_surfaces.IHS_HEIGHT_RULE["height_m"]),
            "ihs_elevation_amsl": datum + float(ols_surfaces.IHS_HEIGHT_RULE["height_m"]),
            "ihs_ref": ols_surfaces.IHS_HEIGHT_RULE["ref"],
            "conical": conical,
            "ohs": ohs,
            "extend_conical_to_ohs": False,
            "governing_runway_id": main.runway_id,
        }

    def parameters(
        self,
        profile,
        context: Optional[OlsConstructionContext],
        runway: Optional[OlsRunwayContext],
        end: Optional[OlsRunwayEndContext],
        arc_number: int,
        runway_type: Optional[str],
        surface_type: str,
    ):
        from .cap168 import ols_surfaces

        del profile, context
        params = ols_surfaces.get_ols_params(arc_number, runway_type, surface_type)
        if not params or runway is None:
            return params
        normalized = "".join(character for character in str(surface_type).upper() if character.isalnum())
        if normalized in {"APPROACH", "APPROACHSURFACE"}:
            resolved_sections = [dict(section) for section in params]
            if runway.is_wide_runway and resolved_sections:
                strip_width = float((runway.strip_parameters or {}).get("overall_width") or 0.0)
                resolved_sections[0]["start_width"] = max(
                    strip_width,
                    float(resolved_sections[0].get("start_width") or 0.0),
                )
                resolved_sections[0]["wide_runway_rule_applied"] = True
            return resolved_sections
        if normalized in {"TOCS", "TAKEOFFCLIMB", "TAKEOFFCLIMBSURFACE"}:
            resolved = dict(params)
            if end is not None:
                if end.clearway_length_m > 0 and arc_number in {1, 2}:
                    resolved["inner_edge_width"] = resolved.get(
                        "clearway_inner_edge_width", resolved.get("inner_edge_width")
                    )
                if end.takeoff_track_changes_over_15_degrees:
                    resolved["final_width"] = resolved.get(
                        "heading_change_gt_15_final_width", resolved.get("final_width")
                    )
                resolved["origin_station_from_pavement_end"] = max(
                    float(resolved.get("origin_offset") or 0.0),
                    end.clearway_length_m,
                )
            if runway.is_wide_runway:
                strip_width = float((runway.strip_parameters or {}).get("overall_width") or 0.0)
                if strip_width > float(resolved.get("inner_edge_width") or 0.0):
                    resolved["inner_edge_width"] = strip_width
                    resolved["wide_runway_rule_applied"] = True
            return resolved
        if normalized in {"BALKEDLANDING", "BALKEDLANDINGSURFACE", "BAULKEDLANDING", "BAULKEDLANDINGSURFACE"}:
            resolved = dict(params)
            if resolved.get("start_dist_rule") == "60_m_beyond_lda" and end is not None and end.lda_m is not None:
                resolved["start_dist_from_thr"] = float(end.lda_m) + 60.0
                resolved["start_dist_rule"] = "resolved_from_lda"
            if runway.arc_letter == "F" and resolved.get("code_letter_f_width"):
                resolved["width"] = resolved["code_letter_f_width"]
            return resolved
        if normalized in {"INNERAPPROACH", "INNERAPPROACHSURFACE"}:
            resolved = dict(params)
            if runway.arc_letter == "F" and resolved.get("code_letter_f_width"):
                resolved["width"] = resolved["code_letter_f_width"]
            return resolved
        return params

    @staticmethod
    def _runway_proximity_m(first: OlsRunwayContext, second: OlsRunwayContext) -> float:
        distances = []
        for point_a in (first.primary_threshold_point, first.reciprocal_threshold_point):
            for point_b in (second.primary_threshold_point, second.reciprocal_threshold_point):
                try:
                    distances.append(float(point_a.distance(point_b)))
                except Exception:
                    continue
        return min(distances) if distances else float("inf")


class Annex14CurrentOlsConstructionPolicy(ConventionalOlsConstructionPolicy):
    """Current conventional Annex 14 OLS, separate from future OFS/OES."""

    key = "annex14_current_ols"

    def validate(self, context: OlsConstructionContext) -> Tuple[str, ...]:
        errors = list(super().validate(context))
        if context.reference_elevation_datum_m is None:
            errors.append(
                "Current Annex 14 airport-wide OLS requires an established inner-horizontal elevation datum."
            )
        for runway in context.runways:
            strip = runway.strip_parameters or {}
            if strip.get("overall_width") is None or strip.get("extension_length") is None:
                errors.append(
                    f"{runway.runway_id}: current Annex 14 runway-strip width and extension are required."
                )
        return tuple(errors)

    def parameters(
        self,
        profile,
        context: Optional[OlsConstructionContext],
        runway: Optional[OlsRunwayContext],
        end: Optional[OlsRunwayEndContext],
        arc_number: int,
        runway_type: Optional[str],
        surface_type: str,
    ):
        params = super().parameters(
            profile,
            context,
            runway,
            end,
            arc_number,
            runway_type,
            surface_type,
        )
        if not params:
            return params
        normalized = "".join(
            character for character in str(surface_type).upper() if character.isalnum()
        )
        if normalized in {"TOCS", "TAKEOFFCLIMB", "TAKEOFFCLIMBSURFACE"}:
            resolved = dict(params)
            if end is not None:
                resolved["origin_station_from_pavement_end"] = max(
                    float(resolved.get("origin_offset") or 0.0),
                    end.clearway_length_m,
                )
                if end.takeoff_track_changes_over_15_degrees:
                    resolved["final_width"] = resolved.get(
                        "heading_change_gt_15_final_width",
                        resolved.get("final_width"),
                    )
            return resolved
        if normalized in {
            "INNERAPPROACH",
            "INNERAPPROACHSURFACE",
            "BALKEDLANDING",
            "BALKEDLANDINGSURFACE",
            "BAULKEDLANDING",
            "BAULKEDLANDINGSURFACE",
        }:
            resolved = dict(params)
            if runway is not None and runway.arc_letter == "F" and resolved.get(
                "code_letter_f_width"
            ):
                resolved["width"] = resolved["code_letter_f_width"]
            return resolved
        return params


class SourceGatedOlsConstructionPolicy(ConventionalOlsConstructionPolicy):
    """Policy used where an authoritative conventional OLS table is absent."""

    source_ready = False

    def __init__(self, reason: str):
        self.reason = reason

    def validate(self, context: OlsConstructionContext) -> Tuple[str, ...]:
        del context
        return (self.reason,)

    def airport_wide_spec(self, profile, context: OlsConstructionContext) -> Mapping[str, Any]:
        del profile, context
        return {}


MOS139_OLS_CONSTRUCTION_POLICY = Mos139OlsConstructionPolicy()
EASA_OLS_CONSTRUCTION_POLICY = EasaOlsConstructionPolicy()
CAP168_OLS_CONSTRUCTION_POLICY = Cap168OlsConstructionPolicy()
ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY = Annex14CurrentOlsConstructionPolicy()


def policy_for_ruleset(ruleset_id: str) -> ConventionalOlsConstructionPolicy:
    return {
        MOS139_RULESET_ID: MOS139_OLS_CONSTRUCTION_POLICY,
        EASA_RULESET_ID: EASA_OLS_CONSTRUCTION_POLICY,
        CAP168_RULESET_ID: CAP168_OLS_CONSTRUCTION_POLICY,
        ANNEX14_CURRENT_RULESET_ID: ANNEX14_CURRENT_OLS_CONSTRUCTION_POLICY,
    }.get(str(ruleset_id or ""), ConventionalOlsConstructionPolicy())


__all__ = [
    "ALIGNED_TRACK",
    "OFFSET_TRACK",
    "CURVED_TRACK",
    "CURVED_OVER_15_TRACK",
    "SUPPORTED_TRACK_TYPES",
    "OlsRunwayEndContext",
    "OlsRunwayContext",
    "OlsConstructionContext",
    "ConventionalOlsConstructionPolicy",
    "Mos139OlsConstructionPolicy",
    "EasaOlsConstructionPolicy",
    "Cap168OlsConstructionPolicy",
    "Annex14CurrentOlsConstructionPolicy",
    "SourceGatedOlsConstructionPolicy",
    "policy_for_ruleset",
]
