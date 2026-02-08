"""Momentum strategy - selects and trades stocks internally (buy and hold)."""

from typing import Dict
import pandas as pd

from nautilus_trader.model import Bar, BarType, InstrumentId, Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.trading.strategy import Strategy, StrategyConfig

from Strategy.stock_selector import momentum_select


class MomentumStrategy(Strategy):
    """Momentum-based stock selection and trading (buy and hold).

    The backtester passes ALL available data.
    The strategy decides which stocks to trade.
    """

    def __init__(
        self,
        stock_data: Dict[str, pd.DataFrame],
        index_data: Dict[str, pd.DataFrame],
        bar_types: Dict[str, str],
        invest_amount: float = 50000.0,
        top_n: int = 50,
        lookback_days: int = 200,
        **kwargs,
    ):
        super().__init__(config=StrategyConfig())

        # Data from backtester
        self.stock_data = stock_data
        self.all_bar_types = bar_types

        # Strategy parameters
        self.invest_amount = invest_amount
        self.top_n = top_n
        self.lookback_days = lookback_days

        # Will be set on first bar
        self.selected_stocks = []
        self.target_shares = {}
        self.bought = set()
        self.initialized = False

    def on_start(self):
        """Subscribe to all stocks."""
        for ticker in self.stock_data:
            if ticker in self.all_bar_types:
                bar_type = BarType.from_str(self.all_bar_types[ticker])
                self.subscribe_bars(bar_type)

    def _initialize(self, as_of_date: str):
        """Select stocks and calculate shares on first bar."""
        # 1. Select stocks using momentum
        self.selected_stocks = momentum_select(
            self.stock_data,
            as_of_date=as_of_date,
            lookback_days=self.lookback_days,
            top_n=self.top_n,
        )
        self.log.info(f"Selected {len(self.selected_stocks)} stocks")

        # 2. Calculate target shares
        if not self.selected_stocks:
            return

        per_stock = self.invest_amount / len(self.selected_stocks)

        for ticker in self.selected_stocks:
            if ticker not in self.stock_data:
                continue

            df = self.stock_data[ticker]
            close_col = 'Close' if 'Close' in df.columns else 'close'

            try:
                price = float(df.loc[:as_of_date][close_col].iloc[-1])
                shares = int(per_stock / price)
                if shares > 0:
                    self.target_shares[ticker] = shares
            except Exception:
                pass

        self.log.info(f"Will trade {len(self.target_shares)} stocks")
        self.initialized = True

    def on_bar(self, bar: Bar):
        """Handle incoming bar data - execute trades."""
        # Initialize on first bar
        if not self.initialized:
            current_date = pd.Timestamp(bar.ts_event, unit='ns')
            self._initialize(current_date.strftime('%Y-%m-%d'))

        ticker = str(bar.bar_type.instrument_id).split('.')[0]

        # Only trade selected stocks that we haven't bought yet
        if ticker in self.target_shares and ticker not in self.bought:
            self._buy(instrument_id, self.target_shares[ticker])
            self.bought.add(ticker)

    def _buy(self, instrument_id: InstrumentId, shares: int):
        """Submit buy order."""
        quantity = Quantity.from_int(shares)
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=OrderSide.BUY,
            quantity=quantity,
        )
        self.submit_order(order)
        self.log.info(f"Bought {shares} of {instrument_id}")

    def on_stop(self):
        """Cleanup on strategy stop."""
        for ticker in self.selected_stocks:
            if ticker in self.all_bar_types:
                bar_type = BarType.from_str(self.all_bar_types[ticker])
                self.unsubscribe_bars(bar_type)

    def on_dispose(self):
        pass
