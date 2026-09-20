using System;

namespace RFThreatDetection.Models
{
    [Serializable]
    public class PodSignalData
    {
        public float pod_a;
        public float pod_b;
        public float pod_c;
        public float StrongestDbm()
        {
            float best = -127f;
            foreach (float value in new[] { pod_a, pod_b, pod_c })
                if (value < 0f && value >= -127f) best = Math.Max(best, value);
            return best;
        }

        public float AverageDbm()
        {
            float total = 0f;
            int count = 0;
            foreach (float value in new[] { pod_a, pod_b, pod_c })
            {
                if (value >= 0f || value < -127f) continue;
                total += value;
                count++;
            }
            return count == 0 ? -127f : total / count;
        }
    }

    [Serializable]
    public class Position2DData
    {
        public float x;
        public float y;

        public Position2DData() { }

        public Position2DData(float x, float y)
        {
            this.x = x;
            this.y = y;
        }

        public override string ToString()
        {
            return string.Format("({0:F2}, {1:F2})", x, y);
        }
    }

    [Serializable]
    public class SensorNodeData
    {
        public string pod_id;
        public float x;
        public float y;

        public SensorNodeData() { }

        public SensorNodeData(string podId, float x, float y)
        {
            this.pod_id = podId;
            this.x = x;
            this.y = y;
        }
    }

    [Serializable]
    public class ThreatItemData
    {
        public string threat_id;
        public string bssid;
        public string ssid;
        public string status;
        public float risk_score;
        public string[] evidence_flags;
        public Position2DData estimated_position_2d;
        public float uncertainty_radius_m;
        public int channel;
        public string authmode;
        public long first_seen_ms;
        public long last_seen_ms;
        public string[] observed_by_pods;
        public PodSignalData filtered_rssi_by_pod;
        public float StrongestDbm => filtered_rssi_by_pod?.StrongestDbm() ?? -127f;
        public float SignalScoreDbm => filtered_rssi_by_pod?.AverageDbm() ?? -127f;

        [NonSerialized] public bool isBelowThreshold;

        public bool HasEstimatedPosition()
        {
            return estimated_position_2d != null;
        }

        public bool HasStableLocalization()
        {
            if (estimated_position_2d == null || observed_by_pods == null ||
                observed_by_pods.Length < 3) return false;
            return !float.IsNaN(estimated_position_2d.x) && !float.IsInfinity(estimated_position_2d.x) &&
                   !float.IsNaN(estimated_position_2d.y) && !float.IsInfinity(estimated_position_2d.y);
        }

        public string GetFormattedEvidenceFlags()
        {
            if (evidence_flags == null || evidence_flags.Length == 0)
                return "None";
            return string.Join(", ", evidence_flags);
        }

        public string GetPositionConfidence()
        {
            if (uncertainty_radius_m <= 0.65f) return "HIGH";
            if (uncertainty_radius_m <= 1.25f) return "MEDIUM";
            return "LOW";
        }
    }

    [Serializable]
    public class ThreatStateData
    {
        public string version;
        public long generated_at_ms;
        public SensorNodeData[] sensor_nodes;
        public ThreatItemData[] threats;
        public ThreatItemData[] active_threats;
        public ThreatItemData[] monitored_aps;

        public static bool FocusTargetOnly = false;
        public const string DemoTargetSsid = "AdrianPhone";

        public ThreatItemData[] GetDemoSources()
        {
            var near = new System.Collections.Generic.List<ThreatItemData>(GetDisplayCandidates());
            if (near.Count > 3) near.RemoveRange(3, near.Count - 3);
            return near.ToArray();
        }

        public ThreatItemData[] GetDisplayCandidates()
        {
            var byRadio = new System.Collections.Generic.Dictionary<string, ThreatItemData>();
            foreach (var item in GetPresentSources())
            {
                if (!item.HasStableLocalization()) continue;
                string radioId = GetPhysicalRadioIdentity(item.bssid);
                if (!byRadio.TryGetValue(radioId, out ThreatItemData existing) ||
                    item.SignalScoreDbm > existing.SignalScoreDbm)
                    byRadio[radioId] = item;
            }
            var near = new System.Collections.Generic.List<ThreatItemData>(byRadio.Values);
            near.Sort((a, b) => {
                int order = b.SignalScoreDbm.CompareTo(a.SignalScoreDbm);
                return order != 0 ? order : string.CompareOrdinal(a.threat_id, b.threat_id);
            });
            return near.ToArray();
        }

        public ThreatItemData[] GetPresentSources()
        {
            var present = new System.Collections.Generic.List<ThreatItemData>();
            foreach (var item in GetVisibleSources())
            {
                if (item == null || IsIgnoredInfrastructure(item)) continue;
                if (FocusTargetOnly && !string.Equals(item.ssid, DemoTargetSsid, StringComparison.Ordinal)) continue;
                present.Add(item);
            }
            return present.ToArray();
        }

        public static string GetPhysicalRadioIdentity(string bssid)
        {
            if (string.IsNullOrWhiteSpace(bssid)) return bssid ?? string.Empty;
            string[] octets = bssid.Split(':');
            if (octets.Length != 6 || !byte.TryParse(octets[0],
                System.Globalization.NumberStyles.HexNumber,
                System.Globalization.CultureInfo.InvariantCulture, out byte first))
                return bssid.ToUpperInvariant();
            // Clear the locally-administered bit. APs commonly expose paired
            // open/secured BSSIDs that only differ by this bit.
            octets[0] = (first & 0xFD).ToString("X2");
            return string.Join(":", octets).ToUpperInvariant();
        }

        public static bool IsIgnoredInfrastructure(ThreatItemData item)
        {
            if (item == null) return true;
            if (string.Equals(item.ssid, "WMBY 2056", StringComparison.OrdinalIgnoreCase))
                return true;
            if (!string.IsNullOrEmpty(item.ssid) &&
                item.ssid.StartsWith("DIRECT-Meta-", StringComparison.OrdinalIgnoreCase))
                return true;
            // Laptop-hosted transport BSSID on this machine.
            return string.Equals(item.bssid, "46:F7:9F:3B:26:7B", StringComparison.OrdinalIgnoreCase);
        }

        public static bool IsInsidePodTriangle(Position2DData point)
        {
            if (point == null) return false;
            const float height = 1.7320508f;
            const float tolerance = 0.12f;
            if (point.y < -tolerance || point.y > height + tolerance) return false;
            float leftEdge = point.y / height;
            float rightEdge = 2f - leftEdge;
            return point.x >= leftEdge - tolerance && point.x <= rightEdge + tolerance;
        }

        public ThreatItemData[] GetVisibleSources()
        {
            var result = new System.Collections.Generic.List<ThreatItemData>();
            var ids = new System.Collections.Generic.HashSet<string>();
            foreach (var item in GetActiveThreats())
            {
                if (item == null || !ids.Add(item.threat_id)) continue;
                item.isBelowThreshold = false;
                result.Add(item);
            }
            foreach (var item in monitored_aps ?? new ThreatItemData[0])
            {
                if (item == null || !ids.Add(item.threat_id)) continue;
                item.isBelowThreshold = true;
                result.Add(item);
            }
            return result.ToArray();
        }


        public ThreatItemData[] GetActiveThreats()
        {
            if (threats != null && threats.Length > 0)
                return threats;
            if (active_threats != null && active_threats.Length > 0)
                return active_threats;
            return new ThreatItemData[0];
        }
    }
}
