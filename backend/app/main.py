"""FastAPI application factory."""

import asyncio
import logging
import mimetypes
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from app.config import settings
from app.models.db import create_tables
from app.routers import docs, forecast, wellbeing, activity, locations, subscribe
from app.models.schemas import HealthResponse
from app.services import alerts, mailer
from app.services.rate_limit import RateLimiter
from app.services.weather import get_weather_client


logger = logging.getLogger(__name__)

# Python's own list doesn't have this on every system
mimetypes.add_type("font/woff2", ".woff2")

# The page loads only its own files. /docs and /redoc need more, so they go
# without the content policy.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
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
# The API's requests are a few short fields
MAX_BODY_BYTES = 4096
FORM_PATHS = ("/api/subscribe", "/api/unsubscribe-link")
# How often network and email addresses the limits no longer need are forgotten.
# The privacy page says they are kept for up to a day.
FORGET_INTERVAL_SECONDS = 600
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

# Without this the app's own INFO lines, such as how many alerts went out, are
# dropped. httpx logs every request's address at INFO, which is only noise here.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


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


class LimitApiBodySize:
    """
    Refuse an API request with a body over the limit, however it was sent.
    
    A chunked request declares no length, so the body is read here, stopping at
    the limit, and handed on to the app once it's known to fit.
    """
    
    def __init__(self, app: ASGIApp, limit: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.limit = limit
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        
        length = Headers(scope=scope).get("content-length", "0")
        too_large = not length.isdecimal() or int(length) > self.limit
        messages: list[Message] = []
        size = 0
        more = not too_large
        while more:
            message = await receive()
            messages.append(message)
            size += len(message.get("body", b""))
            too_large = size > self.limit
            more = message.get("more_body", False) and not too_large
        
        if too_large:
            response = JSONResponse({"detail": "That request is too large."}, status_code=413)
            await response(scope, receive, send)
            return
        
        async def replay() -> Message:
            return messages.pop(0) if messages else await receive()
        
        await self.app(scope, replay, send)


async def forget_old_addresses() -> None:
    """Every FORGET_INTERVAL_SECONDS, drop the addresses the limits no longer need, even when nobody is using the site."""
    while True:
        await asyncio.sleep(FORGET_INTERVAL_SECONDS)
        api_limiter.forget_old()
        form_limiter.forget_old()
        alerts.forget_old_addresses()


def warn_if_email_links_are_local() -> None:
    """
    Say so when emails' links would work for nobody: they point to this machine,
    or PUBLIC_URL isn't a full web address (no https://), so mail apps can't open them.
    """
    if not mailer.is_configured():
        return
    url = urlsplit(settings.public_url)
    if url.scheme not in ("http", "https") or not url.hostname:
        logger.warning(
            "PUBLIC_URL is %s, which isn't a full web address: emails' links won't open. "
            "Set it to the site's address, starting with https://",
            settings.public_url
        )
    elif url.hostname in ("localhost", "127.0.0.1"):
        logger.warning(
            "PUBLIC_URL is %s, so the confirmation and unsubscribe links in emails won't work for anyone else",
            settings.public_url
        )


def warn_if_subscribers_would_be_lost() -> None:
    """
    Say so when Railway runs the app on the image's own SQLite file: every
    redeploy starts a new container and deletes it, subscribers and all.
    """
    on_railway = bool(os.environ.get("RAILWAY_PROJECT_ID"))
    volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    url = settings.database_url
    if on_railway and mailer.is_configured() and url.startswith("sqlite") and not (volume and volume in url):
        logger.warning(
            "DATABASE_URL isn't a PostgreSQL database, so subscribers are deleted on every redeploy. "
            "Add PostgreSQL in Railway and set DATABASE_URL to it"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup
    create_tables()
    print("✓ Database tables initialized")
    print("✓ Weather client ready (Open-Meteo)")
    
    warn_if_email_links_are_local()
    warn_if_subscribers_would_be_lost()
    
    forget_task = asyncio.create_task(forget_old_addresses())
    
    # Daily alerts run in the background, in this process
    alert_task = None
    if mailer.is_configured():
        alert_task = asyncio.create_task(alerts.run_alert_loop())
        print(f"✓ Daily alerts scheduled for {settings.alert_hour:02d}:00 local time")
    else:
        print("• Email not configured (MAIL_FROM, and BREVO_API_KEY or SMTP_HOST) - daily alerts are off")
    
    yield
    
    # Shutdown
    forget_task.cancel()
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
        lifespan=lifespan,
        # Served by routers/docs.py instead, with their scripts pinned and checked
        docs_url=None,
        redoc_url=None,
    )
    
    # app.js and styles.css are 40 KB and more, which is slow on a mobile connection
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    
    # CORS: the page is served from this app, so other sites only need to read
    # the public GET endpoints. They can't subscribe, unsubscribe or send cookies.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET"],
    )
    
    app.add_middleware(LimitApiBodySize)
    
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
        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            response.headers["X-Robots-Tag"] = "noindex"
        return response
    
    @app.exception_handler(RequestValidationError)
    async def refuse_invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        """Say what was wrong without echoing the input: what can't be parsed can't be sent back as JSON either."""
        fields = [{key: problem[key] for key in ("type", "loc", "msg")} for problem in error.errors()]
        return JSONResponse({"detail": fields}, status_code=422)
    
    # Include routers
    app.include_router(forecast.router)
    app.include_router(wellbeing.router)
    app.include_router(activity.router)
    app.include_router(locations.router)
    app.include_router(subscribe.router)
    app.include_router(docs.router)
    
    # Health check
    @app.get("/health")
    async def health() -> HealthResponse:
        """Health check endpoint for Railway deploy probe."""
        return HealthResponse(status="ok")
    
    # HEAD too, which uptime monitors often use: otherwise it falls through to the static
    # files' 404. Kept out of the API schema, where it would repeat GET's operation ID.
    app.add_api_route("/health", health, methods=["HEAD"], include_in_schema=False)
    
    # Static files (frontend)
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/", RevalidatedStaticFiles(directory=str(static_path), html=True), name="static")
    
    return app


app = create_app()
