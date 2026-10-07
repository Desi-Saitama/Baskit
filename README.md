# 🧺 Baskit (Kharcha Tracker)

<div align="center">

**Intelligent, private, self-hosted expense tracker and receipt parser for Indian delivery apps.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite)](https://vitejs.dev)
[![Android](https://img.shields.io/badge/Android-Jetpack%20Compose-3DDC84?style=flat-square&logo=android)](https://developer.android.com/jetpack/compose)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://python.org)
[![Gemini](https://img.shields.io/badge/Gemini-Vision%20OCR-8E75B2?style=flat-square&logo=google)](https://aistudio.google.com)

**Supported Quick-Commerce & Delivery Apps:**  
⚡ **Zepto** • 🟡 **Blinkit** • 🟢 **Swiggy Instamart** • 🥬 **BigBasket** • 🔵 **JioMart** • 🍔 **Swiggy Food** • 🔴 **Zomato**

</div>

---

## 📖 Overview

Quick-commerce makes everyday ordering effortless, but tracking cumulative grocery and food spending across multiple apps is chaotic. Receipts are scattered across emails and in-app order histories with noisy, inconsistent naming (e.g. *"Amul Taaza Milk 500ml"* vs *"Amul Milk Pouch 500 ml"*).

**Baskit** gives you complete visibility over your quick-commerce expenses with **zero manual data entry** and **100% data privacy**:

1. **Snap or export receipts**: Upload screenshots or PDF invoices from any supported app.
2. **AI-powered Vision OCR**: Google Gemini Vision parses and structures order metadata, item names, brands, categories, prices, discounts, and delivery fees.
3. **Fuzzy Normalization**: Intelligent string clustering automatically groups noisy item name variants under canonical names without modifying raw receipt history.
4. **Interactive Analytics**: Web dashboard and native Android app visualizing monthly burn, platform spend share, delivery fee leakage, and price histories.
5. **Self-Hosted & Private**: Runs locally on your machine with SQLite. Your financial data stays exclusively on your hardware.

---

## ✨ Features

- **📸 Multi-App Receipt Parser**: Native support for screenshots and PDF invoices from Zepto, Blinkit, Instamart, BigBasket, JioMart, Swiggy, and Zomato.
- **🔄 Rotating Gemini API Key Pool**: Operates 100% on the Google AI Studio free tier. Configure up to 6 free keys; Baskit monitors daily usage (20 req/day per key) and rotates keys automatically to bypass rate limits.
- **🪄 Fuzzy Item Clustering & Aliasing**: Auto-detects near-duplicate line items using string similarity (threshold $\ge 0.72$). Merge variations into a single canonical item, brand, and category with one click.
- **📊 Comprehensive Analytics Dashboard**:
  - Key financial metrics (Total Spend, Total Saved, Net Delivery Fees, Average Order Value).
  - Spend over time with interactive daily/weekly trends.
  - App spend distribution & category breakdowns.
  - 30-day activity spend heatmap.
  - Frequent items directory with unit price ranges and purchase cadence.
- **📱 Native Android Companion**: Built with Kotlin and Jetpack Compose featuring a matching warm-amber design system and an Android Share Target (share invoice screenshots directly into Baskit).
- **📁 Bulk Import**: Point Baskit to any folder containing past receipts. Features crash-resilient resume checkpoints and duplicate receipt prevention.
- **🔒 Password-Protected & Private**: Single-user bcrypt authentication and JWT tokens. Everything is persisted in a local SQLite database (WAL mode).
- **💾 CSV Export**: Export clean `orders.csv` and `items.csv` anytime for external analysis or backups.

---

## 🏗️ Architecture

```
┌────────────────────────┐      ┌────────────────────────┐
│  React Web App (Vite)  │      │  Android Companion App │
│  http://localhost:5173 │      │   (Jetpack Compose)    │
└───────────┬────────────┘      └───────────┬────────────┘
            │                               │
            └───────────────┬───────────────┘
                            ▼
              ┌───────────────────────────┐
              │   FastAPI REST API Server │
              │   http://localhost:8000   │
              └─────────────┬─────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
  ┌───────────────────┐           ┌───────────────────┐
  │   Local SQLite    │           │ Gemini Key Pool   │
  │ (data/tracker.db) │           │ (Vision OCR API)  │
  └───────────────────┘           └───────────────────┘
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.11+** (managed via [`uv`](https://github.com/astral-sh/uv) or standard `pip`)
- **Node.js 18+** & `npm`
- One or more free Google Gemini API keys from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 2. Clone the Repository
```bash
git clone git@github.com:Desi-Saitama/Baskit.git
cd Baskit
```

### 3. Configure Environment Variables
Copy the template and add your Gemini API key(s):
```bash
cp .env.example .env
```
Open `.env` in your editor:
```env
# Free keys from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=AIzaSy...
GEMINI_API_KEY1=AIzaSy...   # Optional extra keys for rotation
GEMINI_API_KEY2=AIzaSy...   # Optional
```

### 4. Install Dependencies

#### Backend (`uv` recommended):
```bash
# Install uv if you don't have it:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python dependencies:
uv sync
```
*(Or with pip: `pip install -e .`)*

#### Frontend:
```bash
cd web
npm install
cd ..
```

### 5. Launch the Application

Run both the FastAPI backend and Vite frontend with a single command:
```bash
uv run run_all.py
```

This starts:
- 🌐 **Web Frontend**: [http://localhost:5173](http://localhost:5173)
- ⚙️ **Backend API**: [http://localhost:8000](http://localhost:8000)
- 📚 **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

*On your first visit to http://localhost:5173, you will be prompted to create your admin account (username and password).*

---

## 📱 Android Companion App

The Android app communicates with the same FastAPI server, allowing you to upload screenshots on the go or view your spending metrics.

### Building the APK
```bash
cd android-app
./gradlew assembleDebug
```
The output APK is located at:
```
android-app/app/build/outputs/apk/debug/app-debug.apk
```

### Installing on Device
1. Enable **USB Debugging** on your Android device.
2. Run:
   ```bash
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   ```
3. In the Android app Settings, enter your backend server URL (e.g., `http://192.168.1.X:8000` for your local network, or `http://10.0.2.2:8000` when running inside the Android Emulator).

---

## 📂 Project Structure

```
.
├── api_server.py            # FastAPI REST backend (auth, orders, stats, cleanup, settings)
├── database.py              # SQLite persistence layer (WAL mode, parameterized SQL)
├── parser.py                # Gemini Vision OCR parser & receipt extraction logic
├── key_pool.py              # Rotating Gemini API key pool manager with daily quota tracking
├── normalizer.py            # Fuzzy item clustering and canonical alias mappings
├── run_all.py               # Process manager launching FastAPI + Vite concurrently
├── pyproject.toml           # Python dependencies and project configuration
├── .env.example             # Template for API keys
│
├── web/                     # React + Vite frontend
│   ├── src/
│   │   ├── components/      # UI cards, header, sidebar, charts
│   │   ├── lib/api.ts       # Typed API client with JWT bearer auth
│   │   ├── pages/           # Dashboard, Upload, BulkImport, AppsItems, History, Cleanup, Settings
│   │   └── styles/          # Tailwind CSS & warm amber design tokens
│   ├── package.json
│   └── vite.config.ts
│
├── android-app/             # Native Android companion app
│   ├── app/src/main/
│   │   ├── java/com/kharchatracker/
│   │   │   ├── data/        # Retrofit API client, models & offline cache
│   │   │   └── ui/          # Jetpack Compose screens & navigation
│   │   └── res/             # Launcher icons & resources
│   └── build.gradle.kts
│
└── data/                    # Local storage (git-ignored)
    ├── tracker.db           # SQLite database (auto-created on startup)
    └── key_usage.json       # Daily API key quota tracker (auto-created)
```

---

## 🛡️ Security & Privacy Notice

- **No Remote Telemetry**: Baskit does not send your receipt contents or expense data to any third-party server besides Google Gemini Vision for OCR parsing.
- **Zero Committed Secrets**: `.env`, databases (`*.db`), cached logs, and uploaded receipts are explicitly ignored via `.gitignore`.
- **Local Authentication**: User passwords are encrypted with bcrypt before being stored in SQLite. Sessions are protected via signed JWT tokens.

---

## 🗄️ Backup & Data Management

Your entire expense history is stored in a single SQLite database file:
```
data/tracker.db
```
To back up your data, simply copy this file or download a CSV export from **Settings → CSV Exporter** in the web dashboard.

---

## ⚖️ Disclaimer

Baskit is an independent, open-source personal finance tool. It is not affiliated with, endorsed by, or associated with Zepto, Blinkit, Swiggy, Zomato, BigBasket, JioMart, or Google. All trademarks, service marks, and company names are the property of their respective owners.
