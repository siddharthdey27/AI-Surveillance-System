"""
model_loader.py  (project root)
-----------------------------------------------------------------
Re-exports model loading functions from backend/model_loader.py.
This exists for backward compatibility with the Streamlit app.py.
"""

import sys
from pathlib import Path

# Ensure backend/ is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Now import. We use a direct import after adding to path.
from model_loader import load_all_models, load_yolo_model, get_device  # noqa: E402

__all__ = ["load_all_models", "load_yolo_model", "get_device"]