from decimal import Decimal

from nautilus_trader.core.message import Event
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model import Bar, BarType, InstrumentId, Position, Quantity
from nautilus_trader.model.enums import OrderSide, PositionSide
from nautilus_trader.model.events import PositionClosed, PositionOpened
from nautilus_trader.trading.strategy import Strategy, StrategyConfig


class EMACrossConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    trade_size: Decimal = Decimal("10000")


class EMACrossStrategy(Strategy):
    """A simple EMA crossover strategy for a single stock.

    Goes long when fast EMA crosses above slow EMA,
    closes position when fast EMA crosses below slow EMA.
    """

    def __init__(self, config: EMACrossConfig):
        super().__init__(config=config)
        self.instrument_id = config.instrument_id
        self.bar_type = config.bar_type
        self.trade_size = Quantity.from_str(str(config.trade_size))
        self.fast_ema = ExponentialMovingAverage(config.fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_ema_period)

    def on_start(self):
        self.register_indicator_for_bars(self.bar_type, self.fast_ema)
        self.register_indicator_for_bars(self.bar_type, self.slow_ema)
        self.subscribe_bars(self.bar_type)

    def on_bar(self, bar: Bar):
        if not self.fast_ema.initialized or not self.slow_ema.initialized:
            return

        # Detect crossover
        fast = self.fast_ema.value
        slow = self.slow_ema.value

        if fast > slow and not self._is_long():
            self._close_position()
            self._buy()
        elif fast < slow and self._is_long():
            self._close_position()

    def _is_long(self) -> bool:
        if self.portfolio.is_net_long(self.instrument_id):
            return True
        return False

    def _buy(self):
        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=OrderSide.BUY,
            quantity=self.trade_size,
        )
        self.submit_order(order)

    def _close_position(self):
        if self.portfolio.is_net_long(self.instrument_id):
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.trade_size,
            )
            self.submit_order(order)

    def on_stop(self):
        self.close_all_positions(self.instrument_id)
        self.unsubscribe_bars(self.bar_type)

    def on_dispose(self):
        pass
