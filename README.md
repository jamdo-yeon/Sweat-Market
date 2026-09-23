# 🏋️ SweatMarket

SweatMarket is a full-stack fitness platform that helps users find workout partners, coordinate group workouts, verify attendance, and earn in-app rewards.

Originally built during **CSSS Fall Hacks 2025**, the project was later expanded into a more complete FastAPI application with real-time workout chat, geolocation-based verification, QR check-ins, automated rewards, and a tested backend.

[Live Demo](https://sweat-market-iota.vercel.app/) · [GitHub Repository](https://github.com/jamdo-yeon/Sweat-Market)

---

## ✨ Features

### 🏃 Workout Offers

- Create workouts with a title, sport, location, date, time, and participant limit
- Search locations using Google Places autocomplete
- Join available workouts
- View workout details and participant status

### 💬 Real-Time Workout Chat

- Each workout has its own group conversation
- Real-time messaging using WebSockets
- Participant names displayed with each message
- Image sharing with JPEG, PNG, WEBP, and GIF validation
- Live conversation previews and timestamps
- Chat access restricted to workout participants

### 📍 Location Verification

- Browser geolocation verifies that participants are near the workout location
- Verification is restricted to the workout time window
- Location verification expires after a limited period
- Nearby-participant checks ensure check-in requirements are met before a QR code is available

### 📱 QR Check-In

- Hosts receive a signed, time-limited QR code once check-in requirements are met
- Participants scan the host's QR code to complete attendance
- Signed tokens prevent QR data from being modified
- Expired, invalid, and workout-mismatched tokens are rejected
- Duplicate check-ins are prevented

### 💰 Rewards

- Successful workout check-ins automatically award coins
- Reward transactions are recorded in the user's wallet history
- Wallet and market pages demonstrate how earned coins can be used

### 🔐 Authentication & Profiles

- Signup, login, and logout
- Cookie-based user sessions
- Argon2 password hashing
- User profiles with fitness preferences and profile photos
- Protected routes and participant-specific permissions

---

## 🧰 Tech Stack

| Area | Technologies |
| --- | --- |
| **Backend** | Python, FastAPI |
| **Database** | SQLModel, SQLite / PostgreSQL |
| **Frontend** | Jinja2, Tailwind CSS, JavaScript |
| **Authentication** | Starlette SessionMiddleware, Argon2 |
| **Real-Time** | WebSockets |
| **Location** | Browser Geolocation API, Google Places API |
| **QR Check-In** | qrcode, itsdangerous signed tokens |
| **Testing** | Pytest, FastAPI TestClient, WebSocket tests |
| **CI / DevOps** | GitHub Actions, Docker |
| **Deployment** | Vercel |

---

## 🧪 Testing

SweatMarket includes **36 automated tests** covering critical backend and integration flows.

Tests include:

- Authentication and protected routes
- Workout creation and participation
- Location and time-window validation
- Nearby-participant verification
- QR generation permissions
- Signed QR token validation
- Expired and invalid QR tokens
- Workout-mismatched QR tokens
- Duplicate check-in protection
- Coin reward transactions
- Workout chat permissions
- WebSocket messaging
- Image-upload validation

Run the test suite locally:

```bash
pytest -q
```

Or run the tests with Docker:

```bash
docker build -f Dockerfile.test -t sweatmarket-test .
docker run --rm sweatmarket-test
```

---

## 🔄 Workout Check-In Flow

```text
Create / Join Workout
        ↓
Arrive Near Workout Location
        ↓
Verify Location
        ↓
Host + Participant Proximity Confirmed
        ↓
Host QR Code Unlocks
        ↓
Participant Scans QR Code
        ↓
Check-In Validated
        ↓
Coins Awarded
```

The check-in system combines location, time, participant status, and signed QR tokens to validate attendance before issuing a reward.

---

## 📂 Project Structure

```text
app/
  main.py           # FastAPI application setup
  auth.py           # authentication and profile flows
  offers.py         # workout creation, joining, and location verification
  chat.py           # workout chat, WebSockets, and image uploads
  qr.py             # signed QR check-in tokens
  models.py         # SQLModel database models
  db.py             # database engine and session dependency
  config.py         # application configuration
  templates/        # Jinja2 pages

static/
  avatars/          # profile photos
  chat_images/      # workout chat images

tests/              # automated backend and integration tests

Dockerfile.test
pytest.ini
requirements.txt
```

---

## 🚀 Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/jamdo-yeon/Sweat-Market.git
cd Sweat-Market
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./sweatmarket.db
GOOGLE_MAPS_API_KEY=your-google-maps-key
```

### 5. Start the application

```bash
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

---

## 🌐 Deployment

SweatMarket is configured for deployment on Vercel.

For a production-style deployment, configure:

```text
SECRET_KEY
DATABASE_URL
GOOGLE_MAPS_API_KEY
```

A hosted PostgreSQL database is recommended for persistent production data. Vercel's local filesystem and SQLite storage are not durable across serverless instances.

Chat image uploads currently use local filesystem storage. A production deployment would move uploaded media to persistent object storage such as Amazon S3 or Cloudinary.

---

## 🏁 Project Background

SweatMarket began as a **12-hour hackathon project at CSSS Fall Hacks 2025**, built around the idea of combining fitness accountability with a reward system.

After the hackathon, the project was expanded with:

- A complete workout creation and participation flow
- Real-time workout group chat
- Image sharing
- Google Places integration
- Geolocation-based attendance verification
- Signed QR check-ins
- Automated coin rewards
- Expanded authentication and authorization checks
- A 36-test automated test suite

The project demonstrates the process of taking an early prototype and developing it into a more complete, tested full-stack application.