using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR;
using RFThreatDetection.Presentation;
using RFThreatDetection.Visualization;

namespace RFThreatDetection.Interaction
{
    /// <summary>
    /// Uses the right motion controller as a laser pointer. Right trigger selects a
    /// threat heatmap; right grip drags the world-anchored information panel.
    /// </summary>
    public class ThreatFocusController : MonoBehaviour
    {
        [SerializeField] private SpatialThreatDashboard dashboard;
        [SerializeField] private float maxDistanceMeters = 20f;

        private readonly List<InputDevice> controllers = new List<InputDevice>();
        private ThreatVolumeController focusedThreat;
        private ThreatVolumeController selectedThreat;
        private bool triggerWasPressed;
        private bool gripWasPressed;
        private bool draggingDashboard;
        private float dashboardDragDistance = 1f;
        private Transform reticle;
        private Renderer reticleRenderer;
        private LineRenderer pointerLine;

        private void Awake()
        {
            if (dashboard == null) dashboard = FindAnyObjectByType<SpatialThreatDashboard>();
            CreatePointerVisuals();
        }

        private void Update()
        {
            if (!TryGetRightController(out InputDevice controller) ||
                !controller.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 position) ||
                !controller.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion rotation))
            {
                SetFocusedThreat(null);
                SetPointerVisible(false);
                draggingDashboard = false;
                triggerWasPressed = false;
                gripWasPressed = false;
                return;
            }

            Transform trackingSpace = Camera.main != null ? Camera.main.transform.parent : null;
            if (trackingSpace != null)
            {
                position = trackingSpace.TransformPoint(position);
                rotation = trackingSpace.rotation * rotation;
            }
            Ray ray = new Ray(position, rotation * Vector3.forward);
            Physics.SyncTransforms();
            bool hasHit = Physics.Raycast(ray, out RaycastHit hit, maxDistanceMeters, ~0,
                                          QueryTriggerInteraction.Collide);
            float distance = hasHit ? hit.distance : 3f;
            ThreatVolumeController candidate = hasHit
                ? hit.collider.GetComponentInParent<ThreatVolumeController>()
                : null;
            bool pointsAtDashboard = hasHit && dashboard != null && dashboard.OwnsCollider(hit.collider);

            SetFocusedThreat(candidate);

            bool triggerPressed = controller.TryGetFeatureValue(CommonUsages.triggerButton, out bool trigger) && trigger;
            if (controller.TryGetFeatureValue(CommonUsages.trigger, out float triggerValue))
                triggerPressed |= triggerValue >= (triggerWasPressed ? 0.25f : 0.65f);
            if (triggerPressed && !triggerWasPressed)
            {
                if (pointsAtDashboard) dashboard.HandlePointerClick(hit.collider);
                else if (focusedThreat != null) SelectThreat(focusedThreat);
            }
            triggerWasPressed = triggerPressed;

            bool gripPressed = controller.TryGetFeatureValue(CommonUsages.gripButton, out bool grip) && grip;
            if (gripPressed && !gripWasPressed && pointsAtDashboard)
            {
                draggingDashboard = true;
                dashboardDragDistance = Mathf.Clamp(hit.distance, 0.35f, 3f);
            }
            if (draggingDashboard && gripPressed)
                dashboard.MovePanelToRay(ray, dashboardDragDistance);
            if (!gripPressed) draggingDashboard = false;
            gripWasPressed = gripPressed;

            Color pointerColor = candidate != null
                ? new Color(1f, 0.2f, 0.08f, 0.9f)
                : pointsAtDashboard
                    ? new Color(0.75f, 0.35f, 1f, 0.9f)
                    : new Color(0.15f, 0.9f, 1f, 0.72f);
            UpdatePointer(ray, distance, pointerColor, candidate != null || pointsAtDashboard);
        }

        private bool TryGetRightController(out InputDevice controller)
        {
            controllers.Clear();
            InputDevices.GetDevicesWithCharacteristics(InputDeviceCharacteristics.Controller |
                                                        InputDeviceCharacteristics.Right, controllers);
            if (controllers.Count > 0)
            {
                controller = controllers[0];
                return true;
            }
            controller = default;
            return false;
        }

        private void SetFocusedThreat(ThreatVolumeController candidate)
        {
            if (candidate == focusedThreat)
            {
                if (candidate == null) dashboard?.ClearThreat();
                return;
            }
            if (focusedThreat != null) focusedThreat.SetFocused(false);
            focusedThreat = candidate;
            if (focusedThreat != null)
            {
                focusedThreat.SetFocused(true);
                dashboard?.ShowThreat(focusedThreat.LatestData);
            }
            else
            {
                dashboard?.ClearThreat();
            }
        }

        private void SelectThreat(ThreatVolumeController threat)
        {
            if (selectedThreat != null && selectedThreat != threat)
                selectedThreat.SetSelected(false);
            selectedThreat = threat;
            selectedThreat.SetSelected(true);
            dashboard?.ShowThreat(selectedThreat.LatestData);
        }

        private void CreatePointerVisuals()
        {
            Shader shader = Resources.Load<Shader>("Shaders/SolidUnlit");

            GameObject lineObject = new GameObject("RightThreatPointerRay");
            pointerLine = lineObject.AddComponent<LineRenderer>();
            pointerLine.positionCount = 2;
            pointerLine.useWorldSpace = true;
            pointerLine.startWidth = 0.007f;
            pointerLine.endWidth = 0.002f;
            if (shader != null) pointerLine.material = new Material(shader);

            GameObject reticleObject = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            reticleObject.name = "ControllerPointerReticle";
            reticleObject.transform.localScale = Vector3.one * 0.018f;
            Destroy(reticleObject.GetComponent<Collider>());
            reticleRenderer = reticleObject.GetComponent<Renderer>();
            if (shader != null) reticleRenderer.material = new Material(shader);
            reticle = reticleObject.transform;
            SetPointerVisible(false);
        }

        private void UpdatePointer(Ray ray, float distance, Color color, bool hasTarget)
        {
            SetPointerVisible(true);
            Vector3 endpoint = ray.GetPoint(Mathf.Clamp(distance, 0.05f, maxDistanceMeters));
            pointerLine.SetPosition(0, ray.origin);
            pointerLine.SetPosition(1, endpoint);
            pointerLine.startColor = color;
            pointerLine.endColor = color;
            reticle.position = endpoint;
            reticle.localScale = Vector3.one * (hasTarget ? 0.026f : 0.014f);
            SetColor(pointerLine.material, color);
            SetColor(reticleRenderer.material, color);
        }

        private void SetPointerVisible(bool visible)
        {
            if (pointerLine != null) pointerLine.enabled = visible;
            if (reticleRenderer != null) reticleRenderer.enabled = visible;
        }

        private static void SetColor(Material material, Color color)
        {
            if (material != null && material.HasProperty("_Color")) material.SetColor("_Color", color);
        }
    }
}
