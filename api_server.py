"""
api_server.py — FastAPI REST server for the Kharcha Tracker Android companion app.

Shares the same SQLite database as the Streamlit web app, so all changes
sync automatically between platforms.

Run with:
    uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import io
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

# ── Local imports (reuse existing modules) ────────────────────────────────────
from database import (
    init_db, verify_user, user_exists, create_user,
    get_conn, insert_order, get_order_items, delete_order,
    update_order_and_items, is_duplicate_order,
)
from parser import parse_images, parse_pdf, parse_mixed, APP_CATEGORIES
from normalizer import init_normalizer_tables

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
        query += " AND (order_id LIKE ? OR notes LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY order_date DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])

    rows = conn.execute(query, params).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
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
            data = parse_pdf(content, app_name=app_name, filename=filename)
        elif any(content_type.startswith(t) for t in ["image/", "application/octet-stream"]):
            data = parse_images([content], app_name=app_name, filename=filename)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {content_type}. Upload JPG, PNG, or PDF."
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
def get_stats_by_app(_user: str = Depends(get_current_user)):
    """Per-app spending breakdown."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT app_name,
               COUNT(*) as orders,
               SUM(total_amount) as total_spent,
               SUM(discount) as total_saved,
               SUM(delivery_fee) as total_fees,
               AVG(total_amount) as avg_order
        FROM orders
        GROUP BY app_name
        ORDER BY total_spent DESC
    """).fetchall()
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
def get_stats_by_category(_user: str = Depends(get_current_user)):
    """Per-category item spending breakdown."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.category,
               COUNT(*) as item_count,
               SUM(i.total_price) as total_spent,
               AVG(i.unit_price) as avg_price
        FROM items i
        JOIN orders o ON i.order_id = o.id
        GROUP BY i.category
        ORDER BY total_spent DESC
    """).fetchall()
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


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Kharcha Tracker API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
