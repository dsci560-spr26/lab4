"""Universal backtester - handles all data preparation."""

import importlib
import os
from typing import Type, Dict, List

import pandas as pd
import yaml
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
from nautilus_trader.trading.strategy import Strategy

from data_loader import load_stock_data, load_index_data

VENUE = Venue("NYSE")
RESULT_DIR = os.path.join(os.path.dirname(__file__), "result")


# =============================================================================
# Data Preparation (Backtester's responsibility)
# =============================================================================

def make_instrument(ticker: str, venue: Venue = VENUE) -> Equity:
    """Create a Nautilus Equity instrument."""
    instrument_id = InstrumentId(Symbol(ticker), venue)
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


def make_bars(ticker: str, instrument: Equity, df: pd.DataFrame,
              start_date: str, end_date: str) -> list:
    """Convert DataFrame to Nautilus Bar objects."""
    df = df.copy()
    df.index.name = "timestamp"
    df = df.loc[start_date:end_date]
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df = df.dropna()

    if df.empty:
        return []

    # Data quality: filter invalid OHLC rows
    # Valid: low <= open <= high, low <= close <= high
    valid = (
        (df['low'] <= df['open']) &
        (df['low'] <= df['close']) &
        (df['high'] >= df['open']) &
        (df['high'] >= df['close']) &
        (df['low'] <= df['high'])
    )
    df = df[valid]

    if df.empty:
        return []

    bar_type = BarType.from_str(f"{instrument.id}-1-DAY-LAST-EXTERNAL")
    wrangler = BarDataWrangler(bar_type=bar_type, instrument=instrument)
    bars = wrangler.process(df, ts_init_delta=86_400_000_000_000)
    return bars


def prepare_all_data(
    stock_data: Dict[str, pd.DataFrame],
    index_data: Dict[str, pd.DataFrame],
    start_date: str,
    end_date: str
) -> tuple:
    """Prepare all instruments and bars for backtesting.

    Returns:
        (instruments, bars, bar_types_map)
        - instruments: List of all Equity instruments
        - bars: List of all Bar objects
        - bar_types_map: Dict mapping ticker -> bar_type string
    """
    all_data = {**stock_data, **index_data}

    instruments = []
    all_bars = []
    bar_types_map = {}

    for ticker, df in all_data.items():
        instrument = make_instrument(ticker)
        bars = make_bars(ticker, instrument, df, start_date, end_date)

        if bars:
            instruments.append(instrument)
            all_bars.extend(bars)
            bar_types_map[ticker] = f"{instrument.id}-1-DAY-LAST-EXTERNAL"

    return instruments, all_bars, bar_types_map


# =============================================================================
# Equity Calculation
# =============================================================================

def get_equity(engine, venue, data_source, positions_report) -> float:
    """Calculate total equity = cash + position values."""
    account_report = engine.trader.generate_account_report(venue)
    cash = float(account_report['total'].iloc[-1])

    position_value = 0.0
    if not positions_report.empty:
        for _, pos in positions_report.iterrows():
            ticker = str(pos['instrument_id']).split('.')[0]
            qty = float(pos['quantity'])

            if ticker in data_source:
                df = data_source[ticker]
                close_col = 'Close' if 'Close' in df.columns else 'close'
                last_price = float(df[close_col].iloc[-1])
                position_value += qty * last_price

    return cash + position_value


def calculate_equity_curve(
    starting_cash: float,
    positions_report: pd.DataFrame,
    data_source: dict,
    start_date: str,
    end_date: str
) -> pd.Series:
    """Calculate daily equity curve from positions and price data."""
    if positions_report.empty:
        return pd.Series(dtype=float)

    positions = {}
    total_cost = 0.0

    for _, pos in positions_report.iterrows():
        ticker = str(pos['instrument_id']).split('.')[0]
        qty = float(pos['quantity'])
        avg_px = float(pos['avg_px_open'])
        positions[ticker] = qty
        total_cost += qty * avg_px

    cash = starting_cash - total_cost

    first_ticker = list(positions.keys())[0]
    if first_ticker not in data_source:
        return pd.Series(dtype=float)

    df = data_source[first_ticker].loc[start_date:end_date]
    dates = df.index

    equity = []
    for date in dates:
        position_value = 0.0
        for ticker, qty in positions.items():
            if ticker in data_source:
                ticker_df = data_source[ticker]
                close_col = 'Close' if 'Close' in ticker_df.columns else 'close'
                if date in ticker_df.index:
                    price = float(ticker_df.loc[date, close_col])
                    position_value += qty * price
        equity.append(cash + position_value)

    return pd.Series(equity, index=dates, name='equity')


# =============================================================================
# Result Saving
# =============================================================================

def save_results(result, equity_curve, config, output_dir):
    """Save backtest results to files."""
    os.makedirs(output_dir, exist_ok=True)

    equity_curve.to_csv(os.path.join(output_dir, "equity_curve.csv"))

    with open(os.path.join(output_dir, "config.yaml"), "w") as f:
        yaml.dump(config, f)

    summary = {
        'starting_cash': result['starting_cash'],
        'final_equity': result['total_equity'],
        'total_return_pct': result['returns'],
    }
    with open(os.path.join(output_dir, "summary.yaml"), "w") as f:
        yaml.dump(summary, f)

    if len(equity_curve) > 1:
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 1:
            try:
                qs.reports.html(
                    returns,
                    benchmark="SPY",
                    output=os.path.join(output_dir, "report.html"),
                    title=config.get('name', 'Strategy Report')
                )
                print(f"QuantStats report saved to {output_dir}/report.html")
            except Exception as e:
                print(f"Could not generate QuantStats report: {e}")

    print(f"Results saved to {output_dir}/")


# =============================================================================
# Main Backtest Runner
# =============================================================================

def run_backtest(
    strategy_class: Type[Strategy],
    start_date: str,
    end_date: str,
    starting_cash: float = 100000,
    trader_id: str = "BACKTEST-001",
    save_to: str = None,
    **strategy_params
) -> dict:
    """Run backtest for a strategy.

    The backtester:
    1. Loads ALL stock and index data
    2. Prepares ALL instruments and bars
    3. Passes everything to the strategy
    4. Strategy decides what to trade

    Args:
        strategy_class: Strategy class (must accept stock_data, bar_types in config)
        start_date: Backtest start date
        end_date: Backtest end date
        starting_cash: Initial cash
        trader_id: Trader ID for the engine
        save_to: Directory to save results (optional)
        **strategy_params: Parameters passed to strategy config

    Returns:
        Dict with backtest results
    """
    # 1. Load ALL data
    print("Loading data...")
    stock_data = load_stock_data()
    index_data = load_index_data()
    all_data = {**stock_data, **index_data}

    # 2. Prepare ALL instruments and bars
    print("Preparing instruments and bars...")
    instruments, all_bars, bar_types_map = prepare_all_data(
        stock_data, index_data, start_date, end_date
    )
    print(f"Prepared {len(instruments)} instruments, {len(all_bars)} bars")

    # 3. Configure engine
    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId(trader_id),
    ))

    engine.add_venue(
        venue=VENUE,
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=USD,
        starting_balances=[Money(starting_cash, USD)],
    )

    for instrument in instruments:
        engine.add_instrument(instrument)
    engine.add_data(all_bars)

    # 4. Create strategy - pass all data directly
    strategy = strategy_class(
        stock_data=stock_data,
        index_data=index_data,
        bar_types=bar_types_map,
        start_date=start_date,
        starting_cash=starting_cash,
        **strategy_params
    )
    engine.add_strategy(strategy)

    # 5. Run
    print("Running backtest...")
    engine.run()

    # 6. Get results
    positions_report = engine.trader.generate_positions_report()
    total_equity = get_equity(engine, VENUE, all_data, positions_report)
    returns_pct = (total_equity / starting_cash - 1) * 100

    print(f"Starting cash: ${starting_cash:,.2f}")
    print(f"Final equity: ${total_equity:,.2f}")
    print(f"Return: {returns_pct:.2f}%")

    # Use strategy's equity curve if available (for rebalancing strategies)
    if hasattr(strategy, 'get_equity_series'):
        equity_curve = strategy.get_equity_series()
    else:
        # Fallback for buy-hold strategies
        equity_curve = calculate_equity_curve(
            starting_cash, positions_report, all_data, start_date, end_date
        )

    engine.dispose()

    result = {
        'total_equity': total_equity,
        'starting_cash': starting_cash,
        'returns': returns_pct,
        'equity_curve': equity_curve,
    }

    if save_to:
        config = {
            'name': strategy_class.__name__,
            'start_date': start_date,
            'end_date': end_date,
            'starting_cash': starting_cash,
            'params': strategy_params,
        }
        save_results(result, equity_curve, config, save_to)

    return result


def run_from_config(config_path: str) -> dict:
    """Run backtest from a YAML config file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    strategy_config = config['strategy']
    module = importlib.import_module(strategy_config['module'])
    strategy_class = getattr(module, strategy_config['class'])

    params = strategy_config.get('params', {})
    output_dir = config.get('output_dir', os.path.join(RESULT_DIR, strategy_config['class']))

    return run_backtest(
        strategy_class=strategy_class,
        start_date=config['start_date'],
        end_date=config['end_date'],
        starting_cash=config.get('starting_cash', 100000),
        trader_id=config.get('trader_id', 'BACKTEST-001'),
        save_to=output_dir,
        **params
    )


# =============================================================================
# Demo
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = run_from_config(sys.argv[1])
    else:
        from Strategy.momentum import MomentumStrategy

        result = run_backtest(
            MomentumStrategy,
            start_date="2023-01-01",
            end_date="2024-12-31",
            starting_cash=100000,
            save_to=os.path.join(RESULT_DIR, "MomentumStrategy"),
            invest_amount=50000,
            top_n=50,
        )