# Kharcha Tracker (Baskit) AI Rules

## Critical Constraints
- **Multi-Platform Sync**: The React web app (`web/`) and Android companion app (`android-app/`) share the single SQLite DB (`data/tracker.db`) via the FastAPI server.
- **React Frontend Consumes FastAPI**: The React app talks only to FastAPI (`api_server.py`) through `web/src/lib/api.ts`; it never reads SQLite directly.
- **Do Not Break Android App**: Any change to DB queries, API endpoints, or schemas must maintain backward compatibility with `android-app/`. New endpoints are additive.
- **API Key Rotation**: Preserve the rotating Gemini API Key Pool logic in `key_pool.py`.
- **Warm Amber Theme**: Keep the React web CSS variables (`web/src/styles/theme.css`) and Android colors (`android-app/.../ui/theme/Color.kt`) visually consistent.

## Build & Run Commands
- **Run everything (API + Web)**: `uv run run_all.py` (FastAPI on :8000 + Vite on :5173)
- **React Web App**: `cd web && npm run dev`
- **FastAPI API Server**: `uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload`
- **Check Android Build**: `cd android-app && ./gradlew compileDebugKotlin`
- **Python Dependencies**: managed via `uv` / `pyproject.toml`

