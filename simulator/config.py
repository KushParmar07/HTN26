"""Configuration and scenarios for sensor simulation."""

from enum import Enum
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    """Simulation scenario types."""

    NORMAL = "normal"                  # Only authorized and stable background APs
    SUSPICIOUS = "suspicious"          # Includes rogue evil-twin AP
    ATTACK_APPEARANCE = "appearance"   # Starts normal, rogue appears mid-run


class SimulatedAP(BaseModel):
    """Specification of a simulated transmitter."""

    bssid: str
    ssid: str
    authmode: str
    channel: int
    is_mobile: bool = False
    start_pos: Tuple[float, float] = (0.0, 0.0)
    end_pos: Tuple[float, float] = (0.0, 0.0)


class SimulatorConfig(BaseModel):
    """Simulator environment settings."""

    # Pod coordinates in meters
    pods: Dict[str, Tuple[float, float]] = Field(
        default_factory=lambda: {
            "pod_a": (0.0, 0.0),
            "pod_b": (2.0, 0.0),
            "pod_c": (1.0, 1.7320508075688772),
        }
    )

    # Path loss parameters
    reference_rssi: float = -45.0   # RSSI at 1 meter (dBm)
    path_loss_exponent: float = 2.7
    rssi_noise_std: float = 2.0      # Gaussian noise standard deviation in dBm
    packet_drop_prob: float = 0.05   # Chance a pod drops an AP in a scan
    random_seed: Optional[int] = 42  # Seed for reproducible deterministic runs

    # Authorized legitimate AP
    legitimate_ap: SimulatedAP = Field(
        default_factory=lambda: SimulatedAP(
            bssid="00:11:22:33:44:55",
            ssid="HTN-Secure",
            authmode="WPA2_PSK",
            channel=6,
            is_mobile=False,
            start_pos=(1.0, 0.6),
            end_pos=(1.0, 0.6),
        )
    )

    # Rogue evil-twin AP
    rogue_ap: SimulatedAP = Field(
        default_factory=lambda: SimulatedAP(
            bssid="DE:AD:BE:EF:00:01",
            ssid="HTN-Secure",
            authmode="OPEN",
            channel=1,
            is_mobile=True,
            start_pos=(0.3, 0.3),
            end_pos=(1.5, 0.5),
        )
    )

    # Stable background ambient APs
    background_aps: List[SimulatedAP] = Field(
        default_factory=lambda: [
            SimulatedAP(
                bssid="AA:BB:CC:11:22:33",
                ssid="eduroam",
                authmode="WPA2_ENTERPRISE",
                channel=11,
                is_mobile=False,
                start_pos=(-1.0, 4.0),
                end_pos=(-1.0, 4.0),
            ),
            SimulatedAP(
                bssid="AA:BB:CC:44:55:66",
                ssid="HP-Print-44",
                authmode="OPEN",
                channel=6,
                is_mobile=False,
                start_pos=(5.0, 1.0),
                end_pos=(5.0, 1.0),
            ),
            SimulatedAP(
                bssid="AA:BB:CC:77:88:99",
                ssid="Corporate-Guest",
                authmode="WPA2_PSK",
                channel=1,
                is_mobile=False,
                start_pos=(1.0, 3.0),
                end_pos=(1.0, 3.0),
            ),
        ]
    )


DEFAULT_SIMULATOR_CONFIG = SimulatorConfig()
