import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from google.oauth2 import id_token
from google.auth.transport import requests

from app.database import get_db
from app.models import User
from app.schemas import RegisterIn, LoginIn, Token, UserOut
from app.security import (
    hash_password,
    verify_password,
    create_token,
    current_user,
)
from app.config import settings


router = APIRouter()


# =======================================================
# NORMAL REGISTER
# =======================================================

@router.post("/register", response_model=Token)
def register(
    d: RegisterIn,
    db: Session = Depends(get_db)
):
    existing_user = db.scalar(
        select(User).where(User.email == d.email)
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    u = User(
        email=d.email,
        display_name=d.display_name,
        password_hash=hash_password(d.password)
    )

    db.add(u)
    db.commit()
    db.refresh(u)

    return Token(
        access_token=create_token(u)
    )


# =======================================================
# NORMAL LOGIN
# =======================================================

@router.post("/login", response_model=Token)
def login(
    d: LoginIn,
    db: Session = Depends(get_db)
):
    u = db.scalar(
        select(User).where(User.email == d.email)
    )

    if not u or not verify_password(
        d.password,
        u.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not u.is_active:
        raise HTTPException(
            status_code=401,
            detail="User is inactive"
        )

    return Token(
        access_token=create_token(u)
    )


# =======================================================
# GOOGLE LOGIN
# =======================================================

@router.post("/google", response_model=Token)
def google_login(
    data: dict,
    db: Session = Depends(get_db)
):
    google_token = data.get("credential")

    if not google_token:
        raise HTTPException(
            status_code=400,
            detail="Google credential is required"
        )

    # ---------------------------------------------------
    # VERIFY GOOGLE TOKEN
    # ---------------------------------------------------

    try:
        google_user = id_token.verify_oauth2_token(
            google_token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google credential"
        )

    # ---------------------------------------------------
    # GET GOOGLE USER INFORMATION
    # ---------------------------------------------------

    email = google_user.get("email")
    email_verified = google_user.get(
        "email_verified",
        False
    )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Google account email not available"
        )

    if not email_verified:
        raise HTTPException(
            status_code=401,
            detail="Google email is not verified"
        )

    display_name = (
        google_user.get("name")
        or google_user.get("given_name")
        or email.split("@")[0]
    )

    # ---------------------------------------------------
    # CHECK IF USER ALREADY EXISTS
    # ---------------------------------------------------

    user = db.scalar(
        select(User).where(User.email == email)
    )

    # ---------------------------------------------------
    # FIRST GOOGLE LOGIN
    # ---------------------------------------------------

    if not user:

        random_password = secrets.token_urlsafe(32)

        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(
                random_password
            ),
            role="READER",
            is_active=True
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    # ---------------------------------------------------
    # EXISTING USER
    # ---------------------------------------------------

    else:

        if not user.is_active:
            raise HTTPException(
                status_code=401,
                detail="User is inactive"
            )

        # Update the display name using the
        # Google account's name.
        #
        # IMPORTANT:
        # We DO NOT change the user's role.
        # Therefore an existing ADMIN remains ADMIN.
        user.display_name = display_name

        db.commit()
        db.refresh(user)

    # ---------------------------------------------------
    # CREATE OUR APPLICATION JWT
    # ---------------------------------------------------

    return Token(
        access_token=create_token(user)
    )


# =======================================================
# CURRENT USER
# =======================================================

@router.get("/me", response_model=UserOut)
def me(
    u=Depends(current_user)
):
    return u