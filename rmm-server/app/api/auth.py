"""Auth routes: register admin, login (OAuth2 password flow), current user."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_event
from app.core.deps import get_current_active_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, UserOut, UserRegister

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # First user to register becomes the superadmin.
    count = await db.scalar(select(func.count()).select_from(User))
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_superadmin=(count == 0),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await log_event(db, "admin.registered", actor=user.email, admin_id=user.id)
    return user


@router.post("/login", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    # OAuth2PasswordRequestForm uses "username"; we treat it as email.
    user = await db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")

    user.last_login_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    await log_event(db, "admin.login", actor=user.email, admin_id=user.id)

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_active_user)) -> User:
    return user
