# Kharcha Tracker AI Rules

## Critical Constraints
- **Multi-Platform Sync**: The React web app (`web/`) and the Android companion app (`android-app/`) all share the single SQLite DB (`data/tracker.db`) via the FastAPI server.
- **React Frontend Consumes FastAPI**: The React app (`web/`) talks ONLY to the FastAPI REST API (`api_server.py`) — it never touches SQLite directly.
- **Do Not Break Android App**: Any change to DB queries, API endpoints (`api_server.py`), or schemas (`database.py`) must keep compatibility with `android-app/` code. New endpoints are additive — never modify the contract of existing endpoints.
- **Do Not Break Web Frontend**: The React app (`web/src/lib/api.ts`) depends on the FastAPI endpoints. Changing an endpoint's request/response shape must update `api.ts` too.
- **API Key Rotation**: Preserve the rotating Gemini API Key Pool logic in `key_pool.py`.
- **Warm Amber Theme**: The React web app and the Android app share a warm amber/orange palette (web CSS vars in `web/src/styles/theme.css`; Android colors in `android-app/.../ui/theme/Color.kt`). Keep them visually consistent.

## Build & Run Commands
- **Run everything (API + Web)**: `uv run run_all.py` (FastAPI on :8000 + Vite on :5173)
- **React Web App (primary frontend)**: `cd web && npm run dev` (Vite dev server on :5173, proxies `/api` → FastAPI on :8000)
- **Build Web App**: `cd web && npm run build`
- **FastAPI API Server**: `uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload`
- **Build installable Android APK**: `cd android-app && ./gradlew assembleDebug` (output: `app/build/outputs/apk/debug/app-debug.apk`)
- **Check Android Build**: `cd android-app && ./gradlew compileDebugKotlin`
- **Python Dependencies**: managed via `uv` / `pyproject.toml`

## Architecture Notes
- FastAPI (`api_server.py`) is the single backend for both active clients: React web (`web/`) and Android (`android-app/`).
- The FastAPI server exposes the original Android endpoints plus the extended `/api/stats/*`, `/api/cleanup/*`, `/api/settings/*`, `/api/export/*`, and `/api/auth/register` endpoints used by the React frontend.
- The React app authenticates via JWT (`/api/auth/login` + `/api/auth/register`); the token is stored in `localStorage` under `kharcha_token`.
- Streamlit is no longer the active frontend. Do not add or update Streamlit pages for new product work unless explicitly requested for migration/archival support.
