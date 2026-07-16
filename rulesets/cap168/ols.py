"""UK CAA CAP 168 obstacle-limitation wrappers.

The public lookups expose the source-loaded runway-direction tables.  Airport-
wide IHS/conical/OHS decisions remain context-dependent and are supplied by
the CAP168 construction policy rather than this legacy lookup facade.
"""

from . import ols_surfaces


def ihs_base_height():
    return ols_surfaces.get_ihs_base_height()


def ols_parameters(arc_num: int, runway_type, surface_type: str):
    return ols_surfaces.get_ols_params(arc_num, runway_type, surface_type)


__all__ = ["ihs_base_height", "ols_parameters"]
