"""Momentum strategy with periodic rebalancing."""

from typing import Dict, Set
import pandas as pd

from nautilus_trader.model import Bar, BarType, Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.trading.strategy import Strategy, StrategyConfig

from Strategy.stock_selector import momentum_select


class MomentumRebalanceStrategy(Strategy):
    """Momentum strategy with periodic rebalancing.

    - Selects top N stocks by momentum
    - Rebalances monthly/quarterly
    - Sells stocks no longer in top N
    - Buys new stocks that entered top N
    """

    def __init__(
        self,
        stock_data: Dict[str, pd.DataFrame],
        index_data: Dict[str, pd.DataFrame],
        bar_types: Dict[str, str],
        invest_amount: float = 50000.0,
        top_n: int = 50,
        lookback_days: int = 200,
        rebalance_frequency: str = "monthly",
        **kwargs,
    ):
        super().__init__(config=StrategyConfig())

        self.stock_data = stock_data
        self.all_bar_types = bar_types

        self.invest_amount = invest_amount
        self.top_n = top_n
        self.lookback_days = lookback_days
        self.rebalance_frequency = rebalance_frequency

        # Current state
        self.selected_stocks: Set[str] = set()
        self.positions: Dict[str, int] = {}  # ticker -> shares
        self.cash = invest_amount  # Track cash (start with invest_amount)
        self.last_rebalance_month = None

        # Track daily equity for accurate reporting
        self.equity_history: Dict[str, float] = {}  # date_str -> equity
        self.last_prices: Dict[str, float] = {}  # ticker -> last price

    def on_start(self):
        """Subscribe to ALL stocks (we need to trade any of them)."""
        for ticker, bar_type_str in self.all_bar_types.items():
            if ticker in self.stock_data:  # Only stocks, not indices
                bar_type = BarType.from_str(bar_type_str)
                self.subscribe_bars(bar_type)

        self.log.info(f"Subscribed to {len(self.stock_data)} stocks")

    def on_bar(self, bar: Bar):
        """Check if rebalance needed, then execute trades."""
        current_date = pd.Timestamp(bar.ts_event, unit='ns')
        ticker = str(bar.bar_type.instrument_id).split('.')[0]
        price = float(bar.close)

        # Update last known price
        self.last_prices[ticker] = price

        # Check if it's time to rebalance
        if self._should_rebalance(current_date):
            self._do_rebalance(current_date)

        # Record daily equity (once per day, use last bar of day)
        date_str = current_date.strftime('%Y-%m-%d')
        self.equity_history[date_str] = self._calculate_equity()

    def _should_rebalance(self, current_date: pd.Timestamp) -> bool:
        """Check if we should rebalance on this date."""
        current_month = current_date.to_period('M')

        # First bar or new month
        if self.last_rebalance_month is None:
            return True

        if self.rebalance_frequency == "monthly":
            return current_month != self.last_rebalance_month
        elif self.rebalance_frequency == "quarterly":
            return (current_month.month - 1) // 3 != (self.last_rebalance_month.month - 1) // 3

        return False

    def _do_rebalance(self, current_date: pd.Timestamp):
        """Execute rebalancing: select new stocks, sell old, buy new."""
        date_str = current_date.strftime('%Y-%m-%d')
        self.log.info(f"=== REBALANCING on {date_str} ===")

        # 1. Select new stocks based on current momentum
        new_selected = set(momentum_select(
            self.stock_data,
            as_of_date=date_str,
            lookback_days=self.lookback_days,
            top_n=self.top_n,
        ))

        # 2. Determine what to sell and buy
        to_sell = self.selected_stocks - new_selected
        to_buy = new_selected - self.selected_stocks

        self.log.info(f"Current: {len(self.selected_stocks)}, New: {len(new_selected)}")
        self.log.info(f"Selling: {len(to_sell)}, Buying: {len(to_buy)}")

        # 3. Sell ALL current positions (to rebalance evenly)
        for ticker in list(self.positions.keys()):
            if self.positions.get(ticker, 0) > 0:
                self._sell(ticker, self.positions[ticker], date_str)

        # 4. Calculate investment amount based on current equity
        # Use invest_amount for first rebalance, current equity thereafter
        if self.last_rebalance_month is None:
            invest = self.invest_amount
        else:
            # Use current cash (after selling all positions)
            invest = self.cash * 0.98  # Keep 2% buffer to avoid negative balance

        # 5. Calculate new position sizes for ALL selected stocks
        target_shares = self._calculate_shares_with_budget(new_selected, date_str, invest)

        # 6. Buy all new positions
        for ticker in new_selected:
            if ticker in target_shares and target_shares[ticker] > 0:
                self._buy(ticker, target_shares[ticker], date_str)

        # Update state
        self.selected_stocks = new_selected
        self.last_rebalance_month = current_date.to_period('M')

    def _calculate_shares_with_budget(self, tickers: Set[str], as_of_date: str, budget: float) -> Dict[str, int]:
        """Calculate target shares for each stock given a budget."""
        if not tickers or budget <= 0:
            return {}

        per_stock = budget / len(tickers)
        shares = {}

        for ticker in tickers:
            if ticker not in self.stock_data:
                continue

            price = self._get_price(ticker, as_of_date)
            if price <= 0:
                continue

            qty = int(per_stock / price)
            if qty > 0:
                shares[ticker] = qty

        return shares

    def _get_price(self, ticker: str, as_of_date: str) -> float:
        """Get price from DataFrame as of given date."""
        if ticker not in self.stock_data:
            return 0.0

        df = self.stock_data[ticker]
        close_col = 'Close' if 'Close' in df.columns else 'close'

        try:
            # Get price on or before as_of_date
            available = df.loc[:as_of_date]
            if available.empty:
                return 0.0
            return float(available[close_col].iloc[-1])
        except Exception:
            return 0.0

    def _buy(self, ticker: str, shares: int, as_of_date: str):
        """Submit buy order."""
        if ticker not in self.all_bar_types:
            return

        bar_type_str = self.all_bar_types[ticker]
        instrument_id = BarType.from_str(bar_type_str).instrument_id

        # Get price from DataFrame for accurate cash tracking
        price = self._get_price(ticker, as_of_date)
        if price <= 0:
            return

        cost = shares * price

        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=OrderSide.BUY,
            quantity=Quantity.from_int(shares),
        )
        self.submit_order(order)
        self.positions[ticker] = self.positions.get(ticker, 0) + shares
        self.cash -= cost  # Reduce cash
        self.log.info(f"BUY {shares} {ticker} @ {price:.2f}")

    def _sell(self, ticker: str, shares: int, as_of_date: str):
        """Submit sell order."""
        if ticker not in self.all_bar_types:
            return

        bar_type_str = self.all_bar_types[ticker]
        instrument_id = BarType.from_str(bar_type_str).instrument_id

        # Get price from DataFrame for accurate cash tracking
        price = self._get_price(ticker, as_of_date)
        if price <= 0:
            return

        proceeds = shares * price

        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=OrderSide.SELL,
            quantity=Quantity.from_int(shares),
        )
        self.submit_order(order)
        self.positions[ticker] = 0
        self.cash += proceeds  # Add cash
        self.log.info(f"SELL {shares} {ticker} @ {price:.2f}")

    def _calculate_equity(self) -> float:
        """Calculate current total equity = cash + position values."""
        position_value = 0.0
        for ticker, shares in self.positions.items():
            if shares > 0 and ticker in self.last_prices:
                position_value += shares * self.last_prices[ticker]
        return self.cash + position_value

    def get_equity_series(self) -> pd.Series:
        """Get equity curve as pandas Series."""
        if not self.equity_history:
            return pd.Series(dtype=float)
        dates = pd.to_datetime(list(self.equity_history.keys()))
        values = list(self.equity_history.values())
        return pd.Series(values, index=dates, name='equity').sort_index()

    def on_stop(self):
        for ticker, bar_type_str in self.all_bar_types.items():
            if ticker in self.stock_data:
                bar_type = BarType.from_str(bar_type_str)
                self.unsubscribe_bars(bar_type)

    def on_dispose(self):
        pass
