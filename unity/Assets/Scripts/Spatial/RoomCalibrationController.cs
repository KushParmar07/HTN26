using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using XRCommonUsages = UnityEngine.XR.CommonUsages;
using XRInputDevice = UnityEngine.XR.InputDevice;
using XRInputDeviceCharacteristics = UnityEngine.XR.InputDeviceCharacteristics;
using XRInputDevices = UnityEngine.XR.InputDevices;

namespace RFThreatDetection.Spatial
{
    /// <summary>
    /// Places backend coordinate (0, 0) in the physical room in front of the viewer.
    /// Press C in the Editor or either controller's secondary button (B/Y) on Quest.
    /// </summary>
    public class RoomCalibrationController : MonoBehaviour
    {
        [SerializeField] private RoomCoordinateTransformer transformer;
        [SerializeField] private Camera viewerCamera;
        [SerializeField, Min(0.5f)] private float originDistanceMeters = 1.5f;

        public event Action<string> OnCalibrationStatusChanged;

        private readonly List<XRInputDevice> controllers = new List<XRInputDevice>();
        private bool secondaryWasPressed;

        private void Awake()
        {
            if (transformer == null)
                transformer = GetComponent<RoomCoordinateTransformer>() ?? FindAnyObjectByType<RoomCoordinateTransformer>();
            if (viewerCamera == null)
                viewerCamera = Camera.main;
        }

        private void Update()
        {
            bool keyboardPressed = Keyboard.current != null && Keyboard.current.cKey.wasPressedThisFrame;
            bool secondaryPressed = ReadSecondaryButton();

            if (keyboardPressed || (secondaryPressed && !secondaryWasPressed))
                CalibrateInFrontOfViewer();

            secondaryWasPressed = secondaryPressed;
        }

        public void CalibrateInFrontOfViewer()
        {
            if (transformer == null || viewerCamera == null)
            {
                OnCalibrationStatusChanged?.Invoke("Calibration unavailable: camera or transformer missing");
                return;
            }

            Vector3 forward = Vector3.ProjectOnPlane(viewerCamera.transform.forward, Vector3.up).normalized;
            if (forward.sqrMagnitude < 0.1f)
                forward = Vector3.forward;

            Vector3 origin = viewerCamera.transform.position + forward * originDistanceMeters;
            origin.y = 0f;
            float yaw = Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg;
            transformer.RecalibrateOrigin(origin, yaw);

            string message = $"Room aligned: Pod A origin {origin.x:F1}, {origin.z:F1} m";
            Debug.Log($"[RoomCalibrationController] {message}");
            OnCalibrationStatusChanged?.Invoke(message);
        }

        private bool ReadSecondaryButton()
        {
            controllers.Clear();
            XRInputDevices.GetDevicesWithCharacteristics(XRInputDeviceCharacteristics.Controller, controllers);
            foreach (XRInputDevice controller in controllers)
            {
                if (controller.TryGetFeatureValue(XRCommonUsages.secondaryButton, out bool pressed) && pressed)
                    return true;
            }
            return false;
        }
    }
}
