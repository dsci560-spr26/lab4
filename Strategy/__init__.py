"""Trading strategies module."""

from Strategy.strategy import EMACrossStrategy, EMACrossConfig
from Strategy.stoch import StochCrossStrategy, StochConfig

__all__ = [
    "EMACrossStrategy",
    "EMACrossConfig",
    "StochCrossStrategy",
    "StochConfig",
]