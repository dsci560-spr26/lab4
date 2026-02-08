"""EMA Crossover Strategy - Single stock trading based on EMA signals."""

from typing import Dict
import pandas as pd

from nautilus_trader.model import Bar, BarType, Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.trading.strategy import Strategy, StrategyConfig
from nautilus_trader.indicators import ExponentialMovingAverage


class EMACrossStrategy(Strategy):
    """EMA Crossover strategy for a single stock.

    Goes long when fast EMA crosses above slow EMA (Golden Cross),
    closes position when fast EMA crosses below slow EMA (Death Cross).
    """

    def __init__(
        self,
        stock_data: Dict[str, pd.DataFrame],
        index_data: Dict[str, pd.DataFrame],
        bar_types: Dict[str, str],
        ticker: str = "AAPL",
        invest_amount: float = 50000.0,
        fast_ema_period: int = 10,
        slow_ema_period: int = 20,
        **kwargs,
    ):
        super().__init__(config=StrategyConfig())

        self.stock_data = stock_data
        self.all_bar_types = bar_types
        self.ticker = ticker
        self.invest_amount = invest_amount

        # EMA indicators
        self.fast_ema = ExponentialMovingAverage(fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(slow_ema_period)

        # State
        self.target_shares = 0
        self.is_long = False

    def on_start(self):
        """Subscribe to stock data and register indicators."""
        if self.ticker not in self.all_bar_types:
            self.log.error(f"{self.ticker} not found in bar types")
            return

        bar_type = BarType.from_str(self.all_bar_types[self.ticker])
        self.register_indicator_for_bars(bar_type, self.fast_ema)
        self.register_indicator_for_bars(bar_type, self.slow_ema)
        self.subscribe_bars(bar_type)
        self.log.info(f"Subscribed to {self.ticker} with EMA({self.fast_ema.period}, {self.slow_ema.period})")

    def on_bar(self, bar: Bar):
        """Check for EMA crossover signals."""
        # Wait for indicators to initialize
        if not self.fast_ema.initialized or not self.slow_ema.initialized:
            return

        fast = self.fast_ema.value
        slow = self.slow_ema.value
        price = float(bar.close)

        # Golden Cross: Fast EMA crosses above Slow EMA -> Buy
        if fast > slow and not self.is_long:
            self.target_shares = int(self.invest_amount / price)
            if self.target_shares > 0:
                order = self.order_factory.market(
                    instrument_id=bar.bar_type.instrument_id,
                    order_side=OrderSide.BUY,
                    quantity=Quantity.from_int(self.target_shares),
                )
                self.submit_order(order)
                self.is_long = True
                self.log.info(f"BUY {self.target_shares} {self.ticker} @ {price:.2f} (Golden Cross)")

        # Death Cross: Fast EMA crosses below Slow EMA -> Sell
        elif fast < slow and self.is_long:
            order = self.order_factory.market(
                instrument_id=bar.bar_type.instrument_id,
                order_side=OrderSide.SELL,
                quantity=Quantity.from_int(self.target_shares),
            )
            self.submit_order(order)
            self.is_long = False
            self.log.info(f"SELL {self.target_shares} {self.ticker} @ {price:.2f} (Death Cross)")

    def on_stop(self):
        if self.ticker in self.all_bar_types:
            bar_type = BarType.from_str(self.all_bar_types[self.ticker])
            self.unsubscribe_bars(bar_type)

    def on_dispose(self):
        pass