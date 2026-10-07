# Implementation Plan: Next Month Expense & Smart Basket Predictor

## Goal Description
Enable Kharcha Tracker (Baskit) to automatically:
1. **Forecast Next Month's Total & Category-wise Expense** (Regression with uncertainty intervals).
2. **Predict What the User is Going to Buy Next Month** (Smart Basket / Repurchase Ranking).

### Core Design Philosophy: Learning Weights Without Hard Rules
As requested, the model must **give weightage to frequently bought items while naturally avoiding occasional / one-off purchases**, but **these must not be hardcoded `if/else` rules**. Instead:
- Continuous signals (frequency velocity, inter-purchase intervals, cycle maturity ratio, exponential time decay, and category repeat priors) are fed into a supervised statistical/ML model.
- The model's loss function automatically learns the optimal continuous decision boundary and weight coefficients from historical invoice data.
- Occasional items (bought once or twice with huge erratic gaps) naturally receive low probabilities ($P < 0.15$), regular staples receive high probabilities ($P > 0.75$), and periodic restocks (items bought on an established 20-30 day rhythm) are appropriately timed without arbitrary threshold cutoffs.

---

## User Review Required

> [!IMPORTANT]
> **Dependency Addition**: We propose adding `scikit-learn>=1.4.0` to `pyproject.toml`. Scikit-learn is lightweight, fast, has zero C++ compile issues in uv/Python 3.12, and runs inference in <10ms on CPU without any GPU or heavy daemon requirements.

> [!NOTE]
> **Data Size & Rolling-Window Validation**: The current database contains **89 orders** (May 2 to July 19, 2026) and **306 item transactions** (166 unique canonical items). To train effectively without needing years of data, we use **rolling walk-forward time windows** (e.g., month-over-month / bi-weekly snapshots) so the model trains on multiple historical prediction horizons.

> [!IMPORTANT]
> **Android App & DB Compatibility**: In accordance with project rules, all new prediction endpoints are **additive** (`/api/predictions/*`). Existing Android endpoints, order schemas, and DB tables remain 100% backward compatible.

---

## Proposed Architecture & Workflow

```mermaid
graph TD
    subgraph Data Layer
        A[(SQLite: orders & items)] --> B[normalizer.py: apply_normalization]
        B --> C[Clean Canonical Items & Timestamps]
    end

    subgraph Feature Engineering (predictor.py)
        C --> D1[Frequency Features: velocity, order share, decay rate]
        C --> D2[Cadence Features: avg interval, std gap, cycle maturity]
        C --> D3[Recency & Streak: days since last buy, monthly presence]
        C --> D4[Context Priors: category repurchase rate, price stability]
    end

    subgraph Machine Learning Engine
        D1 & D2 & D3 & D4 --> E1[Basket Predictor: Logistic/GBM Classifier]
        D1 & D2 & D3 & D4 --> E2[Expense Regressor: Top-Down Trend + Bottom-Up Basket Sum]
        E1 --> F1[Ranked Repurchase Probabilities P(buy)]
        E2 --> F2[Next Month Spend Forecast + Bounds]
    end

    subgraph API & Presentation
        F1 & F2 --> G[FastAPI Endpoints /api/predictions/*]
        G --> H[React Web UI: Predictions & Smart Shopping List]
        G -.-> I[Android App - Future Optional Consumption]
    end
```

---

## Detailed Technical Design

### 1. Item Repurchase Model ("What I Am Going to Buy")

#### Feature Engineering Matrix (Per Item $i$ at Prediction Cutoff $T$)

Rather than rigid rules like `if count > 2`, we compute continuous mathematical features:

| Feature Name | Formula / Definition | Intuitive Meaning |
| :--- | :--- | :--- |
| `purchase_frequency_rate` | $\frac{\text{orders with item } i}{\text{total user orders in window}}$ | Overall user purchase concentration |
| `exponential_decay_velocity` | $\sum_{k} e^{-\lambda (T - t_{k})}$ with half-life $\approx 30$ days | Gives recent purchases higher weight than distant ones |
| `monthly_recurrence_ratio` | $\frac{\text{months item was bought}}{\text{total active user months}}$ | Distinguishes continuous staples from 1-month fads |
| `mean_interpurchase_days` ($\mu_{\Delta t}$) | Average gap between consecutive purchases of item $i$ | Natural consumption cycle (e.g. 5 days for milk, 30 days for detergent) |
| `interpurchase_std_days` ($\sigma_{\Delta t}$) | Std deviation of intervals between purchases | Regularity vs erraticness (low = routine staple; high = occasional) |
| `days_since_last_purchase` ($\Delta t_{\text{last}}$) | $T - t_{\text{last}}$ | How long user has gone without buying this item |
| `cycle_maturity_ratio` | $\tau = \frac{\Delta t_{\text{last}}}{\mu_{\Delta t} + 1.0}$ | **The key learned signal**: $\tau \approx 1$ means restock is due; $\tau \ll 1$ means user has stock; $\tau \gg 1$ means abandoned or rare |
| `category_repurchase_prior` | Empirical repeat rate of item's category in the dataset | e.g. "Dairy & Eggs" (high baseline) vs "Household" (low baseline) |
| `price_consistency` | Coefficient of variation of unit price ($\sigma_p / \mu_p$) | Price stability indicator |

#### How the Model Learns Continuous Weighting
- **Training Labels**: For historical time cutoff $T$ (e.g. end of May), target $y_i = 1$ if item $i$ was purchased in the subsequent 30 days (June), else $0$.
- **Objective Function**: Calibrated Regularized Logistic Loss (Binary Cross-Entropy with L2 regularization) or HistGradientBoosting:
  $$\min_{w, b} -\sum_{i} \left[ y_i \log \hat{p}_i + (1 - y_i) \log (1 - \hat{p}_i) \right] + \frac{\lambda}{2} \|w\|^2$$
- **Automatic Discrimination**:
  - A staple like **Banana Robusta** or **Paneer** has high `monthly_recurrence_ratio` (1.0), low `mean_interpurchase_days` (5-10d), and low `interpurchase_std_days`. The positive weights on frequency and cycle maturity drive $\hat{p}_i > 0.85$.
  - An occasional item (e.g. bought once 60 days ago) has `monthly_recurrence_ratio` = 0.33, `cycle_maturity` imputed to prior, and zero recent velocity. The loss function pushes its score to $\hat{p}_i < 0.10$.
  - A periodic item (bought twice, 25 days apart, with last purchase 24 days ago) has $\tau \approx 0.96 \to$ the model naturally assigns $\hat{p}_i \approx 0.65$ without needing a hardcoded count threshold!

---

### 2. Next Month Expense Forecasting Model

We implement a **Dual Reconciled Spending Forecaster**:

1. **Top-Down Macro Model (Time Series & Rolling Trend)**:
   - Uses 14-day and 30-day rolling daily spend velocity, momentum ($\frac{\text{spend}_{14d}}{\text{spend}_{30d}/2}$), day-of-week spend multipliers, and order cadence.
   - Fits a trend regressor to estimate baseline next 30-day spend.
2. **Bottom-Up Micro Model (Basket Summation)**:
   - For every item $i$, expected spend is:
     $$\hat{E}_{\text{items}} = \sum_{i} \left( \hat{p}_i \times \hat{q}_i \times \bar{c}_i \right)$$
     where $\hat{p}_i$ is the predicted probability, $\hat{q}_i$ is median order quantity, and $\bar{c}_i$ is average unit price.
   - Plus expected delivery fees and discretionary/unseen new item buffer:
     $$\hat{E}_{\text{discretionary}} = \text{historical fraction of spend on new/one-off items} \times \text{trend spend}$$
3. **Combined Forecast**:
   - $\hat{E}_{\text{total}} = \alpha \hat{E}_{\text{top\_down}} + (1 - \alpha) \hat{E}_{\text{bottom\_up}}$ (where $\alpha \approx 0.5$, calibrated via validation).
   - Generates an 80% confidence interval: $[\hat{E} - 1.28 \sigma_{\text{err}}, \hat{E} + 1.28 \sigma_{\text{err}}]$.
   - Provides an interpretable breakdown:
     - Predicted Grocery Spend (Staples vs Discretionary)
     - Predicted Food Delivery Spend
     - Predicted Delivery & Convenience Fees

---

### 3. Proposed Changes by Component

#### Backend (`./`)

##### [MODIFY] `pyproject.toml`
- Add `"scikit-learn>=1.4.0"` to `dependencies`.

##### [NEW] `predictor.py`
A clean, self-contained Python module providing:
- `FeatureExtractor`: Takes normalized items DataFrame and orders DataFrame; generates sliding-window feature snapshots.
- `BasketPredictor`: Trains and persists the item repurchase model, outputs probabilities, confidence bands, cycle status, and feature importances.
- `ExpensePredictor`: Computes top-down regression, category breakdowns, and bottom-up aggregated expense forecasts.
- `PredictionPipeline`: Coordinates retraining, model caching to `data/models/predictor_cache.pkl`, and exposes high-level inference functions.

##### [MODIFY] `api_server.py`
Add additive REST endpoints:
- `GET /api/predictions/summary`: Returns next month total spend forecast, confidence range, category breakdown, comparison with current/last month, and top budget drivers.
- `GET /api/predictions/smart-basket`: Returns ranked list of items predicted for next month with purchase probability, expected price, cycle maturity status (e.g., "Due for restock", "Weekly staple", "Low probability"), and category.
- `POST /api/predictions/retrain`: Triggers on-demand model retraining, returns training evaluation metrics (ROC-AUC, Precision@K, spend MAE).
- `GET /api/predictions/feature-weights`: Returns learned weights/feature importances to give full transparency on how frequency vs recency vs cadence are balanced.

---

#### Frontend (`web/`)

##### [MODIFY] `web/src/lib/api.ts`
- Add TypeScript interfaces: `PredictionSummary`, `PredictedItem`, `ModelFeatureWeights`, `RetrainResult`.
- Add client helper functions: `getPredictionSummary()`, `getSmartBasket()`, `retrainPredictor()`, `getFeatureWeights()`.

##### [NEW] `web/src/pages/Predictions.tsx`
A rich, warm-amber themed dashboard view featuring:
1. **Next Month Spend Forecast Card**:
   - Hero metric: e.g. **₹8,450** (Range: ₹7,800 – ₹9,100).
   - Monthly trend badge (+/- % vs previous month).
   - Category budget projection bars (Groceries, Dairy, Food Delivery, etc.).
2. **Interactive "Smart Shopping Basket"**:
   - Ranked items by purchase probability.
   - Filter pills: "All", "Staples (>75%)", "Due for Restock", "Occasional (<30%)".
   - Item row with probability badge, expected cost, restock cycle indicator, and interactive checkbox to generate an actionable next-month shopping list with instant running total.
3. **Model Transparency & Retraining Panel**:
   - Visual bar chart / indicator showing learned feature weights (e.g. Cadence Maturity: +38%, Frequency Velocity: +32%, Monthly Recurrence: +20%, Category Prior: +10%).
   - "Retrain Model" button with live status feedback.

##### [MODIFY] `web/src/components/layout/Sidebar.tsx`
- Add **"Predictions"** navigation item with a `Sparkles` or `BrainCircuit` icon.

##### [MODIFY] `web/src/App.tsx`
- Register `page === 'Predictions'` view routing.

---

## Verification Plan

### Automated Tests
1. **Dependency check**: Run `uv sync` to confirm `scikit-learn` installs without conflicts.
2. **Model Training Unit Test**:
   ```bash
   uv run python -c "
   import predictor
   pipeline = predictor.PredictionPipeline()
   metrics = pipeline.train()
   print('Training metrics:', metrics)
   summary = pipeline.predict_summary()
   print('Forecast spend:', summary['forecast_spend'])
   basket = pipeline.predict_smart_basket()
   print('Top 5 predicted items:', [(it['name'], it['probability']) for it in basket[:5]])
   "
   ```
3. **API Endpoint Verification**:
   ```bash
   uv run python -c "
   from fastapi.testclient import TestClient
   from api_server import app
   client = TestClient(app)
   # Test endpoints with auth token
   "
   ```
4. **Web Frontend Build**:
   ```bash
   cd web && npm run build
   ```

### Manual Verification
1. Open the React web app at `http://localhost:5173`.
2. Navigate to the new **"Predictions"** page.
3. Verify:
   - Forecast spend is displayed with realistic confidence intervals.
   - Top predicted items match frequent staples (e.g., Paneer, Cucumber, Carrot, Milk, Bread) with high probabilities (>70%).
   - One-off items (e.g., bought once in May and never again) have low probabilities (<15%).
   - Selecting checkboxes in the Smart Basket dynamically calculates the estimated cart total.
   - Clicking "Retrain Model" completes smoothly and updates the metrics.
