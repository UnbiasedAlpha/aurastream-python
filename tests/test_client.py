import json

import pandas as pd
import pytest
import responses

import aurastream_client.client as client_mod
from aurastream_client import (
    AuraStream,
    AuthenticationError,
    BadRequestError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)

URL = "https://api.aurastream.unbiased-alpha.com/timeseries"
SAMPLE = {
    "BTCUSDT": {
        "2025-01-02 00:00:00": {"Open": "94900.0", "High": "96100.0", "Low": "94200.0", "Close": "95800.0"},
        "2025-01-01 00:00:00": {"Open": "94500.0", "High": "95200.0", "Low": "93800.0", "Close": "94900.0"},
    }
}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(client_mod.AuraStream, "_sleep", staticmethod(lambda attempt: None))
    for var in ["AURASTREAM_API_KEY", "FRED_API_KEY", "OANDA_ACCOUNT_ID", "OANDA_TOKEN", "OANDA_ENVIRONMENT"]:
        monkeypatch.delenv(var, raising=False)


def test_missing_key_raises():
    with pytest.raises(AuthenticationError):
        AuraStream()


def test_key_from_env(monkeypatch):
    monkeypatch.setenv("AURASTREAM_API_KEY", "env-key")
    assert AuraStream().session.headers["x-api-key"] == "env-key"


@responses.activate
def test_request_body_and_headers():
    responses.post(URL, json=SAMPLE)
    c = AuraStream("k")
    out = c.timeseries("BTCUSDT", "2025-01-01", "2025-01-31", source="bybit", category="linear")
    assert out == SAMPLE
    req = responses.calls[0].request
    assert req.headers["x-api-key"] == "k"
    body = json.loads(req.body)
    assert body == {
        "tickerlist": ["BTCUSDT"],
        "start": "2025-01-01",
        "end": "2025-01-31",
        "interval": "1d",
        "source": "bybit",
        "credentials": None,
        "category": "linear",
    }


@responses.activate
def test_datetime_formatting():
    from datetime import date, datetime

    responses.post(URL, json={})
    AuraStream("k").timeseries(["X"], date(2025, 1, 1), datetime(2025, 1, 2, 13, 30), "1h", source="binance")
    body = json.loads(responses.calls[0].request.body)
    assert body["start"] == "2025-01-01" and body["end"] == "2025-01-02 13:30"


@responses.activate
def test_credentials_from_env(monkeypatch):
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "acc")
    monkeypatch.setenv("OANDA_TOKEN", "tok")
    responses.post(URL, json={})
    AuraStream("k").timeseries("EUR_USD", "2025-01-01", "2025-02-01", source="oanda")
    body = json.loads(responses.calls[0].request.body)
    assert body["credentials"] == {"id": "acc", "token": "tok", "environment": "practice"}


@responses.activate
def test_batching_merges():
    responses.post(URL, json={"A": {}, "B": {}})
    responses.post(URL, json={"C": {}})
    out = AuraStream("k").timeseries(["A", "B", "C"], "2025-01-01", "2025-01-02", source="binance", batch_size=2)
    assert set(out) == {"A", "B", "C"}
    assert len(responses.calls) == 2


@responses.activate
@pytest.mark.parametrize(
    "status,message,exc",
    [
        (400, "Unknown source", BadRequestError),
        (403, "Forbidden", AuthenticationError),
        (429, "Limit Exceeded", QuotaExceededError),
    ],
)
def test_non_retryable_errors(status, message, exc):
    responses.post(URL, json={"message": message}, status=status)
    with pytest.raises(exc):
        AuraStream("k").timeseries("X", "2025-01-01", "2025-01-02", source="binance")
    assert len(responses.calls) == 1


@responses.activate
def test_retries_then_succeeds():
    responses.post(URL, json={"message": "Too Many Requests"}, status=429)
    responses.post(URL, json={"message": "Bad Gateway"}, status=502)
    responses.post(URL, json=SAMPLE)
    out = AuraStream("k").timeseries("BTCUSDT", "2025-01-01", "2025-01-02", source="bybit")
    assert out == SAMPLE and len(responses.calls) == 3


@responses.activate
def test_gateway_timeout_not_retried():
    responses.post(URL, json={"message": "Endpoint request timed out"}, status=504)
    with pytest.raises(ServerError, match="Split it"):
        AuraStream("k").timeseries("X", "2025-01-01", "2025-01-02", source="binance")
    assert len(responses.calls) == 1


@responses.activate
def test_error_body_200_is_bad_request():
    responses.post(URL, json={"error": "oanda needs credentials"})
    with pytest.raises(BadRequestError, match="needs credentials"):
        AuraStream("k").timeseries("XAU_USD", "2025-01-01", "2025-02-01", source="oanda")
    assert len(responses.calls) == 1


@responses.activate
def test_plain_text_200_is_server_error():
    for _ in range(2):
        responses.post(URL, body="Internal Server Error", status=200, content_type="application/json")
    with pytest.raises(ServerError, match="Internal Server Error"):
        AuraStream("k", max_retries=1).timeseries("X", "2025-01-01", "2025-01-02", source="cftc")
    assert len(responses.calls) == 2


@responses.activate
def test_retries_exhausted():
    for _ in range(3):
        responses.post(URL, json={"message": "Too Many Requests"}, status=429)
    with pytest.raises(RateLimitError):
        AuraStream("k", max_retries=2).timeseries("X", "2025-01-01", "2025-01-02", source="binance")
    assert len(responses.calls) == 3


@responses.activate
def test_server_error_type():
    for _ in range(2):
        responses.post(URL, json={"message": "upstream"}, status=500)
    with pytest.raises(ServerError):
        AuraStream("k", max_retries=1).timeseries("X", "2025-01-01", "2025-01-02", source="binance")


@responses.activate
def test_get_frame_types_and_order():
    responses.post(URL, json=SAMPLE)
    df = AuraStream("k").get_frame("BTCUSDT", "2025-01-01", "2025-01-02", source="binance")
    assert list(df.columns) == ["Open", "High", "Low", "Close"]
    assert df.index.is_monotonic_increasing
    assert str(df.index.tz) == "UTC"
    assert df["Close"].dtype == float
    assert df["Close"].iloc[-1] == 95800.0
