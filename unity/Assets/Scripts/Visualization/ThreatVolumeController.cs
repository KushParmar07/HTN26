using UnityEngine;
using RFThreatDetection.Models;

namespace RFThreatDetection.Visualization
{
    /// <summary>
    /// Displays a localized RF source as one translucent 3D orb. Orb size and
    /// blue-to-green color both represent signal strength. A stable BSSID tint
    /// makes nearby sources easier to distinguish.
    /// </summary>
    public class ThreatVolumeController : MonoBehaviour
    {
        [SerializeField] private string threatId;
        [SerializeField] private string bssid;
        [SerializeField] private string ssid;
        [SerializeField] private float positionLerpSpeed = 8f;
        [SerializeField] private float scaleLerpSpeed = 6f;
        [SerializeField] private Transform orbRoot;
        [SerializeField] private Renderer orbRenderer;
        [SerializeField] private SphereCollider interactionCollider;
        [SerializeField] private TextMesh billboardText;

        private readonly Color weakSignalColor = new Color(0.08f, 0.34f, 1f, 0.74f);
        private readonly Color strongSignalColor = new Color(0.06f, 0.92f, 0.50f, 0.74f);
        private Vector3 targetPosition;
        private float targetDiameter = 0.65f;
        private Color currentColor = Color.blue;
        private ThreatItemData latestData;
        private bool isFocused;
        private bool isSelected;

        public string ThreatId => threatId;
        public string Bssid => bssid;
        public ThreatItemData LatestData => latestData;
        public float TargetDiameter => targetDiameter;
        public Vector3 TargetPosition => targetPosition;

        private void Awake()
        {
            targetPosition = transform.position;
            EnsureVisualComponents();
        }

        public void UpdateThreatData(ThreatItemData data, Vector3 worldPosition)
        {
            EnsureVisualComponents();
            threatId = data.threat_id;
            bssid = data.bssid;
            ssid = data.ssid;
            latestData = data;
            targetPosition = worldPosition;
            // Size and cold-scale color both communicate signal strength.
            float signalT = Mathf.InverseLerp(-82f, -30f, data.SignalScoreDbm);
            targetDiameter = Mathf.Lerp(0.34f, 0.92f, signalT);
            currentColor = Color.Lerp(weakSignalColor, strongSignalColor, signalT);
            float identityOffset = StableTintOffset(data.bssid);
            currentColor.g = Mathf.Clamp01(currentColor.g + identityOffset);
            currentColor.b = Mathf.Clamp01(currentColor.b - identityOffset * 0.65f);
            RefreshVisualState();
            UpdateBillboardText(data);
        }

        public void SetFocused(bool focused)
        {
            isFocused = focused;
            if (billboardText != null) billboardText.gameObject.SetActive(focused);
            RefreshVisualState();
        }

        public void SetSelected(bool selected)
        {
            isSelected = selected;
            RefreshVisualState();
            if (latestData != null) UpdateBillboardText(latestData);
        }

        private void Update()
        {
            transform.position = Vector3.Lerp(
                transform.position, targetPosition, Time.deltaTime * positionLerpSpeed);
            if (orbRoot != null)
            {
                float pulse = 1f + Mathf.Sin(Time.time * 2f) * 0.008f;
                Vector3 targetScale = Vector3.one * targetDiameter * pulse;
                orbRoot.localScale = Vector3.Lerp(
                    orbRoot.localScale, targetScale, Time.deltaTime * scaleLerpSpeed);
            }
            if (interactionCollider != null)
                interactionCollider.radius = Mathf.Max(0.25f, targetDiameter * 0.52f);
            if (billboardText != null)
                billboardText.transform.localPosition = new Vector3(
                    0f, targetDiameter * 0.58f + 0.12f, 0f);
            OrientBillboardToCamera();
        }

        private void RefreshVisualState()
        {
            if (orbRenderer == null) return;
            Color visual = currentColor;
            if (isSelected)
                visual = Color.Lerp(visual, Color.white, 0.28f);
            else if (isFocused)
                visual = Color.Lerp(visual, new Color(1f, 0.9f, 0.25f, 1f), 0.22f);
            visual.a = isSelected || isFocused ? 0.86f : 0.74f;
            if (orbRenderer.material.HasProperty("_Color"))
                orbRenderer.material.SetColor("_Color", visual);
        }

        private static float StableTintOffset(string identity)
        {
            unchecked
            {
                int hash = 17;
                foreach (char character in identity ?? string.Empty)
                    hash = hash * 31 + character;
                return (((hash & 255) / 255f) - 0.5f) * 0.12f;
            }
        }

        private void EnsureVisualComponents()
        {
            Shader solidShader = Resources.Load<Shader>("Shaders/SolidUnlit");
            if (solidShader == null) solidShader = Shader.Find("RFThreat/SolidUnlit");
            if (orbRoot == null)
            {
                GameObject orb = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                orb.name = "ThreatOrb";
                orb.transform.SetParent(transform, false);
                orbRoot = orb.transform;
                orbRenderer = orb.GetComponent<Renderer>();
                if (solidShader != null) orbRenderer.material = new Material(solidShader);
                SafeDestroy(orb.GetComponent<Collider>());
            }
            if (interactionCollider == null)
            {
                interactionCollider = GetComponent<SphereCollider>();
                if (interactionCollider == null)
                    interactionCollider = gameObject.AddComponent<SphereCollider>();
                interactionCollider.isTrigger = true;
                interactionCollider.radius = 0.35f;
            }
            if (billboardText == null)
            {
                GameObject label = new GameObject("ThreatLabel");
                label.transform.SetParent(transform, false);
                billboardText = label.AddComponent<TextMesh>();
                billboardText.fontSize = 32;
                billboardText.characterSize = 0.019f;
                billboardText.anchor = TextAnchor.MiddleCenter;
                billboardText.alignment = TextAlignment.Center;
                billboardText.color = Color.white;
                billboardText.richText = true;
                billboardText.gameObject.SetActive(false);
            }
            RefreshVisualState();
        }

        private void OrientBillboardToCamera()
        {
            Camera mainCamera = Camera.main;
            if (mainCamera == null || billboardText == null) return;
            billboardText.transform.LookAt(
                billboardText.transform.position + mainCamera.transform.rotation * Vector3.forward,
                mainCamera.transform.rotation * Vector3.up);
        }

        private void UpdateBillboardText(ThreatItemData data)
        {
            if (billboardText == null) return;
            billboardText.gameObject.SetActive(isFocused);
            string safeSsid = (data.ssid ?? "Hidden network")
                .Replace("<", "").Replace(">", "").Replace("\n", " ");
            if (safeSsid.Length > 28) safeSsid = safeSsid.Substring(0, 25) + "...";
            string selectedMarker = isSelected ? "  [SELECTED]" : string.Empty;
            string labelColor = data.SignalScoreDbm >= -55f ? "#68F0A6" : "#77D9FF";
            billboardText.text = $"<b><color={labelColor}>{safeSsid}</color></b>{selectedMarker}\n" +
                                 $"SIGNAL {data.SignalScoreDbm:F0} dBm   POSITION {data.GetPositionConfidence()}";
        }

        private static void SafeDestroy(Object obj)
        {
            if (obj == null) return;
            if (Application.isPlaying) Destroy(obj);
            else DestroyImmediate(obj);
        }
    }
}
