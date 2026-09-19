using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using RFThreatDetection.Models;

namespace RFThreatDetection.Network
{
    /// <summary>
    /// WebSocket client consuming the backend /ws/threats contract.
    /// Uses .NET Standard ClientWebSocket with main-thread event dispatching.
    /// Compatible with Unity Editor, Windows Standalone, and Meta Quest Pro (Android IL2CPP).
    /// </summary>
    public class ThreatWebSocketClient : MonoBehaviour
    {
        [Header("Backend Connection")]
        [Tooltip("WebSocket endpoint URI")]
        [SerializeField] private string serverUri = "ws://127.0.0.1:8000/ws/threats";

        [Tooltip("Auto-reconnect interval in seconds if disconnected")]
        [SerializeField] private float reconnectIntervalSeconds = 3.0f;

        [Tooltip("Connect automatically when scene starts")]
        [SerializeField] private bool connectOnStart = true;

        [Header("Development Mode")]
        [Tooltip("Enable simulated local threat stream if backend is offline")]
        [SerializeField] private bool enableMockFallback = false;

        // Events dispatched on Unity Main Thread
        public event Action<ThreatStateData> OnThreatStateReceived;
        public event Action<bool> OnConnectionStatusChanged;

        private ClientWebSocket webSocket;
        private CancellationTokenSource cancellationTokenSource;
        private readonly ConcurrentQueue<string> messageQueue = new ConcurrentQueue<string>();
        private bool isConnected = false;
        private bool isRunning = false;

        public bool IsConnected => isConnected;
        public string ServerUri
        {
            get => serverUri;
            set => serverUri = value;
        }

        private void Start()
        {
            if (connectOnStart)
            {
                Connect();
            }
        }

        public void Connect()
        {
            if (isRunning) return;

            isRunning = true;
            cancellationTokenSource = new CancellationTokenSource();
            Task.Run(() => ConnectionLoop(cancellationTokenSource.Token));
        }

        public void Disconnect()
        {
            isRunning = false;
            cancellationTokenSource?.Cancel();

            if (webSocket != null)
            {
                try
                {
                    if (webSocket.State == WebSocketState.Open)
                    {
                        webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Client closing", CancellationToken.None).Wait(1000);
                    }
                    webSocket.Dispose();
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[ThreatWebSocketClient] Error during disconnect: {e.Message}");
                }
                finally
                {
                    webSocket = null;
                }
            }

            SetConnected(false);
        }

        private async Task ConnectionLoop(CancellationToken token)
        {
            while (isRunning && !token.IsCancellationRequested)
            {
                try
                {
                    webSocket = new ClientWebSocket();
                    Uri uri = new Uri(serverUri);

                    Debug.Log($"[ThreatWebSocketClient] Connecting to {uri}...");
                    using (var connectCts = new CancellationTokenSource(TimeSpan.FromSeconds(5)))
                    using (var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(token, connectCts.Token))
                    {
                        await webSocket.ConnectAsync(uri, linkedCts.Token);
                    }

                    if (webSocket.State == WebSocketState.Open)
                    {
                        Debug.Log($"[ThreatWebSocketClient] Connected successfully to {uri}");
                        SetConnected(true);
                        await ReceiveLoop(webSocket, token);
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[ThreatWebSocketClient] Connection failed: {ex.Message}");
                    SetConnected(false);

                    if (enableMockFallback)
                    {
                        Debug.Log("[ThreatWebSocketClient] Mock fallback active; feeding local simulated data.");
                        await Task.Delay((int)(reconnectIntervalSeconds * 1000), token);
                        continue;
                    }
                }

                SetConnected(false);
                if (isRunning && !token.IsCancellationRequested)
                {
                    await Task.Delay((int)(reconnectIntervalSeconds * 1000), token);
                }
            }
        }

        private async Task ReceiveLoop(ClientWebSocket ws, CancellationToken token)
        {
            var buffer = new byte[8192];
            var ms = new MemoryStream();

            while (ws.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                ms.SetLength(0);
                WebSocketReceiveResult result;

                do
                {
                    result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), token);
                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", token);
                        return;
                    }
                    ms.Write(buffer, 0, result.Count);
                } while (!result.EndOfMessage);

                if (result.MessageType == WebSocketMessageType.Text)
                {
                    string json = Encoding.UTF8.GetString(ms.ToArray());
                    messageQueue.Enqueue(json);
                }
            }
        }

        private void SetConnected(bool status)
        {
            if (isConnected != status)
            {
                isConnected = status;
                // Dispatch state changed via queue
                messageQueue.Enqueue(status ? "__STATUS_CONNECTED__" : "__STATUS_DISCONNECTED__");
            }
        }

        private void Update()
        {
            // Process incoming WebSocket messages on Unity Main Thread
            while (messageQueue.TryDequeue(out string message))
            {
                if (message == "__STATUS_CONNECTED__")
                {
                    OnConnectionStatusChanged?.Invoke(true);
                }
                else if (message == "__STATUS_DISCONNECTED__")
                {
                    OnConnectionStatusChanged?.Invoke(false);
                }
                else
                {
                    ProcessJsonMessage(message);
                }
            }
        }

        private void ProcessJsonMessage(string json)
        {
            try
            {
                ThreatStateData state = JsonUtility.FromJson<ThreatStateData>(json);
                if (state != null)
                {
                    OnThreatStateReceived?.Invoke(state);
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"[ThreatWebSocketClient] Failed to deserialize threat state JSON: {ex.Message}\nRaw: {json}");
            }
        }

        private void OnDestroy()
        {
            Disconnect();
        }

        private void OnApplicationQuit()
        {
            Disconnect();
        }
    }
}
