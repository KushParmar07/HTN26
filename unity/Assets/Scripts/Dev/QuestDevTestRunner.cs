using UnityEngine;
using RFThreatDetection.Models;
using RFThreatDetection.Network;
using RFThreatDetection.Visualization;

namespace RFThreatDetection.Dev
{
    /// <summary>
    /// Development and debugging controller for testing the Meta Quest client in Unity Editor
    /// or standalone without physical ESP32 sensors or Quest Pro hardware.
    /// Provides connection HUD, stats overlay, and simulated offline fallback streaming.
    /// </summary>
    public class QuestDevTestRunner : MonoBehaviour
    {
        [Header("Components")]
        [SerializeField] private ThreatWebSocketClient webSocketClient;
        [SerializeField] private ThreatVisualizationManager visualizationManager;

        [Header("Debugging GUI")]
        [SerializeField] private bool showDebugOverlay = true;

        [Header("Offline Local Simulation")]
        [Tooltip("If true, feeds synthetic local threat frames when offline")]
        [SerializeField] private bool runOfflineSimulation = false;
        [SerializeField] private float offlineSimulationSpeed = 1.0f;

        private ThreatStateData latestState;
        private bool isConnected = false;
        private float offlineProgress = 0f;

        private void Awake()
        {
            if (webSocketClient == null) webSocketClient = FindObjectOfType<ThreatWebSocketClient>();
            if (visualizationManager == null) visualizationManager = FindObjectOfType<ThreatVisualizationManager>();
        }

        private void OnEnable()
        {
            if (webSocketClient != null)
            {
                webSocketClient.OnThreatStateReceived += OnThreatStateReceived;
                webSocketClient.OnConnectionStatusChanged += OnConnectionStatusChanged;
            }
        }

        private void OnDisable()
        {
            if (webSocketClient != null)
            {
                webSocketClient.OnThreatStateReceived -= OnThreatStateReceived;
                webSocketClient.OnConnectionStatusChanged -= OnConnectionStatusChanged;
            }
        }

        private void OnThreatStateReceived(ThreatStateData state)
        {
            latestState = state;
        }

        private void OnConnectionStatusChanged(bool connected)
        {
            isConnected = connected;
        }

        private void Update()
        {
            if (runOfflineSimulation && (!isConnected || webSocketClient == null))
            {
                UpdateOfflineSimulation();
            }
        }

        private void UpdateOfflineSimulation()
        {
            offlineProgress += Time.deltaTime * 0.15f * offlineSimulationSpeed;
            if (offlineProgress > 1.0f) offlineProgress -= 1.0f;

            float t = (Mathf.Sin(offlineProgress * Mathf.PI * 2f - Mathf.PI / 2f) + 1f) / 2f;
            float posX = Mathf.Lerp(0.5f, 3.5f, t);
            float posY = Mathf.Lerp(0.5f, 2.5f, t);

            ThreatStateData mockState = new ThreatStateData
            {
                version = "1.0",
                generated_at_ms = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                sensor_nodes = new SensorNodeData[]
                {
                    new SensorNodeData("pod_a", 0.0f, 0.0f),
                    new SensorNodeData("pod_b", 4.0f, 0.0f),
                    new SensorNodeData("pod_c", 2.0f, 3.5f)
                },
                threats = new ThreatItemData[]
                {
                    new ThreatItemData
                    {
                        threat_id = "threat_deadbeef0001",
                        bssid = "DE:AD:BE:EF:00:01",
                        ssid = "HTN-Secure",
                        status = "SUSPICIOUS_INFRASTRUCTURE",
                        risk_score = 100.0f,
                        evidence_flags = new string[] { "UNKNOWN_BSSID", "SECURITY_MISMATCH", "UNEXPECTED_CHANNEL" },
                        estimated_position_2d = new Position2DData(posX, posY),
                        uncertainty_radius_m = 0.45f,
                        channel = 1,
                        authmode = "OPEN",
                        first_seen_ms = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - 5000,
                        last_seen_ms = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                        observed_by_pods = new string[] { "pod_a", "pod_b", "pod_c" }
                    }
                }
            };

            latestState = mockState;
            visualizationManager?.HandleThreatState(mockState);
        }

        private void OnGUI()
        {
            if (!showDebugOverlay) return;

            GUILayout.BeginArea(new Rect(15, 15, 340, 240), GUI.skin.box);
            GUILayout.Label("<b><size=14>RF Threat Detection - VR HUD</size></b>");

            string statusColor = isConnected ? "green" : (runOfflineSimulation ? "yellow" : "red");
            string statusText = isConnected ? "CONNECTED TO BACKEND" : (runOfflineSimulation ? "OFFLINE (SIMULATION MODE)" : "DISCONNECTED");
            GUILayout.Label($"WebSocket: <color={statusColor}><b>{statusText}</b></color>");
            GUILayout.Label($"Target: {webSocketClient?.ServerUri ?? "N/A"}");

            int threatCount = latestState != null ? latestState.GetActiveThreats().Length : 0;
            GUILayout.Label($"Active Threats: <b>{threatCount}</b>");

            if (latestState != null && threatCount > 0)
            {
                var threat = latestState.GetActiveThreats()[0];
                GUILayout.Label($"SSID: {threat.ssid} (Risk: {threat.risk_score:F0}%)");
                if (threat.estimated_position_2d != null)
                {
                    GUILayout.Label($"Est 2D Pos: ({threat.estimated_position_2d.x:F2}m, {threat.estimated_position_2d.y:F2}m)");
                }
                GUILayout.Label($"Uncertainty: ±{threat.uncertainty_radius_m:F2}m");
            }

            GUILayout.Space(5);
            GUILayout.BeginHorizontal();
            if (GUILayout.Button(isConnected ? "Disconnect" : "Connect"))
            {
                if (isConnected) webSocketClient?.Disconnect();
                else webSocketClient?.Connect();
            }
            if (GUILayout.Button(runOfflineSimulation ? "Disable Mock" : "Enable Mock"))
            {
                runOfflineSimulation = !runOfflineSimulation;
                if (!runOfflineSimulation) visualizationManager?.ClearAllThreats();
            }
            GUILayout.EndHorizontal();

            GUILayout.EndArea();
        }
    }
}
