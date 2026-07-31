# -*- coding: utf-8 -*-
"""Per-run obstacle limitation surface table report."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


TYPE_LABELS = {
    "NI": "NON INST",
    "NPA": "NON PREC",
    "PA_I": "PREC CAT I",
    "PA_II_III": "PREC CAT II/III",
}


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


def render_ols_table_markdown(report: Mapping[str, Any]) -> str:
    """Render the resolved OLS values as a VS Code-friendly Markdown report."""
    airport = report.get("airport", {})
    horizontal = report.get("horizontal", {})
    generated_at = report.get("generated_at")
    generated_text = (
        generated_at.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(generated_at, datetime)
        else _markdown_cell(generated_at)
    )
    lines = [
        "# Obstacle Restriction and Limitation Surfaces Table of Values",
        "",
        f"## {_markdown_cell(report.get('icao_code'))} Safeguarding OLS",
        "",
        f"- Baseline ruleset: {_markdown_cell(report.get('ruleset_name'))} "
        f"({_markdown_cell(report.get('ruleset_edition'))})",
        f"- Ruleset ID: `{_markdown_cell(report.get('ruleset_id'))}`",
        f"- Generated: {generated_text}",
        f"- Run ID: `{_markdown_cell(report.get('run_id'))}`",
        f"- Test case ID: `{_markdown_cell(report.get('test_case_id'))}`",
        f"- Input fingerprint: `{_markdown_cell(report.get('input_fingerprint'))}`",
        "- Units: distances and lengths in metres; elevations in metres AMSL",
        "",
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
        "- Values are resolved from the selected baseline OLS ruleset and the "
        "processed runway inputs used for this run.",
    ]
    lines.extend(f"- {_markdown_cell(value)}" for value in report.get("warnings", ()))
    lines.extend(["", "### Source references", ""])
    references = report.get("references", ())
    lines.extend(
        [f"- {_markdown_cell(reference)}" for reference in references]
        or ["- N/A"]
    )
    return "\n".join(lines).rstrip() + "\n"


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


def _markdown_cell(value: Any) -> str:
    text = str(value if value not in (None, "") else "N/A")
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


__all__ = [
    "build_ols_table_values",
    "render_ols_table_markdown",
    "write_ols_table_markdown",
]
