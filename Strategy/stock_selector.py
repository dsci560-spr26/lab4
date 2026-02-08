"""Stock selection module for index enhancement strategies."""

import pandas as pd
from typing import List, Dict


def momentum_select(stock_data: Dict[str, pd.DataFrame],
                    as_of_date: str,
                    lookback_days: int = 200,
                    top_n: int = 50) -> List[str]:
    """Select top N stocks by momentum (past returns).

    Args:
        stock_data: dict of {ticker: DataFrame}
        as_of_date: selection date (use data before this date)
        lookback_days: lookback period in trading days (default 200)
        top_n: number of stocks to select

    Returns:
        List of selected ticker symbols
    """
    momentum = {}

    for ticker, df in stock_data.items():
        try:
            # Get data up to as_of_date
            df = df.loc[:as_of_date]
            if len(df) < lookback_days:
                continue

            close_col = 'Close' if 'Close' in df.columns else 'close'

            # Calculate momentum (return over lookback period)
            current_price = float(df[close_col].iloc[-1])
            past_price = float(df[close_col].iloc[-lookback_days])
            returns = (current_price - past_price) / past_price

            momentum[ticker] = returns
        except Exception:
            pass

    # Sort by momentum descending and select top N
    sorted_stocks = sorted(momentum.items(), key=lambda x: x[1], reverse=True)
    selected = [ticker for ticker, _ in sorted_stocks[:top_n]]

    return selected


def equal_weight(selected_stocks: List[str],
                 total_amount: float) -> Dict[str, float]:
    """Calculate equal weight allocation.

    Args:
        selected_stocks: list of ticker symbols
        total_amount: total amount to invest

    Returns:
        dict of {ticker: amount}
    """
    if not selected_stocks:
        return {}

    per_stock = total_amount / len(selected_stocks)
    return {ticker: per_stock for ticker in selected_stocks}


def calculate_shares(allocations: Dict[str, float],
                     stock_data: Dict[str, pd.DataFrame],
                     as_of_date: str) -> Dict[str, float]:
    """Convert dollar allocations to share counts.

    Args:
        allocations: dict of {ticker: dollar_amount}
        stock_data: dict of {ticker: DataFrame}
        as_of_date: date to get prices from

    Returns:
        dict of {ticker: shares}
    """
    shares = {}

    for ticker, amount in allocations.items():
        if ticker not in stock_data:
            continue

        df = stock_data[ticker]
        close_col = 'Close' if 'Close' in df.columns else 'close'

        try:
            price = float(df.loc[:as_of_date][close_col].iloc[-1])
            shares[ticker] = amount / price
        except Exception:
            pass

    return shares
