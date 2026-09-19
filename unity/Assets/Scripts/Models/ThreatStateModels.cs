using System;

namespace RFThreatDetection.Models
{
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

        public bool HasEstimatedPosition()
        {
            return estimated_position_2d != null;
        }

        public string GetFormattedEvidenceFlags()
        {
            if (evidence_flags == null || evidence_flags.Length == 0)
                return "None";
            return string.Join(", ", evidence_flags);
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
