"""FastAPI main application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config import settings
from .routers import search
from .services.es_client import ESClient
from .services.deepseek_client import DeepSeekClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    yield
    # Shutdown
    ESClient.close()
    await DeepSeekClient.close()

app = FastAPI(
    title="DauThau Search API",
    version="4.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Routes
app.include_router(search.router)

@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.VERSION}

@app.get("/health")
async def health():
    """Health check with ES connection."""
    es = ESClient.get_client()
    es_health = es.ping()
    return {"status": "ok", "elasticsearch": es_health}  # v4.0.5



