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

        [Header("Display Stability")]
        [SerializeField, Min(0.5f)] private float absenceGraceSeconds = 2f;
        [SerializeField, Min(0f)] private float replacementMarginDb = 5f;

        private const int MaxVisibleSources = 3;

        private readonly Dictionary<string, ThreatVolumeController> activeThreats =
            new Dictionary<string, ThreatVolumeController>();

        private readonly Dictionary<string, float> lastSourceSeenAt =
            new Dictionary<string, float>();

        private float lastStateAt;

        private void Update()
        {
            ExpireMissingSources();
            if (activeThreats.Count > 0 && Time.unscaledTime - lastStateAt > 12f)
                ClearAllThreats();
        }

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
            lastStateAt = Time.unscaledTime;
            EnsureDependencies();

            // 1. Update physical sensor nodes (Pods A, B, C)
            if (sensorVisualizer != null && state.sensor_nodes != null)
            {
                sensorVisualizer.UpdateSensorNodes(state.sensor_nodes);
            }

            // Presence and localization are intentionally separate. Partial pod
            // cycles keep the source alive without moving it to a bogus origin.
            foreach (var source in state.GetPresentSources())
            {
                if (string.IsNullOrEmpty(source.threat_id)) continue;
                if (source.observed_by_pods == null || source.observed_by_pods.Length == 0) continue;
                lastSourceSeenAt[source.threat_id] = Time.unscaledTime;
            }

            // Only a complete three-pod solution can create or reposition an orb.
            ThreatItemData[] incomingThreats = state.GetDisplayCandidates();

            foreach (var threatData in incomingThreats)
            {
                if (string.IsNullOrEmpty(threatData.threat_id)) continue;
                if (!threatData.HasStableLocalization()) continue;
                lastSourceSeenAt[threatData.threat_id] = Time.unscaledTime;
            }

            ExpireMissingSources();

            // Refresh already-selected sources first so brief ranking changes do not
            // make them blink or jump between identities.
            foreach (var threatData in incomingThreats)
            {
                if (activeThreats.ContainsKey(threatData.threat_id))
                    UpdateVisibleSource(threatData);
            }

            // Fill empty slots using the strongest currently reported sources.
            foreach (var threatData in incomingThreats)
            {
                if (activeThreats.Count >= MaxVisibleSources) break;
                if (!activeThreats.ContainsKey(threatData.threat_id))
                    UpdateVisibleSource(threatData);
            }

            // Only replace a visible source when a newcomer is at least 5 dB stronger.
            // This hysteresis keeps the display stable around close RSSI rankings.
            foreach (var threatData in incomingThreats)
            {
                if (activeThreats.ContainsKey(threatData.threat_id)) continue;
                string weakestId = FindWeakestVisibleSource();
                if (string.IsNullOrEmpty(weakestId)) break;
                float weakestDbm = activeThreats[weakestId].LatestData?.SignalScoreDbm ?? -127f;
                if (threatData.SignalScoreDbm < weakestDbm + replacementMarginDb) break;
                RemoveVisibleSource(weakestId, "replaced by stronger source");
                UpdateVisibleSource(threatData);
            }
        }

        private void UpdateVisibleSource(ThreatItemData threatData)
        {
            Vector3 worldPos = transformer != null
                ? transformer.BackendToWorld(threatData.estimated_position_2d.x, threatData.estimated_position_2d.y, 0.62f)
                : new Vector3(threatData.estimated_position_2d.x, 0.62f, threatData.estimated_position_2d.y);

            if (!activeThreats.TryGetValue(threatData.threat_id, out ThreatVolumeController controller))
            {
                controller = SpawnThreatVolume(threatData, worldPos);
                activeThreats[threatData.threat_id] = controller;
                Debug.Log($"[ThreatVisualizationManager] Spawned source: {threatData.threat_id} (SSID={threatData.ssid}, RSSI={threatData.SignalScoreDbm:F0} dBm average)");
            }
            controller.UpdateThreatData(threatData, worldPos);
        }

        private string FindWeakestVisibleSource()
        {
            string weakestId = null;
            float weakestDbm = float.PositiveInfinity;
            foreach (var kvp in activeThreats)
            {
                float dbm = kvp.Value != null && kvp.Value.LatestData != null
                    ? kvp.Value.LatestData.SignalScoreDbm : -127f;
                if (dbm < weakestDbm)
                {
                    weakestDbm = dbm;
                    weakestId = kvp.Key;
                }
            }
            return weakestId;
        }

        private void ExpireMissingSources()
        {
            float now = Time.unscaledTime;
            var stale = new List<string>();
            foreach (var kvp in activeThreats)
            {
                if (!lastSourceSeenAt.TryGetValue(kvp.Key, out float seenAt) ||
                    now - seenAt > absenceGraceSeconds)
                    stale.Add(kvp.Key);
            }
            foreach (string id in stale)
                RemoveVisibleSource(id, "not reported during hold window");
        }

        private void RemoveVisibleSource(string id, string reason)
        {
            if (!activeThreats.TryGetValue(id, out ThreatVolumeController controller)) return;
            activeThreats.Remove(id);
            Debug.Log($"[ThreatVisualizationManager] Source removed: {id} ({reason})");
            if (controller != null) Destroy(controller.gameObject);
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
            lastSourceSeenAt.Clear();
        }
    }
}
