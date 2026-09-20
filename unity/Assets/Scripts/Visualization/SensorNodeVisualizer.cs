using System.Collections.Generic;
using UnityEngine;
using RFThreatDetection.Models;
using RFThreatDetection.Spatial;

namespace RFThreatDetection.Visualization
{
    /// <summary>
    /// Renders physical sensor node markers (Pods A, B, C) and reference boundary lines
    /// outlining the enclosed monitoring area in Meta Quest space.
    /// </summary>
    public class SensorNodeVisualizer : MonoBehaviour
    {
        [Header("Dependencies")]
        [SerializeField] private RoomCoordinateTransformer transformer;

        [Header("Appearance")]
        [SerializeField] private Color nodeColor = new Color(0.2f, 0.8f, 1.0f, 0.9f); // Cyan
        [SerializeField] private Color boundaryLineColor = new Color(0.2f, 0.8f, 1.0f, 0.35f);
        [SerializeField] private float nodeRadius = 0.12f;

        private readonly Dictionary<string, GameObject> podObjects = new Dictionary<string, GameObject>();
        private LineRenderer boundaryRenderer;
        private SensorNodeData[] latestNodes = {
            new SensorNodeData("pod_a", 0f, 0f),
            new SensorNodeData("pod_b", 2f, 0f),
            new SensorNodeData("pod_c", 1f, Mathf.Sqrt(3f))
        };
        private readonly Dictionary<string, Vector3> placementPreviews = new Dictionary<string, Vector3>();

        public void SetPlacementPreview(int index, Vector3 floorPosition)
        {
            placementPreviews["pod_" + (char)('a' + index)] = floorPosition + Vector3.up * 0.05f;
            UpdateSensorNodes(latestNodes);
        }

        public void ClearPlacementPreviews()
        {
            placementPreviews.Clear();
            UpdateSensorNodes(latestNodes);
        }

        private void LateUpdate()
        {
            // Calibration must remain responsive even without backend messages.
            UpdateSensorNodes(latestNodes);
        }

        private void Awake()
        {
            EnsureTransformer();
        }

        private void EnsureTransformer()
        {
            if (transformer == null)
            {
                transformer = GetComponent<RoomCoordinateTransformer>();
                if (transformer == null)
                {
                    transformer = FindAnyObjectByType<RoomCoordinateTransformer>();
                }
            }
        }

        public void UpdateSensorNodes(SensorNodeData[] nodes)
        {
            EnsureTransformer();
            if (nodes == null || nodes.Length == 0 || transformer == null) return;

            latestNodes = nodes;
            EnsureBoundaryLineRenderer();
            List<Vector3> worldPositions = new List<Vector3>();

            foreach (var node in nodes)
            {
                // Keep the room footprint on the physical floor so the wearer stands
                // inside the triangle instead of looking through a floating wireframe.
                Vector3 worldPos = transformer.TransformSensorNode(node.x, node.y, 0.05f);
                bool preview = placementPreviews.TryGetValue(node.pod_id, out Vector3 placed);
                if (preview) worldPos = placed;
                worldPositions.Add(worldPos);

                if (!podObjects.TryGetValue(node.pod_id, out GameObject podObj))
                {
                    podObj = CreatePodMarker(node.pod_id);
                    podObjects[node.pod_id] = podObj;
                }

                podObj.transform.position = worldPos;
                SetMaterialColor(podObj.GetComponent<Renderer>().material,
                    preview ? new Color(1f, 0.76f, 0.18f, 1f) : nodeColor);
            }

            UpdateBoundaryLines(worldPositions);
        }

        private GameObject CreatePodMarker(string podId)
        {
            Transform existing = transform.Find($"SensorNode_{podId}");
            if (existing != null)
                return existing.gameObject;

            GameObject pod = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            pod.name = $"SensorNode_{podId}";
            pod.transform.SetParent(this.transform, false);
            pod.transform.localScale = new Vector3(nodeRadius * 2f, 0.05f, nodeRadius * 2f);

            Collider col = pod.GetComponent<Collider>();
            SafeDestroy(col);

            Renderer r = pod.GetComponent<Renderer>();
            if (r != null)
            {
                Shader shader = Resources.Load<Shader>("Shaders/SolidUnlit");
                if (shader == null) shader = Shader.Find("RFThreat/SolidUnlit");
                if (shader != null) r.material = new Material(shader);
                SetMaterialColor(r.material, nodeColor);
            }

            // Add label above pod
            GameObject label = new GameObject("Label");
            label.transform.SetParent(pod.transform, false);
            label.transform.localPosition = new Vector3(0f, 2.5f, 0f);

            TextMesh tm = label.AddComponent<TextMesh>();
            tm.text = podId.ToUpper();
            tm.fontSize = 20;
            tm.characterSize = 0.04f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = Color.white;

            return pod;
        }

        private void EnsureBoundaryLineRenderer()
        {
            if (boundaryRenderer == null)
            {
                boundaryRenderer = GetComponent<LineRenderer>();
                if (boundaryRenderer == null)
                    boundaryRenderer = gameObject.AddComponent<LineRenderer>();
                if (boundaryRenderer == null) return;
                boundaryRenderer.loop = true;
                boundaryRenderer.startWidth = 0.02f;
                boundaryRenderer.endWidth = 0.02f;
                Shader shader = Resources.Load<Shader>("Shaders/SolidUnlit");
                if (shader == null) shader = Shader.Find("RFThreat/SolidUnlit");
                if (shader != null) boundaryRenderer.material = new Material(shader);
                SetMaterialColor(boundaryRenderer.material, boundaryLineColor);
                boundaryRenderer.startColor = boundaryLineColor;
                boundaryRenderer.endColor = boundaryLineColor;
            }
        }

        private static void SetMaterialColor(Material material, Color color)
        {
            if (material == null) return;
            if (material.HasProperty("_Color")) material.SetColor("_Color", color);
        }

        private void UpdateBoundaryLines(List<Vector3> positions)
        {
            if (boundaryRenderer == null || positions.Count < 3) return;

            boundaryRenderer.positionCount = positions.Count;
            for (int i = 0; i < positions.Count; i++)
            {
                boundaryRenderer.SetPosition(i, positions[i]);
            }
        }

        private static void SafeDestroy(UnityEngine.Object obj)
        {
            if (obj == null) return;
            if (Application.isPlaying)
            {
                Destroy(obj);
            }
            else
            {
                DestroyImmediate(obj);
            }
        }
    }
}
