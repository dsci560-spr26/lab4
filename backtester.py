"""Backtest runner that loads strategy from config file."""

from decimal import Decimal
import importlib
import os

import yaml
import pandas as pd
import quantstats as qs

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.model import BarType, Money, TraderId, Venue
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.wranglers import BarDataWrangler

from data_loader import load_data, load_tickers, download_data, save_data, DATA_DIR

VENUE = Venue("NYSE")
RESULT_DIR = os.path.join(os.path.dirname(__file__), "result")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config(path: str = CONFIG_FILE) -> dict:
    """Load backtest configuration from YAML file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_class(module_name: str, class_name: str):
    """Dynamically import a class from a module."""
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def make_instrument(ticker: str) -> Equity:
    """Create a Nautilus Equity instrument for the given ticker."""
    instrument_id = InstrumentId(Symbol(ticker), VENUE)
    return Equity(
        instrument_id=instrument_id,
        raw_symbol=Symbol(ticker),
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        lot_size=Quantity.from_int(1),
        ts_event=0,
        ts_init=0,
    )


def load_bars(ticker: str, instrument: Equity, data: dict, start_date: str, end_date: str) -> list:
    """Wrangle a ticker's OHLCV DataFrame into Nautilus Bar objects."""
    df = data[ticker].copy()
    df.index.name = "timestamp"

    # Filter by date range
    df = df.loc[start_date:end_date]

    # Ensure column names match what BarDataWrangler expects
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df = df.dropna()

    bar_type = BarType.from_str(f"{instrument.id}-1-DAY-LAST-EXTERNAL")
    wrangler = BarDataWrangler(bar_type=bar_type, instrument=instrument)

    # ts_init_delta: shift to bar close (1 day = 86400 * 1e9 ns)
    bars = wrangler.process(df, ts_init_delta=86_400_000_000_000)
    return bars


def create_strategy(strategy_config: dict, instrument, bar_type, params: dict, trade_size: int):
    """Create strategy instance from config."""
    # Load strategy and config classes dynamically
    strategy_cls = load_class(strategy_config["module"], strategy_config["class"])
    config_cls = load_class(strategy_config["module"], strategy_config["config_class"])

    # Build config with instrument_id, bar_type, trade_size and strategy params
    config = config_cls(
        instrument_id=instrument.id,
        bar_type=bar_type,
        trade_size=Decimal(str(trade_size)),
        **params,
    )

    return strategy_cls(config=config)


def run_backtest(config_path: str = CONFIG_FILE):
    """Run backtest based on config file."""
    # Load config
    config = load_config(config_path)

    strategy_config = config["strategy"]
    strategy_name = strategy_config["name"]
    ticker = config["ticker"]
    start_date = config["start_date"]
    end_date = config["end_date"]
    starting_cash = config.get("starting_cash", 100000)
    trade_size = config.get("trade_size", 100)
    params = config.get("params", {})

    print(f"Running {strategy_name} strategy on {ticker}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Parameters: {params}")

    # Load data
    if not os.listdir(DATA_DIR):
        print("No data found. Downloading...")
        tickers = load_tickers()
        all_data = download_data(tickers, start_date=start_date, end_date=end_date)
        save_data(all_data)
    data = load_data()

    if ticker not in data:
        print(f"Ticker {ticker} not found in data. Available: {list(data.keys())[:10]}...")
        return

    # Create instrument and bars
    instrument = make_instrument(ticker)
    bars = load_bars(ticker, instrument, data, start_date, end_date)
    print(f"Loaded {len(bars)} daily bars for {ticker}")

    # Configure engine
    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId("BACKTESTER-001"),
    ))

    engine.add_venue(
        venue=VENUE,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=USD,
        starting_balances=[Money(starting_cash, USD)],
    )

    engine.add_instrument(instrument)
    engine.add_data(bars)

    # Create and add strategy
    bar_type = BarType.from_str(f"{instrument.id}-1-DAY-LAST-EXTERNAL")
    strategy = create_strategy(strategy_config, instrument, bar_type, params, trade_size)
    engine.add_strategy(strategy)

    # Run backtest
    engine.run()

    # Generate reports
    account_report = engine.trader.generate_account_report(VENUE)
    positions_report = engine.trader.generate_positions_report()
    order_fills_report = engine.trader.generate_order_fills_report()

    print("\n=== Account Report ===")
    print(account_report)
    print("\n=== Positions Report ===")
    print(positions_report)
    print("\n=== Order Fills Report ===")
    print(order_fills_report)

    # Save results to result/{strategy}_{ticker}/
    result_name = f"{strategy_name}_{ticker}"
    result_dir = os.path.join(RESULT_DIR, result_name)
    os.makedirs(result_dir, exist_ok=True)

    account_report.to_csv(os.path.join(result_dir, "account.csv"))
    positions_report.to_csv(os.path.join(result_dir, "positions.csv"))
    order_fills_report.to_csv(os.path.join(result_dir, "order_fills.csv"))

    # Save config used for this run
    with open(os.path.join(result_dir, "config.yaml"), "w") as f:
        yaml.dump(config, f)

    # Generate quantstats report
    equity = account_report["total"].astype(float)
    equity.index = pd.to_datetime(equity.index)
    returns = equity.pct_change().dropna()

    if len(returns) > 1:
        qs.reports.html(
            returns,
            benchmark=ticker,
            output=os.path.join(result_dir, "report.html"),
            title=f"{ticker} {strategy_name.upper()} Strategy"
        )
        print(f"\nResults saved to {result_dir}/")
    else:
        print(f"\nNot enough data to generate quantstats report (returns length: {len(returns)})")
        print(f"CSV reports saved to {result_dir}/")

    engine.dispose()


if __name__ == "__main__":
    run_backtest()
