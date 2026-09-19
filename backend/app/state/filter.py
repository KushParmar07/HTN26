"""RSSI temporal filtering implementations (Rolling Median & EMA)."""

from collections import deque
from typing import Optional
import numpy as np


class RollingMedianFilter:
    """Rolling median filter to reject impulse noise and multipath spikes."""

    def __init__(self, window_size: int = 5):
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self.window_size = window_size
        self._history: deque[float] = deque(maxlen=window_size)

    def update(self, value: float) -> float:
        # Protect against non-finite values (NaN / Inf)
        if not np.isfinite(value):
            return self.current_value if self.current_value is not None else -65.0
        self._history.append(float(value))
        return float(np.median(self._history))

    @property
    def current_value(self) -> Optional[float]:
        if not self._history:
            return None
        return float(np.median(self._history))

    @property
    def sample_count(self) -> int:
        return len(self._history)

    def reset(self) -> None:
        self._history.clear()


class ExponentialMovingAverageFilter:
    """Exponential Moving Average (EMA) filter to smoothly track continuous RSSI changes."""

    def __init__(self, alpha: float = 0.3):
        if not (0.0 < alpha <= 1.0):
            raise ValueError("alpha must be in range (0.0, 1.0]")
        self.alpha = alpha
        self._value: Optional[float] = None
        self._sample_count: int = 0

    def update(self, value: float) -> float:
        # Protect against non-finite values (NaN / Inf)
        if not np.isfinite(value):
            return self._value if self._value is not None else -65.0
        self._sample_count += 1
        if self._value is None:
            self._value = float(value)
        else:
            self._value = float(self.alpha * value + (1.0 - self.alpha) * self._value)
        return self._value

    @property
    def current_value(self) -> Optional[float]:
        return self._value

    @property
    def sample_count(self) -> int:
        return self._sample_count

    def reset(self) -> None:
        self._value = None
        self._sample_count = 0


class CompositeRssiFilter:
    """Chains Rolling Median (spike rejection) into EMA (continuous smoothing)."""

    def __init__(self, median_window: int = 5, ema_alpha: float = 0.3):
        self.median_filter = RollingMedianFilter(window_size=median_window)
        self.ema_filter = ExponentialMovingAverageFilter(alpha=ema_alpha)

    def update(self, rssi: float) -> float:
        median_val = self.median_filter.update(rssi)
        return self.ema_filter.update(median_val)

    @property
    def current_value(self) -> Optional[float]:
        return self.ema_filter.current_value

    @property
    def sample_count(self) -> int:
        return self.ema_filter.sample_count

    def reset(self) -> None:
        self.median_filter.reset()
        self.ema_filter.reset()
