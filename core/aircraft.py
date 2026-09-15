"""Bundled design-aircraft dimensions, independent of any design ruleset."""

import csv
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def aircraft_registry():
    with (Path(__file__).resolve().parents[1] / "data" / "aircraft.csv").open(
        encoding="utf-8", newline=""
    ) as source:
        records = list(csv.DictReader(source))
    registry = {record["id"]: record for record in records}
    if "" in registry or len(registry) != len(records):
        raise ValueError("Aircraft registry requires unique, non-empty IDs.")
    return registry


def aircraft_gear_span(inputs):
    """Selected aircraft takes precedence over a legacy saved gear dimension."""
    aircraft_id = str(inputs.get("design_aircraft_id") or "").strip()
    if aircraft_id:
        aircraft = aircraft_registry().get(aircraft_id)
        if aircraft is None:
            raise ValueError(f"Design aircraft '{aircraft_id}' is unavailable; select an aircraft from the list.")
        span = aircraft.get("outer_main_gear_wheel_span_m")
    else:
        span = inputs.get("outer_main_gear_wheel_span_m")
    return float(span) if span not in (None, "") else None
