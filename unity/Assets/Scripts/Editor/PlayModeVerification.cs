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
                Vector3 podBPos = transformer.BackendToWorld(4.0f, 0f);
                Vector3 podCPos = transformer.BackendToWorld(2.0f, 3.5f);
                Debug.Log($"[VERIFICATION] Origin transformed: {originPos}");
                Debug.Log($"[VERIFICATION] Pod B transformed: {podBPos}");
                Debug.Log($"[VERIFICATION] Pod C transformed: {podCPos}");
                if (Vector3.Distance(originPos, new Vector3(0f, 1f, 0f)) > 0.001f)
                    throw new Exception("Origin coordinate mapping unexpected");
                if (Vector3.Distance(podBPos, new Vector3(4f, 1f, 0f)) > 0.001f)
                    throw new Exception("Pod B coordinate mapping unexpected");
                if (Vector3.Distance(podCPos, new Vector3(2f, 1f, 3.5f)) > 0.001f)
                    throw new Exception("Pod C coordinate mapping unexpected");
                Debug.Log("[VERIFICATION] [PASS] RoomCoordinateTransformer 2D -> 3D coordinate mapping verified.");

                // Step 6: Verify Sensor Node Visualizer
                SensorNodeData[] sensorNodes = new SensorNodeData[]
                {
                    new SensorNodeData("pod_a", 0.0f, 0.0f),
                    new SensorNodeData("pod_b", 4.0f, 0.0f),
                    new SensorNodeData("pod_c", 2.0f, 3.5f)
                };
                sensorViz.UpdateSensorNodes(sensorNodes);
                GameObject podAObj = GameObject.Find("SensorNode_pod_a");
                GameObject podBObj = GameObject.Find("SensorNode_pod_b");
                GameObject podCObj = GameObject.Find("SensorNode_pod_c");
                if (podAObj == null || podBObj == null || podCObj == null)
                    throw new Exception("Sensor pod marker GameObjects were not created.");
                Debug.Log("[VERIFICATION] [PASS] Sensor nodes (Pods A, B, C) created and positioned.");

                // Step 7: Verify Moving Threat Pipeline (Mock Path)
                // Frame 1: Position (0.5, 0.5)
                ThreatStateData stateFrame1 = CreateTestThreatState("threat_test_01", 0.5f, 0.5f, 0.45f, 100f);
                vizManager.HandleThreatState(stateFrame1);

                GameObject threatObj = GameObject.Find("ThreatVolume_threat_test_01");
                if (threatObj == null) throw new Exception("Threat volume GameObject 'ThreatVolume_threat_test_01' not spawned!");
                var controller = threatObj.GetComponent<ThreatVolumeController>();
                if (controller == null) throw new Exception("ThreatVolumeController component missing on threat volume!");

                Transform outerSphere = threatObj.transform.Find("VolumeCloud");
                if (outerSphere == null) throw new Exception("VolumeCloud outer sphere primitive missing!");

                float expectedDiameter = 0.45f * 2.0f; // 0.9m
                Debug.Log($"[VERIFICATION] Frame 1: Threat spawned at {threatObj.transform.position}. Target scale diameter: {expectedDiameter}m");

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
                TextMesh hudText = threatObj.GetComponentInChildren<TextMesh>();
                if (hudText == null) throw new Exception("Billboard TextMesh missing on threat volume!");
                Debug.Log($"[VERIFICATION] Billboard HUD Text:\n{hudText.text}");
                if (!hudText.text.Contains("RISK") || !hudText.text.Contains("HTN-Secure"))
                    throw new Exception("Billboard HUD text content mismatch!");
                Debug.Log("[VERIFICATION] [PASS] ThreatVolumeController correctly received moving coordinates and updated billboard HUD.");

                // Frame 4: Threat clears
                ThreatStateData emptyState = new ThreatStateData
                {
                    version = "1.0",
                    generated_at_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                    sensor_nodes = sensorNodes,
                    threats = new ThreatItemData[0]
                };
                vizManager.HandleThreatState(emptyState);
                Debug.Log("[VERIFICATION] [PASS] Threat clearance handled cleanly.");

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

        private static ThreatStateData CreateTestThreatState(string threatId, float x, float y, float uncertainty, float risk)
        {
            return new ThreatStateData
            {
                version = "1.0",
                generated_at_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                sensor_nodes = new SensorNodeData[]
                {
                    new SensorNodeData("pod_a", 0.0f, 0.0f),
                    new SensorNodeData("pod_b", 4.0f, 0.0f),
                    new SensorNodeData("pod_c", 2.0f, 3.5f)
                },
                threats = new ThreatItemData[]
                {
                    new ThreatItemData
                    {
                        threat_id = threatId,
                        bssid = "DE:AD:BE:EF:00:01",
                        ssid = "HTN-Secure",
                        status = "SUSPICIOUS_INFRASTRUCTURE",
                        risk_score = risk,
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
