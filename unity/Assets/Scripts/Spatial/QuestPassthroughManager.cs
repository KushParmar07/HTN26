using UnityEngine;

namespace RFThreatDetection.Spatial
{
    /// <summary>
    /// Configures camera clear flags and manages Passthrough rendering for Meta Quest Pro.
    /// In Meta Quest OpenXR / Passthrough architecture:
    /// 1. The main camera background clear flag must be set to SolidColor.
    /// 2. The clear color must have an alpha channel of 0 (Color(0, 0, 0, 0)), allowing the
    ///    underlying Quest compositor passthrough feed to be visible behind virtual holograms.
    /// </summary>
    public class QuestPassthroughManager : MonoBehaviour
    {
        [Header("Camera Configuration")]
        [Tooltip("The VR eye camera. If null, Camera.main will be automatically detected.")]
        [SerializeField] private Camera targetCamera;

        [Header("Passthrough Settings")]
        [Tooltip("Whether Passthrough mode is enabled on start.")]
        [SerializeField] private bool passthroughOnStart = true;

        [Tooltip("Background color used when passthrough is DISABLED (e.g. Dark VR Void for Editor testing)")]
        [SerializeField] private Color voidBackgroundColor = new Color(0.05f, 0.07f, 0.12f, 1.0f);

        [Tooltip("Allow pressing the 'P' key in Editor or standalone to toggle Passthrough mode")]
        [SerializeField] private bool enableKeyboardShortcut = true;

        private bool isPassthroughActive;
        private CameraClearFlags defaultClearFlags;
        private Color defaultBgColor;

        public bool IsPassthroughActive
        {
            get { return isPassthroughActive; }
        }

        private void Awake()
        {
            if (targetCamera == null)
            {
                targetCamera = Camera.main;
            }

            if (targetCamera != null)
            {
                defaultClearFlags = targetCamera.clearFlags;
                defaultBgColor = targetCamera.backgroundColor;
            }
        }

        private void Start()
        {
            if (passthroughOnStart)
            {
                EnablePassthrough();
            }
            else
            {
                DisablePassthrough();
            }
        }

        private void Update()
        {
            if (enableKeyboardShortcut && Input.GetKeyDown(KeyCode.P))
            {
                TogglePassthrough();
            }
        }

        /// <summary>
        /// Enables Meta Quest passthrough rendering by clearing camera to transparent black (0, 0, 0, 0).
        /// </summary>
        public void EnablePassthrough()
        {
            if (targetCamera == null)
            {
                targetCamera = Camera.main;
                if (targetCamera == null) return;
            }

            targetCamera.clearFlags = CameraClearFlags.SolidColor;
            targetCamera.backgroundColor = new Color(0f, 0f, 0f, 0f);
            isPassthroughActive = true;

            Debug.Log("[QuestPassthroughManager] Passthrough ENABLED: Camera background set to RGBA(0, 0, 0, 0).");
        }

        /// <summary>
        /// Disables passthrough and reverts camera to a dark void background (useful for indoor VR simulation).
        /// </summary>
        public void DisablePassthrough()
        {
            if (targetCamera == null)
            {
                targetCamera = Camera.main;
                if (targetCamera == null) return;
            }

            targetCamera.clearFlags = CameraClearFlags.SolidColor;
            targetCamera.backgroundColor = voidBackgroundColor;
            isPassthroughActive = false;

            Debug.Log("[QuestPassthroughManager] Passthrough DISABLED: Camera background set to dark void.");
        }

        /// <summary>
        /// Toggles between passthrough mode and dark VR void mode.
        /// </summary>
        public void TogglePassthrough()
        {
            if (isPassthroughActive)
            {
                DisablePassthrough();
            }
            else
            {
                EnablePassthrough();
            }
        }
    }
}
