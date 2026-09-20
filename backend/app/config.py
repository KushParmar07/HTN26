from enum import Enum
from typing import List, Optional, Set
from pydantic import BaseModel, Field


class SensorNodeType(str, Enum):
    """Classification of an RF sensing node."""

    FIXED = "fixed"
    MOBILE = "mobile"


class SensorNodeConfig(BaseModel):
    """Configuration of an RF sensing node."""

    pod_id: str
    x: float = 0.0
    y: float = 0.0
    node_type: SensorNodeType = SensorNodeType.FIXED
    enabled: bool = True


class AuthorizedNetworkConfig(BaseModel):
    """Authorized baseline network specification."""

    ssid: str = "HTN-Secure"
    authorized_bssids: Set[str] = {"00:11:22:33:44:55"}
    expected_authmode: str = "WPA2_PSK"
    expected_channels: Set[int] = {6}


class DetectionWeights(BaseModel):
    """Configurable weights for deterministic risk scoring."""

    unknown_bssid: float = 30.0
    duplicate_ssid: float = 25.0
    security_mismatch: float = 20.0
    unexpected_channel: float = 15.0
    sudden_appearance: float = 10.0
    multiple_sensors: float = 10.0
    strong_signal: float = 5.0


class SystemConfig(BaseModel):
    """Root configuration for backend RF threat detection."""

    # Sensor positions in meters
    sensor_nodes: List[SensorNodeConfig] = Field(
        default_factory=lambda: [
            SensorNodeConfig(pod_id="pod_a", x=0.0, y=0.0),
            SensorNodeConfig(pod_id="pod_b", x=4.0, y=0.0),
            SensorNodeConfig(pod_id="pod_c", x=2.0, y=3.5),
        ]
    )

    # Baseline authorized network
    authorized_network: AuthorizedNetworkConfig = Field(
        default_factory=AuthorizedNetworkConfig
    )

    # Detection weights and thresholds
    detection_weights: DetectionWeights = Field(default_factory=DetectionWeights)
    suspicious_threshold: float = 40.0
    sudden_appearance_threshold_ms: int = 60000  # 60 seconds

    # RSSI Path Loss Model parameters (RSSI = A - 10 * n * log10(d))
    path_loss_reference_rssi: float = -45.0  # RSSI at 1 meter (dBm)
    path_loss_exponent: float = 2.7          # Path loss exponent n

    # Temporal RSSI filtering
    median_window: int = 5
    ema_alpha: float = 0.3
    stale_ap_ttl_ms: int = 20000             # 20 seconds

    # Spatial position temporal smoothing (1.0 = direct from filtered RSSI)
    spatial_smoothing_alpha: float = 1.0

    # Development & test endpoint gating
    enable_dev_endpoints: bool = True

    # WebSocket heartbeat & state sync interval
    websocket_heartbeat_interval_s: float = 1.0


# Global default instance
DEFAULT_CONFIG = SystemConfig()
