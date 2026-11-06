"""Exceptions raised by the AuraStream client."""

from __future__ import annotations


class AuraStreamError(Exception):
    """Base class for every error raised by this package."""

    def __init__(self, message: str, status_code: int | None = None, response_body: object = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        if self.status_code is None:
            return self.message
        return f"[{self.status_code}] {self.message}"


class BadRequestError(AuraStreamError):
    """400: unknown source, bad date format, unsupported interval or missing credentials."""


class AuthenticationError(AuraStreamError):
    """403: missing, invalid, deleted or paused API key."""


class RateLimitError(AuraStreamError):
    """429 "Too Many Requests": you are sending requests faster than your plan allows."""


class QuotaExceededError(AuraStreamError):
    """429 "Limit Exceeded": the monthly call allowance is used up (resets on the 1st, 00:00 UTC)."""


class ServerError(AuraStreamError):
    """500 or 504: an upstream data source failed or the request timed out."""
