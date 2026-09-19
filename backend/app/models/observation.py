"""Observation data models for ESP32 and simulator telemetry."""

from typing import List, Optional
import re
from pydantic import BaseModel, Field, field_validator


def normalize_bssid(raw_bssid: str) -> str:
    """Normalize MAC/BSSID string to uppercase colon-separated format."""
    clean = re.sub(r"[^0-9A-Fa-f]", "", raw_bssid)
    if len(clean) != 12:
        raise ValueError(f"Invalid BSSID length/format: '{raw_bssid}'")
    chunks = [clean[i : i + 2].upper() for i in range(0, 12, 2)]
    return ":".join(chunks)


class SingleObservation(BaseModel):
    """Observation of a single Wi-Fi AP by a sensor pod."""

    bssid: str = Field(..., description="Transmitter MAC address (e.g., DE:AD:BE:EF:00:01)")
    ssid: str = Field(default="", description="Network SSID / name (empty if hidden)")
    rssi: int = Field(..., ge=-120, le=0, description="Received signal strength indicator in dBm")
    channel: int = Field(..., ge=1, le=165, description="Operating Wi-Fi channel")
    authmode: str = Field(default="UNKNOWN", description="Authentication/security mode (e.g. OPEN, WPA2_PSK)")

    @field_validator("bssid")
    @classmethod
    def validate_and_normalize_bssid(cls, v: str) -> str:
        return normalize_bssid(v)

    @field_validator("authmode")
    @classmethod
    def normalize_authmode(cls, v: str) -> str:
        cleaned = v.strip().upper()
        return cleaned if cleaned else "UNKNOWN"


class PodObservationBatch(BaseModel):
    """Batch of observations transmitted by a sensor pod."""

    pod_id: str = Field(..., min_length=1, description="Sensor node identifier (e.g., 'pod_a')")
    timestamp_ms: Optional[int] = Field(
        default=None, description="Pod local timestamp in ms (epoch or uptime)"
    )
    observations: List[SingleObservation] = Field(
        default_factory=list, description="Observed AP records in this scan cycle"
    )
