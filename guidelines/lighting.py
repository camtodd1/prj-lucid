# -*- coding: utf-8 -*-
"""Compatibility shim for NASF Guideline E lighting control zones."""

try:
    from ..frameworks.nasf.lighting import LightingGuidelineMixin
except ImportError:
    from frameworks.nasf.lighting import LightingGuidelineMixin

__all__ = ["LightingGuidelineMixin"]
