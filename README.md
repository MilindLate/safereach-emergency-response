# SafeReach — Intelligent Emergency Response for Road Accidents

> AI-powered emergency response platform for road accidents, built to cut ambulance dispatch time and connect victims, dispatchers, ambulance crews, hospitals, and families on one coordinated system.

---

## Overview

Road accident fatalities in India are heavily driven by delayed emergency response — every additional minute before help arrives meaningfully lowers survival odds. SafeReach addresses this directly: an AI-driven coordination layer that takes a victim's SOS signal, classifies crash severity from a photo, finds and dispatches the nearest available ambulance, recomputes the optimal route in real time, and keeps hospitals and family members informed automatically — aiming to cut time-to-dispatch by **30–40%**.

### Four Components

| Component | Tech | User |
|-----------|------|------|
| **Victim App** | React Native (Expo) | Road accident victim |
| **Dispatcher Dashboard** | Next.js 14 | Emergency coordination centre |
| **Crew App** | React Native (Expo) | Ambulance driver |
| **Family Tracker** | Next.js (no-login page) | Emergency contacts |

### Three AI Models

| Model | Architecture | Target |
|-------|-------------|--------|
| **Crash Severity CNN** | EfficientNet-B2 | ≥ 85% accuracy, < 1.5s inference |
| **Accident Hotspot** | XGBoost (14 features) | F1 ≥ 0.82, AUC ≥ 0.85 |
| **Route Optimiser** | OSRM + Google Maps | ETA within 15% accuracy |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CLIENT LAYER                                               │
│  Victim App (RN)  │  Dashboard (Next.js)  │  Crew App (RN) │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS + WSS
┌──────────────────────────┴──────────────────────────────────┐
│  API GATEWAY (FastAPI)                                      │
│  JWT Auth · Rate Limiting · SSL Termination                 │
└──────┬──────────────┬──────────────┬────────────────────────┘
       │              │              │
  [SOS Svc]   [Dispatch Svc]  [Routing Svc]  [Notify Svc]
       │              │              │
┌──────┴──────────────┴──────────────┴────────────────────────┐
│  AI ENGINE                                                  │
│  EfficientNet-B2 CNN │ XGBoost Hotspot │ OSRM │ Whisper     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│  DATA LAYER                                                 │
│  PostgreSQL + PostGIS │ Redis │ AWS S3 │ iRAD Feed │ Celery │
└─────────────────────────────────────────────────────────────┘
```

---

## How It Works

1. **SOS Trigger** — a victim (or bystander) taps the SOS button in the mobile app. GPS location is captured within 5 seconds, with retry logic for poor signal conditions.
2. **Severity Classification** — an optional crash photo is uploaded and run through the EfficientNet-B2 severity model, returning a result in under 2 seconds.
3. **Dispatch** — the dispatcher dashboard surfaces the incident with the nearest available ambulances ranked by ETA; a coordinator assigns a unit in one click, or the system can auto-assign based on configured rules.
4. **Live Routing** — the assigned crew gets turn-by-turn navigation, with the route recomputed roughly every 30 seconds as traffic conditions change.
5. **Hospital Pre-Alert** — the destination hospital is notified ahead of arrival so triage can be prepped in advance.
6. **Family Notification** — emergency contacts receive an SMS with a live tracking link, no login required.
7. **Offline Fallback** — if data connectivity is unavailable, the system falls back to an SMS-based SOS path.
8. **Hotspot Intelligence** — historical incident data feeds a rolling XGBoost model that refreshes an accident hotspot heatmap every 6 hours, useful for proactive resource positioning.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+
- Python 3.11+

### 1. Clone and configure

```bash
git clone https://github.com/MilindLate/Road-Safety-CtrlAltElite
cd Road-Safety-CtrlAltElite

# Copy env template
cp backend/.env.example backend/.env.local
# Edit backend/.env.local with your API keys:
#   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
#   GOOGLE_MAPS_API_KEY
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

### 2. Start all services

```bash
docker compose up -d

# Check all services are healthy
docker compose ps

# View backend logs
docker compose logs -f backend
```

### 3. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Seed sample data (development)

```bash
docker compose exec backend python scripts/seed_data.py
```

### 5. Access the dashboard

Open [http://localhost:3000](http://localhost:3000) — login with seeded dispatcher credentials:
- Email: `dispatcher@safereach.dev`
- Password: `SafeReach2026!`

API documentation: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

---

## Development

### Backend only

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Start FastAPI with hot reload
uvicorn app.main:app --reload --port 8000

# Run tests
pytest app/tests/ -v --cov=app
```

### Frontend only

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### Mobile app

```bash
cd mobile
npm install

# Start Expo development server
npx expo start

# Run on Android emulator
npx expo start --android

# Run on iOS simulator (Mac only)
npx expo start --ios
```

### Train AI models

```bash
cd notebooks

# Train Severity CNN (requires CRASH_DATASET_PATH env var for real data)
python severity_cnn/train_severity_cnn.py

# Train Hotspot XGBoost
python hotspot_model/train_hotspot_xgboost.py

# Copy trained models to backend
cp severity_cnn/models/severity_cnn.pt ../backend/app/ai/models/
cp hotspot_model/models/hotspot_xgboost.pkl ../backend/app/ai/models/
```

---

## Repository Structure

```
Road-Safety-CtrlAltElite/
├── backend/                   FastAPI services
│   ├── app/
│   │   ├── api/v1/endpoints/  Route handlers
│   │   ├── core/              Config, DB, Redis, Security
│   │   ├── models/            SQLAlchemy ORM models
│   │   ├── schemas/           Pydantic request/response
│   │   ├── services/          Business logic
│   │   │   ├── sos_service.py        SOS pipeline
│   │   │   ├── ai_service.py         CNN + XGBoost inference
│   │   │   ├── routing_service.py    OSRM + Google Maps
│   │   │   ├── notification_service.py  Twilio + FCM
│   │   │   ├── geocoding_service.py   Address ↔ coordinates
│   │   │   ├── bhashini_service.py    Multilingual support
│   │   │   └── s3_service.py         Photo upload
│   │   ├── tasks/             Celery async tasks
│   │   └── tests/             pytest test suites
│   ├── alembic/               Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                  Next.js dispatcher dashboard
│   ├── src/
│   │   ├── pages/             index.jsx, track/[token].jsx
│   │   └── components/        IncidentMap, TrackerMap
│   ├── next.config.js
│   └── package.json
├── mobile/                    React Native victim + crew apps
│   ├── src/screens/
│   │   ├── SOSScreen.jsx            Victim — single SOS button
│   │   ├── CrewNavigationScreen.jsx  Crew — turn-by-turn nav
│   │   └── SettingsScreen.jsx       Emergency contact setup
│   ├── app.json               Expo config
│   └── package.json
├── notebooks/
│   ├── severity_cnn/
│   │   └── train_severity_cnn.py    EfficientNet-B2 training
│   └── hotspot_model/
│       └── train_hotspot_xgboost.py  XGBoost training
├── docker-compose.yml
├── .github/workflows/ci.yml   CI/CD pipeline
└── README.md
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sos/trigger` | Victim SOS activation |
| `POST` | `/api/v1/sos/photo/{id}` | Crash photo upload |
| `POST` | `/api/v1/sos/offline` | SMS fallback |
| `GET`  | `/api/v1/incidents/` | List incidents (dispatcher) |
| `GET`  | `/api/v1/incidents/{id}` | Incident detail |
| `POST` | `/api/v1/dispatch/assign` | Assign ambulance |
| `GET`  | `/api/v1/dispatch/candidates/{id}` | Nearest free units |
| `PUT`  | `/api/v1/dispatch/status/{id}` | Update lifecycle status |
| `PUT`  | `/api/v1/ambulances/location` | Crew location update |
| `GET`  | `/api/v1/hospitals/nearby` | Nearest hospitals |
| `GET`  | `/api/v1/tracker/data?token=...` | Family tracker data |
| `POST` | `/api/v1/auth/device/register` | Device registration |
| `POST` | `/api/v1/auth/dispatcher/login` | Dashboard login |

---

## Key Functional Capabilities

| Capability | Implementation |
|------------|-----------------|
| GPS capture within 5s of SOS | `SOSScreen.jsx` with retry logic |
| Photo upload within 10s | Background upload + compression |
| Severity result within 2s | `ai_service.py` with 1.5s timeout |
| One-click unit assignment | `dispatch/assign` endpoint |
| Route recomputed every 30s | `routing_service.py` + Socket.io push |
| Family SMS within 60s | `notification_service.py` via Twilio |
| Hospital pre-alert 10 min before arrival | Celery scheduled task |
| SMS fallback when offline | `/sos/offline` + service worker |
| Voice SOS detection | Whisper-tiny on-device module |
| Hotspot heatmap refreshed every 6h | Celery beat `refresh_hotspot_grid` |

---

## Technology Stack

**Backend:** FastAPI 0.110 · PostgreSQL 15 + PostGIS 3.4 · Redis 7.2 · Celery 5.3 · SQLAlchemy 2.0 · uvicorn

**Frontend:** Next.js 14 · Tailwind CSS 3.4 · Socket.io · D3.js · Recharts · Leaflet

**Mobile:** React Native 0.73 · Expo 50 · React Native Maps · Socket.io Client

**AI/ML:** PyTorch 2.0 · EfficientNet-B2 · XGBoost 2.0 · OSRM 5.27 · Whisper-tiny · SHAP

**Infrastructure:** Docker · GitHub Actions · Railway · Vercel · AWS S3

**External APIs:** Twilio SMS · Firebase FCM · Google Maps · Open-Meteo · Bhashini · iRAD/eDAR

---

## Social Impact

Based on published research, a **12-minute reduction** in response time across Indian highway crashes is estimated to prevent **15,000–20,000 fatalities annually** if adopted nationwide. SafeReach is designed to integrate with existing national infrastructure (iRAD, MoRTH 112, NHA) rather than replace it.

---

