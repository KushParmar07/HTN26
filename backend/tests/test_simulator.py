"""Unit tests for sensor simulator."""

from simulator.config import DEFAULT_SIMULATOR_CONFIG
from simulator.sensor_simulator import SensorSimulator


def test_sensor_simulator_batch_generation():
    sim = SensorSimulator(config=DEFAULT_SIMULATOR_CONFIG)
    batches = sim.generate_step(progress=0.0, add_noise=False, simulate_drops=False)

    assert len(batches) == 3
    pod_ids = {b.pod_id for b in batches}
    assert pod_ids == {"pod_a", "pod_b", "pod_c"}

    for batch in batches:
        bssids = {obs.bssid for obs in batch.observations}
        # Must observe legitimate and rogue AP
        assert "00:11:22:33:44:55" in bssids
        assert "DE:AD:BE:EF:00:01" in bssids


def test_simulator_rogue_movement():
    sim = SensorSimulator(config=DEFAULT_SIMULATOR_CONFIG)

    pos_start = sim.get_ap_position(sim.config.rogue_ap, progress=0.0)
    pos_mid = sim.get_ap_position(sim.config.rogue_ap, progress=0.5)

    assert pos_start == (0.3, 0.3)
    assert pos_mid == (1.5, 0.5)
