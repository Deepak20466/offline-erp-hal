"""Dashboard route with stat widgets and quick actions."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.dependencies import require_login
from app.models.user import User
from app.services.dashboard_service import get_dashboard_stats
from app.templating import render

router = APIRouter(tags=["dashboard"])


@router.get("/")
def root():
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(require_login)):
    stats = get_dashboard_stats(db)
    return render(request, "dashboard.html", {"stats": stats}, user=user, active_nav="dashboard")
