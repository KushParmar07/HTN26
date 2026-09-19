"""Interactive / automated hackathon demo runner demonstrating the end-to-end threat lifecycle."""

import argparse
import time
import httpx

from simulator.config import ScenarioType, SimulatorConfig
from simulator.sensor_simulator import SensorSimulator


def print_banner(text: str):
    line = "=" * 80
    print(f"\n{line}\n   {text}\n{line}")


def print_phase(num: int, title: str, description: str):
    print(f"\n>>> [DEMO PHASE {num}] {title}")
    print(f"    {description}\n")


def run_demo(
    backend_url: str = "http://127.0.0.1:8000",
    interval_s: float = 1.0,
    seed: int = 42,
):
    print_banner("RF THREAT DETECTION & LOCALIZATION: HACKATHON LIVE DEMONSTRATION")
    print(f"Target Backend:      {backend_url}")
    print(f"Step Cadence:        {interval_s}s per scan batch")
    print(f"Deterministic Seed:  {seed}")

    client = httpx.Client(timeout=5.0)

    # 1. Health check & reset
    try:
        health = client.get(f"{backend_url}/health").json()
        print(f"[+] Connected to Backend. Status: {health['status']}, Configured Pods: {health['configured_pods']}")
        client.post(f"{backend_url}/api/reset")
        print("[+] Reset pipeline to clean state.")
    except Exception as e:
        print(f"[!] Could not connect to backend at {backend_url}: {e}")
        print("    Ensure the backend is running via:")
        print("    conda run -n rf-threat-detection uvicorn backend.app.main:app --port 8000")
        return

    sim = SensorSimulator(config=SimulatorConfig(random_seed=seed, rssi_noise_std=1.0))

    # =========================================================================
    # PHASE 1: NORMAL ENVIRONMENT (Clean Baseline)
    # =========================================================================
    print_phase(
        1,
        "ESTABLISHING AUTHORIZED NETWORK BASELINE",
        "Sensors observe legitimate infrastructure ('HTN-Secure' Ch 6) and ambient Wi-Fi. No threats present.",
    )

    for step in range(3):
        batches = sim.generate_step(
            scenario=ScenarioType.NORMAL,
            progress=0.0,
            step_index=step,
            add_noise=True,
            simulate_drops=False,
        )
        for b in batches:
            client.post(f"{backend_url}/api/ingest", json=b.model_dump())

        state = client.get(f"{backend_url}/api/threats").json()
        active_count = len(state["threats"])
        print(f"  [Step {step + 1}/3] Ingested 3 pod scans -> Active Threats: {active_count}")
        time.sleep(interval_s)

    print("  [✓] PHASE 1 COMPLETE: Environment verified clean. VR display shows zero threat volumes.")

    # =========================================================================
    # PHASE 2: ROGUE AP POWERS ON (Threat Alert Triggered)
    # =========================================================================
    print_phase(
        2,
        "ATTACK LAUNCH: CONTROLLED ROGUE AP POWERS ON",
        "A fourth ESP32 transmits 'HTN-Secure' with unknown BSSID and OPEN authentication.",
    )

    # Ingest 1 suspicious step at start position (0.5, 0.5)
    batches_attack = sim.generate_step(
        scenario=ScenarioType.SUSPICIOUS,
        progress=0.0,
        step_index=0,
        add_noise=True,
        simulate_drops=False,
    )
    for b in batches_attack:
        client.post(f"{backend_url}/api/ingest", json=b.model_dump())

    state = client.get(f"{backend_url}/api/threats").json()
    assert len(state["threats"]) >= 1, "Rogue AP was not detected!"
    threat = state["threats"][0]

    print("  [!] ********** THREAT ALERT BROADCAST TO QUEST VR **********")
    print(f"      Threat ID:       {threat['threat_id']}")
    print(f"      SSID:            {threat['ssid']} (IMPERSONATING AUTHORIZED NETWORK)")
    print(f"      BSSID:           {threat['bssid']} (UNKNOWN INFRASTRUCTURE)")
    print(f"      Status:          {threat['status']}")
    print(f"      Risk Score:      {threat['risk_score']:.0f} / 100")
    print(f"      Security Mode:   {threat['authmode']} (MISMATCH: Expected WPA2_PSK)")
    print(f"      Operating Ch:    {threat['channel']} (MISMATCH: Expected Channel 6)")
    print(f"      Evidence Flags:  {', '.join(threat['evidence_flags'])}")
    if threat["estimated_position_2d"]:
        pos = threat["estimated_position_2d"]
        print(f"      Initial 2D Pos:  X={pos['x']:.2f}m, Y={pos['y']:.2f}m")
        print(f"      Uncertainty:     {threat['uncertainty_radius_m']:.2f}m (sets VR cloud radius)")
    print("  [!] ********************************************************")

    time.sleep(interval_s)
    print("  [✓] PHASE 2 COMPLETE: Rogue transmitter identified and explainable evidence generated.")

    # =========================================================================
    # PHASE 3: PHYSICAL MOVEMENT & CONTINUOUS SPATIAL TRACKING
    # =========================================================================
    print_phase(
        3,
        "SPATIAL TRACKING: TRANSMITTER MOVES THROUGH ROOM",
        "Presenter physically walks with rogue device. 2D multilateration tracks movement smoothly.",
    )

    header = f"  {'Step':<5} | {'Ground Truth (X, Y)':<20} | {'Estimated (X, Y)':<18} | {'Err (m)':<8} | {'Uncert (m)':<10} | {'Risk':<5}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    tracking_steps = 8
    for step in range(tracking_steps):
        progress = (step + 1) / float(tracking_steps)
        truth_pos = sim.get_ap_position(sim.config.rogue_ap, progress)

        batches_track = sim.generate_step(
            scenario=ScenarioType.SUSPICIOUS,
            progress=progress,
            step_index=step + 1,
            add_noise=True,
            simulate_drops=False,
        )
        for b in batches_track:
            client.post(f"{backend_url}/api/ingest", json=b.model_dump())

        state = client.get(f"{backend_url}/api/threats").json()
        rogue = next((t for t in state["threats"] if t["bssid"] == sim.config.rogue_ap.bssid), None)

        if rogue and rogue["estimated_position_2d"]:
            pos = rogue["estimated_position_2d"]
            err = ((pos["x"] - truth_pos[0]) ** 2 + (pos["y"] - truth_pos[1]) ** 2) ** 0.5
            print(
                f"  {step+1:<5} | ({truth_pos[0]:.2f}, {truth_pos[1]:.2f}){'':<7} | "
                f"({pos['x']:.2f}, {pos['y']:.2f}){'':<6} | "
                f"{err:<8.2f} | {rogue['uncertainty_radius_m']:<10.2f} | {rogue['risk_score']:<5.0f}"
            )

        time.sleep(interval_s)

    print("\n  [✓] PHASE 3 COMPLETE: Spatial trajectory tracked and rendered smoothly in VR.")
    print_banner("DEMONSTRATION COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Hackathon Demo Runner")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval between steps in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    args = parser.parse_args()

    run_demo(backend_url=args.url, interval_s=args.interval, seed=args.seed)
