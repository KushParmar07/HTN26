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

        private void Awake()
        {
            EnsureTransformer();
            EnsureBoundaryLineRenderer();
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

            List<Vector3> worldPositions = new List<Vector3>();

            foreach (var node in nodes)
            {
                Vector3 worldPos = transformer.TransformSensorNode(node.x, node.y);
                worldPositions.Add(worldPos);

                if (!podObjects.TryGetValue(node.pod_id, out GameObject podObj))
                {
                    podObj = CreatePodMarker(node.pod_id);
                    podObjects[node.pod_id] = podObj;
                }

                podObj.transform.position = worldPos;
            }

            UpdateBoundaryLines(worldPositions);
        }

        private GameObject CreatePodMarker(string podId)
        {
            GameObject pod = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            pod.name = $"SensorNode_{podId}";
            pod.transform.SetParent(this.transform, false);
            pod.transform.localScale = new Vector3(nodeRadius * 2f, 0.05f, nodeRadius * 2f);

            Collider col = pod.GetComponent<Collider>();
            SafeDestroy(col);

            Renderer r = pod.GetComponent<Renderer>();
            if (r != null)
            {
                r.material.color = nodeColor;
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
                boundaryRenderer = gameObject.AddComponent<LineRenderer>();
                boundaryRenderer.loop = true;
                boundaryRenderer.startWidth = 0.02f;
                boundaryRenderer.endWidth = 0.02f;
                boundaryRenderer.material = new Material(Shader.Find("Sprites/Default"));
                boundaryRenderer.startColor = boundaryLineColor;
                boundaryRenderer.endColor = boundaryLineColor;
            }
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
