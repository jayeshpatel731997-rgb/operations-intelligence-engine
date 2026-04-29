import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.engine import OperationsEngine

settings = get_settings()
engine = OperationsEngine(settings)
logger = logging.getLogger("operations_intelligence.websocket")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_simulation_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Operations Intelligence Engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _simulation_loop() -> None:
    while True:
        await engine.tick()
        await asyncio.sleep(settings.simulation_interval_seconds)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/snapshot")
async def get_snapshot():
    return await engine.snapshot()


@app.post("/api/insights/generate")
async def generate_insight():
    return await engine.tick(force_insight=True)


@app.websocket("/ws")
async def operations_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket connected: %s", client)
    try:
        while True:
            snapshot = await engine.snapshot()
            await websocket.send_json(snapshot.model_dump(mode="json"))
            await asyncio.sleep(settings.simulation_interval_seconds)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", client)
        return
