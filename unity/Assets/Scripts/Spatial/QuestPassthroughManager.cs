using System;
using System.Reflection;
using UnityEngine;
using UnityEngine.InputSystem;

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
        private Behaviour metaPassthroughLayer;
        private Behaviour metaOvrManager;

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
            if (enableKeyboardShortcut && Keyboard.current != null && Keyboard.current.pKey.wasPressedThisFrame)
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
            TrySetMetaPassthrough(true);
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
            TrySetMetaPassthrough(false);
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

        private void TrySetMetaPassthrough(bool enabled)
        {
            Type managerType = FindType("OVRManager");
            Type layerType = FindType("OVRPassthroughLayer");

            if (managerType == null || layerType == null)
            {
                if (enabled)
                    Debug.LogWarning("[QuestPassthroughManager] Camera is transparent, but Meta XR Core SDK is not installed. Install it to render physical-room passthrough on Quest.");
                return;
            }

            PropertyInfo passthroughProperty = managerType.GetProperty(
                "isInsightPassthroughEnabled",
                BindingFlags.Public | BindingFlags.Static);
            passthroughProperty?.SetValue(null, enabled);

            EnsureMetaOvrManager(managerType, enabled);

            if (metaPassthroughLayer == null)
            {
                metaPassthroughLayer = GetComponent(layerType) as Behaviour;
                if (metaPassthroughLayer == null)
                    metaPassthroughLayer = gameObject.AddComponent(layerType) as Behaviour;
            }

            if (metaPassthroughLayer != null)
            {
                metaPassthroughLayer.enabled = enabled;
                SetMember(layerType, metaPassthroughLayer, "hidden", !enabled);
                SetMember(layerType, metaPassthroughLayer, "textureOpacity", enabled ? 1f : 0f);
                SetMember(layerType, metaPassthroughLayer, "edgeRenderingEnabled", false);
            }
        }

        private void EnsureMetaOvrManager(Type managerType, bool enabled)
        {
            if (metaOvrManager == null)
            {
                metaOvrManager = GetComponent(managerType) as Behaviour;
                if (metaOvrManager == null)
                    metaOvrManager = gameObject.AddComponent(managerType) as Behaviour;
            }

            if (metaOvrManager == null) return;

            metaOvrManager.enabled = true;
            SetMember(managerType, metaOvrManager, "isInsightPassthroughEnabled", enabled);
            SetMember(managerType, metaOvrManager, "SimultaneousHandsAndControllersEnabled", true);
            SetMember(managerType, metaOvrManager, "shouldBoundaryVisibilityBeSuppressed", false);
        }

        private static void SetMember(Type type, object instance, string memberName, object value)
        {
            FieldInfo field = type.GetField(memberName, BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static);
            if (field != null)
            {
                field.SetValue(field.IsStatic ? null : instance, value);
                return;
            }

            PropertyInfo property = type.GetProperty(memberName, BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static);
            if (property != null && property.CanWrite)
                property.SetValue(property.GetGetMethod()?.IsStatic == true ? null : instance, value);
        }

        private static Type FindType(string typeName)
        {
            string[] likelyAssemblies = { "Oculus.VR", "Meta.XR.SDK.Core" };
            foreach (string assemblyName in likelyAssemblies)
            {
                Type type = Type.GetType($"{typeName}, {assemblyName}", false);
                if (type != null) return type;
            }
            return null;
        }
    }
}
