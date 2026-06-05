"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.models.db import create_tables
from app.routers import forecast, wellbeing, subscribe, demo
from app.models.schemas import HealthResponse
from app.services.weatherai import get_weatherai_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup
    create_tables()
    print("✓ Database tables initialized")
    print(f"✓ WeatherAI client ready")
    
    yield
    
    # Shutdown
    client = get_weatherai_client()
    await client.close()
    print("✓ Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="MoodForecast AI",
        description="Where environmental intelligence meets psychological wellbeing",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(forecast.router)
    app.include_router(wellbeing.router)
    app.include_router(subscribe.router)
    app.include_router(demo.router)
    
    # Health check
    @app.get("/health")
    async def health() -> HealthResponse:
        """Health check endpoint for Railway deploy probe."""
        return HealthResponse(status="ok")
    
    # Static files (frontend)
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
    
    return app


app = create_app()
