from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password cannot exceed 72 bytes.")

    return bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        return False

    return bcrypt.checkpw(
        password_bytes,
        password_hash.encode("utf-8")
    )


def create_token(user: User) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRES_MINUTES
    )

    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": expires
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm="HS256"
    )


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
):
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"]
        )

        user_id = int(payload["sub"])
        user = db.get(User, user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail="User is inactive or does not exist"
            )

        return user

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
        
def optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
):
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"]
        )

        user_id = int(payload["sub"])
        user = db.get(User, user_id)

        if not user or not user.is_active:
            return None

        return user

    except Exception:
        return None

def admin_user(user: User = Depends(current_user)):
    if user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return user