#if UNITY_EDITOR
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace RFThreatDetection.Editor
{
    /// <summary>
    /// Reproducible local Quest build entry point. Build output stays outside
    /// version control under Builds/Quest.
    /// </summary>
    public static class QuestBuildHelper
    {
        private const string OutputPath = "Builds/Quest/RFThreatDetection-dev.apk";

        [MenuItem("RF Threat Detection/Build Quest Development APK", false, 20)]
        public static void BuildDevelopmentApk()
        {
            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            {
                Debug.LogError("[QUEST BUILD] Switch the active build target to Android before building.");
                return;
            }

            string[] scenes = EditorBuildSettings.scenes
                .Where(scene => scene.enabled)
                .Select(scene => scene.path)
                .ToArray();

            if (scenes.Length == 0)
            {
                Debug.LogError("[QUEST BUILD] No enabled scenes are present in Build Settings.");
                return;
            }

            Directory.CreateDirectory(Path.GetDirectoryName(OutputPath));
            BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = OutputPath,
                target = BuildTarget.Android,
                options = BuildOptions.Development
            });

            BuildSummary summary = report.summary;
            string message = $"[QUEST BUILD] {summary.result} | errors={summary.totalErrors} | " +
                             $"warnings={summary.totalWarnings} | size={summary.totalSize} bytes | " +
                             $"time={summary.totalTime} | {OutputPath}";

            if (summary.result == BuildResult.Succeeded)
                Debug.Log(message);
            else
                Debug.LogError(message);
        }
    }
}
#endif
