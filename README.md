# 🛒 Kharcha Tracker

> A private, self-hosted expense tracker for Indian delivery apps — Zepto, Blinkit, Instamart, BigBasket, JioMart, Swiggy, and Zomato.

A **React + FastAPI** web app and a **Jetpack Compose** Android companion, all sharing a single SQLite database through the FastAPI REST API. Warm amber/orange themed.

## Features

- **Upload screenshots or PDF invoices** from all 7 apps
- **AI parsing with Gemini** — automatically extracts items, prices, brands, quantities using the `google-genai` SDK
- **Rotating API Key Pool** — configure up to 6 Gemini API keys to automatically rotate when a key hits the 20 requests/day free-tier limit
- **Fuzzy Item Normalisation** — auto-detect near-duplicate item name variants (fuzzy similarity threshold 0.72) and resolve category conflicts
- **Database Aliasing** — merge duplicate items and persist canonical mappings in the SQLite DB to clean up your analytics without mutating original invoice data
- **Comprehensive Analytics Dashboard** — KPI widgets, spending-over-time chart, app spend share, category breakdown, 30-day spend heatmap, item frequency/price-range table, and savings insights
- **Review & Edit** before saving — review and modify AI-extracted line items
- **History log** — searchable, filterable log of orders with inline expand and delete
- **Single user, private** — password-protected (bcrypt + JWT), local SQLite database
- **Export** — download your orders and items data as CSV
- **Android app** — same data, mobile companion with share-to-upload from any invoice screenshot

## Quick Start

### 1. Get free Gemini API keys
- Visit [aistudio.google.com](https://aistudio.google.com/app/apikey)
- Create one or more free API keys (Gemini 2.0 Flash)

### 2. Add your API keys
```bash
cp .env.example .env
# Edit .env and paste your keys:
# GEMINI_API_KEY=AIza...
# GEMINI_API_KEY1=AIza...
# GEMINI_API_KEY2=AIza...
# GEMINI_API_KEY3=AIza...
```

### 3. Install web dependencies (first time)
```bash
cd web && npm install
```

### 4. Run the app
```bash
uv run run_all.py
```
This starts both servers:
- **FastAPI API:** http://localhost:8000  (`/api/*`)
- **React Web App:** http://localhost:5173  (proxies `/api` → :8000)

Open http://localhost:5173 in your browser. On first launch you'll create your account (username + password) — a one-time setup.

### Run only the API server
```bash
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

## Android companion app

Build an installable debug APK:
```bash
cd android-app && ./gradlew assembleDebug
```
Output: `app/build/outputs/apk/debug/app-debug.apk`. Install over USB with `adb install -r` or copy to your phone and tap to install. The app authenticates against the same FastAPI server.

## Project Structure

```
├── api_server.py        # FastAPI REST server (Android + Web endpoints)
├── database.py          # SQLite persistence layer (WAL mode, direct SQL)
├── parser.py            # Gemini Vision OCR parser
├── key_pool.py          # Rotating API key pool with daily usage tracking
├── normalizer.py        # Fuzzy clustering and alias mapping logic
├── run_all.py           # Orchestrates FastAPI + Vite dev servers
├── web/                 # React + Vite + Tailwind + Recharts frontend
│   └── src/
│       ├── lib/api.ts   # API client (fetch + JWT)
│       └── pages/       # Dashboard, Apps&Items, Savings, Upload, BulkImport, Cleanup, Settings, Login
├── android-app/         # Jetpack Compose companion app (warm amber theme)
├── data/
│   ├── tracker.db       # SQLite database (auto-created)
│   └── key_usage.json   # Tracks daily API key usages (auto-created)
├── pyproject.toml       # uv project + Python dependencies
└── .env                 # Your secrets (not committed)
```

## Database backup

Your data lives in `data/tracker.db`. Just copy this file to back it up. You can also export CSVs from the web app's **Settings → CSV exporter**.
