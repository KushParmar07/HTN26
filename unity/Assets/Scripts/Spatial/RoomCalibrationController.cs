using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using RFThreatDetection.Visualization;
using XRCommonUsages = UnityEngine.XR.CommonUsages;
using XRInputDevice = UnityEngine.XR.InputDevice;
using XRInputDeviceCharacteristics = UnityEngine.XR.InputDeviceCharacteristics;
using XRInputDevices = UnityEngine.XR.InputDevices;

namespace RFThreatDetection.Spatial
{
    /// <summary>
    /// Provides quick viewer-centered calibration and precise three-point placement.
    /// Aim the left controller at the floor and pull its trigger to place A, B, then C.
    /// </summary>
    public class RoomCalibrationController : MonoBehaviour
    {
        [SerializeField] private RoomCoordinateTransformer transformer;
        [SerializeField] private Camera viewerCamera;
        [SerializeField] private float pointerLengthMeters = 8f;
        private static readonly Vector3 BackendTriangleCentroid = new Vector3(1f, 0f, Mathf.Sqrt(3f) / 3f);

        public event Action<string> OnCalibrationStatusChanged;
        public int NextPodPlacementIndex => nextPodPlacementIndex;
        public bool HasThreePointPlacement => transformer != null && transformer.UsesPlacedPodCalibration;

        private readonly List<XRInputDevice> controllers = new List<XRInputDevice>();
        private readonly Vector3[] placedPods = new Vector3[3];
        private int nextPodPlacementIndex;
        private SensorNodeVisualizer sensorVisualizer;
        private bool leftTriggerWasPressed;

        private LineRenderer placementRay;

        private void Awake()
        {
            EnsureDependencies();
            CreatePlacementRay();
        }

        private IEnumerator Start()
        {
            yield return null;
            CalibrateInFrontOfViewer();
            PublishPlacementPrompt();
        }

        private void Update()
        {
            EnsureDependencies();
            bool keyboardPressed = Keyboard.current != null && Keyboard.current.cKey.wasPressedThisFrame;
            if (keyboardPressed)
            {
                CalibrateInFrontOfViewer();
                ResetPlacementSequence();
            }


            UpdateLeftControllerPlacement();
        }

        public void CalibrateInFrontOfViewer()
        {
            EnsureDependencies();
            if (transformer == null || viewerCamera == null)
            {
                OnCalibrationStatusChanged?.Invoke("Calibration unavailable: camera or transformer missing");
                return;
            }

            Vector3 forward = Vector3.ProjectOnPlane(viewerCamera.transform.forward, Vector3.up).normalized;
            if (forward.sqrMagnitude < 0.1f) forward = Vector3.forward;

            float yaw = Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg;
            Quaternion roomRotation = Quaternion.Euler(0f, yaw, 0f);
            Vector3 viewerFloorPosition = viewerCamera.transform.position;
            viewerFloorPosition.y = 0f;
            Vector3 origin = viewerFloorPosition - roomRotation * BackendTriangleCentroid;
            transformer.RecalibrateOrigin(origin, yaw);

            const string message = "Room centered: use left trigger to place Pod A";
            Debug.Log($"[RoomCalibrationController] {message}");
            OnCalibrationStatusChanged?.Invoke(message);
        }

        public void ResetPlacementSequence()
        {
            nextPodPlacementIndex = 0;
            sensorVisualizer?.ClearPlacementPreviews();
            PublishPlacementPrompt();
        }

        private void UpdateLeftControllerPlacement()
        {
            if (!TryGetController(XRInputDeviceCharacteristics.Left, out XRInputDevice controller) ||
                !controller.TryGetFeatureValue(XRCommonUsages.devicePosition, out Vector3 position) ||
                !controller.TryGetFeatureValue(XRCommonUsages.deviceRotation, out Quaternion rotation))
            {
                if (placementRay != null) placementRay.enabled = false;
                return;
            }

            // XR device poses are relative to the camera's tracking-space parent.
            Transform trackingSpace = viewerCamera != null ? viewerCamera.transform.parent : null;
            if (trackingSpace != null)
            {
                position = trackingSpace.TransformPoint(position);
                rotation = trackingSpace.rotation * rotation;
            }
            Ray ray = new Ray(position, rotation * Vector3.forward);
            Plane floor = new Plane(Vector3.up, Vector3.zero);
            bool hitsFloor = floor.Raycast(ray, out float distance) && distance > 0.05f && distance <= pointerLengthMeters;
            Vector3 endpoint = hitsFloor ? ray.GetPoint(distance) : ray.GetPoint(pointerLengthMeters);
            UpdatePlacementRay(position, endpoint, hitsFloor);

            bool triggerPressed = controller.TryGetFeatureValue(XRCommonUsages.triggerButton, out bool trigger) && trigger;
            if (controller.TryGetFeatureValue(XRCommonUsages.trigger, out float triggerValue))
                triggerPressed |= triggerValue >= (leftTriggerWasPressed ? 0.25f : 0.65f);
            if (triggerPressed && !leftTriggerWasPressed && hitsFloor)
                PlaceNextPod(endpoint);
            leftTriggerWasPressed = triggerPressed;

        }

        public void PlaceNextPod(Vector3 floorPoint)
        {
            if (nextPodPlacementIndex >= placedPods.Length) return;

            floorPoint.y = 0f;
            for (int i = 0; i < nextPodPlacementIndex; i++)
            {
                if (Vector3.Distance(placedPods[i], floorPoint) < 0.35f)
                {
                    OnCalibrationStatusChanged?.Invoke("Too close to the previous pod. Aim at the next physical pod.");
                    return;
                }
            }
            placedPods[nextPodPlacementIndex] = floorPoint;
            sensorVisualizer?.SetPlacementPreview(nextPodPlacementIndex, floorPoint);
            string podName = ((char)('A' + nextPodPlacementIndex)).ToString();
            Debug.Log($"[RoomCalibrationController] Placed Pod {podName} at {floorPoint}");
            nextPodPlacementIndex++;

            if (nextPodPlacementIndex == 3)
            {
                if (transformer != null && transformer.RecalibrateFromPlacedPods(placedPods[0], placedPods[1], placedPods[2]))
                {
                    sensorVisualizer?.ClearPlacementPreviews();
                    OnCalibrationStatusChanged?.Invoke("A / B / C placed. Aim right controller at AdrianPhone to inspect.");
                }
                else
                {
                    nextPodPlacementIndex = 2;
                    OnCalibrationStatusChanged?.Invoke("Triangle too narrow. Place C away from the A-B line.");
                }
                return;
            }

            PublishPlacementPrompt();
        }

        private void PublishPlacementPrompt()
        {
            string podName = ((char)('A' + Mathf.Clamp(nextPodPlacementIndex, 0, 2))).ToString();
            OnCalibrationStatusChanged?.Invoke($"STEP {nextPodPlacementIndex + 1}/3  |  Aim LEFT at floor under {podName}, then pull trigger");
        }

        private void EnsureDependencies()
        {
            if (transformer == null)
                transformer = GetComponent<RoomCoordinateTransformer>() ?? FindAnyObjectByType<RoomCoordinateTransformer>();
            if (viewerCamera == null) viewerCamera = Camera.main;
            if (sensorVisualizer == null)
                sensorVisualizer = GetComponent<SensorNodeVisualizer>() ?? FindAnyObjectByType<SensorNodeVisualizer>();
        }

        private bool TryGetController(XRInputDeviceCharacteristics hand, out XRInputDevice controller)
        {
            controllers.Clear();
            XRInputDevices.GetDevicesWithCharacteristics(XRInputDeviceCharacteristics.Controller | hand, controllers);
            if (controllers.Count > 0)
            {
                controller = controllers[0];
                return true;
            }
            controller = default;
            return false;
        }

        private void CreatePlacementRay()
        {
            GameObject rayObject = new GameObject("LeftPodPlacementRay");
            placementRay = rayObject.AddComponent<LineRenderer>();
            placementRay.positionCount = 2;
            placementRay.useWorldSpace = true;
            placementRay.startWidth = 0.008f;
            placementRay.endWidth = 0.003f;
            Shader shader = Resources.Load<Shader>("Shaders/SolidUnlit");
            if (shader != null) placementRay.material = new Material(shader);
            placementRay.enabled = false;
        }

        private void UpdatePlacementRay(Vector3 start, Vector3 end, bool validFloorPoint)
        {
            if (placementRay == null) return;
            placementRay.enabled = true;
            placementRay.SetPosition(0, start);
            placementRay.SetPosition(1, end);
            Color color = validFloorPoint ? new Color(0.15f, 0.95f, 1f, 0.85f) : new Color(1f, 0.35f, 0.12f, 0.65f);
            placementRay.startColor = color;
            placementRay.endColor = color;
            if (placementRay.material != null && placementRay.material.HasProperty("_Color"))
                placementRay.material.SetColor("_Color", color);
        }
    }
}
