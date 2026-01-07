# 🏋️ SweatMarket (Hackathon Prototype)

SweatMarket is a hackathon mashup project combining **fitness** 🏃 + **finance** 💰.  
Users can find workout partners, check in together *(planned: QR + geolocation)*, and earn in-app coins that can later be used in a reward market / DEX *(prototype)*.

**Repo Goal:** demonstrate an end-to-end FastAPI web app with auth, social features (DM + posts), and a demo-friendly wallet/DEX module.

---

## ✨ Key Features

### 🔐 Authentication + Profile (Cookie Sessions)
- Signup / Login / Logout
- Session-based auth using Starlette `SessionMiddleware`
- Profile setup
  - Nickname, birth date, gender, preferred sport
  - Time window / region / goal
  - Profile photo upload

### 🏠 Home
- Personalized landing page after login
- Quick navigation into profile + chat

### 💬 1:1 Chat (WebSockets)
- Direct messages using Starlette WebSockets
- Start a chat from another user’s profile
- Send
  - Text messages (real-time)
  - Images (upload + broadcast)

### 📸 Community Posts
- Create posts with caption + optional image upload
- Posts list + “New Post” flow

### 💰 Wallet + Market (DEX) — Prototype
- Wallet page shows transactions / coin balance
- DEX page supports
  - Demo mode (seeded mock orders)
  - Real mode (orders stored in DB if available)

---

## 🧰 Tech Stack
- **Backend:** FastAPI (Python 3.12)
- **Database:** SQLite + SQLModel
- **Frontend:** Jinja2 Templates + Tailwind CSS
- **Auth:** Cookie-based sessions + Argon2 password hashing
- **Real-time:** WebSocket (Starlette)
- **Testing:** Pytest + FastAPI TestClient (+ httpx)
- **CI-ready:** Docker test image + GitHub Actions workflow (optional)

---

## 📂 Project Structure
```text
app/
  main.py           # FastAPI app entry (home, posts, wallet, dex)
  auth.py           # signup/login/logout + profile edit flows
  chat.py           # DM routes + websocket handler
  posts.py          # posts list/create routes
  models.py         # SQLModel tables (User, Post, ChatRoom, etc.)
  db.py             # engine + init_db + session dependency
  templates/        # Jinja2 HTML pages

static/
  avatars/          # uploaded profile photos
  post_images/      # uploaded post images
  chat_images/      # uploaded chat images

tests/
  conftest.py
  test_auth.py
  test_posts.py
  test_websocket.py

Dockerfile.test
pytest.ini
requirements.txt
```

### 🚀 Run Locally
1) Install + run
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```
Open:

http://127.0.0.1:8000/

2) DB location
Default (all OS):

```bash
DATABASE_URL=sqlite:///./sweatmarket.db
```
Override (macOS/Linux):

```bash
export DATABASE_URL="sqlite:///./sweatmarket_local.db"
```
Override (Windows PowerShell):

```bash
$env:DATABASE_URL="sqlite:///C:/path/to/sweatmarket_local.db"
```
### ✅ Run Tests (Docker)
Build:

```bash
docker build -f Dockerfile.test -t sweatmarket-test .
```
Run:

```bash
docker run --rm sweatmarket-test
```
### 🧪 What the Tests Cover
Signup/login flow creates a session cookie

Protected route redirects when not authenticated

Posting with caption (+ optional image upload)

WebSocket DM basic connection & messaging

### 🗺️ Roadmap (Planned)
Workout offers + join flow

QR + geolocation check-in verification

Coin earning rules + reward market

Harden auth + permissions for posts/comments

Deployment polish (Render/Heroku)

### 🏁 Hackathon Context
Built as a 12-hour hackathon prototype (CSSS Fall Hacks 2025).
Focus was on demonstrating a realistic product flow + working backend features quickly.
