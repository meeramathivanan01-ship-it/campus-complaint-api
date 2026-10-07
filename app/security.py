from datetime import datetime, timedelta, timezone
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User


SECRET_KEY = settings.secret_key
logger = logging.getLogger(__name__)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user_id: int, role: str) -> str:
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable must be configured.")

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"user_id": user_id, "role": role, "exp": expires_at}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not SECRET_KEY:
        logger.warning("Authentication failed: credentials unavailable")
        raise authentication_error

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require_exp": True},
        )
    except (JWTError, TypeError, ValueError):
        logger.warning("Authentication failed: invalid bearer token")
        raise authentication_error from None

    user_id = payload.get("user_id")
    if type(user_id) is not int or user_id <= 0:
        logger.warning("Authentication failed: invalid token subject")
        raise authentication_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning("Authentication failed: token subject has no user")
        raise authentication_error
    logger.info("Authentication succeeded (user_id=%s)", user.id)
    return user


def require_roles(*allowed_roles: str):
    """Return a dependency that allows only users with one of the given roles."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "Authorization denied (user_id=%s role=%s)",
                current_user.id,
                current_user.role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return role_checker
