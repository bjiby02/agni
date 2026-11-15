from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env() -> None:
    path = ROOT / ".env"
    if not path.exists(): return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_env()

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import bus, db
from .config import settings
from . import vision
from . import landmarks as landmark_service
from . import merge as merge_service
from . import spread
from . import warnings as warning_service
from . import routing
from . import evidence as evidence_service
from . import pollers
from .services import serial_bridge, eleven, gemini, neon
from sim import surge as surge_runner
import feeds
import geo
import swarm


class IncidentIn(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=120)
    landmark_text: str = Field(min_length=1, max_length=300)
    what_seen: str = Field(default="unknown", max_length=1000)
    language: str = Field(default="en", max_length=12)
    address_text: str | None = Field(default=None, max_length=300)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class BearingIn(BaseModel):
    conversation_id: str
    direction_words: str | None = Field(default=None, max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    bearing_deg: float | None = Field(default=None, ge=0, lt=360)
    source: str = "words"


class VisionInput(BaseModel):
    smoke_density: Literal["none", "light", "moderate", "heavy", "unknown"]
    visible_flames: bool = False
    blocked_exit: bool = False
    reason: str = Field(default="Demo assessment", max_length=240)


class DecisionInput(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=500)


class DispatchInput(BaseModel):
    unit_id: str
    approved_by: str = Field(min_length=1, max_length=100)


class OverrideInput(BaseModel):
    note: str = Field(min_length=3, max_length=280)
    actor: str = "dispatcher"


class SettingsInput(BaseModel):
    overflow_enabled: bool


class NeedsInput(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=120)
    mobility: bool = False
    people: int | None = Field(default=None, ge=1, le=50)
    notes: str = Field(default="", max_length=300)


class GuidanceInput(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=120)


class RescueInput(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=120)
    digits: str = Field(default="", max_length=8)
    said_help: bool = False


class TranscriptInput(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=120)
    speaker: str = Field(min_length=1, max_length=24)
    text: str = Field(min_length=1, max_length=4000)
    lang: str | None = Field(default=None, max_length=12)


class RingInput(BaseModel):
    minutes: int = Field(default=30, ge=1, le=120)
    wind_to_deg: float = Field(ge=0, lt=360)


class WarningInput(BaseModel):
    languages: list[str] = Field(default_factory=lambda: ["en"], max_length=8)
    message_key: str = Field(default="wildfire_targeted_warning", min_length=1, max_length=80)


class SurgeInput(BaseModel):
    n: int = Field(default=75, ge=3, le=75)
    seconds: int = Field(default=90, ge=1, le=90)


class JumpInInput(BaseModel):
    actor: str = Field(default="dispatcher", min_length=1, max_length=100)


class HandBackInput(BaseModel):
    actor: str = Field(default="dispatcher", min_length=1, max_length=100)


class SignReportInput(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    edits: str = Field(default="", max_length=4000)


async def postcall(request: Request, x_agni_webhook_signature: str | None = Header(default=None)):
    """Accept a signed completion notice. Provider header format needs a live check."""
    secret=os.environ.get("ELEVENLABS_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(503,"Post-call webhook is disabled until its secret is set")
    body=await request.body()
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    supplied=(x_agni_webhook_signature or "").removeprefix("sha256=")
    if not hmac.compare_digest(expected,supplied):
        raise HTTPException(401,"Invalid post-call signature")
    try:
        payload=json.loads(body)
    except (json.JSONDecodeError,UnicodeDecodeError):
        raise HTTPException(400,"Invalid JSON payload")
    if not isinstance(payload,dict):
        raise HTTPException(400,"JSON body must be an object")
    details=payload.get("data") if isinstance(payload.get("data"),dict) else {}
    conversation_id=payload.get("conversation_id") or details.get("conversation_id")
    if not conversation_id:
        raise HTTPException(422,"conversation_id is required")
    with db.connect() as conn:
        updated=conn.execute("UPDATE calls SET state='ended',ended_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                             (conversation_id,)).rowcount
    if not updated:
        raise HTTPException(404,"Call not found")
    return {"ok":True,"provider_signature":"live-unverified"}


def _ensure_seed() -> None:
    with db.connect() as conn:
        has = conn.execute("SELECT 1 FROM incidents LIMIT 1").fetchone()
        if not has:
            iid = "inc_demo_torrey"
            conn.execute("INSERT INTO incidents(id,status,level,kind,title,lat,lon,location_src,description) VALUES(?,?,?,?,?,?,?,?,?)",
                         (iid,"possible",3,"fire","Possible smoke near Torrey Pines",32.866,-117.251,"demo","Demo incident. Confirm with a human."))
            conn.commit()
    if has is None:
        bus.emit("incident.created", "inc_demo_torrey", {"status":"possible","level":3,"lat":32.866,"lon":-117.251,"location_src":"demo","title":"Possible smoke near Torrey Pines"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    _ensure_seed()
    pollers.ensure_demo_hazards()
    yield


app = FastAPI(title="AGNI Incident API", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
app.add_api_route("/api/calls/postcall", postcall, methods=["POST"])


def operator(request: Request, authorization: str | None = Header(default=None)) -> str:
    expected = settings.operator_token or os.environ.get("OPS_TOKEN", "")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not supplied:
        supplied = request.query_params.get("token", "")
    if expected and supplied != expected:
        raise HTTPException(401, "Operator token required")
    if expected and supplied == expected:
        return "local-operator"
    if (not expected and settings.mock and request.client is not None
            and request.client.host in {"127.0.0.1", "::1", "testclient"}):
        return "local-operator"
    raise HTTPException(503, "Set OPS_TOKEN in .env")


def tool_auth(x_agni_tool_secret: str | None = Header(default=None)) -> None:
    expected = settings.tool_secret or os.environ.get("ELEVENLABS_TOOL_SECRET", "")
    if expected and x_agni_tool_secret != expected:
        raise HTTPException(401, "Invalid tool secret")
    if not expected:
        raise HTTPException(503, "Tool endpoint is disabled until ELEVENLABS_TOOL_SECRET is set")


def incident_or_404(iid: str) -> dict:
    item = db.incident(iid)
    if item is None: raise HTTPException(404, "Incident not found")
    return item


async def resolve_call_landmark(iid: str, conversation_id: str, spoken: str) -> None:
    """Resolve in the background. Only cached records may supply coordinates."""
    extracted = await asyncio.to_thread(landmark_service.extract_landmark, spoken)
    match = landmark_service.match_landmark(extracted["text"])
    detail = "Landmark matched to the local cache" if match else "No verified landmark match; location remains unknown"
    with db.connect() as conn:
        conn.execute("UPDATE calls SET landmark_text=? WHERE id=?", (extracted["text"], conversation_id))
        if match:
            why_line = "Caller landmark · " + str(match.get("name", "matched place"))
            conn.execute("UPDATE incidents SET lat=?,lon=?,location_src='caller',why_line=? WHERE id=?",
                         (match["lat"], match["lon"], why_line, iid))
            conn.execute("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail,updated_at) "
                         "VALUES(?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                         (iid,"caller_location","agree",detail))
        else:
            conn.execute("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail,updated_at) "
                         "VALUES(?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                         (iid,"caller_location","empty",detail))
    bus.emit("evidence.updated", iid, {"source":"caller_location","state":"agree" if match else "empty",
                                      "detail":detail,"lat":match["lat"] if match else None,
                                      "lon":match["lon"] if match else None,
                                      "location_src":"caller" if match else None,
                                      "why_line":("Caller landmark · " + str(match.get("name", "matched place"))) if match else None,
                                      "extraction_status":extracted["status"]})
    if match:
        merge_service.suggest_for_incident(iid)


@app.get("/health")
def health():
    return {"ok": True, "database": "sqlite", "mode": "mock" if settings.mock else "live-unverified",
            "overflow_enabled": db.overflow_enabled(),
            "firms_key_set": bool(os.environ.get("FIRMS_MAP_KEY")),
            "brightdata_key_set": bool(os.environ.get("BRIGHTDATA_API_TOKEN") or os.environ.get("BRIGHTDATA_API_KEY"))}


@app.get("/api/state")
def get_state(_: str = Depends(operator)):
    state = db.state()
    if settings.mock:
        state["feeds"] = {"status":"mock","wind":None,"wind_age_s":None,"camera_count":0,"cameras":[],
                          "fires":[],"hotspots":[],"note":"No external feeds are called in mock mode."}
        return state
    spot = feeds.area()
    if spot:
        sit = feeds.situation(spot["lat"],spot["lon"])
        state["feeds"] = {"center": spot, "wind": sit.get("wind"), "wind_age_s": sit.get("wind_age_s"),
                          "camera_count": sit.get("camera_count",0), "cameras": sit.get("cameras",[]),
                          "fires": sit.get("fires",[]), "hotspots": sit.get("hotspots",[]),
                          "firms_status":"ready" if os.environ.get("FIRMS_MAP_KEY") else "key_not_set",
                          "generated_at":sit.get("generated_at")}
    else:
        state["feeds"] = {"status":"area_not_configured"}
    return state


@app.get("/api/incidents")
def list_incidents(_: str = Depends(operator)):
    return db.state()["incidents"]


@app.get("/api/settings")
def get_settings(_: str = Depends(operator)):
    return {"overflow_enabled": db.overflow_enabled(), "mode": "mock" if settings.mock else "live-unverified"}


@app.put("/api/settings")
def put_settings(payload: SettingsInput, actor: str = Depends(operator)):
    with db.connect() as conn:
        conn.execute("UPDATE settings SET overflow_enabled=?,updated_by=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=1",
                     (int(payload.overflow_enabled), actor))
    return get_settings(actor)


@app.get("/api/incidents/{iid}")
def get_incident(iid: str, _: str = Depends(operator)):
    return incident_or_404(iid)


@app.get("/api/incidents/{iid}/evidence")
def evidence(iid: str, _: str = Depends(operator)):
    incident_or_404(iid)
    with db.connect() as conn:
        rows=[dict(r) for r in conn.execute("SELECT * FROM evidence WHERE incident_id=? ORDER BY source",(iid,))]
    if not rows:
        rows=evidence_service.default_rows(firms_key_set=bool(os.environ.get("FIRMS_MAP_KEY")))
    line = evidence_service.why_line(rows)
    if line:
        with db.connect() as conn:
            conn.execute("UPDATE incidents SET why_line=? WHERE id=?", (line, iid))
    return {"incident_id":iid,"rows":rows,"why_line":line or None}


@app.post("/api/tools/report_fire")
async def report_fire(payload: IncidentIn, _: None = Depends(tool_auth)):
    if not db.overflow_enabled():
        return {"incident_id":None,"overflow":False,"say":"Please hang up and dial 911."}
    with db.connect() as conn:
        call = conn.execute("SELECT incident_id FROM calls WHERE id=?", (payload.conversation_id,)).fetchone()
        if call and call["incident_id"]:
            iid = call["incident_id"]
            conn.execute("UPDATE calls SET landmark_text=?,language=? WHERE id=?",
                         (payload.landmark_text, payload.language, payload.conversation_id))
            return {"incident_id":iid,"overflow":True,"say":"Got it. Which way is the smoke from you?"}
        iid="inc_"+uuid4().hex[:10]
        conn.execute("INSERT INTO incidents(id,status,level,kind,title,lat,lon,location_src,description) VALUES(?,?,?,?,?,?,?,?,?)",
                     (iid,"possible",3,"fire","Possible fire report",payload.lat,payload.lon,"caller",payload.what_seen))
        conn.execute("INSERT INTO calls(id,incident_id,direction,language,landmark_text) VALUES(?,?,'inbound',?,?)",
                     (payload.conversation_id,iid,payload.language,payload.landmark_text))
    bus.emit("call.started",iid,{"call_id":payload.conversation_id,"direction":"inbound","language":payload.language})
    bus.emit("incident.created",iid,{"status":"possible","level":3,"lat":payload.lat,"lon":payload.lon,
                                     "location_src":"caller","landmark_text":payload.landmark_text,
                                     "title":"Possible fire report"})
    asyncio.create_task(resolve_call_landmark(iid, payload.conversation_id, payload.landmark_text))
    return {"incident_id":iid,"overflow":True,"say":"Got it. Which way is the smoke from you?"}


@app.post("/api/tools/add_bearing")
def add_bearing(payload: BearingIn, _: None = Depends(tool_auth)):
    with db.connect() as conn:
        call=conn.execute("SELECT incident_id FROM calls WHERE id=?",(payload.conversation_id,)).fetchone()
        if not call or not call["incident_id"]: raise HTTPException(404,"Call not found")
        iid=call["incident_id"]
        direction=payload.direction_words
        bearing=payload.bearing_deg
        if bearing is None and direction:
            directions={"n":0,"north":0,"ne":45,"northeast":45,"e":90,"east":90,
                        "se":135,"southeast":135,"s":180,"south":180,"sw":225,
                        "southwest":225,"w":270,"west":270,"nw":315,"northwest":315}
            bearing=directions.get(direction.strip().lower())
        conn.execute("INSERT INTO bearings(incident_id,call_id,lat,lon,bearing_deg,direction_words,source) VALUES(?,?,?,?,?,?,?)",
                     (iid,payload.conversation_id,payload.lat,payload.lon,bearing,direction,payload.source))
    ev=bus.emit("bearing.added",iid,{"call_id":payload.conversation_id,"lat":payload.lat,"lon":payload.lon,
                                    "bearing_deg":bearing,"direction_words":direction,"source":payload.source})
    if payload.lat is None or payload.lon is None or bearing is None:
        return {"say":"Thank you. Is anyone with you who cannot walk?"}
    with db.connect() as conn:
        rows=[dict(r) for r in conn.execute("SELECT lat,lon,bearing_deg,created_at FROM bearings WHERE incident_id=?",(iid,))]
    estimate=None
    if len(rows)>=2:
        reports=[]
        for r in rows:
            bearing=r["bearing_deg"]
            code=min(swarm.CODES,key=lambda name:abs((swarm.CODES[name]-bearing+180)%360-180))
            reports.append(swarm.Report(lat=r["lat"],lon=r["lon"],hazard=code,age_s=0))
        found=swarm.ignition(reports,min_reports=2)
        if found:
            estimate={"lat":found.lat,"lon":found.lon,"support":found.support,"spread_m":round(found.spread_m),"label":"estimate"}
            with db.connect() as conn:
                conn.execute("UPDATE incidents SET lat=?,lon=?,location_src='estimate',estimate_m=? WHERE id=?",(found.lat,found.lon,found.spread_m,iid)); conn.commit()
            bus.emit("estimate.updated",iid,estimate)
    return {"ok":True,"event_seq":ev["seq"],"estimate":estimate,"say":"Thank you. I have recorded the direction."}


@app.post("/api/tools/set_needs")
def set_needs(payload: NeedsInput, _: None = Depends(tool_auth)):
    with db.connect() as conn:
        call=conn.execute("SELECT incident_id,needs_json FROM calls WHERE id=?",(payload.conversation_id,)).fetchone()
        if not call: raise HTTPException(404,"Call not found")
        iid=call["incident_id"]
        needs={"mobility":payload.mobility,"people":payload.people,"notes":payload.notes}
        conn.execute("UPDATE calls SET needs_json=? WHERE id=?",(json.dumps(needs),payload.conversation_id))
        if payload.mobility and iid:
            conn.execute("UPDATE incidents SET immobile=1,level=MIN(level,2) WHERE id=?",(iid,))
    if iid:
        bus.emit("triage.result",iid,{"source":"caller_needs","immobile":payload.mobility,
                                      "people":payload.people,"priority_raised":payload.mobility})
    say="I've marked that someone cannot move. A dispatcher will review this." if payload.mobility else "Thank you. I have noted that."
    return {"say":say}


@app.post("/api/tools/get_guidance")
def get_guidance(payload: GuidanceInput, _: None = Depends(tool_auth)):
    with db.connect() as conn:
        call=conn.execute("SELECT incident_id FROM calls WHERE id=?",(payload.conversation_id,)).fetchone()
        if not call: raise HTTPException(404,"Call not found")
        iid=call["incident_id"]
        incident=conn.execute("SELECT status,assigned_unit FROM incidents WHERE id=?",(iid,)).fetchone() if iid else None
        dispatch=conn.execute("SELECT unit_id,eta_s,route_kind FROM dispatches WHERE incident_id=? ORDER BY id DESC LIMIT 1",(iid,)).fetchone() if iid else None
    confirmed=bool(incident and incident["status"] in {"confirmed","dispatched"})
    dispatched=bool(incident and incident["status"]=="dispatched")
    say="A dispatcher is reviewing your report. Stay where you are safe."
    eta_s=None
    if dispatched and dispatch:
        say=f"A dispatcher has sent {dispatch['unit_id']}. Stay where you are safe."
    elif dispatched:
        say="A dispatcher has sent help. Stay where you are safe."
    if dispatch and dispatch["route_kind"]=="road" and dispatch["eta_s"] is not None:
        eta_s=dispatch["eta_s"]
    return {"say":say,"incident_id":iid,"confirmed":confirmed,"dispatched":dispatched,
            "should_transfer":False,"shelter":None,"eta_s":eta_s}


@app.post("/api/tools/send_cam_link")
def send_cam_link(payload: GuidanceInput, _: None = Depends(tool_auth)):
    if settings.mock:
        return {"say":"A camera link is not available in this practice call."}
    # SMS is disabled until the opt-in and signed-link path is implemented.
    return {"say":"A camera link is not available yet. Please keep describing what you see."}


@app.post("/api/tools/request_rescue")
def request_rescue(payload: RescueInput, _: None = Depends(tool_auth)):
    with db.connect() as conn:
        call=conn.execute("SELECT incident_id FROM calls WHERE id=?",(payload.conversation_id,)).fetchone()
        if not call: raise HTTPException(404,"Call not found")
        iid=call["incident_id"]
        conn.execute("INSERT INTO rescues(incident_id,call_id,digits) VALUES(?,?,?)",
                     (iid,payload.conversation_id,payload.digits))
    bus.emit("rescue.requested",iid,{"call_id":payload.conversation_id,"digits":payload.digits,
                                    "said_help":payload.said_help})
    return {"say":"Help is noted. Stay where you are safe and keep your phone on."}


@app.post("/api/calls/transcript")
def add_transcript(payload: TranscriptInput, _: None = Depends(tool_auth)):
    with db.connect() as conn:
        call=conn.execute("SELECT incident_id FROM calls WHERE id=?",(payload.conversation_id,)).fetchone()
        if not call: raise HTTPException(404,"Call not found")
        conn.execute("INSERT INTO transcripts(call_id,speaker,text,lang) VALUES(?,?,?,?)",
                     (payload.conversation_id,payload.speaker,payload.text,payload.lang))
    bus.emit("call.transcript",call["incident_id"],{"call_id":payload.conversation_id,
                                                     "speaker":payload.speaker,"text":payload.text,"lang":payload.lang})
    return {"ok":True}


@app.post("/api/incidents/{iid}/vision")
def assess_vision(iid: str,payload: VisionInput,_: str=Depends(operator)):
    item=incident_or_404(iid)
    suggested=1 if payload.visible_flames or payload.blocked_exit or payload.smoke_density=="heavy" else (2 if payload.smoke_density=="moderate" else None)
    with db.connect() as conn:
        level=item["level"] if suggested is None else min(item["level"],suggested)
        conn.execute("UPDATE incidents SET level=? WHERE id=?",(level,iid)); conn.commit()
        conn.execute("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail) VALUES(?,?,?,?)",
                     (iid,"camera","agree" if suggested else "empty",payload.reason)); conn.commit()
    data={"source":"caller_frame","frame_source":"demo","label":payload.smoke_density,"flames_visible":payload.visible_flames,
          "blocked_exit":payload.blocked_exit,"reason":payload.reason,"suggested_level":suggested,"applied_level":level}
    bus.emit("triage.result",iid,data)
    bus.emit("evidence.updated",iid,{"rows":[{"source":"camera","state":"agree" if suggested else "empty","detail":payload.reason}],"status":"possible"})
    return incident_or_404(iid)


@app.post("/api/triage/vision/{iid}")
async def triage_uploaded_frame(iid: str, request: Request, _: str = Depends(operator)):
    """Assess one caller-approved image. Unknown results never change priority."""
    item=incident_or_404(iid)
    mime_type=request.headers.get("content-type","").split(";",1)[0].strip().lower()
    if mime_type not in {"image/jpeg","image/png","image/webp"}:
        raise HTTPException(415,"Upload a JPEG, PNG, or WebP image")
    blob=await request.body()
    if len(blob)>5_000_000: raise HTTPException(413,"Image must be 5 MB or smaller")
    result=await asyncio.to_thread(vision.assess,blob,mime_type)
    suggested=result.get("recommended_level")
    # Vision is allowed to raise priority only. It cannot confirm a fire.
    level=item["level"]
    if result["label"] in {"smoke","flames"} and isinstance(suggested,int):
        level=min(level,suggested)
    with db.connect() as conn:
        conn.execute("UPDATE incidents SET level=? WHERE id=?",(level,iid))
        conn.execute("INSERT OR REPLACE INTO evidence(incident_id,source,state,detail) VALUES(?,?,?,?)",
                     (iid,"cameras","agree" if result["label"] in {"smoke","flames"} else "empty",result["reason"]))
        conn.commit()
    event_data={"source":"caller_frame","frame_source":"live","label":result["label"],"box":result.get("box_2d"),
                "flames_visible":result.get("flames_visible",False),"reason":result["reason"],"latency_ms":None,
                "status":result["status"],"applied_level":level}
    bus.emit("triage.result",iid,event_data)
    return event_data


@app.post("/api/incidents/{iid}/confirm")
def confirm(iid: str,payload: DecisionInput,_: str=Depends(operator)):
    incident_or_404(iid)
    with db.connect() as conn:
        conn.execute("UPDATE incidents SET status='confirmed',confirmed_by=?,confirmed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(payload.actor,iid))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",(iid,payload.actor,"confirm",json.dumps({"note":payload.note}))); conn.commit()
    bus.emit("evidence.updated",iid,{"confirmed_by":payload.actor,"note":payload.note,"fire_status":"confirmed"})
    return incident_or_404(iid)


@app.post("/api/incidents/{iid}/reject")
def reject(iid: str,payload: DecisionInput,_: str=Depends(operator)):
    incident_or_404(iid)
    with db.connect() as conn:
        conn.execute("UPDATE incidents SET status='rejected' WHERE id=?",(iid,))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",(iid,payload.actor,"reject",json.dumps({"reason":payload.note}))); conn.commit()
    bus.emit("evidence.updated",iid,{"rejected_by":payload.actor,"reason":payload.note,"fire_status":"rejected"})
    return incident_or_404(iid)


@app.post("/api/merges/{merge_id}/accept")
def accept_merge(merge_id: int, actor: str = Depends(operator)):
    try:
        return merge_service.accept(merge_id, actor)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))


@app.post("/api/merges/{merge_id}/keep-apart")
def keep_merge_apart(merge_id: int, actor: str = Depends(operator)):
    try:
        return merge_service.keep_apart(merge_id, actor)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))


@app.post("/api/merges/{merge_id}/undo")
def undo_merge(merge_id: int, actor: str = Depends(operator)):
    try:
        return merge_service.undo(merge_id, actor)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))


@app.get("/api/cameras")
def cameras(lat: float,lon: float,n: int=3,_: str=Depends(operator)):
    cams=[] if settings.mock else feeds.cameras(lat,lon)
    result=cams[:max(1,min(n,12))]
    bus.emit("cameras.selected",None,{"cameras":[{k:v for k,v in cam.items() if k!="image"} for cam in result]})
    return {"cameras":result,"count":len(result)}


@app.get("/api/cameras/{camera_id}/frame")
def camera_frame(camera_id: str,lat: float,lon: float,_: str=Depends(operator)):
    from fastapi.responses import Response
    if settings.mock: raise HTTPException(503,"Camera frames are unavailable in mock mode")
    blob=feeds.camera_jpeg(lat,lon,camera_id)
    if not blob: raise HTTPException(404,"Camera image is not available")
    return Response(blob,media_type="image/jpeg",headers={"Cache-Control":"public, max-age=10"})


@app.get("/api/satellite")
def satellite(lat: float,lon: float,_: str=Depends(operator)):
    hits=[] if settings.mock else feeds.hotspots(lat,lon)
    data={"source":"firms","detections":hits,"count":len(hits),"status":"mock" if settings.mock else ("ready" if os.environ.get("FIRMS_MAP_KEY") else "key_not_set"),
          "reason":"No detection yet; satellite data can lag hours" if not hits else None,"checked_at":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    bus.emit("satellite.result",None,data)
    return data


@app.get("/api/incidents/{iid}/route")
def route(iid: str,_: str=Depends(operator)):
    item=incident_or_404(iid)
    with db.connect() as conn:
        units=[dict(r) for r in conn.execute("SELECT * FROM units WHERE status='available'")]
        raw_hazards=[dict(r) for r in conn.execute("SELECT * FROM hazards WHERE kind='road_closure'")]
        ring=conn.execute("SELECT wind_json FROM rings WHERE incident_id=? ORDER BY id DESC LIMIT 1", (iid,)).fetchone()
    if item["lat"] is None or item["lon"] is None: raise HTTPException(409,"Incident location is not known")
    closures=[]
    for hazard in raw_hazards:
        try:
            closures.append({**hazard, "geometry": json.loads(hazard.get("geometry_json") or "null")})
        except json.JSONDecodeError:
            continue
    wind_to_deg=None
    if ring:
        try:
            wind_to_deg=json.loads(ring["wind_json"]).get("to_deg")
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    ranked=routing.route_options((item["lat"], item["lon"]), units, closures)
    shelters=routing.choose_shelter((item["lat"], item["lon"]), None, wind_to_deg)
    data={"units":ranked[:3],"route_kind":"estimate","avoids":[row["blocked_by"] for row in ranked if row["blocked_by"]],
          "shelter":shelters["shelter"],"refused":shelters["refused"],
          "note":"Straight-line estimate. It is not a safe-route guarantee."}
    bus.emit("route.ready",iid,data)
    return data


@app.post("/api/incidents/{iid}/ring")
def create_ring(iid: str, payload: RingInput, _: str = Depends(operator)):
    incident = incident_or_404(iid)
    if incident["lat"] is None or incident["lon"] is None:
        raise HTTPException(409, "A verified caller location or bearing estimate is required")
    ring = spread.estimate_ring(float(incident["lat"]), float(incident["lon"]), payload.wind_to_deg, payload.minutes)
    with db.connect() as conn:
        cur = conn.execute("INSERT INTO rings(incident_id,minutes,geom_json,wind_json,homes_est) VALUES(?,?,?,?,NULL)",
                           (iid, payload.minutes, json.dumps(ring["geometry"]),
                            json.dumps({"to_deg": payload.wind_to_deg, "status": "manual"})))
    data = {"ring_id": cur.lastrowid, "incident_id": iid, "label": ring["properties"]["label"],
            "geojson": ring, "wind_to_deg": payload.wind_to_deg}
    bus.emit("ring.updated", iid, data)
    return data


@app.post("/api/warnings/{iid}")
def send_warning(iid: str, payload: WarningInput, idempotency_key: str = Header(alias="Idempotency-Key"),
                 actor: str = Depends(operator)):
    incident = incident_or_404(iid)
    if incident["status"] not in {"confirmed", "dispatched"}:
        raise HTTPException(409, "A dispatcher must confirm the incident before a warning")
    with db.connect() as conn:
        prior = conn.execute("SELECT * FROM warnings WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if prior:
            if prior["incident_id"] != iid:
                raise HTTPException(409, "Idempotency key was used for a different incident")
            return {"warning_id": prior["id"], "recipients": prior["recipients"], "replayed": True, "status": prior["status"]}
        ring_row = conn.execute("SELECT * FROM rings WHERE incident_id=? ORDER BY id DESC LIMIT 1", (iid,)).fetchone()
        if not ring_row:
            raise HTTPException(409, "Create a human-reviewed spread estimate before a warning")
        ring = {"type": "Feature", "properties": {"label": f"{ring_row['minutes']}-min estimate"},
                "geometry": json.loads(ring_row["geom_json"])}
        recipients = warning_service.targeted_contacts(ring)
        if not recipients:
            raise HTTPException(409, "No opted-in recipients are inside the estimate ring")
        # This project has no live dialer implementation. Persist the approved batch only.
        status = "mock_queued" if settings.mock else "live_unverified"
        cur = conn.execute(
            "INSERT INTO warnings(incident_id,approved_by,recipients,languages_json,message_key,idempotency_key,status) VALUES(?,?,?,?,?,?,?)",
            (iid, actor, len(recipients), json.dumps(payload.languages), payload.message_key, idempotency_key, status),
        )
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (iid, actor, "warning_approved", json.dumps({"warning_id": cur.lastrowid, "recipients": len(recipients)})))
    data = {"warning_id": cur.lastrowid, "incident_id": iid, "recipients": len(recipients),
            "recipient_ids": [str(recipient.get("id", "")) for recipient in recipients],
            "languages": payload.languages, "status": status}
    bus.emit("warning.sent", iid, data)
    return data


def _read_measured(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


@app.get("/api/proof")
def proof(_: str = Depends(operator)):
    return {"sim": _read_measured(ROOT / "backend" / "sim" / "sim.json"),
            "eval": _read_measured(ROOT / "backend" / "ml" / "eval" / "eval.json")}


@app.post("/api/ops/surge")
def run_surge(payload: SurgeInput, _: str = Depends(operator)):
    result = surge_runner.run(payload.n, payload.seconds)
    bus.emit("surge.stats", None, result)
    return result


@app.post("/api/incidents/{iid}/dispatch")
def dispatch(iid: str,payload: DispatchInput,idempotency_key: str=Header(alias="Idempotency-Key"),_: str=Depends(operator)):
    item=incident_or_404(iid)
    if item["status"] not in {"confirmed","dispatched"}: raise HTTPException(409,"A dispatcher must confirm the incident first")
    with db.connect() as conn:
        prior=conn.execute("SELECT * FROM dispatches WHERE idempotency_key=?",(idempotency_key,)).fetchone()
        if prior:
            if prior["incident_id"] != iid:
                raise HTTPException(409,"Idempotency key was used for a different incident")
            return {"id":prior["id"],"incident_id":iid,"unit_id":prior["unit_id"],"replayed":True}
        unit=conn.execute("SELECT * FROM units WHERE id=? AND status='available'",(payload.unit_id,)).fetchone()
        if not unit: raise HTTPException(409,"Unit is not available")
        cur=conn.execute("INSERT INTO dispatches(incident_id,unit_id,idempotency_key,approved_by,detail_json) VALUES(?,?,?,?,?)",
                         (iid,payload.unit_id,idempotency_key,payload.approved_by,json.dumps({})))
        conn.execute("UPDATE units SET status='assigned' WHERE id=?",(payload.unit_id,))
        conn.execute("UPDATE incidents SET status='dispatched',assigned_unit=? WHERE id=?",(payload.unit_id,iid)); conn.commit()
    serial = serial_bridge.write_dispatch(payload.unit_id)
    data={"dispatch_id":cur.lastrowid,"unit_id":payload.unit_id,"callsign":unit["callsign"],
          "approved_by":payload.approved_by,"idempotency_key":idempotency_key,"serial":serial}
    bus.emit("unit.dispatched",iid,data)
    return data


def _live_call_for_incident(iid: str):
    with db.connect() as conn:
        return conn.execute(
            "SELECT * FROM calls WHERE incident_id=? AND state IN ('live','human') ORDER BY started_at DESC LIMIT 1",
            (iid,),
        ).fetchone()


def _do_jump_in(iid: str, payload: JumpInInput, call_id: str | None = None, note: str | None = None):
    call = None
    if call_id:
        with db.connect() as conn:
            call = conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        if not call:
            raise HTTPException(404, "Call not found")
        iid = call["incident_id"]
    incident = incident_or_404(iid)
    if call is None:
        call = _live_call_for_incident(iid)
    if not call:
        raise HTTPException(409, "No live call to transfer")
    with db.connect() as conn:
        lines = [dict(r) for r in conn.execute(
            "SELECT speaker,text,lang,ts FROM transcripts WHERE call_id=? ORDER BY id DESC LIMIT 3",
            (call["id"],))]
        lines.reverse()
        conn.execute("UPDATE calls SET state='human' WHERE id=?", (call["id"],))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (iid, payload.actor, "jump_in", json.dumps({"call_id": call["id"], "note": note or ""})))
    summary = note or gemini.handoff_summary(lines, incident)
    transfer = eleven.transfer_to_dispatcher(call["id"], summary)
    data = {"summary": summary, "to": "dispatcher", "mode": "jump_in",
            "call_id": call["id"], "transfer": transfer}
    bus.emit("handoff.started", iid, data)
    return data


def _do_hand_back(iid: str, payload: HandBackInput, call_id: str | None = None):
    call = None
    if call_id:
        with db.connect() as conn:
            call = conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        if not call:
            raise HTTPException(404, "Call not found")
        iid = call["incident_id"]
    incident_or_404(iid)
    if call is None:
        with db.connect() as conn:
            call = conn.execute(
                "SELECT * FROM calls WHERE incident_id=? AND state='human' ORDER BY started_at DESC LIMIT 1",
                (iid,),
            ).fetchone()
    if not call:
        raise HTTPException(409, "No human-held call to hand back")
    with db.connect() as conn:
        conn.execute("UPDATE calls SET state='live' WHERE id=?", (call["id"],))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (iid, payload.actor, "hand_back", json.dumps({"call_id": call["id"], "mode": "callback"})))
    callback = eleven.callback_caller(call["id"], None, {"incident_id": iid, "mode": "callback"})
    data = {"resumed_by": "agent", "mode": "callback", "call_id": call["id"], "callback": callback}
    bus.emit("handoff.ended", iid, data)
    return data


@app.post("/api/incidents/{iid}/override")
def override(iid: str, payload: OverrideInput, _: str = Depends(operator)):
    """Legacy alias for JUMP IN when only a note is supplied."""
    return _do_jump_in(iid, JumpInInput(actor=payload.actor), note=payload.note)


@app.post("/api/incidents/{iid}/jump-in")
def jump_in_incident(iid: str, payload: JumpInInput | None = None, _: str = Depends(operator)):
    return _do_jump_in(iid, payload or JumpInInput())


@app.post("/api/calls/{call_id}/jump-in")
def jump_in_call(call_id: str, payload: JumpInInput | None = None, _: str = Depends(operator)):
    return _do_jump_in("", payload or JumpInInput(), call_id=call_id)


@app.post("/api/incidents/{iid}/hand-back")
def hand_back_incident(iid: str, payload: HandBackInput | None = None, _: str = Depends(operator)):
    return _do_hand_back(iid, payload or HandBackInput())


@app.post("/api/calls/{call_id}/hand-back")
def hand_back_call(call_id: str, payload: HandBackInput | None = None, _: str = Depends(operator)):
    return _do_hand_back("", payload or HandBackInput(), call_id=call_id)


@app.get("/api/incidents/{iid}/report")
def get_report(iid: str, _: str = Depends(operator)):
    incident = incident_or_404(iid)
    with db.connect() as conn:
        prior = conn.execute("SELECT * FROM reports WHERE incident_id=?", (iid,)).fetchone()
        events = [dict(r) for r in conn.execute(
            "SELECT type,ts,data_json FROM events WHERE incident_id=? ORDER BY seq", (iid,))]
    if prior:
        return dict(prior) | {"clock": json.loads(prior["clock_json"] or "{}")}
    draft = gemini.report_draft(
        [{"type": e["type"], "ts": e["ts"], "data": json.loads(e["data_json"])} for e in events],
        incident,
    )
    clock = {
        "first_event_ts": events[0]["ts"] if events else None,
        "last_event_ts": events[-1]["ts"] if events else None,
        "event_count": len(events),
    }
    with db.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO reports(incident_id,draft,clock_json) VALUES(?,?,?)",
                     (iid, draft, json.dumps(clock)))
    return {"incident_id": iid, "draft": draft, "signed_by": None, "signed_at": None, "clock": clock}


@app.post("/api/incidents/{iid}/report/sign")
def sign_report(iid: str, payload: SignReportInput, _: str = Depends(operator)):
    incident_or_404(iid)
    report = get_report(iid, _)
    draft = payload.edits.strip() or report["draft"]
    with db.connect() as conn:
        conn.execute(
            "UPDATE reports SET draft=?,signed_by=?,signed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE incident_id=?",
            (draft, payload.actor, iid),
        )
        conn.execute("UPDATE incidents SET status='closed',closed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                     (iid,))
        conn.execute("INSERT INTO decisions(incident_id,actor,action,detail_json) VALUES(?,?,?,?)",
                     (iid, payload.actor, "sign_report", json.dumps({"clock": report.get("clock")})))
    data = {"signed_by": payload.actor, "report": draft, "clock": report.get("clock")}
    bus.emit("incident.closed", iid, data)
    return {"incident_id": iid, "signed_by": payload.actor, "draft": draft, "clock": report.get("clock")}


@app.post("/api/ops/signals/refresh")
def refresh_signals(_: str = Depends(operator)):
    return pollers.refresh_crowd_signals()


@app.get("/api/signals")
def list_signals(_: str = Depends(operator)):
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM signals ORDER BY scraped_at DESC LIMIT 100")]
    return {"signals": rows, "count": len(rows)}


@app.post("/api/ops/reset")
def reset_calm(_: str = Depends(operator)):
    """Reset practice state for the next judge. Does not touch measured sim.json/eval.json."""
    with db.connect() as conn:
        conn.execute("UPDATE calls SET state='ended',ended_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE state IN ('live','human')")
        conn.execute("UPDATE units SET status='available'")
        conn.execute("UPDATE settings SET overflow_enabled=0,updated_by='reset',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=1")
    return neon.reset_to_calm()


@app.get("/api/events")
async def events(request: Request,since: int=0,authorization: str|None=Header(default=None),_: str=Depends(operator)):
    try: last=max(since,int(request.headers.get("last-event-id",since)))
    except ValueError: last=since
    async def stream():
        nonlocal last
        while True:
            if await request.is_disconnected(): break
            rows=db.events_after(last)
            for ev in rows:
                last=ev["seq"]
                yield f"id: {last}\nevent: {ev['type']}\ndata: {json.dumps(ev)}\n\n"
            if not rows: yield ": ping\n\n"
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

