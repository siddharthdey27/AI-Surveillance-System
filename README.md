# AI Surveillance System v2.0

Real-time violence & anomaly detection powered by YOLOv8 + Deep Learning, with phone alerts and a modern React dashboard.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE                                 │
│                                                                     │
│  ┌──────────────┐     HTTP/SSE      ┌──────────────────────────┐   │
│  │   React UI   │◄────────────────► │    FastAPI Backend       │   │
│  │  (Vite)      │   Port 5173       │    Port 8000             │   │
│  │              │                   │                          │   │
│  │ • Upload     │   POST /upload    │ ┌──────────────────────┐ │   │
│  │ • Live Feed  │   GET  /stream/*  │ │  Detection Engine    │ │   │
│  │ • Alerts     │   GET  /alerts/*  │ │  ┌────────────────┐  │ │   │
│  │ • Analytics  │   GET  /report/*  │ │  │ YOLOv8 Weapons │  │ │   │
│  │ • Settings   │                   │ │  │ YOLOv8 Fire    │  │ │   │
│  └──────────────┘                   │ │  │ Keras Violence │  │ │   │
│                                     │ │  └────────────────┘  │ │   │
│                                     │ └──────────────────────┘ │   │
│                                     │                          │   │
│                                     │ ┌──────────────────────┐ │   │
│                                     │ │   Notifications      │ │   │
│                                     │ │  • Twilio SMS/MMS    │ │   │
│                                     │ │  • Telegram Bot      │ │   │
│                                     │ └──────────────────────┘ │   │
│                                     │                          │   │
│                                     │ ┌──────────────────────┐ │   │
│                                     │ │  Reports (PDF)       │ │   │
│                                     │ │  • ReportLab         │ │   │
│                                     │ └──────────────────────┘ │   │
│                                     └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Clone & Setup Environment

```bash
# Copy environment template
cp .env.example .env
# Edit .env with your credentials (optional for Twilio/Telegram)
```

### 2. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Place model files in backend/
#   - violence_detection.h5
#   - guns_knives.pt
#   - Fire_smoke.pt

# Start the backend
cd backend
python main.py
# → Running on http://localhost:8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
# → Running on http://localhost:5173
```

### 4. Docker (Alternative)

```bash
docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload video file, returns `job_id` |
| `GET` | `/stream/{job_id}` | SSE stream of detection results |
| `GET` | `/alerts/{job_id}` | Full alert history |
| `GET` | `/logs/{job_id}/download` | Download CSV detection log |
| `GET` | `/report/{job_id}` | Generate & download PDF report |
| `GET` | `/analytics/{job_id}` | Detection analytics data |
| `GET` | `/health` | Health check |

## Mock Mode (Frontend Only)

Run the frontend without a backend:

```bash
VITE_MOCK=true npm run dev
```

## Twilio Setup

1. Sign up at [twilio.com/try-twilio](https://www.twilio.com/try-twilio)
2. Get your Account SID and Auth Token from the Console Dashboard
3. Get a Twilio phone number (Messaging → Phone Numbers)
4. Add to `.env`:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_FROM=+15551234567
   TWILIO_TO=+15559876543
   ```

## Telegram Bot Setup

1. Open Telegram, search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token
4. Send any message to your new bot
5. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Find `"chat":{"id":123456789}` in the response
7. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   TELEGRAM_CHAT_ID=123456789
   ```

## Project Structure

```
project/
├── backend/
│   ├── main.py                  # FastAPI server
│   ├── alert_system.py          # Alert management (unchanged)
│   ├── detection.py             # AI detection logic (unchanged)
│   ├── model_loader.py          # Model loading (unchanged)
│   ├── utils.py                 # Utilities (unchanged)
│   └── notifications/
│       ├── twilio_alert.py      # Twilio SMS/MMS
│       └── telegram_alert.py    # Telegram bot
├── reports/
│   └── report_generator.py      # PDF report generation
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main application
│   │   ├── components/
│   │   │   ├── VideoFeed.jsx    # Live video + gauge
│   │   │   ├── AlertPanel.jsx   # Real-time alerts
│   │   │   ├── IncidentTimeline.jsx
│   │   │   ├── Analytics.jsx    # Charts (Recharts)
│   │   │   └── Settings.jsx     # Configuration
│   │   └── hooks/
│   │       └── useSSEStream.js  # SSE client hook
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

## Tech Stack

- **Backend**: FastAPI, Uvicorn, Python 3.12
- **AI Models**: TensorFlow/Keras, YOLOv8 (Ultralytics), OpenCV
- **Frontend**: React 18, Vite, Tailwind CSS, Recharts
- **Notifications**: Twilio, python-telegram-bot
- **Reports**: ReportLab (PDF)

## License

MIT
