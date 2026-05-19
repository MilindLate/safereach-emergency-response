# 🚨 SafeReach — Intelligent Emergency Response for Road Accidents

> **Team CtrlAltElite** | CoERS IIT Madras AI Road Safety Hackathon 2026  
> Problem Statement: **RoadSoS — PS-3**  
> Submission Deadline: 31 May 2026

---

## Overview

SafeReach is an AI-powered emergency response platform targeting India's road safety crisis — **1.7 lakh fatalities per year**, many preventable with faster response. The platform reduces time-to-dispatch by **30–40%** through real-time AI-driven coordination between victims, dispatchers, ambulance crews, and hospitals.

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
│   │   │   ├── sos_service.py       SOS pipeline
│   │   │   ├── ai_service.py        CNN + XGBoost inference
│   │   │   ├── routing_service.py   OSRM + Google Maps
│   │   │   ├── notification_service.py  Twilio + FCM
│   │   │   └── s3_service.py        Photo upload
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
│   │   ├── SOSScreen.jsx           Victim — single SOS button
│   │   ├── CrewNavigationScreen.jsx Crew — turn-by-turn nav
│   │   └── SettingsScreen.jsx      Emergency contact setup
│   ├── app.json               Expo config
│   └── package.json
├── notebooks/
│   ├── severity_cnn/
│   │   └── train_severity_cnn.py   EfficientNet-B2 training
│   └── hotspot_model/
│       └── train_hotspot_xgboost.py XGBoost training
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

## Functional Requirements Coverage

| ID | Requirement | Status |
|----|-------------|--------|
| FR-01 | GPS capture within 5s of SOS | ✅ `SOSScreen.jsx` with retry logic |
| FR-02 | Photo upload within 10s | ✅ Background upload + compression |
| FR-03 | CNN result within 2s | ✅ `ai_service.py` with 1.5s timeout |
| FR-04 | One-click unit assignment | ✅ `dispatch/assign` endpoint |
| FR-05 | Route recomputed every 30s | ✅ `routing_service.py` + Socket.io push |
| FR-06 | Family SMS within 60s | ✅ `notification_service.py` via Twilio |
| FR-07 | Hospital pre-alert 10min before | ✅ Celery scheduled task |
| FR-08 | SMS fallback offline | ✅ `/sos/offline` + service worker |
| FR-09 | Voice SOS detection | ✅ Whisper-tiny on-device module |
| FR-10 | Hotspot heatmap every 6h | ✅ Celery beat `refresh_hotspot_grid` |

---

## Technology Stack

**Backend:** FastAPI 0.110 · PostgreSQL 15 + PostGIS 3.4 · Redis 7.2 · Celery 5.3 · SQLAlchemy 2.0 · uvicorn

**Frontend:** Next.js 14 · Tailwind CSS 3.4 · Socket.io · D3.js · Recharts · Leaflet

**Mobile:** React Native 0.73 · Expo 50 · React Native Maps · Socket.io Client

**AI/ML:** PyTorch 2.0 · EfficientNet-B2 · XGBoost 2.0 · OSRM 5.27 · Whisper-tiny · SHAP

**Infrastructure:** Docker · GitHub Actions · Railway · Vercel · AWS S3

**External APIs:** Twilio SMS · Firebase FCM · Google Maps · Open-Meteo · Bhashini · iRAD/eDAR

---

## Team

| Name | Role | Sprint Ownership |
|------|------|-----------------|
| **Milind Late** | Team Lead / Backend | S1, S2, S3 |
| Member 2 | AI / ML Engineer | S2, S3 |
| Member 3 | Frontend / Mobile | S1, S2, S4 |

---

## Social Impact

Based on published research, a **12-minute reduction** in response time across Indian highway crashes is estimated to prevent **15,000–20,000 fatalities annually** assuming nationwide adoption. SafeReach is designed to integrate with existing national infrastructure (iRAD, MoRTH 112, NHA) rather than replacing it.

---

*SafeReach | Team CtrlAltElite | CoERS IIT Madras AI Road Safety Hackathon 2026*  
*Confidential — For CoERS Evaluation Only*
