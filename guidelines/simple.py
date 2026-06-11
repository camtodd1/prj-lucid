# -*- coding: utf-8 -*-
"""Compatibility shim for NASF-backed safeguarding generators."""

try:
    from ..frameworks.nasf.processors import NasfGuidelinesMixin as SimpleGuidelinesMixin
except ImportError:
    from frameworks.nasf.processors import NasfGuidelinesMixin as SimpleGuidelinesMixin

__all__ = ["SimpleGuidelinesMixin"]
