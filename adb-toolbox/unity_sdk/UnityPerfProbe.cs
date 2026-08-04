using System;
using System.IO;
using UnityEngine;

public class UnityPerfProbe : MonoBehaviour
{
    [SerializeField] private string outputFile = "unity_perf_probe.jsonl";
    [SerializeField] private float flushIntervalSec = 0.25f;

    private float _elapsed;
    private int _frameCount;
    private string _outputPath = "";

    [Serializable]
    private class FramePayload
    {
        public long timestamp_ms;
        public float fps;
        public float frame_time_ms;
        public float unscaled_delta_ms;
    }

    private void Start()
    {
        _outputPath = Path.Combine(Application.persistentDataPath, outputFile);
    }

    private void Update()
    {
        _elapsed += Time.unscaledDeltaTime;
        _frameCount++;
        if (_elapsed < flushIntervalSec)
        {
            return;
        }

        float fps = _frameCount / Mathf.Max(_elapsed, 0.0001f);
        float frameMs = 1000f / Mathf.Max(fps, 0.0001f);

        var payload = new FramePayload
        {
            timestamp_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            fps = fps,
            frame_time_ms = frameMs,
            unscaled_delta_ms = Time.unscaledDeltaTime * 1000f
        };

        string json = JsonUtility.ToJson(payload);
        File.AppendAllText(_outputPath, json + "\n");

        _elapsed = 0f;
        _frameCount = 0;
    }
}
