# Kharcha Tracker AI Rules

## Critical Constraints
- **Multi-Platform Sync**: The Streamlit webapp and Android companion app share the SQLite DB (`data/tracker.db`).
- **Do Not Break Android App**: Any change to DB queries, API endpoints (`api_server.py`), or schemas (`database.py`) must keep compatibility with `android-app/` code.
- **Do Not Break Streamlit Webapp**: Validate changes to pages in `views/` and the main `app.py`.
- **API Key Rotation**: Preserve the rotating Gemini API Key Pool logic in `key_pool.py`.

## Build & Run Commands
- **Streamlit Webapp**: `uv run streamlit run app.py`
- **FastAPI API Server**: `uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload`
- **Check Android Build**: `cd android-app && ./gradlew compileDebugKotlin`
- **Python Dependencies**: managed via `uv` / `pyproject.toml`
