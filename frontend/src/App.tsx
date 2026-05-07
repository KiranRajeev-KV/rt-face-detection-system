import { useEffect, useRef, useState } from "react";

type RoiItem = {
  frame_id: number;
  timestamp_ms: number;
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number | null;
  frame_width: number;
  frame_height: number;
  detector_name: string;
  created_at: string;
};

type FrameResult = {
  type: "frame_result";
  session_id: string;
  frame_id: number;
  has_face: boolean;
  roi: null | {
    x: number;
    y: number;
    width: number;
    height: number;
    confidence: number | null;
    frame_width: number;
    frame_height: number;
  };
  processing_ms: number;
  warning: string | null;
};

type FrameError = {
  type: "frame_error";
  session_id: string;
  frame_id: number | null;
  detail: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000";
const DEFAULT_FPS = 5;

function createSessionId(): string {
  return crypto.randomUUID();
}

async function fetchRoiHistory(sessionId: string): Promise<RoiItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/roi?session_id=${sessionId}&limit=10`);
  if (!response.ok) {
    if (response.status === 404) {
      return [];
    }
    throw new Error(`ROI request failed with status ${response.status}`);
  }
  const body = await response.json();
  return body.items as RoiItem[];
}

function App() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const inFlightRef = useRef(false);
  const frameIdRef = useRef(0);

  const [sessionId, setSessionId] = useState<string>(() => createSessionId());
  const [status, setStatus] = useState("idle");
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [latestResult, setLatestResult] = useState<FrameResult | null>(null);
  const [roiHistory, setRoiHistory] = useState<RoiItem[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  const [sentFrames, setSentFrames] = useState(0);
  const [receivedFrames, setReceivedFrames] = useState(0);

  useEffect(() => {
    return () => {
      stopStreaming();
    };
  }, []);

  useEffect(() => {
    if (status !== "streaming") {
      return;
    }
    const poll = window.setInterval(() => {
      void fetchRoiHistory(sessionId)
        .then(setRoiHistory)
        .catch((error: Error) => setErrorMessage(error.message));
    }, 2000);
    return () => window.clearInterval(poll);
  }, [sessionId, status]);

  async function startStreaming() {
    setErrorMessage(null);
    setWarningMessage(null);
    setStreamUrl(null);
    setLatestResult(null);
    setRoiHistory([]);
    setSentFrames(0);
    setReceivedFrames(0);
    frameIdRef.current = 0;
    inFlightRef.current = false;

    const nextSessionId = createSessionId();
    setSessionId(nextSessionId);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
        audio: false,
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      const socket = new WebSocket(`${WS_BASE_URL}/api/v1/video/feed?session_id=${nextSessionId}`);
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;

      socket.onopen = () => {
        setStatus("streaming");
        setStreamUrl(`${API_BASE_URL}/api/v1/video/stream?session_id=${nextSessionId}`);
        timerRef.current = window.setInterval(() => {
          void captureAndSendFrame();
        }, 1000 / DEFAULT_FPS);
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data) as FrameResult | FrameError;
        inFlightRef.current = false;
        if (data.type === "frame_error") {
          setErrorMessage(data.detail);
          return;
        }
        setReceivedFrames((value) => value + 1);
        setLatestResult(data);
        setWarningMessage(data.warning);
      };

      socket.onerror = () => {
        setErrorMessage("WebSocket connection failed");
      };

      socket.onclose = () => {
        setStatus("stopped");
        setStreamUrl(null);
        setLatestResult(null);
        clearCaptureTimer();
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to start webcam";
      setErrorMessage(message);
      stopStreaming();
    }
  }

  function stopStreaming() {
    clearCaptureTimer();
    if (socketRef.current && socketRef.current.readyState < WebSocket.CLOSING) {
      socketRef.current.close();
    }
    socketRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setStreamUrl(null);
    setLatestResult(null);
    setStatus("stopped");
  }

  function clearCaptureTimer() {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  async function captureAndSendFrame() {
    if (!videoRef.current || !canvasRef.current || !socketRef.current) {
      return;
    }
    if (socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    if (inFlightRef.current) {
      return;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext("2d");
    if (!context || video.videoWidth === 0 || video.videoHeight === 0) {
      return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.8));
    if (!blob) {
      setErrorMessage("Frame capture failed");
      return;
    }

    const imageBuffer = await blob.arrayBuffer();
    const metadata = {
      frame_id: frameIdRef.current,
      timestamp_ms: Date.now(),
      content_type: "image/jpeg",
    };
    const metadataBytes = new TextEncoder().encode(JSON.stringify(metadata));
    const payload = new Uint8Array(4 + metadataBytes.length + imageBuffer.byteLength);
    const view = new DataView(payload.buffer);
    view.setUint32(0, metadataBytes.length);
    payload.set(metadataBytes, 4);
    payload.set(new Uint8Array(imageBuffer), 4 + metadataBytes.length);

    socketRef.current.send(payload);
    inFlightRef.current = true;
    frameIdRef.current += 1;
    setSentFrames((value) => value + 1);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Mega AI Hiring Assignment</p>
          <h1>Real-Time Face ROI Monitor</h1>
        </div>
        <div className="status-cluster">
          <span className={`status-pill status-${status}`}>{status}</span>
          <span className="session-pill">{sessionId.slice(0, 8)}</span>
        </div>
      </header>

      <main className="dashboard">
        <section className="panel controls-panel">
          <div className="panel-heading">
            <h2>Session Control</h2>
            <p>Browser webcam to FastAPI over bounded WebSocket uploads.</p>
          </div>
          <div className="actions">
            <button type="button" className="action-button primary" onClick={() => void startStreaming()}>
              Start
            </button>
            <button type="button" className="action-button" onClick={stopStreaming}>
              Stop
            </button>
          </div>
          <div className="metrics-grid">
            <article>
              <span>Frames sent</span>
              <strong>{sentFrames}</strong>
            </article>
            <article>
              <span>Frames returned</span>
              <strong>{receivedFrames}</strong>
            </article>
            <article>
              <span>Latency</span>
              <strong>{latestResult ? `${latestResult.processing_ms} ms` : "n/a"}</strong>
            </article>
            <article>
              <span>Feed endpoint</span>
              <strong>/api/v1/video/feed</strong>
            </article>
          </div>
          {errorMessage ? <p className="message error">{errorMessage}</p> : null}
          {warningMessage ? <p className="message warning">{warningMessage}</p> : null}
        </section>

        <section className="panel video-panel">
          <div className="panel-heading">
            <h2>Local Camera</h2>
            <p>Sampling at {DEFAULT_FPS} FPS and skipping while the backend is still busy.</p>
          </div>
          <video ref={videoRef} className="video-tile" autoPlay muted playsInline />
          <canvas ref={canvasRef} hidden />
        </section>

        <section className="panel video-panel">
          <div className="panel-heading">
            <h2>Annotated Result</h2>
            <p>Rendered from the processed MJPEG stream after MediaPipe detection and Pillow drawing.</p>
          </div>
          {streamUrl !== null ? (
            <img className="video-tile" src={streamUrl} alt="Annotated backend stream" />
          ) : (
            <div className="placeholder-tile">Processed frame will appear here.</div>
          )}
        </section>

        <section className="panel roi-panel">
          <div className="panel-heading">
            <h2>Latest ROI</h2>
            <p>Minimal axis-aligned bounding box selected from the highest-confidence face.</p>
          </div>
          <div className="roi-stats">
            <div><span>x</span><strong>{latestResult?.roi?.x ?? "n/a"}</strong></div>
            <div><span>y</span><strong>{latestResult?.roi?.y ?? "n/a"}</strong></div>
            <div><span>width</span><strong>{latestResult?.roi?.width ?? "n/a"}</strong></div>
            <div><span>height</span><strong>{latestResult?.roi?.height ?? "n/a"}</strong></div>
            <div><span>confidence</span><strong>{latestResult?.roi?.confidence?.toFixed(3) ?? "n/a"}</strong></div>
            <div><span>has_face</span><strong>{latestResult?.has_face ? "true" : "false"}</strong></div>
          </div>
        </section>

        <section className="panel history-panel">
          <div className="panel-heading">
            <h2>ROI History</h2>
            <p>Latest persisted rows from PostgreSQL.</p>
          </div>
          <div className="history-table">
            <div className="history-row history-head">
              <span>frame</span>
              <span>timestamp</span>
              <span>roi</span>
              <span>confidence</span>
            </div>
            {roiHistory.length === 0 ? (
              <div className="history-row empty-row">
                <span>No stored detections yet.</span>
              </div>
            ) : (
              roiHistory.map((item) => (
                <div className="history-row" key={`${item.frame_id}-${item.created_at}`}>
                  <span>{item.frame_id}</span>
                  <span>{item.timestamp_ms}</span>
                  <span>{item.x},{item.y} {item.width}x{item.height}</span>
                  <span>{item.confidence?.toFixed(3) ?? "n/a"}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
