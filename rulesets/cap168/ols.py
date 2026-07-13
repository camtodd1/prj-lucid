"""Capability-gated UK CAA CAP 168 obstacle-limitation wrappers.

Chapter 4 parameters are source-loaded in :mod:`rulesets.cap168.ols_surfaces`,
but the public ruleset facade must remain non-generating until the shared
constructor supports CAP168's elevation datum and runway-length plan rules.
"""


def ihs_base_height():
    return None


def ols_parameters(arc_num: int, runway_type, surface_type: str):
    del arc_num, runway_type, surface_type
    return None


__all__ = ["ihs_base_height", "ols_parameters"]
