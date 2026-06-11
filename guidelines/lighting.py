# -*- coding: utf-8 -*-
"""Compatibility shim for NASF-backed lighting control safeguarding."""

try:
    from ..frameworks.nasf.lighting import LightingGuidelineMixin
except ImportError:
    from frameworks.nasf.lighting import LightingGuidelineMixin

__all__ = ["LightingGuidelineMixin"]
