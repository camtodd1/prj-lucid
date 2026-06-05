# -*- coding: utf-8 -*-
"""Shared helpers for NASF guideline processor mixins."""

from ..registry import get_framework_profile


class NasfGuidelineProcessorBase:
    def _active_safeguarding_framework(self):
        getter = getattr(self, "get_active_framework", None)
        if callable(getter):
            return getter()
        return get_framework_profile()
