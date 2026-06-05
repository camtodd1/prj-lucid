# -*- coding: utf-8 -*-
"""Composed NASF guideline processor mixin."""

from .airport_guidelines import NasfAirportGuidelinesMixin
from .cns_guideline import NasfCnsGuidelineMixin
from .runway_guidelines import NasfRunwayGuidelinesMixin


class NasfGuidelinesMixin(
    NasfRunwayGuidelinesMixin,
    NasfAirportGuidelinesMixin,
    NasfCnsGuidelineMixin,
):
    """Aggregate NASF Guideline A/B/C/D/G/I processors."""


__all__ = ["NasfGuidelinesMixin"]
