"""Compatibility shim for legacy MOS139 AGL dimension imports.

The active MOS139 lighting source now lives in rulesets.mos139.lighting so
future standards can keep their lighting dimensions inside their ruleset
package.
"""

try:
    from ..rulesets.mos139 import lighting as _lighting
except ImportError:
    from rulesets.mos139 import lighting as _lighting  # type: ignore

for _name in dir(_lighting):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_lighting, _name)

__all__ = [_name for _name in globals() if not _name.startswith("_")]
