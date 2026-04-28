import { useState, useEffect, useRef, useCallback } from 'react';

const MOCK_EVENTS = [
  { violence_prob: 0.12, is_violent: false, detections: { weapons: [], fire_smoke: [] }, alerts: [], progress: 0.1, video_ts: "0:00:03", frame_idx: 30, total_frames: 300 },
  { violence_prob: 0.35, is_violent: false, detections: { weapons: [], fire_smoke: [] }, alerts: [], progress: 0.25, video_ts: "0:00:08", frame_idx: 75, total_frames: 300 },
  { violence_prob: 0.78, is_violent: true, detections: { weapons: [], fire_smoke: [] }, alerts: [{ event_type: "Violence", video_timestamp: "0:00:12", confidence: 0.78, message: "\u{1f6a8} ALERT: Violence detected at 0:00:12 [conf: 0.78]" }], progress: 0.4, video_ts: "0:00:12", frame_idx: 120, total_frames: 300 },
  { violence_prob: 0.92, is_violent: true, detections: { weapons: [{ label: "gun", confidence: 0.89, box: [100,50,200,150] }], fire_smoke: [] }, alerts: [{ event_type: "Gun", video_timestamp: "0:00:18", confidence: 0.89, message: "\u{1f52b} ALERT: Gun detected at 0:00:18 [conf: 0.89]" }], progress: 0.6, video_ts: "0:00:18", frame_idx: 180, total_frames: 300 },
  { violence_prob: 0.45, is_violent: false, detections: { weapons: [], fire_smoke: [{ label: "smoke", confidence: 0.72, box: [50,30,300,200] }] }, alerts: [{ event_type: "Smoke", video_timestamp: "0:00:24", confidence: 0.72, message: "\u{1f4a8} ALERT: Smoke detected at 0:00:24 [conf: 0.72]" }], progress: 0.8, video_ts: "0:00:24", frame_idx: 240, total_frames: 300 },
  { violence_prob: 0.08, is_violent: false, detections: { weapons: [], fire_smoke: [] }, alerts: [], progress: 1.0, video_ts: "0:00:30", frame_idx: 300, total_frames: 300 },
];

export default function useSSEStream(jobId) {
  const [frame, setFrame] = useState(null);
  const [violenceProb, setViolenceProb] = useState(0);
  const [isViolent, setIsViolent] = useState(false);
  const [detections, setDetections] = useState({ weapons: [], fire_smoke: [] });
  const [alerts, setAlerts] = useState([]);
  const [allAlerts, setAllAlerts] = useState([]);
  const [progress, setProgress] = useState(0);
  const [videoTs, setVideoTs] = useState("0:00:00");
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [violenceHistory, setViolenceHistory] = useState([]);
  const [detectionCounts, setDetectionCounts] = useState({});
  const eventSourceRef = useRef(null);
  const isMock = import.meta.env.VITE_MOCK === 'true';

  const startStream = useCallback(() => {
    if (!jobId && !isMock) return;

    setStatus('connecting');
    setError(null);
    setProgress(0);
    setAllAlerts([]);
    setViolenceHistory([]);
    setDetectionCounts({});

    if (isMock) {
      setStatus('streaming');
      let idx = 0;
      const interval = setInterval(() => {
        if (idx >= MOCK_EVENTS.length) {
          clearInterval(interval);
          setStatus('completed');
          return;
        }
        const evt = MOCK_EVENTS[idx];
        setViolenceProb(evt.violence_prob);
        setIsViolent(evt.is_violent);
        setDetections(evt.detections);
        setAlerts(evt.alerts);
        if (evt.alerts.length > 0) {
          setAllAlerts(prev => [...prev, ...evt.alerts]);
          evt.alerts.forEach(a => {
            setDetectionCounts(prev => ({ ...prev, [a.event_type]: (prev[a.event_type] || 0) + 1 }));
          });
        }
        setProgress(evt.progress);
        setVideoTs(evt.video_ts);
        setViolenceHistory(prev => [...prev, { frame: evt.frame_idx, prob: evt.violence_prob, ts: evt.video_ts }]);
        idx++;
      }, 1500);
      return () => clearInterval(interval);
    }

    const apiBase = import.meta.env.VITE_API_URL || '';
    const es = new EventSource(`${apiBase}/stream/${jobId}`);
    eventSourceRef.current = es;

    es.onopen = () => setStatus('streaming');

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.heartbeat) return;

        if (data.error) {
          setError(data.error);
          setStatus('error');
          es.close();
          return;
        }

        if (data.done) {
          setProgress(1.0);
          setStatus('completed');
          es.close();
          return;
        }

        if (data.frame_b64) setFrame(`data:image/jpeg;base64,${data.frame_b64}`);
        if (data.violence_prob !== undefined) setViolenceProb(data.violence_prob);
        if (data.is_violent !== undefined) setIsViolent(data.is_violent);
        if (data.detections) setDetections(data.detections);
        if (data.progress !== undefined) setProgress(data.progress);
        if (data.video_ts) setVideoTs(data.video_ts);

        if (data.alerts && data.alerts.length > 0) {
          setAlerts(data.alerts);
          setAllAlerts(prev => [...prev, ...data.alerts]);
          data.alerts.forEach(a => {
            setDetectionCounts(prev => ({ ...prev, [a.event_type]: (prev[a.event_type] || 0) + 1 }));
          });
        }

        if (data.violence_prob !== undefined) {
          setViolenceHistory(prev => {
            const next = [...prev, { frame: data.frame_idx, prob: data.violence_prob, ts: data.video_ts }];
            return next.length > 500 ? next.slice(-500) : next;
          });
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setStatus(prev => prev === 'streaming' ? 'completed' : 'error');
      } else {
        setStatus('error');
        setError('Connection lost');
      }
      es.close();
    };
  }, [jobId, isMock]);

  const stopStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setStatus('stopped');
  }, []);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    frame, violenceProb, isViolent, detections,
    alerts, allAlerts, progress, videoTs,
    status, error, violenceHistory, detectionCounts,
    startStream, stopStream,
  };
}
