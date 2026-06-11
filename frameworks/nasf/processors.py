# -*- coding: utf-8 -*-
"""Composed safeguarding generator mixin backed by NASF policy parameters."""

from .airport_guidelines import NasfAirportGuidelinesMixin
from .cns_guideline import NasfCnsGuidelineMixin
from .runway_guidelines import NasfRunwayGuidelinesMixin


class NasfGuidelinesMixin(
    NasfRunwayGuidelinesMixin,
    NasfAirportGuidelinesMixin,
    NasfCnsGuidelineMixin,
):
    """Aggregate NASF-backed safeguarding generators."""


__all__ = ["NasfGuidelinesMixin"]
