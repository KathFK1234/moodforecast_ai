"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.models.db import create_tables
from app.routers import forecast, wellbeing, activity, locations, subscribe
from app.models.schemas import HealthResponse
from app.services import alerts, mailer
from app.services.weather import get_weather_client


class RevalidatedStaticFiles(StaticFiles):
    """
    Static files that browsers must check are current before reusing.
    
    Without a Cache-Control header browsers guess how long to keep each file,
    and can pair a cached app.js with a newer index.html. That breaks the page
    whenever the two change together.
    """
    
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        # "no-cache" still allows caching, but only after asking the server (a cheap 304)
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup
    create_tables()
    print("✓ Database tables initialized")
    print("✓ Weather client ready (Open-Meteo)")
    
    # Daily alerts run in the background, in this process
    alert_task = None
    if mailer.is_configured():
        alert_task = asyncio.create_task(alerts.run_alert_loop())
        print(f"✓ Daily alerts scheduled for {settings.alert_hour:02d}:00 local time")
    else:
        print("• Email not configured (SMTP_HOST, MAIL_FROM) - daily alerts are off")
    
    yield
    
    # Shutdown
    if alert_task:
        alert_task.cancel()
    client = get_weather_client()
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
    app.include_router(activity.router)
    app.include_router(locations.router)
    app.include_router(subscribe.router)
    
    # Health check
    @app.get("/health")
    async def health() -> HealthResponse:
        """Health check endpoint for Railway deploy probe."""
        return HealthResponse(status="ok")
    
    # Static files (frontend)
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/", RevalidatedStaticFiles(directory=str(static_path), html=True), name="static")
    
    return app


app = create_app()
