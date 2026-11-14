from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .domain import DispatchService, demo_service


class VisionInput(BaseModel):
    smoke_density: str = Field(pattern="^(none|light|moderate|heavy)$")
    visible_flames: bool = False
    blocked_exit: bool = False


class OverrideInput(BaseModel):
    note: str = Field(min_length=3, max_length=280)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.dispatch = demo_service()
    yield


app = FastAPI(title="AGNI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def service() -> DispatchService:
    return app.state.dispatch


def incident_or_404(incident_id: str):
    incident = service().incidents.get(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident


@app.get("/health")
def health():
    return {"status": "ok", "mode": "demo"}


@app.get("/api/incidents")
def list_incidents():
    return [incident.public() for incident in service().incidents.values()]


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    return incident_or_404(incident_id).public()


@app.post("/api/incidents/{incident_id}/vision")
def assess_vision(incident_id: str, payload: VisionInput):
    incident_or_404(incident_id)
    return service().record_vision(incident_id, **payload.model_dump()).public()


@app.post("/api/incidents/{incident_id}/dispatch")
def dispatch(incident_id: str):
    incident_or_404(incident_id)
    try:
        return service().dispatch(incident_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.post("/api/incidents/{incident_id}/override")
def override(incident_id: str, payload: OverrideInput):
    incident_or_404(incident_id)
    return service().enable_override(incident_id, payload.note).public()


@app.get("/api/events")
async def events():
    async def stream():
        while True:
            payload = json.dumps([item.public() for item in service().incidents.values()])
            yield f"event: incidents\ndata: {payload}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(stream(), media_type="text/event-stream")

