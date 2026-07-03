# 🛒 Kharcha Tracker

> A private, self-hosted expense tracker for Indian delivery apps — Zepto, Blinkit, Instamart, BigBasket, JioMart, Swiggy, and Zomato.

## Features

- **Upload screenshots or PDF invoices** from all 7 apps
- **AI parsing with Gemini** — automatically extracts items, prices, brands, quantities using the `google-genai` SDK
- **Rotating API Key Pool** — configure up to 4 Gemini API keys to automatically rotate when a key hits the 20 requests/day free-tier limit
- **Bulk Import Engine** — batch-process a directory of invoices/screenshots with rate-limiting compliance (4 requests/minute sliding window) and automatic key rotation
- **Processed-File Resume** — tracks successfully imported files in `data/processed_files.json` so you never pay API quota twice for the same file when resuming an import
- **Fuzzy Item Normalisation** — auto-detect near-duplicate item name variants (fuzzy similarity threshold 0.72) and resolve category conflicts
- **Database Aliasing** — merge duplicate items and persist canonical mappings in the SQLite DB to clean up your analytics charts without mutating original invoice data
- **Comprehensive Analytics Dashboard** — interactive KPI widgets (Spend, Saved, Orders, Avg Order, Delivery Fees) and 4 analysis tabs:
  - **Spending Overview:** Rolling average timeseries charts, Food vs Groceries share, and a 30-day density heatmap calendar
  - **App-wise Analysis:** Multi-app spending, order count, average order values, and convenience fee costs
  - **Item Intelligence:** Purchase frequency counts, spend category treemaps, search filters, and price range/history charts
  - **Savings & Insights:** Auto-generated tips to consolidate orders, optimize subscriptions, and purchase when price variance is lowest
- **Review & Edit** before saving — review and modify AI-extracted line items
- **History log** — searchable, filterable log of orders with inline edit and delete
- **Single user, private** — password-protected using bcrypt, local SQLite database
- **Export** — download your orders and items data as CSV

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

### 3. Run the app
```bash
uv run streamlit run app.py
```

The app will be available at:
- **Local:** http://localhost:8501
- **Phone/LAN:** http://<your-ip>:8501

### 4. First run
On first launch you'll be prompted to create your account (username + password). This is a one-time setup.

## Running on your phone

Since you're on your home network, open the **Network URL** shown in the terminal on your phone's browser. The app is mobile-friendly and designed for easy screenshot uploads.

## Project Structure

```
├── app.py              # Streamlit entry point & page router
├── database.py         # SQLite persistence layer (WAL mode, direct SQL)
├── parser.py           # Gemini Vision OCR parser
├── key_pool.py         # Rotating API key pool with daily usage tracking
├── normalizer.py       # Fuzzy clustering and alias mapping logic
├── bulk_processor.py   # SDK for folder batch imports and rate limit cooling
├── views/
│   ├── dashboard.py    # 4-tab interactive charts and KPIs dashboard
│   ├── upload.py       # Single-order upload, AI parse, and edit flow
│   ├── bulk.py         # Bulk import UI and live log console
│   ├── history.py      # Order history log with edit/delete
│   ├── cleanup.py      # Duplicate merge, category mapping, and alias list UI
│   └── settings.py     # Multi-key settings, security, and CSV export
├── static/style.css    # Custom dark theme CSS
├── .streamlit/
│   └── config.toml     # Streamlit server config
├── data/
│   ├── tracker.db      # SQLite database (auto-created)
│   ├── key_usage.json  # Tracks daily API key usages (auto-created)
│   ├── processed_files.json # List of successfully bulk-imported stems
│   └── logs/           # Timestamped execution logs for bulk runs (auto-created)
├── pyproject.toml      # uv project + Python dependencies
└── .env                # Your secrets (not committed)
```

## Keeping it private on Streamlit Cloud

If hosting on [streamlit.io/cloud](https://streamlit.io/cloud):
1. Add `GEMINI_API_KEY`, `GEMINI_API_KEY1`, etc., as **Secrets** in the app settings
2. The app has its own password gate — only you can log in

## Database backup

Your data lives in `data/tracker.db`. Just copy this file to back it up.
To export as CSV: go to **Settings → Export Data**.

