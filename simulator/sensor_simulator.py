"""Simulates 3 ESP32 sensing pods observing legitimate, rogue, and background APs."""

import argparse
import math
import random
import time
from typing import List, Optional, Tuple
import httpx
import numpy as np

from backend.app.models.observation import PodObservationBatch, SingleObservation
from simulator.config import (
    DEFAULT_SIMULATOR_CONFIG,
    ScenarioType,
    SimulatedAP,
    SimulatorConfig,
)


class SensorSimulator:
    """
    Simulates multi-pod RF observations with mobile transmitters, realistic path loss,
    and deterministic repeatable scenarios.
    """

    def __init__(self, config: SimulatorConfig = DEFAULT_SIMULATOR_CONFIG):
        self.config = config
        self._rng = random.Random(config.random_seed) if config.random_seed is not None else random.Random()

    def reset_seed(self, seed: Optional[int] = None) -> None:
        """Reset deterministic seed for reproducible test sequences."""
        use_seed = seed if seed is not None else self.config.random_seed
        self._rng = random.Random(use_seed) if use_seed is not None else random.Random()

    def get_ap_position(self, ap: SimulatedAP, progress: float) -> Tuple[float, float]:
        """Interpolate position for mobile AP, or return static position."""
        if not ap.is_mobile:
            return ap.start_pos

        # Triangular oscillation between start_pos and end_pos: progress in [0, 1]
        t = (math.sin(progress * 2 * math.pi - math.pi / 2) + 1.0) / 2.0
        x = ap.start_pos[0] + t * (ap.end_pos[0] - ap.start_pos[0])
        y = ap.start_pos[1] + t * (ap.end_pos[1] - ap.start_pos[1])
        return (round(x, 3), round(y, 3))

    def calculate_rssi(
        self,
        ap_pos: Tuple[float, float],
        pod_pos: Tuple[float, float],
        add_noise: bool = True,
    ) -> int:
        """Calculate RSSI in dBm using log-distance model with optional Gaussian noise."""
        dx = ap_pos[0] - pod_pos[0]
        dy = ap_pos[1] - pod_pos[1]
        dist = max(math.sqrt(dx * dx + dy * dy), 0.1)

        expected_rssi = self.config.reference_rssi - 10.0 * self.config.path_loss_exponent * math.log10(dist)

        if add_noise and self.config.rssi_noise_std > 0:
            noise = self._rng.gauss(0.0, self.config.rssi_noise_std)
            expected_rssi += noise

        # Clamp between -95 dBm and -20 dBm
        clamped = int(np.clip(round(expected_rssi), -95, -20))
        return clamped

    def get_active_aps_for_step(
        self,
        scenario: ScenarioType,
        step_index: int = 0,
        appearance_step: int = 5,
    ) -> List[SimulatedAP]:
        """Determine which APs are transmitting during this step based on the scenario."""
        # Always include legitimate and ambient background APs
        aps = [self.config.legitimate_ap] + list(self.config.background_aps)

        if scenario == ScenarioType.NORMAL:
            # Clean environment without rogue AP
            return aps
        elif scenario == ScenarioType.SUSPICIOUS:
            # Constant presence of rogue AP
            return aps + [self.config.rogue_ap]
        elif scenario == ScenarioType.ATTACK_APPEARANCE:
            # Rogue AP appears only after appearance_step
            if step_index >= appearance_step:
                return aps + [self.config.rogue_ap]
            return aps
        else:
            return aps

    def generate_step(
        self,
        scenario: ScenarioType = ScenarioType.SUSPICIOUS,
        progress: float = 0.0,
        step_index: int = 0,
        appearance_step: int = 5,
        timestamp_ms: int = 0,
        add_noise: bool = True,
        simulate_drops: bool = True,
    ) -> List[PodObservationBatch]:
        """Generate one observation batch for each of the 3 pods."""
        if timestamp_ms == 0:
            timestamp_ms = int(time.time() * 1000)

        active_aps = self.get_active_aps_for_step(
            scenario=scenario,
            step_index=step_index,
            appearance_step=appearance_step,
        )
        batches: List[PodObservationBatch] = []

        for pod_id, pod_pos in self.config.pods.items():
            pod_observations: List[SingleObservation] = []

            for ap in active_aps:
                # Check for simulated packet drop
                if simulate_drops and (self._rng.random() < self.config.packet_drop_prob):
                    continue

                pos = self.get_ap_position(ap, progress)
                rssi = self.calculate_rssi(pos, pod_pos, add_noise=add_noise)

                pod_observations.append(
                    SingleObservation(
                        bssid=ap.bssid,
                        ssid=ap.ssid,
                        rssi=rssi,
                        channel=ap.channel,
                        authmode=ap.authmode,
                    )
                )

            batches.append(
                PodObservationBatch(
                    pod_id=pod_id,
                    timestamp_ms=timestamp_ms,
                    observations=pod_observations,
                )
            )

        return batches

    def run_live(
        self,
        scenario: ScenarioType = ScenarioType.SUSPICIOUS,
        target_url: str = "http://127.0.0.1:8000/api/ingest",
        update_interval_s: float = 1.0,
        total_steps: int = 30,
        appearance_step: int = 5,
    ) -> None:
        """Stream simulated observations to a running backend."""
        print(f"[*] Starting sensor simulation:")
        print(f"    Scenario:         {scenario.value}")
        print(f"    Target URL:       {target_url}")
        print(f"    Update Interval:  {update_interval_s}s")
        print(f"    Total Steps:      {total_steps}")
        if scenario == ScenarioType.ATTACK_APPEARANCE:
            print(f"    Rogue Appearance: Step {appearance_step}")

        with httpx.Client(timeout=5.0) as client:
            for step in range(total_steps):
                progress = step / float(max(1, total_steps))
                batches = self.generate_step(
                    scenario=scenario,
                    progress=progress,
                    step_index=step,
                    appearance_step=appearance_step,
                    add_noise=True,
                    simulate_drops=True,
                )

                rogue_active = (
                    scenario == ScenarioType.SUSPICIOUS
                    or (scenario == ScenarioType.ATTACK_APPEARANCE and step >= appearance_step)
                )

                if rogue_active:
                    rogue_pos = self.get_ap_position(self.config.rogue_ap, progress)
                    status_str = f"ROGUE ACTIVE at ({rogue_pos[0]:.2f}, {rogue_pos[1]:.2f})"
                else:
                    status_str = "CLEAN / NORMAL ENVIRONMENT"

                print(f"[{step + 1:>2}/{total_steps}] {status_str} (sending {len(batches)} pod batches)")

                for batch in batches:
                    try:
                        resp = client.post(target_url, json=batch.model_dump())
                        if resp.status_code != 200:
                            print(f"    [!] Error sending batch from {batch.pod_id}: {resp.status_code}")
                    except Exception as e:
                        print(f"    [!] Connection error sending batch from {batch.pod_id}: {e}")

                time.sleep(update_interval_s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RF Sensor Pod Simulator")
    parser.add_argument(
        "--scenario",
        choices=["normal", "suspicious", "appearance"],
        default="suspicious",
        help="Simulation scenario",
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/ingest", help="Backend ingest URL")
    parser.add_argument("--interval", type=float, default=1.0, help="Scan update interval in seconds")
    parser.add_argument("--steps", type=int, default=30, help="Total simulation steps to run")
    parser.add_argument("--appearance-step", type=int, default=5, help="Step at which rogue AP appears (appearance scenario)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism")
    args = parser.parse_args()

    cfg = SimulatorConfig(random_seed=args.seed)
    sim = SensorSimulator(config=cfg)
    sim.run_live(
        scenario=ScenarioType(args.scenario),
        target_url=args.url,
        update_interval_s=args.interval,
        total_steps=args.steps,
        appearance_step=args.appearance_step,
    )
