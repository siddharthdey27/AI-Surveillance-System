"""
alert_system.py
---------------
Manages real-time alert generation with cooldown deduplication.

Usage
-----
    alerts = AlertSystem(cooldown_seconds=3)
    alert = alerts.check_and_raise("Violence", "00:01:23", 0.85)
    if alert:
        print(alert.message)
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ── Alert record ───────────────────────────────────────────────────────────────

@dataclass
class AlertRecord:
    event_type: str
    video_timestamp: str
    confidence: float
    wall_time: float = field(default_factory=time.time)
    message: str = ""

    def __post_init__(self):
        emoji_map = {
            "violence": "🚨",
            "weapon":   "🔫",
            "gun":      "🔫",
            "knife":    "🔪",
            "fire":     "🔥",
            "smoke":    "💨",
        }
        emoji = "⚠️"
        for key, em in emoji_map.items():
            if key in self.event_type.lower():
                emoji = em
                break
        self.message = (
            f"{emoji} ALERT: {self.event_type} detected "
            f"at {self.video_timestamp}  "
            f"[conf: {self.confidence:.2f}]"
        )

    def to_dict(self) -> dict:
        return {
            "event_type":      self.event_type,
            "video_timestamp": self.video_timestamp,
            "confidence":      round(self.confidence, 4),
            "message":         self.message,
        }


# ── Alert system ───────────────────────────────────────────────────────────────

class AlertSystem:
    """
    Thread-safe alert manager that:
    - Deduplicates repeated alerts within a cooldown window
    - Maintains a bounded history deque for UI rendering
    - Exposes severity levels (warning / error)
    """

    SEVERITY_ERROR   = {"violence", "gun", "weapon", "fire"}
    SEVERITY_WARNING = {"knife", "smoke"}

    def __init__(self, cooldown_seconds: float = 3.0, max_history: int = 100):
        self._cooldown = cooldown_seconds
        self._last_alert: dict = {}          # event_type → last wall_time
        self.history: deque = deque(maxlen=max_history)

    def _on_cooldown(self, event_type: str) -> bool:
        last = self._last_alert.get(event_type, 0.0)
        return (time.time() - last) < self._cooldown

    def check_and_raise(
        self,
        event_type: str,
        video_timestamp: str,
        confidence: float,
    ) -> Optional[AlertRecord]:
        """
        Returns AlertRecord if a new alert was raised, else None.
        Suppresses duplicate alerts within the cooldown window.
        """
        if self._on_cooldown(event_type):
            return None

        record = AlertRecord(event_type, video_timestamp, confidence)
        self._last_alert[event_type] = record.wall_time
        self.history.append(record)
        return record

    def severity(self, event_type: str) -> str:
        """Return 'error' or 'warning' for UI alert styling."""
        for key in self.SEVERITY_ERROR:
            if key in event_type.lower():
                return "error"
        return "warning"

    def recent_alerts(self, n: int = 10) -> list:
        """Return the N most recent alerts as dicts (newest first)."""
        return [r.to_dict() for r in reversed(list(self.history))][:n]

    def clear(self):
        self.history.clear()
        self._last_alert.clear()
