using UnityEngine;

namespace RFThreatDetection.Spatial
{
    /// <summary>
    /// Isolates all coordinate mapping between the 2D backend metric plane and
    /// the 3D Meta Quest spatial room coordinate system.
    ///
    /// Backend plane:
    ///   - Pod A is at origin (0, 0)
    ///   - Pod B is at (2.0, 0) along the baseline (+X)
    ///   - Pod C is at (1.0, 1.73205) into the room (+Y)
    ///
    /// Quest 3D space:
    ///   - +X is Right
    ///   - +Y is Up
    ///   - +Z is Forward / Depth
    /// </summary>
    public class RoomCoordinateTransformer : MonoBehaviour
    {
        [Header("Room Calibration")]
        [Tooltip("World position representing the reference pod (Pod A at 0, 0)")]
        [SerializeField] private Vector3 roomOrigin = Vector3.zero;

        [Tooltip("Yaw rotation in degrees to align backend room axes with physical room")]
        [SerializeField] private float roomYawDegrees = 0f;

        [Tooltip("Default height above floor for floating threat volumes in meters")]
        [SerializeField] private float defaultHeightMeters = 1.0f;

        [Tooltip("Global metric scale factor (1.0 = 1 meter)")]
        [SerializeField] private float scaleFactor = 1.0f;

        private bool usesPlacedPodCalibration;
        private Vector3 placedXAxisPerMeter = Vector3.right;
        private Vector3 placedYAxisPerMeter = Vector3.forward;

        public Vector3 RoomOrigin => roomOrigin;
        public float RoomYawDegrees => roomYawDegrees;
        public float DefaultHeightMeters => defaultHeightMeters;
        public bool UsesPlacedPodCalibration => usesPlacedPodCalibration;

        /// <summary>
        /// Transform 2D backend coordinates (X, Y) into 3D Quest world coordinates.
        /// </summary>
        /// <param name="backendX">X coordinate in meters (along Pod A -> Pod B baseline)</param>
        /// <param name="backendY">Y coordinate in meters (into the room towards Pod C)</param>
        /// <param name="customHeight">Optional custom vertical height in meters (-1 uses defaultHeightMeters)</param>
        /// <returns>World position in Meta Quest space</returns>
        public Vector3 BackendToWorld(float backendX, float backendY, float customHeight = -1f)
        {
            float height = customHeight >= 0f ? customHeight : defaultHeightMeters;

            if (usesPlacedPodCalibration)
            {
                return roomOrigin + placedXAxisPerMeter * backendX +
                       placedYAxisPerMeter * backendY + Vector3.up * height;
            }

            // Map backend 2D (X, Y) into local 3D (Right, Up, Forward)
            Vector3 localPos = new Vector3(
                backendX * scaleFactor,
                height,
                backendY * scaleFactor
            );

            // Apply room rotation around Y axis
            Quaternion rotation = Quaternion.Euler(0f, roomYawDegrees, 0f);
            Vector3 rotatedPos = rotation * localPos;

            // Apply world origin offset
            return roomOrigin + rotatedPos;
        }

        /// <summary>
        /// Transform sensor pod coordinates into Quest world position (fixed at antenna height).
        /// </summary>
        public Vector3 TransformSensorNode(float backendX, float backendY, float podHeight = 0.8f)
        {
            return BackendToWorld(backendX, backendY, podHeight);
        }

        /// <summary>
        /// Inverse transformation: Map 3D Quest world position back to 2D backend plane coordinates.
        /// Useful for calibration and placing virtual pods with Quest controllers.
        /// </summary>
        public Vector2 WorldToBackend(Vector3 worldPos)
        {
            Vector3 diff = worldPos - roomOrigin;

            if (usesPlacedPodCalibration)
            {
                diff.y = 0f;
                float xx = Vector3.Dot(placedXAxisPerMeter, placedXAxisPerMeter);
                float xy = Vector3.Dot(placedXAxisPerMeter, placedYAxisPerMeter);
                float yy = Vector3.Dot(placedYAxisPerMeter, placedYAxisPerMeter);
                float dx = Vector3.Dot(diff, placedXAxisPerMeter);
                float dy = Vector3.Dot(diff, placedYAxisPerMeter);
                float determinant = xx * yy - xy * xy;
                if (Mathf.Abs(determinant) < 0.0001f) return Vector2.zero;
                return new Vector2((dx * yy - dy * xy) / determinant,
                                   (dy * xx - dx * xy) / determinant);
            }

            Quaternion invRot = Quaternion.Euler(0f, -roomYawDegrees, 0f);
            Vector3 local = invRot * diff;

            float x = local.x / scaleFactor;
            float y = local.z / scaleFactor;
            return new Vector2(x, y);
        }

        /// <summary>
        /// Recalibrate room alignment at runtime (e.g. by pressing a controller button at Pod A).
        /// </summary>
        public void RecalibrateOrigin(Vector3 newOrigin, float newYaw)
        {
            usesPlacedPodCalibration = false;
            roomOrigin = newOrigin;
            roomYawDegrees = newYaw;
            Debug.Log($"[RoomCoordinateTransformer] Recalibrated: Origin={roomOrigin}, Yaw={roomYawDegrees}°");
        }

        /// <summary>
        /// Fits the backend coordinate plane to three controller-placed physical pod points.
        /// This preserves the backend's fixed A(0,0), B(2,0), C(1,sqrt(3)) geometry while
        /// allowing the AR overlay to match the actual room.
        /// </summary>
        public bool RecalibrateFromPlacedPods(Vector3 podAWorld, Vector3 podBWorld, Vector3 podCWorld)
        {
            podAWorld.y = 0f;
            podBWorld.y = 0f;
            podCWorld.y = 0f;

            Vector3 xAxis = (podBWorld - podAWorld) / 2f;
            Vector3 yAxis = (podCWorld - podAWorld - xAxis * 1f) / Mathf.Sqrt(3f);
            if (xAxis.magnitude < 0.15f || yAxis.magnitude < 0.15f ||
                Vector3.Cross(xAxis, yAxis).sqrMagnitude < 0.0025f)
                return false;

            roomOrigin = podAWorld;
            placedXAxisPerMeter = xAxis;
            placedYAxisPerMeter = yAxis;
            usesPlacedPodCalibration = true;
            roomYawDegrees = Mathf.Atan2(xAxis.z, xAxis.x) * Mathf.Rad2Deg;
            Debug.Log($"[RoomCoordinateTransformer] Three-point pod calibration applied: A={podAWorld}, B={podBWorld}, C={podCWorld}");
            return true;
        }

        private void OnDrawGizmosSelected()
        {
            // Visualize room axes in Unity Editor scene view
            Gizmos.color = Color.green;
            Gizmos.DrawWireSphere(roomOrigin, 0.15f);

            Vector3 podA = BackendToWorld(0f, 0f, 0.1f);
            Vector3 podB = BackendToWorld(2f, 0f, 0.1f);
            Vector3 podC = BackendToWorld(1f, Mathf.Sqrt(3f), 0.1f);

            Gizmos.color = Color.cyan;
            Gizmos.DrawLine(podA, podB);
            Gizmos.DrawLine(podB, podC);
            Gizmos.DrawLine(podC, podA);
        }
    }
}
