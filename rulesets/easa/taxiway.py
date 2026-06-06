"""EASA taxiway separation policy placeholders."""

import logging
from typing import Any, Dict, Optional

LOGGER = logging.getLogger(__name__)


def get_taxiway_separation_offset(
    arc_num: int, arc_let: Optional[str], runway_type_str: Optional[str]
) -> Optional[Dict[str, Any]]:
    LOGGER.info(
        "EASA taxiway separation lookup is not implemented yet (Code %r, Letter %r, Type %r).",
        arc_num,
        arc_let,
        runway_type_str,
    )
    return None


__all__ = ["get_taxiway_separation_offset"]
