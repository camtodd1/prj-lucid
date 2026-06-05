# -*- coding: utf-8 -*-
"""Compatibility shim for NASF CNS BRA dimensions."""

try:
    from ..frameworks.nasf import cns as _cns
except ImportError:
    from frameworks.nasf import cns as _cns

for _name in dir(_cns):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_cns, _name)

__all__ = [_name for _name in globals() if not _name.startswith("_")]
