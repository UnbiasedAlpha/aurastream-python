"""HTTP client for the AuraStream `/timeseries` endpoint."""

from __future__ import annotations

import os
import random
import time
from datetime import date, datetime
from typing import Any, Iterable, Mapping

import requests

from . import __version__
from .exceptions import (
    AuraStreamError,
    AuthenticationError,
    BadRequestError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)

DEFAULT_BASE_URL = "https://api.aurastream.unbiased-alpha.com"
API_KEY_ENV = "AURASTREAM_API_KEY"

# Provider credentials the client can pick up from environment variables.
# Variable names match the ones used by aurastream-mcp.
_ENV_CREDENTIALS: dict[str, dict[str, str]] = {
    "fred": {"key": "FRED_API_KEY"},
    "oanda": {"id": "OANDA_ACCOUNT_ID", "token": "OANDA_TOKEN", "environment": "OANDA_ENVIRONMENT"},
    "signals": {"key": "NEMETON_API_KEY"},
    "nemeton": {"key": "NEMETON_API_KEY"},
}
_ENV_DEFAULTS = {"OANDA_ENVIRONMENT": "practice"}

DateLike = str | date | datetime


def _fmt_date(value: DateLike) -> str:
    """Format a date for the API: `YYYY-MM-DD`, or `YYYY-MM-DD HH:MM` (UTC) when a time is given."""
    if isinstance(value, datetime):
        if value.hour or value.minute:
            return value.strftime("%Y-%m-%d %H:%M")
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _credentials_from_env(source: str) -> dict[str, str] | None:
    mapping = _ENV_CREDENTIALS.get(source)
    if not mapping:
        return None
    creds = {}
    for field, var in mapping.items():
        value = os.environ.get(var, _ENV_DEFAULTS.get(var))
        if value is None:
            return None
        creds[field] = value
    return creds


class AuraStream:
    """Client for the AuraStream unified market data API.

    >>> from aurastream_client import AuraStream
    >>> client = AuraStream()                      # reads AURASTREAM_API_KEY
    >>> df = client.get_frame("BTCUSDT", "2025-01-01", "2025-06-30", source="binance")

    Args:
        api_key: Your AuraStream key. Defaults to the `AURASTREAM_API_KEY` environment variable.
        base_url: API base URL.
        timeout: Seconds to wait for a response. The API gateway stops a request after about 30 s
            (504); split long ranges or ticker lists with `batch_size` or several calls.
        max_retries: Retries for rate limiting (429 "Too Many Requests") and other 5xx errors,
            with exponential backoff. 400, 403, an exhausted monthly allowance and 504 (the same
            request would time out again) are never retried.
        session: Optional `requests.Session` to reuse connections or add proxies.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ):
        self.api_key = api_key or os.environ.get(API_KEY_ENV)
        if not self.api_key:
            raise AuthenticationError(
                f"No API key. Pass api_key=... or set {API_KEY_ENV}. "
                "Get a free key (500 calls/month, no card) at https://aurastream.unbiased-alpha.com"
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": f"aurastream-python/{__version__}",
            }
        )

    # ------------------------------------------------------------------ raw API

    def timeseries(
        self,
        tickers: str | Iterable[str],
        start: DateLike,
        end: DateLike,
        interval: str = "1d",
        *,
        source: str,
        credentials: Mapping[str, Any] | None = None,
        batch_size: int | None = None,
        **params: Any,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Call `POST /timeseries` and return the raw JSON: `{ticker: {timestamp: {field: value}}}`.

        Args:
            tickers: One ticker or a list, in the source's own format (`BTCUSDT`, `EUR_USD`, `CPIAUCSL`...).
            start, end: `YYYY-MM-DD`, `YYYY-MM-DD HH:MM` (UTC), or `date`/`datetime` objects.
            interval: `1s 5s 30s 1M 5M 15M 30M 1h 4h 1d 1w 1m` (case matters: `1M` = minute, `1m` = month).
            source: Source identifier, e.g. `binance`, `bybit`, `fred`, `oanda`, `cftc`, `sdmx`, `treasury`.
            credentials: Provider credentials. If omitted, read from environment variables where supported
                (FRED_API_KEY, OANDA_ACCOUNT_ID/OANDA_TOKEN/OANDA_ENVIRONMENT, NEMETON_API_KEY).
            batch_size: Split a long ticker list into several requests of this size and merge the results.
                Each request counts as one call against your allowance.
            **params: Source-specific fields passed through as-is (`dtype`, `instrument`, `bars`,
                `price_type`, `dataset`, `report`, `as_of`...).
        """
        tickerlist = [tickers] if isinstance(tickers, str) else list(tickers)
        if not tickerlist:
            raise ValueError("tickers must not be empty")
        if credentials is None:
            credentials = _credentials_from_env(source)

        base_body: dict[str, Any] = {
            "start": _fmt_date(start),
            "end": _fmt_date(end),
            "interval": interval,
            "source": source,
            "credentials": dict(credentials) if credentials else None,
            **params,
        }

        size = batch_size or len(tickerlist)
        result: dict[str, Any] = {}
        for i in range(0, len(tickerlist), size):
            body = {"tickerlist": tickerlist[i : i + size], **base_body}
            result.update(self._post("/timeseries", body))
        return result

    # ------------------------------------------------------------- pandas helpers

    def get_frame(self, ticker: str, start: DateLike, end: DateLike, interval: str = "1d", *, source: str, **kwargs: Any):
        """Fetch one ticker as a pandas DataFrame indexed by UTC timestamp, with numeric columns."""
        from .frames import to_frame

        data = self.timeseries(ticker, start, end, interval, source=source, **kwargs)
        return to_frame(data, ticker)

    def get_panel(
        self,
        tickers: Iterable[str],
        start: DateLike,
        end: DateLike,
        interval: str = "1d",
        *,
        source: str,
        field: str = "Close",
        **kwargs: Any,
    ):
        """Fetch several tickers and return one wide DataFrame of `field` (one column per ticker)."""
        from .frames import to_panel

        data = self.timeseries(list(tickers), start, end, interval, source=source, **kwargs)
        return to_panel(data, field=field)

    # ---------------------------------------------------------------- internals

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        attempt = 0
        while True:
            try:
                resp = self.session.post(url, json=body, timeout=self.timeout)
            except requests.Timeout as exc:
                if attempt < self.max_retries:
                    self._sleep(attempt)
                    attempt += 1
                    continue
                raise ServerError(f"Request timed out after {self.timeout}s") from exc
            except requests.RequestException as exc:
                raise AuraStreamError(f"Network error: {exc}") from exc

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    data = None
                # Request errors (missing credentials, unknown source) come back as 200 {"error": "..."}
                if isinstance(data, dict) and set(data) == {"error"} and isinstance(data["error"], str):
                    raise BadRequestError(data["error"], resp.status_code, data)
                if isinstance(data, dict):
                    return data
                # A failure inside the server can come back as 200 with a plain-text body
                error = ServerError(f"Unexpected response from the server: {resp.text[:200]}", resp.status_code, resp.text)
            else:
                error = self._error_for(resp)
            retryable = isinstance(error, (RateLimitError, ServerError)) and resp.status_code != 504
            if retryable and attempt < self.max_retries:
                self._sleep(attempt)
                attempt += 1
                continue
            raise error

    @staticmethod
    def _sleep(attempt: int) -> None:
        time.sleep(min(2**attempt, 30) + random.uniform(0, 0.5))

    @staticmethod
    def _error_for(resp: requests.Response) -> AuraStreamError:
        try:
            body = resp.json()
            message = body.get("message", resp.text) if isinstance(body, dict) else resp.text
        except ValueError:
            body, message = resp.text, resp.text or resp.reason
        code = resp.status_code
        if code == 400:
            return BadRequestError(message, code, body)
        if code == 403:
            return AuthenticationError(message, code, body)
        if code == 429:
            if "limit exceeded" in str(message).lower():
                return QuotaExceededError(
                    f"{message}: monthly allowance used up. It resets on the 1st at 00:00 UTC, "
                    "or upgrade at https://aurastream.unbiased-alpha.com",
                    code,
                    body,
                )
            return RateLimitError(message, code, body)
        if code == 504:
            return ServerError(
                f"{message}: the request took longer than the API allows (about 30 s). "
                "Split it into shorter date ranges or fewer tickers (batch_size=...)",
                code,
                body,
            )
        if code >= 500:
            return ServerError(message, code, body)
        return AuraStreamError(message, code, body)
