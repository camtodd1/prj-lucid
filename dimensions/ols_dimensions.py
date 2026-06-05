"""Compatibility shim for legacy MOS139 OLS dimension imports.

The active MOS139 source now lives in rulesets.mos139.ols_dimensions so that
future standards can keep their dimensions inside their ruleset package.
"""

try:
    from ..rulesets.mos139.ols_dimensions import *  # noqa: F401,F403
except ImportError:
    from rulesets.mos139.ols_dimensions import *  # type: ignore  # noqa: F401,F403
