"""Test verifying demo runner functions against test client."""

from backend.app.main import app, pipeline
from simulator.config import ScenarioType, SimulatorConfig
from simulator.sensor_simulator import SensorSimulator


def test_demo_phases_sequence():
    """Verify the 3-phase demo sequence programmatically."""
    pipeline.reset()
    sim = SensorSimulator(config=SimulatorConfig(random_seed=42, rssi_noise_std=1.0))

    # Phase 1: Normal
    for step in range(3):
        batches = sim.generate_step(scenario=ScenarioType.NORMAL, step_index=step)
        for b in batches:
            pipeline.ingest(b)
    state1 = pipeline.generate_threat_state()
    assert len(state1.threats) == 0

    # Phase 2: Rogue AP appears
    batches_rogue = sim.generate_step(scenario=ScenarioType.SUSPICIOUS, progress=0.0, step_index=0)
    for b in batches_rogue:
        pipeline.ingest(b)
    state2 = pipeline.generate_threat_state()
    assert len(state2.threats) == 1
    assert state2.threats[0].bssid == "DE:AD:BE:EF:00:01"
    assert state2.threats[0].threat_id == "threat_deadbeef0001"
    assert state2.threats[0].channel == 1
    assert state2.threats[0].authmode == "OPEN"

    # Phase 3: Tracking
    for step in range(5):
        prog = (step + 1) / 5.0
        batches_track = sim.generate_step(scenario=ScenarioType.SUSPICIOUS, progress=prog, step_index=step + 1)
        for b in batches_track:
            pipeline.ingest(b)
    state3 = pipeline.generate_threat_state()
    assert len(state3.threats) == 1
    assert state3.threats[0].estimated_position_2d is not None
