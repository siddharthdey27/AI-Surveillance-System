"""
app.py
------
Real-Time AI Violence & Anomaly Detection System
Streamlit entry point.

Run with:
    streamlit run app.py
"""

import logging
import queue
import tempfile
import threading
import time
from pathlib import Path

import base64
import cv2
import numpy as np
import streamlit as st

from alert_system import AlertSystem
from detection import annotate_frame, run_parallel_detection
from model_loader import load_all_models
from utils import (
    FPSController,
    ensure_log_dirs,
    format_timestamp,
    get_log_path,
    get_video_info,
    log_event,
    save_snapshot,
)

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Surveillance System",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        color: #e0e0e0;
    }
    section[data-testid="stSidebar"] {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255,255,255,0.1);
    }
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.07);
        border-radius: 12px;
        padding: 10px;
        border: 1px solid rgba(255,255,255,0.12);
    }
    .alert-box {
        background: rgba(255,50,50,0.15);
        border-left: 4px solid #ff4444;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 0.9rem;
    }
    .stDataFrame { border-radius: 10px; }
    h1 { color: #00d4ff; font-weight: 700; letter-spacing: -0.5px; }
    h2, h3 { color: #a0c8f0; }
    .stButton > button {
        background: linear-gradient(90deg, #00d4ff, #7b2ff7);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }
    .stProgress > div > div { background: linear-gradient(90deg, #00d4ff, #7b2ff7); }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Session state initialisation ───────────────────────────────────────────────

def _init_state():
    defaults = {
        "processing":    False,
        "stop_flag":     False,
        "frame_queue":   queue.Queue(maxsize=32),
        "alert_system":  AlertSystem(cooldown_seconds=3),
        "detection_log": [],
        "fps_display":   0.0,
        "frame_count":   0,
        "total_frames":  1,
        "current_ts":    "00:00:00",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()
ensure_log_dirs()


# ── Model loading (cached) ─────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading AI models... (first run only)")
def _load_models():
    return load_all_models()


# ── Processing thread ──────────────────────────────────────────────────────────

def _processing_loop(
    video_source,
    models: dict,
    alert_system: AlertSystem,      # ← FIX: passed directly, NOT via st.session_state
    yolo_conf: float,
    violence_conf: float,
    frame_skip: int,
    save_snapshots: bool,
    result_queue: queue.Queue,
    stop_event: threading.Event,
):
    """
    Background thread: reads frames, runs models, pushes results to queue.
    Does NOT touch st.session_state — all shared state passed as arguments.
    """
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        result_queue.put({"error": f"Cannot open video source: {video_source}"})
        return

    info         = get_video_info(cap)
    fps_ctrl     = FPSController(info["fps"])
    frame_buffer = []
    BUFFER_MAX   = 32
    frame_idx    = 0

    guns_knives  = models["guns_knives_model"]
    fire_smoke   = models["fire_smoke_model"]
    violence_mdl = models["violence_model"]
    v_shape      = models["violence_input_shape"]

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx    += 1
        video_seconds = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        video_ts      = format_timestamp(video_seconds)

        # Frame skipping
        if frame_idx % max(frame_skip, 1) != 0:
            fps_ctrl.wait()
            fps_ctrl.tick()
            continue

        display_frame = cv2.resize(frame, (640, 480))

        # Rolling buffer for violence model
        frame_buffer.append(display_frame)
        if len(frame_buffer) > BUFFER_MAX:
            frame_buffer.pop(0)

        # Run all models in parallel
        detections = run_parallel_detection(
            display_frame, frame_buffer,
            guns_knives, fire_smoke,
            violence_mdl, v_shape,
            yolo_conf=yolo_conf,
            violence_conf=violence_conf,
        )

        # ── Post-processing: fix inverted violence model output ────────
        import os
        violence_invert = os.getenv("VIOLENCE_INVERT", "true").lower() == "true"
        if violence_invert:
            raw_prob = detections["violence_prob"]
            corrected_prob = 1.0 - raw_prob
            detections["violence_prob"] = corrected_prob
            detections["is_violent"] = corrected_prob >= violence_conf

        # Build alerts — using the passed-in alert_system, NOT session_state
        new_alerts = []

        if detections["is_violent"]:
            a = alert_system.check_and_raise("Violence", video_ts, detections["violence_prob"])
            if a:
                new_alerts.append(a)
                log_event("Violence", video_ts, detections["violence_prob"])
                if save_snapshots:
                    save_snapshot(display_frame, video_ts, "Violence")

        for det in detections["weapons"]:
            label = det["label"].capitalize()
            a = alert_system.check_and_raise(label, video_ts, det["confidence"])
            if a:
                new_alerts.append(a)
                log_event(label, video_ts, det["confidence"], str(det["box"]))
                if save_snapshots:
                    save_snapshot(display_frame, video_ts, label)

        for det in detections["fire_smoke"]:
            label = det["label"].capitalize()
            a = alert_system.check_and_raise(label, video_ts, det["confidence"])
            if a:
                new_alerts.append(a)
                log_event(label, video_ts, det["confidence"], str(det["box"]))
                if save_snapshots:
                    save_snapshot(display_frame, video_ts, label)

        # Annotate and convert BGR → RGB
        annotated     = annotate_frame(display_frame, detections,
                                       detections["violence_prob"], detections["is_violent"])
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        smoothed_fps  = fps_ctrl.tick()

        payload = {
            "frame":        annotated_rgb,
            "fps":          smoothed_fps,
            "frame_idx":    frame_idx,
            "total_frames": info["total_frames"],
            "video_ts":     video_ts,
            "new_alerts":   [a.to_dict() for a in new_alerts],
            "detections":   detections,
        }

        try:
            result_queue.put_nowait(payload)
        except queue.Full:
            pass  # Drop frame if UI is lagging

        fps_ctrl.wait()

    cap.release()
    result_queue.put({"done": True})


# ── Sidebar ────────────────────────────────────────────────────────────────────

def render_sidebar(models: dict):
    with st.sidebar:
        st.markdown("## Control Panel")
        st.divider()

        st.markdown("### Video Source")
        source_type = st.radio(
            "Input type",
            ["Upload Video File", "Stream URL / Webcam"],
            key="source_type",
            label_visibility="collapsed",
        )

        uploaded_file = None
        stream_url    = "0"  # always initialised to avoid scope bug

        if source_type == "Upload Video File":
            uploaded_file = st.file_uploader(
                "Upload a video",
                type=["mp4", "avi", "mov", "mkv", "webm"],
                key="video_upload",
            )
        else:
            stream_url = st.text_input(
                "Stream URL (RTSP / Webcam index)",
                value="0",
                key="stream_url",
                help="Enter RTSP URL or 0 for webcam",
            )

        st.divider()
        st.markdown("### Detection Thresholds")

        yolo_conf = st.slider(
            "YOLO Confidence", 0.1, 1.0, 0.4, 0.05, key="yolo_conf",
        )
        violence_conf = st.slider(
            "Violence Threshold", 0.1, 1.0, 0.6, 0.05, key="violence_conf",
        )

        st.divider()
        st.markdown("### Performance")

        frame_skip = st.selectbox(
            "Process every Nth frame", [1, 2, 3, 4], index=1, key="frame_skip",
            help="Higher = faster but less accurate. Recommended: 2-3 for CPU.",
        )
        save_snaps = st.checkbox("Save snapshots on detection", value=True, key="save_snaps")

        st.divider()

        # Model status
        st.markdown("### Model Status")
        v_ok  = models.get("violence_model")    is not None
        gk_ok = models.get("guns_knives_model") is not None
        fs_ok = models.get("fire_smoke_model")  is not None

        st.markdown(
            f"{'✅' if gk_ok else '❌'} Guns & Knives (YOLO)  \n"
            f"{'✅' if fs_ok else '❌'} Fire & Smoke (YOLO)   \n"
            f"{'✅' if v_ok  else '⚠️'} Violence Model (Keras)"
        )
        if not gk_ok and not fs_ok and not v_ok:
            st.error("No models loaded. Check terminal logs.")

        col1, col2 = st.columns(2)
        with col1:
            start_btn = st.button("▶ Start", key="start_btn", use_container_width=True)
        with col2:
            stop_btn = st.button("⏹ Stop", key="stop_btn", use_container_width=True)

        st.divider()
        st.markdown("### Export")
        log_path = get_log_path()
        if log_path.exists():
            with open(log_path, "rb") as f:
                st.download_button(
                    "Download Detection Log (CSV)",
                    data=f,
                    file_name="detections.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    return {
        "uploaded_file": uploaded_file,
        "source_type":   source_type,
        "stream_url":    stream_url,
        "yolo_conf":     yolo_conf,
        "violence_conf": violence_conf,
        "frame_skip":    frame_skip,
        "save_snaps":    save_snaps,
        "start":         start_btn,
        "stop":          stop_btn,
    }


# ── Main UI ────────────────────────────────────────────────────────────────────

def main():
    st.markdown(
        """
        <div style='text-align:center; padding: 20px 0 10px 0;'>
          <h1 style='margin:0;'>AI Surveillance System</h1>
          <p style='color:#8899aa; font-size:1.05rem; margin-top:4px;'>
            Real-Time Violence &amp; Anomaly Detection · Powered by YOLOv8 &amp; Deep Learning
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("Loading AI models..."):
        models = _load_models()

    ctrl = render_sidebar(models)

    # ── Metrics row ───────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    fps_ph    = m1.empty()
    frame_ph  = m2.empty()
    alert_ph  = m3.empty()
    status_ph = m4.empty()

    def _update_metrics():
        fps_ph.metric("FPS",    f"{st.session_state.get('fps_display', 0):.1f}")
        frame_ph.metric(
            "Frame",
            f"{st.session_state.get('frame_count', 0)} / "
            f"{st.session_state.get('total_frames', 0)}",
        )
        alert_ph.metric("Alerts", len(st.session_state["alert_system"].history))
        status_ph.metric("Status", "Running" if st.session_state["processing"] else "Idle")

    _update_metrics()
    st.divider()

    # ── Two-column layout ─────────────────────────────────────────────────────
    vid_col, info_col = st.columns([3, 2])

    with vid_col:
        st.markdown("### Live Feed")
        progress_bar = st.progress(0)
        ts_display   = st.empty()
        video_ph     = st.empty()
        video_ph.markdown(
            "<div style='height:480px; display:flex; align-items:center; "
            "justify-content:center; background:rgba(0,0,0,0.4); border-radius:12px; "
            "color:#555; font-size:1.2rem;'>Upload a video and press Start</div>",
            unsafe_allow_html=True,
        )

    with info_col:
        st.markdown("### Alert Panel")
        alert_panel  = st.empty()
        st.markdown("### Detection Log")
        log_table_ph = st.empty()
        log_table_ph.markdown("_No detections yet._")

    # ── Start ─────────────────────────────────────────────────────────────────
    if ctrl["start"] and not st.session_state["processing"]:

        if ctrl["source_type"] == "Upload Video File":
            if ctrl["uploaded_file"] is None:
                st.error("Please upload a video file first.")
                st.stop()
            suffix = Path(ctrl["uploaded_file"].name).suffix
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(ctrl["uploaded_file"].read())
            tmp.flush()
            tmp.close()
            video_source = tmp.name
        else:
            raw = ctrl["stream_url"].strip()
            video_source = int(raw) if raw.isdigit() else raw

        # Reset state
        alert_sys = AlertSystem(cooldown_seconds=3)
        st.session_state["alert_system"]  = alert_sys
        st.session_state["detection_log"] = []
        st.session_state["processing"]    = True
        st.session_state["stop_flag"]     = False
        st.session_state["frame_count"]   = 0
        new_q = queue.Queue(maxsize=32)
        st.session_state["frame_queue"]   = new_q

        stop_event = threading.Event()
        st.session_state["_stop_event"]   = stop_event

        thread = threading.Thread(
            target=_processing_loop,
            args=(
                video_source,
                models,
                alert_sys,           # ← passed directly, thread never touches session_state
                ctrl["yolo_conf"],
                ctrl["violence_conf"],
                ctrl["frame_skip"],
                ctrl["save_snaps"],
                new_q,
                stop_event,
            ),
            daemon=True,
        )
        thread.start()
        st.session_state["_thread"] = thread
        st.rerun()

    # ── Stop ──────────────────────────────────────────────────────────────────
    if ctrl["stop"]:
        st.session_state["processing"] = False
        st.session_state["stop_flag"]  = True
        ev = st.session_state.get("_stop_event")
        if ev:
            ev.set()
        st.rerun()

    # ── Render loop ───────────────────────────────────────────────────────────
    if st.session_state["processing"]:
        result_q:  queue.Queue = st.session_state["frame_queue"]
        alert_sys: AlertSystem = st.session_state["alert_system"]

        done = False
        payload = None

        # Drain queue — keep only the latest frame to avoid lag
        while True:
            try:
                candidate = result_q.get_nowait()
                payload = candidate
            except queue.Empty:
                break

        # If queue was empty, wait briefly for next frame
        if payload is None:
            try:
                payload = result_q.get(timeout=0.3)
            except queue.Empty:
                payload = None

        if payload is not None:
            if "error" in payload:
                st.error(payload["error"])
                st.session_state["processing"] = False

            elif "done" in payload:
                done = True
                st.session_state["processing"] = False
                st.success("Processing complete!")

            else:
                # Encode frame as JPEG bytes → base64 → data URI
                # This avoids Streamlit's MediaFileHandler entirely (no missing file errors)
                import cv2 as _cv2
                _, jpg_buf = _cv2.imencode(".jpg", _cv2.cvtColor(payload["frame"], _cv2.COLOR_RGB2BGR), [_cv2.IMWRITE_JPEG_QUALITY, 85])
                b64 = base64.b64encode(jpg_buf.tobytes()).decode()
                video_ph.markdown(
                    f'<img src="data:image/jpeg;base64,{b64}" style="width:100%;border-radius:8px;">',
                    unsafe_allow_html=True,
                )

                total    = max(payload["total_frames"], 1)
                progress = min(payload["frame_idx"] / total, 1.0)
                progress_bar.progress(progress)
                ts_display.caption(f"Video time: {payload['video_ts']}")

                st.session_state["fps_display"]  = payload["fps"]
                st.session_state["frame_count"]  = payload["frame_idx"]
                st.session_state["total_frames"] = payload["total_frames"]
                st.session_state["current_ts"]   = payload["video_ts"]

                for a in payload["new_alerts"]:
                    st.session_state["detection_log"].insert(0, a)

        _update_metrics()

        # Alert panel
        recent = alert_sys.recent_alerts(8)
        if recent:
            alerts_html = ""
            for a in recent:
                colour = "#ff4444" if alert_sys.severity(a["event_type"]) == "error" else "#ffaa00"
                alerts_html += (
                    f"<div class='alert-box' style='border-color:{colour};'>"
                    f"{a['message']}</div>"
                )
            alert_panel.markdown(alerts_html, unsafe_allow_html=True)
        else:
            alert_panel.info("No alerts yet.")

        # Detection log
        log_data = st.session_state["detection_log"][:50]
        if log_data:
            import pandas as pd
            log_table_ph.dataframe(
                pd.DataFrame(log_data)[["event_type", "video_timestamp", "confidence", "message"]],
                use_container_width=True,
                hide_index=True,
            )

        if not done:
            time.sleep(0.1)
            st.rerun()

    else:
        # Static view when not processing
        alert_sys: AlertSystem = st.session_state["alert_system"]
        recent = alert_sys.recent_alerts(8)
        if recent:
            alerts_html = "".join(
                f"<div class='alert-box'>{a['message']}</div>" for a in recent
            )
            alert_panel.markdown(alerts_html, unsafe_allow_html=True)
        else:
            alert_panel.info("No alerts yet.")

        log_data = st.session_state["detection_log"][:50]
        if log_data:
            import pandas as pd
            log_table_ph.dataframe(
                pd.DataFrame(log_data)[["event_type", "video_timestamp", "confidence", "message"]],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()
    st.markdown(
        "<p style='text-align:center; color:#445566; font-size:0.8rem;'>"
        "AI Surveillance System · YOLOv8 + Deep Learning</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()