# app/auth.py
from __future__ import annotations

import os
import re
import logging
from datetime import datetime, date, timezone

from fastapi import APIRouter, Depends, Request, Form, status, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlmodel import select, Session
from sqlalchemy.exc import IntegrityError

from .db import get_session
from .models import User

log = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

pwd = CryptContext(schemes=["argon2"], deprecated="auto")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,20}$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d).{6,}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(email: str) -> bool:
    """Validate email using Pydantic v2 if available; otherwise fallback regex."""
    email = (email or "").strip()
    if not email:
        return True

    try:
        from pydantic import EmailStr, TypeAdapter  # type: ignore

        TypeAdapter(EmailStr).validate_python(email)
        return True
    except Exception:
        return EMAIL_RE.fullmatch(email) is not None


def current_user(request: Request, session: Session) -> User | None:
    uid = request.session.get("uid")
    if not uid:
        return None
    return session.get(User, uid)


# ---------- Signup ----------
@router.get("/signup")
def signup_form(request: Request):
    return templates.TemplateResponse(request, "signup.html", {})


@router.post("/signup")
def signup(
    request: Request,
    username: str = Form(...),
    email: str | None = Form(None),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    username = (username or "").strip()
    email = (email or "").strip() or None
    password = password or ""

    if not USERNAME_RE.fullmatch(username):
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Username must be 5–20 chars (A–Z, a–z, 0–9, underscore)."},
            status_code=400,
        )

    if not PASSWORD_RE.fullmatch(password):
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Password must be ≥6 chars, include ≥1 uppercase & ≥1 digit."},
            status_code=400,
        )

    if email and not _valid_email(email):
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Invalid email format."},
            status_code=400,
        )

    exists = session.exec(select(User).where(User.username == username)).first()
    if exists:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Username already exists."},
            status_code=400,
        )

    if email:
        exists_email = session.exec(select(User).where(User.email == email)).first()
        if exists_email:
            return templates.TemplateResponse(
                request,
                "signup.html",
                {"error": "Email already exists."},
                status_code=400,
            )

    try:
        pw_hash = pwd.hash(password)
    except Exception:
        log.exception("Password hashing failed")
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Password hashing failed. Try a different password."},
            status_code=400,
        )

    user = User(
        username=username,
        email=email,
        password_hash=pw_hash,
        is_active=True,
        email_confirmed_at=datetime.now(timezone.utc),
    )
    try:
        session.add(user)
        session.commit()
        session.refresh(user)
    except IntegrityError:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Username already exists (race condition)."},
            status_code=400,
        )
    except Exception:
        session.rollback()
        log.exception("DB error during signup")
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": "Unexpected server error while creating the account."},
            status_code=500,
        )

    request.session["uid"] = int(user.id)
    return RedirectResponse(url="/profile/edit", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Login / Logout ----------
@router.get("/login")
def login_form(request: Request, msg: str | None = None):
    return templates.TemplateResponse(request, "login.html", {"error": msg})


@router.post("/login")
def login(
    request: Request,
    username: str | None = Form(None),
    email: str | None = Form(None),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    password = password or ""
    username = (username or "").strip()
    email = (email or "").strip()

    user = None
    if username:
        user = session.exec(select(User).where(User.username == username)).first()
    elif email:
        user = session.exec(select(User).where(User.email == email)).first()

    if not user or not pwd.verify(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username/email or password."},
            status_code=401,
        )

    request.session["uid"] = int(user.id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout_post(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout_get(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Profile guard ----------
@router.get("/profile")
def profile_redirect(request: Request, session: Session = Depends(get_session)):
    me = current_user(request, session)
    if not me:
        return RedirectResponse("/login", status_code=302)
    return RedirectResponse("/profile/edit", status_code=302)


@router.get("/profile/edit")
def profile_edit(request: Request, session: Session = Depends(get_session)):
    user = current_user(request, session)
    if not user:
        return RedirectResponse("/login?msg=Please+log+in+first", status_code=303)
    saved = request.query_params.get("saved")
    return templates.TemplateResponse(request, "profile_edit.html", {"user": user, "saved": saved})


@router.post("/profile/edit")
def profile_update(
    request: Request,
    nickname: str = Form(...),
    birth_year: str = Form(...),
    birth_month: str = Form(...),
    birth_day: str = Form(...),
    gender: str = Form(...),
    sport: str = Form(...),
    time_window: str | None = Form(None),
    region: str | None = Form(None),
    goal: str | None = Form(None),
    avatar: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    user = current_user(request, session)
    if not user:
        return RedirectResponse("/login?msg=Please+log+in+first", status_code=303)

    nick = (nickname or "").strip()
    if not (3 <= len(nick) <= 12):
        return templates.TemplateResponse(
            request,
            "profile_edit.html",
            {"user": user, "error": "Nickname must be 3–12 characters."},
            status_code=400,
        )

    try:
        y, m, d = int(birth_year), int(birth_month), int(birth_day)
        bdate = date(y, m, d)
    except Exception:
        return templates.TemplateResponse(
            request,
            "profile_edit.html",
            {"user": user, "error": "Invalid birth date."},
            status_code=400,
        )

    if gender not in ("male", "female", "prefer_not_to_answer"):
        return templates.TemplateResponse(
            request,
            "profile_edit.html",
            {"user": user, "error": "Invalid gender."},
            status_code=400,
        )

    if sport not in ("gym", "soccer", "running", "others"):
        return templates.TemplateResponse(
            request,
            "profile_edit.html",
            {"user": user, "error": "Invalid sport."},
            status_code=400,
        )

    if avatar and avatar.filename:
        os.makedirs("static/avatars", exist_ok=True)
        ext = os.path.splitext(avatar.filename)[1].lower() or ".jpg"
        path = f"static/avatars/{user.id}{ext}"
        with open(path, "wb") as f:
            f.write(avatar.file.read())
        user.avatar_url = "/" + path

    user.nickname = nick
    user.birth_date = bdate
    user.gender = gender
    user.sport = sport
    user.time_window = time_window
    user.region = region
    user.goal = goal

    session.add(user)
    session.commit()

    return RedirectResponse("/profile/edit?saved=1", status_code=303)
