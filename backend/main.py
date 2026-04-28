"""
backend/main.py
---------------
FastAPI backend for the AI Surveillance System.

Endpoints:
    POST /upload           — Upload a video file, returns job_id
    GET  /stream/{job_id}  — SSE stream of detection results per frame
    GET  /alerts/{job_id}  — Full alert history for a job
    GET  /logs/{job_id}/download — Download CSV log file
    GET  /report/{job_id}  — Generate and download incident report PDF
"""

import asyncio
import base64
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

# ── Ensure backend/ is on sys.path so local modules are importable ─────────
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alert_system import AlertSystem
from detection import annotate_frame, run_parallel_detection
from model_loader import load_all_models
from utils import (
    FPSController,
    ensure_log_dirs,
    format_timestamp,
    get_video_info,
    log_event,
    save_snapshot,
)

# ── Load .env ──────────────────────────────────────────────────────────────────
load_dotenv(BACKEND_DIR.parent / ".env")

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Surveillance System API",
    version="2.0.0",
    description="Real-time violence & anomaly detection backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global state ───────────────────────────────────────────────────────────────
models: dict = {}
UPLOAD_DIR = BACKEND_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Job storage: job_id → job metadata
jobs: Dict[str, dict] = {}


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    global models
    logger.info("Loading AI models at startup...")
    ensure_log_dirs()
    models = load_all_models()
    logger.info("Models loaded: %d / 3", models.get("loaded_count", 0))


# ── POST /upload ───────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Accept a video file upload, save to uploads/, return a job_id."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    allowed = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed)}",
        )

    job_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{job_id}{ext}"

    content = await file.read()
    save_path.write_bytes(content)

    file_size = len(content)
    logger.info("Uploaded %s → %s (%d bytes)", file.filename, save_path.name, file_size)

    jobs[job_id] = {
        "job_id": job_id,
        "filename": file.filename,
        "file_path": str(save_path),
        "file_size": file_size,
        "status": "uploaded",
        "created_at": time.time(),
        "alert_system": AlertSystem(cooldown_seconds=3),
        "alert_history": [],
        "detection_events": [],
        "violence_timeline": [],
        "snapshots": [],
        "progress": 0.0,
    }

    return {
        "job_id": job_id,
        "filename": file.filename,
        "file_size": file_size,
        "status": "uploaded",
    }


# ── Processing function (runs in a thread) ─────────────────────────────────────

def _process_video(job_id: str, result_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    """
    Background thread: reads frames, runs AI models, pushes results to an
    asyncio queue for the SSE endpoint to consume.
    """
    job = jobs[job_id]
    video_path = job["file_path"]
    alert_sys = job["alert_system"]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        asyncio.run_coroutine_threadsafe(
            result_queue.put({"error": f"Cannot open video: {video_path}"}), loop
        )
        return

    info = get_video_info(cap)
    fps_ctrl = FPSController(info["fps"])
    frame_buffer = []
    BUFFER_MAX = 32
    frame_idx = 0

    guns_knives = models.get("guns_knives_model")
    fire_smoke = models.get("fire_smoke_model")
    violence_mdl = models.get("violence_model")
    v_shape = models.get("violence_input_shape")

    yolo_conf = float(os.getenv("YOLO_CONF", "0.4"))
    violence_conf = float(os.getenv("VIOLENCE_CONF", "0.8"))
    frame_skip = int(os.getenv("FRAME_SKIP", "2"))
    save_snapshots = os.getenv("SAVE_SNAPSHOTS", "true").lower() == "true"

    # Many Keras violence models output [violent, non_violent] but detection.py
    # reads index [1] assuming [non_violent, violent]. When VIOLENCE_INVERT=true
    # (the default), we flip: prob = 1 - prob, which corrects the class order.
    violence_invert = os.getenv("VIOLENCE_INVERT", "true").lower() == "true"

    total_frames = max(info["total_frames"], 1)
    job["status"] = "processing"

    # Import notification modules (fail silently)
    try:
        from notifications.twilio_alert import send_sms_alert
    except Exception:
        send_sms_alert = None

    try:
        from notifications.telegram_alert import send_telegram_alert
    except Exception:
        send_telegram_alert = None

    # Track which event types have already triggered phone notifications
    notified_types = set()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        video_seconds = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        video_ts = format_timestamp(video_seconds)

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
        if violence_invert:
            raw_prob = detections["violence_prob"]
            corrected_prob = 1.0 - raw_prob
            detections["violence_prob"] = corrected_prob
            detections["is_violent"] = corrected_prob >= violence_conf

        # Build alerts
        new_alerts = []

        if detections["is_violent"]:
            a = alert_sys.check_and_raise("Violence", video_ts, detections["violence_prob"])
            if a:
                new_alerts.append(a)
                log_event("Violence", video_ts, detections["violence_prob"])
                snapshot_path = None
                if save_snapshots:
                    snapshot_path = save_snapshot(display_frame, video_ts, "Violence")
                    job["snapshots"].append(snapshot_path)

                # Fire phone notifications (once per event type per job)
                if "Violence" not in notified_types:
                    notified_types.add("Violence")
                    if send_sms_alert:
                        try:
                            send_sms_alert("Violence", video_ts, detections["violence_prob"], snapshot_path)
                        except Exception:
                            pass
                    if send_telegram_alert:
                        try:
                            send_telegram_alert("Violence", video_ts, detections["violence_prob"], snapshot_path)
                        except Exception:
                            pass

        for det in detections["weapons"]:
            label = det["label"].capitalize()
            a = alert_sys.check_and_raise(label, video_ts, det["confidence"])
            if a:
                new_alerts.append(a)
                log_event(label, video_ts, det["confidence"], str(det["box"]))
                snapshot_path = None
                if save_snapshots:
                    snapshot_path = save_snapshot(display_frame, video_ts, label)
                    job["snapshots"].append(snapshot_path)

                if label not in notified_types:
                    notified_types.add(label)
                    if send_sms_alert:
                        try:
                            send_sms_alert(label, video_ts, det["confidence"], snapshot_path)
                        except Exception:
                            pass
                    if send_telegram_alert:
                        try:
                            send_telegram_alert(label, video_ts, det["confidence"], snapshot_path)
                        except Exception:
                            pass

        for det in detections["fire_smoke"]:
            label = det["label"].capitalize()
            a = alert_sys.check_and_raise(label, video_ts, det["confidence"])
            if a:
                new_alerts.append(a)
                log_event(label, video_ts, det["confidence"], str(det["box"]))
                snapshot_path = None
                if save_snapshots:
                    snapshot_path = save_snapshot(display_frame, video_ts, label)
                    job["snapshots"].append(snapshot_path)

                if label not in notified_types:
                    notified_types.add(label)
                    if send_sms_alert:
                        try:
                            send_sms_alert(label, video_ts, det["confidence"], snapshot_path)
                        except Exception:
                            pass
                    if send_telegram_alert:
                        try:
                            send_telegram_alert(label, video_ts, det["confidence"], snapshot_path)
                        except Exception:
                            pass

        # Store alert history
        for a in new_alerts:
            job["alert_history"].append(a.to_dict())

        # Store detection events for analytics
        event_data = {
            "frame_idx": frame_idx,
            "video_ts": video_ts,
            "violence_prob": detections["violence_prob"],
            "is_violent": detections["is_violent"],
            "weapons": [{"label": d["label"], "confidence": d["confidence"]} for d in detections["weapons"]],
            "fire_smoke": [{"label": d["label"], "confidence": d["confidence"]} for d in detections["fire_smoke"]],
        }
        job["detection_events"].append(event_data)
        job["violence_timeline"].append({
            "frame": frame_idx,
            "ts": video_ts,
            "prob": round(detections["violence_prob"], 4),
        })

        # Annotate and encode frame
        annotated = annotate_frame(
            display_frame, detections,
            detections["violence_prob"], detections["is_violent"],
        )
        _, jpg_buf = cv2.imencode(
            ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80]
        )
        frame_b64 = base64.b64encode(jpg_buf.tobytes()).decode("utf-8")

        progress = min(frame_idx / total_frames, 1.0)
        job["progress"] = progress

        # Serialize detections for SSE (convert box tuples to lists)
        weapons_serial = [
            {"label": d["label"], "confidence": round(d["confidence"], 4), "box": list(d["box"])}
            for d in detections["weapons"]
        ]
        fire_smoke_serial = [
            {"label": d["label"], "confidence": round(d["confidence"], 4), "box": list(d["box"])}
            for d in detections["fire_smoke"]
        ]

        payload = {
            "frame_b64": frame_b64,
            "violence_prob": round(detections["violence_prob"], 4),
            "is_violent": detections["is_violent"],
            "detections": {
                "weapons": weapons_serial,
                "fire_smoke": fire_smoke_serial,
            },
            "alerts": [a.to_dict() for a in new_alerts],
            "progress": round(progress, 4),
            "video_ts": video_ts,
            "frame_idx": frame_idx,
            "total_frames": total_frames,
        }

        # Backpressure: if queue is full, drop the oldest frame
        try:
            asyncio.run_coroutine_threadsafe(
                result_queue.put(payload), loop
            ).result(timeout=0.5)
        except Exception:
            # Queue full or event loop issue — skip frame
            pass

        fps_ctrl.wait()
        fps_ctrl.tick()

    cap.release()
    job["status"] = "completed"
    job["progress"] = 1.0

    asyncio.run_coroutine_threadsafe(
        result_queue.put({"done": True, "progress": 1.0}), loop
    )


# ── GET /stream/{job_id} — SSE stream ─────────────────────────────────────────
@app.get("/stream/{job_id}")
async def stream_detections(job_id: str):
    """Server-Sent Events stream of detection results frame by frame."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] == "completed":
        raise HTTPException(status_code=400, detail="Job already completed")

    result_queue = asyncio.Queue(maxsize=16)
    loop = asyncio.get_event_loop()

    # Start processing in a background thread
    thread = threading.Thread(
        target=_process_video,
        args=(job_id, result_queue, loop),
        daemon=True,
    )
    thread.start()

    async def event_generator():
        while True:
            try:
                payload = await asyncio.wait_for(result_queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                continue

            if "error" in payload:
                yield f"data: {json.dumps({'error': payload['error']})}\n\n"
                break

            if "done" in payload:
                yield f"data: {json.dumps({'done': True, 'progress': 1.0})}\n\n"
                break

            yield f"data: {json.dumps(payload)}\n\n"

            # Handle backpressure: if frames are piling up, drain to latest
            drained = 0
            while not result_queue.empty() and drained < 5:
                try:
                    payload = result_queue.get_nowait()
                    drained += 1
                    if "done" in payload or "error" in payload:
                        yield f"data: {json.dumps(payload)}\n\n"
                        return
                except asyncio.QueueEmpty:
                    break

            if drained > 0:
                yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── GET /alerts/{job_id} ──────────────────────────────────────────────────────
@app.get("/alerts/{job_id}")
async def get_alerts(job_id: str):
    """Return full alert history for a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "alerts": job["alert_history"],
        "total_alerts": len(job["alert_history"]),
    }


# ── GET /logs/{job_id}/download ───────────────────────────────────────────────
@app.get("/logs/{job_id}/download")
async def download_log(job_id: str):
    """Serve the CSV log file for download."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    from utils import get_log_path
    log_path = get_log_path()

    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(
        path=str(log_path),
        filename=f"detections_{job_id[:8]}.csv",
        media_type="text/csv",
    )


# ── GET /analytics/{job_id} ──────────────────────────────────────────────────
@app.get("/analytics/{job_id}")
async def get_analytics(job_id: str):
    """Return detection analytics data for charts."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Count detections by type
    type_counts = {}
    for alert in job["alert_history"]:
        et = alert["event_type"]
        type_counts[et] = type_counts.get(et, 0) + 1

    return {
        "job_id": job_id,
        "detection_counts": type_counts,
        "violence_timeline": job["violence_timeline"],
        "total_events": len(job["alert_history"]),
        "snapshots": job["snapshots"],
    }


# ── GET /report/{job_id} ─────────────────────────────────────────────────────
@app.get("/report/{job_id}")
async def generate_report_endpoint(job_id: str):
    """Generate and return an incident report PDF."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Import report generator
    sys.path.insert(0, str(BACKEND_DIR.parent / "reports"))
    try:
        from report_generator import generate_report
    except ImportError:
        raise HTTPException(status_code=500, detail="Report generator not available")

    try:
        pdf_path = generate_report(
            job_id=job_id,
            alert_history=job["alert_history"],
            snapshots=job["snapshots"],
            filename=job.get("filename", "unknown"),
            duration_frames=job.get("progress", 0),
        )
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

    return FileResponse(
        path=pdf_path,
        filename=f"incident_report_{job_id[:8]}.pdf",
        media_type="application/pdf",
    )


# ── GET /jobs ─────────────────────────────────────────────────────────────────
@app.get("/jobs")
async def list_jobs():
    """List all jobs."""
    return [
        {
            "job_id": j["job_id"],
            "filename": j["filename"],
            "status": j["status"],
            "progress": j["progress"],
            "total_alerts": len(j["alert_history"]),
            "created_at": j["created_at"],
        }
        for j in jobs.values()
    ]


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "models_loaded": models.get("loaded_count", 0),
        "active_jobs": len(jobs),
    }


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
