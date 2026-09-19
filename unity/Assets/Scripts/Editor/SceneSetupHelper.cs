#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using RFThreatDetection.Dev;
using RFThreatDetection.Network;
using RFThreatDetection.Spatial;
using RFThreatDetection.Visualization;

namespace RFThreatDetection.Editor
{
    /// <summary>
    /// Editor helper to programmatically generate or configure the main threat visualization demo scene.
    /// Developer 2 can simply run this menu command after importing the project into Unity 6.3 LTS.
    /// </summary>
    public static class SceneSetupHelper
    {
        private const string SceneDirectory = "Assets/Scenes";
        private const string ScenePath = "Assets/Scenes/MainThreatVisualization.unity";

        [MenuItem("RF Threat Detection/Setup Demo Scene", false, 1)]
        public static void SetupDemoScene()
        {
            // Ensure Assets/Scenes directory exists
            if (!AssetDatabase.IsValidFolder(SceneDirectory))
            {
                AssetDatabase.CreateFolder("Assets", "Scenes");
            }

            // Create new empty scene or edit current scene
            Scene currentScene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // 1. Setup Main Camera
            GameObject cameraObj = new GameObject("Main Camera");
            cameraObj.tag = "MainCamera";
            Camera cam = cameraObj.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.05f, 0.07f, 0.12f, 1.0f);
            cam.nearClipPlane = 0.1f;
            cam.farClipPlane = 100f;
            cameraObj.AddComponent<AudioListener>();
            
            // Position camera looking at the demo room space
            cameraObj.transform.position = new Vector3(2.0f, 1.6f, -1.0f);
            cameraObj.transform.rotation = Quaternion.Euler(15f, 0f, 0f);

            // 2. Setup Directional Light
            GameObject lightObj = new GameObject("Directional Light");
            Light light = lightObj.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = Color.white;
            light.intensity = 1.0f;
            lightObj.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            // 3. Setup RF Threat System Root
            GameObject rfSystemObj = new GameObject("[RFThreatSystem]");
            rfSystemObj.transform.position = Vector3.zero;

            // Add Core Subsystems
            RoomCoordinateTransformer transformer = rfSystemObj.AddComponent<RoomCoordinateTransformer>();
            ThreatWebSocketClient wsClient = rfSystemObj.AddComponent<ThreatWebSocketClient>();
            SensorNodeVisualizer sensorVisualizer = rfSystemObj.AddComponent<SensorNodeVisualizer>();
            ThreatVisualizationManager vizManager = rfSystemObj.AddComponent<ThreatVisualizationManager>();
            QuestPassthroughManager passthroughManager = rfSystemObj.AddComponent<QuestPassthroughManager>();
            QuestDevTestRunner devRunner = rfSystemObj.AddComponent<QuestDevTestRunner>();

            // Save the scene
            EditorSceneManager.SaveScene(currentScene, ScenePath);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log($"[SceneSetupHelper] Successfully built and saved demo scene to '{ScenePath}'!");
            if (!Application.isBatchMode)
            {
                EditorUtility.DisplayDialog(
                    "RF Threat Detection Scene Setup",
                    $"Demo scene created successfully at:\n{ScenePath}\n\nYou can now press Play in the Unity Editor to test with mock threat data, or connect to the running Python backend via 'ws://127.0.0.1:8000/ws/threats'.",
                    "OK"
                );
            }
        }
    }
}
#endif
