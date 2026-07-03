"""
app.py — Main Streamlit application entry point.

Run with:
    uv run streamlit run app.py
"""

import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Kharcha Tracker",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

from database import init_db, verify_user, create_user, user_exists
from views.upload import render_upload
from views.dashboard import render_dashboard
from views.history import render_history
from views.settings import render_settings
from views.bulk import render_bulk
from views.cleanup import render_cleanup
from normalizer import init_normalizer_tables
init_normalizer_tables()

# Initialise DB on first run
init_db()

# ── Inject CSS ────────────────────────────────────────────────────────────────
def _load_css():
    css_path = Path(__file__).parent / "static" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

_load_css()

# ── Session state defaults ────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
def render_auth():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 2rem 0 1rem;">
            <div style="font-size:3.5rem;">🛒</div>
            <h1 style="margin:0; font-size:2rem; font-weight:800; 
                       background: linear-gradient(135deg, #6366f1, #8b5cf6);
                       -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
                Kharcha Tracker
            </h1>
            <p style="color:#94a3b8; margin-top:0.25rem;">
                Your private expense tracker for Indian delivery apps
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        is_first_run = not user_exists()

        with st.form("auth_form", clear_on_submit=False):
            if is_first_run:
                st.info("👋 First time setup — create your account below.")

            username = st.text_input(
                "Username", placeholder="your username",
                label_visibility="collapsed" if not is_first_run else "visible"
            )
            username = username or "admin"  # default for single-user

            password = st.text_input(
                "Password", type="password", placeholder="Enter password"
            )

            if is_first_run:
                confirm = st.text_input(
                    "Confirm Password", type="password",
                    placeholder="Confirm password"
                )
                submitted = st.form_submit_button(
                    "🚀 Create Account & Sign In",
                    width="stretch", type="primary"
                )
                if submitted:
                    if not password:
                        st.error("Password cannot be empty.")
                    elif password != confirm:
                        st.error("Passwords do not match.")
                    else:
                        create_user(username, password)
                        st.session_state.authenticated = True
                        st.rerun()
            else:
                submitted = st.form_submit_button(
                    "🔓 Sign In", width="stretch", type="primary"
                )
                if submitted:
                    if verify_user(username, password):
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP (after auth)
# ═══════════════════════════════════════════════════════════════════════════════
def render_main():
    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:1rem 0 0.5rem;">
            <div style="font-size:2.5rem;">🛒</div>
            <div style="font-weight:800; font-size:1.2rem;
                        background:linear-gradient(135deg,#6366f1,#8b5cf6);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                Kharcha Tracker
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        pages = {
            "📊 Dashboard":   "Dashboard",
            "📤 Upload":      "Upload",
            "📂 Bulk Import": "Bulk",
            "📋 History":     "History",
            "🧹 Data Cleanup": "Cleanup",
            "⚙️ Settings":    "Settings",
        }
        for label, key in pages.items():
            active = st.session_state.page == key
            if st.button(
                label,
                width="stretch",
                type="primary" if active else "secondary",
                key=f"nav_{key}",
            ):
                st.session_state.page = key
                st.rerun()

        st.divider()
        if st.button("🚪 Sign Out", width="stretch"):
            st.session_state.authenticated = False
            st.rerun()

    # ── Page routing ──────────────────────────────────────────────────────────
    page = st.session_state.page
    if page == "Dashboard":
        render_dashboard()
    elif page == "Upload":
        render_upload()
    elif page == "Bulk":
        render_bulk()
    elif page == "History":
        render_history()
    elif page == "Cleanup":
        render_cleanup()
    elif page == "Settings":
        render_settings()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.authenticated:
    render_main()
else:
    render_auth()
