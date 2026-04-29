# Operations Intelligence Control Tower

## Overview

Operations Intelligence Control Tower is a real-time manufacturing dashboard for monitoring operational performance, production losses, anomalies, and AI-generated decision recommendations.

This system simulates a real-time industrial analytics platform used in manufacturing environments.

Key capabilities:
- Ingests operational data (CSV or simulated stream)
- Calculates OEE and identifies performance losses
- Detects anomalies in machine behavior
- Quantifies financial impact of operational inefficiencies
- Generates AI-driven recommendations for maintenance and process improvement

Designed to mimic real-world plant decision systems where engineers monitor production, detect issues, and take immediate action.

## Features

- OEE monitoring with Availability, Performance, Quality, and overall OEE metrics
- Live WebSocket streaming from the backend to the dashboard
- Anomaly detection for downtime, speed loss, and quality issues
- AI decision recommendations based on loss drivers and operational trends
- Revenue impact modeling for production losses

## Tech Stack

- FastAPI backend
- React frontend
- WebSockets for live updates
- Python analytics modules
- Recharts for dashboard visualizations
- TailwindCSS for UI styling

## Architecture

```text
Synthetic Production Data
        |
        v
FastAPI Backend
  - OEE calculation
  - Loss classification
  - Anomaly detection
  - Financial impact
  - AI decisions
        |
        | REST APIs + WebSocket /ws
        v
React Control Tower Dashboard
  - KPI cards
  - OEE trend chart
  - Loss breakdown
  - Alerts
  - AI decision panel
```

## How to Run

### Backend

```powershell
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend URLs:

```text
API:       http://localhost:8000
WebSocket: ws://localhost:8000/ws
```

### Frontend

Create `frontend/.env.local`:

```env
VITE_API_BASE=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

Run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

## Demo

Demo link and screenshots coming soon.
