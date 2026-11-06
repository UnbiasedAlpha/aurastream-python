# aurastream

**One API for crypto, FX, rates, macro, positioning and alternative data, from 47 sources, in one response format.**

The official Python client for [AuraStream](https://unbiased-alpha.com/aurastream) by Unbiased Alpha. Pull Binance candles and funding, ECB and BIS statistics, FRED vintages, CFTC positioning and SEC filings with the same call, and get a clean pandas DataFrame back.

[![PyPI](https://img.shields.io/pypi/v/aurastream.svg)](https://pypi.org/project/aurastream/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

```bash
pip install "aurastream[pandas]"
```

The package installs as `aurastream` and imports as `aurastream_client`.

**Free plan: 500 calls a month, no card.** [Get a key →](https://aurastream.unbiased-alpha.com)

## Quickstart

```python
from aurastream_client import AuraStream

client = AuraStream()   # reads AURASTREAM_API_KEY from the environment

# Bitcoin daily candles from Binance, with no provider account needed
btc = client.get_frame("BTCUSDT", "2025-01-01", "2025-06-30", source="binance")

# Several coins' closes in one wide DataFrame
prices = client.get_panel(["BTCUSDT", "ETHUSDT", "SOLUSDT"], "2024-01-01", "2025-01-01", source="binance")
prices.pct_change().corr()

# The ECB's daily EUR/USD reference rate
eurusd = client.get_frame("ECB,EXR,1.0/D.USD.EUR.SP00.A", "2024-01-01", "2025-01-01", source="sdmx", db="ECB")
```

## Why AuraStream

- **One endpoint, one schema.** Stop writing a new adapter for every vendor. Every source returns `{ticker: {timestamp: {field: value}}}`.
- **47 sources.** Binance, Bybit, Kraken, Deribit, Hyperliquid, dYdX, FRED, US Treasury, ECB/BIS/OECD (SDMX), World Bank, CFTC, SEC EDGAR, USDA WASDE, GDELT, TSA, and more, plus brokers and vendors you already have an account with (Oanda, Alpaca, Polygon...). [Full list](https://aurastream.unbiased-alpha.com/docs/data-sources/overview/).
- **Point-in-time where it matters.** FRED series come with every revision, and CFTC data is stamped by release date, so your backtests don't peek.
- **Bring your own keys.** For sources that need an account (Oanda, Alpaca, Polygon, FRED…), your credentials pass through per request and are never stored.

## Examples

| Notebook | What it shows | Sources (no provider account needed) |
|---|---|---|
| [01 – Crypto funding & carry](examples/01_crypto_funding_carry.ipynb) | Perp funding rates vs. price, annualized carry | `binance` |
| [02 – Rates, FX and crypto regime dashboard](examples/02_cross_asset_dashboard.ipynb) | Bitcoin, ether, gold token, EUR/USD, USD/JPY, euro yields, Fed rate: drawdowns, the curve, rolling correlations | `binance`, `sdmx` |
| [03 – Speculative positioning (COT)](examples/03_cftc_positioning.ipynb) | CFTC positioning vs. price for gold and the euro | `cftc`, `binance`, `sdmx` |

Every notebook opens in Google Colab and runs on the free plan.

## Usage

### Raw JSON

```python
data = client.timeseries(["BTCUSDT", "ETHUSDT"], "2025-01-01", "2025-01-31", "1h", source="bybit")
```

### Source-specific parameters

Pass any extra field as a keyword argument, and it goes straight into the request body:

```python
# Binance USD-M perpetual funding rates
funding = client.get_frame("BTCUSDT", "2025-01-01", "2025-06-30", "8h",
                           source="binance", instrument="futures", bars="funding")

# CFTC Traders in Financial Futures report for euro futures
cot = client.get_frame("6E", "2020-01-01", "2025-01-01", "1w", source="cftc", report="tff")
```

### Provider credentials

Pass `credentials=` explicitly, or set environment variables (the same names [aurastream-mcp](https://github.com/UnbiasedAlpha/aurastream-mcp) uses):

| Source | Variables |
|---|---|
| `fred` | `FRED_API_KEY` |
| `oanda` | `OANDA_ACCOUNT_ID`, `OANDA_TOKEN`, `OANDA_ENVIRONMENT` (default `practice`) |
| `signals`, `nemeton` | `NEMETON_API_KEY` |

```python
cpi = client.get_frame("CPIAUCSL", "2020-01-01", "2025-01-01", "1m",
                       source="fred", credentials={"key": "YOUR_FRED_KEY"})
```

### Large requests

The API stops a request after about 30 seconds. Split long histories into several date ranges, and long ticker lists with `batch_size`:

```python
coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
data = client.timeseries(coins, "2025-01-01", "2025-06-30", "1h", source="binance", batch_size=4)
```

Each batch counts as one call against your allowance.

### Errors and retries

The client retries rate limiting (`429 Too Many Requests`) and server errors with exponential backoff, three times by default. It never retries bad requests, auth errors, an exhausted monthly allowance or a timeout (`504`: split the request instead):

```python
from aurastream_client import QuotaExceededError, BadRequestError

try:
    client.timeseries("XAU_USD", "2025-01-01", "2025-02-01", source="oanda")
except BadRequestError as e:
    print(e.message)          # e.g. missing credentials
except QuotaExceededError:
    print("Monthly allowance used: upgrade at aurastream.unbiased-alpha.com")
```

## Also available

- **MCP server** for Claude and ChatGPT: `pip install aurastream-mcp` ([repo](https://github.com/UnbiasedAlpha/aurastream-mcp))
- **OpenBB extension**: `pip install openbb-aurastream` ([repo](https://github.com/UnbiasedAlpha/openbb-aurastream))
- **REST docs**: [aurastream.unbiased-alpha.com/docs](https://aurastream.unbiased-alpha.com/docs/)

## Plans

| Plan | Calls / month | Price |
|---|---|---|
| Free | 500 | $0, no card |
| API Integration | 5,000 | $30 / month |
| Nemeton (order-book data and signals) | 50,000 | $250 / month |

[Compare plans →](https://aurastream.unbiased-alpha.com/prices)

## License

MIT © Unbiased Alpha GmbH
