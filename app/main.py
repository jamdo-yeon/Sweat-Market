# app/main.py — Part A baseline + Part D (Wallet/DEX), demo-friendly, user in nav

from __future__ import annotations

import os
import random
import logging
from contextlib import asynccontextmanager
from typing import Dict, List

# Optional .env loading (safe if python-dotenv is missing)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import Session as SQLSession, select

# ---- Project modules
from .db import init_db, engine
from .auth import router as auth_router
from .posts import router as posts_router
from .chat import router as chat_router
from .uploads import UPLOAD_ROOT
from .models import User, Tx, Order
from .offers import router as offers_router

# ---- Templates / Static
templates = Jinja2Templates(directory="app/templates")

# ---- DEX demo storage
_MOCK_ORDERS: Dict[str, List[Dict[str, int]]] = {"buy": [], "sell": []}


def _seed_mock_orders() -> None:
    if _MOCK_ORDERS["buy"] or _MOCK_ORDERS["sell"]:
        return
    for p in [96, 98, 100, 101, 103]:
        _MOCK_ORDERS["buy"].append({"price": p, "amount": random.randint(5, 20)})
    for p in [104, 106, 108, 110]:
        _MOCK_ORDERS["sell"].append({"price": p, "amount": random.randint(5, 20)})


def _is_demo(request: Request) -> bool:
    return os.getenv("SWEATMARKET_DEMO") == "1" or request.query_params.get("demo") == "1"


# ---- App setup
logging.getLogger("uvicorn").info(f"DATABASE_URL={os.getenv('DATABASE_URL')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_mock_orders()
    yield


app = FastAPI(title="SweatMarket", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret"),
    session_cookie="sweatmarket_session",
    https_only=os.getenv("VERCEL_ENV") == "production",
    same_site="lax",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
if os.getenv("VERCEL"):
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")

# ---- Routers
app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(chat_router)
app.include_router(offers_router)

# =========================================================
#                       Home (Part A)
# =========================================================
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    uid = request.session.get("uid")
    user = None
    if uid:
        with SQLSession(engine) as s:
            user = s.exec(select(User).where(User.id == uid)).first()
    return templates.TemplateResponse(request, "index.html", {"user": user})


@app.get("/health")
def health():
    return {"ok": True}



# =========================================================
#                       Part D: Wallet
# =========================================================
@app.get("/wallet", response_class=HTMLResponse)
def wallet_page(request: Request) -> HTMLResponse:
    uid = request.session.get("uid")

    user_for_nav = None
    if uid:
        with SQLSession(engine) as s:
            user_for_nav = s.get(User, uid)

    if _is_demo(request):
        demo_user = type("U", (), {"coins": 42})()
        txs = [
            {"created_at": "now-1h", "kind": "earn", "amount": 10, "note": "Meetup demo"},
            {"created_at": "now-3h", "kind": "spend", "amount": -3, "note": "Gold Badge"},
            {"created_at": "yesterday", "kind": "bonus", "amount": 5, "note": "Streak"},
        ]
        return templates.TemplateResponse(
            request,
            "wallet.html",
            {"u": demo_user, "txs": txs, "demo": True, "user": user_for_nav},
        )

    if not uid:
        return RedirectResponse("/login", status_code=303)

    with SQLSession(engine) as s:
        u = s.get(User, uid)
        if not u:
            return HTMLResponse("<h2>Wallet</h2><p>User not found.</p>", status_code=404)
        txs = s.exec(select(Tx).where(Tx.user_id == uid).order_by(Tx.id.desc())).all()

    return templates.TemplateResponse(
        request,
        "wallet.html",
        {"u": u, "txs": txs, "demo": False, "user": u},
    )


# =========================================================
#                       Part D: DEX
# =========================================================
@app.get("/dex", response_class=HTMLResponse)
def dex_page(request: Request) -> HTMLResponse:
    uid = request.session.get("uid")
    user_for_nav = None
    if uid:
        with SQLSession(engine) as s:
            user_for_nav = s.get(User, uid)

    if _is_demo(request):
        buys = sorted(_MOCK_ORDERS["buy"], key=lambda o: o["price"], reverse=True)
        sells = sorted(_MOCK_ORDERS["sell"], key=lambda o: o["price"])
        return templates.TemplateResponse(
            request,
            "dex.html",
            {"buys": buys, "sells": sells, "demo": True, "user": user_for_nav},
        )

    try:
        with SQLSession(engine) as s:
            buys = s.exec(select(Order).where(Order.side == "buy").order_by(Order.price.desc())).all()
            sells = s.exec(select(Order).where(Order.side == "sell").order_by(Order.price.asc())).all()
    except Exception as e:
        buys = sorted(_MOCK_ORDERS["buy"], key=lambda o: o["price"], reverse=True)
        sells = sorted(_MOCK_ORDERS["sell"], key=lambda o: o["price"])
        return templates.TemplateResponse(
            request,
            "dex.html",
            {"buys": buys, "sells": sells, "demo": True, "user": user_for_nav, "error": str(e)},
        )

    return templates.TemplateResponse(
        request,
        "dex.html",
        {"buys": buys, "sells": sells, "demo": False, "user": user_for_nav},
    )


@app.post("/dex/new")
def dex_new(
    request: Request, side: str = Form(...), price: int = Form(...), amount: int = Form(...)
) -> RedirectResponse:
    if _is_demo(request):
        if side not in ("buy", "sell"):
            side = "buy"
        _MOCK_ORDERS[side].append({"price": int(price), "amount": int(amount)})
        return RedirectResponse("/dex?demo=1", status_code=303)

    uid = request.session.get("uid")
    if not uid:
        return RedirectResponse("/login", status_code=303)

    with SQLSession(engine) as s:
        s.add(Order(user_id=uid, side=side, price=price, amount=amount))
        s.commit()
    return RedirectResponse("/dex", status_code=303)
