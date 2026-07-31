"""Shared Jinja2Templates instance with custom filters and globals."""
from decimal import Decimal

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from app.config import BASE_DIR
from app.utils.security import generate_csrf_token, generate_document_open_token

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def render(
    request: Request,
    template_name: str,
    context: dict | None = None,
    *,
    user=None,
    active_nav: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render a template with the common context (current_user, active_nav) pre-filled."""
    merged = {"request": request, "current_user": user, "active_nav": active_nav}
    merged.update(context or {})
    return templates.TemplateResponse(template_name, merged, status_code=status_code)


def format_inr(value) -> str:
    """Format a number using Indian digit grouping, e.g. 1234567.5 -> '12,34,567.50'."""
    if value is None:
        return "0.00"
    number = Decimal(str(value))
    negative = number < 0
    number = abs(number)
    rupees, _, paise = f"{number:.2f}".partition(".")

    if len(rupees) <= 3:
        grouped = rupees
    else:
        last_three = rupees[-3:]
        rest = rupees[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last_three

    result = f"{grouped}.{paise}"
    return f"-{result}" if negative else result


def format_date(value, fmt: str = "%d-%b-%Y") -> str:
    if not value:
        return ""
    return value.strftime(fmt)


templates.env.filters["inr"] = format_inr
templates.env.filters["fdate"] = format_date
templates.env.globals["csrf_token"] = generate_csrf_token
templates.env.globals["document_open_token"] = generate_document_open_token
