using UnityEngine;
using RFThreatDetection.Models;
using RFThreatDetection.Network;
using RFThreatDetection.Spatial;

namespace RFThreatDetection.Presentation
{
    /// <summary>
    /// A world-space dashboard designed for mixed reality. It follows the viewer
    /// gently instead of being rigidly head-locked and displays live connection,
    /// localization, and evidence information inside the headset.
    /// </summary>
    public class SpatialThreatDashboard : MonoBehaviour
    {
        [SerializeField] private ThreatWebSocketClient webSocketClient;
        [SerializeField] private RoomCalibrationController calibrationController;
        [SerializeField] private Camera viewerCamera;
        [SerializeField] private float distanceMeters = 1.15f;
        [SerializeField] private float verticalOffsetMeters = -0.22f;

        private Transform panelRoot;
        private TextMesh statusText;
        private TextMesh detailText;
        private ThreatItemData selectedThreat;
        private int activeThreatCount;
        private bool connected;
        private string calibrationStatus = "Press B/Y (or C) to align Pod A";

        private void Awake()
        {
            if (webSocketClient == null)
                webSocketClient = GetComponent<ThreatWebSocketClient>() ?? FindAnyObjectByType<ThreatWebSocketClient>();
            if (calibrationController == null)
                calibrationController = GetComponent<RoomCalibrationController>() ?? FindAnyObjectByType<RoomCalibrationController>();
            if (viewerCamera == null) viewerCamera = Camera.main;
            BuildPanel();
            RefreshText();
        }

        private void OnEnable()
        {
            if (webSocketClient != null)
            {
                webSocketClient.OnConnectionStatusChanged += HandleConnectionChanged;
                webSocketClient.OnThreatStateReceived += HandleThreatState;
                connected = webSocketClient.IsConnected;
            }
            if (calibrationController != null)
                calibrationController.OnCalibrationStatusChanged += HandleCalibrationStatus;
        }

        private void OnDisable()
        {
            if (webSocketClient != null)
            {
                webSocketClient.OnConnectionStatusChanged -= HandleConnectionChanged;
                webSocketClient.OnThreatStateReceived -= HandleThreatState;
            }
            if (calibrationController != null)
                calibrationController.OnCalibrationStatusChanged -= HandleCalibrationStatus;
        }

        public void ShowThreat(ThreatItemData threat)
        {
            selectedThreat = threat;
            RefreshText();
        }

        private void HandleConnectionChanged(bool value)
        {
            connected = value;
            RefreshText();
        }

        private void HandleThreatState(ThreatStateData state)
        {
            ThreatItemData[] threats = state?.GetActiveThreats();
            activeThreatCount = threats?.Length ?? 0;

            if (selectedThreat != null && threats != null)
            {
                foreach (ThreatItemData threat in threats)
                {
                    if (threat.threat_id == selectedThreat.threat_id)
                    {
                        selectedThreat = threat;
                        RefreshText();
                        return;
                    }
                }
                selectedThreat = null;
            }

            if (selectedThreat == null && activeThreatCount > 0)
                selectedThreat = threats[0];
            RefreshText();
        }

        private void HandleCalibrationStatus(string message)
        {
            calibrationStatus = message;
            RefreshText();
        }

        private void BuildPanel()
        {
            GameObject root = new GameObject("SpatialThreatDashboard");
            Transform anchor = viewerCamera != null ? viewerCamera.transform : transform;
            root.transform.SetParent(anchor, false);
            panelRoot = root.transform;
            panelRoot.localPosition = new Vector3(0f, verticalOffsetMeters, distanceMeters);
            panelRoot.localRotation = Quaternion.identity;

            GameObject background = GameObject.CreatePrimitive(PrimitiveType.Quad);
            background.name = "DashboardBackground";
            background.transform.SetParent(panelRoot, false);
            background.transform.localScale = new Vector3(0.72f, 0.42f, 1f);
            Destroy(background.GetComponent<Collider>());
            Renderer renderer = background.GetComponent<Renderer>();
            Shader shader = Shader.Find("Unlit/Color") ?? Shader.Find("Sprites/Default");
            renderer.material = new Material(shader);
            renderer.material.color = new Color(0.015f, 0.03f, 0.05f, 0.92f);

            statusText = CreateText("Status", new Vector3(-0.33f, 0.18f, -0.012f), 0.008f, 42);
            detailText = CreateText("Details", new Vector3(-0.33f, 0.095f, -0.012f), 0.007f, 38);
        }

        private TextMesh CreateText(string objectName, Vector3 localPosition, float characterSize, int fontSize)
        {
            GameObject textObject = new GameObject(objectName);
            textObject.transform.SetParent(panelRoot, false);
            textObject.transform.localPosition = localPosition;
            TextMesh text = textObject.AddComponent<TextMesh>();
            text.anchor = TextAnchor.UpperLeft;
            text.alignment = TextAlignment.Left;
            text.fontSize = fontSize;
            text.characterSize = characterSize;
            text.richText = true;
            text.color = Color.white;
            return text;
        }

        private void RefreshText()
        {
            if (statusText == null || detailText == null) return;
            string connectionColor = connected ? "#45F29A" : "#FFB347";
            statusText.text = $"<b>RF SPATIAL DEFENSE</b>   <color={connectionColor}>{(connected ? "LIVE" : "OFFLINE")}</color>\n" +
                              $"Threats: {activeThreatCount}   {calibrationStatus}";

            if (selectedThreat == null)
            {
                detailText.text = "<color=#8FA9B8>Scanning the room...\nLook at a threat cloud to inspect it.</color>";
                return;
            }

            string evidence = selectedThreat.GetFormattedEvidenceFlags().Replace(", ", "  |  ");
            detailText.text = $"<color=#FF5A55><b>{selectedThreat.ssid}</b>   RISK {selectedThreat.risk_score:F0}</color>\n" +
                              $"{selectedThreat.bssid}   CH {selectedThreat.channel}   {selectedThreat.authmode}\n" +
                              $"Observed by: {string.Join(", ", selectedThreat.observed_by_pods ?? new string[0])}\n" +
                              $"Uncertainty: +/- {selectedThreat.uncertainty_radius_m:F2} m\n" +
                              $"<color=#FFB347>{evidence}</color>";
        }
    }
}
