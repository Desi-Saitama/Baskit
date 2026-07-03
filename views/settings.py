"""views/settings.py — Gemini API key config (multi-key), password change, data export."""

import streamlit as st
import os
import pandas as pd
from pathlib import Path
from database import get_orders_df, get_items_df, verify_user, create_user, user_exists, get_conn

ENV_PATH = Path(__file__).parent.parent / ".env"

# Ordered list of env var names for the 4 key slots
KEY_VARS = ["GEMINI_API_KEY", "GEMINI_API_KEY1", "GEMINI_API_KEY2", "GEMINI_API_KEY3"]


def _read_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env


def _write_env(env: dict):
    lines = [f"{k}={v}" for k, v in env.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")


def _mask(key: str) -> str:
    if len(key) > 6:
        return "●" * (len(key) - 6) + key[-6:]
    return "●●●●●●"


def render_settings():
    st.markdown("## ⚙️ Settings")

    # ══════════════════════════════════════════════════════════════════════════
    # Gemini API Keys (multi-key)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🤖 Gemini API Keys")
    st.markdown(
        "Add up to **4 keys** to enable automatic rotation when one hits the "
        "20 req/day free-tier limit. "
        "Get free keys at [aistudio.google.com](https://aistudio.google.com/app/apikey)."
    )

    env = _read_env()

    # ── Usage status card ─────────────────────────────────────────────────────
    try:
        from key_pool import ApiKeyPool, DAILY_LIMIT
        pool = ApiKeyPool()
        usage_list = pool.all_usage()

        st.markdown("**📊 Today's usage per key:**")
        cols = st.columns(len(usage_list) if usage_list else 1)
        for col, u in zip(cols, usage_list):
            pct = u["count"] / DAILY_LIMIT
            status = "🚫 Exhausted" if u["exhausted"] else ("⚡ Active" if u["active"] else "💤 Standby")
            color  = "#ef4444" if u["exhausted"] else ("#22c55e" if u["active"] else "#64748b")
            col.markdown(
                f'<div style="border:1px solid {color}33; border-radius:8px; padding:0.6rem; '
                f'background:{color}11; text-align:center;">'
                f'<div style="font-size:0.75rem; color:#94a3b8;">Key #{u["index"]} (…{u["suffix"]})</div>'
                f'<div style="font-size:1.3rem; font-weight:700; color:{color};">'
                f'{u["count"]}/{DAILY_LIMIT}</div>'
                f'<div style="font-size:0.7rem; color:{color};">{status}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.caption("Counts reset automatically at midnight UTC (start of a new calendar day).")
    except Exception as e:
        st.info(f"ℹ️ Key usage tracking unavailable: {e}")

    st.markdown("")

    # ── Edit keys form ────────────────────────────────────────────────────────
    with st.form("api_keys_form"):
        st.markdown("**🔑 API Keys** — leave blank to remove a key slot")
        new_vals: dict[str, str] = {}

        for var in KEY_VARS:
            current = env.get(var, os.environ.get(var, "")).strip().strip("'\"")
            placeholder = _mask(current) if current else "Paste API key (optional)"
            label_suffix = " *(primary)*" if var == "GEMINI_API_KEY" else ""
            new_vals[var] = st.text_input(
                f"`{var}`{label_suffix}",
                value="",
                type="password",
                placeholder=placeholder,
                key=f"settings_key_{var}",
            )

        if st.form_submit_button("💾 Save API Keys", type="primary"):
            changed = 0
            for var, val in new_vals.items():
                val = val.strip()
                if val:
                    env[var] = val
                    os.environ[var] = val
                    changed += 1
                elif var in env and not new_vals[var]:
                    # Only clear if user explicitly left blank AND it was there before
                    pass  # keep existing key when field is left empty
            _write_env(env)
            if changed:
                st.success(f"✅ Saved {changed} API key(s) to .env file.")
            else:
                st.info("ℹ️ No new keys entered — existing keys unchanged.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # Password Change
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🔒 Change Password")
    with st.form("change_pw_form"):
        old_pw     = st.text_input("Current Password", type="password")
        new_pw     = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("🔑 Update Password", type="primary"):
            if not verify_user("admin", old_pw):
                st.error("Current password is incorrect.")
            elif new_pw != confirm_pw:
                st.error("New passwords do not match.")
            elif len(new_pw) < 4:
                st.error("Password must be at least 4 characters.")
            else:
                import bcrypt
                new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
                conn = get_conn()
                conn.execute("UPDATE auth SET pw_hash = ? WHERE username = ?", (new_hash, "admin"))
                conn.commit()
                conn.close()
                st.success("✅ Password updated successfully.")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # Export Data
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 📥 Export Data")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        orders_df = get_orders_df()
        if not orders_df.empty:
            st.download_button(
                "⬇️ Download Orders CSV",
                data=orders_df.to_csv(index=False).encode("utf-8"),
                file_name="kharcha_orders.csv",
                mime="text/csv",
                width="stretch",
            )

    with col_exp2:
        items_df = get_items_df()
        if not items_df.empty:
            st.download_button(
                "⬇️ Download Items CSV",
                data=items_df.to_csv(index=False).encode("utf-8"),
                file_name="kharcha_items.csv",
                mime="text/csv",
                width="stretch",
            )

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # DB Info
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🗄️ Database Info")
    from database import DB_PATH
    if DB_PATH.exists():
        size_kb = DB_PATH.stat().st_size / 1024
        st.info(
            f"📁 Database location: `{DB_PATH}`\n\n"
            f"💾 Size: {size_kb:.1f} KB  |  "
            f"📦 Orders: {len(get_orders_df())}  |  "
            f"🛍️ Items: {len(get_items_df())}"
        )
    else:
        st.warning("Database file not found yet.")
