"""FastAPI application factory."""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.models.db import create_tables
from app.routers import forecast, wellbeing, activity, locations, subscribe
from app.models.schemas import HealthResponse
from app.services import alerts, mailer
from app.services.rate_limit import RateLimiter
from app.services.weather import get_weather_client


# The page loads only its own files and Google Fonts. /docs and /redoc need
# more, so they go without the content policy.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # Email links carry a subscriber's token, which must not reach other sites
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

# Generous for someone using the page, and low enough to stop one script using
# up the weather services' allowance, or the form emails for everyone else
api_limiter = RateLimiter(300, 60)
form_limiter = RateLimiter(20, 3600)
FORM_PATHS = ("/api/subscribe", "/api/unsubscribe-link")
TOO_MANY_REQUESTS_MESSAGE = "That's a lot of requests in a short time. Please wait a few minutes and try again."


# Paths that carry a subscriber's token, as the access log prints them
TOKEN_IN_PATH = re.compile(r"(/api/(?:confirm|unsubscribe)/|[?&](?:confirm|unsubscribe)=)[^/?&\s]+")


class HideTokens(logging.Filter):
    """Keep subscribers' tokens out of the access log: anyone reading it could unsubscribe them."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                TOKEN_IN_PATH.sub(r"\1[token]", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


logging.getLogger("uvicorn.access").addFilter(HideTokens())


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
        print("• Email not configured (MAIL_FROM, and BREVO_API_KEY or SMTP_HOST) - daily alerts are off")
    
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
    
    # CORS: the page is served from this app, so other sites only need to read
    # the public GET endpoints. They can't subscribe, unsubscribe or send cookies.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET"],
    )
    
    # Added first, so the security headers wrap this response too
    @app.middleware("http")
    async def limit_requests(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            # Railway's proxy says who the visitor is; without one there's the connection
            visitor = request.headers.get("x-real-ip") or (request.client.host if request.client else "")
            limiter = form_limiter if path in FORM_PATHS and request.method == "POST" else api_limiter
            if not limiter.allow(visitor):
                return JSONResponse(
                    {"detail": TOO_MANY_REQUESTS_MESSAGE},
                    status_code=429,
                    headers={"Retry-After": str(int(limiter.window_seconds))}
                )
        return await call_next(request)
    
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if request.url.path not in ("/docs", "/redoc"):
            response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response
    
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
