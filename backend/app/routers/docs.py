"""API docs pages - GET /docs (Swagger UI) and /redoc (ReDoc)"""

from fastapi import APIRouter
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

OPENAPI_URL = "/openapi.json"
TITLE = "MoodForecast AI"
FAVICON = "/favicon.svg"

# Swagger UI and ReDoc come from a CDN, so these pages run without the site's content
# policy. Exact versions, each checked against its hash (from the npm package), so a
# changed or compromised file is refused instead of run on this site. To update, take
# a release at least two weeks old and hash the file from its npm tarball:
#   openssl dgst -sha384 -binary <file> | openssl base64 -A
SWAGGER_JS = (
    "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.34.0/swagger-ui-bundle.js",
    "sha384-9Td7MKiIr2S83E1kZyyVi8KdJw/S8CpAvu0llLyMeg0xq/hDGiZJfVn0fV4llCmK",
)
SWAGGER_CSS = (
    "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.34.0/swagger-ui.css",
    "sha384-4c3vsE5f+trhFyHrFrLM1fFGUn531NIaC7dcqEWIJdoRQJ5CkJbSuSCwXLpaS1KF",
)
REDOC_JS = (
    "https://cdn.jsdelivr.net/npm/redoc@2.5.4/bundles/redoc.standalone.js",
    "sha384-w447zOpYfw/1Tv/5AK9NfHTlQIqE3RVR6KY62jCyy9zNDgO64cMwGGP1Fj0zJVf5",
)


def with_integrity(page: HTMLResponse, *files: tuple[str, str]) -> HTMLResponse:
    """The page with each CDN file's integrity hash added where it is loaded."""
    html = page.body.decode()
    for url, digest in files:
        tagged = f'"{url}" integrity="{digest}" crossorigin="anonymous"'
        if html.count(f'"{url}"') != 1:
            raise RuntimeError(f"Expected {url} once in the docs page")
        html = html.replace(f'"{url}"', tagged)
    return HTMLResponse(html)


@router.get("/docs")
async def swagger_ui() -> HTMLResponse:
    """Interactive API docs."""
    page = get_swagger_ui_html(
        openapi_url=OPENAPI_URL,
        title=f"{TITLE} - Swagger UI",
        swagger_js_url=SWAGGER_JS[0],
        swagger_css_url=SWAGGER_CSS[0],
        swagger_favicon_url=FAVICON,
        # Otherwise Swagger UI sends the API description's address to swagger.io for a badge
        swagger_ui_parameters={"validatorUrl": None},
    )
    return with_integrity(page, SWAGGER_JS, SWAGGER_CSS)


@router.get("/redoc")
async def redoc() -> HTMLResponse:
    """API reference."""
    page = get_redoc_html(
        openapi_url=OPENAPI_URL,
        title=f"{TITLE} - ReDoc",
        redoc_js_url=REDOC_JS[0],
        redoc_favicon_url=FAVICON,
        with_google_fonts=False,
    )
    return with_integrity(page, REDOC_JS)
