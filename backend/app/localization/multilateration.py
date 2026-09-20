"""2D RF Multilateration using log-distance path loss and nonlinear least squares."""

from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull, QhullError
from backend.app.config import SensorNodeConfig
from backend.app.models.threat import Position2D


def rssi_to_distance_m(rssi: float, reference_rssi: float = -45.0, path_loss_exponent: float = 2.7) -> float:
    """
    Convert RSSI (dBm) to estimated distance (meters) using log-distance model:
    d = 10 ** ((reference_rssi - rssi) / (10 * n))
    """
    if not np.isfinite(rssi):
        return 1.0
    if path_loss_exponent <= 0:
        raise ValueError("path_loss_exponent must be > 0")
    exponent = (reference_rssi - rssi) / (10.0 * path_loss_exponent)
    # Bound exponent to prevent numerical overflow/underflow (0.001m to 10,000m)
    exponent = float(np.clip(exponent, -3.0, 4.0))
    dist = float(10.0 ** exponent)
    return dist if np.isfinite(dist) and dist > 0 else 1.0


class MultilaterationSolver2D:
    """Solves 2D coordinates and uncertainty from multi-sensor RSSI measurements."""

    def __init__(
        self,
        sensor_nodes: List[SensorNodeConfig],
        reference_rssi: float = -45.0,
        path_loss_exponent: float = 2.7,
        min_uncertainty_radius_m: float = 0.3,
        max_uncertainty_radius_m: float = 5.0,
    ):
        # Only FIXED enabled sensor nodes can serve as spatial anchors for multilateration
        self.sensor_nodes = {
            node.pod_id: (float(node.x), float(node.y))
            for node in sensor_nodes
            if getattr(node, "node_type", SensorNodeType.FIXED) == SensorNodeType.FIXED
            and getattr(node, "enabled", True)
        }
        self.reference_rssi = reference_rssi
        self.path_loss_exponent = path_loss_exponent
        self.min_uncertainty_radius_m = min_uncertainty_radius_m
        self.max_uncertainty_radius_m = max_uncertainty_radius_m

    @staticmethod
    def _inside_sensor_hull(point: np.ndarray, coords: np.ndarray) -> bool:
        """Return whether point lies inside the convex hull of non-collinear pods."""
        try:
            hull = ConvexHull(coords)
        except QhullError:
            return True  # Degenerate layouts retain the finite least-squares fallback.
        polygon = coords[hull.vertices]
        crosses = []
        for index in range(len(polygon)):
            start = polygon[index]
            end = polygon[(index + 1) % len(polygon)]
            edge = end - start
            offset = point - start
            crosses.append(edge[0] * offset[1] - edge[1] * offset[0])
        return all(value >= -1e-6 for value in crosses) or all(
            value <= 1e-6 for value in crosses
        )

    @staticmethod
    def _signal_weighted_centroid(
        coords: np.ndarray, rssi_values: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """
        Produce an always-in-hull fallback from relative signal strengths.

        Absolute RSSI-to-distance calibration varies substantially between ESP32
        antennas and phone radios. Relative weighting still provides a stable,
        explainable direction toward the pod receiving the strongest signal.
        """
        strongest = float(np.max(rssi_values))
        weights = np.exp((rssi_values - strongest) / 10.0)
        centroid = np.average(coords, axis=0, weights=weights)
        spread = float(
            np.sqrt(np.average(np.sum((coords - centroid) ** 2, axis=1), weights=weights))
        )
        return centroid, spread

    def solve(
        self, pod_rssi: Dict[str, float]
    ) -> Tuple[Optional[Position2D], Optional[float]]:
        """
        Estimate 2D position (x, y) and uncertainty radius in meters.
        Returns: (Position2D, uncertainty_radius_m) or (None, None) if < 3 sensors.
        """
        available_pods = [
            pid
            for pid in pod_rssi
            if pid in self.sensor_nodes
            and pod_rssi[pid] is not None
            and np.isfinite(pod_rssi[pid])
        ]

        if len(available_pods) < 3:
            return None, None

        pod_coords = np.array([self.sensor_nodes[pid] for pid in available_pods], dtype=float)
        distances = np.array(
            [
                rssi_to_distance_m(
                    float(pod_rssi[pid]),
                    reference_rssi=self.reference_rssi,
                    path_loss_exponent=self.path_loss_exponent,
                )
                for pid in available_pods
            ],
            dtype=float,
        )
        rssi_values = np.array([float(pod_rssi[pid]) for pid in available_pods], dtype=float)

        # Residual function: difference between candidate Euclidean distance and estimated distance
        def residuals(pos: np.ndarray) -> np.ndarray:
            diffs = pod_coords - pos
            dist_cand = np.linalg.norm(diffs, axis=1)
            return dist_cand - distances

        # Initial guess: weighted centroid by inverse estimated distance
        safe_distances = np.maximum(distances, 0.1)
        weights = 1.0 / safe_distances
        initial_guess = np.average(pod_coords, axis=0, weights=weights)

        try:
            res = least_squares(
                residuals,
                initial_guess,
                method="lm",  # Levenberg-Marquardt
                loss="linear",
                max_nfev=200,
            )
            estimated_x = float(res.x[0])
            estimated_y = float(res.x[1])

            if not (np.isfinite(estimated_x) and np.isfinite(estimated_y)):
                estimated_x, estimated_y = float(initial_guess[0]), float(initial_guess[1])

            # Compute residual RMSE
            dof = max(1, len(available_pods) - 2)
            rmse = float(np.sqrt(np.sum(res.fun ** 2) / dof))

            # Approximate covariance from Jacobian if available
            spatial_std = rmse
            if hasattr(res, "jac") and res.jac is not None and res.jac.size > 0:
                try:
                    jtj = res.jac.T @ res.jac
                    cov = np.linalg.pinv(jtj) * (rmse ** 2)
                    tr = np.trace(cov)
                    if np.isfinite(tr) and tr > 0:
                        spatial_std = float(np.sqrt(tr))
                except Exception:
                    spatial_std = rmse

            # Generic path-loss calibration can yield a mathematically valid point
            # well outside a compact physical pod formation. When measurements are
            # mutually inconsistent, use relative RSSI to keep the estimate inside
            # the sensor hull and moving toward the strongest receiving pod.
            estimated = np.array([estimated_x, estimated_y], dtype=float)
            max_baseline = max(
                np.linalg.norm(first - second)
                for first in pod_coords
                for second in pod_coords
            )
            inconsistent = rmse > max(0.75, max_baseline * 0.35)
            if inconsistent or not self._inside_sensor_hull(estimated, pod_coords):
                fallback, spread = self._signal_weighted_centroid(pod_coords, rssi_values)
                estimated_x, estimated_y = float(fallback[0]), float(fallback[1])
                spatial_std = max(self.min_uncertainty_radius_m, spread)
        except Exception:
            # Fallback to robust weighted centroid if nonlinear optimization fails
            fallback, spread = self._signal_weighted_centroid(pod_coords, rssi_values)
            estimated_x = float(fallback[0])
            estimated_y = float(fallback[1])
            spatial_std = max(self.min_uncertainty_radius_m, spread)

        # Clamp uncertainty within strictly finite positive bounds
        if not np.isfinite(spatial_std) or spatial_std <= 0:
            spatial_std = self.min_uncertainty_radius_m

        uncertainty = float(
            np.clip(spatial_std, self.min_uncertainty_radius_m, self.max_uncertainty_radius_m)
        )

        return (
            Position2D(x=round(estimated_x, 3), y=round(estimated_y, 3)),
            round(uncertainty, 3),
        )
