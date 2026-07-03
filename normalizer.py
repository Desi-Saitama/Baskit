"""
normalizer.py — Smart item-name & category normalisation for the Invoice Tracker.

Two modes:
  1. Auto-detect near-duplicates (fuzzy clustering) at display time — zero DB writes.
  2. Persist a user-approved canonical mapping in the DB so future queries are clean.
"""

import re
import difflib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "tracker.db"

# ── Similarity threshold ───────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.72   # lower = more aggressive grouping

# ── Canonical category precedence (most-specific wins) ────────────────────────
# When an item cluster has conflicting categories, pick the first match.
CANONICAL_CATEGORY_ORDER = [
    "Dairy & Eggs",
    "Fruits & Vegetables",
    "Grains & Pulses",
    "Snacks",
    "Beverages",
    "Personal Care",
    "Household",
    "Bakery",
    "Spices & Condiments",
    "Ready to Eat",
    "Restaurant Food",
    "Meat & Seafood",
    "Other",
]


# ══════════════════════════════════════════════════════════════════════════════
#  DB table for persisted mappings
# ══════════════════════════════════════════════════════════════════════════════

def init_normalizer_tables():
    """Create the item_aliases table if it doesn't exist."""
    conn = _conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS item_aliases (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_name      TEXT NOT NULL,
            raw_brand     TEXT NOT NULL DEFAULT '',
            canonical_name  TEXT NOT NULL,
            canonical_brand TEXT NOT NULL DEFAULT '',
            canonical_cat   TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    # unique on (raw_name, raw_brand) so we can upsert
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_item_aliases_raw
        ON item_aliases (lower(raw_name), lower(raw_brand))
    """)
    conn.commit()
    conn.close()


def _conn():
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


# ══════════════════════════════════════════════════════════════════════════════
#  Text helpers
# ══════════════════════════════════════════════════════════════════════════════

def _strip_for_compare(name: str, brand: str) -> str:
    """
    Strip leading brand prefix, trailing parenthetical size/desc,
    and normalise whitespace — used only for similarity comparison.
    """
    text = name.strip()
    # Strip leading brand name (case-insensitive)
    if brand and brand.strip():
        text = re.sub(r"(?i)^\s*" + re.escape(brand.strip()) + r"\s*", "", text)
    # Remove trailing parenthetical e.g. " (250g)" or "(Arati pandu)"
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text)
    # Remove trailing pipe-separated sub-descriptions  "| Spicy And Tangy | Dip"
    text = re.sub(r"\s*\|.*$", "", text)
    # Collapse spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _best_category(categories: list[str]) -> str:
    """Pick the most-specific / most-informative category from a list."""
    for cat in CANONICAL_CATEGORY_ORDER:
        if cat in categories:
            return cat
    return categories[0] if categories else "Other"


def _best_name(names: list[str], brands: list[str]) -> tuple[str, str]:
    """
    Pick the canonical (name, brand) pair from a cluster:
      - prefer the name that does NOT redundantly start with the brand
      - prefer the shortest non-trivial name (less OCR noise)
    """
    # Collect unique non-empty brands
    unique_brands = sorted({b.strip() for b in brands if b and b.strip()})
    canon_brand = unique_brands[0] if unique_brands else ""

    candidates = []
    for name, brand in zip(names, brands):
        # Strip brand prefix if the name starts with it
        clean = name.strip()
        if brand and brand.strip() and clean.lower().startswith(brand.strip().lower()):
            clean = clean[len(brand.strip()):].strip()
        candidates.append(clean)

    # Sort by length — shorter cleaned name wins (less noise)
    best = sorted(candidates)[0] if candidates else names[0]
    return best.strip(), canon_brand


# ══════════════════════════════════════════════════════════════════════════════
#  Core clustering
# ══════════════════════════════════════════════════════════════════════════════

def find_duplicate_clusters(items_df) -> list[dict]:
    """
    Given a DataFrame with columns [name, brand, category],
    return a list of clusters where each cluster is:
    {
      "indices":        [list of df row indices],
      "keys":           [(name, brand, category), ...],
      "canonical_name": str,
      "canonical_brand": str,
      "canonical_cat":  str,
      "stripped":       [stripped comparison strings],
    }
    Only clusters with > 1 distinct (name, brand) pair are returned.
    """
    rows = list(items_df[["name","brand","category"]].drop_duplicates().itertuples(index=False))
    n = len(rows)
    stripped = [_strip_for_compare(r.name, r.brand) for r in rows]

    used = [False] * n
    clusters = []

    for i in range(n):
        if used[i]:
            continue
        grp_idx = [i]
        used[i] = True
        for j in range(i + 1, n):
            if used[j]:
                continue
            if _sim(stripped[i], stripped[j]) >= SIMILARITY_THRESHOLD:
                grp_idx.append(j)
                used[j] = True

        if len(grp_idx) < 2:
            continue

        # Check at least 2 distinct (name, brand) combos
        keys = [(rows[k].name, rows[k].brand, rows[k].category) for k in grp_idx]
        distinct_pairs = {(n_, b_) for n_, b_, _ in keys}
        if len(distinct_pairs) < 2:
            continue

        names_  = [k[0] for k in keys]
        brands_ = [k[1] for k in keys]
        cats_   = [k[2] for k in keys]

        canon_name, canon_brand = _best_name(names_, brands_)
        canon_cat = _best_category(cats_)

        clusters.append({
            "indices":        grp_idx,
            "keys":           keys,
            "canonical_name": canon_name,
            "canonical_brand": canon_brand,
            "canonical_cat":  canon_cat,
            "stripped":       [stripped[k] for k in grp_idx],
        })

    return clusters


# ══════════════════════════════════════════════════════════════════════════════
#  Apply normalisation to a DataFrame (read-only, no DB writes)
# ══════════════════════════════════════════════════════════════════════════════

def apply_normalization(items_df, extra_aliases: dict | None = None):
    """
    Return a copy of items_df with name/brand/category columns normalised.

    Normalization sources (applied in order of precedence):
      1. Persisted aliases from the DB  (item_aliases table)
      2. extra_aliases dict  {(raw_name, raw_brand): (canon_name, canon_brand, canon_cat)}
      3. Auto-detected clusters (fuzzy, applied in-memory only)

    The original DataFrame is never mutated.
    """
    df = items_df.copy()

    # 1 — Load persisted aliases
    aliases = _load_persisted_aliases()

    # 2 — Merge extra_aliases
    if extra_aliases:
        aliases.update(extra_aliases)

    # 3 — Apply persisted aliases
    def _remap_row(row):
        key = (row["name"].strip(), (row["brand"] or "").strip())
        if key in aliases:
            cn, cb, cc = aliases[key]
            row = row.copy()
            row["name"]     = cn if cn else row["name"]
            row["brand"]    = cb if cb else row["brand"]
            row["category"] = cc if cc else row["category"]
        return row

    df = df.apply(_remap_row, axis=1)

    # 4 — Auto-cluster remaining entries and apply canonical name/cat
    clusters = find_duplicate_clusters(df)
    for cluster in clusters:
        for name, brand, cat in cluster["keys"]:
            mask = (
                (df["name"].str.strip() == name.strip()) &
                (df["brand"].fillna("").str.strip() == (brand or "").strip())
            )
            df.loc[mask, "name"]     = cluster["canonical_name"]
            df.loc[mask, "brand"]    = cluster["canonical_brand"]
            df.loc[mask, "category"] = cluster["canonical_cat"]

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  Persisted alias CRUD
# ══════════════════════════════════════════════════════════════════════════════

def _load_persisted_aliases() -> dict:
    """Return {(raw_name, raw_brand): (canon_name, canon_brand, canon_cat)}."""
    try:
        conn = _conn()
        rows = conn.execute("SELECT * FROM item_aliases").fetchall()
        conn.close()
        return {
            (r["raw_name"].strip(), (r["raw_brand"] or "").strip()):
            (r["canonical_name"], r["canonical_brand"], r["canonical_cat"])
            for r in rows
        }
    except Exception:
        return {}


def save_alias(raw_name: str, raw_brand: str,
               canon_name: str, canon_brand: str, canon_cat: str):
    """Upsert a single alias mapping."""
    conn = _conn()
    conn.execute("""
        INSERT INTO item_aliases (raw_name, raw_brand, canonical_name, canonical_brand, canonical_cat)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(lower(raw_name), lower(raw_brand))
        DO UPDATE SET
            canonical_name  = excluded.canonical_name,
            canonical_brand = excluded.canonical_brand,
            canonical_cat   = excluded.canonical_cat
    """, (raw_name.strip(), (raw_brand or "").strip(), canon_name, canon_brand, canon_cat))
    conn.commit()
    conn.close()


def save_aliases_bulk(mappings: list[tuple]):
    """
    Save many aliases at once.
    mappings: [(raw_name, raw_brand, canon_name, canon_brand, canon_cat), ...]
    """
    conn = _conn()
    conn.executemany("""
        INSERT INTO item_aliases (raw_name, raw_brand, canonical_name, canonical_brand, canonical_cat)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(lower(raw_name), lower(raw_brand))
        DO UPDATE SET
            canonical_name  = excluded.canonical_name,
            canonical_brand = excluded.canonical_brand,
            canonical_cat   = excluded.canonical_cat
    """, [(rn.strip(), (rb or "").strip(), cn, cb, cc)
          for rn, rb, cn, cb, cc in mappings])
    conn.commit()
    conn.close()


def delete_alias(raw_name: str, raw_brand: str):
    conn = _conn()
    conn.execute(
        "DELETE FROM item_aliases WHERE lower(raw_name)=lower(?) AND lower(raw_brand)=lower(?)",
        (raw_name.strip(), (raw_brand or "").strip())
    )
    conn.commit()
    conn.close()


def get_all_aliases() -> list[dict]:
    try:
        conn = _conn()
        rows = conn.execute("SELECT * FROM item_aliases ORDER BY raw_name").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
