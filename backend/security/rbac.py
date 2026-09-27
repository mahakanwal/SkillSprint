"""
security/rbac.py
Role-Based Access Control dependencies for FastAPI routes.

get_current_user reads the "Authorization: Bearer <token>" header (FastAPI's
OAuth2PasswordBearer declares this as a proper security scheme, which is
exactly what the earlier security/permissions.py version was missing -- it
took `token` as a bare function argument with no scheme, so FastAPI never
knew to pull it from the header at all).

require_roles(*roles) builds on top of it: use as a route/router dependency
to restrict access to specific User.role values.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from security.auth import decode_access_token, AuthError

# tokenUrl is just what Swagger's "Authorize" button calls -- doesn't
# affect how tokens are validated.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=True)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(token)
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first() if user_id else None

    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return user


def require_roles(*allowed_roles: str):
    """
    Dependency factory. Use as:
        Depends(require_roles("admin", "training_manager"))
    on a single route, or as `dependencies=[Depends(require_roles(...))]`
    on app.include_router(...) to protect a whole router at once.
    """

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}. "
                       f"Your role is '{current_user.role}'.",
            )
        return current_user

    return checker
