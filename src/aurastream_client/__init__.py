"""AuraStream: one endpoint for market, macro and alternative data from 47 sources."""

__version__ = "0.1.0"

from .client import AuraStream  # noqa: E402
from .exceptions import (  # noqa: E402
    AuraStreamError,
    AuthenticationError,
    BadRequestError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)

__all__ = [
    "AuraStream",
    "AuraStreamError",
    "AuthenticationError",
    "BadRequestError",
    "QuotaExceededError",
    "RateLimitError",
    "ServerError",
    "__version__",
]
