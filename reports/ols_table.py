# -*- coding: utf-8 -*-
"""Per-run obstacle limitation surface table report."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from zoneinfo import ZoneInfo


TYPE_LABELS = {
    "NI": "NON INST",
    "NPA": "NON PREC",
    "PA_I": "PREC CAT I",
    "PA_II_III": "PREC CAT II/III",
}

REPORT_TIMEZONE = ZoneInfo("Europe/Amsterdam")


def build_ols_table_values(
    icao_code: str,
    ruleset,
    construction_context,
    generated_at: Optional[datetime] = None,
    run_id: Optional[str] = None,
    test_case_id: Optional[str] = None,
    input_fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve the values used by conventional OLS construction."""
    generated_at = generated_at or datetime.now()
    policy = ruleset.ols_construction_policy()
    context = construction_context
    airport_spec = dict(policy.airport_wide_spec(ruleset, context) or {})
    governing_runway = _governing_runway(context, airport_spec)
    governing_end = _governing_end(governing_runway)
    ihs_params = _resolved_parameters(
        policy,
        ruleset,
        context,
        governing_runway,
        governing_end,
        "IHS",
    )
    ihs_plan = (
        dict(policy.ihs_plan(context, governing_runway) or {})
        if governing_runway is not None
        else {}
    )
    ohs = dict(airport_spec.get("ohs") or {})
    datum_elevation = airport_spec.get(
        "datum_elevation_m",
        getattr(context, "reference_elevation_datum_m", None),
    )
    ihs_height = airport_spec.get("ihs_height_m", ihs_params.get("height_agl"))
    ihs_elevation = airport_spec.get("ihs_elevation_amsl")
    if ihs_elevation is None:
        ihs_elevation = _sum_optional(datum_elevation, ihs_height)

    references = set()
    warnings: List[str] = []
    _collect_ref(references, ihs_params)
    _collect_ref(references, ohs)
    _collect_ref(references, airport_spec.get("conical"))

    approach_rows = []
    transitional_rows = []
    takeoff_rows = []
    for runway in getattr(context, "runways", ()):
        for end in runway.ends:
            lookup_type = end.approach_type or end.classified_type
            approach = _resolved_parameters(
                policy,
                ruleset,
                context,
                runway,
                end,
                "Approach",
                lookup_type,
            )
            transitional = _resolved_parameters(
                policy,
                ruleset,
                context,
                runway,
                end,
                "Transitional",
                lookup_type,
            )
            takeoff = _resolved_parameters(
                policy,
                ruleset,
                context,
                runway,
                end,
                "TOCS",
                None,
            )
            sections = _sections(approach)
            positive_sections = [
                section
                for section in sections
                if _number(section.get("slope")) not in (None, 0.0)
            ]
            horizontal_length = sum(
                _number(section.get("length")) or 0.0
                for section in sections
                if _number(section.get("slope")) == 0.0
            )
            explicit_total = [
                _number(section.get("total_length"))
                for section in sections
                if _number(section.get("total_length")) is not None
            ]
            total_length = (
                max(explicit_total)
                if explicit_total
                else sum(_number(section.get("length")) or 0.0 for section in sections)
            )
            first = positive_sections[0] if positive_sections else (sections[0] if sections else {})
            second = positive_sections[1] if len(positive_sections) > 1 else {}

            approach_rows.append(
                {
                    "runway": end.designator,
                    "code": runway.arc_number,
                    "instrument_type": TYPE_LABELS.get(
                        end.classified_type,
                        end.classified_type or "N/A",
                    ),
                    "inner_edge_elevation": end.threshold_elevation_m,
                    "inner_edge_length": first.get("start_width"),
                    "distance_from_threshold": first.get("start_dist_from_thr"),
                    "divergence": first.get("divergence"),
                    "first_section_length": first.get("length"),
                    "first_section_slope": first.get("slope"),
                    "second_section_length": second.get("length"),
                    "second_section_slope": second.get("slope"),
                    "horizontal_section_length": (
                        horizontal_length if horizontal_length > 0 else None
                    ),
                    "total_length": total_length if sections else None,
                }
            )
            transitional_rows.append(
                {
                    "runway": end.designator,
                    "code": runway.arc_number,
                    "slope": transitional.get("slope"),
                }
            )
            takeoff_rows.append(
                {
                    "runway": end.designator,
                    "code": runway.arc_number,
                    "inner_edge_elevation": end.runway_end_elevation_m,
                    "inner_edge_length": takeoff.get("inner_edge_width"),
                    "distance_from_runway_end": takeoff.get(
                        "origin_station_from_pavement_end",
                        takeoff.get("origin_offset"),
                    ),
                    "divergence": takeoff.get("divergence"),
                    "overall_length": takeoff.get("length"),
                    "final_width": takeoff.get("final_width"),
                    "slope": takeoff.get("slope"),
                }
            )
            for params in sections + [transitional, takeoff]:
                _collect_ref(references, params)
            if not sections:
                warnings.append(
                    f"Approach parameters were unavailable for runway {end.designator}."
                )
            if not transitional:
                warnings.append(
                    f"Transitional parameters were unavailable for runway {end.designator}."
                )
            if not takeoff:
                warnings.append(
                    f"Take-off climb parameters were unavailable for runway {end.designator}."
                )

    return {
        "format": "conventional",
        "icao_code": str(icao_code or "UNKNOWN").strip().upper(),
        "ruleset_id": ruleset.id,
        "ruleset_name": ruleset.display_name,
        "ruleset_edition": ruleset.edition,
        "generated_at": generated_at,
        "run_id": str(run_id or "").strip() or None,
        "test_case_id": str(test_case_id or "").strip() or None,
        "input_fingerprint": str(input_fingerprint or "").strip() or None,
        "runways": [
            {
                "name": runway.runway_id,
                "physical_length": runway.physical_length_m,
                "width": runway.width_m,
                "strip_width": (runway.strip_parameters or {}).get("overall_width"),
            }
            for runway in getattr(context, "runways", ())
        ],
        "airport": {
            "arp_elevation": getattr(context, "arp_elevation_m", None),
            "datum_label": _datum_label(airport_spec.get("datum_name")),
            "datum_elevation": datum_elevation,
        },
        "horizontal": {
            "outer_elevation": ohs.get("elevation_amsl"),
            "outer_height": ohs.get("height_agl"),
            "outer_radius": ohs.get("radius"),
            "inner_elevation": ihs_elevation,
            "inner_height": ihs_height,
            "inner_radius": ihs_plan.get("radius", ihs_params.get("radius")),
        },
        "approach": approach_rows,
        "transitional": transitional_rows,
        "takeoff": takeoff_rows,
        "references": sorted(references),
        "warnings": _unique(warnings),
    }


def build_modernised_ols_table_values(
    icao_code: str,
    ruleset,
    construction_context,
    generated_at: Optional[datetime] = None,
    run_id: Optional[str] = None,
    test_case_id: Optional[str] = None,
    input_fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve the OFS/OES values used by modernised Annex 14 construction."""
    context = construction_context
    references = set()
    warnings: List[str] = []
    operations_rows: List[Dict[str, Any]] = []
    ofs_rows: List[Dict[str, Any]] = []
    oes_rows: List[Dict[str, Any]] = []

    for runway in getattr(context, "runways", ()):
        data = dict(runway.generation_data or {})
        config = data.get("annex14_modernised")
        config = config if isinstance(config, Mapping) else {}
        design_group = data.get("adg") or data.get("design_group")
        code_f_no_digital = bool(
            config.get("code_f_without_digital_go_around_avionics", False)
        )
        if not config.get("confirmed"):
            warnings.append(
                f"{runway.runway_id}: modernised Annex 14 configuration was not confirmed."
            )
        if not design_group:
            warnings.append(
                f"{runway.runway_id}: aircraft design group was unavailable."
            )
            continue

        horizontal = ruleset.horizontal_surface_parameters(design_group)
        if horizontal:
            oes_rows.append(
                _modern_oes_row(
                    runway,
                    None,
                    design_group,
                    "All runway operations",
                    "Horizontal",
                    "Airport-wide",
                    horizontal,
                    start_rule=horizontal.get("outer_limits_rule"),
                    height=horizontal.get(
                        "height_above_aerodrome_elevation_m"
                    ),
                    length=horizontal.get("radius_m"),
                )
            )
            _collect_refs(references, horizontal)

        straight_in_selected = False
        for end in runway.ends:
            end_config = config.get(f"{end.direction}_end")
            end_config = end_config if isinstance(end_config, Mapping) else {}
            operations = dict(end_config.get("operations") or {})
            selected = [
                name.replace("_", " ")
                for name, enabled in operations.items()
                if enabled
            ]
            mass = _number(
                end_config.get("maximum_certificated_takeoff_mass_kg")
            )
            slope_percent = _number(
                end_config.get("governing_approach_surface_slope_percent")
            )
            obstacle_clearance_height = _number(
                end_config.get("obstacle_clearance_height_m")
            )
            operations_rows.append(
                {
                    "runway": runway.runway_id,
                    "end": end.designator,
                    "design_group": design_group,
                    "runway_type": TYPE_LABELS.get(
                        end.classified_type,
                        end.classified_type or end.approach_type,
                    ),
                    "operations": ", ".join(selected) if selected else "None",
                    "takeoff_mass": mass,
                    "approach_slope": (
                        slope_percent / 100.0
                        if slope_percent is not None
                        else None
                    ),
                    "obstacle_clearance_height": obstacle_clearance_height,
                }
            )

            ofs = ruleset.obstacle_free_surfaces(
                design_group=design_group,
                runway_type=end.approach_type,
                runway_width_m=data.get("runway_width"),
                approach_surface_slope=(
                    slope_percent / 100.0
                    if slope_percent is not None
                    else None
                ),
                obstacle_clearance_height_m=obstacle_clearance_height,
                code_letter_f_without_digital_avionics=code_f_no_digital,
            )
            for group_name, surfaces in (ofs or {}).get("groups", {}).items():
                for surface in surfaces or ():
                    ofs_rows.append(
                        _modern_ofs_row(
                            runway,
                            end,
                            design_group,
                            group_name,
                            surface,
                        )
                    )
                    _collect_refs(references, surface)

            straight_in_selected = straight_in_selected or bool(
                operations.get("straight_in_non_precision_instrument")
            )
            if (
                operations.get("precision_approach")
                and end.classified_type in {"PA_I", "PA_II_III"}
            ):
                precision = ruleset.precision_approach_surface_parameters()
                _append_precision_oes_rows(
                    oes_rows,
                    runway,
                    end,
                    design_group,
                    precision,
                )
                _collect_refs(references, precision)
            if (
                operations.get("instrument_departure")
                and end.classified_type != "NI"
            ):
                departure = ruleset.instrument_departure_surface_parameters()
                _append_section_oes_rows(
                    oes_rows,
                    runway,
                    end,
                    design_group,
                    "Instrument departure",
                    "instrument departure",
                    departure,
                    start_rule=departure.get("inner_edge_location"),
                    inner_edge=departure.get("inner_edge_length_m"),
                    slope=departure.get("slope"),
                    height=departure.get("inner_edge_elevation_offset_m"),
                )
                _collect_refs(references, departure)
            if operations.get("take_off"):
                takeoff = ruleset.take_off_climb_surface_parameters(
                    design_group,
                    max_certificated_takeoff_mass_kg=mass,
                )
                if takeoff:
                    oes_rows.append(
                        _modern_oes_row(
                            runway,
                            end,
                            design_group,
                            "Take-off",
                            "Take-off climb",
                            takeoff.get("mass_category"),
                            takeoff,
                            start_rule=takeoff.get("start_rule"),
                            inner_edge=takeoff.get("inner_edge_length_m"),
                            length=takeoff.get("length_m"),
                            divergence=takeoff.get("divergence"),
                            slope=takeoff.get("slope"),
                            final_width=takeoff.get("final_width_m"),
                        )
                    )
                    _collect_refs(references, takeoff)

        if straight_in_selected:
            straight_in = (
                ruleset.straight_in_instrument_approach_surface_parameters()
            )
            lower = straight_in.get("lower_section", {})
            upper = straight_in.get("upper_section", {})
            oes_rows.extend(
                [
                    _modern_oes_row(
                        runway,
                        None,
                        design_group,
                        "Straight-in non-precision instrument",
                        "Straight-in instrument approach",
                        "Lower",
                        straight_in,
                        start_rule=lower.get("length_rule"),
                        height=lower.get(
                            "height_above_aerodrome_elevation_m"
                        ),
                    ),
                    _modern_oes_row(
                        runway,
                        None,
                        design_group,
                        "Straight-in non-precision instrument",
                        "Straight-in instrument approach",
                        "Upper",
                        straight_in,
                        length=upper.get("shorter_side_length_m"),
                        final_width=upper.get(
                            "longer_side_length_from_threshold_or_thresholds_m"
                        ),
                        height=upper.get(
                            "height_above_aerodrome_elevation_m"
                        ),
                    ),
                ]
            )
            _collect_refs(references, straight_in)

    return {
        "format": "modernised_ofs_oes",
        "icao_code": str(icao_code or "UNKNOWN").strip().upper(),
        "ruleset_id": ruleset.id,
        "ruleset_name": ruleset.display_name,
        "ruleset_edition": ruleset.edition,
        "generated_at": generated_at or datetime.now(REPORT_TIMEZONE),
        "run_id": str(run_id or "").strip() or None,
        "test_case_id": str(test_case_id or "").strip() or None,
        "input_fingerprint": str(input_fingerprint or "").strip() or None,
        "runways": [
            {
                "name": runway.runway_id,
                "physical_length": runway.physical_length_m,
                "width": runway.width_m,
                "strip_width": (runway.strip_parameters or {}).get(
                    "overall_width"
                ),
            }
            for runway in getattr(context, "runways", ())
        ],
        "operations": operations_rows,
        "ofs": ofs_rows,
        "oes": oes_rows,
        "references": sorted(references),
        "warnings": _unique(warnings),
    }


def render_ols_table_markdown(report: Mapping[str, Any]) -> str:
    """Render the resolved OLS values as a VS Code-friendly Markdown report."""
    generated_at = report.get("generated_at")
    generated_text = _format_report_timestamp(generated_at)
    lines = [
        "# Obstacle Restriction and Limitation Surfaces Table of Values",
        "",
        f"## {_markdown_cell(report.get('icao_code'))} Safeguarding OLS",
        "",
        f"- Generated: {generated_text}",
        f"- Run ID: `{_markdown_cell(report.get('run_id'))}`",
        f"- Test case ID: `{_markdown_cell(report.get('test_case_id'))}`",
        f"- Input fingerprint: `{_markdown_cell(report.get('input_fingerprint'))}`",
        "- Units: distances and lengths in metres; elevations in metres AMSL",
        "",
    ]
    lines.extend(_render_ruleset_section(report, "Baseline OLS"))
    for comparison in report.get("comparisons", ()):
        lines.extend([""])
        lines.extend(_render_ruleset_section(comparison, "Comparison OLS"))
    return "\n".join(lines).rstrip() + "\n"


def _render_ruleset_section(
    report: Mapping[str, Any],
    role: str,
) -> List[str]:
    lines = [
        f"## {role} — {_markdown_cell(report.get('ruleset_name'))}",
        "",
        f"- Edition: {_markdown_cell(report.get('ruleset_edition'))}",
        f"- Ruleset ID: `{_markdown_cell(report.get('ruleset_id'))}`",
        "",
    ]
    if report.get("format") == "modernised_ofs_oes":
        lines.extend(_render_modernised_section(report))
    else:
        lines.extend(_render_conventional_section(report))
    return lines


def _render_conventional_section(report: Mapping[str, Any]) -> List[str]:
    airport = report.get("airport", {})
    horizontal = report.get("horizontal", {})
    lines = [
        "### Runways",
        "",
        _markdown_table(
            ["Runway", "Physical length", "Width", "Runway strip width"],
            [
                [
                    row.get("name"),
                    _format_number(row.get("physical_length")),
                    _format_number(row.get("width")),
                    _format_number(row.get("strip_width")),
                ]
                for row in report.get("runways", ())
            ],
        ),
        "",
        "### Airport",
        "",
        _markdown_table(
            ["ARP elevation", airport.get("datum_label")],
            [[
                _format_number(airport.get("arp_elevation")),
                _format_number(airport.get("datum_elevation")),
            ]],
        ),
        "",
        "### Horizontal surfaces",
        "",
        _markdown_table(
            [
                "Outer elevation",
                "Outer height",
                "Outer radius",
                "Inner elevation",
                "Inner height",
                "Inner radius",
            ],
            [[
                _format_number(horizontal.get("outer_elevation")),
                _format_number(horizontal.get("outer_height")),
                _format_number(horizontal.get("outer_radius")),
                _format_number(horizontal.get("inner_elevation")),
                _format_number(horizontal.get("inner_height")),
                _format_number(horizontal.get("inner_radius")),
            ]],
        ),
        "",
        "### Approach surfaces",
        "",
        _markdown_table(
            [
                "RWY",
                "Code",
                "Instrument type",
                "Inner edge elev",
                "Inner edge length",
                "Dist from THR",
                "Divergence each side",
                "First length",
                "First slope",
                "Second length",
                "Second slope",
                "Horizontal length",
                "Total length",
            ],
            [
                [
                    row.get("runway"),
                    row.get("code"),
                    row.get("instrument_type"),
                    _format_number(row.get("inner_edge_elevation")),
                    _format_number(row.get("inner_edge_length")),
                    _format_number(row.get("distance_from_threshold")),
                    _format_percent(row.get("divergence")),
                    _format_number(row.get("first_section_length")),
                    _format_percent(row.get("first_section_slope")),
                    _format_number(row.get("second_section_length")),
                    _format_percent(row.get("second_section_slope")),
                    _format_number(row.get("horizontal_section_length")),
                    _format_number(row.get("total_length")),
                ]
                for row in report.get("approach", ())
            ],
        ),
        "",
        "### Transitional surfaces",
        "",
        _markdown_table(
            ["Runway", "Code", "Slope"],
            [
                [row.get("runway"), row.get("code"), _format_percent(row.get("slope"))]
                for row in report.get("transitional", ())
            ],
        ),
        "",
        "### Take-off climb surfaces",
        "",
        _markdown_table(
            [
                "Runway",
                "Code",
                "Inner edge elevation",
                "Inner edge length",
                "Distance from runway end",
                "Divergence each side",
                "Overall length",
                "Final width",
                "Slope",
            ],
            [
                [
                    row.get("runway"),
                    row.get("code"),
                    _format_number(row.get("inner_edge_elevation")),
                    _format_number(row.get("inner_edge_length")),
                    _format_number(row.get("distance_from_runway_end")),
                    _format_percent(row.get("divergence")),
                    _format_number(row.get("overall_length")),
                    _format_number(row.get("final_width")),
                    _format_percent(row.get("slope")),
                ]
                for row in report.get("takeoff", ())
            ],
        ),
        "",
        "### Notes",
        "",
        "- Values are resolved from this conventional OLS ruleset and the "
        "processed runway inputs used for the run.",
    ]
    lines.extend(f"- {_markdown_cell(value)}" for value in report.get("warnings", ()))
    lines.extend(["", "### Source references", ""])
    references = report.get("references", ())
    lines.extend(
        [f"- {_markdown_cell(reference)}" for reference in references]
        or ["- N/A"]
    )
    return lines


def _render_modernised_section(report: Mapping[str, Any]) -> List[str]:
    lines = [
        "### Runways",
        "",
        _markdown_table(
            ["Runway", "Physical length", "Width", "Runway strip width"],
            [
                [
                    row.get("name"),
                    _format_number(row.get("physical_length")),
                    _format_number(row.get("width")),
                    _format_number(row.get("strip_width")),
                ]
                for row in report.get("runways", ())
            ],
        ),
        "",
        "### Operational inputs and applicability",
        "",
        _markdown_table(
            [
                "Runway",
                "End",
                "ADG",
                "Runway type",
                "Selected operations",
                "Max take-off mass (kg)",
                "Governing approach slope",
                "Obstacle clearance height",
            ],
            [
                [
                    row.get("runway"),
                    row.get("end"),
                    row.get("design_group"),
                    row.get("runway_type"),
                    row.get("operations"),
                    _format_number(row.get("takeoff_mass")),
                    _format_percent(row.get("approach_slope")),
                    _format_number(row.get("obstacle_clearance_height")),
                ]
                for row in report.get("operations", ())
            ],
        ),
        "",
        "### Obstacle Free Surfaces (OFS)",
        "",
        _markdown_table(
            [
                "Runway",
                "End",
                "ADG",
                "Group",
                "Surface",
                "Start / rule",
                "Inner edge",
                "Length / rule",
                "Divergence",
                "Slope",
                "Upper height",
            ],
            [
                [
                    row.get("runway"),
                    row.get("end"),
                    row.get("design_group"),
                    row.get("group"),
                    row.get("surface"),
                    _format_value_or_rule(row.get("start"), row.get("start_rule")),
                    _format_number(row.get("inner_edge")),
                    _format_value_or_rule(row.get("length"), row.get("length_rule")),
                    _format_percent(row.get("divergence")),
                    _format_percent(row.get("slope")),
                    _format_number(row.get("height")),
                ]
                for row in report.get("ofs", ())
            ],
        ),
        "",
        "### Obstacle Evaluation Surfaces (OES)",
        "",
        _markdown_table(
            [
                "Runway",
                "End",
                "ADG",
                "Operation",
                "Surface",
                "Component",
                "Start / rule",
                "Inner edge",
                "Length / radius",
                "Divergence",
                "Slope",
                "Final width / extent",
                "Height / elevation offset",
            ],
            [
                [
                    row.get("runway"),
                    row.get("end"),
                    row.get("design_group"),
                    row.get("operation"),
                    row.get("surface"),
                    row.get("component"),
                    _markdown_cell(row.get("start_rule")),
                    _format_number(row.get("inner_edge")),
                    _format_number(row.get("length")),
                    _format_percent(row.get("divergence")),
                    _format_percent(row.get("slope")),
                    _format_number(row.get("final_width")),
                    _format_number(row.get("height")),
                ]
                for row in report.get("oes", ())
            ],
        ),
        "",
        "### Notes",
        "",
        "- OFS and OES use separate tables because the modernised Annex 14 "
        "model is operation- and aircraft-design-group-dependent.",
    ]
    lines.extend(f"- {_markdown_cell(value)}" for value in report.get("warnings", ()))
    lines.extend(["", "### Source references", ""])
    references = report.get("references", ())
    lines.extend(
        [f"- {_markdown_cell(reference)}" for reference in references]
        or ["- N/A"]
    )
    return lines


def _modern_ofs_row(
    runway,
    end,
    design_group: str,
    group_name: str,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "runway": runway.runway_id,
        "end": end.designator,
        "design_group": design_group,
        "group": str(group_name).replace("_", " ").title(),
        "surface": str(params.get("surface") or "N/A").replace("_", " ").title(),
        "start": params.get(
            "distance_from_threshold_m",
            params.get("distance_from_runway_end_m"),
        ),
        "start_rule": params.get(
            "distance_rule",
            params.get("inner_edge_location"),
        ),
        "inner_edge": params.get("inner_edge_length_m"),
        "length": params.get("length_m"),
        "length_rule": params.get("length_rule"),
        "divergence": params.get("divergence"),
        "slope": params.get("slope", params.get("inclined_section_slope")),
        "height": params.get(
            "upper_edge_height_above_highest_threshold_m",
            params.get("vertical_section_height_m"),
        ),
    }


def _modern_oes_row(
    runway,
    end,
    design_group: str,
    operation: str,
    surface: str,
    component: Any,
    params: Mapping[str, Any],
    *,
    start_rule: Any = None,
    inner_edge: Any = None,
    length: Any = None,
    divergence: Any = None,
    slope: Any = None,
    final_width: Any = None,
    height: Any = None,
) -> Dict[str, Any]:
    return {
        "runway": runway.runway_id,
        "end": end.designator if end is not None else "All",
        "design_group": design_group,
        "operation": operation,
        "surface": surface,
        "component": str(component or "N/A").replace("_", " ").title(),
        "start_rule": start_rule,
        "inner_edge": inner_edge,
        "length": length,
        "divergence": divergence,
        "slope": slope,
        "final_width": final_width,
        "height": height,
        "ref": params.get("ref"),
    }


def _append_precision_oes_rows(
    rows: List[Dict[str, Any]],
    runway,
    end,
    design_group: str,
    params: Mapping[str, Any],
) -> None:
    components = params.get("components", {})
    for component_name, operation_name in (
        ("approach", "Precision approach"),
        ("missed_approach", "Precision missed approach"),
    ):
        component = components.get(component_name, {})
        start_rule = (
            f"{_format_number(component.get('distance_from_threshold_m'))} m from threshold"
            if component.get("distance_from_threshold_m") is not None
            else f"{_format_number(component.get('distance_after_threshold_m'))} m after threshold"
        )
        for section in component.get("sections", ()):
            rows.append(
                _modern_oes_row(
                    runway,
                    end,
                    design_group,
                    operation_name,
                    "Precision approach",
                    f"{component_name} {section.get('section')}",
                    params,
                    start_rule=start_rule,
                    inner_edge=component.get("inner_edge_length_m"),
                    length=section.get("length_m"),
                    divergence=section.get("divergence"),
                    slope=section.get("slope"),
                )
            )
    transitional = components.get("transitional", {})
    rows.append(
        _modern_oes_row(
            runway,
            end,
            design_group,
            "Precision approach",
            "Precision approach",
            "Transitional",
            params,
            start_rule=transitional.get("lower_edge_rule"),
            slope=transitional.get("slope"),
            height=transitional.get("upper_edge_height_above_threshold_m"),
        )
    )


def _append_section_oes_rows(
    rows: List[Dict[str, Any]],
    runway,
    end,
    design_group: str,
    operation: str,
    surface: str,
    params: Mapping[str, Any],
    *,
    start_rule: Any = None,
    inner_edge: Any = None,
    slope: Any = None,
    height: Any = None,
) -> None:
    for section in params.get("sections", ()):
        rows.append(
            _modern_oes_row(
                runway,
                end,
                design_group,
                operation,
                surface,
                section.get("section"),
                params,
                start_rule=start_rule,
                inner_edge=inner_edge,
                length=section.get("length_m"),
                divergence=section.get("divergence"),
                slope=section.get("slope", slope),
                height=height,
            )
        )


def write_ols_table_markdown(
    report: Mapping[str, Any],
    output_path: Path | str,
) -> str:
    """Write a UTF-8 Markdown report."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_ols_table_markdown(report), encoding="utf-8")
    return str(output)


def _resolved_parameters(
    policy,
    ruleset,
    context,
    runway,
    end,
    surface_type: str,
    runway_type: Optional[str] = None,
) -> Dict[str, Any]:
    if runway is None:
        return {}
    params = policy.parameters(
        ruleset,
        context,
        runway,
        end,
        runway.arc_number,
        runway_type or (end.approach_type if end is not None else None),
        surface_type,
    )
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, (list, tuple)):
        return {"sections": [dict(item) for item in params]}
    return {}


def _sections(params: Mapping[str, Any]) -> List[Dict[str, Any]]:
    if "sections" in params:
        return [dict(item) for item in params.get("sections") or ()]
    return [dict(params)] if params else []


def _governing_runway(context, airport_spec: Mapping[str, Any]):
    runway_id = airport_spec.get("governing_runway_id")
    for runway in getattr(context, "runways", ()):
        if runway.runway_id == runway_id:
            return runway
    return getattr(context, "main_runway", None)


def _governing_end(runway):
    if runway is None:
        return None
    rank = {"NI": 0, "NPA": 1, "PA_I": 2, "PA_II_III": 3}
    return max(runway.ends, key=lambda end: rank.get(end.classified_type, -1))


def _datum_label(value: Any) -> str:
    labels = {
        "reference_elevation_datum": "REFERENCE ELEV DATUM",
        "lowest_runway_threshold": "LOWEST THRESHOLD DATUM",
    }
    return labels.get(str(value or ""), "OLS ELEVATION DATUM")


def _markdown_table(
    headers: Iterable[Any],
    rows: Iterable[Iterable[Any]],
) -> str:
    header_values = [_markdown_cell(value) for value in headers]
    lines = [
        "| " + " | ".join(header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_markdown_cell(value) for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def _format_number(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "N/A"
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}"
    return f"{number:,.3f}".rstrip("0").rstrip(".")


def _format_percent(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "N/A"
    return f"{number * 100:.2f}".rstrip("0").rstrip(".") + "%"


def _format_value_or_rule(value: Any, rule: Any) -> str:
    number = _number(value)
    if number is not None:
        return _format_number(number)
    return _markdown_cell(
        str(rule).replace("_", " ") if rule not in (None, "") else None
    )


def _format_report_timestamp(value: Any) -> str:
    if not isinstance(value, datetime):
        return _markdown_cell(value)
    timestamp = value
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=REPORT_TIMEZONE)
    else:
        timestamp = timestamp.astimezone(REPORT_TIMEZONE)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S %Z")


def _number(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_optional(first: Any, second: Any) -> Optional[float]:
    left = _number(first)
    right = _number(second)
    return left + right if left is not None and right is not None else None


def _collect_ref(references: set, params: Any) -> None:
    if isinstance(params, Mapping) and params.get("ref"):
        references.add(str(params["ref"]))


def _collect_refs(references: set, value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).endswith("ref") and item:
                references.add(str(item))
            else:
                _collect_refs(references, item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_refs(references, item)


def _markdown_cell(value: Any) -> str:
    text = str(value if value not in (None, "") else "N/A")
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


__all__ = [
    "build_modernised_ols_table_values",
    "build_ols_table_values",
    "render_ols_table_markdown",
    "write_ols_table_markdown",
]
