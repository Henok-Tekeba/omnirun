"""OmniRun core: inspection, estimation, verdict, recommendations.

This package contains no web framework code. It is safe to import from a CLI,
a notebook, or the API.
"""

from core.errors import HFError, InputError, InspectionError, OmniRunError

__all__ = ["HFError", "InputError", "InspectionError", "OmniRunError"]

__version__ = "0.1.0"
