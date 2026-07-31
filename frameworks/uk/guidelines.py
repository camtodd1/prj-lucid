"""Source-scoped parameters for implemented UK safeguarding mechanisms."""

from typing import Mapping, Optional


DEFAULT_WILDLIFE_RADIUS_KM = 13.0
DEFAULT_WIND_TURBINE_RADIUS_KM = 30.0
BUFFER_SEGMENTS = 144


def wildlife_parameters(options: Optional[Mapping[str, object]] = None) -> dict:
    """Return the fixed UK wildlife consultation radius."""
    del options
    return {
        "model": "uk_consultation_circle",
        "radius_m": DEFAULT_WILDLIFE_RADIUS_KM * 1000.0,
        "buffer_segments": BUFFER_SEGMENTS,
        "family_id": "wildlife_consultation",
        "profile_id": "uk_caa_safeguarding",
        "source_id": "UK-1; UK-3",
        "source_ref": "CAP 738; CAP 772",
        "source_version": "CAP 738 v3; CAP 772 v2",
        "authority_level": "CAA guidance and officially lodged safeguarding map",
        "applicability": "officially safeguarded aerodrome; operator map controls",
        "geometry_status": "indicative_default",
        "assessment_result": "consult",
        "caveat": (
            "Not a universal wildlife-risk boundary; the officially lodged aerodrome "
            "safeguarding map and site-specific wildlife assessment control."
        ),
    }


def wind_turbine_parameters(options: Optional[Mapping[str, object]] = None) -> dict:
    """Return the fixed UK wind-turbine consultation radius."""
    del options
    return {
        "model": "uk_consultation_circle",
        "radius_m": DEFAULT_WIND_TURBINE_RADIUS_KM * 1000.0,
        "buffer_segments": BUFFER_SEGMENTS,
        "family_id": "wind_energy_consultation",
        "profile_id": "uk_caa_safeguarding",
        "source_id": "UK-1; UK-4",
        "source_ref": "CAP 738; CAP 764",
        "source_version": "CAP 738 v3; CAP 764 v7",
        "authority_level": "CAA guidance and officially lodged safeguarding map",
        "applicability": "officially safeguarded aerodrome; operator map controls",
        "geometry_status": "indicative_default",
        "assessment_result": "consult",
        "caveat": (
            "The officially lodged renewable-energy safeguarding map or operator-supplied "
            "geometry overrides this default; the circle does not decide acceptability."
        ),
    }


def public_safety_area_parameters(options: Optional[Mapping[str, object]] = None) -> dict:
    """Return explicitly selected DfT Public Safety Zone parameters."""
    options = options or {}
    raw_enabled = options.get("psz_applicable", False)
    enabled = (
        raw_enabled.strip().casefold() in {"1", "true", "yes", "on"}
        if isinstance(raw_enabled, str)
        else bool(raw_enabled)
    )
    try:
        pscz_length = float(options.get("pscz_length_m"))
    except (TypeError, ValueError):
        pscz_length = 0.0
    if pscz_length not in {1000.0, 1500.0}:
        pscz_length = 0.0
    return {
        "model": "uk_psz_triangles",
        "enabled": enabled and pscz_length > 0,
        "selection_complete": (not enabled) or pscz_length > 0,
        "zones": (
            {
                "zone_code": "PSRZ",
                "family_id": "public_safety_ground_risk",
                "profile_id": "uk_dft_psz_2021",
                "length_m": 500.0,
                "threshold_half_width_m": 75.0,
                "distal_half_width_m": 0.0,
                "description": "Public Safety Restricted Zone",
            },
            {
                "zone_code": "PSCZ",
                "family_id": "public_safety_ground_risk",
                "profile_id": "uk_dft_psz_2021",
                "length_m": pscz_length,
                "threshold_half_width_m": 140.0,
                "distal_half_width_m": 0.0,
                "description": "Public Safety Controlled Zone",
            },
        ),
        "source_ref": "DfT Control of development in airport public safety zones",
        "source_id": "UK-5",
        "source_version": "8 October 2021",
        "authority_level": "DfT planning policy",
        "applicability": "operator-confirmed PSZ airport and relevant landing runway end",
        "geometry_status": "indicative_default",
        "assessment_result": "not_assessed",
        "caveat": (
            "Generate only where PSZ policy applicability has been confirmed. The official "
            "operator-produced PSZ map controls; exactly 45,000 CATMs requires an explicit choice."
        ),
    }


def crane_notification_parameters() -> dict:
    """Return the UK CAA crane-notification screening thresholds."""
    return {
        "family_id": "temporary_obstacle_notification",
        "profile_id": "uk_caa_cranes",
        "source_id": "UK-7",
        "local_distance_m": 6000.0,
        "local_height_agl_m": 10.0,
        "national_height_agl_m": 100.0,
        "source_ref": "UK CAA Crane notification",
        "source_version": "web guidance reviewed 31 July 2026",
        "authority_level": "CAA notification guidance",
        "applicability": "crane candidate with approved aerodrome distance basis",
        "geometry_status": "screening_only",
        "caveat": (
            "Distance is to the relevant aerodrome boundary or approved reference geometry. "
            "Notification does not imply obstacle approval."
        ),
    }


def screen_crane_notification(
    distance_to_aerodrome_m: float,
    height_agl_m: float,
    shielded_by_surroundings: bool = False,
) -> dict:
    """Screen a crane candidate against the published UK notification triggers."""
    params = crane_notification_parameters()
    distance_m = float(distance_to_aerodrome_m)
    height_m = float(height_agl_m)
    if distance_m < 0 or height_m < 0:
        raise ValueError("Crane distance and height must be non-negative.")
    national_trigger = height_m >= params["national_height_agl_m"]
    local_trigger = (
        distance_m <= params["local_distance_m"]
        and height_m > params["local_height_agl_m"]
        and not bool(shielded_by_surroundings)
    )
    reason_codes = []
    if local_trigger:
        reason_codes.append("within_6km_over_10m_unshielded")
    if national_trigger:
        reason_codes.append("at_or_above_100m_agl")
    return {
        "notification_required": bool(local_trigger or national_trigger),
        "local_trigger": local_trigger,
        "national_trigger": national_trigger,
        "reason_codes": tuple(reason_codes),
        "family_id": params["family_id"],
        "profile_id": params["profile_id"],
        "source_id": params["source_id"],
        "source_ref": params["source_ref"],
        "source_version": params["source_version"],
        "authority_level": params["authority_level"],
        "applicability": params["applicability"],
        "geometry_status": params["geometry_status"],
        "assessment_result": "consult" if local_trigger or national_trigger else "not_assessed",
        "caveat": params["caveat"],
    }


__all__ = [
    "DEFAULT_WILDLIFE_RADIUS_KM",
    "DEFAULT_WIND_TURBINE_RADIUS_KM",
    "wildlife_parameters",
    "wind_turbine_parameters",
    "public_safety_area_parameters",
    "crane_notification_parameters",
    "screen_crane_notification",
]
