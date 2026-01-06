# app/posts.py

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .db import engine
from .models import User, Post, Comment
from .auth import current_user  # chat.py에서도 쓰는 거라 너 프로젝트에 이미 있을 확률 높음

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

POST_IMG_DIR = Path("static/post_images")
POST_IMG_DIR.mkdir(parents=True, exist_ok=True)


def get_session():
    # 프로젝트에 이미 get_session이 있으면 그걸 쓰는 게 더 깔끔하지만,
    # 없을 수도 있으니 안전하게 여기서도 제공
    with Session(engine) as s:
        yield s


def _save_upload(image: UploadFile) -> str:
    ext = Path(image.filename or "").suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        ext = ".png"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = POST_IMG_DIR / fname
    with dest.open("wb") as f:
        f.write(image.file.read())
    return f"/static/post_images/{fname}"


@router.get("/posts", response_class=HTMLResponse)
def posts_list(request: Request, session: Session = Depends(get_session)):
    uid = request.session.get("uid")
    user = session.get(User, uid) if uid else None

    posts = session.exec(select(Post).order_by(Post.created_at.desc())).all()
    authors = {p.author_id: session.get(User, p.author_id) for p in posts}

    return templates.TemplateResponse(
        "posts_list.html",
        {"request": request, "user": user, "posts": posts, "authors": authors},
    )


@router.get("/posts/new", response_class=HTMLResponse)
def posts_new_page(request: Request, session: Session = Depends(get_session)):
    me = current_user(request, session)
    if not me:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        "posts_new.html",
        {"request": request, "user": me},
    )


@router.post("/posts/new")
def posts_create_new(
    request: Request,
    caption: str = Form(...),
    image: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
):
    me = current_user(request, session)
    if not me:
        return RedirectResponse("/login", status_code=303)

    image_url = _save_upload(image) if image else None
    post = Post(author_id=me.id, caption=(caption or "").strip(), image_url=image_url)
    session.add(post)
    session.commit()
    session.refresh(post)

    return RedirectResponse(f"/posts/{post.id}", status_code=303)


# ✅ 테스트 호환용: tests가 POST /posts 로 쏘고 있어서 alias 제공
@router.post("/posts")
def posts_create_alias(
    request: Request,
    caption: str = Form(...),
    image: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
):
    return posts_create_new(request, caption, image, session)


@router.get("/posts/{post_id}", response_class=HTMLResponse)
def posts_detail(post_id: int, request: Request, session: Session = Depends(get_session)):
    uid = request.session.get("uid")
    user = session.get(User, uid) if uid else None

    post = session.get(Post, post_id)
    if not post:
        return HTMLResponse("Post not found", status_code=404)

    author = session.get(User, post.author_id)
    comments = session.exec(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at)
    ).all()
    comment_authors = {c.author_id: session.get(User, c.author_id) for c in comments}

    return templates.TemplateResponse(
        "posts_detail.html",
        {
            "request": request,
            "user": user,
            "post": post,
            "author": author,
            "comments": comments,
            "comment_authors": comment_authors,
        },
    )


@router.post("/posts/{post_id}/comment")
def posts_add_comment(
    post_id: int,
    request: Request,
    content: str = Form(...),
    session: Session = Depends(get_session),
):
    me = current_user(request, session)
    if not me:
        return RedirectResponse("/login", status_code=303)

    post = session.get(Post, post_id)
    if not post:
        return HTMLResponse("Post not found", status_code=404)

    c = Comment(post_id=post_id, author_id=me.id, content=(content or "").strip())
    session.add(c)
    session.commit()

    return RedirectResponse(f"/posts/{post_id}#comments", status_code=303)
