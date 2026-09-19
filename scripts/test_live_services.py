"""Live integration test: connects to WebSocket /ws/threats, streams batches to /api/ingest, and prints live events."""

import asyncio
import json
import httpx
import websockets

from simulator.config import ScenarioType, SimulatorConfig
from simulator.sensor_simulator import SensorSimulator


async def run_live_test():
    base_http = "http://127.0.0.1:8000"
    base_ws = "ws://127.0.0.1:8000/ws/threats"

    print(f"[*] Checking backend health at {base_http}/health...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{base_http}/health")
            if resp.status_code != 200:
                print(f"[!] Backend returned status {resp.status_code}")
                return False
            print(f"[+] Health check OK: {resp.json()}")
        except Exception as e:
            print(f"[!] Failed to connect to backend: {e}")
            return False

        # Reset pipeline
        await client.post(f"{base_http}/api/reset")
        print("[+] Reset pipeline state.")

    # Connect WebSocket client (simulating Meta Quest headset)
    print(f"[*] Connecting WebSocket client to {base_ws}...")
    async with websockets.connect(base_ws) as ws:
        # Receive initial state
        init_raw = await ws.recv()
        init_state = json.loads(init_raw)
        print(f"[+] WebSocket connected. Initial threats: {len(init_state['threats'])}")

        sim = SensorSimulator(config=SimulatorConfig(random_seed=42))

        # Part A: Send normal step
        print("[*] Streaming 1 NORMAL step (authorized + ambient APs)...")
        batches_normal = sim.generate_step(scenario=ScenarioType.NORMAL, progress=0.0, step_index=0)
        async with httpx.AsyncClient() as client:
            for b in batches_normal:
                await client.post(f"{base_http}/api/ingest", json=b.model_dump())
                normal_evt_raw = await ws.recv()
                normal_evt = json.loads(normal_evt_raw)

        print(f"[+] WebSocket received event. Active threats: {len(normal_evt['threats'])}")
        assert len(normal_evt['threats']) == 0, "Expected 0 threats for normal scenario!"

        # Part B: Send suspicious step (rogue AP evil twin)
        print("[*] Streaming 1 SUSPICIOUS step (rogue AP evil twin)...")
        batches_suspicious = sim.generate_step(
            scenario=ScenarioType.SUSPICIOUS,
            progress=0.0,
            step_index=0,
            simulate_drops=False,
        )
        async with httpx.AsyncClient() as client:
            for b in batches_suspicious:
                await client.post(f"{base_http}/api/ingest", json=b.model_dump())
                susp_evt_raw = await ws.recv()
                susp_evt = json.loads(susp_evt_raw)

        print(f"[+] WebSocket received event. Active threats: {len(susp_evt['threats'])}")
        assert len(susp_evt['threats']) == 1, "Expected 1 threat for suspicious scenario!"
        threat = susp_evt['threats'][0]
        print(f"    Threat BSSID:     {threat['bssid']}")
        print(f"    Threat SSID:      {threat['ssid']}")
        print(f"    Threat Status:    {threat['status']}")
        print(f"    Risk Score:       {threat['risk_score']}")
        print(f"    Evidence Flags:   {threat['evidence_flags']}")
        print(f"    Estimated Pos 2D: {threat['estimated_position_2d']}")
        print(f"    Uncertainty (m):  {threat['uncertainty_radius_m']}")

    print("\n[✓] Live HTTP Ingest -> Pipeline -> WebSocket Quest delivery successfully verified!")
    return True


if __name__ == "__main__":
    asyncio.run(run_live_test())
