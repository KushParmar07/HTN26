using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;

namespace RFThreatDetection.Spatial
{
    /// <summary>
    /// Configures a minimal OpenXR camera rig that works in the Editor and on Quest.
    /// The component creates direct HMD bindings so the scene does not depend on an
    /// imported sample Input Action asset.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public class QuestXRBootstrap : MonoBehaviour
    {
        [SerializeField] private XROrigin xrOrigin;
        [SerializeField] private Camera xrCamera;
        [SerializeField] private GameObject cameraFloorOffsetObject;

        public XROrigin Origin => xrOrigin;
        public Camera XRCamera => xrCamera;

        private void Awake()
        {
            EnsureRigConfigured();
        }

        public void EnsureRigConfigured()
        {
            if (xrOrigin == null)
            {
                xrOrigin = GetComponent<XROrigin>() ?? FindAnyObjectByType<XROrigin>();
            }

            if (xrCamera == null)
            {
                xrCamera = Camera.main;
            }

            if (xrOrigin == null || xrCamera == null)
            {
                Debug.LogWarning("[QuestXRBootstrap] XR Origin or Main Camera is missing.");
                return;
            }

            if (cameraFloorOffsetObject == null)
            {
                cameraFloorOffsetObject = xrCamera.transform.parent != null
                    ? xrCamera.transform.parent.gameObject
                    : xrOrigin.gameObject;
            }

            xrOrigin.Origin = xrOrigin.gameObject;
            xrOrigin.Camera = xrCamera;
            xrOrigin.CameraFloorOffsetObject = cameraFloorOffsetObject;
            xrOrigin.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Floor;
            xrOrigin.CameraYOffset = 0f;

            xrCamera.nearClipPlane = 0.05f;
            xrCamera.farClipPlane = 100f;

            TrackedPoseDriver poseDriver = xrCamera.GetComponent<TrackedPoseDriver>();
            if (poseDriver == null)
            {
                poseDriver = xrCamera.gameObject.AddComponent<TrackedPoseDriver>();
            }

            poseDriver.trackingType = TrackedPoseDriver.TrackingType.RotationAndPosition;
            poseDriver.updateType = TrackedPoseDriver.UpdateType.UpdateAndBeforeRender;
            poseDriver.positionInput = CreateAction("HMD Position", "<XRHMD>/centerEyePosition");
            poseDriver.rotationInput = CreateAction("HMD Rotation", "<XRHMD>/centerEyeRotation");
            poseDriver.trackingStateInput = CreateAction("HMD Tracking State", "<XRHMD>/trackingState");
        }

        private static InputActionProperty CreateAction(string name, string binding)
        {
            return new InputActionProperty(new InputAction(name, InputActionType.Value, binding));
        }
    }
}
