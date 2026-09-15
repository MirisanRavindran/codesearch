from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.config import settings
from backend.metrics import SEARCH_ERRORS, SEARCH_LATENCY, SEARCH_REQUESTS
from backend.models import SearchRequest, SearchResponse
from backend.search import SearchService

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("codesearch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model + FAISS index once at boot, close cleanly on shutdown."""
    log.info("loading search service (this may take 5-10s)…")
    app.state.svc = SearchService()
    log.info("ready. index has %d chunks", app.state.svc.index.index.ntotal)
    yield
    log.info("shutting down")


app = FastAPI(
    title="CodeSearch",
    description="Semantic code search over open-source Python.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow the frontend to hit the API. In production, restrict origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to your deployed frontend URL
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, request: Request):
    with SEARCH_LATENCY.time():
        try:
            svc: SearchService = request.app.state.svc
            resp = svc.search(req.query, req.top_k)
            SEARCH_REQUESTS.labels(status="ok").inc()
            log.info(
                'query=%r top_k=%d hits=%d latency=%.1fms',
                req.query, req.top_k, len(resp.hits), resp.latency_ms,
            )
            return resp
        except Exception as e:
            SEARCH_REQUESTS.labels(status="error").inc()
            SEARCH_ERRORS.labels(kind="internal").inc()
            log.exception("search failed")
            raise HTTPException(status_code=500, detail=str(e))
