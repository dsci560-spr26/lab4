# DSCI-560 Lab 4: Algorithmic Trading

## Team Members
- Tien-Ching (Jeremy) Hsieh
- HsiangYu Tsai
- Justin Chen

## Project Overview

This project implements a momentum-based algorithmic trading strategy with backtesting capabilities using NautilusTrader.

## Installation

### Prerequisites
- Python 3.11+
- pip or uv

### Install Dependencies

```bash
# Using pip
pip install nautilus_trader yfinance quantstats pandas pyyaml

# Or using uv
uv sync
```

## Project Structure

```
lab4/
├── backtester.py           # Main backtest engine
├── data_loader.py          # Data download utility
├── config_momentum.yaml    # Momentum strategy config
├── config_index.yaml       # SPY benchmark config
├── Strategy/
│   ├── __init__.py
│   ├── momentum_rebalance.py   # Momentum + monthly rebalancing
│   ├── momentum.py             # Momentum buy-and-hold
│   ├── index_hold.py           # SPY benchmark
│   └── stock_selector.py       # Selection algorithms
├── data/
│   ├── stock/              # 503 S&P 500 stock CSVs
│   └── index/              # SPY, QQQ CSVs
└── result/                 # Backtest results
```

## Usage

### 1. Download Data (First Time Only)

```bash
python data_loader.py
```

This downloads 10 years of daily price data for 503 S&P 500 stocks.

### 2. Run Momentum Strategy Backtest

```bash
python backtester.py config_momentum.yaml
```

### 3. Run SPY Benchmark Backtest

```bash
python backtester.py config_index.yaml
```

### 4. View Results

Results are saved in the `result/` directory:
- `equity_curve.csv` - Daily portfolio values
- `summary.yaml` - Performance summary
- `report.html` - QuantStats performance report (open in browser)

## Configuration

Edit the YAML config files to customize:

```yaml
strategy:
  module: Strategy.momentum_rebalance
  class: MomentumRebalanceStrategy
  params:
    invest_amount: 100000    # Amount to invest
    top_n: 50                # Number of stocks to hold
    lookback_days: 200       # Momentum lookback period
    rebalance_frequency: monthly

start_date: "2015-01-01"
end_date: "2025-12-31"
starting_cash: 100000
output_dir: result/MomentumRebalance_10Y
```

## Performance Results (10-Year Backtest: 2015-2025)

| Metric | Momentum Strategy | SPY Benchmark |
|--------|-------------------|---------------|
| Total Return | 703.75% | 302.62% |
| CAGR | 20.93% | 13.54% |
| Sharpe Ratio | 1.02 | 0.80 |
| Max Drawdown | -33.89% | -33.71% |

## Algorithm Description

The momentum strategy:
1. Calculates 200-day returns for all 503 stocks
2. Selects top 50 stocks by momentum
3. Allocates equal weight to each stock
4. Rebalances monthly to capture ongoing momentum
