"""Unit tests for RSSI filtering (median, EMA, composite)."""

import pytest
from backend.app.state.filter import (
    CompositeRssiFilter,
    ExponentialMovingAverageFilter,
    RollingMedianFilter,
)


def test_rolling_median_filter_spike_rejection():
    filt = RollingMedianFilter(window_size=5)

    # Baseline around -50 dBm
    filt.update(-50.0)
    filt.update(-51.0)
    filt.update(-49.0)

    # A single severe spike (e.g. multipath drop to -85 dBm)
    spike_out = filt.update(-85.0)
    assert spike_out == pytest.approx(-50.5, abs=1.0)

    # Another normal measurement
    normal_out = filt.update(-50.0)
    # Median of [-50, -51, -49, -85, -50] -> sorted: [-85, -51, -50, -50, -49] -> median is -50
    assert normal_out == pytest.approx(-50.0)


def test_ema_filter_smoothing():
    filt = ExponentialMovingAverageFilter(alpha=0.5)

    assert filt.update(-60.0) == -60.0
    # Next sample -50 -> 0.5 * -50 + 0.5 * -60 = -55.0
    assert filt.update(-50.0) == -55.0
    # Next sample -40 -> 0.5 * -40 + 0.5 * -55 = -47.5
    assert filt.update(-40.0) == -47.5


def test_composite_rssi_filter():
    comp = CompositeRssiFilter(median_window=3, ema_alpha=0.4)

    # Feed a series of noisy measurements around -60 dBm
    values = [-60.0, -62.0, -59.0, -80.0, -61.0, -60.0]
    out = None
    for v in values:
        out = comp.update(v)

    assert out is not None
    # Out should stay close to -60 despite the -80 dBm spike
    assert -65.0 < out < -58.0
    assert comp.sample_count == len(values)
