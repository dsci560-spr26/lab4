# NautilusTrader Backtesting Project

A backtesting framework for trading strategies using NautilusTrader.

## Setup

### Using uv (Recommended)

```bash
# Install dependencies
uv pip install -e .

# Or sync from pyproject.toml
uv sync
```

### Using pip

```bash
pip install -e .
```

## Quick Start

```bash
# 1. Download stock data (S&P 500, 2022-2025)
uv run python data_loader.py

# 2. Run backtest
uv run python backtester.py
```

## Project Structure

```
lab4/
├── backtester.py           # Backtest engine runner
├── config.yaml             # Backtest configuration
├── data_loader.py          # Downloads OHLCV data from Yahoo Finance
├── ticker.yaml             # Stock ticker list
├── Strategy/               # Trading strategies
│   ├── __init__.py
│   ├── strategy.py         # EMA crossover strategy
│   └── stoch.py            # Stochastics crossover strategy
├── data/                   # Stock data (CSV files)
└── result/                 # Backtest output reports
```

## Configuration

Edit `config.yaml` to customize your backtest:

```yaml
# Strategy definition
strategy:
  name: stoch                        # strategy identifier
  module: Strategy.stoch             # module path (Strategy/stoch.py)
  class: StochCrossStrategy          # strategy class name
  config_class: StochConfig          # config class name

# Stock ticker
ticker: AAPL

# Date range
start_date: "2022-01-01"
end_date: "2025-01-01"

# Account settings
starting_cash: 100000
trade_size: 100

# Strategy parameters (passed to config_class)
params:
  k_period: 14
  d_period: 3
```

### Switching Strategies

To use EMA crossover strategy:

```yaml
strategy:
  name: ema
  module: Strategy.strategy
  class: EMACrossStrategy
  config_class: EMACrossConfig

params:
  fast_ema_period: 10
  slow_ema_period: 20
```

To use Stochastics strategy:

```yaml
strategy:
  name: stoch
  module: Strategy.stoch
  class: StochCrossStrategy
  config_class: StochConfig

params:
  k_period: 14
  d_period: 3
```

## Usage

```bash
# Run backtest with config.yaml settings
uv run python backtester.py
```

Results saved to `result/{strategy}_{ticker}/`:
- `account.csv` - Account balance history
- `positions.csv` - Position report
- `order_fills.csv` - Order execution report
- `report.html` - QuantStats analysis
- `config.yaml` - Config used for this run

## Log

- 20260202: downloaded data from 2023-2025
