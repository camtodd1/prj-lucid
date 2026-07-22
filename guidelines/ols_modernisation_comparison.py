# -*- coding: utf-8 -*-
"""Derived comparison products for current and modernised OLS envelopes."""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from qgis.PyQt.QtCore import QVariant  # type: ignore
from qgis.core import (  # type: ignore
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsPointXY,
    QgsRectangle,
    QgsWkbTypes,
)

from .controlling_ols_engine import (
    CONICAL_CONICAL_SMOOTHING_MAX_EQUALITY_RESIDUAL_M,
    ControllingOlsCandidate,
    PlanarControllingOlsEngine,
)

try:
    from ..core.run_log import QgsMessageLog
except ImportError:
    from core.run_log import QgsMessageLog  # type: ignore

PLUGIN_TAG = "SafeguardingBuilder"
COMPARISON_TOLERANCE_M = 0.01
COMPARISON_MIN_AREA_M2 = 0.01
COMPARISON_NO_OVERLAY_COVERAGE_TOLERANCE_M = 0.5
COMPARISON_NO_OVERLAY_MIN_AREA_M2 = 5.0
COMPARISON_NO_OVERLAY_GRID_M = 0.001
COMPARISON_DISSOLVE_GRID_M = 0.000001
COMPARISON_DISSOLVE_MAX_RELATIVE_AREA_CHANGE = 1e-9
COMPARISON_RECOVERY_SLIVER_MAX_EFFECTIVE_WIDTH_M = 0.10
COMPARISON_RECOVERY_SLIVER_MIN_SHARED_BOUNDARY_FRACTION = 0.2
COMPARISON_RECOVERY_SLIVER_MIN_SHARED_BOUNDARY_M = 1.0
COMPARISON_RECOVERY_SLIVER_DOMINANT_CONTACT_RATIO = 1.5
COMPARISON_SPIKE_ANGLE_DEGREES = 12.0
COMPARISON_SPIKE_DETOUR_RATIO = 1.8
COMPARISON_SPIKE_BASE_MAX_M = 175.0
COMPARISON_SPIKE_HEIGHT_MIN_M = 25.0
COMPARISON_SEVERE_SPIKE_DETOUR_RATIO = 8.0
COMPARISON_SEVERE_SPIKE_ANGLE_DEGREES = 15.0
COMPARISON_COLLINEAR_BACKTRACK_ANGLE_DEGREES = 0.1
COMPARISON_FINAL_BACKTRACK_MAX_AREA_CHANGE_M2 = COMPARISON_MIN_AREA_M2
COMPARISON_SPIKE_MAX_AREA_CHANGE_RATIO = 0.01
COMPARISON_SPIKE_MAX_AREA_CHANGE_M2 = 25.0
COMPARISON_DELTA_DECIMALS = 3
COMPARISON_CONTOUR_INTERVAL_M = 1.0
COMPARISON_PRIMARY_CONTOUR_INTERVAL_M = 5.0
COMPARISON_CONTOUR_MIN_LENGTH_M = 0.01
COMPARISON_CONTOUR_CLIP_TOLERANCE_M = 0.01
COMPARISON_CURVED_CONTOUR_MIN_LENGTH_M = 1.0
COMPARISON_CURVED_CONTOUR_MAX_RESIDUAL_M = 0.05
COMPARISON_CURVED_CONTOUR_OUTPUT_SPACING_M = 5.0
CONVENTIONAL_OLS_RULESET_IDS = frozenset({
    "mos139_2019",
    "uk_caa_cap168_edition_13",
    "easa_cs_adr_dsn_issue_7",
    "icao_annex14_vol1_current_ols",
})

ComparisonPart = Tuple[
    ControllingOlsCandidate,
    ControllingOlsCandidate,
    QgsGeometry,
]


@dataclass(frozen=True)
class ComparisonFinalizationResult:
    """Explicit publishable comparison output and its finalization evidence."""

    gain: Tuple[ComparisonPart, ...]
    loss: Tuple[ComparisonPart, ...]
    no_change: Tuple[ComparisonPart, ...]
    transitions: Tuple[ComparisonPart, ...]
    diagnostics: Dict[str, object]
    recovery: Dict[str, object]
    invariants: Dict[str, object]

    @property
    def parts(self) -> Dict[str, List[ComparisonPart]]:
        """Return the legacy mutable container expected by layer writers."""
        return {
            "gain": list(self.gain),
            "loss": list(self.loss),
            "no_change": list(self.no_change),
            "transition": list(self.transitions),
        }


class OlsEnvelopeComparisonEngine:
    """Compare two already-solved lower envelopes over their common domain."""

    def __init__(
        self,
        baseline_engine: PlanarControllingOlsEngine,
        future_engine: PlanarControllingOlsEngine,
        tolerance_m: float = COMPARISON_TOLERANCE_M,
    ):
        self.baseline_engine = baseline_engine
        self.future_engine = future_engine
        self.tolerance_m = max(0.0, float(tolerance_m))
        self._comparison_diagnostics: Dict[str, float] = {}
        self._comparison_invariant_report: Dict[str, object] = {}
        self._recovered_sliver_geometries: List[QgsGeometry] = []
        self._pair_domain_cache: Dict[Tuple[int, int], QgsGeometry] = {}
        self._region_union_cache: Dict[Tuple[int, ...], Optional[QgsGeometry]] = {}
        self._common_domain_cache: Dict[
            Tuple[Tuple[int, ...], Tuple[int, ...]],
            Optional[QgsGeometry],
        ] = {}
        self._delta_range_cache: Dict[
            Tuple[int, int, int, Optional[str]],
            Tuple[QgsGeometry, Tuple[Optional[float], Optional[float], Optional[float]]],
        ] = {}

    def comparison_diagnostics(self) -> Dict[str, object]:
        """Return structured attribution for approximation and recovery operations."""
        stats = self._comparison_diagnostics
        return {
            "unresolved_comparisons": int(stats.get("unresolved_comparisons", 0.0)),
            "unresolved_sign_area_m2": stats.get("unresolved_sign_area_m2", 0.0),
            "bounded_approximations": {
                "fallback_lower_region_calls": int(stats.get("fallback_lower_region_calls", 0.0)),
                "sampled_whole_overlap_calls": int(stats.get("sampled_whole_overlap_calls", 0.0)),
                "vertical_error_bound_m": None,
            },
            "exceptional_recovery": {
                "common_domain_gap_parts": int(stats.get("common_domain_gap_parts", 0.0)),
                "common_domain_gap_area_m2": stats.get("common_domain_gap_area_m2", 0.0),
                "final_remainder_parts": int(stats.get("final_remainder_parts", 0.0)),
                "final_remainder_area_m2": stats.get("final_remainder_area_m2", 0.0),
            },
            "local_recovery_normalisation": {
                "reattached_parts": int(
                    stats.get("recovered_sliver_reattached_parts", 0.0)
                ),
                "reattached_area_m2": stats.get(
                    "recovered_sliver_reattached_area_m2",
                    0.0,
                ),
                "reclassified_parts": int(
                    stats.get("recovered_sliver_reclassified_parts", 0.0)
                ),
                "merged_no_change_slivers": int(
                    stats.get("merged_no_change_slivers", 0.0)
                ),
                "suppressed_no_change_slivers": int(
                    stats.get("suppressed_no_change_slivers", 0.0)
                ),
                "maximum_effective_width_m": (
                    COMPARISON_RECOVERY_SLIVER_MAX_EFFECTIVE_WIDTH_M
                ),
            },
            "invariants": dict(self._comparison_invariant_report),
        }

    def comparison_invariants(self) -> Dict[str, object]:
        """Return the non-mutating audit of the published comparison partition."""
        return dict(self._comparison_invariant_report)

    def comparison_parts(
        self,
    ) -> Dict[str, List[Tuple[ControllingOlsCandidate, ControllingOlsCandidate, QgsGeometry]]]:
        """Compatibility wrapper returning only finalized comparison parts."""
        return self.finalize_comparison().parts

    def finalize_comparison(self) -> ComparisonFinalizationResult:
        """Return publishable comparison parts with diagnostics and invariant evidence."""
        self._comparison_diagnostics = {}
        self._comparison_invariant_report = {}
        self._recovered_sliver_geometries = []
        self._pair_domain_cache = {}
        self._region_union_cache = {}
        self._common_domain_cache = {}
        self._delta_range_cache = {}
        baseline_regions = self.baseline_engine._controlling_region_geometries()
        future_regions = self.future_engine._controlling_region_geometries()
        strict_conventional = self._strict_conventional_partition_enabled()
        result = self._raw_comparison_parts(
            baseline_regions,
            future_regions,
            clean_spikes=not strict_conventional,
        )
        self._finalize_comparison_partition(
            result,
            baseline_regions,
            future_regions,
            strict_conventional=strict_conventional,
        )
        self._comparison_invariant_report = self._audit_comparison_invariants(
            result,
            baseline_regions,
            future_regions,
        )
        diagnostics = self.comparison_diagnostics()
        recovery = diagnostics["exceptional_recovery"]
        invariants = diagnostics["invariants"]
        QgsMessageLog.logMessage(
            "[diagnostics] OLS comparison: "
            f"invariants={'pass' if invariants.get('passed') else 'fail'}, "
            f"unresolved={diagnostics['unresolved_comparisons']}, "
            f"fallbacks={diagnostics['bounded_approximations']['fallback_lower_region_calls']}, "
            f"recovery_parts={int(recovery['common_domain_gap_parts']) + int(recovery['final_remainder_parts'])}, "
            f"recovery_area_m2={float(recovery['common_domain_gap_area_m2']) + float(recovery['final_remainder_area_m2']):.6f}.",
            PLUGIN_TAG,
            Qgis.Info,
        )
        return ComparisonFinalizationResult(
            gain=tuple(result["gain"]),
            loss=tuple(result["loss"]),
            no_change=tuple(result["no_change"]),
            transitions=tuple(result["transition"]),
            diagnostics=diagnostics,
            recovery={
                "exceptional": dict(diagnostics["exceptional_recovery"]),
                "local_normalisation": dict(
                    diagnostics["local_recovery_normalisation"]
                ),
            },
            invariants=dict(invariants),
        )

    def _finalize_comparison_partition(
        self,
        result: Dict[str, List[ComparisonPart]],
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        strict_conventional: bool,
    ) -> None:
        """Finalize one partition; no caller may mutate geometry after this pass."""
        if not strict_conventional:
            self._finalise_comparison_parts(result)

        # Recover pair-attributed coverage once after controller-aware cleanup,
        # then normalize the complete raw/recovered partition once. The final
        # remainder pass only restores any area trimmed by normalization.
        self._append_common_domain_gap_parts(result, baseline_regions, future_regions)
        if not strict_conventional:
            self._normalize_raw_classified_parts(result)
        self._append_final_common_domain_remainders(result, baseline_regions, future_regions)
        self._reattach_tracked_recovered_sliver_parts(result)
        common_domain = self._common_domain(baseline_regions, future_regions)
        common_area = common_domain.area() if self._has_area(common_domain) else 0.0
        self._normalize_numerical_no_change_slivers(
            result,
            area_tolerance_m2=max(COMPARISON_MIN_AREA_M2, common_area * 1e-9),
        )

        # These are the only final destructive polygon stages. Each invariant
        # is enforced once, in dependency order, before transitions are derived.
        self._enforce_final_height_signs(result)
        self._partition_classified_parts(result)
        self._remove_final_boundary_backtracks(result)
        self._dissolve_congruous_classified_parts(result)
        self._derive_final_transition_parts(result)

    def _raw_comparison_parts(
        self,
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        clean_spikes: bool,
    ) -> Dict[str, List[ComparisonPart]]:
        """Solve controller-pair overlaps before any finalization or recovery."""
        result: Dict[str, List[ComparisonPart]] = {
            "gain": [],
            "loss": [],
            "no_change": [],
            "transition": [],
        }
        for baseline_candidate, baseline_region in baseline_regions:
            for future_candidate, future_region in future_regions:
                overlap = self._pair_domain(
                    baseline_region,
                    future_region,
                )
                if not self._has_area(overlap):
                    continue
                self._append_classified_overlap(
                    result,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                    clean_spikes=clean_spikes,
                )
        return result

    def _pair_domain(
        self,
        baseline_region: QgsGeometry,
        future_region: QgsGeometry,
    ) -> QgsGeometry:
        """Return one cached controller-region overlap for this finalization run."""
        key = (id(baseline_region), id(future_region))
        cached = self._pair_domain_cache.get(key)
        if cached is not None:
            return cached
        if not self._bounding_boxes_intersect(baseline_region, future_region):
            overlap = QgsGeometry()
        else:
            overlap = self._safe_intersection(baseline_region, future_region)
            if overlap is None:
                overlap = QgsGeometry()
        self._pair_domain_cache[key] = overlap
        return overlap

    def _region_union(
        self,
        regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> Optional[QgsGeometry]:
        """Return a cached union for an unchanged controlling-region sequence."""
        key = tuple(id(geometry) for _candidate, geometry in regions)
        if key not in self._region_union_cache:
            self._region_union_cache[key] = self._union_geometries(
                [geometry for _candidate, geometry in regions]
            )
        return self._region_union_cache[key]

    def _common_domain(
        self,
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> Optional[QgsGeometry]:
        """Return the cached common domain for the current finalization run."""
        baseline_key = tuple(id(geometry) for _candidate, geometry in baseline_regions)
        future_key = tuple(id(geometry) for _candidate, geometry in future_regions)
        key = (baseline_key, future_key)
        if key not in self._common_domain_cache:
            baseline_union = self._region_union(baseline_regions)
            future_union = self._region_union(future_regions)
            self._common_domain_cache[key] = (
                self._safe_intersection(baseline_union, future_union)
                if baseline_union is not None and future_union is not None
                else None
            )
        return self._common_domain_cache[key]

    def _derive_final_transition_parts(
        self,
        result: Dict[str, List[ComparisonPart]],
    ) -> None:
        """Derive verified transitions once from finalized gain/loss adjacency."""
        result["transition"] = [
            (baseline, future, geometry)
            for baseline, future, geometry, _delta, _contour_class, _sequence
            in self.zero_change_contour_parts(result)
        ]

    def _audit_comparison_invariants(
        self,
        result,
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> Dict[str, object]:
        """Measure final partition guarantees without repairing or reclassifying it."""
        common_domain = self._common_domain(baseline_regions, future_regions)
        class_unions = {
            change: self._union_geometries([
                geometry
                for _baseline, _future, geometry in result.get(change, [])
                if geometry is not None and not geometry.isEmpty()
            ])
            for change in ("gain", "loss", "no_change")
        }
        classified_geometries = [
            geometry
            for change in ("gain", "loss", "no_change")
            for _baseline, _future, geometry in result.get(change, [])
            if geometry is not None and not geometry.isEmpty()
        ]
        classified_union = self._union_geometries(classified_geometries)
        common_area = common_domain.area() if self._has_area(common_domain) else 0.0
        area_tolerance = max(COMPARISON_MIN_AREA_M2, common_area * 1e-9)
        unclassified = (
            self._safe_difference(common_domain, classified_union)
            if common_domain is not None and classified_union is not None
            else common_domain
        )
        outside = (
            self._safe_difference(classified_union, common_domain)
            if classified_union is not None and common_domain is not None
            else classified_union
        )

        class_overlap_area = 0.0
        for first, second in (("gain", "loss"), ("gain", "no_change"), ("loss", "no_change")):
            first_union = class_unions[first]
            second_union = class_unions[second]
            if first_union is None or second_union is None:
                continue
            overlap = self._safe_intersection(first_union, second_union)
            if overlap is not None:
                class_overlap_area += max(0.0, overlap.area())

        invalid_parts = 0
        empty_parts = 0
        sign_violation_parts = 0
        sign_violation_area = 0.0
        for change in ("gain", "loss", "no_change"):
            for baseline, future, geometry in result.get(change, []):
                if geometry is None or geometry.isEmpty():
                    empty_parts += 1
                    continue
                try:
                    if not geometry.isGeosValid():
                        invalid_parts += 1
                except Exception:
                    invalid_parts += 1
                delta_min, delta_max, delta_sample = self.delta_range(
                    geometry,
                    baseline,
                    future,
                    change,
                )
                violation = delta_min is None or delta_max is None or delta_sample is None
                if change == "gain" and delta_min is not None:
                    violation = delta_min < -self.tolerance_m
                elif change == "loss" and delta_max is not None:
                    violation = delta_max > self.tolerance_m
                elif change == "no_change" and delta_min is not None and delta_max is not None:
                    violation = (
                        abs(delta_min) > self.tolerance_m
                        or abs(delta_max) > self.tolerance_m
                    )
                if violation:
                    sign_violation_parts += 1
                    sign_violation_area += max(0.0, geometry.area())

        transition_geometries = [
            geometry
            for _baseline, _future, geometry in result.get("transition", [])
            if geometry is not None and not geometry.isEmpty()
        ]
        try:
            transition_union = (
                QgsGeometry.unaryUnion(transition_geometries)
                if transition_geometries
                else None
            )
        except Exception:
            transition_union = (
                QgsGeometry(transition_geometries[0])
                if transition_geometries
                else None
            )
        gain_union = class_unions["gain"]
        loss_union = class_unions["loss"]
        shared_boundary = None
        if gain_union is not None and loss_union is not None:
            try:
                gain_boundary = gain_union.convertToType(
                    Qgis.GeometryType.Line,
                    True,
                )
                loss_boundary = loss_union.convertToType(
                    Qgis.GeometryType.Line,
                    True,
                )
                shared_boundary = gain_boundary.intersection(loss_boundary)
            except Exception:
                shared_boundary = None
        transition_outside_boundary_length = 0.0
        if transition_union is not None and not transition_union.isEmpty():
            if shared_boundary is None or shared_boundary.isEmpty():
                transition_outside_boundary_length = max(0.0, transition_union.length())
            else:
                try:
                    boundary_buffer = shared_boundary.buffer(
                        max(COMPARISON_CONTOUR_CLIP_TOLERANCE_M, self.tolerance_m),
                        4,
                    )
                    transition_outside_boundary_length = max(
                        0.0,
                        transition_union.difference(boundary_buffer).length(),
                    )
                except Exception:
                    transition_outside_boundary_length = max(0.0, transition_union.length())

        unclassified_area = unclassified.area() if self._has_area(unclassified) else 0.0
        outside_area = outside.area() if self._has_area(outside) else 0.0
        passed = (
            unclassified_area <= area_tolerance
            and outside_area <= area_tolerance
            and class_overlap_area <= area_tolerance
            and invalid_parts == 0
            and empty_parts == 0
            and sign_violation_parts == 0
            and transition_outside_boundary_length <= COMPARISON_CONTOUR_CLIP_TOLERANCE_M
        )
        return {
            "passed": passed,
            "area_tolerance_m2": area_tolerance,
            "coverage": {
                "common_domain_area_m2": common_area,
                "classified_union_area_m2": (
                    classified_union.area() if self._has_area(classified_union) else 0.0
                ),
                "unclassified_area_m2": unclassified_area,
                "outside_common_domain_area_m2": outside_area,
            },
            "exclusivity": {"class_overlap_area_m2": class_overlap_area},
            "height_sign": {
                "violation_parts": sign_violation_parts,
                "violation_area_m2": sign_violation_area,
            },
            "geometry": {
                "invalid_parts": invalid_parts,
                "empty_parts": empty_parts,
            },
            "transitions": {
                "parts": len(transition_geometries),
                "outside_gain_loss_boundary_length_m": transition_outside_boundary_length,
            },
        }

    def _strict_conventional_partition_enabled(self) -> bool:
        """Preserve exact controller-pair coverage for current-OLS comparisons."""
        ruleset_ids = {
            str(getattr(self.baseline_engine, "ruleset_id", "") or ""),
            str(getattr(self.future_engine, "ruleset_id", "") or ""),
        }
        return (
            "icao_annex14_vol1_current_ols" in ruleset_ids
            and ruleset_ids.issubset(CONVENTIONAL_OLS_RULESET_IDS)
        )

    def _append_classified_overlap(
        self,
        result,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
        overlap: QgsGeometry,
        clean_spikes: bool = True,
    ) -> None:
        """Classify one controller-pair overlap without losing mixed fallback areas."""
        if not self._has_area(overlap):
            return
        if self._append_no_change_if_equal(
            result["no_change"],
            baseline_candidate,
            future_candidate,
            overlap,
            clean_spikes=clean_spikes,
        ):
            return

        pair_engine = PlanarControllingOlsEngine(
            [baseline_candidate, future_candidate],
            tie_tolerance_m=0.0,
        )
        affine_regions = self._affine_change_regions(
            pair_engine,
            baseline_candidate,
            future_candidate,
            overlap,
        )
        if affine_regions is not None:
            gain_geometry, loss_geometry, no_change_geometry = affine_regions
            self._append_parts(
                result["gain"], baseline_candidate, future_candidate, gain_geometry, "gain", clean_spikes
            )
            self._append_parts(
                result["loss"], baseline_candidate, future_candidate, loss_geometry, "loss", clean_spikes
            )
            self._append_parts(
                result["no_change"],
                baseline_candidate,
                future_candidate,
                no_change_geometry,
                "no_change",
                clean_spikes,
            )
            return

        # A higher future surface is a gain, so the baseline is the lower
        # candidate on the gain side of the equality boundary.
        try:
            baseline_lower = pair_engine._candidate_lower_region(
                baseline_candidate,
                future_candidate,
                overlap,
            )
        except Exception:
            baseline_lower = None
        if baseline_lower is None:
            baseline_lower = self._fallback_lower_region(
                pair_engine,
                baseline_candidate,
                future_candidate,
                overlap,
            )
        if baseline_lower is None:
            self._append_sampled_whole_overlap(
                result,
                baseline_candidate,
                future_candidate,
                overlap,
                clean_spikes=clean_spikes,
            )
            return

        if baseline_lower.isEmpty():
            future_lower = QgsGeometry(overlap)
        else:
            baseline_lower = self._safe_intersection(baseline_lower, overlap)
            if baseline_lower is None:
                self._append_sampled_whole_overlap(
                    result,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                    clean_spikes=clean_spikes,
                )
                return
            future_lower = self._safe_difference(overlap, baseline_lower)
            if future_lower is None:
                self._append_sampled_whole_overlap(
                    result,
                    baseline_candidate,
                    future_candidate,
                    overlap,
                    clean_spikes=clean_spikes,
                )
                return

        self._append_parts(
            result["gain"], baseline_candidate, future_candidate, baseline_lower, "gain", clean_spikes
        )
        self._append_parts(
            result["loss"], baseline_candidate, future_candidate, future_lower, "loss", clean_spikes
        )
    def _affine_change_regions(
        self,
        pair_engine: PlanarControllingOlsEngine,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        overlap: QgsGeometry,
    ) -> Optional[Tuple[QgsGeometry, QgsGeometry, QgsGeometry]]:
        """Split a mixed affine comparison at equality without creating a tolerance strip."""
        baseline_plane = self._candidate_affine_coefficients(baseline)
        future_plane = self._candidate_affine_coefficients(future)
        if baseline_plane is None or future_plane is None:
            return None
        delta_min, delta_max, _delta_sample = self.delta_range(overlap, baseline, future)
        if delta_min is None or delta_max is None:
            return None
        if delta_min >= -self.tolerance_m and delta_max <= self.tolerance_m:
            return QgsGeometry(), QgsGeometry(), QgsGeometry(overlap)
        if delta_min >= 0.0:
            return QgsGeometry(overlap), QgsGeometry(), QgsGeometry()
        if delta_max <= 0.0:
            return QgsGeometry(), QgsGeometry(overlap), QgsGeometry()

        coefficients = tuple(
            future_plane[index] - baseline_plane[index]
            for index in range(3)
        )
        threshold = self._affine_change_contour(overlap, coefficients, 0.0)
        if threshold is None or threshold.isEmpty():
            return None
        try:
            split_parts = pair_engine._split_overlap_by_transition_curve(overlap, threshold)
        except Exception:
            return None
        if len(split_parts) <= 1:
            return None

        classified = {"gain": [], "loss": [], "no_change": []}
        for part in split_parts:
            point = part.pointOnSurface().asPoint()
            delta = self._delta_at_point(QgsPointXY(point.x(), point.y()), baseline, future)
            if delta is None:
                continue
            change = "gain" if delta > 0.0 else "loss" if delta < 0.0 else None
            if change is None:
                continue
            classified[change].append(part)
        gain_geometry = self._union_geometries(classified["gain"])
        loss_geometry = self._union_geometries(classified["loss"])
        no_change_geometry = self._union_geometries(classified["no_change"])
        gain = gain_geometry if gain_geometry is not None else QgsGeometry()
        loss = loss_geometry if loss_geometry is not None else QgsGeometry()
        no_change = no_change_geometry if no_change_geometry is not None else QgsGeometry()
        coverage = self._union_geometries([gain, loss, no_change])
        if coverage is None:
            return None
        remainder = self._safe_difference(overlap, coverage)
        if remainder is not None and self._has_area(remainder):
            return None
        return gain, loss, no_change

    def _fallback_lower_region(
        self,
        pair_engine: PlanarControllingOlsEngine,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
        overlap: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        """Resolve an otherwise unresolved overlap with dense tests and a local TIN."""
        self._comparison_diagnostics["fallback_lower_region_calls"] = (
            self._comparison_diagnostics.get("fallback_lower_region_calls", 0.0) + 1.0
        )
        try:
            decision = pair_engine._sampled_lower_decision(
                baseline_candidate,
                future_candidate,
                overlap,
                dense=True,
            )
        except Exception:
            decision = None
        if decision == "all_lower":
            return QgsGeometry(overlap)
        if decision == "all_higher":
            return QgsGeometry()
        try:
            triangulated = pair_engine._triangulated_candidate_lower_region(
                baseline_candidate,
                future_candidate,
                overlap,
            )
        except Exception:
            triangulated = None
        return self._safe_intersection(triangulated, overlap) if triangulated is not None else None

    def baseline_only_parts(self) -> List[Tuple[ControllingOlsCandidate, QgsGeometry]]:
        """Return baseline controlling regions outside the future envelope."""
        result: List[Tuple[ControllingOlsCandidate, QgsGeometry]] = []
        future_regions = [region for _, region in self.future_engine._controlling_region_geometries()]
        future_union = self._union_geometries(future_regions)
        future_coverage = self._comparison_coverage_geometry(future_union)
        for baseline_candidate, baseline_region in self.baseline_engine._controlling_region_geometries():
            if future_union is None or future_union.isEmpty():
                remaining = QgsGeometry(baseline_region)
                tolerant_remaining = QgsGeometry(baseline_region)
            else:
                remaining = self._safe_difference(baseline_region, future_union)
                if remaining is None:
                    continue
                tolerant_remaining = (
                    self._safe_difference(baseline_region, future_coverage)
                    if future_coverage is not None and not future_coverage.isEmpty()
                    else QgsGeometry(remaining)
                )
                if tolerant_remaining is None:
                    tolerant_remaining = QgsGeometry(remaining)
            remaining = self._normalise_no_overlay_geometry(remaining)
            tolerant_remaining = self._normalise_no_overlay_geometry(tolerant_remaining)
            for part in self.baseline_engine._polygon_parts(remaining):
                if not self._no_overlay_part_has_tolerant_core(part, tolerant_remaining):
                    continue
                part = self._clean_no_overlay_part(part)
                if self._has_no_overlay_area(part):
                    result.append((baseline_candidate, QgsGeometry(part)))
        return result

    def delta_range(
        self,
        geometry: QgsGeometry,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
        change: Optional[str] = None,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        cache_key = (
            id(geometry),
            id(baseline_candidate),
            id(future_candidate),
            change,
        )
        cached = self._delta_range_cache.get(cache_key)
        if cached is not None and cached[0] is geometry:
            return cached[1]
        values: List[float] = []
        for point in self._sample_points(geometry, baseline_candidate, future_candidate, change):
            baseline_z = baseline_candidate.elevation_at_xy(point)
            future_z = future_candidate.elevation_at_xy(point)
            if baseline_z is None or future_z is None:
                continue
            delta = float(future_z) - float(baseline_z)
            if not math.isfinite(delta):
                continue
            # A classified range describes the interior side represented by the
            # feature. GEOS overlays can retain zero-area boundary vertices from
            # the opposite side, particularly on curved conical/constant splits.
            # Raw calls (change=None) retain every sample and are used by the
            # final analytic sign-area audit.
            if change == "gain" and delta < -self.tolerance_m:
                continue
            if change == "loss" and delta > self.tolerance_m:
                continue
            if change == "no_change" and abs(delta) > self.tolerance_m:
                continue
            values.append(self._round_delta(delta))
        if not values:
            result = (None, None, None)
            self._delta_range_cache[cache_key] = (geometry, result)
            return result
        # The first sample is pointOnSurface().  It is an interior classification
        # sample only; it is not an area-weighted or otherwise representative value.
        result = (min(values), max(values), values[0])
        self._delta_range_cache[cache_key] = (geometry, result)
        return result

    def change_contour_parts(
        self,
        parts: Sequence[Tuple[ControllingOlsCandidate, ControllingOlsCandidate, QgsGeometry]],
        change: str,
        interval_m: float = COMPARISON_CONTOUR_INTERVAL_M,
        primary_interval_m: float = COMPARISON_PRIMARY_CONTOUR_INTERVAL_M,
    ) -> List[
        Tuple[
            ControllingOlsCandidate,
            ControllingOlsCandidate,
            QgsGeometry,
            float,
            str,
            int,
        ]
    ]:
        """Return signed change isolines clipped to finalized gain/loss polygons."""
        if change not in {"gain", "loss"}:
            return []
        try:
            interval_m = float(interval_m)
            primary_interval_m = float(primary_interval_m)
        except (TypeError, ValueError):
            return []
        if interval_m <= 0.0 or primary_interval_m <= 0.0:
            return []

        contours = []
        affine_line_cache: Dict[
            Tuple[str, str, float],
            QgsGeometry,
        ] = {}
        affine_bounds_cache: Dict[Tuple[str, str], QgsRectangle] = {}
        curved_value_caches: Dict[
            Tuple[str, str],
            Dict[Tuple[float, float], Optional[float]],
        ] = {}
        for parent_sequence, (baseline, future, geometry) in enumerate(parts, start=1):
            pair_key = (baseline.surface_id, future.surface_id)
            baseline_plane = self._candidate_affine_coefficients(baseline)
            future_plane = self._candidate_affine_coefficients(future)
            generated: List[Tuple[float, QgsGeometry]] = []
            if baseline_plane is not None and future_plane is not None:
                delta_min, delta_max, _delta_sample = self.delta_range(
                    geometry,
                    baseline,
                    future,
                    change,
                )
                if delta_min is None or delta_max is None:
                    continue
                coefficients = tuple(
                    future_plane[index] - baseline_plane[index]
                    for index in range(3)
                )
                for delta_m in self._change_contour_levels(delta_min, delta_max, interval_m):
                    line_key = (*pair_key, delta_m)
                    line = affine_line_cache.get(line_key)
                    if line is None:
                        bounds = affine_bounds_cache.get(pair_key)
                        if bounds is None:
                            bounds = self._candidate_pair_bounds(baseline, future)
                            affine_bounds_cache[pair_key] = bounds
                        line = self._affine_change_line(bounds, coefficients, delta_m)
                        if line is not None:
                            affine_line_cache[line_key] = line
                    contour = self._clip_change_contour_line(line, geometry)
                    if contour is not None:
                        generated.append((delta_m, contour))
            else:
                value_cache = curved_value_caches.setdefault(pair_key, {})
                generated = self._triangulated_change_contours(
                    geometry,
                    baseline,
                    future,
                    interval_m=interval_m,
                    value_cache=value_cache,
                )

            for delta_m, contour in generated:
                if contour is None or contour.isEmpty() or contour.length() <= COMPARISON_CONTOUR_MIN_LENGTH_M:
                    continue
                ratio = delta_m / primary_interval_m
                contour_class = (
                    "primary"
                    if abs(ratio - round(ratio)) <= 10 ** (-COMPARISON_DELTA_DECIMALS)
                    else "intermediate"
                )
                contours.append(
                    (baseline, future, contour, delta_m, contour_class, parent_sequence)
                )
        return contours

    def zero_change_contour_parts(
        self,
        parts: Dict[
            str,
            Sequence[
                Tuple[
                    ControllingOlsCandidate,
                    ControllingOlsCandidate,
                    QgsGeometry,
                ]
            ],
        ],
    ) -> List[
        Tuple[
            ControllingOlsCandidate,
            ControllingOlsCandidate,
            QgsGeometry,
            float,
            str,
            int,
        ]
    ]:
        """Return verified zero contours from finalized gain/loss adjacency.

        A gain/loss boundary is only a candidate contour.  Where the applicable
        controlling surfaces change at a footprint or controller seam, the
        envelope difference can jump across zero without ever equalling zero on
        the boundary.  Verify every boundary edge against the actual solved
        envelopes before publishing it as an equal-height contour.
        """
        gain_union = self._union_geometries(
            [geometry for _baseline, _future, geometry in parts.get("gain", [])]
        )
        loss_union = self._union_geometries(
            [geometry for _baseline, _future, geometry in parts.get("loss", [])]
        )
        if gain_union is None or loss_union is None:
            return []
        if gain_union.isEmpty() or loss_union.isEmpty():
            return []
        try:
            gain_boundary = gain_union.convertToType(Qgis.GeometryType.Line, True)
            loss_boundary = loss_union.convertToType(Qgis.GeometryType.Line, True)
            shared_boundary = gain_boundary.intersection(loss_boundary)
        except Exception:
            return []
        if shared_boundary is None or shared_boundary.isEmpty():
            return []

        residual_tolerance_m = max(
            self.tolerance_m,
            COMPARISON_CURVED_CONTOUR_MAX_RESIDUAL_M,
        )
        verified_by_pair = {}
        controllers = {}
        for geometry in self._line_parts(shared_boundary):
            vertices = [QgsPointXY(vertex.x(), vertex.y()) for vertex in geometry.vertices()]
            for start, end in zip(vertices[:-1], vertices[1:]):
                segment = QgsGeometry.fromPolylineXY([start, end])
                segment_length = segment.length()
                if segment_length <= COMPARISON_CONTOUR_MIN_LENGTH_M:
                    continue
                midpoint = QgsPointXY(
                    (start.x() + end.x()) / 2.0,
                    (start.y() + end.y()) / 2.0,
                )
                try:
                    baseline_result = self.baseline_engine.controlling_candidate_at_xy(midpoint)
                    future_result = self.future_engine.controlling_candidate_at_xy(midpoint)
                except Exception:
                    continue
                if baseline_result is None or future_result is None:
                    continue
                baseline_candidate, baseline_z = baseline_result
                future_candidate, future_z = future_result
                midpoint_residual = float(future_z) - float(baseline_z)
                if (
                    not math.isfinite(midpoint_residual)
                    or abs(midpoint_residual) > residual_tolerance_m
                ):
                    continue

                # Guard against a non-zero seam whose residual happens to cross
                # zero at the midpoint of one long straight boundary edge.
                residuals = []
                for fraction in (0.25, 0.75):
                    sample = QgsPointXY(
                        start.x() + ((end.x() - start.x()) * fraction),
                        start.y() + ((end.y() - start.y()) * fraction),
                    )
                    residuals.append(
                        self._delta_at_point(sample, baseline_candidate, future_candidate)
                    )
                if any(
                    residual is None or abs(residual) > residual_tolerance_m
                    for residual in residuals
                ):
                    continue
                key = (baseline_candidate.surface_id, future_candidate.surface_id)
                verified_by_pair.setdefault(key, []).append(segment)
                controllers[key] = (baseline_candidate, future_candidate)

        zero_contours = []
        for key, geometries in verified_by_pair.items():
            merged = self._merged_change_contour_lines(geometries)
            if merged is None or merged.isEmpty():
                continue
            baseline_candidate, future_candidate = controllers[key]
            for geometry in self._line_parts(merged):
                if geometry.length() <= COMPARISON_CONTOUR_MIN_LENGTH_M:
                    continue
                zero_contours.append(
                    (
                        baseline_candidate,
                        future_candidate,
                        QgsGeometry(geometry),
                        0.0,
                        "primary",
                        len(zero_contours) + 1,
                    )
                )
        return zero_contours

    @staticmethod
    def _candidate_pair_bounds(
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
    ) -> QgsRectangle:
        bounds = QgsRectangle(baseline.footprint.boundingBox())
        bounds.combineExtentWith(future.footprint.boundingBox())
        return bounds

    def _change_contour_levels(
        self,
        delta_min: float,
        delta_max: float,
        interval_m: float,
    ) -> List[float]:
        lower = min(float(delta_min), float(delta_max))
        upper = max(float(delta_min), float(delta_max))
        start = int(math.ceil((lower - self.tolerance_m) / interval_m))
        end = int(math.floor((upper + self.tolerance_m) / interval_m))
        levels: List[float] = []
        for multiple in range(start, end + 1):
            level = self._round_delta(multiple * interval_m)
            if abs(level) <= self.tolerance_m:
                continue
            if level < lower - self.tolerance_m or level > upper + self.tolerance_m:
                continue
            levels.append(level)
        return levels

    def _change_contour_geometry(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        baseline_plane = self._candidate_affine_coefficients(baseline)
        future_plane = self._candidate_affine_coefficients(future)
        if baseline_plane is not None and future_plane is not None:
            coefficients = tuple(
                future_plane[index] - baseline_plane[index]
                for index in range(3)
            )
            return self._affine_change_contour(geometry, coefficients, delta_m)
        return self._triangulated_change_contour(geometry, baseline, future, delta_m)

    @staticmethod
    def _candidate_affine_coefficients(
        candidate: ControllingOlsCandidate,
    ) -> Optional[Tuple[float, float, float]]:
        metadata = candidate.metadata or {}
        try:
            if candidate.model == "plane":
                return (
                    float(metadata["plane_a"]),
                    float(metadata["plane_b"]),
                    float(metadata["plane_c"]),
                )
            if candidate.model == "axis":
                azimuth = math.radians(float(metadata["azimuth_degrees"]))
                slope = float(metadata["slope"])
                a = slope * math.sin(azimuth)
                b = slope * math.cos(azimuth)
                origin_x = float(metadata["origin_x"])
                origin_y = float(metadata["origin_y"])
                origin_z = float(metadata["origin_elevation_m"])
                return a, b, origin_z - (a * origin_x) - (b * origin_y)
            if candidate.model == "constant":
                elevation = metadata.get("elevation_m")
                if elevation is None:
                    point_geometry = candidate.footprint.pointOnSurface()
                    if point_geometry is None or point_geometry.isEmpty():
                        return None
                    point = point_geometry.asPoint()
                    elevation = candidate.elevation_at_xy(QgsPointXY(point.x(), point.y()))
                if elevation is not None and math.isfinite(float(elevation)):
                    return 0.0, 0.0, float(elevation)
        except (KeyError, TypeError, ValueError, RuntimeError, AttributeError):
            return None
        return None

    def _affine_change_contour(
        self,
        geometry: QgsGeometry,
        coefficients: Tuple[float, float, float],
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        line = self._affine_change_line(geometry.boundingBox(), coefficients, delta_m)
        return self._clip_change_contour_line(line, geometry)

    @staticmethod
    def _affine_change_line(
        bbox: QgsRectangle,
        coefficients: Tuple[float, float, float],
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        a, b, c = coefficients
        gradient_squared = (a * a) + (b * b)
        if gradient_squared <= 1e-18:
            return None
        centre_x = (bbox.xMinimum() + bbox.xMaximum()) / 2.0
        centre_y = (bbox.yMinimum() + bbox.yMaximum()) / 2.0
        displacement = (float(delta_m) - ((a * centre_x) + (b * centre_y) + c)) / gradient_squared
        origin = QgsPointXY(centre_x + (a * displacement), centre_y + (b * displacement))
        gradient_length = math.sqrt(gradient_squared)
        direction_x = -b / gradient_length
        direction_y = a / gradient_length
        extent = max(math.hypot(bbox.width(), bbox.height()) * 2.0, 1.0)
        line = QgsGeometry.fromPolylineXY(
            [
                QgsPointXY(origin.x() - (direction_x * extent), origin.y() - (direction_y * extent)),
                QgsPointXY(origin.x() + (direction_x * extent), origin.y() + (direction_y * extent)),
            ]
        )
        return line

    @classmethod
    def _clip_change_contour_line(
        cls,
        line: Optional[QgsGeometry],
        geometry: QgsGeometry,
    ) -> Optional[QgsGeometry]:
        if line is None or line.isEmpty() or geometry is None or geometry.isEmpty():
            return None
        try:
            clipped = line.intersection(geometry)
        except Exception:
            return None
        exact = cls._merged_change_contour_lines([clipped])
        try:
            tolerant_domain = geometry.buffer(
                COMPARISON_CONTOUR_CLIP_TOLERANCE_M,
                4,
            )
            tolerant_clipped = line.intersection(tolerant_domain)
            tolerant = cls._merged_change_contour_lines([tolerant_clipped])
        except Exception:
            tolerant = None
        if tolerant is None or tolerant.isEmpty():
            return exact
        if exact is None or exact.isEmpty():
            return tolerant
        exact_parts = len(cls._line_parts(exact))
        tolerant_parts = len(cls._line_parts(tolerant))
        recovered_length = tolerant.length() - exact.length()
        if (
            tolerant_parts < exact_parts
            or recovered_length > (4.0 * COMPARISON_CONTOUR_CLIP_TOLERANCE_M)
        ):
            return tolerant
        return exact

    def _triangulated_change_contour(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        contours = self._triangulated_change_contours(
            geometry,
            baseline,
            future,
            requested_levels=[float(delta_m)],
        )
        return contours[0][1] if contours else None

    def _triangulated_change_contours(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        interval_m: float = COMPARISON_CONTOUR_INTERVAL_M,
        requested_levels: Optional[Sequence[float]] = None,
        value_cache: Optional[Dict[Tuple[float, float], Optional[float]]] = None,
    ) -> List[Tuple[float, QgsGeometry]]:
        points = self.baseline_engine._triangulation_sample_points(geometry)
        if len(points) < 3:
            return []

        if value_cache is None:
            value_cache = {}

        def _value(point: QgsPointXY) -> Optional[float]:
            key = (round(point.x(), 3), round(point.y(), 3))
            if key not in value_cache:
                value_cache[key] = self._delta_at_point(point, baseline, future)
            return value_cache[key]

        if requested_levels is None:
            sampled_values = [value for value in (_value(point) for point in points) if value is not None]
            if not sampled_values:
                return []
            levels = self._change_contour_levels(
                min(sampled_values),
                max(sampled_values),
                interval_m,
            )
        else:
            levels = sorted({self._round_delta(level) for level in requested_levels})
        if not levels:
            return []

        try:
            triangles = QgsGeometry.fromMultiPointXY(points).delaunayTriangulation(0.0, False)
        except Exception:
            return []
        prepared_geometry = None
        try:
            prepared_geometry = QgsGeometry.createGeometryEngine(geometry.constGet())
            prepared_geometry.prepareGeometry()
        except Exception:
            prepared_geometry = None
        segments_by_level: Dict[float, List[QgsGeometry]] = {level: [] for level in levels}
        for triangle in self.baseline_engine._polygon_parts(triangles):
            try:
                ring = triangle.asPolygon()[0]
            except (IndexError, TypeError):
                continue
            triangle_points = [QgsPointXY(point) for point in ring[:3]]
            if len(triangle_points) < 3:
                continue
            values = [_value(point) for point in triangle_points]
            if any(value is None for value in values):
                continue
            numeric_values = [float(value) for value in values]
            triangle_min = min(numeric_values)
            triangle_max = max(numeric_values)
            for level in levels:
                if level < triangle_min - 1e-9 or level > triangle_max + 1e-9:
                    continue
                triangle_segments = self._triangle_change_contour_segments(
                    triangle_points,
                    numeric_values,
                    level,
                )
                has_coincident_edge = any(
                    abs(numeric_values[start_index] - level) <= 1e-9
                    and abs(numeric_values[end_index] - level) <= 1e-9
                    for start_index, end_index in ((0, 1), (1, 2), (2, 0))
                )
                for segment in triangle_segments:
                    # Marching triangles treats an edge whose endpoint samples
                    # both equal the level as a contour.  On curved surfaces the
                    # value between those endpoints can depart from the level,
                    # leaving a short wireframe-aligned spur in the output.
                    if has_coincident_edge and not self._coincident_change_contour_edge_is_valid(
                        segment,
                        level,
                        baseline,
                        future,
                    ):
                        continue
                    try:
                        wholly_inside = bool(
                            prepared_geometry is not None
                            and prepared_geometry.contains(segment.constGet())
                        )
                        clipped = segment if wholly_inside else segment.intersection(geometry)
                    except Exception:
                        try:
                            clipped = segment.intersection(geometry)
                        except Exception:
                            clipped = segment
                    if clipped is not None and not clipped.isEmpty():
                        segments_by_level[level].append(clipped)
        contours: List[Tuple[float, QgsGeometry]] = []
        conical_pair_engine = (
            PlanarControllingOlsEngine(
                [future, baseline],
                tie_tolerance_m=0.0,
            )
            if baseline.model == "conical" and future.model == "conical"
            else None
        )
        for level in levels:
            merged = self._merged_change_contour_lines(segments_by_level[level])
            if (
                merged is not None
                and not merged.isEmpty()
                and conical_pair_engine is not None
            ):
                merged = self._project_change_contour_to_level(
                    merged,
                    geometry,
                    baseline,
                    future,
                    level,
                )
            if (
                merged is not None
                and not merged.isEmpty()
                and conical_pair_engine is not None
            ):
                fair_parts = []
                for source_part in self._line_parts(merged):
                    fair_part = conical_pair_engine._smoothed_conical_conical_contour(
                        source_part,
                        future,
                        baseline,
                        geometry,
                        target_difference_m=level,
                    )
                    if (
                        fair_part is not None
                        and not fair_part.isEmpty()
                        and fair_part.length()
                        > COMPARISON_CURVED_CONTOUR_MIN_LENGTH_M
                    ):
                        fair_parts.append(fair_part)
                        continue
                    source_residual = (
                        conical_pair_engine._maximum_candidate_pair_curve_residual(
                            source_part,
                            future,
                            baseline,
                            level,
                        )
                    )
                    # A failed fairing attempt used to fall back to the sampled
                    # component unconditionally.  That retained triangulation
                    # fragments along controlling-region wireframes even when
                    # they were metres away from the requested change level.
                    if (
                        source_residual is not None
                        and source_residual
                        <= CONICAL_CONICAL_SMOOTHING_MAX_EQUALITY_RESIDUAL_M
                        and source_part.length()
                        > COMPARISON_CURVED_CONTOUR_MIN_LENGTH_M
                    ):
                        fair_parts.append(source_part)
                fair_merged = self._merged_change_contour_lines(fair_parts)
                if fair_merged is not None and not fair_merged.isEmpty():
                    merged = fair_merged
                else:
                    merged = None
            if merged is not None and not merged.isEmpty():
                accurate_parts = []
                for source_part in self._line_parts(merged):
                    source_residual = (
                        self.baseline_engine._maximum_candidate_pair_curve_residual(
                            source_part,
                            future,
                            baseline,
                            level,
                        )
                    )
                    if (
                        source_residual is not None
                        and source_residual
                        <= COMPARISON_CURVED_CONTOUR_MAX_RESIDUAL_M
                        and source_part.length()
                        > COMPARISON_CURVED_CONTOUR_MIN_LENGTH_M
                    ):
                        accurate_parts.append(source_part)
                        continue
                    projected = self._project_change_contour_to_level(
                        source_part,
                        geometry,
                        baseline,
                        future,
                        level,
                    )
                    for projected_part in self._line_parts(projected):
                        projected_residual = (
                            self.baseline_engine._maximum_candidate_pair_curve_residual(
                                projected_part,
                                future,
                                baseline,
                                level,
                            )
                        )
                        if (
                            projected_residual is not None
                            and projected_residual
                            <= COMPARISON_CURVED_CONTOUR_MAX_RESIDUAL_M
                            and projected_part.length()
                            > COMPARISON_CURVED_CONTOUR_MIN_LENGTH_M
                        ):
                            accurate_parts.append(projected_part)
                merged = self._merged_change_contour_lines(accurate_parts)
            if merged is not None and not merged.isEmpty():
                contours.append((level, merged))
        return contours

    def _project_change_contour_to_level(
        self,
        sampled_contour: QgsGeometry,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        delta_m: float,
    ) -> Optional[QgsGeometry]:
        """Project a triangulated isoline onto the exact signed-change level."""
        def _shifted_future_elevation(point: QgsPointXY) -> Optional[float]:
            elevation = future.elevation_at_xy(point)
            return None if elevation is None else float(elevation) - float(delta_m)

        shifted_future = ControllingOlsCandidate(
            surface_id=f"{future.surface_id}:change:{delta_m:.3f}",
            surface_type=future.surface_type,
            footprint=future.footprint,
            elevation_at_xy=_shifted_future_elevation,
            model=future.model,
            metadata=future.metadata,
        )
        projected_parts: List[QgsGeometry] = []
        for source_part in self._line_parts(sampled_contour):
            source_residual = self.baseline_engine._maximum_candidate_pair_curve_residual(
                source_part,
                future,
                baseline,
                delta_m,
            )
            if (
                source_residual is not None
                and source_residual <= COMPARISON_CURVED_CONTOUR_MAX_RESIDUAL_M
            ):
                projected_parts.append(source_part)
                continue
            try:
                densified = source_part.densifyByDistance(
                    COMPARISON_CURVED_CONTOUR_OUTPUT_SPACING_M
                )
            except Exception:
                densified = source_part
            for dense_part in self._line_parts(densified):
                try:
                    source_points = dense_part.asPolyline()
                except (TypeError, RuntimeError):
                    continue
                projected_points: List[QgsPointXY] = []
                for point in source_points:
                    projected = (
                        self.baseline_engine._project_candidate_pair_point_to_equality(
                            shifted_future,
                            baseline,
                            point,
                        )
                    )
                    if (
                        not projected_points
                        or projected.distance(projected_points[-1]) > 1e-6
                    ):
                        projected_points.append(projected)
                if len(projected_points) < 2:
                    continue

                refined_points: List[QgsPointXY] = []
                for start_point, end_point in zip(
                    projected_points[:-1], projected_points[1:]
                ):
                    segment_points = (
                        self.baseline_engine._refine_candidate_pair_equality_segment(
                            shifted_future,
                            baseline,
                            start_point,
                            end_point,
                        )
                    )
                    if not segment_points:
                        continue
                    if refined_points:
                        refined_points.extend(segment_points[1:])
                    else:
                        refined_points.extend(segment_points)
                refined_points = self.baseline_engine._remove_transition_curve_backtracking(
                    refined_points
                )
                if len(refined_points) < 2:
                    continue
                projected_part = QgsGeometry.fromPolylineXY(refined_points)
                try:
                    projected_part = projected_part.intersection(geometry)
                except Exception:
                    pass
                for clipped_part in self._line_parts(projected_part):
                    if clipped_part.length() > COMPARISON_CURVED_CONTOUR_MIN_LENGTH_M:
                        projected_parts.append(clipped_part)
        return self._merged_change_contour_lines(projected_parts)

    @staticmethod
    def _triangle_change_contour_segments(
        points: Sequence[QgsPointXY],
        values: Sequence[float],
        delta_m: float,
    ) -> List[QgsGeometry]:
        epsilon = 1e-9
        crossings: List[QgsPointXY] = []
        coincident: List[QgsGeometry] = []

        def _add_crossing(point: QgsPointXY) -> None:
            if any(point.distance(existing) <= 1e-7 for existing in crossings):
                return
            crossings.append(QgsPointXY(point))

        for start_index, end_index in ((0, 1), (1, 2), (2, 0)):
            start_point = points[start_index]
            end_point = points[end_index]
            start_difference = values[start_index] - delta_m
            end_difference = values[end_index] - delta_m
            start_is_level = abs(start_difference) <= epsilon
            end_is_level = abs(end_difference) <= epsilon
            if start_is_level and end_is_level:
                coincident.append(QgsGeometry.fromPolylineXY([start_point, end_point]))
                continue
            if start_is_level:
                _add_crossing(start_point)
            elif end_is_level:
                _add_crossing(end_point)
            elif start_difference * end_difference < 0.0:
                denominator = abs(start_difference) + abs(end_difference)
                fraction = 0.5 if denominator <= epsilon else abs(start_difference) / denominator
                _add_crossing(
                    QgsPointXY(
                        start_point.x() + ((end_point.x() - start_point.x()) * fraction),
                        start_point.y() + ((end_point.y() - start_point.y()) * fraction),
                    )
                )
        if coincident:
            return coincident
        if len(crossings) < 2:
            return []
        if len(crossings) > 2:
            crossings = max(
                (
                    [first, second]
                    for first_index, first in enumerate(crossings)
                    for second in crossings[first_index + 1 :]
                ),
                key=lambda pair: pair[0].distance(pair[1]),
            )
        return [QgsGeometry.fromPolylineXY(crossings[:2])]

    @classmethod
    def _coincident_change_contour_edge_is_valid(
        cls,
        segment: QgsGeometry,
        delta_m: float,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
    ) -> bool:
        """Confirm that a sampled level edge is a real contour between its endpoints."""
        try:
            points = segment.asPolyline()
        except (TypeError, RuntimeError):
            return False
        if len(points) < 2:
            return False
        start = points[0]
        end = points[-1]
        for fraction in (0.25, 0.5, 0.75):
            point = QgsPointXY(
                start.x() + ((end.x() - start.x()) * fraction),
                start.y() + ((end.y() - start.y()) * fraction),
            )
            value = cls._delta_at_point(point, baseline, future)
            if value is None or abs(value - delta_m) > 1e-7:
                return False
        return True

    @classmethod
    def _merged_change_contour_lines(
        cls,
        geometries: Sequence[QgsGeometry],
    ) -> Optional[QgsGeometry]:
        line_parts: List[QgsGeometry] = []
        for geometry in geometries:
            for part in cls._line_parts(geometry):
                if part.length() > COMPARISON_CONTOUR_MIN_LENGTH_M:
                    line_parts.append(part)
        if not line_parts:
            return None
        try:
            merged = QgsGeometry.unaryUnion(line_parts) if len(line_parts) > 1 else line_parts[0]
        except Exception:
            merged = line_parts[0]
        try:
            line_merged = merged.mergeLines()
            if line_merged is not None and not line_merged.isEmpty():
                merged = line_merged
        except Exception:
            pass
        return merged

    def _append_sampled_whole_overlap(
        self,
        result,
        baseline,
        future,
        overlap,
        clean_spikes: bool = True,
    ) -> None:
        self._comparison_diagnostics["sampled_whole_overlap_calls"] = (
            self._comparison_diagnostics.get("sampled_whole_overlap_calls", 0.0) + 1.0
        )
        delta_min, delta_max, delta_sample = self.delta_range(overlap, baseline, future)
        if delta_sample is None:
            return
        if (
            delta_min is not None
            and delta_max is not None
            and abs(delta_min) <= self.tolerance_m
            and abs(delta_max) <= self.tolerance_m
        ):
            self._append_parts(result["no_change"], baseline, future, overlap, "no_change", clean_spikes)
        elif delta_sample > 0.0:
            self._append_parts(result["gain"], baseline, future, overlap, "gain", clean_spikes)
        elif delta_sample < 0.0:
            self._append_parts(result["loss"], baseline, future, overlap, "loss", clean_spikes)

    def _append_no_change_if_equal(
        self,
        destination,
        baseline,
        future,
        overlap,
        clean_spikes: bool = True,
    ) -> bool:
        delta_min, delta_max, _delta_sample = self.delta_range(overlap, baseline, future)
        if delta_min is None or delta_max is None:
            return False
        if abs(delta_min) > self.tolerance_m or abs(delta_max) > self.tolerance_m:
            return False
        self._append_parts(destination, baseline, future, overlap, "no_change", clean_spikes)
        return True

    def _append_parts(
        self,
        destination,
        baseline,
        future,
        geometry,
        change: str,
        clean_spikes: bool = True,
    ) -> None:
        if geometry is None or geometry.isEmpty():
            return
        for part in self.baseline_engine._polygon_parts(geometry):
            if not self._has_area(part):
                continue
            if clean_spikes:
                part = self._clean_comparison_part(part, baseline, future, change)
            if not self._has_area(part):
                continue
            delta_min, delta_max, delta_sample = self.delta_range(part, baseline, future, change)
            if delta_sample is None:
                continue
            if change == "gain":
                if delta_max is None or delta_max <= 0.0:
                    continue
            if change == "loss":
                if delta_min is None or delta_min >= 0.0:
                    continue
            if change == "no_change":
                if delta_min is None or delta_max is None:
                    continue
                if abs(delta_min) > self.tolerance_m or abs(delta_max) > self.tolerance_m:
                    continue
            destination.append((baseline, future, QgsGeometry(part)))

    def _append_common_domain_gap_parts(
        self,
        result,
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> None:
        classified_geometries = [
            geometry
            for change in ("gain", "loss", "no_change")
            for _baseline, _future, geometry in result.get(change, [])
            if geometry is not None and not geometry.isEmpty()
        ]
        classified_union = self._union_geometries(classified_geometries)
        # Repair within each original controller-pair overlap.  A union-wide
        # remainder may span several controlling regions; assigning one sampled
        # controller pair to that whole polygon is the source of dropped and
        # incorrectly attributed comparison features.
        for baseline_candidate, baseline_region in baseline_regions:
            for future_candidate, future_region in future_regions:
                pair_domain = self._pair_domain(
                    baseline_region,
                    future_region,
                )
                if not self._has_area(pair_domain):
                    continue
                pair_remainder = (
                    self._safe_difference(pair_domain, classified_union)
                    if classified_union is not None and not classified_union.isEmpty()
                    else QgsGeometry(pair_domain)
                )
                if not self._has_area(pair_remainder):
                    continue
                for part in self.baseline_engine._polygon_parts(pair_remainder):
                    if not self._has_area(part):
                        continue
                    self._comparison_diagnostics["common_domain_gap_parts"] = (
                        self._comparison_diagnostics.get("common_domain_gap_parts", 0.0) + 1.0
                    )
                    self._comparison_diagnostics["common_domain_gap_area_m2"] = (
                        self._comparison_diagnostics.get("common_domain_gap_area_m2", 0.0) + part.area()
                    )
                    starts = {
                        change: len(result[change])
                        for change in ("gain", "loss", "no_change")
                    }
                    self._append_classified_overlap(
                        result,
                        baseline_candidate,
                        future_candidate,
                        part,
                        clean_spikes=False,
                    )
                    self._reattach_recovered_sliver_parts(result, starts)
                    # Controller-region edges can overlap by numerical dust.
                    # Carry each successful repair into the assigned union so
                    # the same gap is not recovered again under a later pair.
                    classified_union = self._union_geometries([
                        geometry
                        for classified_change in ("gain", "loss", "no_change")
                        for _baseline, _future, geometry
                        in result.get(classified_change, [])
                        if geometry is not None and not geometry.isEmpty()
                    ])

    def _reattach_recovered_sliver_parts(self, result, starts) -> None:
        """Join only narrow gap-recovery parts to their verified neighbour."""
        recovered = []
        for change in ("gain", "loss", "no_change"):
            recovered.extend(
                (change, baseline, future, geometry)
                for baseline, future, geometry in result[change][starts[change]:]
            )
            del result[change][starts[change]:]

        for change, baseline, future, geometry in recovered:
            if not self._reattach_recovered_sliver_part(
                result,
                change,
                baseline,
                future,
                geometry,
            ):
                self._track_recovered_sliver_geometry(geometry)
                result[change].append((baseline, future, geometry))

    def _track_recovered_sliver_geometry(self, geometry: QgsGeometry) -> None:
        """Retain spatial provenance for a narrow recovery part across merges."""
        perimeter = geometry.length()
        if perimeter <= 0.0:
            return
        if (
            (2.0 * geometry.area()) / perimeter
            <= COMPARISON_RECOVERY_SLIVER_MAX_EFFECTIVE_WIDTH_M
        ):
            self._recovered_sliver_geometries.append(QgsGeometry(geometry))

    def _track_new_recovered_sliver_parts(self, result, starts) -> None:
        for change in ("gain", "loss", "no_change"):
            for _baseline, _future, geometry in result[change][starts[change]:]:
                self._track_recovered_sliver_geometry(geometry)

    def _reattach_tracked_recovered_sliver_parts(self, result) -> None:
        """Rejoin pending recovery slivers after every recovery target exists."""
        if not self._recovered_sliver_geometries:
            return
        for _pass in range(2):
            changed = False
            for change in ("gain", "loss", "no_change"):
                for index in range(len(result.get(change, [])) - 1, -1, -1):
                    baseline, future, geometry = result[change][index]
                    recovered_indexes = self._tracked_recovered_sliver_indexes(
                        geometry
                    )
                    if not recovered_indexes:
                        continue
                    result[change].pop(index)
                    if self._reattach_recovered_sliver_part(
                        result,
                        change,
                        baseline,
                        future,
                        geometry,
                    ):
                        for recovered_index in reversed(recovered_indexes):
                            self._recovered_sliver_geometries.pop(recovered_index)
                        changed = True
                    else:
                        result[change].insert(index, (baseline, future, geometry))
            if not changed:
                break

    def _tracked_recovered_sliver_indexes(
        self,
        geometry: QgsGeometry,
    ) -> List[int]:
        perimeter = geometry.length()
        if perimeter <= 0.0:
            return []
        if (
            (2.0 * geometry.area()) / perimeter
            > COMPARISON_RECOVERY_SLIVER_MAX_EFFECTIVE_WIDTH_M
        ):
            return []
        area = geometry.area()
        if area <= 0.0:
            return []
        matching_indexes = []
        matching_geometries = []
        for index, recovered in enumerate(self._recovered_sliver_geometries):
            if not self._bounding_boxes_intersect(geometry, recovered):
                continue
            try:
                overlap_area = geometry.intersection(recovered).area()
            except Exception:
                continue
            if overlap_area <= 0.0:
                continue
            matching_indexes.append(index)
            matching_geometries.append(recovered)
        if not matching_geometries:
            return []
        tracked_union = self._union_geometries(matching_geometries)
        if tracked_union is None:
            return []
        try:
            untracked_area = geometry.difference(tracked_union).area()
        except Exception:
            return []
        # Provenance applies only to the recorded recovery geometry.  A
        # percentage threshold lets a later merge carry an unrelated tail and
        # then reclassifies that tail with the sliver.  Permit only the same
        # absolute sub-threshold noise used by the comparison area contract.
        return (
            matching_indexes
            if untracked_area <= COMPARISON_MIN_AREA_M2
            else []
        )

    def _reattach_recovered_sliver_part(
        self,
        result,
        change: str,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        geometry: QgsGeometry,
    ) -> bool:
        """Attach a line-like recovery remainder without dissolving other parts."""
        perimeter = geometry.length()
        if perimeter <= 0.0:
            return False
        effective_width = (2.0 * geometry.area()) / perimeter
        if effective_width > COMPARISON_RECOVERY_SLIVER_MAX_EFFECTIVE_WIDTH_M:
            return False

        numeric_zero_m = 1e-9
        sample_records = []
        for sample, is_interior in self._recovery_classification_samples(geometry):
            baseline_sample = self.baseline_engine.controlling_candidate_at_xy(
                sample
            )
            future_sample = self.future_engine.controlling_candidate_at_xy(sample)
            if baseline_sample is None or future_sample is None:
                continue
            sample_records.append(
                (
                    float(future_sample[1]) - float(baseline_sample[1]),
                    (
                        baseline_sample[0].surface_id,
                        future_sample[0].surface_id,
                    ),
                    is_interior,
                )
            )
        if not sample_records:
            return False
        envelope_deltas = [record[0] for record in sample_records]
        has_gain = any(delta > numeric_zero_m for delta in envelope_deltas)
        has_loss = any(delta < -numeric_zero_m for delta in envelope_deltas)
        if has_gain and has_loss:
            return False
        if has_gain:
            preferred_change = "gain"
            actual_id_options = {
                ids for delta, ids, is_interior in sample_records
                if is_interior and delta > numeric_zero_m
            }
        elif has_loss:
            preferred_change = "loss"
            actual_id_options = {
                ids for delta, ids, is_interior in sample_records
                if is_interior and delta < -numeric_zero_m
            }
        else:
            preferred_change = "no_change"
            # Ring vertices lie on controller ties and can legitimately report
            # either owner. Interior probes must agree before an all-zero
            # recovery wedge can be attributed to one controller pair.
            actual_id_options = {
                ids for _delta, ids, is_interior in sample_records
                if is_interior
            }
        if len(actual_id_options) == 1:
            actual_ids = next(iter(actual_id_options))
        elif actual_id_options:
            return False
        elif self._controller_pair_covers_recovery_geometry(
            baseline,
            future,
            geometry,
        ):
            # A sub-resolution sign can exist only at the recovery ring.  In
            # that case use the source pair only when the solved pair domain
            # covers the whole wedge to numerical precision.
            actual_ids = (baseline.surface_id, future.surface_id)
        else:
            return False

        candidates = []
        for target_change in (preferred_change,):
            for target_index, (
                target_baseline,
                target_future,
                target_geometry,
            ) in enumerate(result.get(target_change, [])):
                target_ids = (
                    target_baseline.surface_id,
                    target_future.surface_id,
                )
                if target_ids != actual_ids:
                    continue
                if not self._bounding_boxes_intersect(geometry, target_geometry):
                    continue
                shared_length = self._shared_boundary_length(
                    geometry,
                    target_geometry,
                )
                shared_fraction = shared_length / perimeter
                if (
                    shared_length
                    >= max(
                        COMPARISON_RECOVERY_SLIVER_MIN_SHARED_BOUNDARY_M,
                        10.0 * effective_width,
                    )
                    and shared_fraction
                    >= COMPARISON_RECOVERY_SLIVER_MIN_SHARED_BOUNDARY_FRACTION
                ):
                    candidates.append((
                        -shared_length,
                        -shared_fraction,
                        -target_geometry.area(),
                        target_change,
                        target_index,
                        target_baseline,
                        target_future,
                        target_geometry,
                    ))
        if not candidates:
            return False

        candidates.sort(key=lambda item: item[:3])
        chosen = candidates[0]
        chosen_shared_length = -chosen[0]
        runner_up_shared_length = (
            -candidates[1][0] if len(candidates) > 1 else 0.0
        )
        if (
            runner_up_shared_length > 0.0
            and chosen_shared_length
            < (
                runner_up_shared_length
                * COMPARISON_RECOVERY_SLIVER_DOMINANT_CONTACT_RATIO
            )
        ):
            return False

        (
            _negative_shared_length,
            _negative_shared_fraction,
            _negative_area,
            target_change,
            target_index,
            target_baseline,
            target_future,
            target_geometry,
        ) = chosen
        unique = self._safe_difference(geometry, target_geometry)
        if unique is None:
            return False
        if not self._has_area(unique):
            result[target_change][target_index] = (
                target_baseline,
                target_future,
                target_geometry,
            )
            return True
        try:
            combined = QgsGeometry.unaryUnion([target_geometry, unique])
        except Exception:
            return False
        if combined is None or combined.isNull() or combined.isEmpty():
            return False
        if not combined.isGeosValid():
            return False
        if (
            self.baseline_engine._polygon_part_count(combined)
            > self.baseline_engine._polygon_part_count(target_geometry)
        ):
            return False
        expected_area = target_geometry.area() + unique.area()
        area_tolerance = max(COMPARISON_MIN_AREA_M2, expected_area * 1e-10)
        if abs(combined.area() - expected_area) > area_tolerance:
            return False

        result[target_change][target_index] = (
            target_baseline,
            target_future,
            combined,
        )
        self._comparison_diagnostics["recovered_sliver_reattached_parts"] = (
            self._comparison_diagnostics.get(
                "recovered_sliver_reattached_parts",
                0.0,
            )
            + 1.0
        )
        self._comparison_diagnostics["recovered_sliver_reattached_area_m2"] = (
            self._comparison_diagnostics.get(
                "recovered_sliver_reattached_area_m2",
                0.0,
            )
            + geometry.area()
        )
        if target_change != change:
            self._comparison_diagnostics["recovered_sliver_reclassified_parts"] = (
                self._comparison_diagnostics.get(
                    "recovered_sliver_reclassified_parts",
                    0.0,
                )
                + 1.0
            )
        return True

    def _controller_pair_covers_recovery_geometry(
        self,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        geometry: QgsGeometry,
    ) -> bool:
        """Confirm that a boundary-only recovery belongs wholly to its pair."""
        baseline_coverage = self._union_geometries([
            region for candidate, region
            in self.baseline_engine._controlling_region_geometries()
            if candidate.surface_id == baseline.surface_id
        ])
        future_coverage = self._union_geometries([
            region for candidate, region
            in self.future_engine._controlling_region_geometries()
            if candidate.surface_id == future.surface_id
        ])
        if baseline_coverage is None or future_coverage is None:
            return False
        pair_coverage = self._safe_intersection(
            baseline_coverage,
            future_coverage,
        )
        if pair_coverage is None or pair_coverage.isEmpty():
            return False
        try:
            outside_area = geometry.difference(pair_coverage).area()
        except Exception:
            return False
        return outside_area <= max(1e-9, geometry.area() * 1e-9)

    def _recovery_classification_samples(
        self,
        geometry: QgsGeometry,
    ) -> List[Tuple[QgsPointXY, bool]]:
        """Return boundary samples plus interior probes for controller checks."""
        try:
            representative_geometry = geometry.pointOnSurface()
            representative = representative_geometry.asPoint()
            interior_origin = QgsPointXY(representative.x(), representative.y())
        except Exception:
            return []

        samples: List[Tuple[QgsPointXY, bool]] = []
        seen = set()

        def add(point_xy: QgsPointXY, is_interior: bool) -> None:
            key = (round(point_xy.x(), 7), round(point_xy.y(), 7))
            if key in seen:
                return
            seen.add(key)
            samples.append((QgsPointXY(point_xy), is_interior))

        add(interior_origin, True)
        boundary_samples = self._sample_points(geometry)[1:]
        for boundary in boundary_samples:
            add(boundary, False)
            for fraction in (0.25, 0.5, 0.75):
                probe = QgsPointXY(
                    interior_origin.x()
                    + ((boundary.x() - interior_origin.x()) * fraction),
                    interior_origin.y()
                    + ((boundary.y() - interior_origin.y()) * fraction),
                )
                try:
                    if geometry.contains(QgsGeometry.fromPointXY(probe)):
                        add(probe, True)
                except Exception:
                    continue
        return samples

    @staticmethod
    def _shared_boundary_length(
        first: QgsGeometry,
        second: QgsGeometry,
    ) -> float:
        """Return line contact only; polygon overlap perimeter is not contact."""
        try:
            first_boundary = first.convertToType(
                Qgis.GeometryType.Line,
                True,
            )
            second_boundary = second.convertToType(
                Qgis.GeometryType.Line,
                True,
            )
            shared = first_boundary.intersection(second_boundary)
            length = float(shared.length())
        except Exception:
            return 0.0
        return length if math.isfinite(length) and length > 0.0 else 0.0

    def _append_final_common_domain_remainders(
        self,
        result,
        baseline_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
        future_regions: Sequence[Tuple[ControllingOlsCandidate, QgsGeometry]],
    ) -> None:
        """Assign numerical residuals after all destructive cleanup has finished."""
        common_domain = self._common_domain(baseline_regions, future_regions)
        if common_domain is None:
            return
        classified_union = self._union_geometries(
            [
                geometry
                for change in ("gain", "loss", "no_change")
                for _baseline, _future, geometry in result.get(change, [])
            ]
        )
        remaining = (
            self._safe_difference(common_domain, classified_union)
            if classified_union is not None
            else common_domain
        )
        if not self._has_area(remaining):
            return

        for baseline, baseline_region in baseline_regions:
            if not self._has_area(remaining):
                break
            for future, future_region in future_regions:
                if not self._has_area(remaining):
                    break
                pair_domain = self._pair_domain(
                    baseline_region,
                    future_region,
                )
                if not self._has_area(pair_domain):
                    continue
                pair_remaining = self._safe_intersection(remaining, pair_domain)
                if not self._has_area(pair_remaining):
                    continue
                assigned_parts = []
                for part in self.baseline_engine._polygon_parts(pair_remaining):
                    if (
                        self._strict_conventional_partition_enabled()
                        and part.area() <= COMPARISON_MIN_AREA_M2
                    ):
                        # Sub-threshold overlay fragments remain in the audited
                        # common-domain difference and are covered by the
                        # fixture's absolute area tolerance. They are not a
                        # semantic controller-recovery operation.
                        continue
                    starts = {
                        change: len(result[change])
                        for change in ("gain", "loss", "no_change")
                    }
                    # A final remainder can still cross the equal-height locus.
                    # Classifying the whole polygon from pointOnSurface() puts
                    # both signs into one output feature and lets contours of
                    # the opposite sign leak into it.  Reuse the canonical
                    # pair solver so the repair has the same shared zero-height
                    # edge as the main comparison partition.
                    self._append_classified_overlap(
                        result,
                        baseline,
                        future,
                        part,
                        clean_spikes=False,
                    )
                    self._track_new_recovered_sliver_parts(result, starts)
                    newly_assigned = [
                        geometry
                        for change in ("gain", "loss", "no_change")
                        for _baseline, _future, geometry in result[change][starts[change]:]
                        if self._has_area(geometry)
                    ]
                    if not newly_assigned:
                        self._comparison_diagnostics["unresolved_comparisons"] = (
                            self._comparison_diagnostics.get("unresolved_comparisons", 0.0) + 1.0
                        )
                        continue
                    self._comparison_diagnostics["final_remainder_parts"] = (
                        self._comparison_diagnostics.get("final_remainder_parts", 0.0) + 1.0
                    )
                    self._comparison_diagnostics["final_remainder_area_m2"] = (
                        self._comparison_diagnostics.get("final_remainder_area_m2", 0.0) + part.area()
                    )
                    assigned_parts.extend(newly_assigned)
                assigned = self._union_geometries(assigned_parts)
                if assigned is not None:
                    remaining = self._safe_difference(remaining, assigned)

    def _partition_classified_parts(self, result) -> None:
        """Remove repair overlap without changing the combined classified coverage."""
        assigned = QgsGeometry()
        # No-change is inclusive at +/- tolerance, so it owns numerical overlap
        # on those boundaries before the strict gain/loss classes are applied.
        for change in ("no_change", "gain", "loss"):
            partitioned = []
            for baseline, future, geometry in result.get(change, []):
                if not self._has_area(geometry):
                    continue
                unique = (
                    self._safe_difference(geometry, assigned)
                    if not assigned.isEmpty()
                    else QgsGeometry(geometry)
                )
                if not self._has_area(unique):
                    continue
                for part in self.baseline_engine._polygon_parts(unique):
                    if not self._has_area(part):
                        continue
                    partitioned.append((baseline, future, QgsGeometry(part)))
                if assigned.isEmpty():
                    assigned = QgsGeometry(unique)
                else:
                    merged_assigned = self._union_geometries([assigned, unique])
                    if merged_assigned is not None:
                        assigned = merged_assigned
            result[change] = partitioned

    def _enforce_final_height_signs(self, result) -> None:
        """Split any repaired polygon that still spans both sides of zero."""
        rebuilt = {"gain": [], "loss": []}
        for source_change in ("gain", "loss"):
            for baseline, future, geometry in result.get(source_change, []):
                if not self._has_area(geometry):
                    continue
                delta_min, delta_max, _delta_sample = self.delta_range(
                    geometry,
                    baseline,
                    future,
                )
                potential_wrong_side = (
                    source_change == "gain"
                    and delta_min is not None
                    and delta_min < -self.tolerance_m
                ) or (
                    source_change == "loss"
                    and delta_max is not None
                    and delta_max > self.tolerance_m
                )
                if not potential_wrong_side:
                    rebuilt[source_change].append((baseline, future, geometry))
                    continue

                pair_engine = PlanarControllingOlsEngine(
                    [baseline, future],
                    tie_tolerance_m=0.0,
                )
                try:
                    gain_geometry = pair_engine._candidate_lower_region(
                        baseline,
                        future,
                        geometry,
                    )
                except Exception:
                    gain_geometry = None
                if gain_geometry is None:
                    gain_geometry = self._fallback_lower_region(
                        pair_engine,
                        baseline,
                        future,
                        geometry,
                    )
                if gain_geometry is None:
                    self._comparison_diagnostics["unresolved_comparisons"] = (
                        self._comparison_diagnostics.get("unresolved_comparisons", 0.0)
                        + 1.0
                    )
                    rebuilt[source_change].append((baseline, future, geometry))
                    continue

                gain_geometry = self._safe_intersection(geometry, gain_geometry)
                if gain_geometry is None:
                    self._comparison_diagnostics["unresolved_comparisons"] = (
                        self._comparison_diagnostics.get("unresolved_comparisons", 0.0)
                        + 1.0
                    )
                    rebuilt[source_change].append((baseline, future, geometry))
                    continue
                loss_geometry = self._safe_difference(geometry, gain_geometry)
                if loss_geometry is None:
                    self._comparison_diagnostics["unresolved_comparisons"] = (
                        self._comparison_diagnostics.get("unresolved_comparisons", 0.0)
                        + 1.0
                    )
                    rebuilt[source_change].append((baseline, future, geometry))
                    continue

                wrong_side_geometry = (
                    loss_geometry if source_change == "gain" else gain_geometry
                )
                if not self._has_area(wrong_side_geometry):
                    # Raw vertex extrema can include a zero-area GEOS boundary
                    # backtrack. Preserve the polygon when the analytic sign
                    # partition confirms that it has no wrong-side area.
                    rebuilt[source_change].append((baseline, future, geometry))
                    continue

                starts = {
                    change: len(rebuilt[change]) for change in ("gain", "loss")
                }
                self._append_parts(
                    rebuilt["gain"],
                    baseline,
                    future,
                    gain_geometry,
                    "gain",
                    clean_spikes=False,
                )
                self._append_parts(
                    rebuilt["loss"],
                    baseline,
                    future,
                    loss_geometry,
                    "loss",
                    clean_spikes=False,
                )
                new_geometries = [
                    item[2]
                    for change in ("gain", "loss")
                    for item in rebuilt[change][starts[change]:]
                ]
                coverage = self._union_geometries(new_geometries)
                coverage_error = (
                    geometry.area()
                    if coverage is None
                    else geometry.symDifference(coverage).area()
                )
                allowed_error = max(0.01, geometry.area() * 1e-9)
                if coverage_error > allowed_error:
                    self._comparison_diagnostics["unresolved_comparisons"] = (
                        self._comparison_diagnostics.get("unresolved_comparisons", 0.0)
                        + 1.0
                    )
                    self._comparison_diagnostics["unresolved_sign_area_m2"] = (
                        self._comparison_diagnostics.get("unresolved_sign_area_m2", 0.0)
                        + coverage_error
                    )
                    continue
        result["gain"] = rebuilt["gain"]
        result["loss"] = rebuilt["loss"]

    def _remove_final_boundary_backtracks(self, result) -> None:
        """Remove zero-area ring tendrils introduced by the final partition."""
        for change in ("gain", "loss", "no_change"):
            cleaned_parts = []
            for baseline, future, geometry in result.get(change, []):
                cleaned = self._remove_zero_area_boundary_backtracks(geometry)
                if self._has_area(cleaned):
                    cleaned_parts.append((baseline, future, cleaned))
            result[change] = cleaned_parts

    def _normalize_raw_classified_parts(self, result) -> None:
        """Normalize each raw controller pair once before coverage recovery."""
        for change in ("gain", "loss", "no_change"):
            grouped: Dict[Tuple[str, str], list] = {}
            controllers: Dict[
                Tuple[str, str],
                Tuple[ControllingOlsCandidate, ControllingOlsCandidate],
            ] = {}
            for baseline, future, geometry in result.get(change, []):
                if not self._has_area(geometry):
                    continue
                key = (baseline.surface_id, future.surface_id)
                grouped.setdefault(key, []).append(geometry)
                controllers[key] = (baseline, future)
            normalized_parts = []
            for key, geometries in grouped.items():
                merged = self._union_geometries(geometries)
                if not self._has_area(merged):
                    continue
                baseline, future = controllers[key]
                for part in self.baseline_engine._polygon_parts(merged):
                    if not self._has_area(part):
                        continue
                    classified = self._clip_geometry_to_change(
                        part,
                        baseline,
                        future,
                        change,
                    )
                    for classified_part in self.baseline_engine._polygon_parts(classified):
                        if not self._has_area(classified_part):
                            continue
                        delta_min, delta_max, delta_sample = self.delta_range(
                            classified_part,
                            baseline,
                            future,
                            change,
                        )
                        if delta_sample is None:
                            continue
                        if change == "gain" and (
                            delta_max is None or delta_max <= 0.0
                        ):
                            continue
                        if change == "loss" and (
                            delta_min is None or delta_min >= 0.0
                        ):
                            continue
                        if change == "no_change" and (
                            delta_min is None
                            or delta_max is None
                            or abs(delta_min) > self.tolerance_m
                            or abs(delta_max) > self.tolerance_m
                        ):
                            continue
                        normalized_parts.append(
                            (baseline, future, QgsGeometry(classified_part))
                        )
            result[change] = normalized_parts

    def _normalize_numerical_no_change_slivers(
        self,
        result,
        area_tolerance_m2: float,
    ) -> None:
        """Merge or suppress verified no-change remnants within audit tolerance."""
        items = list(result.get("no_change", []))
        while True:
            merged_one = False
            for source_index, (baseline, future, geometry) in enumerate(items):
                perimeter = geometry.length()
                if perimeter <= 0.0:
                    continue
                effective_width = (2.0 * geometry.area()) / perimeter
                if effective_width > COMPARISON_RECOVERY_SLIVER_MAX_EFFECTIVE_WIDTH_M:
                    continue
                candidates = []
                for target_index, (
                    target_baseline,
                    target_future,
                    target_geometry,
                ) in enumerate(items):
                    if target_index == source_index:
                        continue
                    if not self._bounding_boxes_intersect(geometry, target_geometry):
                        continue
                    shared_length = self._shared_boundary_length(
                        geometry,
                        target_geometry,
                    )
                    shared_fraction = shared_length / perimeter
                    if (
                        shared_length
                        < max(
                            COMPARISON_RECOVERY_SLIVER_MIN_SHARED_BOUNDARY_M,
                            10.0 * effective_width,
                        )
                        or shared_fraction
                        < COMPARISON_RECOVERY_SLIVER_MIN_SHARED_BOUNDARY_FRACTION
                    ):
                        continue
                    candidates.append((
                        -shared_length,
                        -target_geometry.area(),
                        target_index,
                        target_baseline,
                        target_future,
                        target_geometry,
                    ))
                if not candidates:
                    if geometry.area() <= area_tolerance_m2:
                        items.pop(source_index)
                        self._comparison_diagnostics[
                            "suppressed_no_change_slivers"
                        ] = (
                            self._comparison_diagnostics.get(
                                "suppressed_no_change_slivers",
                                0.0,
                            )
                            + 1.0
                        )
                        merged_one = True
                        break
                    continue
                candidates.sort(key=lambda item: item[:2])
                chosen = candidates[0]
                if (
                    len(candidates) > 1
                    and -chosen[0]
                    < -candidates[1][0]
                    * COMPARISON_RECOVERY_SLIVER_DOMINANT_CONTACT_RATIO
                ):
                    continue
                (
                    _negative_shared_length,
                    _negative_target_area,
                    target_index,
                    target_baseline,
                    target_future,
                    target_geometry,
                ) = chosen
                combined_geometry = self._union_geometries(
                    [geometry, target_geometry]
                )
                if (
                    not self._has_area(combined_geometry)
                    or not combined_geometry.isGeosValid()
                    or self.baseline_engine._polygon_part_count(combined_geometry)
                    > self.baseline_engine._polygon_part_count(target_geometry)
                ):
                    continue
                combined_baseline = self._combined_envelope_candidate(
                    [baseline, target_baseline],
                    combined_geometry,
                )
                combined_future = self._combined_envelope_candidate(
                    [future, target_future],
                    combined_geometry,
                )
                delta_min, delta_max, delta_sample = self.delta_range(
                    combined_geometry,
                    combined_baseline,
                    combined_future,
                    "no_change",
                )
                if (
                    delta_sample is None
                    or delta_min is None
                    or delta_max is None
                    or abs(delta_min) > self.tolerance_m
                    or abs(delta_max) > self.tolerance_m
                ):
                    continue
                items = [
                    item
                    for index, item in enumerate(items)
                    if index not in {source_index, target_index}
                ]
                items.append((
                    combined_baseline,
                    combined_future,
                    QgsGeometry(combined_geometry),
                ))
                self._comparison_diagnostics["merged_no_change_slivers"] = (
                    self._comparison_diagnostics.get(
                        "merged_no_change_slivers",
                        0.0,
                    )
                    + 1.0
                )
                merged_one = True
                break
            if not merged_one:
                break
        result["no_change"] = items

    def _remove_zero_area_boundary_backtracks(self, geometry: QgsGeometry) -> QgsGeometry:
        """Simplify collinear out-and-back edges without suppressing thin areas."""
        if geometry is None or geometry.isEmpty():
            return geometry
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return geometry
            if not geometry.isGeosValid():
                return geometry
            if geometry.isMultipart():
                polygons = [
                    self._remove_zero_area_polygon_backtracks(polygon)
                    for polygon in geometry.asMultiPolygon()
                ]
                cleaned = QgsGeometry.fromMultiPolygonXY(
                    [polygon for polygon in polygons if polygon]
                )
            else:
                polygon = self._remove_zero_area_polygon_backtracks(geometry.asPolygon())
                cleaned = QgsGeometry.fromPolygonXY(polygon) if polygon else QgsGeometry()
            if cleaned.isEmpty() or not cleaned.isGeosValid():
                return geometry
            area_change = abs(cleaned.area() - geometry.area())
            if area_change > COMPARISON_FINAL_BACKTRACK_MAX_AREA_CHANGE_M2:
                return geometry
            changed_area = geometry.symDifference(cleaned).area()
            if changed_area > COMPARISON_FINAL_BACKTRACK_MAX_AREA_CHANGE_M2:
                return geometry
            return cleaned
        except Exception:
            return geometry

    def _remove_zero_area_polygon_backtracks(self, polygon) -> list:
        if not polygon:
            return []
        cleaned = [self._remove_zero_area_backtracks_from_ring(polygon[0])]
        for ring in polygon[1:]:
            cleaned_ring = self._remove_zero_area_backtracks_from_ring(ring)
            if len(cleaned_ring) >= 4:
                cleaned.append(cleaned_ring)
        return cleaned if len(cleaned[0]) >= 4 else []

    def _remove_zero_area_backtracks_from_ring(self, ring) -> list:
        points = [QgsPointXY(point) for point in ring]
        if len(points) >= 2 and self._same_point(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            return []
        for _ in range(len(points)):
            removed = False
            count = len(points)
            if count < 4:
                break
            for index in range(count):
                if self._is_zero_area_backtrack_vertex(
                    points[(index - 1) % count],
                    points[index],
                    points[(index + 1) % count],
                ):
                    points.pop(index)
                    removed = True
                    break
            if not removed:
                break
        return points + [points[0]]

    @staticmethod
    def _is_zero_area_backtrack_vertex(
        previous_point: QgsPointXY,
        current_point: QgsPointXY,
        next_point: QgsPointXY,
    ) -> bool:
        ax = previous_point.x() - current_point.x()
        ay = previous_point.y() - current_point.y()
        bx = next_point.x() - current_point.x()
        by = next_point.y() - current_point.y()
        first_length = math.hypot(ax, ay)
        second_length = math.hypot(bx, by)
        if first_length <= 1e-9 or second_length <= 1e-9:
            return False
        cosine = (ax * bx + ay * by) / (first_length * second_length)
        angle_degrees = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        if angle_degrees > COMPARISON_COLLINEAR_BACKTRACK_ANGLE_DEGREES:
            return False
        triangle_area = abs((ax * by) - (ay * bx)) / 2.0
        return triangle_area <= COMPARISON_FINAL_BACKTRACK_MAX_AREA_CHANGE_M2

    def _dissolve_congruous_classified_parts(self, result) -> None:
        """Dissolve equal-range output parts carried by congruous surfaces.

        Controller IDs often change at an internal OLS seam even though the
        baseline and comparison elevation functions remain the same. Those
        seams add no information to a change layer. Grouping by both source
        surface definitions and the exported change range removes them without
        merging surfaces with different elevations or shapes.
        """
        for change in ("gain", "loss", "no_change"):
            grouped = {}
            unchanged = []
            for baseline, future, geometry in result.get(change, []):
                if not self._has_area(geometry):
                    continue
                baseline_surface = self._comparison_surface_key(baseline)
                future_surface = self._comparison_surface_key(future)
                delta_min, delta_max, _delta_sample = self.delta_range(
                    geometry,
                    baseline,
                    future,
                    change,
                )
                if (
                    baseline_surface is None
                    or future_surface is None
                    or delta_min is None
                    or delta_max is None
                ):
                    unchanged.append((baseline, future, geometry))
                    continue
                key = (
                    baseline_surface,
                    future_surface,
                    delta_min,
                    delta_max,
                )
                grouped.setdefault(key, []).append((baseline, future, geometry))

            dissolved = list(unchanged)
            for items in grouped.values():
                if len(items) == 1:
                    dissolved.append(items[0])
                    continue
                merged = self._union_geometries([item[2] for item in items])
                if not self._has_area(merged):
                    dissolved.extend(items)
                    continue
                merged = self._finalize_congruous_dissolve(
                    merged,
                    [item[2] for item in items],
                )
                baseline = self._combined_congruous_candidate(
                    [item[0] for item in items],
                    merged,
                )
                future = self._combined_congruous_candidate(
                    [item[1] for item in items],
                    merged,
                )
                dissolved.append((baseline, future, QgsGeometry(merged)))
            result[change] = dissolved

    def _dissolve_coplanar_classified_parts(self, result) -> None:
        """Compatibility wrapper for the former plane-only dissolve name."""
        self._dissolve_congruous_classified_parts(result)

    def _finalize_congruous_dissolve(
        self,
        geometry: QgsGeometry,
        source_geometries: Sequence[QgsGeometry],
    ) -> QgsGeometry:
        """Collapse numerical seams between congruous joined polygons."""
        source_area = geometry.area()
        allowed_area_change = max(
            COMPARISON_MIN_AREA_M2,
            source_area * COMPARISON_DISSOLVE_MAX_RELATIVE_AREA_CHANGE,
        )
        candidates = [QgsGeometry(geometry)]
        try:
            snapped_parts = [
                source.snappedToGrid(
                    COMPARISON_DISSOLVE_GRID_M,
                    COMPARISON_DISSOLVE_GRID_M,
                )
                for source in source_geometries
                if source is not None and not source.isEmpty()
            ]
            snapped_union = QgsGeometry.unaryUnion(snapped_parts)
            if snapped_union is not None and not snapped_union.isEmpty():
                candidates.append(snapped_union)
        except Exception:
            pass

        finalized = []
        for candidate in candidates:
            try:
                buffered = candidate.buffer(0.0, 8)
                if buffered is not None and not buffered.isEmpty():
                    candidate = buffered
            except Exception:
                pass
            candidate = self._remove_zero_area_boundary_backtracks(candidate)
            candidate = self._remove_dissolve_remnant_holes(candidate)
            if (
                self._has_area(candidate)
                and candidate.isGeosValid()
                and abs(candidate.area() - source_area) <= allowed_area_change
            ):
                finalized.append(candidate)
        if not finalized:
            return geometry
        return min(
            finalized,
            key=lambda candidate: (
                len(self.baseline_engine._polygon_parts(candidate)),
                abs(candidate.area() - source_area),
            ),
        )

    def _comparison_surface_key(
        self,
        candidate: ControllingOlsCandidate,
    ) -> Optional[Tuple[object, ...]]:
        """Return a model-aware key for an equivalent elevation function."""
        plane = self._candidate_affine_coefficients(candidate)
        if plane is not None:
            return ("affine", *self._comparison_plane_key(plane))
        if candidate.model != "conical":
            return None
        metadata = candidate.metadata or {}
        try:
            base_footprint = QgsGeometry(metadata["base_footprint"])
            if base_footprint.isEmpty():
                return None
            base_footprint.normalize()
            max_distance = metadata.get("max_distance_m")
            return (
                "conical",
                bytes(base_footprint.asWkb()),
                round(float(metadata["base_elevation_m"]), 9),
                round(float(metadata["slope"]), 9),
                None if max_distance is None else round(float(max_distance), 9),
            )
        except (KeyError, TypeError, ValueError, RuntimeError):
            return None

    @staticmethod
    def _remove_dissolve_remnant_holes(geometry: QgsGeometry) -> QgsGeometry:
        """Remove collapsed interior rings left by a polygon union."""
        if geometry is None or geometry.isEmpty():
            return geometry
        try:
            polygons = (
                geometry.asMultiPolygon()
                if geometry.isMultipart()
                else [geometry.asPolygon()]
            )
            cleaned_polygons = []
            removed = False
            for polygon in polygons:
                if not polygon:
                    continue
                cleaned = [polygon[0]]
                for ring in polygon[1:]:
                    ring_geometry = QgsGeometry.fromPolygonXY([ring])
                    if abs(ring_geometry.area()) < COMPARISON_MIN_AREA_M2:
                        removed = True
                        continue
                    cleaned.append(ring)
                cleaned_polygons.append(cleaned)
            if not removed or not cleaned_polygons:
                return geometry
            cleaned_geometry = (
                QgsGeometry.fromMultiPolygonXY(cleaned_polygons)
                if geometry.isMultipart()
                else QgsGeometry.fromPolygonXY(cleaned_polygons[0])
            )
            if cleaned_geometry.isEmpty() or not cleaned_geometry.isGeosValid():
                return geometry
            return cleaned_geometry
        except (TypeError, RuntimeError):
            return geometry

    @staticmethod
    def _comparison_plane_key(
        coefficients: Tuple[float, float, float],
    ) -> Tuple[float, float, float]:
        """Return a stable key for planes derived through equivalent formulas."""
        return tuple(round(float(value), 9) for value in coefficients)

    @staticmethod
    def _combined_congruous_candidate(
        candidates: Sequence[ControllingOlsCandidate],
        footprint: QgsGeometry,
    ) -> ControllingOlsCandidate:
        """Retain all source IDs while using one equivalent surface evaluator."""
        representative = candidates[0]
        surface_ids = sorted({candidate.surface_id for candidate in candidates})
        surface_types = sorted({candidate.surface_type for candidate in candidates})
        if len(surface_ids) == 1 and len(surface_types) == 1:
            return representative
        return ControllingOlsCandidate(
            surface_id="; ".join(surface_ids),
            surface_type="; ".join(surface_types),
            footprint=QgsGeometry(footprint),
            elevation_at_xy=representative.elevation_at_xy,
            model=representative.model,
            metadata=dict(representative.metadata or {}),
        )

    @staticmethod
    def _combined_envelope_candidate(
        candidates: Sequence[ControllingOlsCandidate],
        footprint: QgsGeometry,
    ) -> ControllingOlsCandidate:
        """Combine adjacent controller provenance using their lower envelope."""
        unique = {
            candidate.surface_id: candidate
            for candidate in candidates
        }
        ordered = [unique[surface_id] for surface_id in sorted(unique)]
        if len(ordered) == 1:
            return ordered[0]

        def elevation_at_xy(point: QgsPointXY) -> Optional[float]:
            elevations = []
            for candidate in ordered:
                try:
                    if not candidate.contains_xy(point):
                        continue
                    elevation = candidate.elevation_at_xy(point)
                except Exception:
                    continue
                if elevation is not None and math.isfinite(float(elevation)):
                    elevations.append(float(elevation))
            return min(elevations) if elevations else None

        return ControllingOlsCandidate(
            surface_id="; ".join(candidate.surface_id for candidate in ordered),
            surface_type="; ".join(sorted({
                candidate.surface_type for candidate in ordered
            })),
            footprint=QgsGeometry(footprint),
            elevation_at_xy=elevation_at_xy,
            model="composite",
            metadata={
                "source_surface_ids": [
                    candidate.surface_id for candidate in ordered
                ],
            },
        )

    def _clip_geometry_to_change(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> QgsGeometry:
        """Enforce the height-sign invariant on a final gain or loss polygon."""
        if geometry is None or geometry.isEmpty() or change not in {"gain", "loss"}:
            return geometry
        lower_candidate, upper_candidate = (
            (baseline, future) if change == "gain" else (future, baseline)
        )
        pair_engine = PlanarControllingOlsEngine(
            [lower_candidate, upper_candidate],
            # Final comparison polygons already include their canonical
            # equality edge. Treat sub-centimetre contour residuals as tied so
            # each side is not independently re-meshed along a new chord.
            tie_tolerance_m=self.tolerance_m,
        )
        try:
            decision = pair_engine._sampled_lower_decision(
                lower_candidate,
                upper_candidate,
                geometry,
                dense=True,
            )
        except Exception:
            decision = None
        if decision == "all_lower":
            return geometry
        if decision == "all_higher":
            return QgsGeometry()

        try:
            lower_region = pair_engine._candidate_lower_region(
                lower_candidate,
                upper_candidate,
                geometry,
            )
        except Exception:
            lower_region = None
        if lower_region is not None:
            if lower_region.isEmpty():
                return QgsGeometry()
            clipped = self._safe_intersection(geometry, lower_region)
            if self._has_area(clipped):
                # The direct lower-region solver is exact for supported linear
                # and conical pairings. Trust that equation-based clip instead
                # of densifying it through an unnecessary triangulation pass.
                return clipped
        else:
            clipped = None

        # Curved or topologically awkward rings can remain mixed after an
        # unresolved analytic comparison. Rebuild only that residual part from
        # locally clipped triangles; this is independent of map scale/CRS.
        source = geometry
        try:
            triangulated = pair_engine._triangulated_candidate_lower_region(
                lower_candidate,
                upper_candidate,
                source,
            )
        except Exception:
            triangulated = None
        triangulated = self._safe_intersection(source, triangulated) if triangulated is not None else None
        if self._has_area(triangulated):
            return triangulated
        return clipped if clipped is not None else geometry

    def _finalise_comparison_parts(self, result) -> None:
        """Apply final geometry hygiene before common-domain coverage repair."""
        for change in ("gain", "loss", "no_change"):
            final_parts = []
            for baseline, future, geometry in result.get(change, []):
                cleaned = self._clean_comparison_part(geometry, baseline, future, change)
                if not self._has_area(cleaned):
                    continue
                delta_min, delta_max, delta_sample = self.delta_range(
                    cleaned,
                    baseline,
                    future,
                    change,
                )
                if delta_sample is None:
                    continue
                if change == "gain" and delta_sample <= 0.0:
                    continue
                if change == "loss" and delta_sample >= 0.0:
                    continue
                if change == "no_change":
                    if delta_min is None or delta_max is None:
                        continue
                    if abs(delta_min) > self.tolerance_m or abs(delta_max) > self.tolerance_m:
                        continue
                final_parts.append((baseline, future, cleaned))
            result[change] = final_parts

    def _classify_change_for_part(
        self,
        geometry: QgsGeometry,
        baseline_candidate: ControllingOlsCandidate,
        future_candidate: ControllingOlsCandidate,
    ) -> Optional[str]:
        delta_min, delta_max, delta_sample = self.delta_range(
            geometry,
            baseline_candidate,
            future_candidate,
        )
        if delta_sample is None:
            return None
        if (
            delta_min is not None
            and delta_max is not None
            and abs(delta_min) <= self.tolerance_m
            and abs(delta_max) <= self.tolerance_m
        ):
            return "no_change"
        if delta_sample > 0.0:
            return "gain"
        if delta_sample < 0.0:
            return "loss"
        if delta_max is not None and delta_max > 0.0:
            return "gain"
        if delta_min is not None and delta_min < 0.0:
            return "loss"
        return "no_change"

    def _sample_points(
        self,
        geometry: QgsGeometry,
        baseline: Optional[ControllingOlsCandidate] = None,
        future: Optional[ControllingOlsCandidate] = None,
        change: Optional[str] = None,
    ) -> List[QgsPointXY]:
        points: List[QgsPointXY] = []
        affine_pair = bool(
            baseline is not None
            and future is not None
            and self._candidate_affine_coefficients(baseline) is not None
            and self._candidate_affine_coefficients(future) is not None
        )
        try:
            representative = geometry.pointOnSurface()
            if representative is not None and not representative.isEmpty():
                point = representative.asPoint()
                points.append(QgsPointXY(point.x(), point.y()))
        except Exception:
            pass
        if baseline is not None and future is not None and change:
            if affine_pair:
                # Affine differences attain their exact extrema at polygon
                # vertices.  Do not run those vertices through the generic
                # spike-shape filter: a long, acute but legitimate controller
                # wedge (such as the YMML approach-adjacent transitional
                # region) can look like a spike and lose its true maximum.
                # Excluding only vertices on the wrong side of the classified
                # change retains protection against zero-area GEOS tendrils.
                affine_vertices = []
                try:
                    for vertex in geometry.vertices():
                        point = QgsPointXY(vertex.x(), vertex.y())
                        delta = self._delta_at_point(point, baseline, future)
                        if delta is None:
                            continue
                        if change == "gain" and delta < -self.tolerance_m:
                            continue
                        if change == "loss" and delta > self.tolerance_m:
                            continue
                        if change == "no_change" and abs(delta) > self.tolerance_m:
                            continue
                        affine_vertices.append(point)
                except Exception:
                    affine_vertices = []
                if affine_vertices:
                    points.extend(affine_vertices)
                    return points
            comparison_vertices = self._comparison_sample_vertices(
                geometry,
                baseline,
                future,
                change,
            )
            if comparison_vertices:
                points.extend(comparison_vertices)
                return points
        try:
            vertices = list(geometry.vertices())
            if not affine_pair and len(vertices) > 48:
                step = max(1, len(vertices) // 48)
                vertices = vertices[::step]
            points.extend(QgsPointXY(vertex.x(), vertex.y()) for vertex in vertices)
        except Exception:
            pass
        return points

    def _comparison_sample_vertices(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> List[QgsPointXY]:
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return []
            rings = []
            if geometry.isMultipart():
                for polygon in geometry.asMultiPolygon():
                    for ring_index, ring in enumerate(polygon):
                        rings.append((ring, ring_index == 0))
            else:
                for ring_index, ring in enumerate(geometry.asPolygon()):
                    rings.append((ring, ring_index == 0))
            vertices: List[QgsPointXY] = []
            for ring, is_exterior in rings:
                if not ring:
                    continue
                filtered = self._filtered_comparison_sample_ring(
                    ring,
                    is_exterior,
                    baseline,
                    future,
                    change,
                )
                vertices.extend(filtered)
            if len(vertices) > 48:
                step = max(1, len(vertices) // 48)
                vertices = vertices[::step]
            return vertices
        except Exception:
            return []

    def _filtered_comparison_sample_ring(
        self,
        ring,
        exterior: bool,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> List[QgsPointXY]:
        points = [QgsPointXY(point) for point in ring]
        if len(points) >= 2 and self._same_point(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            return []
        if not exterior:
            return points
        filtered = list(points)
        for _ in range(24):
            removed = False
            count = len(filtered)
            if count < 4:
                break
            for index in range(count):
                previous_point = filtered[(index - 1) % count]
                current_point = filtered[index]
                next_point = filtered[(index + 1) % count]
                if self._comparison_spike_vertex_kind(
                    previous_point,
                    current_point,
                    next_point,
                    baseline,
                    future,
                    change,
                ):
                    filtered.pop(index)
                    removed = True
                    break
            if not removed:
                break
        return filtered

    @staticmethod
    def _bounding_boxes_intersect(first: QgsGeometry, second: QgsGeometry) -> bool:
        try:
            return first.boundingBox().intersects(second.boundingBox())
        except Exception:
            return True

    @staticmethod
    def _has_area(geometry: Optional[QgsGeometry]) -> bool:
        return bool(
            geometry is not None
            and not geometry.isEmpty()
            and geometry.area() > COMPARISON_MIN_AREA_M2
        )

    @staticmethod
    def _has_no_overlay_area(geometry: Optional[QgsGeometry]) -> bool:
        return bool(
            geometry is not None
            and not geometry.isEmpty()
            and geometry.area() >= COMPARISON_NO_OVERLAY_MIN_AREA_M2
        )

    def _comparison_coverage_geometry(self, geometry: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return geometry
        coverage = QgsGeometry(geometry)
        try:
            coverage = coverage.buffer(COMPARISON_NO_OVERLAY_COVERAGE_TOLERANCE_M, 4)
        except Exception:
            pass
        return self._normalise_no_overlay_geometry(coverage)

    def _no_overlay_part_has_tolerant_core(
        self,
        exact_part: QgsGeometry,
        tolerant_remaining: Optional[QgsGeometry],
    ) -> bool:
        if not self._has_no_overlay_area(exact_part):
            return False
        if tolerant_remaining is None:
            return True
        if tolerant_remaining.isEmpty():
            return False
        try:
            core = exact_part.intersection(tolerant_remaining)
        except Exception:
            return True
        return self._has_no_overlay_area(core)

    def _normalise_no_overlay_geometry(self, geometry: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return geometry
        normalised = QgsGeometry(geometry)
        try:
            normalised = normalised.snappedToGrid(
                COMPARISON_NO_OVERLAY_GRID_M,
                COMPARISON_NO_OVERLAY_GRID_M,
            )
        except Exception:
            pass
        try:
            if normalised is not None and not normalised.isEmpty() and not normalised.isGeosValid():
                normalised = normalised.makeValid()
        except Exception:
            pass
        try:
            buffered = normalised.buffer(0.0, 8)
            if buffered is not None and not buffered.isEmpty():
                normalised = buffered
        except Exception:
            pass
        return normalised

    def _clean_comparison_part(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> QgsGeometry:
        """Remove split artefact spikes without treating removed area as classified."""
        if geometry is None or geometry.isEmpty():
            return geometry
        original_area = geometry.area()
        if original_area < COMPARISON_MIN_AREA_M2:
            return QgsGeometry()
        cleaned, removed_severe_spike = self._remove_comparison_ring_spikes(
            geometry,
            baseline,
            future,
            change,
        )
        if cleaned is None or cleaned.isEmpty():
            return geometry
        try:
            source_geometry = QgsGeometry(geometry)
            if not source_geometry.isGeosValid():
                source_geometry = source_geometry.makeValid()
            cleaned = cleaned.intersection(source_geometry)
            if cleaned is not None and not cleaned.isEmpty() and not cleaned.isGeosValid():
                cleaned = cleaned.makeValid()
        except Exception:
            return geometry
        area_change = abs(cleaned.area() - original_area)
        allowed_change = max(
            COMPARISON_SPIKE_MAX_AREA_CHANGE_M2,
            original_area * COMPARISON_SPIKE_MAX_AREA_CHANGE_RATIO,
        )
        source_violation = self._comparison_sign_violation_m(
            geometry,
            baseline,
            future,
            change,
        )
        cleaned_violation = self._comparison_sign_violation_m(
            cleaned,
            baseline,
            future,
            change,
        )
        if (
            cleaned_violation is not None
            and source_violation is not None
            and cleaned_violation > max(self.tolerance_m, source_violation) + 1e-9
        ):
            return geometry
        if removed_severe_spike or area_change <= allowed_change:
            return cleaned
        return geometry

    def _comparison_sign_violation_m(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Optional[float]:
        """Return the sampled height-sign violation without class-specific filtering."""
        delta_min, delta_max, _delta_sample = self.delta_range(
            geometry,
            baseline,
            future,
        )
        if delta_min is None or delta_max is None:
            return None
        if change == "gain":
            return max(0.0, -delta_min)
        if change == "loss":
            return max(0.0, delta_max)
        if change == "no_change":
            return max(abs(delta_min), abs(delta_max))
        return None

    def _remove_comparison_ring_spikes(
        self,
        geometry: QgsGeometry,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Tuple[Optional[QgsGeometry], bool]:
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return geometry, False
            removed_severe_spike = False
            if geometry.isMultipart():
                cleaned_polygons = []
                for polygon in geometry.asMultiPolygon():
                    cleaned, removed = self._clean_comparison_polygon_rings(
                        polygon,
                        baseline,
                        future,
                        change,
                    )
                    removed_severe_spike = removed_severe_spike or removed
                    if cleaned:
                        cleaned_polygons.append(cleaned)
                geometry = (
                    QgsGeometry.fromMultiPolygonXY(cleaned_polygons)
                    if cleaned_polygons
                    else QgsGeometry()
                )
                return geometry, removed_severe_spike
            cleaned_polygon, removed_severe_spike = self._clean_comparison_polygon_rings(
                geometry.asPolygon(),
                baseline,
                future,
                change,
            )
            geometry = QgsGeometry.fromPolygonXY(cleaned_polygon) if cleaned_polygon else QgsGeometry()
            return geometry, removed_severe_spike
        except Exception:
            return geometry, False

    def _clean_comparison_polygon_rings(
        self,
        polygon,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Tuple[list, bool]:
        if not polygon:
            return [], False
        exterior, removed_severe_spike = self._clean_comparison_ring(
            polygon[0],
            True,
            baseline,
            future,
            change,
        )
        cleaned = [exterior]
        for ring in polygon[1:]:
            cleaned_ring, removed = self._clean_comparison_ring(
                ring,
                False,
                baseline,
                future,
                change,
            )
            removed_severe_spike = removed_severe_spike or removed
            if len(cleaned_ring) >= 4:
                cleaned.append(cleaned_ring)
        return (cleaned if len(cleaned[0]) >= 4 else []), removed_severe_spike

    def _clean_comparison_ring(
        self,
        ring,
        exterior: bool,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Tuple[list, bool]:
        if not ring:
            return [], False
        points = [QgsPointXY(point) for point in ring]
        if len(points) >= 2 and self._same_point(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            return [], False
        if not exterior:
            return points + [points[0]], False
        removed_severe_spike = False
        for _ in range(24):
            removed = False
            count = len(points)
            if count < 4:
                break
            for index in range(count):
                previous_point = points[(index - 1) % count]
                current_point = points[index]
                next_point = points[(index + 1) % count]
                spike_kind = self._comparison_spike_vertex_kind(
                    previous_point,
                    current_point,
                    next_point,
                    baseline,
                    future,
                    change,
                )
                if spike_kind:
                    removed_severe_spike = removed_severe_spike or spike_kind == "severe"
                    points.pop(index)
                    removed = True
                    break
            if not removed:
                break
        return points + [points[0]], removed_severe_spike

    def _clean_no_overlay_part(self, geometry: QgsGeometry) -> QgsGeometry:
        """Remove small overlay artefacts without materially changing real no-overlay areas."""
        if geometry is None or geometry.isEmpty():
            return geometry
        original_area = geometry.area()
        if original_area < COMPARISON_NO_OVERLAY_MIN_AREA_M2:
            return QgsGeometry()
        cleaned = self._remove_no_overlay_ring_spikes(geometry)
        if cleaned is None or cleaned.isEmpty():
            return geometry
        area_change = abs(cleaned.area() - original_area)
        allowed_change = max(
            COMPARISON_SPIKE_MAX_AREA_CHANGE_M2,
            original_area * COMPARISON_SPIKE_MAX_AREA_CHANGE_RATIO,
        )
        if area_change <= allowed_change:
            return cleaned
        return geometry

    def _remove_no_overlay_ring_spikes(self, geometry: QgsGeometry) -> Optional[QgsGeometry]:
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return geometry
            if geometry.isMultipart():
                polygons = geometry.asMultiPolygon()
                cleaned_polygons = []
                for polygon in polygons:
                    cleaned = self._clean_no_overlay_polygon_rings(polygon)
                    if cleaned:
                        cleaned_polygons.append(cleaned)
                return QgsGeometry.fromMultiPolygonXY(cleaned_polygons) if cleaned_polygons else QgsGeometry()
            polygon = geometry.asPolygon()
            cleaned_polygon = self._clean_no_overlay_polygon_rings(polygon)
            return QgsGeometry.fromPolygonXY(cleaned_polygon) if cleaned_polygon else QgsGeometry()
        except Exception:
            return geometry

    def _clean_no_overlay_polygon_rings(self, polygon) -> list:
        if not polygon:
            return []
        cleaned = [self._clean_no_overlay_ring(polygon[0], exterior=True)]
        for ring in polygon[1:]:
            cleaned_ring = self._clean_no_overlay_ring(ring, exterior=False)
            if len(cleaned_ring) >= 4:
                cleaned.append(cleaned_ring)
        return cleaned if len(cleaned[0]) >= 4 else []

    def _clean_no_overlay_ring(self, ring, exterior: bool) -> list:
        if not ring:
            return []
        points = [QgsPointXY(point) for point in ring]
        if len(points) >= 2 and self._same_point(points[0], points[-1]):
            points = points[:-1]
        if len(points) < 3:
            return []
        # Interior rings are left alone except for duplicate/near-duplicate
        # closure handling; removing hole vertices risks changing semantics.
        if not exterior:
            return points + [points[0]]
        for _ in range(12):
            removed = False
            count = len(points)
            if count < 4:
                break
            for index in range(count):
                previous_point = points[(index - 1) % count]
                current_point = points[index]
                next_point = points[(index + 1) % count]
                if self._is_no_overlay_spike_vertex(previous_point, current_point, next_point):
                    points.pop(index)
                    removed = True
                    break
            if not removed:
                break
        return points + [points[0]]

    @staticmethod
    def _same_point(first: QgsPointXY, second: QgsPointXY) -> bool:
        return (
            abs(first.x() - second.x()) <= 1e-9
            and abs(first.y() - second.y()) <= 1e-9
        )

    @staticmethod
    def _is_no_overlay_spike_vertex(
        previous_point: QgsPointXY,
        current_point: QgsPointXY,
        next_point: QgsPointXY,
    ) -> bool:
        first_length = math.hypot(
            previous_point.x() - current_point.x(),
            previous_point.y() - current_point.y(),
        )
        second_length = math.hypot(
            next_point.x() - current_point.x(),
            next_point.y() - current_point.y(),
        )
        base_length = math.hypot(
            previous_point.x() - next_point.x(),
            previous_point.y() - next_point.y(),
        )
        if first_length <= 1e-9 or second_length <= 1e-9 or base_length <= 1e-9:
            return False
        if base_length > COMPARISON_SPIKE_BASE_MAX_M:
            return False
        detour_ratio = (first_length + second_length) / base_length
        if detour_ratio < COMPARISON_SPIKE_DETOUR_RATIO:
            return False
        cosine = (
            (first_length * first_length)
            + (second_length * second_length)
            - (base_length * base_length)
        ) / (2.0 * first_length * second_length)
        angle_degrees = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        if angle_degrees > COMPARISON_SPIKE_ANGLE_DEGREES:
            return False
        semi_perimeter = (first_length + second_length + base_length) / 2.0
        triangle_area = math.sqrt(
            max(
                0.0,
                semi_perimeter
                * (semi_perimeter - first_length)
                * (semi_perimeter - second_length)
                * (semi_perimeter - base_length),
            )
        )
        height = (2.0 * triangle_area / base_length) if base_length > 0.0 else 0.0
        return height >= COMPARISON_SPIKE_HEIGHT_MIN_M or angle_degrees <= 2.0

    def _comparison_spike_vertex_kind(
        self,
        previous_point: QgsPointXY,
        current_point: QgsPointXY,
        next_point: QgsPointXY,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
        change: str,
    ) -> Optional[str]:
        metrics = self._comparison_spike_metrics(previous_point, current_point, next_point)
        if metrics is None:
            return None
        _detour_ratio, angle_degrees, _height, _base_length = metrics
        current_delta = self._delta_at_point(current_point, baseline, future)
        previous_delta = self._delta_at_point(previous_point, baseline, future)
        next_delta = self._delta_at_point(next_point, baseline, future)
        neighbour_values = [
            value for value in (previous_delta, next_delta)
            if value is not None and math.isfinite(value)
        ]
        # GEOS polygon differences can retain a zero-area boundary tendril: the
        # ring overshoots onto the wrong side of the equality boundary and then
        # reverses along the same line.  Its 0-degree turn is definitive, so it
        # must not be constrained by the general spike base-length thresholds.
        if (
            angle_degrees <= COMPARISON_COLLINEAR_BACKTRACK_ANGLE_DEGREES
            and current_delta is not None
            and neighbour_values
        ):
            if change == "loss" and current_delta > self.tolerance_m and any(
                value <= self.tolerance_m for value in neighbour_values
            ):
                return "backtrack"
            if change == "gain" and current_delta < -self.tolerance_m and any(
                value >= -self.tolerance_m for value in neighbour_values
            ):
                return "backtrack"
            if change == "no_change" and abs(current_delta) > self.tolerance_m and any(
                abs(value) <= self.tolerance_m for value in neighbour_values
            ):
                return "backtrack"
        if self._is_severe_comparison_spike_shape(metrics):
            return "severe"
        if not self._is_delta_comparison_spike_shape(metrics):
            return None
        if current_delta is None:
            return None
        if not neighbour_values:
            return None
        if change == "loss":
            return "delta" if (
                current_delta > self.tolerance_m
                and any(value <= self.tolerance_m for value in neighbour_values)
            ) else None
        if change == "gain":
            return "delta" if (
                current_delta < -self.tolerance_m
                and any(value >= -self.tolerance_m for value in neighbour_values)
            ) else None
        if change == "no_change":
            return "delta" if (
                abs(current_delta) > self.tolerance_m
                and any(abs(value) <= self.tolerance_m for value in neighbour_values)
            ) else None
        return None

    @staticmethod
    def _comparison_spike_metrics(
        previous_point: QgsPointXY,
        current_point: QgsPointXY,
        next_point: QgsPointXY,
    ) -> Optional[Tuple[float, float, float, float]]:
        first_length = math.hypot(
            previous_point.x() - current_point.x(),
            previous_point.y() - current_point.y(),
        )
        second_length = math.hypot(
            next_point.x() - current_point.x(),
            next_point.y() - current_point.y(),
        )
        base_length = math.hypot(
            previous_point.x() - next_point.x(),
            previous_point.y() - next_point.y(),
        )
        if first_length <= 1e-9 or second_length <= 1e-9 or base_length <= 1e-9:
            return None
        detour_ratio = (first_length + second_length) / base_length
        cosine = (
            (first_length * first_length)
            + (second_length * second_length)
            - (base_length * base_length)
        ) / (2.0 * first_length * second_length)
        angle_degrees = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        semi_perimeter = (first_length + second_length + base_length) / 2.0
        triangle_area = math.sqrt(
            max(
                0.0,
                semi_perimeter
                * (semi_perimeter - first_length)
                * (semi_perimeter - second_length)
                * (semi_perimeter - base_length),
            )
        )
        height = (2.0 * triangle_area / base_length) if base_length > 0.0 else 0.0
        return detour_ratio, angle_degrees, height, base_length

    @staticmethod
    def _is_delta_comparison_spike_shape(metrics: Tuple[float, float, float, float]) -> bool:
        detour_ratio, angle_degrees, _height, base_length = metrics
        return (
            base_length <= COMPARISON_SPIKE_BASE_MAX_M
            and detour_ratio >= COMPARISON_SPIKE_DETOUR_RATIO
            and angle_degrees <= COMPARISON_SPIKE_ANGLE_DEGREES
        )

    @staticmethod
    def _is_severe_comparison_spike_shape(metrics: Tuple[float, float, float, float]) -> bool:
        detour_ratio, angle_degrees, height, _base_length = metrics
        if (
            detour_ratio >= COMPARISON_SEVERE_SPIKE_DETOUR_RATIO
            and height >= COMPARISON_SPIKE_HEIGHT_MIN_M
            and angle_degrees <= COMPARISON_SEVERE_SPIKE_ANGLE_DEGREES
        ):
            return True
        if detour_ratio >= 20.0:
            return height >= 10.0 and angle_degrees <= COMPARISON_SPIKE_ANGLE_DEGREES
        return detour_ratio >= 50.0 and angle_degrees <= 2.0

    @staticmethod
    def _delta_at_point(
        point: QgsPointXY,
        baseline: ControllingOlsCandidate,
        future: ControllingOlsCandidate,
    ) -> Optional[float]:
        baseline_z = baseline.elevation_at_xy(point)
        future_z = future.elevation_at_xy(point)
        if baseline_z is None or future_z is None:
            return None
        delta = float(future_z) - float(baseline_z)
        return delta if math.isfinite(delta) else None

    @staticmethod
    def _round_delta(delta: float) -> float:
        rounded = round(float(delta), COMPARISON_DELTA_DECIMALS)
        return 0.0 if rounded == 0 else rounded

    def _prepare_overlay_geometry(self, geometry: Optional[QgsGeometry]) -> Optional[QgsGeometry]:
        """Return valid polygonal geometry suitable for a retrying GEOS overlay."""
        if geometry is None or geometry.isEmpty():
            return geometry
        prepared = QgsGeometry(geometry)
        try:
            if not prepared.isGeosValid():
                prepared = prepared.makeValid()
        except Exception:
            pass
        parts = self.baseline_engine._polygon_parts(prepared)
        if not parts:
            return None
        try:
            prepared = QgsGeometry.unaryUnion(parts) if len(parts) > 1 else QgsGeometry(parts[0])
        except Exception:
            prepared = QgsGeometry(parts[0])
            for part in parts[1:]:
                try:
                    combined = prepared.combine(part)
                    if combined is not None and not combined.isEmpty():
                        prepared = combined
                except Exception:
                    continue
        try:
            if prepared is not None and not prepared.isEmpty() and not prepared.isGeosValid():
                prepared = prepared.makeValid()
        except Exception:
            pass
        return prepared

    def _safe_intersection(
        self,
        first: Optional[QgsGeometry],
        second: Optional[QgsGeometry],
    ) -> Optional[QgsGeometry]:
        if first is None or second is None or first.isEmpty() or second.isEmpty():
            return QgsGeometry()
        intersection = None
        try:
            inputs_valid = first.isGeosValid() and second.isGeosValid()
        except Exception:
            inputs_valid = False
        if inputs_valid:
            try:
                intersection = first.intersection(second)
                if intersection is not None and (intersection.isEmpty() or intersection.isGeosValid()):
                    return intersection
            except Exception:
                intersection = None
        prepared_first = self._prepare_overlay_geometry(first)
        prepared_second = self._prepare_overlay_geometry(second)
        if prepared_first is None or prepared_second is None:
            return intersection
        try:
            return prepared_first.intersection(prepared_second)
        except Exception:
            return intersection

    def _safe_difference(
        self,
        first: Optional[QgsGeometry],
        second: Optional[QgsGeometry],
    ) -> Optional[QgsGeometry]:
        if first is None or first.isEmpty():
            return QgsGeometry()
        if second is None or second.isEmpty():
            return QgsGeometry(first)
        difference = None
        try:
            inputs_valid = first.isGeosValid() and second.isGeosValid()
        except Exception:
            inputs_valid = False
        if inputs_valid:
            try:
                difference = first.difference(second)
                if difference is not None and (difference.isEmpty() or difference.isGeosValid()):
                    return difference
            except Exception:
                difference = None
        prepared_first = self._prepare_overlay_geometry(first)
        prepared_second = self._prepare_overlay_geometry(second)
        if prepared_first is None:
            return difference
        if prepared_second is None:
            return QgsGeometry(prepared_first)
        try:
            return prepared_first.difference(prepared_second)
        except Exception:
            return difference

    def _union_geometries(self, geometries: Sequence[QgsGeometry]) -> Optional[QgsGeometry]:
        """Union valid polygon parts, repairing invalid inputs before coverage tests."""
        non_empty: List[QgsGeometry] = []
        for geometry in geometries:
            if geometry is None or geometry.isEmpty():
                continue
            non_empty.extend(self.baseline_engine._polygon_parts(QgsGeometry(geometry)))
        if not non_empty:
            return None
        try:
            merged = QgsGeometry.unaryUnion(non_empty)
            if merged is not None and not merged.isEmpty():
                return merged
        except Exception:
            pass
        merged = QgsGeometry(non_empty[0])
        for geometry in non_empty[1:]:
            try:
                combined = merged.combine(geometry)
                if combined is not None and not combined.isEmpty():
                    merged = combined
            except Exception:
                pass
        return merged

    @staticmethod
    def _line_parts(geometry: QgsGeometry) -> List[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return []
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Line:
                parts: List[QgsGeometry] = []
                if hasattr(geometry, "asGeometryCollection"):
                    for part_geometry in geometry.asGeometryCollection():
                        parts.extend(OlsEnvelopeComparisonEngine._line_parts(part_geometry))
                return parts
        except Exception:
            return [geometry]
        if not geometry.isMultipart():
            return [geometry]
        parts: List[QgsGeometry] = []
        try:
            for line in geometry.asMultiPolyline():
                if line:
                    parts.append(QgsGeometry.fromPolylineXY(line))
        except Exception:
            pass
        return parts


class OlsModernisationComparisonMixin:
    """Create user-facing OFS/OES modernisation comparison layers."""

    def _modernisation_change_contour_intervals(self, family: str) -> Tuple[float, float]:
        """Return intermediate and primary signed-change contour intervals."""
        family_key = str(family or "").strip().upper()
        contour_key = {
            "OLS": "comparison_change",
            "OFS": "modernisation_ofs_change",
            "OES": "modernisation_oes_change",
        }.get(family_key)
        if contour_key is None:
            intermediate_getter = getattr(self, "_get_contour_interval", None)
            primary_getter = getattr(self, "_get_primary_contour_interval", None)
            intermediate = (
                intermediate_getter("default", COMPARISON_CONTOUR_INTERVAL_M)
                if callable(intermediate_getter)
                else COMPARISON_CONTOUR_INTERVAL_M
            )
            primary = (
                primary_getter("default", COMPARISON_PRIMARY_CONTOUR_INTERVAL_M)
                if callable(primary_getter)
                else COMPARISON_PRIMARY_CONTOUR_INTERVAL_M
            )
            return float(intermediate), float(primary)
        intermediate_getter = getattr(self, "_get_contour_interval", None)
        primary_getter = getattr(self, "_get_primary_contour_interval", None)
        intermediate = (
            intermediate_getter(contour_key, COMPARISON_CONTOUR_INTERVAL_M)
            if callable(intermediate_getter)
            else COMPARISON_CONTOUR_INTERVAL_M
        )
        primary = (
            primary_getter(contour_key, COMPARISON_PRIMARY_CONTOUR_INTERVAL_M)
            if callable(primary_getter)
            else COMPARISON_PRIMARY_CONTOUR_INTERVAL_M
        )
        return float(intermediate), float(primary)

    def _modernisation_subphase(self, message: str) -> bool:
        """Report a comparison subphase and honour cancellation between outputs."""
        status = getattr(self, "_set_processing_status", None)
        if callable(status):
            status(self.tr(message))
        cancelled = getattr(self, "_processing_cancel_requested", None)
        return not (callable(cancelled) and cancelled())

    @staticmethod
    def _modernisation_feature_id(family: str, output_kind: str, sequence: int) -> str:
        """Return a readable ID unique across all modernisation output layers."""
        safe_kind = str(output_kind).strip().upper().replace("_", "-")
        return f"{str(family).strip().upper()}-{safe_kind}-{int(sequence):06d}"

    def _create_ols_modernisation_comparison_layers(
        self,
        icao_code: str,
        baseline_ruleset_id: str,
        baseline_candidates: Sequence[ControllingOlsCandidate],
        baseline_exclusions: Sequence[QgsGeometry],
        future_candidates: Sequence[ControllingOlsCandidate],
        ofs_group,
        oes_group,
        solved_baseline_engine: Optional[PlanarControllingOlsEngine] = None,
        solved_future_engines: Optional[Dict[str, PlanarControllingOlsEngine]] = None,
        comparison_ruleset_id: str = "icao_annex14_vol1_modernised_ofs_oes",
    ) -> bool:
        baseline_planar = [
            candidate for candidate in baseline_candidates
            if candidate.model in {"constant", "axis", "plane", "conical"}
        ]
        if not baseline_planar:
            QgsMessageLog.logMessage(
                "[skip] OLS modernisation comparison: baseline has no controlling candidates.",
                PLUGIN_TAG,
                Qgis.Warning,
            )
            return False

        baseline_ids = {candidate.surface_id for candidate in baseline_planar}
        if (
            solved_baseline_engine is None
            or {candidate.surface_id for candidate in solved_baseline_engine.candidates} != baseline_ids
        ):
            baseline_engine = PlanarControllingOlsEngine(
                baseline_planar,
                exclusion_geometries=list(baseline_exclusions or []),
            )
        else:
            baseline_engine = solved_baseline_engine
        created = False
        for family, family_group in (("OFS", ofs_group), ("OES", oes_group)):
            family_candidates = [
                candidate for candidate in future_candidates
                if candidate.model in {"constant", "axis", "plane", "conical"}
                and str((candidate.metadata or {}).get("annex14_family") or "").upper() == family
            ]
            if not family_candidates or family_group is None:
                QgsMessageLog.logMessage(
                    f"[skip] OLS modernisation {family} comparison: no future candidates.",
                    PLUGIN_TAG,
                    Qgis.Warning,
                )
                continue
            future_engine = (solved_future_engines or {}).get(family)
            if (
                future_engine is None
                or {candidate.surface_id for candidate in future_engine.candidates}
                != {candidate.surface_id for candidate in family_candidates}
            ):
                future_engine = PlanarControllingOlsEngine(family_candidates)
            if not self._modernisation_subphase(
                f"Modernisation {family}: classifying gain, loss, and unchanged regions..."
            ):
                return created
            comparison = OlsEnvelopeComparisonEngine(baseline_engine, future_engine)
            finalization = comparison.finalize_comparison()
            parts = finalization.parts
            contour_interval_m, primary_contour_interval_m = (
                self._modernisation_change_contour_intervals(family)
            )
            created = self._create_modernisation_wireframe_layer(
                icao_code, baseline_ruleset_id, family, "baseline",
                "Baseline OLS Wireframe", baseline_engine._controlling_region_geometries(),
                family_group, comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_wireframe_layer(
                icao_code, baseline_ruleset_id, family, "future",
                "Future Annex 14 Wireframe", future_engine._controlling_region_geometries(),
                family_group, comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            gain_name = "Height Gain" if family == "OFS" else "Trigger Height Raised"
            loss_name = "Height Loss" if family == "OFS" else "Trigger Height Lowered"
            no_change_name = "No Height Change" if family == "OFS" else "Trigger Height Unchanged"
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "gain", gain_name,
                parts["gain"], comparison, family_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "loss", loss_name,
                parts["loss"], comparison, family_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_change_layer(
                icao_code, baseline_ruleset_id, family, "no_change", no_change_name,
                parts["no_change"], comparison, family_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            if not self._modernisation_subphase(
                f"Modernisation {family}: generating signed change contours..."
            ):
                return created
            contour_parts = []
            for change in ("gain", "loss"):
                contour_parts.extend(
                    (change, *contour_part)
                    for contour_part in comparison.change_contour_parts(
                        parts[change],
                        change,
                        interval_m=contour_interval_m,
                        primary_interval_m=primary_contour_interval_m,
                    )
                )
            contour_parts.extend(
                ("transition", *contour_part)
                for contour_part in comparison.zero_change_contour_parts(parts)
            )
            if not self._modernisation_subphase(
                f"Modernisation {family}: finalising transitions and baseline-only areas..."
            ):
                return created
            created = self._create_modernisation_change_contour_layer(
                icao_code,
                baseline_ruleset_id,
                family,
                contour_parts,
                family_group,
                contour_interval_m=contour_interval_m,
                primary_interval_m=primary_contour_interval_m,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_transition_layer(
                icao_code, baseline_ruleset_id, family, parts["transition"], comparison, family_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_baseline_only_layer(
                icao_code, baseline_ruleset_id, family,
                comparison.baseline_only_parts(), family_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
        self._reconcile_modernisation_change_contour_groups(
            {"OFS": ofs_group, "OES": oes_group}
        )
        return created

    def _create_ols_ruleset_comparison_layers(
        self,
        *,
        icao_code: str,
        baseline_ruleset_id: str,
        comparison_ruleset_id: str,
        baseline_model: str,
        comparison_model: str,
        baseline_candidates: Sequence[ControllingOlsCandidate],
        baseline_exclusions: Sequence[QgsGeometry],
        comparison_candidates: Sequence[ControllingOlsCandidate],
        comparison_exclusions: Sequence[QgsGeometry],
        output_groups: Dict[str, object],
        solved_baseline_engines: Optional[Dict[str, PlanarControllingOlsEngine]] = None,
        solved_comparison_engines: Optional[Dict[str, PlanarControllingOlsEngine]] = None,
    ) -> bool:
        """Compare arbitrary solved OLS rulesets using a common family adapter."""
        annex_model = "annex14_modernised_ofs_oes"
        baseline_is_annex = baseline_model == annex_model
        comparison_is_annex = comparison_model == annex_model
        families = ("OFS", "OES") if baseline_is_annex or comparison_is_annex else ("OLS",)

        def family_candidates(candidates, is_annex, family):
            planar = [
                candidate
                for candidate in candidates
                if candidate.model in {"constant", "axis", "plane", "conical"}
            ]
            if not is_annex:
                return planar
            return [
                candidate
                for candidate in planar
                if str((candidate.metadata or {}).get("annex14_family") or "").upper()
                == family
            ]

        def matching_engine(solved, family, candidates, exclusions):
            engine = (solved or {}).get(family) or (solved or {}).get("baseline")
            candidate_ids = {candidate.surface_id for candidate in candidates}
            if (
                engine is None
                or {candidate.surface_id for candidate in engine.candidates}
                != candidate_ids
            ):
                engine = PlanarControllingOlsEngine(
                    candidates,
                    exclusion_geometries=list(exclusions or []),
                )
            return engine

        created = False
        for family in families:
            output_group = output_groups.get(family)
            baseline_family_candidates = family_candidates(
                baseline_candidates,
                baseline_is_annex,
                family,
            )
            comparison_family_candidates = family_candidates(
                comparison_candidates,
                comparison_is_annex,
                family,
            )
            if (
                output_group is None
                or not baseline_family_candidates
                or not comparison_family_candidates
            ):
                QgsMessageLog.logMessage(
                    f"[skip] OLS ruleset {family} comparison: candidates or output group unavailable.",
                    PLUGIN_TAG,
                    Qgis.Warning,
                )
                continue
            baseline_engine = matching_engine(
                solved_baseline_engines,
                family,
                baseline_family_candidates,
                [] if baseline_is_annex else baseline_exclusions,
            )
            comparison_engine = matching_engine(
                solved_comparison_engines,
                family,
                comparison_family_candidates,
                [] if comparison_is_annex else comparison_exclusions,
            )
            if not self._modernisation_subphase(
                f"Ruleset {family}: classifying gain, loss, and unchanged regions..."
            ):
                return created

            comparison = OlsEnvelopeComparisonEngine(
                baseline_engine,
                comparison_engine,
            )
            finalization = comparison.finalize_comparison()
            parts = finalization.parts
            contour_interval_m, primary_contour_interval_m = (
                self._modernisation_change_contour_intervals(family)
            )
            created = self._create_modernisation_wireframe_layer(
                icao_code,
                baseline_ruleset_id,
                family,
                "baseline",
                "Baseline OLS Wireframe",
                baseline_engine._controlling_region_geometries(),
                output_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_wireframe_layer(
                icao_code,
                baseline_ruleset_id,
                family,
                "comparison",
                "Comparison OLS Wireframe",
                comparison_engine._controlling_region_geometries(),
                output_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created

            if family == "OES":
                names = {
                    "gain": "Trigger Height Raised",
                    "loss": "Trigger Height Lowered",
                    "no_change": "Trigger Height Unchanged",
                }
            else:
                names = {
                    "gain": "Height Gain",
                    "loss": "Height Loss",
                    "no_change": "No Height Change",
                }
            for change in ("gain", "loss", "no_change"):
                created = self._create_modernisation_change_layer(
                    icao_code,
                    baseline_ruleset_id,
                    family,
                    change,
                    names[change],
                    parts[change],
                    comparison,
                    output_group,
                    comparison_ruleset_id=comparison_ruleset_id,
                ) or created

            contour_parts = []
            for change in ("gain", "loss"):
                contour_parts.extend(
                    (change, *contour_part)
                    for contour_part in comparison.change_contour_parts(
                        parts[change],
                        change,
                        interval_m=contour_interval_m,
                        primary_interval_m=primary_contour_interval_m,
                    )
                )
            contour_parts.extend(
                ("transition", *contour_part)
                for contour_part in comparison.zero_change_contour_parts(parts)
            )
            created = self._create_modernisation_change_contour_layer(
                icao_code,
                baseline_ruleset_id,
                family,
                contour_parts,
                output_group,
                contour_interval_m=contour_interval_m,
                primary_interval_m=primary_contour_interval_m,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_transition_layer(
                icao_code,
                baseline_ruleset_id,
                family,
                parts["transition"],
                comparison,
                output_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
            created = self._create_modernisation_baseline_only_layer(
                icao_code,
                baseline_ruleset_id,
                family,
                comparison.baseline_only_parts(),
                output_group,
                comparison_ruleset_id=comparison_ruleset_id,
            ) or created
        self._reconcile_modernisation_change_contour_groups(output_groups)
        return created

    def _reconcile_modernisation_change_contour_groups(
        self,
        output_groups: Dict[str, object],
    ) -> None:
        """Keep each signed change-contour layer under its attributed family."""
        family_groups = {
            str(family).upper(): group
            for family, group in output_groups.items()
            if isinstance(group, QgsLayerTreeGroup)
        }
        if not family_groups:
            return

        for source_group in list(family_groups.values()):
            for node in list(source_group.children()):
                if not isinstance(node, QgsLayerTreeLayer):
                    continue
                layer = node.layer()
                if layer is None or layer.fields().indexFromName("future_family") < 0:
                    continue
                if layer.fields().indexFromName("delta_m") < 0:
                    continue
                try:
                    attributed_families = {
                        str(feature.attribute("future_family") or "").upper()
                        for feature in layer.getFeatures()
                    }
                    attributed_families.discard("")
                except Exception:
                    continue
                if len(attributed_families) != 1:
                    continue
                family = next(iter(attributed_families))
                target_group = family_groups.get(family)
                if target_group is None or target_group is source_group:
                    continue
                try:
                    target_group.addChildNode(node.clone())
                    source_group.removeChildNode(node)
                    QgsMessageLog.logMessage(
                        f"[normalise] Moved {family} change contours to the {family} comparison group.",
                        PLUGIN_TAG,
                        Qgis.Info,
                    )
                except Exception as exc:
                    QgsMessageLog.logMessage(
                        f"Warning: could not reconcile {family} change-contour group: {exc}",
                        PLUGIN_TAG,
                        Qgis.Warning,
                    )

    @staticmethod
    def _comparison_label_delta(value: float) -> str:
        rounded = round(float(value), 1)
        if rounded == 0:
            rounded = 0.0
        sign = "+" if rounded > 0 else ""
        return f"{sign}{rounded:.1f}"

    def _comparison_label(
        self,
        change: str,
        delta_min: Optional[float],
        delta_max: Optional[float],
    ) -> str:
        if delta_min is None or delta_max is None:
            return ""
        suffix = "no change" if change == "no_change" else change
        minimum = self._comparison_label_delta(delta_min)
        maximum = self._comparison_label_delta(delta_max)
        if minimum == maximum:
            return f"{minimum} m {suffix}"
        return f"{minimum} to {maximum} m {suffix}"

    def _create_modernisation_change_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        change,
        display_name,
        parts,
        comparison,
        output_group,
        comparison_ruleset_id="",
    ) -> bool:
        fields = QgsFields([
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("change", QVariant.String, self.tr("Change"), 24),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("delta_min_m", QVariant.Double, self.tr("Minimum Change (m)"), 12, 3),
            QgsField("delta_max_m", QVariant.Double, self.tr("Maximum Change (m)"), 12, 3),
            QgsField("delta_sample_m", QVariant.Double, self.tr("Interior Sample Change (m)"), 12, 3),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 48),
            QgsField("comparison_ruleset", QVariant.String, self.tr("Comparison Ruleset"), 80),
            QgsField("comparison_family", QVariant.String, self.tr("Comparison Family"), 8),
            QgsField("comparison_surface_id", QVariant.String, self.tr("Comparison Surface ID"), 160),
            QgsField("comparison_surface", QVariant.String, self.tr("Comparison Surface"), 50),
        ])
        features: List[QgsFeature] = []
        if family == "OFS":
            if change == "gain":
                meaning = "Comparison controlling elevation is higher than baseline in the OFS protected-airspace family"
            elif change == "loss":
                meaning = "Comparison controlling elevation is lower than baseline in the OFS protected-airspace family"
            else:
                meaning = "Comparison controlling elevation is effectively equal to baseline in the OFS protected-airspace family"
        elif family == "OES":
            if change == "gain":
                meaning = "Comparison controlling elevation is higher than baseline in the OES assessment-trigger family; not an approval limit"
            elif change == "loss":
                meaning = "Comparison controlling elevation is lower than baseline in the OES assessment-trigger family; not an approval limit"
            else:
                meaning = "Comparison controlling elevation is effectively equal to baseline in the OES assessment-trigger family; not an approval limit"
        else:
            if change == "gain":
                meaning = "Comparison controlling OLS elevation is higher than baseline"
            elif change == "loss":
                meaning = "Comparison controlling OLS elevation is lower than baseline"
            else:
                meaning = "Comparison controlling OLS elevation is effectively equal to baseline"
        for sequence, (baseline, future, geometry) in enumerate(parts, start=1):
            delta_min, delta_max, delta_sample = comparison.delta_range(
                geometry,
                baseline,
                future,
                change,
            )
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, change, sequence),
                change,
                family,
                delta_min,
                delta_max,
                delta_sample,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                future.surface_id,
                future.surface_type,
                meaning,
                self._comparison_label(change, delta_min, delta_max),
                comparison_ruleset_id,
                family,
                future.surface_id,
                future.surface_type,
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            f"OLS_Modernisation_{family}_{change}_{icao_code}",
            display_name,
            fields,
            features,
            output_group,
            {
                "gain": "OLS Modernisation Gain",
                "loss": "OLS Modernisation Loss",
                "no_change": "OLS Modernisation No Change",
            }.get(change, "OLS Modernisation No Change"),
        )
        return layer is not None

    def _create_modernisation_change_contour_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        contour_parts,
        output_group,
        contour_interval_m: float = COMPARISON_CONTOUR_INTERVAL_M,
        primary_interval_m: float = COMPARISON_PRIMARY_CONTOUR_INTERVAL_M,
        comparison_ruleset_id: str = "",
    ) -> bool:
        fields = QgsFields([
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("parent_id", QVariant.String, self.tr("Parent Comparison ID"), 48),
            QgsField("change", QVariant.String, self.tr("Change"), 24),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("delta_m", QVariant.Double, self.tr("Change Contour (m)"), 12, 3),
            QgsField("contour_class", QVariant.String, self.tr("Contour Class"), 20),
            QgsField("contour_interval_m", QVariant.Double, self.tr("Intermediate Interval (m)"), 10, 2),
            QgsField("primary_interval_m", QVariant.Double, self.tr("Primary Interval (m)"), 10, 2),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 24),
            QgsField("comparison_ruleset", QVariant.String, self.tr("Comparison Ruleset"), 80),
            QgsField("comparison_family", QVariant.String, self.tr("Comparison Family"), 8),
            QgsField("comparison_surface_id", QVariant.String, self.tr("Comparison Surface ID"), 160),
            QgsField("comparison_surface", QVariant.String, self.tr("Comparison Surface"), 50),
        ])
        features: List[QgsFeature] = []
        for sequence, contour_part in enumerate(contour_parts, start=1):
            (
                change,
                baseline,
                future,
                geometry,
                delta_m,
                contour_class,
                parent_sequence,
            ) = contour_part
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, "change_contour", sequence),
                (
                    ""
                    if change == "transition"
                    else self._modernisation_feature_id(family, change, parent_sequence)
                ),
                change,
                family,
                delta_m,
                contour_class,
                contour_interval_m,
                primary_interval_m,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                future.surface_id,
                future.surface_type,
                f"{self._comparison_label_delta(delta_m)} m",
                comparison_ruleset_id,
                family,
                future.surface_id,
                future.surface_type,
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiLineString",
            f"OLS_Modernisation_{family}_change_contours_{icao_code}",
            "Change Contours",
            fields,
            features,
            output_group,
            "OLS Modernisation Change Contour",
        )
        return layer is not None

    def _create_modernisation_wireframe_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        source_kind,
        display_name,
        candidate_regions,
        output_group,
        comparison_ruleset_id="",
    ) -> bool:
        fields = QgsFields([
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("source", QVariant.String, self.tr("Source"), 24),
            QgsField("family", QVariant.String, self.tr("Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("surface_id", QVariant.String, self.tr("Surface ID"), 160),
            QgsField("surface", QVariant.String, self.tr("Surface"), 50),
            QgsField("comparison_ruleset", QVariant.String, self.tr("Comparison Ruleset"), 80),
            QgsField("ruleset_id", QVariant.String, self.tr("Ruleset ID"), 80),
        ])
        features: List[QgsFeature] = []
        sequence = 0
        for candidate, geometry in candidate_regions:
            for part in self._modernisation_polygon_parts(geometry):
                if not OlsEnvelopeComparisonEngine._has_area(part):
                    continue
                sequence += 1
                feature = QgsFeature(fields)
                feature.setGeometry(part)
                feature.setAttributes([
                    self._modernisation_feature_id(family, f"{source_kind}_wireframe", sequence),
                    source_kind,
                    family,
                    baseline_ruleset_id,
                    candidate.surface_id,
                    candidate.surface_type,
                    comparison_ruleset_id,
                    baseline_ruleset_id if source_kind == "baseline" else comparison_ruleset_id,
                ])
                features.append(feature)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            f"OLS_Modernisation_{family}_{source_kind}_wireframe_{icao_code}",
            display_name,
            fields,
            features,
            output_group,
            "OLS Modernisation Baseline Wireframe"
            if source_kind == "baseline"
            else "OLS Modernisation Future Wireframe",
        )
        return layer is not None

    def _modernisation_polygon_parts(self, geometry: QgsGeometry) -> List[QgsGeometry]:
        if geometry is None or geometry.isEmpty():
            return []
        try:
            if QgsWkbTypes.geometryType(geometry.wkbType()) != Qgis.GeometryType.Polygon:
                return []
        except Exception:
            return [geometry]
        if not geometry.isMultipart():
            return [QgsGeometry(geometry)]
        parts: List[QgsGeometry] = []
        try:
            for polygon in geometry.asMultiPolygon():
                if polygon:
                    parts.append(QgsGeometry.fromPolygonXY(polygon))
        except Exception:
            pass
        return parts

    def _create_modernisation_transition_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        parts,
        comparison,
        output_group,
        comparison_ruleset_id="",
    ) -> bool:
        fields = QgsFields([
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("future_id", QVariant.String, self.tr("Future Surface ID"), 160),
            QgsField("future_surface", QVariant.String, self.tr("Future Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
            QgsField("comparison_ruleset", QVariant.String, self.tr("Comparison Ruleset"), 80),
            QgsField("comparison_family", QVariant.String, self.tr("Comparison Family"), 8),
            QgsField("comparison_surface_id", QVariant.String, self.tr("Comparison Surface ID"), 160),
            QgsField("comparison_surface", QVariant.String, self.tr("Comparison Surface"), 50),
        ])
        features: List[QgsFeature] = []
        for sequence, (baseline, future, geometry) in enumerate(parts, start=1):
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, "transition", sequence),
                family,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                future.surface_id,
                future.surface_type,
                "Approximate line where the baseline and comparison controlling elevations are equal",
                comparison_ruleset_id,
                family,
                future.surface_id,
                future.surface_type,
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiLineString",
            f"OLS_Modernisation_{family}_transition_{icao_code}",
            "Planar Transition / Equal Height",
            fields,
            features,
            output_group,
            "OLS Modernisation Transition",
        )
        return layer is not None

    def _create_modernisation_baseline_only_layer(
        self,
        icao_code,
        baseline_ruleset_id,
        family,
        parts,
        output_group,
        comparison_ruleset_id="",
    ) -> bool:
        fields = QgsFields([
            QgsField("comparison_id", QVariant.String, self.tr("Comparison Feature ID"), 48),
            QgsField("change", QVariant.String, self.tr("Change"), 32),
            QgsField("future_family", QVariant.String, self.tr("Future Family"), 8),
            QgsField("baseline_ruleset", QVariant.String, self.tr("Baseline Ruleset"), 80),
            QgsField("baseline_id", QVariant.String, self.tr("Baseline Surface ID"), 160),
            QgsField("baseline_surface", QVariant.String, self.tr("Baseline Surface"), 50),
            QgsField("meaning", QVariant.String, self.tr("Regulatory Meaning"), 160),
            QgsField("label_txt", QVariant.String, self.tr("Map Label"), 32),
            QgsField("comparison_ruleset", QVariant.String, self.tr("Comparison Ruleset"), 80),
        ])
        features: List[QgsFeature] = []
        for sequence, (baseline, geometry) in enumerate(parts, start=1):
            feature = QgsFeature(fields)
            feature.setGeometry(geometry)
            feature.setAttributes([
                self._modernisation_feature_id(family, "no_future_overlay", sequence),
                "no_future_overlay",
                family,
                baseline_ruleset_id,
                baseline.surface_id,
                baseline.surface_type,
                "Baseline controlling OLS area with no overlapping comparison surface",
                "no comparison overlay",
                comparison_ruleset_id,
            ])
            features.append(feature)
        layer = self._create_and_add_layer(
            "MultiPolygon",
            f"OLS_Modernisation_{family}_no_future_overlay_{icao_code}",
            "No Comparison OLS Overlay",
            fields,
            features,
            output_group,
            "OLS Modernisation No Future Overlay",
        )
        return layer is not None


__all__ = ["OlsEnvelopeComparisonEngine", "OlsModernisationComparisonMixin"]
