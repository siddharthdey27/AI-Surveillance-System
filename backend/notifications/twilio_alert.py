"""
notifications/twilio_alert.py
-----------------------------
Sends SMS/MMS alerts via Twilio when threat events are detected.
Notification failures are caught silently — they NEVER crash the pipeline.
"""

import logging
import os

logger = logging.getLogger(__name__)

_client = None
_from_number = None
_to_number = None
_initialized = False


def _init_twilio():
    global _client, _from_number, _to_number, _initialized
    if _initialized:
        return _client is not None
    _initialized = True

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    _from_number = os.getenv("TWILIO_FROM", "").strip()
    _to_number = os.getenv("TWILIO_TO", "").strip()

    if not all([account_sid, auth_token, _from_number, _to_number]):
        logger.warning("Twilio credentials not fully configured in .env")
        return False

    try:
        from twilio.rest import Client
        _client = Client(account_sid, auth_token)
        logger.info("Twilio client initialized")
        return True
    except ImportError:
        logger.warning("twilio package not installed")
        return False
    except Exception as e:
        logger.error("Twilio init failed: %s", e)
        return False


def send_sms_alert(event_type, video_ts, confidence, snapshot_path=None):
    """Send SMS alert. Never raises — all errors caught silently."""
    try:
        if not _init_twilio():
            return False

        emoji_map = {"violence": "\U0001f6a8", "gun": "\U0001f52b", "knife": "\U0001f52a", "fire": "\U0001f525", "smoke": "\U0001f4a8"}
        emoji = "\u26a0\ufe0f"
        for key, em in emoji_map.items():
            if key in event_type.lower():
                emoji = em
                break

        body = f"{emoji} AI SURVEILLANCE ALERT\nEvent: {event_type}\nTime: {video_ts}\nConfidence: {confidence:.1%}\nImmediate attention required."

        msg_kwargs = {"body": body, "from_": _from_number, "to": _to_number}

        if snapshot_path and os.path.exists(snapshot_path):
            logger.info("Snapshot at %s (MMS needs public URL)", snapshot_path)

        message = _client.messages.create(**msg_kwargs)
        logger.info("Twilio SMS sent: SID=%s event=%s", message.sid, event_type)
        return True
    except Exception as e:
        logger.error("Twilio SMS failed (non-fatal): %s", e)
        return False
