# Prediction Plan: Next-Month Spend + Shopping List

## 0. Data reality (measured 2026-10-04)
- `data/tracker.db`: **89 orders, 306 items, ~231 distinct raw names** over only **May–Jul 2026** (49 / 22 / 18 orders per month).
- Item names are noisy (`normalizer.py` already handles this via `item_aliases` + fuzzy clustering) — any predictor **must** call `apply_normalization(get_items_df())` first, never raw names.
- Top repeaters: `banana robusta (8x)`, `cucumber, carrot (6x)`, paneer/lemon/tomato/bread (3–5x). Long tail: most items bought 1–2x.
- Stack: `pandas+numpy` present, `sklearn` **not** installed; web app is React + `web/src/lib/api.ts`; backend is `api_server.py` (single backend for web + Android — new endpoints must be **additive only**).

> Caveat on "full forecasting lib" choice: with 2.5 months of history, Prophet/LightGBM **cannot learn seasonality** and will overfit. They are Phase-3 plug-ins below; Phase-1/2 is what gives useful numbers on day one.

Decisions locked: scope = Both spend + items; complexity = Full forecasting lib (phased); UI = New Predictions page.

## 1. Problem split (two heads, one pipeline)
- **Head A — spend regression**: predict `next_month_total` (INR) + confidence interval + category split.
- **Head B — basket classification**: for each normalized item, predict `P(buy next month)` + expected qty + expected price → ranked shopping list.
- Shared feature builder feeds both heads.

## 2. Features to build (new `predictor.py`, pure functions for testability)
From `get_orders_df()` + normalized `get_items_df()`:
- **Monthly series**: `total_spend, order_count, avg_order, discount, fees` per `YYYY-MM` (reuse `_shift_month` logic).
- **Per-item**: `times_bought, distinct_months, days_since_last, avg_inter_purchase_interval, avg/min/max unit_price, price_trend slope, avg_monthly_qty, category, app affinity`.
- **Calendar**: month index, `is_festival_month` flag later; for now just `month_of_year` (matters once >12 mo).
- Anti-leakage rule: features for month `M` use only data `< M`.

## 3. Core ask: soft frequency weighting (learned, not hard rules)
No `times >= 3` thresholds anywhere. Instead:
1. **Recency-decayed frequency** as a *feature*, not a filter:
   `score = sum(0.85^(months_ago))` per purchase — frequent+recent scores high, one-off-old decays toward 0 automatically.
2. **Bayesian smoothing** for repurchase rate: `P = (buys + alpha) / (months_active + alpha + beta)` with e.g. `alpha=2, beta=4`. A 1x-in-3-months item gets ~0.2, an 8x staple gets ~0.8 — occasional items are down-weighted but never zeroed, and can resurface if recency spikes.
3. **Learned weights**: `LogisticRegression` (Head B) / `Ridge` (Head A) learn coefficients for `frequency, recency, interval_regularity, price_stability` from data. Behavior changes adapt without code changes.
4. **Occasional big-ticket guard**: separate `is_occasional` *feature* (bulk/party-sized qty, >2σ price) so the model learns "rare but expensive" contributes to spend variance without polluting the weekly-staples list.

## 4. Model architecture (3 phases)
- **Phase 1 — baseline, zero new deps (works now)**: Head A = `last_month x trend + seasonal-naive blend` (e.g. `0.6*last + 0.3*3mo_avg + 0.1*overall_avg`); Head B = `decayed-frequency x regularity x price-stability` ranking. Ship first so Predictions page has real numbers.
- **Phase 2 — sklearn-lite**: add `scikit-learn` to `pyproject.toml`. Head A -> `Ridge` on monthly features; Head B -> `LogisticRegression` (or `HistGradientBoosting` if >500 orders). Calibrate probabilities (`CalibratedClassifierCV`).
- **Phase 3 — full lib (gated on data)**: `prophet` or `lightgbm` behind a `MODEL_BACKEND` env switch, same `predictor.py` interface. Enable only with >=6–12 months; until then fall back to Phase 2.

All training is **local, on-demand, in-process** — no new services, no data leaves the box, `key_pool.py` untouched.

## 5. Backend changes (additive, Android-safe)
- New module `predictor.py`: `build_features()`, `predict_next_month()`, `predict_basket(top_k)`, `explain()` (top contributing factors per prediction for UI).
- New endpoints in `api_server.py` (all `GET`, JWT-guarded like existing stats):
  - `GET /api/predict/next-month` -> `{ predicted_total, low, high, basis_months, method }`
  - `GET /api/predict/basket?top_k=20` -> `{ items: [{name, brand, category, prob, exp_qty, exp_price}] }`
  - `GET /api/predict/category-split` -> per-category next-month share (reuses `CANONICAL_CATEGORY_ORDER`).
- Cache: compute on request + 1h in-memory TTL; retrain is just recompute (dataset tiny, <100ms). No cron needed yet.
- Never touch existing `/api/stats/*` or `orders`/`items` schemas.

## 6. Frontend changes
- `web/src/lib/api.ts`: add `getNextMonthPrediction()`, `getPredictedBasket()`, `getPredictedCategorySplit()` + TS interfaces (mirrors existing `ItemFrequency` style).
- New route `web/src/pages/Predictions.tsx`: spend forecast card (number + range + "based on N months" disclaimer), predicted list table with probability bars + "why" tooltip from `explain()`, category-split chart (recharts, already a dep). Warm-amber theme vars from `theme.css`. Link from nav + Dashboard teaser card.
- Android: no changes required (additive API); optionally surface later.

## 7. Evaluation (don't ship blind)
- **Backtest now**: train on May–Jun -> predict Jul, report `MAE`, `MAPE` for spend; `Precision@10 / Recall@10` for basket. With 3 months this is one fold — display in API (`accuracy_note`) so users see uncertainty honestly.
- **Going forward**: expanding-window backtest each month; log predictions vs actuals to a new `prediction_logs` table for drift tracking.
- Sanity guards: clamp negative spend to 0, cap single-item prob display, hide interval when `<3 months history` -> show "early estimate" badge.

## 8. Proposed build order
1. `predictor.py` features + Phase-1 baseline + unit test on fixture DB.
2. 3 additive endpoints + manual `curl` check.
3. `api.ts` additions + `Predictions.tsx` page + nav.
4. Backtest script + "early estimate" UX copy.
5. `pyproject.toml` add `scikit-learn` -> Phase-2 models behind flag.
6. Phase-3 Prophet/LightGBM adapter (env-gated, documented as needs 6+ months).
