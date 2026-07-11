"""
api_server.py — FastAPI REST server for the Kharcha Tracker apps.

The React web app and Android companion app share the same SQLite database
through this API, so all changes sync automatically between platforms.

Run with:
    uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import io
import csv
import tempfile
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

# ── Local imports (reuse existing modules) ────────────────────────────────────
from database import (
    init_db, verify_user, user_exists, create_user, update_password,
    get_conn, insert_order, get_order_items, delete_order,
    update_order_and_items, is_duplicate_order,
    get_orders_df, get_items_df,
)
from parser import parse_images, parse_pdf, parse_mixed, APP_CATEGORIES
from normalizer import (
    init_normalizer_tables,
    find_duplicate_clusters,
    apply_normalization,
    get_all_aliases,
    save_aliases_bulk,
    delete_alias_by_id,
    CANONICAL_CATEGORY_ORDER,
)
from key_pool import ApiKeyPool, AllKeysExhaustedException

# Initialise DB and normalizer tables
init_db()
init_normalizer_tables()

# ── JWT config ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("JWT_SECRET", "kharcha-tracker-secret-change-me-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 720  # 30 days

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kharcha Tracker API",
    description="REST API for the Kharcha Tracker Android companion app",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# ══════════════════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    username: str = "admin"
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ItemIn(BaseModel):
    name: str
    brand: str = ""
    category: str = "Other"
    quantity: str = ""
    unit_price: float = 0
    total_price: float = 0

class OrderIn(BaseModel):
    order_date: str
    app_name: str
    app_category: str = ""
    order_id: str = ""
    total_amount: float = 0
    delivery_fee: float = 0
    discount: float = 0
    notes: str = ""
    items: list[ItemIn] = []

class OrderUpdate(BaseModel):
    order_date: str
    app_name: str
    app_category: str = ""
    order_id: str = ""
    total_amount: float = 0
    delivery_fee: float = 0
    discount: float = 0
    notes: str = ""
    items: list[ItemIn] = []

class ParsedOrderSave(BaseModel):
    order_date: str
    app_name: str
    app_category: str = ""
    order_id: str = ""
    total_amount: float = 0
    delivery_fee: float = 0
    discount: float = 0
    notes: str = ""
    items: list[ItemIn] = []
    skip_duplicate_check: bool = False


class RegisterRequest(BaseModel):
    username: str = "admin"
    password: str


class MergeRequest(BaseModel):
    variants: list[str]
    canonical_name: str
    canonical_brand: str = ""
    canonical_cat: str = ""


class UpdatePasswordRequest(BaseModel):
    new_password: str


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """Authenticate and receive a JWT token."""
    if not user_exists():
        raise HTTPException(status_code=400, detail="No account exists. Create one from the web app first.")
    if not verify_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": req.username})
    return TokenResponse(access_token=token)


@app.post("/api/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    """First-time account creation (web frontend). Issues a JWT immediately."""
    if user_exists():
        raise HTTPException(status_code=400, detail="An account already exists. Log in instead.")
    if not req.password:
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    create_user(req.username, req.password)
    token = create_access_token({"sub": req.username})
    return TokenResponse(access_token=token)


# ══════════════════════════════════════════════════════════════════════════════
#  ORDER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/orders")
def list_orders(
    skip: int = 0,
    limit: int = 50,
    app_name: Optional[str] = None,
    search: Optional[str] = None,
    _user: str = Depends(get_current_user),
):
    """List orders with pagination and optional filters."""
    skip = max(skip, 0)
    # Android's existing History screen requests 500 rows, so keep that
    # established contract while still bounding untrusted query values.
    limit = min(max(limit, 1), 500)
    conn = get_conn()
    query = """
        SELECT id, order_date, app_name, app_category, order_id,
               total_amount, delivery_fee, discount, notes, created_at
        FROM orders
        WHERE 1=1
    """
    params: list = []

    if app_name:
        query += " AND app_name = ?"
        params.append(app_name)
    if search:
        query += " AND (app_name LIKE ? OR order_id LIKE ? OR notes LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    count_query = f"SELECT COUNT(*) FROM ({query})"
    total = conn.execute(count_query, params).fetchone()[0]

    query += " ORDER BY order_date DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])

    rows = conn.execute(query, params).fetchall()
    conn.close()

    orders = []
    for r in rows:
        orders.append({
            "id": r["id"],
            "order_date": r["order_date"],
            "app_name": r["app_name"],
            "app_category": r["app_category"],
            "order_id": r["order_id"],
            "total_amount": r["total_amount"],
            "delivery_fee": r["delivery_fee"],
            "discount": r["discount"],
            "notes": r["notes"],
            "created_at": r["created_at"],
        })

    return {"orders": orders, "total": total, "skip": skip, "limit": limit}


@app.get("/api/orders/{order_db_id}")
def get_order(order_db_id: int, _user: str = Depends(get_current_user)):
    """Get a single order with its items."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM orders WHERE id = ?", (order_db_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")

    items = conn.execute(
        "SELECT * FROM items WHERE order_id = ?", (order_db_id,)
    ).fetchall()
    conn.close()

    return {
        "order": {
            "id": row["id"],
            "order_date": row["order_date"],
            "app_name": row["app_name"],
            "app_category": row["app_category"],
            "order_id": row["order_id"],
            "total_amount": row["total_amount"],
            "delivery_fee": row["delivery_fee"],
            "discount": row["discount"],
            "notes": row["notes"],
            "created_at": row["created_at"],
        },
        "items": [
            {
                "id": it["id"],
                "name": it["name"],
                "brand": it["brand"],
                "category": it["category"],
                "quantity": it["quantity"],
                "unit_price": it["unit_price"],
                "total_price": it["total_price"],
            }
            for it in items
        ],
    }


@app.post("/api/orders")
def create_order(order: OrderIn, _user: str = Depends(get_current_user)):
    """Create a new order with items."""
    app_category = order.app_category or APP_CATEGORIES.get(order.app_name, "groceries")
    items_dicts = [item.model_dump() for item in order.items]

    db_id, was_dup = insert_order(
        order_date=order.order_date,
        app_name=order.app_name,
        app_category=app_category,
        order_id=order.order_id,
        total_amount=order.total_amount,
        delivery_fee=order.delivery_fee,
        discount=order.discount,
        notes=order.notes,
        items=items_dicts,
    )

    if was_dup:
        raise HTTPException(status_code=409, detail="Duplicate order detected")

    return {"id": db_id, "message": "Order created successfully"}


@app.put("/api/orders/{order_db_id}")
def update_order(order_db_id: int, order: OrderUpdate, _user: str = Depends(get_current_user)):
    """Update an existing order and its items."""
    conn = get_conn()
    existing = conn.execute("SELECT id FROM orders WHERE id = ?", (order_db_id,)).fetchone()
    conn.close()
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")

    app_category = order.app_category or APP_CATEGORIES.get(order.app_name, "groceries")
    fields = {
        "order_date": order.order_date,
        "app_name": order.app_name,
        "app_category": app_category,
        "order_id": order.order_id,
        "total_amount": order.total_amount,
        "delivery_fee": order.delivery_fee,
        "discount": order.discount,
        "notes": order.notes,
    }
    items_dicts = [item.model_dump() for item in order.items]
    update_order_and_items(order_db_id, fields, items_dicts)

    return {"message": "Order updated successfully"}


@app.delete("/api/orders/{order_db_id}")
def remove_order(order_db_id: int, _user: str = Depends(get_current_user)):
    """Delete an order and its items."""
    conn = get_conn()
    existing = conn.execute("SELECT id FROM orders WHERE id = ?", (order_db_id,)).fetchone()
    conn.close()
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")

    delete_order(order_db_id)
    return {"message": "Order deleted successfully"}


# ══════════════════════════════════════════════════════════════════════════════
#  UPLOAD / PARSE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

def _is_quota_error(error: Exception) -> bool:
    """Identify Gemini quota errors without coupling the API to SDK internals."""
    message = str(error).lower()
    return any(marker in message for marker in ("429", "resource_exhausted", "quota", "rate limit"))


def _parse_with_key_pool(parse_func, *args, **kwargs) -> dict:
    """Run one parse with the persisted key pool and retry only quota failures."""
    pool = ApiKeyPool()
    while True:
        key = pool.current_key()
        try:
            return parse_func(
                *args,
                **kwargs,
                api_key=key,
                on_request=lambda request_key=key: pool.record_request(request_key),
            )
        except Exception as exc:
            if not _is_quota_error(exc):
                raise
            try:
                pool.mark_exhausted(key)
            except AllKeysExhaustedException as exhausted:
                raise exhausted from exc

@app.post("/api/upload/parse")
async def parse_upload(
    file: UploadFile = File(...),
    app_name: Optional[str] = Form(None),
    _user: str = Depends(get_current_user),
):
    """
    Upload an image or PDF, parse it with Gemini AI, return structured data.
    The caller can then review/edit and POST to /api/upload/save.
    """
    content = await file.read()
    filename = file.filename or ""
    content_type = file.content_type or ""

    try:
        if "pdf" in content_type or filename.lower().endswith(".pdf"):
            data = _parse_with_key_pool(parse_pdf, content, app_name=app_name, filename=filename)
        elif any(content_type.startswith(t) for t in ["image/", "application/octet-stream"]):
            data = _parse_with_key_pool(parse_images, [content], app_name=app_name, filename=filename)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {content_type}. Upload JPG, PNG, or PDF."
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AllKeysExhaustedException as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

    # Resolve app
    detected_app = data.pop("_detected_app", None)
    resolved_app = app_name or detected_app
    data["resolved_app"] = resolved_app
    data["resolved_category"] = APP_CATEGORIES.get(resolved_app, "groceries") if resolved_app else "groceries"

    return {"parsed": data}


@app.post("/api/upload/save")
def save_parsed(order: ParsedOrderSave, _user: str = Depends(get_current_user)):
    """Save a previously parsed (and possibly edited) order."""
    app_category = order.app_category or APP_CATEGORIES.get(order.app_name, "groceries")
    items_dicts = [item.model_dump() for item in order.items]

    db_id, was_dup = insert_order(
        order_date=order.order_date,
        app_name=order.app_name,
        app_category=app_category,
        order_id=order.order_id,
        total_amount=order.total_amount,
        delivery_fee=order.delivery_fee,
        discount=order.discount,
        notes=order.notes,
        items=items_dicts,
        skip_duplicate_check=order.skip_duplicate_check,
    )

    if was_dup:
        raise HTTPException(status_code=409, detail="Duplicate order detected")

    return {"id": db_id, "message": "Order saved successfully"}


# ══════════════════════════════════════════════════════════════════════════════
#  STATS / DASHBOARD ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

def _validated_month(month: Optional[str]) -> Optional[str]:
    """Return a safe YYYY-MM filter or reject malformed client input."""
    if month is None or not month.strip():
        return None
    month = month.strip()
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(status_code=422, detail="month must use YYYY-MM")
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must use YYYY-MM") from exc
    return month


@app.get("/api/stats/available-months")
def get_available_months(_user: str = Depends(get_current_user)):
    """Recorded months only, newest first, for month pickers in both clients."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT strftime('%Y-%m', order_date) AS month,
               COUNT(*) AS total_orders,
               COALESCE(SUM(total_amount), 0) AS total_spend
        FROM orders
        GROUP BY month
        HAVING month IS NOT NULL
        ORDER BY month DESC
        """
    ).fetchall()
    conn.close()
    return {
        "months": [
            {
                "month": r["month"],
                "label": datetime.strptime(r["month"], "%Y-%m").strftime("%b %Y"),
                "total_orders": int(r["total_orders"] or 0),
                "total_spend": round(float(r["total_spend"] or 0), 2),
            }
            for r in rows
        ]
    }

@app.get("/api/stats/summary")
def get_summary(_user: str = Depends(get_current_user)):
    """Dashboard KPI data."""
    conn = get_conn()

    today = datetime.now().strftime("%Y-%m-%d")
    # Week start (Monday)
    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    month_start = now.replace(day=1).strftime("%Y-%m-%d")

    def _sum(query, params=()):
        row = conn.execute(query, params).fetchone()
        return row[0] or 0

    total_spend = _sum("SELECT SUM(total_amount) FROM orders")
    total_saved = _sum("SELECT SUM(discount) FROM orders")
    total_fees = _sum("SELECT SUM(delivery_fee) FROM orders")
    total_orders = _sum("SELECT COUNT(*) FROM orders")
    today_spend = _sum("SELECT SUM(total_amount) FROM orders WHERE order_date = ?", (today,))
    week_spend = _sum("SELECT SUM(total_amount) FROM orders WHERE order_date >= ?", (week_start,))
    month_spend = _sum("SELECT SUM(total_amount) FROM orders WHERE order_date >= ?", (month_start,))
    avg_order = total_spend / total_orders if total_orders else 0

    conn.close()

    return {
        "today_spend": today_spend,
        "week_spend": week_spend,
        "month_spend": month_spend,
        "total_spend": total_spend,
        "total_saved": total_saved,
        "total_fees": total_fees,
        "total_orders": total_orders,
        "avg_order": round(avg_order, 2),
    }


@app.get("/api/stats/by-app")
def get_stats_by_app(month: Optional[str] = None, _user: str = Depends(get_current_user)):
    """Per-app spending breakdown."""
    month = _validated_month(month)
    conn = get_conn()
    where = "WHERE strftime('%Y-%m', order_date) = ?" if month else ""
    rows = conn.execute(f"""
        SELECT app_name,
               COUNT(*) as orders,
               SUM(total_amount) as total_spent,
               SUM(discount) as total_saved,
               SUM(delivery_fee) as total_fees,
               AVG(total_amount) as avg_order
        FROM orders
        {where}
        GROUP BY app_name
        ORDER BY total_spent DESC
    """, (month,) if month else ()).fetchall()
    conn.close()

    return {
        "apps": [
            {
                "app_name": r["app_name"],
                "orders": r["orders"],
                "total_spent": r["total_spent"] or 0,
                "total_saved": r["total_saved"] or 0,
                "total_fees": r["total_fees"] or 0,
                "avg_order": round(r["avg_order"] or 0, 2),
            }
            for r in rows
        ]
    }


@app.get("/api/stats/by-category")
def get_stats_by_category(month: Optional[str] = None, _user: str = Depends(get_current_user)):
    """Per-category item spending breakdown."""
    month = _validated_month(month)
    conn = get_conn()
    where = "WHERE strftime('%Y-%m', o.order_date) = ?" if month else ""
    rows = conn.execute(f"""
        SELECT i.category,
               COUNT(*) as item_count,
               SUM(i.total_price) as total_spent,
               AVG(i.unit_price) as avg_price
        FROM items i
        JOIN orders o ON i.order_id = o.id
        {where}
        GROUP BY i.category
        ORDER BY total_spent DESC
    """, (month,) if month else ()).fetchall()
    conn.close()

    return {
        "categories": [
            {
                "category": r["category"],
                "item_count": r["item_count"],
                "total_spent": r["total_spent"] or 0,
                "avg_price": round(r["avg_price"] or 0, 2),
            }
            for r in rows
        ]
    }


@app.get("/api/stats/recent-orders")
def get_recent_orders(limit: int = 5, _user: str = Depends(get_current_user)):
    """Get recent orders for the dashboard quick view."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, order_date, app_name, app_category, order_id,
               total_amount, delivery_fee, discount, notes
        FROM orders
        ORDER BY order_date DESC, created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    return {
        "orders": [
            {
                "id": r["id"],
                "order_date": r["order_date"],
                "app_name": r["app_name"],
                "app_category": r["app_category"],
                "order_id": r["order_id"],
                "total_amount": r["total_amount"],
                "delivery_fee": r["delivery_fee"],
                "discount": r["discount"],
                "notes": r["notes"],
            }
            for r in rows
        ]
    }


def _shift_month(month_start: datetime, delta_months: int) -> datetime:
    month_index = month_start.month - 1 + delta_months
    year = month_start.year + month_index // 12
    month = month_index % 12 + 1
    return month_start.replace(year=year, month=month, day=1)


@app.get("/api/stats/monthly")
def get_monthly_stats(months: int = 12, populated_only: bool = False, _user: str = Depends(get_current_user)):
    """Month-wise spend plus current-vs-previous-month comparison."""
    months = max(2, min(months, 24))
    now = datetime.now()
    current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_month = _shift_month(current_month, -(months - 1))

    conn = get_conn()
    rows = conn.execute(
        """
        SELECT strftime('%Y-%m', order_date) AS month,
               COALESCE(SUM(total_amount), 0) AS total_spend,
               COALESCE(SUM(discount), 0) AS total_saved,
               COALESCE(SUM(delivery_fee), 0) AS total_fees,
               COUNT(*) AS total_orders,
               COALESCE(AVG(total_amount), 0) AS avg_order
        FROM orders
        WHERE order_date >= ?
        GROUP BY month
        ORDER BY month
        """,
        (first_month.strftime("%Y-%m-%d"),),
    ).fetchall()
    conn.close()

    by_month = {r["month"]: r for r in rows if r["month"]}
    month_rows = []
    for i in range(months):
        month_date = _shift_month(first_month, i)
        month_key = month_date.strftime("%Y-%m")
        row = by_month.get(month_key)
        total_spend = float(row["total_spend"] or 0) if row else 0.0
        total_orders = int(row["total_orders"] or 0) if row else 0
        month_rows.append({
            "month": month_key,
            "label": month_date.strftime("%b %Y"),
            "total_spend": round(total_spend, 2),
            "total_saved": round(float(row["total_saved"] or 0), 2) if row else 0,
            "total_fees": round(float(row["total_fees"] or 0), 2) if row else 0,
            "total_orders": total_orders,
            "avg_order": round(float(row["avg_order"] or 0), 2) if row else 0,
            "is_current_month": month_key == current_month.strftime("%Y-%m"),
        })

    current = month_rows[-1]
    previous = month_rows[-2]
    spend_delta = current["total_spend"] - previous["total_spend"]
    spend_delta_percent = (
        (spend_delta / previous["total_spend"]) * 100
        if previous["total_spend"] > 0
        else None
    )

    # Legacy callers retain a continuous zero-filled range. New dashboards opt
    # into populated_only so an empty month never appears in a customer's list.
    visible_months = [m for m in month_rows if m["total_orders"] > 0] if populated_only else month_rows

    return {
        "current_month": current,
        "previous_month": previous,
        "comparison": {
            "spend_delta": round(spend_delta, 2),
            "spend_delta_percent": round(spend_delta_percent, 2) if spend_delta_percent is not None else None,
            "orders_delta": current["total_orders"] - previous["total_orders"],
            "avg_order_delta": round(current["avg_order"] - previous["avg_order"], 2),
        },
        "months": visible_months,
    }


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Kharcha Tracker API", "version": "1.0.0"}


# ══════════════════════════════════════════════════════════════════════════════
#  EXTENDED STATS ENDPOINTS (web frontend)
#  These are ADDITIVE — existing endpoints and the DB schema are untouched.
# ══════════════════════════════════════════════════════════════════════════════

def _item_frequency_rows(
    limit: int = 20,
    category: Optional[str] = None,
    sort_by: str = "times",
    month: Optional[str] = None,
) -> list[dict]:
    """Shared helper: normalised item frequency / price-range stats."""
    df = get_items_df()
    if df is None or df.empty:
        return []
    df = apply_normalization(df)
    for col in ("name", "brand", "category"):
        if col in df.columns:
            df[col] = df[col].fillna("")
    if category:
        df = df[df["category"] == category]
    if month:
        df = df[df["order_date"].astype(str).str.startswith(f"{month}-")]
    if df.empty:
        return []

    grouped = df.groupby(["name", "brand", "category"], dropna=False).agg(
        times=("name", "size"),
        avg_price=("unit_price", "mean"),
        min_price=("unit_price", "min"),
        max_price=("unit_price", "max"),
        total_spent=("total_price", "sum"),
    ).reset_index()
    grouped = grouped.sort_values(sort_by, ascending=False).head(limit)

    out = []
    for r in grouped.to_dict(orient="records"):
        out.append({
            "name": r["name"],
            "brand": r["brand"] or "",
            "category": r["category"] or "",
            "times": int(r["times"]),
            "avg_price": round(float(r["avg_price"] or 0), 2),
            "min_price": round(float(r["min_price"] or 0), 2),
            "max_price": round(float(r["max_price"] or 0), 2),
            "total_spent": round(float(r["total_spent"] or 0), 2),
        })
    return out


@app.get("/api/stats/spending-over-time")
def stats_spending_over_time(period: str = "weekly", _user: str = Depends(get_current_user)):
    """Daily / weekly / monthly aggregated spend for the dashboard chart."""
    conn = get_conn()
    now = datetime.now()
    today = now.date()
    points: list[dict] = []

    if period == "daily":
        start = today - timedelta(days=29)
        rows = conn.execute(
            "SELECT order_date, COALESCE(SUM(total_amount), 0) AS spend "
            "FROM orders WHERE order_date >= ? GROUP BY order_date ORDER BY order_date",
            (start.isoformat(),),
        ).fetchall()
        by_date = {r["order_date"]: r["spend"] or 0 for r in rows}
        for i in range(30):
            d = start + timedelta(days=i)
            ds = d.isoformat()
            points.append({"label": ds[5:], "spend": round(by_date.get(ds, 0), 2)})

    elif period == "monthly":
        rows = conn.execute(
            "SELECT strftime('%Y-%m', order_date) AS ym, COALESCE(SUM(total_amount), 0) AS spend "
            "FROM orders WHERE order_date >= date('now', '-12 months') "
            "GROUP BY ym ORDER BY ym"
        ).fetchall()
        for r in rows:
            try:
                label = datetime.strptime(r["ym"], "%Y-%m").strftime("%b %y")
            except Exception:
                label = r["ym"]
            points.append({"label": label, "spend": round(r["spend"] or 0, 2)})

    else:  # weekly (default) — last 8 weeks
        this_monday = today - timedelta(days=today.weekday())
        first_monday = this_monday - timedelta(weeks=7)
        week_starts = [first_monday + timedelta(weeks=i) for i in range(8)]
        weeks = {ws.isoformat(): 0.0 for ws in week_starts}
        rows = conn.execute(
            "SELECT order_date, total_amount FROM orders WHERE order_date >= ?",
            (first_monday.isoformat(),),
        ).fetchall()
        for r in rows:
            try:
                d = datetime.strptime(r["order_date"], "%Y-%m-%d").date()
            except Exception:
                continue
            monday = (d - timedelta(days=d.weekday())).isoformat()
            if monday in weeks:
                weeks[monday] += r["total_amount"] or 0
        for ws in sorted(weeks):
            points.append({"label": ws[5:], "spend": round(weeks[ws], 2)})

    conn.close()

    spends = [p["spend"] for p in points]
    avg = round(sum(spends) / len(spends), 2) if spends else 0
    for p in points:
        p["avg"] = avg
    return {"data": points}


@app.get("/api/stats/item-frequency")
def stats_item_frequency(limit: int = 20, category: Optional[str] = None, month: Optional[str] = None, _user: str = Depends(get_current_user)):
    """Item frequency, avg/min/max price and total spent (normalised)."""
    return {"items": _item_frequency_rows(limit=limit, category=category, sort_by="times", month=_validated_month(month))}


@app.get("/api/stats/top-items")
def stats_top_items(limit: int = 10, month: Optional[str] = None, _user: str = Depends(get_current_user)):
    """Top items by total spend amount (normalised)."""
    return {"items": _item_frequency_rows(limit=limit, sort_by="total_spent", month=_validated_month(month))}


@app.get("/api/stats/daily-heatmap")
def stats_daily_heatmap(_user: str = Depends(get_current_user)):
    """Last 30 days of daily spend totals (zero-filled for a complete grid)."""
    conn = get_conn()
    today = datetime.now().date()
    start = today - timedelta(days=29)
    rows = conn.execute(
        "SELECT order_date, COALESCE(SUM(total_amount), 0) AS amount "
        "FROM orders WHERE order_date >= ? GROUP BY order_date",
        (start.isoformat(),),
    ).fetchall()
    by_date = {r["order_date"]: r["amount"] or 0 for r in rows}
    conn.close()

    data = []
    for i in range(30):
        d = start + timedelta(days=i)
        ds = d.isoformat()
        data.append({"date": ds, "amount": round(by_date.get(ds, 0), 2)})
    return {"data": data}


@app.get("/api/stats/savings-insights")
def stats_savings_insights(_user: str = Depends(get_current_user)):
    """Computed cost-saving recommendations for the Savings page."""
    conn = get_conn()
    total_spend = conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0]
    total_saved = conn.execute("SELECT COALESCE(SUM(discount), 0) FROM orders").fetchone()[0]
    total_fees = conn.execute("SELECT COALESCE(SUM(delivery_fee), 0) FROM orders").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    app_rows = conn.execute(
        "SELECT app_name, COALESCE(SUM(discount), 0) AS d, COALESCE(SUM(total_amount), 0) AS t "
        "FROM orders GROUP BY app_name"
    ).fetchall()
    conn.close()

    insights: list[dict] = []
    if total_orders > 0:
        avg_fee = total_fees / total_orders
        insights.append({
            "type": "consolidation",
            "title": "Consolidate grocery runs",
            "description": f"Grouping orders could cut ~{max(int(total_orders * 0.3), 1)} redundant delivery fees.",
            "impact": int(avg_fee * total_orders * 0.3) or 620,
        })

        best = max(
            app_rows,
            key=lambda r: (r["d"] or 0) / max(r["t"] or 1, 1),
            default=None,
        )
        if best and (best["d"] or 0) > 0:
            insights.append({
                "type": "discount",
                "title": f"Best discount app: {best['app_name'].title()}",
                "description": "Highest discount ratio across your delivery apps.",
                "impact": int((best["d"] or 0) / max(total_orders, 1)) or 410,
            })

        if total_fees > 200:
            insights.append({
                "type": "subscription",
                "title": "Consider a delivery pass",
                "description": f"You've paid ₹{int(total_fees)} in fees — a subscription may pay off.",
                "impact": int(total_fees * 0.4) or 280,
            })

        items = _item_frequency_rows(limit=50)
        if items:
            var_item = max(items, key=lambda i: i["max_price"] - i["min_price"])
            if var_item["max_price"] > var_item["min_price"]:
                insights.append({
                    "type": "variance",
                    "title": f"Price variance: {var_item['name']}",
                    "description": f"Ranges ₹{int(var_item['min_price'])}–₹{int(var_item['max_price'])} across orders.",
                    "impact": int((var_item["max_price"] - var_item["min_price"]) * var_item["times"]) or 190,
                })

    if not insights:
        insights = [
            {"type": "consolidation", "title": "Consolidate grocery runs", "description": "Group orders to save on delivery fees", "impact": 620},
            {"type": "discount", "title": "Best discount app", "description": "Check which app gives the most discounts", "impact": 410},
            {"type": "subscription", "title": "Consider delivery pass", "description": "Your delivery fees may justify a subscription", "impact": 280},
            {"type": "variance", "title": "Price variance detected", "description": "Some items have significant price swings", "impact": 190},
        ]
    return {"insights": insights}


@app.get("/api/stats/price-trend")
def stats_price_trend(item_name: str, _user: str = Depends(get_current_user)):
    """Price history for a specific item (normalised, matches item-frequency names)."""
    df = get_items_df()
    if df is None or df.empty:
        return {"data": []}
    df = apply_normalization(df)
    df = df.fillna({"name": "", "unit_price": 0, "order_date": ""})
    sub = df[df["name"].str.lower() == (item_name or "").strip().lower()]
    if sub.empty:
        return {"data": []}
    sub = sub.sort_values("order_date")
    prices = [float(p) for p in sub["unit_price"].tolist()]
    avg = round(sum(prices) / len(prices), 2) if prices else 0
    data = [
        {"date": r["order_date"], "price": round(float(r["unit_price"] or 0), 2), "avg": avg}
        for r in sub.to_dict(orient="records")
    ]
    return {"data": data}


@app.get("/api/stats/items-per-app")
def stats_items_per_app(_user: str = Depends(get_current_user)):
    """Unique / total item counts and spend per delivery app."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.app_name,
               COUNT(DISTINCT lower(i.name)) AS unique_items,
               COUNT(*)                     AS total_items,
               COALESCE(AVG(i.unit_price), 0)   AS avg_price,
               COALESCE(SUM(i.total_price), 0)  AS total_spent
        FROM items i
        JOIN orders o ON i.order_id = o.id
        GROUP BY o.app_name
        ORDER BY total_spent DESC
    """).fetchall()
    conn.close()
    return {
        "data": [
            {
                "app_name": r["app_name"],
                "unique_items": r["unique_items"],
                "total_items": r["total_items"],
                "avg_price": round(r["avg_price"] or 0, 2),
                "total_spent": round(r["total_spent"] or 0, 2),
            }
            for r in rows
        ]
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CLEANUP ENDPOINTS (web frontend)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/cleanup/clusters")
def cleanup_clusters(_user: str = Depends(get_current_user)):
    """Fuzzy duplicate clusters (auto-detected, no DB writes)."""
    df = get_items_df()
    if df is None or df.empty:
        return {"clusters": []}
    clusters = find_duplicate_clusters(df)

    out = []
    for c in clusters:
        keys = c["keys"]  # list of (name, brand, category)
        names = list({k[0] for k in keys if k[0]})
        brands = sorted({(k[1] or "").strip() for k in keys if (k[1] or "").strip()})

        cats = [k[2] for k in keys if k[2]]
        cat_ordered: list[str] = []
        for cc in CANONICAL_CATEGORY_ORDER:
            if cc in cats and cc not in cat_ordered:
                cat_ordered.append(cc)
        for cc in cats:
            if cc not in cat_ordered:
                cat_ordered.append(cc)

        stripped = c.get("stripped", [])
        if len(stripped) >= 2:
            import difflib
            pairs = [
                difflib.SequenceMatcher(None, stripped[i], stripped[j]).ratio()
                for i in range(len(stripped))
                for j in range(i + 1, len(stripped))
            ]
            score = round(sum(pairs) / len(pairs), 3) if pairs else 0.0
        else:
            score = 1.0

        out.append({
            "canonical_suggestion": c["canonical_name"],
            "score": score,
            "variants": names,
            "brand_suggestions": brands,
            "category_suggestions": cat_ordered,
        })
    return {"clusters": out}


@app.get("/api/cleanup/aliases")
def cleanup_aliases(_user: str = Depends(get_current_user)):
    """All persisted item-alias mappings."""
    return {"aliases": get_all_aliases()}


@app.post("/api/cleanup/merge")
def cleanup_merge(req: MergeRequest, _user: str = Depends(get_current_user)):
    """Persist canonical mappings for a set of variant names."""
    conn = get_conn()
    mappings: list[tuple] = []
    for v in req.variants:
        v = (v or "").strip()
        if not v:
            continue
        rows = conn.execute(
            "SELECT DISTINCT name, brand FROM items WHERE lower(name) = lower(?)",
            (v,),
        ).fetchall()
        if rows:
            for r in rows:
                mappings.append((r["name"], r["brand"] or "", req.canonical_name, req.canonical_brand, req.canonical_cat))
        else:
            mappings.append((v, "", req.canonical_name, req.canonical_brand, req.canonical_cat))
    conn.close()

    if mappings:
        save_aliases_bulk(mappings)
    return {"message": f"Merged {len(mappings)} variant(s) into '{req.canonical_name}'"}


@app.delete("/api/cleanup/aliases/{alias_id}")
def cleanup_delete_alias(alias_id: int, _user: str = Depends(get_current_user)):
    """Delete a single saved alias mapping by id."""
    if not delete_alias_by_id(alias_id):
        raise HTTPException(status_code=404, detail="Alias not found")
    return {"message": "Alias deleted"}


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS ENDPOINTS (web frontend)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/settings/key-pool")
def settings_key_pool(_user: str = Depends(get_current_user)):
    """Status of every configured Gemini API key in the rotating pool."""
    try:
        pool = ApiKeyPool()
        return {"keys": pool.all_usage()}
    except AllKeysExhaustedException:
        # The dashboard should continue showing the day's recorded usage and
        # exhausted state instead of looking like no keys were configured.
        return {"keys": ApiKeyPool.usage_snapshot()}
    except Exception:
        # No keys configured (or pool not initialised) — return empty list.
        return {"keys": []}


@app.post("/api/settings/update-password")
def settings_update_password(req: UpdatePasswordRequest, user: str = Depends(get_current_user)):
    """Update the currently logged-in user's password."""
    if not req.new_password:
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    if not update_password(user, req.new_password):
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Password updated successfully"}


# ══════════════════════════════════════════════════════════════════════════════
#  CSV EXPORT ENDPOINTS (web frontend)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/export/orders-csv")
def export_orders_csv(_user: str = Depends(get_current_user)):
    """Stream the orders table as a CSV download."""
    df = get_orders_df()
    csv_text = df.to_csv(index=False)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )


@app.get("/api/export/items-csv")
def export_items_csv(_user: str = Depends(get_current_user)):
    """Stream the items table (joined with orders) as a CSV download."""
    df = get_items_df()
    csv_text = df.to_csv(index=False)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=items.csv"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
