# Kharcha Tracker AI Rules

## Critical Constraints
- **Multi-Platform Sync**: The React web app (`web/`) and Android companion app (`android-app/`) share the single SQLite DB (`data/tracker.db`) via the FastAPI server.
- **React Frontend Consumes FastAPI**: The React app talks only to FastAPI (`api_server.py`) through `web/src/lib/api.ts`; it never reads SQLite directly.
- **Do Not Break Android App**: Any change to DB queries, API endpoints, or schemas must keep compatibility with `android-app/`. New endpoints are additive — never modify the contract of existing endpoints unless the Android app is updated at the same time.
- **Do Not Break Web Frontend**: Changes to endpoint request/response shapes must be reflected in `web/src/lib/api.ts` and the affected React views.
- **API Key Rotation**: Preserve the rotating Gemini API Key Pool logic in `key_pool.py`.
- **Warm Amber Theme**: Keep the React web CSS variables (`web/src/styles/theme.css`) and Android colors (`android-app/.../ui/theme/Color.kt`) visually consistent.

## Build & Run Commands
- **Run everything (API + Web)**: `uv run run_all.py` (FastAPI on :8000 + Vite on :5173)
- **React Web App**: `cd web && npm run dev` (Vite dev server on :5173, proxies `/api` to FastAPI on :8000)
- **Build Web App**: `cd web && npm run build`
- **FastAPI API Server**: `uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload`
- **Build installable Android APK**: `cd android-app && ./gradlew assembleDebug`
- **Check Android Build**: `cd android-app && ./gradlew compileDebugKotlin`
- **Python Dependencies**: managed via `uv` / `pyproject.toml`

## Architecture Notes
- FastAPI (`api_server.py`) is the single backend for both active clients: React web (`web/`) and Android (`android-app/`).
- The React app authenticates via JWT (`/api/auth/login` + `/api/auth/register`); the token is stored in `localStorage` under `kharcha_token`.
- Streamlit is no longer the active frontend. Do not add or update Streamlit pages for new product work unless explicitly requested for migration/archival support.
