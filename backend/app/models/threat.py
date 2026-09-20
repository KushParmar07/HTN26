"""Threat state data models consumed by the VR application and REST API."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, computed_field, model_validator


class ThreatStatus(str, Enum):
    """Classification status for an access point."""

    AUTHORIZED = "AUTHORIZED"
    MONITORED = "MONITORED"
    SUSPICIOUS_INFRASTRUCTURE = "SUSPICIOUS_INFRASTRUCTURE"


class EvidenceFlag(str, Enum):
    """Deterministic evidence flags contributing to risk score."""

    UNKNOWN_BSSID = "UNKNOWN_BSSID"
    DUPLICATE_SSID = "DUPLICATE_SSID"
    SECURITY_MISMATCH = "SECURITY_MISMATCH"
    SUDDEN_APPEARANCE = "SUDDEN_APPEARANCE"
    UNEXPECTED_CHANNEL = "UNEXPECTED_CHANNEL"
    SPATIAL_ANOMALY = "SPATIAL_ANOMALY"
    MULTIPLE_SENSORS = "MULTIPLE_SENSORS"
    STRONG_SIGNAL = "STRONG_SIGNAL"


class Position2D(BaseModel):
    """2D estimated physical coordinates in meters."""

    x: float = Field(..., description="X coordinate in meters relative to reference pod")
    y: float = Field(..., description="Y coordinate in meters relative to reference pod")


class Velocity2D(BaseModel):
    """2D velocity vector in meters per second."""

    vx: float = Field(default=0.0, description="Velocity X component in m/s")
    vy: float = Field(default=0.0, description="Velocity Y component in m/s")
    speed_mps: float = Field(default=0.0, description="Scalar speed in m/s")
    direction_deg: Optional[float] = Field(
        default=None, description="Heading direction in degrees [0, 360) where 0 is +X"
    )
    movement_state: str = Field(
        default="STATIONARY", description="Movement classification (e.g. STATIONARY, MOVING)"
    )


class SensorNodeInfo(BaseModel):
    """Physical position and configuration of a sensing pod or node."""

    pod_id: str = Field(..., description="Pod identifier")
    x: float = Field(..., description="Fixed X coordinate in meters")
    y: float = Field(..., description="Fixed Y coordinate in meters")
    node_type: str = Field(default="fixed", description="Node type: 'fixed' or 'mobile'")


class ThreatItem(BaseModel):
    """Active threat entry representing an access point for 3D/VR rendering."""

    threat_id: str = Field(
        default="",
        description="Stable unique threat identifier for 3D/VR object tracking",
    )
    bssid: str = Field(..., description="Transmitter MAC address")
    ssid: str = Field(default="", description="Observed SSID")
    status: ThreatStatus = Field(..., description="Threat classification status")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Explainable risk score (0-100)")
    evidence_flags: List[EvidenceFlag] = Field(
        default_factory=list, description="List of triggered explainable evidence flags"
    )
    estimated_position_2d: Optional[Position2D] = Field(
        default=None, description="Estimated 2D position in meters, or None if insufficient pods"
    )
    uncertainty_radius_m: Optional[float] = Field(
        default=None, ge=0.0, description="Estimated 1-sigma uncertainty radius in meters"
    )
    velocity_2d: Optional[Velocity2D] = Field(
        default=None, description="Derived 2D velocity vector and speed"
    )
    position_history: List[Position2D] = Field(
        default_factory=list, description="Recent bounded valid physical positions"
    )
    channel: Optional[int] = Field(
        default=None, description="Current operating Wi-Fi channel"
    )
    authmode: Optional[str] = Field(
        default=None, description="Observed authentication/security mode"
    )
    first_seen_ms: Optional[int] = Field(
        default=None, description="Unix timestamp ms when AP was first observed"
    )
    last_seen_ms: int = Field(..., description="Unix timestamp ms when AP was last observed")
    observed_by_pods: List[str] = Field(
        default_factory=list, description="List of pods that observed this AP in the active window"
    )
    filtered_rssi_by_pod: Optional[dict[str, float]] = Field(
        default=None, description="Current filtered RSSI per detecting pod in dBm"
    )

    @model_validator(mode="after")
    def populate_defaults(self) -> "ThreatItem":
        if not self.threat_id:
            clean_bssid = self.bssid.replace(":", "").lower()
            self.threat_id = f"threat_{clean_bssid}"
        if self.first_seen_ms is None:
            self.first_seen_ms = self.last_seen_ms
        return self


class ThreatStateResponse(BaseModel):
    """Versioned threat state snapshot streamed over WebSocket and REST."""

    version: str = Field(default="1.0", description="Contract version")
    generated_at_ms: int = Field(..., description="Unix timestamp ms of state generation")
    sensor_nodes: List[SensorNodeInfo] = Field(
        default_factory=list, description="Positions of fixed sensing pods"
    )
    threats: List[ThreatItem] = Field(
        default_factory=list, description="List of active detected threats"
    )

    @computed_field
    @property
    def active_threats(self) -> List[ThreatItem]:
        """Convenience alias for VR clients expecting active_threats."""
        return self.threats
