"""Observation data models for ESP32 and simulator telemetry."""

from typing import List, Optional
import re
from pydantic import BaseModel, Field, field_validator, model_validator


def normalize_bssid(raw_bssid: str) -> str:
    """Normalize MAC/BSSID string to uppercase colon-separated format."""
    if not raw_bssid or not isinstance(raw_bssid, str):
        raise ValueError(f"Invalid BSSID: '{raw_bssid}'")
    clean = re.sub(r"[^0-9A-Fa-f]", "", raw_bssid)
    if len(clean) != 12:
        raise ValueError(f"Invalid BSSID length/format: '{raw_bssid}'")
    chunks = [clean[i : i + 2].upper() for i in range(0, 12, 2)]
    return ":".join(chunks)


class SingleObservation(BaseModel):
    """Observation of a single Wi-Fi AP by a sensor pod."""

    bssid: str = Field(..., description="Transmitter MAC address (e.g., DE:AD:BE:EF:00:01)")
    ssid: Optional[str] = Field(default="", description="Network SSID / name (empty if hidden)")
    rssi: int = Field(..., ge=-120, le=0, description="Received signal strength indicator in dBm")
    channel: int = Field(..., ge=1, le=165, description="Operating Wi-Fi channel")
    authmode: str = Field(default="UNKNOWN", description="Authentication/security mode (e.g. OPEN, WPA2_PSK)")

    @field_validator("bssid", mode="before")
    @classmethod
    def validate_and_normalize_bssid(cls, v) -> str:
        return normalize_bssid(str(v).strip())

    @field_validator("ssid", mode="before")
    @classmethod
    def sanitize_ssid(cls, v) -> str:
        if v is None:
            return ""
        s = str(v).replace("\x00", "")
        if len(s) > 128:
            s = s[:128]
        return s

    @field_validator("rssi", mode="before")
    @classmethod
    def parse_rssi(cls, v) -> int:
        try:
            return int(round(float(v)))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid RSSI value: {v}")

    @field_validator("channel", mode="before")
    @classmethod
    def parse_channel(cls, v) -> int:
        try:
            return int(float(v))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid channel value: {v}")

    @field_validator("authmode", mode="before")
    @classmethod
    def normalize_authmode(cls, v) -> str:
        if v is None:
            return "UNKNOWN"
        cleaned = str(v).strip().upper().replace("-", "_")
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

    @field_validator("pod_id", mode="before")
    @classmethod
    def normalize_pod_id(cls, v) -> str:
        if not v or not str(v).strip():
            raise ValueError("pod_id cannot be empty")
        return str(v).strip().lower()

    @model_validator(mode="after")
    def deduplicate_observations(self) -> "PodObservationBatch":
        """Deduplicate observations by BSSID within the same batch, retaining the strongest RSSI."""
        if not self.observations:
            return self
        deduped: dict[str, SingleObservation] = {}
        for obs in self.observations:
            if obs.bssid not in deduped or obs.rssi > deduped[obs.bssid].rssi:
                deduped[obs.bssid] = obs
        self.observations = list(deduped.values())
        return self
