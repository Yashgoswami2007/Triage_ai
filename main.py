import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from triage import TriageResponse, get_service


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("triage_ai.api")

triage_service = None


class TriageRequest(BaseModel):
    symptoms: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural-language description of the patient's symptoms.",
        example="severe chest pain radiating to my left arm and I feel like I cannot breathe properly",
    )
    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=40,
        description="Optional language for the response (e.g., Hindi, Tagalog, Bahasa). Defaults to English.",
        example="Hindi",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # For Vercel, we can still load dotenv if local, but service is lazy-loaded.
    load_dotenv(override=False)
    yield


def get_triage_service():
    global triage_service
    if triage_service is None:
        triage_service = get_service()
        logger.info("Triage service initialized model=%s", os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-flash"))
    return triage_service


app = FastAPI(
    title="Triage AI — Smart Medical Query Router Agent",
    description="Single-endpoint HTTP API for symptom severity triage with structured, actionable guidance.",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins_raw = os.environ.get("ALLOWED_ORIGINS", "*").strip()
if allowed_origins_raw == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "Authorization", "x-request-id"],
)


@app.get("/")
async def root():
    return {"message": "Triage AI Backend is running", "status": "ok"}


@app.post("/triage", response_model=TriageResponse)
async def triage(payload: TriageRequest, request: Request) -> TriageResponse:
    req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    logger.info("triage_request id=%s symptoms_len=%d", req_id, len(payload.symptoms))

    service = get_triage_service()
    if service is None:
        logger.error("triage_service is not initialized (request id=%s)", req_id)
        raise HTTPException(status_code=500, detail="Triage service is not initialized.")

    result = service.triage(payload.symptoms, language=payload.language)
    return result
