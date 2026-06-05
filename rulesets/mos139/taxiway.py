"""MOS139 taxiway separation policy."""

import logging
from typing import Any, Dict, Optional, Tuple

from .classification import get_runway_type_abbr

LOGGER = logging.getLogger(__name__)

TAXIWAY_SEPARATION_PARAMS: Dict[Tuple[int, str, str], Dict[str, Any]] = {
    (1, "A", "PA_I"): {"offset_m": 77.5, "ref": "MOS T9.1 (Verify 1A-PA)"},
    (1, "B", "PA_I"): {"offset_m": 82.0, "ref": "MOS T9.1 (Verify 1B-PA)"},
    (1, "C", "PA_I"): {"offset_m": 88.0, "ref": "MOS T9.1 (Verify 1C-PA)"},
    (1, "A", "PA_II_III"): {"offset_m": 77.5, "ref": "MOS T9.1 (Verify 1A-PA)"},
    (1, "B", "PA_II_III"): {"offset_m": 82.0, "ref": "MOS T9.1 (Verify 1B-PA)"},
    (1, "C", "PA_II_III"): {"offset_m": 88.0, "ref": "MOS T9.1 (Verify 1C-PA)"},
    (2, "A", "PA_I"): {"offset_m": 77.5, "ref": "MOS T9.1 (Verify 2A-PA)"},
    (2, "B", "PA_I"): {"offset_m": 82.0, "ref": "MOS T9.1 (Verify 2B-PA)"},
    (2, "C", "PA_I"): {"offset_m": 88.0, "ref": "MOS T9.1 (Verify 2C-PA)"},
    (2, "A", "PA_II_III"): {"offset_m": 77.5, "ref": "MOS T9.1 (Verify 2A-PA)"},
    (2, "B", "PA_II_III"): {"offset_m": 82.0, "ref": "MOS T9.1 (Verify 2B-PA)"},
    (2, "C", "PA_II_III"): {"offset_m": 88.0, "ref": "MOS T9.1 (Verify 2C-PA)"},
    (3, "A", "PA_I"): {"offset_m": 152.0, "ref": "MOS T9.1 (Verify 3A-PA)"},
    (3, "B", "PA_I"): {"offset_m": 152.0, "ref": "MOS T9.1 (Verify 3B-PA)"},
    (3, "C", "PA_I"): {"offset_m": 158.0, "ref": "MOS T9.1 (Verify 3C-PA)"},
    (3, "D", "PA_I"): {"offset_m": 166.0, "ref": "MOS T9.1 (Verify 3D-PA)"},
    (3, "E", "PA_I"): {"offset_m": 172.5, "ref": "MOS T9.1 (Verify 3E-PA)"},
    (3, "F", "PA_I"): {"offset_m": 180.0, "ref": "MOS T9.1 (Verify 3F-PA)"},
    (3, "A", "PA_II_III"): {"offset_m": 152.0, "ref": "MOS T9.1 (Verify 3A-PA)"},
    (3, "B", "PA_II_III"): {"offset_m": 152.0, "ref": "MOS T9.1 (Verify 3B-PA)"},
    (3, "C", "PA_II_III"): {"offset_m": 158.0, "ref": "MOS T9.1 (Verify 3C-PA)"},
    (3, "D", "PA_II_III"): {"offset_m": 166.0, "ref": "MOS T9.1 (Verify 3D-PA)"},
    (3, "E", "PA_II_III"): {"offset_m": 172.5, "ref": "MOS T9.1 (Verify 3E-PA)"},
    (3, "F", "PA_II_III"): {"offset_m": 180.0, "ref": "MOS T9.1 (Verify 3F-PA)"},
    (4, "C", "PA_I"): {"offset_m": 158.0, "ref": "MOS T9.1 (Verify 4C-PA)"},
    (4, "D", "PA_I"): {"offset_m": 166.0, "ref": "MOS T9.1 (Verify 4D-PA)"},
    (4, "E", "PA_I"): {"offset_m": 172.5, "ref": "MOS T9.1 (Verify 4E-PA)"},
    (4, "F", "PA_I"): {"offset_m": 180.0, "ref": "MOS T9.1 (Verify 4F-PA)"},
    (4, "C", "PA_II_III"): {"offset_m": 158.0, "ref": "MOS T9.1 (Verify 4C-PA)"},
    (4, "D", "PA_II_III"): {"offset_m": 166.0, "ref": "MOS T9.1 (Verify 4D-PA)"},
    (4, "E", "PA_II_III"): {"offset_m": 172.5, "ref": "MOS T9.1 (Verify 4E-PA)"},
    (4, "F", "PA_II_III"): {"offset_m": 180.0, "ref": "MOS T9.1 (Verify 4F-PA)"},
    (1, "A", "NPA"): {"offset_m": 77.5, "ref": "MOS T9.1 (Verify 1A-NPA)"},
    (1, "B", "NPA"): {"offset_m": 82.0, "ref": "MOS T9.1 (Verify 1B-NPA)"},
    (1, "C", "NPA"): {"offset_m": 88.0, "ref": "MOS T9.1 (Verify 1C-NPA)"},
    (2, "A", "NPA"): {"offset_m": 77.5, "ref": "MOS T9.1 (Verify 2A-NPA)"},
    (2, "B", "NPA"): {"offset_m": 82.0, "ref": "MOS T9.1 (Verify 2B-NPA)"},
    (2, "C", "NPA"): {"offset_m": 88.0, "ref": "MOS T9.1 (Verify 2C-NPA)"},
    (3, "A", "NPA"): {"offset_m": 152.0, "ref": "MOS T9.1 (Verify 3A-NPA)"},
    (3, "B", "NPA"): {"offset_m": 152.0, "ref": "MOS T9.1 (Verify 3B-NPA)"},
    (3, "C", "NPA"): {"offset_m": 158.0, "ref": "MOS T9.1 (Verify 3C-NPA)"},
    (3, "D", "NPA"): {"offset_m": 166.0, "ref": "MOS T9.1 (Verify 3D-NPA)"},
    (3, "E", "NPA"): {"offset_m": 172.5, "ref": "MOS T9.1 (Verify 3E-NPA)"},
    (3, "F", "NPA"): {"offset_m": 180.0, "ref": "MOS T9.1 (Verify 3F-NPA)"},
    (4, "C", "NPA"): {"offset_m": 158.0, "ref": "MOS T9.1 (Verify 4C-NPA)"},
    (4, "D", "NPA"): {"offset_m": 166.0, "ref": "MOS T9.1 (Verify 4D-NPA)"},
    (4, "E", "NPA"): {"offset_m": 172.5, "ref": "MOS T9.1 (Verify 4E-NPA)"},
    (4, "F", "NPA"): {"offset_m": 180.0, "ref": "MOS T9.1 (Verify 4F-NPA)"},
    (1, "A", "NI"): {"offset_m": 37.5, "ref": "MOS T9.1 (Verify 1A-NI)"},
    (1, "B", "NI"): {"offset_m": 42.0, "ref": "MOS T9.1 (Verify 1B-NI)"},
    (1, "C", "NI"): {"offset_m": 48.0, "ref": "MOS T9.1 (Verify 1C-NI)"},
    (2, "A", "NI"): {"offset_m": 47.5, "ref": "MOS T9.1 (Verify 2A-NI)"},
    (2, "B", "NI"): {"offset_m": 52.0, "ref": "MOS T9.1 (Verify 2B-NI)"},
    (2, "C", "NI"): {"offset_m": 58.0, "ref": "MOS T9.1 (Verify 2C-NI)"},
    (3, "A", "NI"): {"offset_m": 52.5, "ref": "MOS T9.1 (Verify 3A-NI)"},
    (3, "B", "NI"): {"offset_m": 87.0, "ref": "MOS T9.1 (Verify 3B-NI)"},
    (3, "C", "NI"): {"offset_m": 93.0, "ref": "MOS T9.1 (Verify 3C-NI)"},
    (3, "D", "NI"): {"offset_m": 101.0, "ref": "MOS T9.1 (Verify 3D-NI)"},
    (3, "E", "NI"): {"offset_m": 107.5, "ref": "MOS T9.1 (Verify 3E-NI)"},
    (3, "F", "NI"): {"offset_m": 115.0, "ref": "MOS T9.1 (Verify 3F-NI)"},
    (4, "C", "NI"): {"offset_m": 93.0, "ref": "MOS T9.1 (Verify 4C-NI)"},
    (4, "D", "NI"): {"offset_m": 101.0, "ref": "MOS T9.1 (Verify 4D-NI)"},
    (4, "E", "NI"): {"offset_m": 107.5, "ref": "MOS T9.1 (Verify 4E-NI)"},
    (4, "F", "NI"): {"offset_m": 115.0, "ref": "MOS T9.1 (Verify 4F-NI)"},
}


def get_taxiway_separation_offset(
    arc_num: int, arc_let: Optional[str], runway_type_str: Optional[str]
) -> Optional[Dict[str, Any]]:
    if not isinstance(arc_num, int) or arc_num not in [1, 2, 3, 4]:
        LOGGER.warning("Invalid ARC Number %r for Taxiway Sep lookup.", arc_num)
        return None

    rwy_abbr = get_runway_type_abbr(runway_type_str)
    arc_let_str = arc_let.strip().upper() if arc_let else ""
    if not arc_let_str:
        LOGGER.info(
            "Missing ARC Letter for Taxiway Sep lookup (Code %s, Type %s).",
            arc_num,
            rwy_abbr,
        )

    key = (arc_num, arc_let_str, rwy_abbr)
    params = TAXIWAY_SEPARATION_PARAMS.get(key)
    if not params and arc_let_str != "":
        params = TAXIWAY_SEPARATION_PARAMS.get((arc_num, "", rwy_abbr))
    return params.copy() if params else None


__all__ = [
    "TAXIWAY_SEPARATION_PARAMS",
    "get_taxiway_separation_offset",
]
