import pytest

from aurastream_client.frames import to_frame, to_panel


def test_lowercase_normalized():
    data = {"AAPL": {"2025-01-01 05:00:00": {"open": 1, "close": 2, "volume": 10}}}
    assert list(to_frame(data).columns) == ["Open", "Close", "Volume"]


def test_text_columns_preserved():
    data = {"statement": {"2025-01-29 19:00:00": {"score": "0.3", "title": "FOMC statement"}}}
    df = to_frame(data)
    assert df["score"].iloc[0] == 0.3
    assert df["title"].iloc[0] == "FOMC statement"


def test_empty_ticker():
    df = to_frame({"INVALID_TICKER": {}})
    assert df.empty


def test_ambiguous_ticker():
    with pytest.raises(ValueError):
        to_frame({"A": {}, "B": {}})


def test_panel():
    data = {
        "SPY": {"2025-01-02 05:00:00": {"Close": 1.0}, "2025-01-03 05:00:00": {"Close": 2.0}},
        "QQQ": {"2025-01-02 05:00:00": {"close": 3.0}},
        "BAD": {},
    }
    p = to_panel(data)
    assert list(p.columns) == ["SPY", "QQQ"]
    assert p.shape == (2, 2)
