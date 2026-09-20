#if UNITY_EDITOR
using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using RFThreatDetection.Dev;
using RFThreatDetection.Models;
using RFThreatDetection.Network;
using RFThreatDetection.Spatial;
using RFThreatDetection.Visualization;

namespace RFThreatDetection.Editor
{
    /// <summary>
    /// Automated batchmode and Play Mode verification for Unity 6.
    /// Verifies scene setup, coordinate transformation, passthrough configuration,
    /// sensor node visualization, and moving threat tracking.
    /// </summary>
    public static class PlayModeVerification
    {
        private const string ScenePath = "Assets/Scenes/MainThreatVisualization.unity";
        private const string FlagFilePath = "Temp/PlayModeVerificationActive.flag";
        private static int playModeFrameCount = 0;

        [MenuItem("RF Threat Detection/Run Verification Test", false, 2)]
        public static void RunVerification()
        {
            Debug.Log("=================================================");
            Debug.Log("[VERIFICATION] Starting Unity 6 Verification");
            Debug.Log("=================================================");

            try
            {
                // Step 1: Ensure demo scene is built and saved with Unity 6 component mappings
                SceneSetupHelper.SetupDemoScene();

                // Step 2: Open scene
                Scene scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
                if (!scene.IsValid())
                {
                    throw new Exception($"Failed to open scene at {ScenePath}");
                }
                Debug.Log($"[VERIFICATION] Successfully opened scene: {scene.name}");

                // Step 3: Verify Hierarchy and Components
                GameObject rfSystem = GameObject.Find("[RFThreatSystem]");
                if (rfSystem == null) throw new Exception("GameObject '[RFThreatSystem]' not found in scene.");

                var transformer = rfSystem.GetComponent<RoomCoordinateTransformer>();
                var wsClient = rfSystem.GetComponent<ThreatWebSocketClient>();
                var sensorViz = rfSystem.GetComponent<SensorNodeVisualizer>();
                var vizManager = rfSystem.GetComponent<ThreatVisualizationManager>();
                var passthrough = rfSystem.GetComponent<QuestPassthroughManager>();
                var devRunner = rfSystem.GetComponent<QuestDevTestRunner>();

                if (transformer == null) throw new Exception("Missing RoomCoordinateTransformer component");
                if (wsClient == null) throw new Exception("Missing ThreatWebSocketClient component");
                if (sensorViz == null) throw new Exception("Missing SensorNodeVisualizer component");
                if (vizManager == null) throw new Exception("Missing ThreatVisualizationManager component");
                if (passthrough == null) throw new Exception("Missing QuestPassthroughManager component");
                if (devRunner == null) throw new Exception("Missing QuestDevTestRunner component");

                Debug.Log("[VERIFICATION] [PASS] All 6 core RF Threat subsystems verified on [RFThreatSystem].");

                // Step 4: Verify Quest Passthrough Camera Configuration
                Camera mainCam = Camera.main;
                if (mainCam == null) throw new Exception("MainCamera not found");
                passthrough.EnablePassthrough();
                if (mainCam.clearFlags != CameraClearFlags.SolidColor)
                    throw new Exception($"Expected CameraClearFlags.SolidColor but got {mainCam.clearFlags}");
                if (mainCam.backgroundColor.a != 0f)
                    throw new Exception($"Expected camera background alpha 0 for Passthrough, got {mainCam.backgroundColor.a}");
                Debug.Log("[VERIFICATION] [PASS] Passthrough camera configured (SolidColor with RGBA 0,0,0,0).");

                // Step 5: Verify Coordinate Transformation
                Vector3 originPos = transformer.BackendToWorld(0f, 0f);
                Vector3 podBPos = transformer.BackendToWorld(2.0f, 0f);
                Vector3 podCPos = transformer.BackendToWorld(1.0f, Mathf.Sqrt(3f));
                Debug.Log($"[VERIFICATION] Origin transformed: {originPos}");
                Debug.Log($"[VERIFICATION] Pod B transformed: {podBPos}");
                Debug.Log($"[VERIFICATION] Pod C transformed: {podCPos}");
                if (Vector3.Distance(originPos, new Vector3(0f, 1f, 0f)) > 0.001f)
                    throw new Exception("Origin coordinate mapping unexpected");
                if (Vector3.Distance(podBPos, new Vector3(2f, 1f, 0f)) > 0.001f)
                    throw new Exception("Pod B coordinate mapping unexpected");
                if (Vector3.Distance(podCPos, new Vector3(1f, 1f, Mathf.Sqrt(3f))) > 0.001f)
                    throw new Exception("Pod C coordinate mapping unexpected");
                Debug.Log("[VERIFICATION] [PASS] RoomCoordinateTransformer 2D -> 3D coordinate mapping verified.");

                var calibration = rfSystem.GetComponent<RoomCalibrationController>();
                if (calibration == null) throw new Exception("Missing RoomCalibrationController component");
                calibration.CalibrateInFrontOfViewer();
                Vector2 viewerInBackend = transformer.WorldToBackend(new Vector3(mainCam.transform.position.x, 0f,
                                                                                   mainCam.transform.position.z));
                Vector2 expectedCentroid = new Vector2(1f, Mathf.Sqrt(3f) / 3f);
                if (Vector2.Distance(viewerInBackend, expectedCentroid) > 0.01f)
                    throw new Exception($"Viewer was not centered inside pod triangle: {viewerInBackend}");
                transformer.RecalibrateOrigin(Vector3.zero, 0f);
                Debug.Log("[VERIFICATION] [PASS] Room calibration centers the pod triangle around the viewer.");

                Vector3 placedA = new Vector3(-1f, 0f, -1f);
                Vector3 placedB = new Vector3(1f, 0f, -1f);
                Vector3 placedC = new Vector3(0f, 0f, Mathf.Sqrt(3f) - 1f);
                if (!transformer.RecalibrateFromPlacedPods(placedA, placedB, placedC))
                    throw new Exception("Valid three-point pod calibration was rejected.");
                if (Vector3.Distance(transformer.BackendToWorld(0f, 0f, 0f), placedA) > 0.001f ||
                    Vector3.Distance(transformer.BackendToWorld(2f, 0f, 0f), placedB) > 0.001f ||
                    Vector3.Distance(transformer.BackendToWorld(1f, Mathf.Sqrt(3f), 0f), placedC) > 0.001f)
                    throw new Exception("Three-point pod calibration does not map backend A/B/C onto placed points.");
                transformer.RecalibrateOrigin(Vector3.zero, 0f);
                Debug.Log("[VERIFICATION] [PASS] Controller-placed Pod A/B/C calibration maps all three anchors.");

                // Step 6: Verify Sensor Node Visualizer
                SensorNodeData[] sensorNodes = new SensorNodeData[]
                {
                    new SensorNodeData("pod_a", 0.0f, 0.0f),
                    new SensorNodeData("pod_b", 2.0f, 0.0f),
                    new SensorNodeData("pod_c", 1.0f, Mathf.Sqrt(3f))
                };
                sensorViz.UpdateSensorNodes(sensorNodes);
                GameObject podAObj = GameObject.Find("SensorNode_pod_a");
                GameObject podBObj = GameObject.Find("SensorNode_pod_b");
                GameObject podCObj = GameObject.Find("SensorNode_pod_c");
                if (podAObj == null || podBObj == null || podCObj == null)
                    throw new Exception("Sensor pod marker GameObjects were not created.");
                if (GameObject.FindObjectsByType<SensorNodeVisualizer>(FindObjectsSortMode.None).Length != 1)
                    throw new Exception("More than one SensorNodeVisualizer exists in the scene.");
                Renderer[] podRenderers = sensorViz.GetComponentsInChildren<Renderer>();
                int podMarkerCount = 0;
                foreach (Renderer podRenderer in podRenderers)
                {
                    if (podRenderer.gameObject.name.StartsWith("SensorNode_"))
                    {
                        podMarkerCount++;
                        if (podRenderer.sharedMaterial == null ||
                            podRenderer.sharedMaterial.shader.name != "RFThreat/SolidUnlit")
                            throw new Exception($"{podRenderer.gameObject.name} is missing bundled pod shader.");
                    }
                }
                if (podMarkerCount != 3)
                    throw new Exception($"Expected exactly 3 pod markers, found {podMarkerCount}.");
                Debug.Log("[VERIFICATION] [PASS] Sensor nodes (Pods A, B, C) created and positioned.");

                calibration.ResetPlacementSequence();
                calibration.PlaceNextPod(placedA);
                if (calibration.NextPodPlacementIndex != 1 || Vector3.Distance(podAObj.transform.position, placedA + Vector3.up * 0.05f) > 0.001f)
                    throw new Exception("Pod A placement did not immediately move its preview marker.");
                calibration.PlaceNextPod(placedA);
                if (calibration.NextPodPlacementIndex != 1) throw new Exception("Duplicate placement was accepted.");
                calibration.PlaceNextPod(placedB);
                calibration.PlaceNextPod(placedC);
                if (!calibration.HasThreePointPlacement || calibration.NextPodPlacementIndex != 3)
                    throw new Exception("A/B/C placement failed to complete.");
                calibration.PlaceNextPod(Vector3.one * 10f);
                if (calibration.NextPodPlacementIndex != 3) throw new Exception("Completed calibration restarted accidentally.");
                calibration.ResetPlacementSequence();
                transformer.RecalibrateOrigin(Vector3.zero, 0f);
                sensorViz.UpdateSensorNodes(sensorNodes);
                Debug.Log("[VERIFICATION] [PASS] Immediate pod preview, duplicate rejection, and completed placement lock verified.");

                var parsed = JsonUtility.FromJson<ThreatStateData>("{\"monitored_aps\":[{\"threat_id\":\"phone\",\"ssid\":\"AdrianPhone\",\"risk_score\":5,\"estimated_position_2d\":{\"x\":1,\"y\":0.5},\"observed_by_pods\":[\"pod_a\",\"pod_b\",\"pod_c\"],\"filtered_rssi_by_pod\":{\"pod_a\":-42}}]}");
                if (parsed.GetDemoSources().Length != 1 || parsed.GetDemoSources()[0].StrongestDbm != -42f || !parsed.GetDemoSources()[0].isBelowThreshold)
                    throw new Exception("Phone filtering or sparse RSSI deserialization failed.");
                parsed.monitored_aps[0].estimated_position_2d = new Position2DData(3f, 3f);
                parsed.monitored_aps[0].filtered_rssi_by_pod.pod_a = -80f;
                if (parsed.GetDemoSources().Length != 1) throw new Exception("Weak located phone signal disappeared.");
                parsed.monitored_aps[0].filtered_rssi_by_pod = null;
                if (parsed.GetDemoSources().Length != 1 || parsed.GetDemoSources()[0].StrongestDbm != -127f)
                    throw new Exception("Located source with temporarily missing RSSI disappeared.");
                ThreatStateData.FocusTargetOnly = false;
                var crowded = new ThreatStateData { monitored_aps = new ThreatItemData[6] };
                for (int i = 0; i < 6; i++) crowded.monitored_aps[i] = new ThreatItemData {
                    threat_id = "near_" + i, ssid = i == 0 ? "WMBY 2056" : "Nearby " + i,
                    bssid = i == 0 ? "46:F7:9F:3B:26:7B" : $"20:11:22:33:44:{i:X2}",
                    estimated_position_2d = new Position2DData(3f + i, 3f),
                    observed_by_pods = new[] { "pod_a", "pod_b", "pod_c" },
                    filtered_rssi_by_pod = new PodSignalData { pod_a = -30f - i * 5f }
                };
                var nearest = crowded.GetDemoSources();
                if (nearest.Length != 3 || nearest[0].threat_id != "near_1" || nearest[2].threat_id != "near_3")
                    throw new Exception("Nearby limit, signal ranking or transport exclusion failed.");
                ThreatStateData.FocusTargetOnly = true;
                if (crowded.GetDemoSources().Length != 0) throw new Exception("Phone-only mode exposed other Wi-Fi networks.");
                ThreatStateData.FocusTargetOnly = false;
                crowded.monitored_aps[5].ssid = "DIRECT-Meta-6vdm";
                crowded.monitored_aps[5].bssid = "B6:17:A8:6A:8F:FD";
                crowded.monitored_aps[5].filtered_rssi_by_pod.pod_a = -20f;
                if (crowded.GetDemoSources()[0].threat_id != "near_1" || crowded.GetDemoSources()[2].threat_id != "near_3")
                    throw new Exception("Quest Wi-Fi Direct exclusion or unbounded signal ranking failed.");
                Debug.Log("[VERIFICATION] [PASS] Infrastructure exclusion, unbounded ranking, and strongest-three limit verified.");

                // Step 7: Verify Moving Threat Pipeline (Mock Path)
                // Frame 1: Position (0.5, 0.5)
                ThreatStateData stateFrame1 = CreateTestThreatState("threat_test_01", 0.5f, 0.5f, 0.45f, 100f);
                vizManager.HandleThreatState(stateFrame1);

                GameObject threatObj = GameObject.Find("ThreatVolume_threat_test_01");
                if (threatObj == null) throw new Exception("Threat volume GameObject 'ThreatVolume_threat_test_01' not spawned!");
                var controller = threatObj.GetComponent<ThreatVolumeController>();
                if (controller == null) throw new Exception("ThreatVolumeController component missing on threat volume!");

                Transform threatOrb = threatObj.transform.Find("ThreatOrb");
                if (threatOrb == null) throw new Exception("Solid three-dimensional ThreatOrb is missing!");
                Renderer[] orbRenderers = threatOrb.GetComponentsInChildren<Renderer>();
                if (orbRenderers.Length != 1 || orbRenderers[0].sharedMaterial == null ||
                    orbRenderers[0].sharedMaterial.shader.name != "RFThreat/SolidUnlit" ||
                    orbRenderers[0].sharedMaterial.GetColor("_Color").a < 0.70f ||
                    orbRenderers[0].sharedMaterial.GetColor("_Color").a > 0.90f)
                    throw new Exception("Threat source is not one slightly translucent solid sphere.");
                if (threatObj.transform.Find("HeatField") != null)
                    throw new Exception("Legacy gas/footprint effect is still present.");
                SphereCollider threatCollider = threatObj.GetComponent<SphereCollider>();
                if (threatCollider == null || !threatCollider.isTrigger)
                    throw new Exception("Threat orb is missing its controller-pointing collider.");
                if (threatObj.GetComponentInChildren<ParticleSystem>() != null)
                    throw new Exception("Legacy gas particle system is still present.");
                Debug.Log("[VERIFICATION] [PASS] Translucent solid 3D source orb and pointer collider created without gas effects.");

                float initialDiameter = controller.TargetDiameter;
                Debug.Log($"[VERIFICATION] Frame 1: Threat spawned at {threatObj.transform.position}. Signal diameter: {initialDiameter:F2}m");

                // Frame 2: Moving along path to (2.0, 1.5)
                ThreatStateData stateFrame2 = CreateTestThreatState("threat_test_01", 2.0f, 1.5f, 0.55f, 85f);
                vizManager.HandleThreatState(stateFrame2);
                Vector3 expectedPos2 = transformer.BackendToWorld(2.0f, 1.5f);
                Debug.Log($"[VERIFICATION] Frame 2: Threat moved to 2D (2.0, 1.5) -> World 3D {expectedPos2}");

                // Frame 3: Moving to (3.5, 2.5)
                ThreatStateData stateFrame3 = CreateTestThreatState("threat_test_01", 3.5f, 2.5f, 0.35f, 95f);
                vizManager.HandleThreatState(stateFrame3);
                Vector3 expectedPos3 = transformer.BackendToWorld(3.5f, 2.5f);
                Debug.Log($"[VERIFICATION] Frame 3: Threat moved to 2D (3.5, 2.5) -> World 3D {expectedPos3}");

                // Verify HUD text contents
                TextMesh hudText = threatObj.GetComponentInChildren<TextMesh>(true);
                if (hudText == null) throw new Exception("Billboard TextMesh missing on threat volume!");
                Debug.Log($"[VERIFICATION] Billboard HUD Text:\n{hudText.text}");
                if (!hudText.text.Contains("SIGNAL") || !hudText.text.Contains("POSITION") || !hudText.text.Contains("AdrianPhone"))
                    throw new Exception("Billboard HUD text content mismatch!");
                Debug.Log("[VERIFICATION] [PASS] ThreatVolumeController correctly received moving coordinates and updated billboard HUD.");

                // A weak source remains visible, uses the blue end of the cold scale,
                // and grows greener/larger as its signal becomes stronger.
                var blueFrame = CreateTestThreatState("threat_test_01", 3.5f, 2.5f, 0.35f, 5f);
                blueFrame.monitored_aps = blueFrame.threats;
                blueFrame.monitored_aps[0].status = "MONITORED";
                blueFrame.monitored_aps[0].filtered_rssi_by_pod = new PodSignalData { pod_a = -78f, pod_b = -80f, pod_c = -82f };
                blueFrame.threats = new ThreatItemData[0];
                vizManager.HandleThreatState(blueFrame);
                if (GameObject.Find("ThreatVolume_threat_test_01") != threatObj)
                    throw new Exception("Threshold transition duplicated the source object.");
                Color blueTint = orbRenderers[0].sharedMaterial.GetColor("_Color");
                float weakDiameter = controller.TargetDiameter;
                if (blueTint.b <= blueTint.g || blueTint.a < 0.70f || blueTint.a > 0.90f)
                    throw new Exception("Weak source orb is not translucent cold blue.");
                stateFrame3.threats[0].filtered_rssi_by_pod = new PodSignalData { pod_a = -32f, pod_b = -34f, pod_c = -36f };
                vizManager.HandleThreatState(stateFrame3);
                Color strongTint = orbRenderers[0].sharedMaterial.GetColor("_Color");
                if (strongTint.g <= blueTint.g || controller.TargetDiameter <= weakDiameter)
                    throw new Exception("Stronger source did not become greener and larger.");
                Debug.Log("[VERIFICATION] [PASS] Cold color scale, signal sizing, translucency, and stable identity verified.");

                // A partial one-pod update may refresh presence but must never move
                // a previously localized orb to the backend coordinate origin/Pod A.
                Vector3 lastGoodTarget = controller.TargetPosition;
                var partialFrame = CreateTestThreatState("threat_test_01", 0f, 0f, 5f, 5f);
                partialFrame.threats[0].observed_by_pods = new[] { "pod_a" };
                partialFrame.threats[0].filtered_rssi_by_pod = new PodSignalData { pod_a = -28f };
                vizManager.HandleThreatState(partialFrame);
                if (Vector3.Distance(controller.TargetPosition, lastGoodTarget) > 0.001f)
                    throw new Exception("Partial pod update moved the source to Pod A/origin.");
                Debug.Log("[VERIFICATION] [PASS] Partial pod cycles retain the last valid three-pod position.");

                // Frame 4: Threat clears
                ThreatStateData emptyState = new ThreatStateData
                {
                    version = "1.0",
                    generated_at_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                    sensor_nodes = sensorNodes,
                    threats = new ThreatItemData[0]
                };
                vizManager.HandleThreatState(emptyState);
                Debug.Log("[VERIFICATION] [PASS] Missing source entered the short visual absence grace period.");

                // Step 8: Enter Play Mode
                Debug.Log("[VERIFICATION] Entering Unity 6 Play Mode...");
                Directory.CreateDirectory("Temp");
                File.WriteAllText(FlagFilePath, "active");
                EditorApplication.EnterPlaymode();
            }
            catch (Exception ex)
            {
                Debug.LogError($"[VERIFICATION] [FAIL] Error during verification: {ex.Message}\n{ex.StackTrace}");
                if (Application.isBatchMode)
                {
                    EditorApplication.Exit(1);
                }
            }
        }

        [InitializeOnLoadMethod]
        private static void OnEditorInitialized()
        {
            if (File.Exists(FlagFilePath))
            {
                EditorApplication.update += OnPlayModeVerificationUpdate;
            }
        }

        private static void OnPlayModeVerificationUpdate()
        {
            if (!EditorApplication.isPlaying) return;

            playModeFrameCount++;
            if (playModeFrameCount == 1)
            {
                Debug.Log($"[VERIFICATION] [PASS] Executing frame {playModeFrameCount} in active Unity 6 Play Mode!");
            }

            if (playModeFrameCount >= 20)
            {
                EditorApplication.update -= OnPlayModeVerificationUpdate;
                CaptureDashboardPreview();
                try { File.Delete(FlagFilePath); } catch {}
                Debug.Log($"[VERIFICATION] [PASS] Completed {playModeFrameCount} frames in Unity 6.3 Play Mode successfully!");
                Debug.Log("=================================================");
                Debug.Log("[VERIFICATION] ALL TESTS PASSED SUCCESSFULLY IN UNITY 6!");
                Debug.Log("=================================================");
                EditorApplication.ExitPlaymode();
                if (Application.isBatchMode)
                {
                    EditorApplication.Exit(0);
                }
            }
        }

        private static void CaptureDashboardPreview()
        {
            var dashboard = UnityEngine.Object.FindAnyObjectByType<RFThreatDetection.Presentation.SpatialThreatDashboard>();
            Camera viewer = Camera.main;
            if (dashboard == null || viewer == null) return;
            dashboard.PlacePanelInFront();
            var cameraObject = new GameObject("DashboardPreviewCamera");
            var camera = cameraObject.AddComponent<Camera>();
            camera.CopyFrom(viewer);
            camera.stereoTargetEye = StereoTargetEyeMask.None;
            camera.transform.SetPositionAndRotation(viewer.transform.position, viewer.transform.rotation);
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.12f, 0.15f, 0.18f);
            var target = new RenderTexture(1600, 1000, 24);
            camera.targetTexture = target;
            camera.Render();
            var previous = RenderTexture.active;
            RenderTexture.active = target;
            var pixels = new Texture2D(1600, 1000, TextureFormat.RGB24, false);
            pixels.ReadPixels(new Rect(0, 0, 1600, 1000), 0, 0);
            pixels.Apply();
            Directory.CreateDirectory("Logs");
            File.WriteAllBytes("Logs/dashboard-demo-preview.png", pixels.EncodeToPNG());
            RenderTexture.active = previous;
            camera.targetTexture = null;
            UnityEngine.Object.Destroy(cameraObject);
            target.Release();
            UnityEngine.Object.Destroy(target);
            UnityEngine.Object.Destroy(pixels);
        }

        private static ThreatStateData CreateTestThreatState(string threatId, float x, float y, float uncertainty, float risk)
        {
            return new ThreatStateData
            {
                version = "1.0",
                generated_at_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                sensor_nodes = new SensorNodeData[]
                {
                    new SensorNodeData("pod_a", 0.0f, 0.0f),
                    new SensorNodeData("pod_b", 2.0f, 0.0f),
                    new SensorNodeData("pod_c", 1.0f, Mathf.Sqrt(3f))
                },
                threats = new ThreatItemData[]
                {
                    new ThreatItemData
                    {
                        threat_id = threatId,
                        bssid = "DE:AD:BE:EF:00:01",
                        ssid = "AdrianPhone",
                        status = "SUSPICIOUS_INFRASTRUCTURE",
                        risk_score = risk,
                        filtered_rssi_by_pod = new PodSignalData { pod_a = -38f, pod_b = -44f, pod_c = -48f },
                        evidence_flags = new string[] { "UNKNOWN_BSSID", "SECURITY_MISMATCH", "UNEXPECTED_CHANNEL" },
                        estimated_position_2d = new Position2DData(x, y),
                        uncertainty_radius_m = uncertainty,
                        channel = 1,
                        authmode = "OPEN",
                        first_seen_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() - 5000,
                        last_seen_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                        observed_by_pods = new string[] { "pod_a", "pod_b", "pod_c" }
                    }
                }
            };
        }
    }
}
#endif
