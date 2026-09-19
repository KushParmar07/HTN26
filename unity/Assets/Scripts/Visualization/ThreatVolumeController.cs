using UnityEngine;
using RFThreatDetection.Models;

namespace RFThreatDetection.Visualization
{
    /// <summary>
    /// Controls the spatial 3D visualization of a single active threat volume in Meta Quest space.
    /// Manages smooth spatial interpolation, volumetric uncertainty scaling, risk-based visual state,
    /// and world-space HUD billboard orientation.
    /// </summary>
    public class ThreatVolumeController : MonoBehaviour
    {
        [Header("Identity")]
        [SerializeField] private string threatId;
        [SerializeField] private string bssid;
        [SerializeField] private string ssid;

        [Header("Motion & Smoothing")]
        [Tooltip("Interpolation speed for smooth spatial movement")]
        [SerializeField] private float positionLerpSpeed = 8.0f;
        [SerializeField] private float scaleLerpSpeed = 5.0f;

        [Header("Visual Components (Assigned or Procedural)")]
        [SerializeField] private Transform volumeOuterSphere;
        [SerializeField] private Transform innerCore;
        [SerializeField] private TextMesh billboardText;

        [Header("Color Tuning")]
        [SerializeField] private Color lowRiskColor = new Color(1.0f, 0.7f, 0.0f, 0.35f);   // Warning Amber
        [SerializeField] private Color highRiskColor = new Color(1.0f, 0.1f, 0.1f, 0.55f);  // Critical Red

        private Vector3 targetPosition;
        private Vector3 targetScale = Vector3.one;
        private Color currentColor;
        private Renderer outerRenderer;
        private Renderer coreRenderer;
        private float currentRiskScore = 0f;

        public string ThreatId => threatId;
        public string Bssid => bssid;

        private void Awake()
        {
            targetPosition = transform.position;
            EnsureVisualComponents();
        }

        /// <summary>
        /// Update the threat volume with latest data from the backend.
        /// </summary>
        public void UpdateThreatData(ThreatItemData data, Vector3 worldPosition)
        {
            this.threatId = data.threat_id;
            this.bssid = data.bssid;
            this.ssid = data.ssid;
            this.currentRiskScore = data.risk_score;
            this.targetPosition = worldPosition;

            // Uncertainty radius in meters determines the volumetric diameter
            float radius = data.uncertainty_radius_m > 0.05f ? data.uncertainty_radius_m : 0.5f;
            float diameter = radius * 2.0f;
            this.targetScale = new Vector3(diameter, diameter, diameter);

            // Compute color based on normalized risk (40..100)
            float t = Mathf.Clamp01((data.risk_score - 40.0f) / 60.0f);
            this.currentColor = Color.Lerp(lowRiskColor, highRiskColor, t);

            UpdateMaterialColors(currentColor);
            UpdateBillboardText(data);
        }

        private void Update()
        {
            // Smoothly glide position towards target
            transform.position = Vector3.Lerp(transform.position, targetPosition, Time.deltaTime * positionLerpSpeed);

            // Smoothly scale outer volume
            if (volumeOuterSphere != null)
            {
                volumeOuterSphere.localScale = Vector3.Lerp(volumeOuterSphere.localScale, targetScale, Time.deltaTime * scaleLerpSpeed);
            }

            // Pulse the inner core slightly
            if (innerCore != null)
            {
                float pulse = 1.0f + Mathf.Sin(Time.time * 4.0f) * 0.12f;
                innerCore.localScale = new Vector3(0.2f * pulse, 0.2f * pulse, 0.2f * pulse);
            }

            // Orient billboard HUD towards the active VR camera
            OrientBillboardToCamera();
        }

        private void OrientBillboardToCamera()
        {
            Camera mainCam = Camera.main;
            if (mainCam != null && billboardText != null)
            {
                billboardText.transform.LookAt(billboardText.transform.position + mainCam.transform.rotation * Vector3.forward,
                                              mainCam.transform.rotation * Vector3.up);
            }
        }

        private void UpdateBillboardText(ThreatItemData data)
        {
            if (billboardText == null) return;

            string flags = data.GetFormattedEvidenceFlags();
            billboardText.text = $"<b><color=red>[THREAT DETECTED]</color></b>\n" +
                                 $"<b>SSID:</b> {data.ssid}\n" +
                                 $"<b>BSSID:</b> {data.bssid}\n" +
                                 $"<b>Risk:</b> {data.risk_score:F0}%\n" +
                                 $"<b>Flags:</b> {flags}\n" +
                                 $"<b>Uncertainty:</b> ±{data.uncertainty_radius_m:F2}m";
        }

        private void UpdateMaterialColors(Color color)
        {
            if (outerRenderer != null)
            {
                outerRenderer.material.color = color;
            }
            if (coreRenderer != null)
            {
                Color solid = color;
                solid.a = 1.0f;
                coreRenderer.material.color = solid;
            }
        }

        private void SetMaterialTransparent(Material mat)
        {
            if (mat == null) return;
            mat.SetFloat("_Mode", 3); // 3 = Transparent in Unity Standard Shader
            mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            mat.SetInt("_ZWrite", 0);
            mat.DisableKeyword("_ALPHATEST_ON");
            mat.EnableKeyword("_ALPHABLEND_ON");
            mat.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            mat.renderQueue = 3000;
        }

        /// <summary>
        /// Create procedural visual primitives if prefabs were not pre-configured.
        /// </summary>
        private void EnsureVisualComponents()
        {
            if (volumeOuterSphere == null)
            {
                GameObject outer = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                outer.name = "VolumeCloud";
                outer.transform.SetParent(this.transform, false);
                outer.transform.localPosition = Vector3.zero;
                Collider col = outer.GetComponent<Collider>();
                if (col != null) Destroy(col);

                outerRenderer = outer.GetComponent<Renderer>();
                if (outerRenderer != null)
                {
                    Material mat = new Material(Shader.Find("Standard"));
                    SetMaterialTransparent(mat);
                    outerRenderer.material = mat;
                }
                volumeOuterSphere = outer.transform;
            }
            else
            {
                outerRenderer = volumeOuterSphere.GetComponent<Renderer>();
                if (outerRenderer != null)
                {
                    SetMaterialTransparent(outerRenderer.material);
                }
            }

            if (innerCore == null)
            {
                GameObject core = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                core.name = "ThreatCore";
                core.transform.SetParent(this.transform, false);
                core.transform.localPosition = Vector3.zero;
                core.transform.localScale = new Vector3(0.2f, 0.2f, 0.2f);
                Collider col = core.GetComponent<Collider>();
                if (col != null) Destroy(col);

                coreRenderer = core.GetComponent<Renderer>();
                innerCore = core.transform;
            }
            else
            {
                coreRenderer = innerCore.GetComponent<Renderer>();
            }

            if (billboardText == null)
            {
                GameObject textObj = new GameObject("ThreatHUD");
                textObj.transform.SetParent(this.transform, false);
                textObj.transform.localPosition = new Vector3(0f, 0.65f, 0f);

                billboardText = textObj.AddComponent<TextMesh>();
                billboardText.fontSize = 24;
                billboardText.characterSize = 0.035f;
                billboardText.anchor = TextAnchor.LowerCenter;
                billboardText.alignment = TextAlignment.Center;
                billboardText.color = Color.white;
            }
        }
    }
}
