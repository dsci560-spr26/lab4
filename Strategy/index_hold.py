"""Index buy-hold strategy."""

from typing import Dict
import pandas as pd

from nautilus_trader.model import Bar, BarType, Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.trading.strategy import Strategy, StrategyConfig


class IndexHoldStrategy(Strategy):
    """Simple buy-and-hold strategy for an index (e.g., SPY)."""

    def __init__(
        self,
        stock_data: Dict[str, pd.DataFrame],
        index_data: Dict[str, pd.DataFrame],
        bar_types: Dict[str, str],
        ticker: str = "SPY",
        invest_amount: float = 50000.0,
        **kwargs,
    ):
        super().__init__(config=StrategyConfig())

        self.index_data = index_data
        self.all_bar_types = bar_types

        self.ticker = ticker
        self.invest_amount = invest_amount

        self.target_shares = 0
        self.bought = False

    def on_start(self):
        """Subscribe to index data."""
        if self.ticker not in self.all_bar_types:
            self.log.error(f"{self.ticker} not found in bar types")
            return

        bar_type = BarType.from_str(self.all_bar_types[self.ticker])
        self.subscribe_bars(bar_type)

    def on_bar(self, bar: Bar):
        """Buy on first bar."""
        if not self.bought:
            price = float(bar.close)
            self.target_shares = int(self.invest_amount / price)

            if self.target_shares > 0:
                order = self.order_factory.market(
                    instrument_id=bar.bar_type.instrument_id,
                    order_side=OrderSide.BUY,
                    quantity=Quantity.from_int(self.target_shares),
                )
                self.submit_order(order)
                self.log.info(f"Bought {self.target_shares} {self.ticker} @ ${price:.2f}")

            self.bought = True

    def on_stop(self):
        if self.ticker in self.all_bar_types:
            bar_type = BarType.from_str(self.all_bar_types[self.ticker])
            self.unsubscribe_bars(bar_type)

    def on_dispose(self):
        pass
