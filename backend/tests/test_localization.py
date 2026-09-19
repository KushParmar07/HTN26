"""Unit tests for 2D multilateration and uncertainty estimation."""

import numpy as np
import pytest
from backend.app.config import SensorNodeConfig
from backend.app.localization.multilateration import (
    MultilaterationSolver2D,
    rssi_to_distance_m,
)


def test_rssi_to_distance_calculation():
    # At d=1m, RSSI should equal reference_rssi (-45 dBm)
    assert rssi_to_distance_m(-45.0, reference_rssi=-45.0, path_loss_exponent=2.7) == pytest.approx(1.0, abs=1e-3)

    # At d=10m, RSSI = -45 - 10*2.7*1 = -72 dBm
    d_10m = rssi_to_distance_m(-72.0, reference_rssi=-45.0, path_loss_exponent=2.7)
    assert d_10m == pytest.approx(10.0, rel=1e-2)


def test_multilateration_noiseless_ground_truth():
    sensors = [
        SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0),
        SensorNodeConfig(pod_id="pod_b", x=4.0, y=0.0),
        SensorNodeConfig(pod_id="pod_c", x=2.0, y=3.5),
    ]
    solver = MultilaterationSolver2D(
        sensor_nodes=sensors,
        reference_rssi=-45.0,
        path_loss_exponent=2.7,
    )

    # Known target position
    target_x, target_y = 1.8, 1.4

    # Calculate exact RSSI without noise
    ref_rssi = -45.0
    n = 2.7
    rssi_map = {}
    for s in sensors:
        dist = np.sqrt((target_x - s.x) ** 2 + (target_y - s.y) ** 2)
        rssi = ref_rssi - 10.0 * n * np.log10(dist)
        rssi_map[s.pod_id] = float(rssi)

    pos, uncertainty = solver.solve(rssi_map)

    assert pos is not None
    assert pos.x == pytest.approx(target_x, abs=0.02)
    assert pos.y == pytest.approx(target_y, abs=0.02)
    assert uncertainty is not None
    assert uncertainty >= solver.min_uncertainty_radius_m


def test_multilateration_noisy_input():
    sensors = [
        SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0),
        SensorNodeConfig(pod_id="pod_b", x=4.0, y=0.0),
        SensorNodeConfig(pod_id="pod_c", x=2.0, y=3.5),
    ]
    solver = MultilaterationSolver2D(
        sensor_nodes=sensors,
        reference_rssi=-45.0,
        path_loss_exponent=2.7,
    )

    target_x, target_y = 2.0, 1.5
    ref_rssi = -45.0
    n = 2.7

    # Add small deterministic noise (+1.5 dBm, -2.0 dBm, +1.0 dBm)
    noise = {"pod_a": 1.5, "pod_b": -2.0, "pod_c": 1.0}
    rssi_map = {}
    for s in sensors:
        dist = np.sqrt((target_x - s.x) ** 2 + (target_y - s.y) ** 2)
        rssi_map[s.pod_id] = float(ref_rssi - 10.0 * n * np.log10(dist) + noise[s.pod_id])

    pos, uncertainty = solver.solve(rssi_map)

    assert pos is not None
    # Solver should still find position within reasonable tolerance (~0.5m)
    assert pos.x == pytest.approx(target_x, abs=0.6)
    assert pos.y == pytest.approx(target_y, abs=0.6)
    assert uncertainty is not None


def test_insufficient_sensor_observations():
    sensors = [
        SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0),
        SensorNodeConfig(pod_id="pod_b", x=4.0, y=0.0),
        SensorNodeConfig(pod_id="pod_c", x=2.0, y=3.5),
    ]
    solver = MultilaterationSolver2D(sensor_nodes=sensors)

    # Only 2 pods available
    pos, uncertainty = solver.solve({"pod_a": -50.0, "pod_b": -55.0})
    assert pos is None
    assert uncertainty is None
