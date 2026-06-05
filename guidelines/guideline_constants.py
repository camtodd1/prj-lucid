# -*- coding: utf-8 -*-
"""Deprecated compatibility re-exports for historical guideline constants."""

try:
    from ..core import constants as _core_constants
    from ..frameworks.nasf import guidelines as _nasf_guidelines
    from ..surfaces import constants as _surface_constants
    from . import ols_constants as _ols_constants
except ImportError:
    from core import constants as _core_constants
    from frameworks.nasf import guidelines as _nasf_guidelines
    from guidelines import ols_constants as _ols_constants
    from surfaces import constants as _surface_constants

_OWNER_MODULES = (_core_constants, _nasf_guidelines, _ols_constants, _surface_constants)
__all__ = sorted({name for module in _OWNER_MODULES for name in getattr(module, "__all__", ())})

for _module in _OWNER_MODULES:
    for _name in getattr(_module, "__all__", ()):
        globals()[_name] = getattr(_module, _name)

del _core_constants, _module, _name, _nasf_guidelines, _ols_constants, _OWNER_MODULES, _surface_constants
