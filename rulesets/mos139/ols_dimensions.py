"""MOS139 OLS compatibility facade.

The real MOS139 policy sources are split across classification, physical_data,
taxiway, and ols_surfaces. This module preserves the older combined import
surface while callers migrate to the domain modules.
"""

from .classification import *  # noqa: F401,F403
from .ols_surfaces import *  # noqa: F401,F403
from .physical_data import *  # noqa: F401,F403
from .taxiway import *  # noqa: F401,F403
