# -*- coding: utf-8 -*-
"""Critical runway information summary report rendering."""

from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


def build_runway_summaries(runway_data_list: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build report-friendly summary dictionaries from processed runway data."""
    return [_build_runway_summary(runway_data) for runway_data in runway_data_list]


def render_markdown_report(
    icao_code: str,
    airport_name: Optional[str],
    runway_summaries: List[Dict[str, Any]],
    generated_at: Optional[datetime] = None,
) -> str:
    """Render a compact human-readable Markdown runway summary report."""
    generated_at = generated_at or datetime.now()
    title_airport = f" - {airport_name}" if airport_name else ""
    lines = [
        f"# Critical Runway Information Summary - {icao_code}{title_airport}",
        "",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if not runway_summaries:
        lines.extend(["No processed runway data was available for reporting.", ""])
        return "\n".join(lines)

    for summary in runway_summaries:
        lines.extend(_render_runway_summary(summary))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_runway_summary(runway_data: Dict[str, Any]) -> Dict[str, Any]:
    runway_name = runway_data.get("short_name") or f"RWY_{runway_data.get('original_index', '?')}"
    declared_distances = list(runway_data.get("declared_distances") or [])
    feature_counts = dict(runway_data.get("generated_feature_counts") or {})
    mos_refs = _collect_mos_refs(runway_data)
    warnings = _collect_warnings(runway_data, feature_counts)

    return {
        "runway": runway_name,
        "designators": _split_designators(runway_name),
        "bearing_primary": _first_declared_value(declared_distances, "primary", "bearing_deg"),
        "bearing_reciprocal": _first_declared_value(declared_distances, "reciprocal", "bearing_deg"),
        "threshold_length": _first_non_none(record.get("threshold_len_m") for record in declared_distances),
        "physical_length": _first_non_none(record.get("physical_len_m") for record in declared_distances),
        "width": runway_data.get("width"),
        "thresholds": [
            {
                "end": _split_designators(runway_name)[0],
                "point": runway_data.get("thr_point"),
                "elevation": runway_data.get("thr_elev_1"),
                "displaced": _number_or_zero(runway_data.get("thr_displaced_1")),
                "pre_threshold_area": _number_or_zero(runway_data.get("thr_pre_area_1")),
            },
            {
                "end": _split_designators(runway_name)[1],
                "point": runway_data.get("rec_thr_point"),
                "elevation": runway_data.get("thr_elev_2"),
                "displaced": _number_or_zero(runway_data.get("thr_displaced_2")),
                "pre_threshold_area": _number_or_zero(runway_data.get("thr_pre_area_2")),
            },
        ],
        "clearway_primary_end": _number_or_zero(runway_data.get("clearway1_len")),
        "clearway_reciprocal_end": _number_or_zero(runway_data.get("clearway2_len")),
        "stopway_primary_end": _number_or_zero(runway_data.get("stopway1_len")),
        "stopway_reciprocal_end": _number_or_zero(runway_data.get("stopway2_len")),
        "declared_distances": declared_distances,
        "feature_counts": feature_counts,
        "mos_refs": mos_refs,
        "warnings": warnings,
    }


def _render_runway_summary(summary: Dict[str, Any]) -> List[str]:
    primary, reciprocal = summary["designators"]
    lines = [
        f"## Runway {summary['runway']}",
        "",
        "### Geometry",
        "| Parameter | Value |",
        "| --- | ---: |",
        f"| Bearing {primary} | {_format_number(summary.get('bearing_primary'), ' deg')} |",
        f"| Bearing {reciprocal} | {_format_number(summary.get('bearing_reciprocal'), ' deg')} |",
        f"| Threshold-to-threshold length | {_format_number(summary.get('threshold_length'), ' m')} |",
        f"| Physical runway length | {_format_number(summary.get('physical_length'), ' m')} |",
        f"| Runway width | {_format_number(summary.get('width'), ' m')} |",
        "",
        "### Ends",
        "| End | Threshold coordinate | Elevation | Displaced threshold | Pre-threshold area | Clearway | Stopway |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    clearways = [summary.get("clearway_primary_end"), summary.get("clearway_reciprocal_end")]
    stopways = [summary.get("stopway_primary_end"), summary.get("stopway_reciprocal_end")]
    for index, threshold in enumerate(summary["thresholds"]):
        lines.append(
            "| {end} | {point} | {elev} | {disp} | {pre} | {clearway} | {stopway} |".format(
                end=threshold["end"],
                point=_format_point(threshold.get("point")),
                elev=_format_number(threshold.get("elevation"), " m"),
                disp=_format_number(threshold.get("displaced"), " m"),
                pre=_format_number(threshold.get("pre_threshold_area"), " m"),
                clearway=_format_number(clearways[index], " m"),
                stopway=_format_number(stopways[index], " m"),
            )
        )

    lines.extend(
        [
            "",
            "### Declared Distances",
            "| Direction | Bearing | TORA | TODA | ASDA | LDA | Takeoff | Landing |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for record in summary["declared_distances"]:
        lines.append(
            "| {end} | {bearing} | {tora} | {toda} | {asda} | {lda} | {takeoff} | {landing} |".format(
                end=record.get("end_desig") or "N/A",
                bearing=_format_number(record.get("bearing_deg"), " deg"),
                tora=_format_number(record.get("tora_m"), " m"),
                toda=_format_number(record.get("toda_m"), " m"),
                asda=_format_number(record.get("asda_m"), " m"),
                lda=_format_number(record.get("lda_m"), " m"),
                takeoff=_yes_no(record.get("takeoff_available")),
                landing=_yes_no(record.get("landing_available")),
            )
        )

    lines.extend(["", "### Generated Features"])
    if summary["feature_counts"]:
        lines.extend(["| Family | Count |", "| --- | ---: |"])
        for family, count in sorted(summary["feature_counts"].items()):
            lines.append(f"| {family} | {count} |")
    else:
        lines.append("No generated physical/protection feature counts were captured.")

    lines.extend(["", "### Warnings And Assumptions"])
    if summary["warnings"]:
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    else:
        lines.append("- None captured.")

    lines.extend(["", "### MOS References"])
    if summary["mos_refs"]:
        lines.extend(f"- {ref}" for ref in summary["mos_refs"])
    else:
        lines.append("- None captured.")

    return lines


def _collect_mos_refs(runway_data: Dict[str, Any]) -> List[str]:
    refs = set()
    for value in runway_data.get("generated_mos_refs") or []:
        for part in str(value).split(";"):
            part = part.strip()
            if part:
                refs.add(part)
    return sorted(refs)


def _collect_warnings(runway_data: Dict[str, Any], feature_counts: Dict[str, int]) -> List[str]:
    warnings = list(runway_data.get("summary_warnings") or [])
    if _number_or_zero(runway_data.get("clearway1_len")) == 0:
        warnings.append("Primary-end clearway is 0 m; TODA uses no clearway extension at that departure end.")
    if _number_or_zero(runway_data.get("clearway2_len")) == 0:
        warnings.append("Reciprocal-end clearway is 0 m; TODA uses no clearway extension at that departure end.")
    if _number_or_zero(runway_data.get("stopway1_len")) > 0 or _number_or_zero(runway_data.get("stopway2_len")) > 0:
        if not feature_counts.get("Stopway"):
            warnings.append("Stopway length is used in ASDA, but stopway geometry generation is not implemented yet.")
    if not runway_data.get("declared_distances"):
        warnings.append("Declared distances could not be calculated for this runway.")
    return sorted(set(warnings))


def summarize_generated_elements(generated_elements: Iterable[Any]) -> Dict[str, Any]:
    """Summarise generated element tuples emitted by physical geometry processing."""
    counts = Counter()
    refs = set()
    for item in generated_elements:
        try:
            element_type, _, attrs = item
        except (TypeError, ValueError):
            continue
        counts[str(element_type)] += 1
        ref = attrs.get("ref_mos") if isinstance(attrs, dict) else None
        if ref:
            refs.add(str(ref))
    return {"counts": dict(counts), "mos_refs": sorted(refs)}


def _split_designators(runway_name: str) -> List[str]:
    if "/" in runway_name:
        primary, reciprocal = runway_name.split("/", 1)
        return [primary, reciprocal]
    return [runway_name, "Reciprocal"]


def _first_declared_value(records: List[Dict[str, Any]], direction: str, key: str) -> Any:
    for record in records:
        if record.get("direction") == direction:
            return record.get(key)
    return None


def _first_non_none(values: Iterable[Any]) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _number_or_zero(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_number(value: Any, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.3f}".rstrip("0").rstrip(".") + suffix


def _format_point(point: Any) -> str:
    if point is None:
        return "N/A"
    try:
        return f"{float(point.x()):.3f}, {float(point.y()):.3f}"
    except Exception:
        return str(point)


def _yes_no(value: Any) -> str:
    return "Yes" if bool(value) else "No"
