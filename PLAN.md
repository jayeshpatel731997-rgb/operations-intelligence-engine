# Operations Intelligence Engine Implementation Plan

## Summary

Build a local MVP OEE system with a FastAPI backend, React dashboard, synthetic machine telemetry, in-memory state, and OpenAI-generated operations insights.

The dashboard shows live OEE, Availability/Performance/Quality, Six Big Losses breakdown, revenue loss, detected anomalies, and root-cause insight text. Real-time behavior runs through FastAPI `asyncio` background tasks and WebSocket updates.

## Key Changes

- FastAPI backend under `backend/` with REST endpoints, WebSocket streaming, synthetic simulation, OEE calculation, Six Big Losses classification, financial impact, anomaly detection, and OpenAI-first insight generation.
- React + Vite frontend under `frontend/` with live KPI tiles, loss breakdown, machine status, anomaly list, and AI insights.
- Project setup docs and examples: `README.md`, `.env.example`, `backend/requirements.txt`, and `frontend/package.json`.

## Interfaces

- `GET /health`
- `GET /api/snapshot`
- `POST /api/insights/generate`
- `WebSocket /ws/operations`

WebSocket payload fields:

- `timestamp`
- `machine`
- `telemetry`
- `oee`
- `losses`
- `financialImpact`
- `anomalies`
- `insight`

## Assumptions

- V1 is an in-memory live demo, not a persistent historian.
- Async work uses FastAPI background tasks, not Modal.
- OpenAI is the first AI provider.
- Synthetic data is enough for v1; no real machine integrations are included.
- Revenue loss uses configurable defaults until real plant economics are provided.
