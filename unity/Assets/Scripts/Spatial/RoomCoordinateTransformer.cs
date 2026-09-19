using UnityEngine;

namespace RFThreatDetection.Spatial
{
    /// <summary>
    /// Isolates all coordinate mapping between the 2D backend metric plane and
    /// the 3D Meta Quest spatial room coordinate system.
    ///
    /// Backend plane:
    ///   - Pod A is at origin (0, 0)
    ///   - Pod B is at (4.0, 0) along the baseline (+X)
    ///   - Pod C is at (2.0, 3.5) into the room (+Y)
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

        public Vector3 RoomOrigin => roomOrigin;
        public float RoomYawDegrees => roomYawDegrees;
        public float DefaultHeightMeters => defaultHeightMeters;

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
            roomOrigin = newOrigin;
            roomYawDegrees = newYaw;
            Debug.Log($"[RoomCoordinateTransformer] Recalibrated: Origin={roomOrigin}, Yaw={roomYawDegrees}°");
        }

        private void OnDrawGizmosSelected()
        {
            // Visualize room axes in Unity Editor scene view
            Gizmos.color = Color.green;
            Gizmos.DrawWireSphere(roomOrigin, 0.15f);

            Vector3 podA = BackendToWorld(0f, 0f, 0.1f);
            Vector3 podB = BackendToWorld(4f, 0f, 0.1f);
            Vector3 podC = BackendToWorld(2f, 3.5f, 0.1f);

            Gizmos.color = Color.cyan;
            Gizmos.DrawLine(podA, podB);
            Gizmos.DrawLine(podB, podC);
            Gizmos.DrawLine(podC, podA);
        }
    }
}
