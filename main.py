"""FastAPI application entrypoint for the Offline ERP HAL system.

Run with: uvicorn main:app --reload
"""
import logging
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from app.config import BASE_DIR, settings
from app.database import init_db
from app.routers import (
    auth,
    clients,
    contracts,
    custom_fields,
    dashboard,
    invoices,
    line_items,
    payments,
    recycle_bin,
    users,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(clients.router)
app.include_router(contracts.router)
app.include_router(line_items.router)
app.include_router(custom_fields.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(recycle_bin.router)
app.include_router(users.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    if settings.secret_key.startswith("hal-erp-offline-secret-key-change-in-production"):
        logger.warning(
            "SECURITY: running with the default SECRET_KEY. Set a unique SECRET_KEY "
            "environment variable before deploying this instance for real use."
        )
    logger.info("Database initialized and application ready.")


@app.exception_handler(HTTPException)
async def redirect_friendly_http_exception(request: Request, exc: HTTPException):
    """Turn bare 303/401/403 HTTPExceptions into the app's normal redirect+toast UX."""
    if exc.status_code == 303 and "Location" in (exc.headers or {}):
        return RedirectResponse(exc.headers["Location"], status_code=303)
    if exc.status_code in (401, 403):
        fallback = "/dashboard" if request.cookies.get(settings.session_cookie_name) else "/login"
        return RedirectResponse(f"{fallback}?error={quote(exc.detail or 'Access denied.')}", status_code=303)
    from fastapi.exception_handlers import http_exception_handler

    return await http_exception_handler(request, exc)
