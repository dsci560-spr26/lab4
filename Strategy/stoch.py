from decimal import Decimal

from nautilus_trader.core.message import Event
from nautilus_trader.indicators import ExponentialMovingAverage, Stochastics
from nautilus_trader.model import Bar, BarType, InstrumentId, Position, Quantity
from nautilus_trader.model.enums import OrderSide, PositionSide
from nautilus_trader.model.events import PositionClosed, PositionOpened
from nautilus_trader.trading.strategy import Strategy, StrategyConfig


class StochConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    k_period: int = 10
    d_period: int = 20
    trade_size: Decimal = Decimal("100")


class StochCrossStrategy(Strategy):
    """A simple stoch crossover strategy for a single stock.

    Goes long when k crosses above d
    closes position when k crosses below d.
    """

    def __init__(self, config: StochConfig):
        super().__init__(config=config)
        self.instrument_id = config.instrument_id
        self.bar_type = config.bar_type
        self.trade_size = Quantity.from_str(str(config.trade_size))
        self.stoch = Stochastics(config.k_period, config.d_period)


    def on_start(self):
        self.register_indicator_for_bars(self.bar_type, self.stoch)
        self.subscribe_bars(self.bar_type)

    def on_bar(self, bar: Bar):
        if not self.stoch.initialized:
            return

        # Detect crossover
        k = self.stoch.value_k
        d = self.stoch.value_d


        if k > d and not self._is_long():
            self._close_position()
            self._buy()
        elif k < d and self._is_long():
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
