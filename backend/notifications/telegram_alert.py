"""
notifications/telegram_alert.py
--------------------------------
Sends Telegram bot alerts when threat events are detected.
Notification failures are caught silently — they NEVER crash the pipeline.
"""

import logging
import os

logger = logging.getLogger(__name__)

_bot_token = None
_chat_id = None
_initialized = False


def _init_telegram():
    global _bot_token, _chat_id, _initialized
    if _initialized:
        return _bot_token is not None
    _initialized = True

    _bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    _chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not _bot_token or not _chat_id:
        logger.warning("Telegram credentials not configured in .env")
        return False

    logger.info("Telegram alert configured for chat_id=%s", _chat_id)
    return True


def send_telegram_alert(event_type, video_ts, confidence, snapshot_path=None):
    """Send Telegram alert. Never raises — all errors caught silently."""
    try:
        if not _init_telegram():
            return False

        import asyncio
        try:
            from telegram import Bot
        except ImportError:
            logger.warning("python-telegram-bot not installed")
            return False

        emoji_map = {
            "violence": "\U0001f6a8", "gun": "\U0001f52b",
            "knife": "\U0001f52a", "fire": "\U0001f525", "smoke": "\U0001f4a8",
        }
        emoji = "\u26a0\ufe0f"
        for key, em in emoji_map.items():
            if key in event_type.lower():
                emoji = em
                break

        severity = "HIGH" if any(k in event_type.lower() for k in ["violence", "gun", "fire"]) else "MEDIUM"

        message = (
            f"{emoji} *AI SURVEILLANCE ALERT*\n\n"
            f"*Event:* {event_type}\n"
            f"*Severity:* {severity}\n"
            f"*Video Time:* `{video_ts}`\n"
            f"*Confidence:* {confidence:.1%}\n\n"
            f"_Automated alert from AI Surveillance System_"
        )

        bot = Bot(token=_bot_token)

        async def _send():
            if snapshot_path and os.path.exists(snapshot_path):
                with open(snapshot_path, "rb") as photo:
                    await bot.send_photo(
                        chat_id=_chat_id, photo=photo,
                        caption=message, parse_mode="Markdown",
                    )
            else:
                await bot.send_message(
                    chat_id=_chat_id, text=message, parse_mode="Markdown",
                )

        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(_send(), loop).result(timeout=10)
        except RuntimeError:
            asyncio.run(_send())

        logger.info("Telegram alert sent: event=%s", event_type)
        return True
    except Exception as e:
        logger.error("Telegram alert failed (non-fatal): %s", e)
        return False
