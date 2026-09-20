using System.Collections;
using UnityEngine;
using RFThreatDetection.Models;
using RFThreatDetection.Network;
using RFThreatDetection.Spatial;
using RFThreatDetection.Visualization;

namespace RFThreatDetection.Presentation
{
    public class SpatialThreatDashboard : MonoBehaviour
    {
        [SerializeField] private ThreatWebSocketClient webSocketClient;
        [SerializeField] private RoomCalibrationController calibrationController;
        [SerializeField] private Camera viewerCamera;
        private Transform panelRoot;
        private TextMesh title, connection, summary, details, placement, controls, modeLabel;
        private ThreatItemData selectedThreat;
        private ThreatStateData latestState;
        private float lastPacketAt = -100f;
        private float nextRefresh;
        private string calibrationStatus = "STEP 1/3  |  Aim LEFT at floor under A, then pull trigger";
        private readonly Color ink = new Color(0.04f, 0.13f, 0.18f);
        public Transform PanelRoot => panelRoot;

        private void Awake()
        {
            webSocketClient = GetComponent<ThreatWebSocketClient>() ?? FindAnyObjectByType<ThreatWebSocketClient>();
            calibrationController = GetComponent<RoomCalibrationController>() ?? FindAnyObjectByType<RoomCalibrationController>();
            viewerCamera = Camera.main;
            BuildPanel();
            panelRoot.gameObject.SetActive(false);
        }

        private IEnumerator Start()
        {
            for (int i = 0; i < 5; i++) yield return null;
            PlacePanelInFront();
            panelRoot.gameObject.SetActive(true);
        }

        private void OnEnable()
        {
            if (webSocketClient != null) webSocketClient.OnThreatStateReceived += HandleThreatState;
            if (calibrationController != null) calibrationController.OnCalibrationStatusChanged += HandleCalibrationStatus;
        }

        private void OnDisable()
        {
            if (webSocketClient != null) webSocketClient.OnThreatStateReceived -= HandleThreatState;
            if (calibrationController != null) calibrationController.OnCalibrationStatusChanged -= HandleCalibrationStatus;
        }

        private void Update()
        {
            if (Time.unscaledTime < nextRefresh) return;
            nextRefresh = Time.unscaledTime + 0.25f;
            RefreshText();
        }

        public void ShowThreat(ThreatItemData threat) { selectedThreat = threat; RefreshText(); }
        public void ClearThreat() { if (selectedThreat == null) return; selectedThreat = null; RefreshText(); }
        public bool OwnsCollider(Collider candidate) => candidate != null && panelRoot != null && candidate.transform.IsChildOf(panelRoot);

        public void HandlePointerClick(Collider candidate)
        {
            if (!OwnsCollider(candidate)) return;
            switch (candidate.name)
            {
                case "Reconnect": webSocketClient?.Reconnect(); lastPacketAt = -100f; break;
                case "Recenter": PlacePanelInFront(); break;
                case "ResetPods": calibrationController?.ResetPlacementSequence(); break;
                case "DemoMode":
                    ThreatStateData.FocusTargetOnly = !ThreatStateData.FocusTargetOnly;
                    selectedThreat = null;
                    if (latestState != null) GetComponent<ThreatVisualizationManager>()?.HandleThreatState(latestState);
                    break;
            }
            RefreshText();
        }

        public void MovePanelToRay(Ray ray, float distance)
        {
            panelRoot.position = ray.GetPoint(Mathf.Clamp(distance, 0.55f, 2f));
            FaceViewer();
        }

        public void PlacePanelInFront()
        {
            if (viewerCamera == null) viewerCamera = Camera.main;
            if (panelRoot == null || viewerCamera == null) return;
            Vector3 forward = Vector3.ProjectOnPlane(viewerCamera.transform.forward, Vector3.up).normalized;
            if (forward.sqrMagnitude < 0.1f) forward = Vector3.forward;
            panelRoot.position = viewerCamera.transform.position + forward * 0.95f - Vector3.up * 0.10f;
            FaceViewer();
        }

        private void FaceViewer()
        {
            if (viewerCamera == null) return;
            panelRoot.rotation = Quaternion.LookRotation(panelRoot.position - viewerCamera.transform.position, Vector3.up);
        }

        private void HandleThreatState(ThreatStateData state)
        {
            latestState = state;
            lastPacketAt = Time.unscaledTime;
            if (selectedThreat != null)
            {
                string id = selectedThreat.threat_id;
                selectedThreat = null;
                foreach (var item in state.GetDisplayCandidates())
                    if (item.threat_id == id) { selectedThreat = item; break; }
            }
            RefreshText();
        }

        private void HandleCalibrationStatus(string message) { calibrationStatus = message; RefreshText(); }

        private void BuildPanel()
        {
            panelRoot = new GameObject("SpatialThreatDashboard").transform;
            Quad("Panel", Vector3.zero, new Vector2(0.84f, 0.57f), new Color(0.88f, 0.94f, 0.95f), true);
            Quad("Header", new Vector3(0f, 0.22f, -0.025f), new Vector2(0.84f, 0.13f), new Color(0.025f, 0.23f, 0.29f));
            Quad("DetailCard", new Vector3(0f, 0.065f, -0.025f), new Vector2(0.78f, 0.165f), Color.white);
            Quad("PlacementCard", new Vector3(0f, -0.095f, -0.025f), new Vector2(0.78f, 0.11f), new Color(0.77f, 0.89f, 0.91f));
            title = Text("Title", -0.39f, 0.263f, Color.white);
            connection = Text("Connection", 0.24f, 0.263f, Color.white);
            summary = Text("Summary", -0.37f, 0.133f, ink);
            details = Text("Details", -0.37f, 0.088f, ink);
            placement = Text("Placement", -0.37f, -0.051f, ink);
            controls = Text("Controls", -0.39f, -0.242f, ink);
            Button("DemoMode", -0.30f, "PHONE ONLY", out modeLabel);
            Button("Reconnect", -0.10f, "RECONNECT", out _);
            Button("Recenter", 0.10f, "PANEL HERE", out _);
            Button("ResetPods", 0.30f, "RESET PODS", out _);
            RefreshText();
        }

        private GameObject Quad(string name, Vector3 position, Vector2 size, Color color, bool collider = false)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Quad);
            obj.name = name;
            obj.transform.SetParent(panelRoot, false);
            obj.transform.localPosition = position;
            obj.transform.localScale = new Vector3(size.x, size.y, 1f);
            var shader = Resources.Load<Shader>("Shaders/SolidUnlit");
            var renderer = obj.GetComponent<Renderer>();
            if (shader != null) renderer.material = new Material(shader);
            renderer.material.SetColor("_Color", color);
            renderer.sortingOrder = name == "Panel" ? 0 : (collider ? 2 : 1);
            if (!collider) DestroySafe(obj.GetComponent<Collider>());
            return obj;
        }

        private TextMesh Text(string name, float x, float y, Color color)
        {
            var obj = new GameObject(name);
            obj.transform.SetParent(panelRoot, false);
            obj.transform.localPosition = new Vector3(x, y, -0.05f);
            var text = obj.AddComponent<TextMesh>();
            text.fontSize = 64;
            text.characterSize = 0.01f;
            text.anchor = TextAnchor.UpperLeft;
            text.color = color;
            text.richText = true;
            text.GetComponent<MeshRenderer>().sortingOrder = 3;
            return text;
        }

        private void Button(string name, float x, string label, out TextMesh text)
        {
            Quad(name, new Vector3(x, -0.197f, -0.025f), new Vector2(0.18f, 0.055f), new Color(0.03f, 0.34f, 0.41f), true);
            text = Text(name + "Label", x - 0.075f, -0.180f, Color.white);
            SetText(text, label, 0.15f, 0.027f);
        }

        private static string Clean(string value, int length = 30)
        {
            string text = (value ?? "").Replace("<", "").Replace(">", "").Replace("\n", " ").Replace("\r", " ");
            return text.Length > length ? text.Substring(0, length - 3) + "..." : text;
        }

        private static void SetText(TextMesh text, string value, float width, float height)
        {
            text.text = value;
            text.transform.localScale = Vector3.one;
            Bounds bounds = text.GetComponent<MeshRenderer>().localBounds;
            float scale = Mathf.Min(width / Mathf.Max(bounds.size.x, 0.001f), height / Mathf.Max(bounds.size.y, 0.001f));
            text.transform.localScale = Vector3.one * Mathf.Min(scale, 1f);
        }

        private void RefreshText()
        {
            if (title == null) return;
            bool live = webSocketClient != null && webSocketClient.IsConnected && Time.unscaledTime - lastPacketAt < 5f;
            connection.color = live ? new Color(0.4f, 1f, 0.72f) : new Color(1f, 0.75f, 0.3f);
            SetText(title, "<b>RF / FIELD VIEW</b>\n" + (ThreatStateData.FocusTargetOnly ? "DEMO TARGET  /  AdrianPhone" : "NEARBY  /  strongest 3 sources"), 0.60f, 0.080f);
            SetText(connection, live ? "LIVE" : "NO DATA", 0.14f, 0.025f);
            var sources = live ? (latestState?.GetDemoSources() ?? new ThreatItemData[0]) : new ThreatItemData[0];
            if (!live) selectedThreat = null;
            int located = 0;
            foreach (var item in sources)
                if (item.HasEstimatedPosition() && item.observed_by_pods.Length >= 3) located++;
            if (selectedThreat == null)
            {
                SetText(summary, sources.Length == 0 ? (ThreatStateData.FocusTargetOnly ? "<b>Waiting for nearby AdrianPhone</b>" : "<b>No strong nearby signals</b>") : $"<b>{sources.Length} nearby  /  {located} localized</b>", 0.72f, 0.030f);
                string hint = sources.Length == 0 ? "Enable the phone's 2.4 GHz hotspot. Signal must reach -55 dBm." :
                    located == 0 ? "Signal found. Waiting for fresh reports from all three pods." : "Point RIGHT at a heat field to inspect. Look away to clear details.";
                SetText(details, hint + "\nBlue to green: weaker to stronger  |  Bigger: stronger\nQuest and laptop transport networks are hidden.", 0.72f, 0.089f);
            }
            else
            {
                var s = selectedThreat;
                string label = string.IsNullOrWhiteSpace(s.ssid) ? "Hidden network" : Clean(s.ssid);
                string classification = s.isBelowThreshold ? "BELOW THRESHOLD" : "FLAGGED";
                SetText(summary, $"<b>{label}</b>  /  {classification}", 0.72f, 0.030f);
                SetText(details, $"SIGNAL {s.SignalScoreDbm:F0} dBm avg    RISK {s.risk_score:F0}/100    PODS {s.observed_by_pods?.Length ?? 0}/3\n" +
                    $"CH {s.channel}   {Clean(s.authmode, 22)}   {Clean(s.bssid, 20)}\n" +
                    $"POSITION {s.GetPositionConfidence()} confidence. Location follows relative pod signal.", 0.72f, 0.089f);
            }
            SetText(placement, "<b>PLACE YOUR 2 m TRIANGLE</b>\n" + Clean(calibrationStatus, 90), 0.72f, 0.080f);
            SetText(controls, "RIGHT trigger: buttons   |   Aim + RIGHT grip: move panel   |   LEFT trigger: place pod", 0.78f, 0.025f);
            SetText(modeLabel, ThreatStateData.FocusTargetOnly ? "SHOW NEARBY" : "PHONE ONLY", 0.15f, 0.027f);
        }

        private void OnDestroy() { if (panelRoot != null) DestroySafe(panelRoot.gameObject); }
        private static void DestroySafe(Object obj)
        {
            if (obj == null) return;
            if (Application.isPlaying) Destroy(obj); else DestroyImmediate(obj);
        }
    }
}
