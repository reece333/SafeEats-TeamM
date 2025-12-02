# SafeEats Admin Manual (System Administrator / IT)

## 1. System overview

SafeEats consists of:

- **Backend API** (`backend/app`):
  - FastAPI application (`main.py`, `routes.py`, `auth_routes.py`, `models.py`).
  - Persists data in **Firebase Realtime Database**.
  - Uses **Firebase Auth (Admin SDK)** to manage user accounts.
  - Exposes endpoints for:
    - Auth: `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/user`, admin user management.
    - Restaurants: CRUD for restaurants and menu items.
    - AI helpers: `/ai/parse-ingredients` (JSON), `/ai/ingest-menu` (file upload) backed by Google Generative AI.

- **Frontend web app** (`frontend`):
  - React 18 SPA, served by Create React App / React Scripts.
  - Communicates with backend at `http://localhost:8000` in development and the Render backend in production.
  - Uses localStorage (`auth_token`, `restaurant_id`, etc.) for session state and listens for a global `auth-change` event to update UI.

- **Auth/session model**:
  - Firebase Admin SDK manages actual user records.
  - SafeEats API issues its **own session tokens** (random hex strings stored in an in‑memory `SESSION_TOKENS` map in `auth_routes.py`).
  - Frontend uses `Authorization: Bearer <token>` for all authenticated requests.

---

## 2. Prerequisites

### 2.1 Backend (FastAPI)

- **Python**: 3.10+ (3.11 works; examples assume `python3.10`).
- **Pip / venv**: ability to create a virtual environment.
- **Firebase Project**:
  - Realtime Database enabled.
  - Service account JSON for Firebase Admin SDK (email/password auth enabled for this project).

### 2.2 Frontend (React + Node)

- **Node.js**: 18.x or 20.x (LTS recommended).
- **npm**: 9+.

### 2.3 Dependencies

- Backend (from `backend/requirements.txt`):
  - `fastapi`
  - `uvicorn`
  - `firebase-admin`
  - `pydantic`
  - `python-dotenv`
  - `google-generativeai`

- Frontend:
  - Installed via `npm ci` or `npm install` in `frontend/` (includes `react-scripts`, `@capacitor/*`, MUI, etc.).

---

## 3. Environment variables & configuration

Backend expects a `.env` file in `backend/app` (or equivalent env vars in the deployment environment).

### 3.1 Required variables

- `FIREBASE_CREDENTIALS`
  - **Type**: JSON string
  - **Description**: The full service account credentials for Firebase Admin.
  - **Example** (do not commit):
    - Contents of your service account JSON, stringified into one environment variable.

- `DATABASE_URL`
  - **Type**: string
  - **Description**: Firebase Realtime Database URL (e.g., `https://your-project-id.firebaseio.com`).

- `GOOGLE_AI_API_KEY`
  - **Type**: string
  - **Description**: API key for Google Generative AI (Gemini) used by `/ai/parse-ingredients` and `/ai/ingest-menu`.

### 3.2 Optional variables

- `GEMINI_MODEL`
  - **Type**: string
  - **Description**: Override model name for AI calls (e.g., `gemini-1.5-flash`).
  - If not set, backend will auto‑discover supported models and fall back through a list.

### 3.3 CORS / origins

In `backend/app/main.py`:

- Allowed origins are:
  - `http://localhost:3000` (frontend dev)
  - `http://localhost:8000` (backend dev)
  - `https://restaurant-allergy-manager.onrender.com` (Render deployment)

Adjust `origins` if you host frontend/backend under different domains.

---

## 4. Local deployment steps

### 4.1 Backend API (local)

```bash
cd backend/app

# Optional: create/activate venv
python3.10 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Ensure .env is present with FIREBASE_CREDENTIALS, DATABASE_URL, GOOGLE_AI_API_KEY

# Run backend (dev)
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Verify:

- Open `http://127.0.0.1:8000` → should return a small JSON message.
- Health check endpoints:
  - `/auth/user` requires a valid `Authorization: Bearer <token>`.

### 4.2 Frontend (local)

```bash
cd frontend

# Install dependencies (CI/clean install recommended)
npm ci   # or: npm install

# Start dev server
DISABLE_ESLINT_PLUGIN=true npm start
```

Verify:

- Visit `http://localhost:3000`.
- Frontend uses `http://localhost:8000` as base API URL when `window.location.hostname === 'localhost'`.

---

## 5. Production deployment (high‑level)

This project has been deployed to Render using:

- One service for the backend (FastAPI + Uvicorn).
- One service for the frontend (React static build).

### 5.1 Backend (Render or similar)

1. Create a new **Web Service**:
   - Runtime: Python 3.10+.
   - Root directory: `backend/app`.
   - Start command (example):
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
2. Set environment variables in the provider’s dashboard:
   - `FIREBASE_CREDENTIALS`
   - `DATABASE_URL`
   - `GOOGLE_AI_API_KEY`
   - Optional: `GEMINI_MODEL`
3. Ensure `requirements.txt` is present so dependencies are installed automatically.

### 5.2 Frontend (Render or static host)

1. Build locally or via CI:
   ```bash
   cd frontend
   npm ci
   npm run build
   ```
2. Deploy contents of `frontend/build` to a static host (e.g., Render Static Site, Netlify, Vercel).
3. Configure environment:
   - For this codebase, base API URL is determined in `src/services/api.js`:
     - If hostname is `localhost` → `http://localhost:8000`.
     - Else → `https://restaurant-allergy-manager-backend.onrender.com` (or your backend URL).
   - Update that URL if you deploy the backend somewhere else.

---

## 6. Authentication & reset instructions

### 6.1 How auth works

- Initial registration:
  - `POST /auth/register`:
    - Creates a user in Firebase Auth (email/password).
    - Stores user metadata under `users/{uid}` in Firebase Realtime Database (name, is_admin, created_at).
    - Issues a SafeEats session token and returns it in the JSON response.
  - Frontend saves:
    - `auth_token` (session token)
    - `user_id` (`uid`)
    - `email`, `user_name`, `restaurant_id`, `is_admin` in `localStorage`.

- Login:
  - `POST /auth/login`:
    - Looks up user by email via Firebase Admin.
    - Reads `is_admin` and `name` from `users/{uid}`.
    - Issues a new session token and returns it.

- Authorization:
  - All protected endpoints require `Authorization: Bearer <token>`.
  - `verify_token` in `auth_routes.py` checks the token against the in‑memory `SESSION_TOKENS` map.
  - Admin‑only endpoints additionally use `admin_only` to ensure `is_admin` is `True`.

### 6.2 Resetting sessions / forcing logout

Because `SESSION_TOKENS` is an in‑memory dictionary:

- **Restarting the backend process**:
  - Clears all session tokens (everyone will need to log in again).

- **Manual invalidation**:
  - There is a `/auth/logout` endpoint, but its current implementation expects the token in the header and attempts to read it from `token_data`. Practically, restarting the backend is the most reliable global reset.

### 6.3 Promoting / demoting admins

- From the backend (API level):
  - `POST /auth/make-admin-by-email` (admin only):
    - Body: `{ "email": "user@example.com" }`
    - Marks `is_admin: true` in `users/{uid}` and updates session entries for that email.
  - `POST /auth/remove-admin-by-email` (admin only):
    - Body: `{ "email": "user@example.com" }`
    - Sets `is_admin: false` and updates in‑memory session flags.

- From Firebase Console:
  - You can also change `is_admin` field under `users/{uid}` directly in Realtime Database, but running users won’t see the change until they log in again or their session is refreshed.

### 6.4 Password resets

- SafeEats defers to **Firebase Auth** for email/password handling.
- Use the Firebase console or your own password reset flow (outside this repo) to send password reset emails.
- Once a user changes their password, existing SafeEats tokens remain valid until the in‑memory `SESSION_TOKENS` map is cleared (e.g., server restart).

---

## 7. Basic troubleshooting

- **Backend won’t start / Firebase errors**:
  - Check that `.env` is present in `backend/app` and that:
    - `FIREBASE_CREDENTIALS` contains valid JSON.
    - `DATABASE_URL` matches your Firebase project’s Realtime Database URL.
  - Look at the logs for “Firebase initialization error”.

- **CORS / “Failed to fetch” from frontend**:
  - Ensure backend is actually running on `http://127.0.0.1:8000`.
  - Use `http://localhost:3000` as the frontend URL (to match the existing CORS origin).
  - If you serve frontend from a different domain, add it to `origins` in `main.py`.

- **401 Unauthorized errors unexpectedly**:
  - Check that `auth_token` exists in localStorage.
  - Ensure the frontend is sending `Authorization: Bearer <token>` (handled by `httpRequest` in `api.js`).
  - Restart the backend to clear bad tokens if needed.

- **AI endpoints failing**:
  - Verify `GOOGLE_AI_API_KEY` is set and valid.
  - Check logs for timeout mapping (AI timeouts return HTTP 504 with `{ "error": "upstream_timeout" }`).

For deeper debugging, inspect backend logs (Uvicorn/FastAPI) and frontend console (browser DevTools) when reproducing issues. 


