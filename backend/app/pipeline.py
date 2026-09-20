"""Backend pipeline coordinating state management, detection rules, and 2D localization."""

import time
from typing import Dict, List, Optional
from backend.app.config import DEFAULT_CONFIG, SystemConfig
from backend.app.detection.rules import DeterministicDetector
from backend.app.localization.multilateration import MultilaterationSolver2D
from backend.app.models.observation import PodObservationBatch
from backend.app.models.threat import (
    SensorNodeInfo,
    ThreatItem,
    ThreatStateResponse,
    ThreatStatus,
)
from backend.app.state.ap_state import APStateManager


class BackendPipeline:
    """Core backend pipeline coordinating state, detection, and localization."""

    def __init__(self, config: SystemConfig = DEFAULT_CONFIG):
        self.config = config
        self.state_manager = APStateManager(
            stale_ttl_ms=config.stale_ap_ttl_ms,
            median_window=config.median_window,
            ema_alpha=config.ema_alpha,
            spatial_ema_alpha=config.spatial_smoothing_alpha,
        )
        self.detector = DeterministicDetector(
            authorized=config.authorized_network,
            weights=config.detection_weights,
            suspicious_threshold=config.suspicious_threshold,
            sudden_appearance_threshold_ms=config.sudden_appearance_threshold_ms,
        )
        self.solver = MultilaterationSolver2D(
            sensor_nodes=config.sensor_nodes,
            reference_rssi=config.path_loss_reference_rssi,
            path_loss_exponent=config.path_loss_exponent,
        )

    def ingest(self, batch: PodObservationBatch, received_at_ms: Optional[int] = None) -> None:
        """Ingest a batch of observations from a sensing pod."""
        now_ms = received_at_ms if received_at_ms is not None else int(time.time() * 1000)
        self.state_manager.ingest_batch(batch, received_at_ms=now_ms)

    def generate_threat_state(self, current_time_ms: Optional[int] = None) -> ThreatStateResponse:
        """Compute the current global threat state across all monitored APs."""
        now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)
        self.state_manager.prune_stale(now_ms=now_ms)

        threat_items: List[ThreatItem] = []
        monitored_items: List[ThreatItem] = []
        all_aps = self.state_manager.get_all_aps()

        for ap in all_aps:
            # Active pods observing this AP within time window
            active_pods = ap.get_active_pods(
                now_ms=now_ms, max_age_ms=self.config.active_pod_window_ms
            )

            # Evaluate threat status with global context
            status, risk_score, flags = self.detector.evaluate(
                ap, current_time_ms=now_ms, all_aps=all_aps, active_pods=active_pods
            )

            # Get filtered RSSI per active pod
            pod_rssi_map: Dict[str, float] = {}
            for pod_id in active_pods:
                f_rssi = ap.get_filtered_rssi(pod_id)
                if f_rssi is not None:
                    pod_rssi_map[pod_id] = f_rssi

            # Solve 2D localization if AP is active across pods
            raw_pos_2d, raw_uncertainty = self.solver.solve(pod_rssi_map)

            # Apply temporal spatial smoothing to prevent VR jitter
            smooth_pos_2d, smooth_uncertainty = ap.update_estimated_position(
                raw_pos=raw_pos_2d, raw_uncertainty=raw_uncertainty, now_ms=now_ms
            )

            # Preserve the threat list; expose other actively observed APs separately.
            is_threat = status == ThreatStatus.SUSPICIOUS_INFRASTRUCTURE or risk_score >= self.config.suspicious_threshold
            if is_threat or active_pods:
                destination = threat_items if is_threat else monitored_items
                clean_bssid = ap.bssid.replace(":", "").lower()
                destination.append(
                    ThreatItem(
                        threat_id=f"threat_{clean_bssid}",
                        bssid=ap.bssid,
                        ssid=ap.ssid,
                        status=status,
                        risk_score=risk_score,
                        evidence_flags=flags,
                        estimated_position_2d=smooth_pos_2d,
                        uncertainty_radius_m=smooth_uncertainty,
                        velocity_2d=ap.velocity_2d,
                        position_history=list(ap.position_history),
                        channel=ap.current_channel,
                        authmode=ap.authmode,
                        first_seen_ms=ap.first_seen_ms,
                        last_seen_ms=ap.last_seen_ms,
                        observed_by_pods=active_pods,
                        filtered_rssi_by_pod=pod_rssi_map if pod_rssi_map else None,
                    )
                )

        sensor_nodes_dict: Dict[str, SensorNodeInfo] = {
            node.pod_id: SensorNodeInfo(
                pod_id=node.pod_id,
                x=node.x,
                y=node.y,
                node_type=node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type),
            )
            for node in self.config.sensor_nodes
            if node.enabled
        }

        # Dynamically include any active reporting sensor (e.g. mobile badge)
        for ap in all_aps:
            for pid, last_seen in ap.pod_last_seen_ms.items():
                if pid not in sensor_nodes_dict and abs(now_ms - last_seen) <= self.config.stale_ap_ttl_ms:
                    sensor_nodes_dict[pid] = SensorNodeInfo(
                        pod_id=pid,
                        x=0.0,
                        y=0.0,
                        node_type="mobile",
                    )

        sensor_nodes_info = list(sensor_nodes_dict.values())

        return ThreatStateResponse(
            version="1.0",
            generated_at_ms=now_ms,
            sensor_nodes=sensor_nodes_info,
            threats=threat_items,
            monitored_aps=monitored_items,
        )

    def reset(self) -> None:
        """Clear all active AP states and threat histories."""
        self.state_manager.aps.clear()
        if hasattr(self.config.authorized_network, "get_default_authorized_bssids"):
            self.config.authorized_network.authorized_bssids = set(
                self.config.authorized_network.get_default_authorized_bssids()
            )
        else:
            self.config.authorized_network.authorized_bssids = {"00:11:22:33:44:55"}
        self.detector.authorized = self.config.authorized_network
