"""FastAPI dependencies shared across routers."""

from app.db.session import get_db
from app.security.auth import get_current_user

__all__ = ["get_db", "get_current_user"]
