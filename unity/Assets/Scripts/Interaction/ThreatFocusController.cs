using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR;
using RFThreatDetection.Presentation;
using RFThreatDetection.Visualization;

namespace RFThreatDetection.Interaction
{
    /// <summary>
    /// Provides controller-free gaze selection. Looking at a threat highlights it;
    /// holding the gaze selects it and opens the spatial details dashboard.
    /// </summary>
    public class ThreatFocusController : MonoBehaviour
    {
        [SerializeField] private Camera viewerCamera;
        [SerializeField] private SpatialThreatDashboard dashboard;
        [SerializeField] private float maxDistanceMeters = 20f;
        [SerializeField] private float dwellSeconds = 0.65f;

        private readonly List<InputDevice> controllers = new List<InputDevice>();
        private ThreatVolumeController focusedThreat;
        private ThreatVolumeController selectedThreat;
        private float focusStartedAt;
        private bool primaryWasPressed;
        private Transform reticle;
        private Renderer reticleRenderer;

        private void Awake()
        {
            if (viewerCamera == null) viewerCamera = Camera.main;
            if (dashboard == null) dashboard = FindAnyObjectByType<SpatialThreatDashboard>();
            CreateReticle();
        }

        private void Update()
        {
            if (viewerCamera == null) return;

            Ray ray = new Ray(viewerCamera.transform.position, viewerCamera.transform.forward);
            ThreatVolumeController candidate = null;
            float reticleDistance = 1.1f;

            // Threat transforms are animated every frame. Sync their colliders before
            // the gaze query so the ray always matches the visible cloud position.
            Physics.SyncTransforms();
            if (Physics.Raycast(ray, out RaycastHit hit, maxDistanceMeters, ~0, QueryTriggerInteraction.Collide))
            {
                candidate = hit.collider.GetComponentInParent<ThreatVolumeController>();
                reticleDistance = Mathf.Clamp(hit.distance - 0.02f, 0.3f, 3f);
            }

            SetFocusedThreat(candidate);
            UpdateReticle(reticleDistance, candidate != null);

            bool primaryPressed = ReadPrimaryButton();
            bool selectPressed = primaryPressed && !primaryWasPressed;
            primaryWasPressed = primaryPressed;

            if (focusedThreat != null && (selectPressed || Time.unscaledTime - focusStartedAt >= dwellSeconds))
                SelectThreat(focusedThreat);
        }

        private void SetFocusedThreat(ThreatVolumeController candidate)
        {
            if (candidate == focusedThreat) return;
            if (focusedThreat != null) focusedThreat.SetFocused(false);
            focusedThreat = candidate;
            focusStartedAt = Time.unscaledTime;
            if (focusedThreat != null) focusedThreat.SetFocused(true);
        }

        private void SelectThreat(ThreatVolumeController threat)
        {
            if (selectedThreat == threat) return;
            if (selectedThreat != null) selectedThreat.SetSelected(false);
            selectedThreat = threat;
            selectedThreat.SetSelected(true);
            dashboard?.ShowThreat(selectedThreat.LatestData);
        }

        private bool ReadPrimaryButton()
        {
            controllers.Clear();
            InputDevices.GetDevicesWithCharacteristics(InputDeviceCharacteristics.Controller, controllers);
            foreach (InputDevice controller in controllers)
            {
                if (controller.TryGetFeatureValue(CommonUsages.primaryButton, out bool pressed) && pressed)
                    return true;
            }
            return false;
        }

        private void CreateReticle()
        {
            GameObject reticleObject = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            reticleObject.name = "GazeReticle";
            reticleObject.transform.localScale = Vector3.one * 0.012f;
            Destroy(reticleObject.GetComponent<Collider>());
            reticleRenderer = reticleObject.GetComponent<Renderer>();
            Shader shader = Shader.Find("Unlit/Color") ?? Shader.Find("Sprites/Default");
            reticleRenderer.material = new Material(shader);
            reticle = reticleObject.transform;
        }

        private void UpdateReticle(float distance, bool hasTarget)
        {
            if (reticle == null) return;
            reticle.position = viewerCamera.transform.position + viewerCamera.transform.forward * distance;
            reticle.rotation = viewerCamera.transform.rotation;
            reticle.localScale = Vector3.one * (hasTarget ? 0.018f : 0.010f);
            if (reticleRenderer != null)
                reticleRenderer.material.color = hasTarget ? new Color(1f, 0.35f, 0.1f) : new Color(0.2f, 0.9f, 1f);
        }
    }
}
