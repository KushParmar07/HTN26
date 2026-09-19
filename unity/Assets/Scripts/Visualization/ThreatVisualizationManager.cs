using System.Collections.Generic;
using UnityEngine;
using RFThreatDetection.Models;
using RFThreatDetection.Network;
using RFThreatDetection.Spatial;

namespace RFThreatDetection.Visualization
{
    /// <summary>
    /// Coordinates spatial 3D threat visualization in Meta Quest space.
    /// Manages threat volume lifecycles (creation, continuous movement, disappearance)
    /// keyed by stable threat_id.
    /// </summary>
    public class ThreatVisualizationManager : MonoBehaviour
    {
        [Header("Components")]
        [SerializeField] private ThreatWebSocketClient webSocketClient;
        [SerializeField] private RoomCoordinateTransformer transformer;
        [SerializeField] private SensorNodeVisualizer sensorVisualizer;

        [Header("Prefabs & Templates (Optional)")]
        [Tooltip("Optional custom prefab containing ThreatVolumeController. If null, procedural visuals are created.")]
        [SerializeField] private GameObject threatVolumePrefab;

        private readonly Dictionary<string, ThreatVolumeController> activeThreats =
            new Dictionary<string, ThreatVolumeController>();

        private readonly HashSet<string> currentFrameThreatIds = new HashSet<string>();

        private void Awake()
        {
            EnsureDependencies();
        }

        public void EnsureDependencies()
        {
            if (webSocketClient == null)
            {
                webSocketClient = GetComponent<ThreatWebSocketClient>() ?? FindAnyObjectByType<ThreatWebSocketClient>();
            }
            if (transformer == null)
            {
                transformer = GetComponent<RoomCoordinateTransformer>() ?? FindAnyObjectByType<RoomCoordinateTransformer>();
            }
            if (sensorVisualizer == null)
            {
                sensorVisualizer = GetComponent<SensorNodeVisualizer>() ?? FindAnyObjectByType<SensorNodeVisualizer>();
            }
        }

        private void OnEnable()
        {
            EnsureDependencies();
            if (webSocketClient != null)
            {
                webSocketClient.OnThreatStateReceived += HandleThreatState;
            }
        }

        private void OnDisable()
        {
            if (webSocketClient != null)
            {
                webSocketClient.OnThreatStateReceived -= HandleThreatState;
            }
        }

        /// <summary>
        /// Process incoming threat state packet from WebSocket stream.
        /// </summary>
        public void HandleThreatState(ThreatStateData state)
        {
            if (state == null) return;
            EnsureDependencies();

            // 1. Update physical sensor nodes (Pods A, B, C)
            if (sensorVisualizer != null && state.sensor_nodes != null)
            {
                sensorVisualizer.UpdateSensorNodes(state.sensor_nodes);
            }

            // 2. Track incoming active threats
            currentFrameThreatIds.Clear();
            ThreatItemData[] incomingThreats = state.GetActiveThreats();

            foreach (var threatData in incomingThreats)
            {
                if (string.IsNullOrEmpty(threatData.threat_id)) continue;
                if (!threatData.HasEstimatedPosition()) continue;

                string id = threatData.threat_id;
                currentFrameThreatIds.Add(id);

                // Transform 2D backend position into 3D Quest world coordinates
                Vector3 worldPos = transformer != null
                    ? transformer.BackendToWorld(threatData.estimated_position_2d.x, threatData.estimated_position_2d.y)
                    : new Vector3(threatData.estimated_position_2d.x, 1.0f, threatData.estimated_position_2d.y);

                // Create or update threat volume
                if (!activeThreats.TryGetValue(id, out ThreatVolumeController controller))
                {
                    controller = SpawnThreatVolume(threatData, worldPos);
                    activeThreats[id] = controller;
                    Debug.Log($"[ThreatVisualizationManager] Spawned new threat volume: {id} (SSID={threatData.ssid}, Risk={threatData.risk_score:F0}%)");
                }

                // Update continuous spatial position, uncertainty volume, and risk state
                controller.UpdateThreatData(threatData, worldPos);
            }

            // 3. Remove/deactivate threats that are no longer active
            List<string> threatsToRemove = new List<string>();
            foreach (var kvp in activeThreats)
            {
                if (!currentFrameThreatIds.Contains(kvp.Key))
                {
                    threatsToRemove.Add(kvp.Key);
                }
            }

            foreach (string staleId in threatsToRemove)
            {
                ThreatVolumeController controller = activeThreats[staleId];
                activeThreats.Remove(staleId);

                Debug.Log($"[ThreatVisualizationManager] Threat cleared/disappeared: {staleId}");
                if (controller != null)
                {
                    Destroy(controller.gameObject);
                }
            }
        }

        private ThreatVolumeController SpawnThreatVolume(ThreatItemData data, Vector3 initialWorldPos)
        {
            GameObject obj;
            if (threatVolumePrefab != null)
            {
                obj = Instantiate(threatVolumePrefab, initialWorldPos, Quaternion.identity, this.transform);
            }
            else
            {
                obj = new GameObject($"ThreatVolume_{data.threat_id}");
                obj.transform.SetParent(this.transform, false);
                obj.transform.position = initialWorldPos;
            }

            ThreatVolumeController controller = obj.GetComponent<ThreatVolumeController>();
            if (controller == null)
            {
                controller = obj.AddComponent<ThreatVolumeController>();
            }

            return controller;
        }

        /// <summary>
        /// Clear all active threat visuals (e.g. upon disconnect or reset).
        /// </summary>
        public void ClearAllThreats()
        {
            foreach (var kvp in activeThreats)
            {
                if (kvp.Value != null)
                {
                    Destroy(kvp.Value.gameObject);
                }
            }
            activeThreats.Clear();
            currentFrameThreatIds.Clear();
        }
    }
}
