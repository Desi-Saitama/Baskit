import os
import subprocess
import time
import datetime
from pathlib import Path
import streamlit as st

from bulk_processor import BulkProcessor, ALL_EXTS, MAX_REQUESTS_PER_MINUTE, RunLogger
from key_pool import ApiKeyPool, AllKeysExhaustedException, DAILY_LIMIT
from parser import APP_NAMES, APP_CATEGORIES
from database import insert_order


# ── Native folder picker ───────────────────────────────────────────────────────

def _pick_folder() -> str | None:
    """
    Open the system's native folder-chooser dialog.
    Tries zenity (GNOME/GTK) → kdialog (KDE) → tkinter as fallback.
    Returns the chosen path string, or None if cancelled / unavailable.
    """
    # 1. zenity (most common on Ubuntu / GNOME)
    try:
        result = subprocess.run(
            ["zenity", "--file-selection", "--directory",
             "--title=Select invoice folder"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. kdialog (KDE Plasma)
    try:
        result = subprocess.run(
            ["kdialog", "--getexistingdirectory", str(Path.home()),
             "--title", "Select invoice folder"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 3. tkinter (fallback — always available on most Python installs)
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()          # hide the empty Tk window
        root.attributes("-topmost", True)
        chosen = filedialog.askdirectory(
            title="Select invoice folder",
            initialdir=str(Path.home()),
        )
        root.destroy()
        return chosen or None
    except Exception:
        pass

    return None

# ── App display helpers (shared with upload.py) ────────────────────────────────
APP_DISPLAY = {
    "zepto":     ("⚡ Zepto",      "#8b5cf6"),
    "blinkit":   ("💛 Blinkit",    "#f59e0b"),
    "instamart": ("🟠 Instamart",  "#f97316"),
    "bigbasket": ("🟢 BigBasket",  "#22c55e"),
    "jiomart":   ("🔵 JioMart",    "#3b82f6"),
    "swiggy":    ("🍊 Swiggy",     "#ea580c"),
    "zomato":    ("🔴 Zomato",     "#ef4444"),
}

ITEM_CATEGORIES = [
    "Fruits & Vegetables", "Dairy & Eggs", "Grains & Pulses",
    "Snacks", "Beverages", "Personal Care", "Household",
    "Meat & Seafood", "Bakery", "Spices & Condiments",
    "Ready to Eat", "Restaurant Food", "Other",
]


def _init_bulk_state():
    defaults = {
        "bulk_folder":       "",
        "bulk_app":          None,
        "bulk_auto_detect":  True,
        "bulk_recursive":    False,
        "bulk_running":      False,
        "bulk_cancel":       False,
        "bulk_results":      [],
        "bulk_log":          [],
        "bulk_status":       "idle",
        "bulk_auto_save":    True,
        "bulk_review_queue": [],
        "bulk_scan_result":  None,   # cached scan (done/pending split)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Main render ────────────────────────────────────────────────────────────────

def render_bulk():
    _init_bulk_state()

    st.markdown("## 📂 Bulk Import")
    st.markdown(
        "Point to a folder of PDFs / screenshots and let the AI process them "
        "one by one — fully automatic, with smart key rotation and rate-limit handling."
    )

    # ── API key status banner ──────────────────────────────────────────────────
    _render_key_status_banner()

    st.divider()

    # ════════════════════════════════════════════════════════════════════════════
    # Configuration panel
    # ════════════════════════════════════════════════════════════════════════════
    with st.expander("⚙️ Configuration", expanded=True):
        # ── Folder path ────────────────────────────────────────────────────────
        # "Browse" button opens the native OS folder picker
        browse_col, input_col = st.columns([1, 5])
        with browse_col:
            st.markdown("<br>", unsafe_allow_html=True)  # vertical align
            if st.button("📁 Browse…", width="stretch", key="bulk_browse_btn"):
                chosen = _pick_folder()
                if chosen:
                    st.session_state.bulk_folder = chosen
                    st.rerun()

        with input_col:
            folder_input = st.text_input(
                "📁 Folder path",
                value=st.session_state.bulk_folder,
                placeholder="/home/you/invoices/zepto  — or click Browse above",
                help="Absolute path to the folder containing your invoice files.",
                key="bulk_folder_input",
            )
            st.session_state.bulk_folder = folder_input.strip()

        # Validate path live
        folder_path = Path(st.session_state.bulk_folder)
        folder_valid = folder_path.is_dir() if st.session_state.bulk_folder else False

        if st.session_state.bulk_folder and not folder_valid:
            st.warning("⚠️ Path does not exist or is not a directory.")
        elif folder_valid:
            # Count files
            exts = ALL_EXTS
            found = [
                p for p in folder_path.iterdir()
                if p.is_file() and p.suffix.lower() in exts
            ]
            st.success(
                f"✅ Found **{len(found)}** processable file(s) in that folder "
                f"({', '.join(sorted({p.suffix.lower() for p in found})) or 'none'})."
            )
            # Folder scan (zero API calls)
            _render_folder_scan(folder_path)

        # ── App selector / auto-detect ────────────────────────────────────────
        st.session_state.bulk_auto_detect = st.checkbox(
            "🤖 Auto-detect the app for each file",
            value=st.session_state.bulk_auto_detect,
            help="Detects the seller per file (no extra API cost). Turn OFF to "
                 "force a single app for the whole folder.",
        )

        if st.session_state.bulk_auto_detect:
            st.info(
                "🤖 Auto-detect is ON — you can point at a folder containing "
                "multiple sellers (e.g. the `invoice/` root). Sub-folders are "
                "scanned automatically."
            )
            st.session_state.bulk_recursive = True
            st.session_state.bulk_app = None
        else:
            st.markdown("**Select the delivery app for this folder:**")
            cols = st.columns(len(APP_DISPLAY))
            for i, (app_key, (label, color)) in enumerate(APP_DISPLAY.items()):
                with cols[i]:
                    is_active = st.session_state.bulk_app == app_key
                    if st.button(
                        label,
                        key=f"bulk_app_{app_key}",
                        width="stretch",
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state.bulk_app = app_key
                        st.rerun()

            if st.session_state.bulk_app:
                label, color = APP_DISPLAY[st.session_state.bulk_app]
                st.markdown(
                    f'<div style="background:{color}22; border-left:4px solid {color}; '
                    f'padding:0.4rem 1rem; border-radius:6px; margin:0.4rem 0;">'
                    f'Selected: <strong>{label}</strong> — '
                    f'<em>{APP_CATEGORIES[st.session_state.bulk_app].title()}</em></div>',
                    unsafe_allow_html=True,
                )

        # ── Options ────────────────────────────────────────────────────────────
        col_a, col_b = st.columns(2)
        with col_a:
            st.session_state.bulk_recursive = st.checkbox(
                "🔁 Include sub-folders recursively",
                value=st.session_state.bulk_recursive,
                disabled=st.session_state.bulk_auto_detect,
                help="Forced ON when auto-detect is enabled (multi-seller folders).",
            )
        with col_b:
            st.session_state.bulk_auto_save = st.checkbox(
                "💾 Auto-save successfully parsed orders",
                value=st.session_state.bulk_auto_save,
                help="When ON, orders are saved to the database without a review step. "
                     "Turn OFF to review each one first.",
            )

    # ════════════════════════════════════════════════════════════════════════════
    # Start / Cancel controls
    # ════════════════════════════════════════════════════════════════════════════
    st.divider()

    app_known = st.session_state.bulk_app is not None or st.session_state.bulk_auto_detect
    can_start = (
        folder_valid
        and app_known
        and st.session_state.bulk_status not in ("running",)
    )

    col_start, col_cancel, col_reset = st.columns([2, 1, 1])

    with col_start:
        if st.button(
            "🚀 Start Bulk Import",
            disabled=not can_start,
            type="primary",
            width="stretch",
            key="bulk_start_btn",
        ):
            st.session_state.bulk_results    = []
            st.session_state.bulk_log        = []
            st.session_state.bulk_status     = "running"
            st.session_state.bulk_cancel     = False
            st.session_state.bulk_review_queue = []
            st.rerun()

    with col_cancel:
        if st.button(
            "🛑 Cancel",
            disabled=st.session_state.bulk_status != "running",
            width="stretch",
            key="bulk_cancel_btn",
        ):
            st.session_state.bulk_cancel = True
            st.session_state.bulk_status = "cancelled"

    with col_reset:
        if st.button("🔄 Reset", width="stretch", key="bulk_reset_btn"):
            for k in ("bulk_results", "bulk_log", "bulk_review_queue"):
                st.session_state[k] = []
            st.session_state.bulk_status      = "idle"
            st.session_state.bulk_cancel      = False
            st.session_state.bulk_scan_result = None
            st.rerun()

    # ════════════════════════════════════════════════════════════════════════════
    # Processing loop (runs while status == "running")
    # ════════════════════════════════════════════════════════════════════════════
    if st.session_state.bulk_status == "running":
        _run_bulk_processing()

    # ════════════════════════════════════════════════════════════════════════════
    # Results panel
    # ════════════════════════════════════════════════════════════════════════════
    if st.session_state.bulk_results or st.session_state.bulk_log:
        _render_results()

    # Daily run logs
    _render_run_logs()

    # ════════════════════════════════════════════════════════════════════════════
    # Manual review queue (when auto-save is OFF)
    # ════════════════════════════════════════════════════════════════════════════
    if st.session_state.bulk_review_queue:
        _render_review_queue()


# ── Key status banner ─────────────────────────────────────────────────────────

def _render_key_status_banner():
    try:
        pool = ApiKeyPool()
        usage = pool.all_usage()
        cols  = st.columns(max(len(usage), 1))
        for col, u in zip(cols, usage):
            exhausted = u["exhausted"]
            active    = u["active"]
            color     = "#ef4444" if exhausted else ("#22c55e" if active else "#64748b")
            icon      = "🚫" if exhausted else ("⚡" if active else "💤")
            col.markdown(
                f'<div style="border:1px solid {color}44;border-radius:8px;padding:0.5rem;'
                f'background:{color}11;text-align:center;">'  
                f'<div style="font-size:0.7rem;color:#94a3b8;">Key #{u["index"]} (…{u["suffix"]})</div>'
                f'<div style="font-size:1.1rem;font-weight:700;color:{color};">{u["count"]}/{DAILY_LIMIT} {icon}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.caption("🔑 API key daily usage — rotates automatically when a key is exhausted. Resets at midnight UTC.")
    except Exception:
        st.info(f"ℹ️ Add API keys in ⚙️ Settings to enable key rotation.", icon="🔑")


# ── Folder scan (no API calls) ─────────────────────────────────────────────────

def _render_folder_scan(folder_path: Path):
    """Show done/pending split purely from the local processed_files.json — zero API calls."""
    with st.expander("🔍 Folder Scan — see which files are done vs pending", expanded=False):
        if st.button("🔄 Scan Folder", key="bulk_scan_btn"):
            try:
                sdk = BulkProcessor(folder_path=folder_path, app_name="zepto")  # app_name irrelevant here
                st.session_state.bulk_scan_result = sdk.scan_folder()
            except Exception as e:
                st.error(f"Scan failed: {e}")

        scan = st.session_state.bulk_scan_result
        if scan:
            done    = scan["done"]
            pending = scan["pending"]
            total   = scan["total"]

            dc, pc = st.columns(2)
            dc.metric("✅ Done (skip API)", len(done))
            pc.metric("⏳ Pending (need API)", len(pending))

            if done:
                with st.expander(f"✅ {len(done)} already processed"):
                    for p in done:
                        st.markdown(f"- `{p.name}`")
            if pending:
                with st.expander(f"⏳ {len(pending)} pending"):
                    for p in pending:
                        st.markdown(f"- `{p.name}`")
        else:
            st.caption("Click Scan Folder to check without making any API requests.")


# ── Daily run logs ─────────────────────────────────────────────────────────────

def _render_run_logs():
    logs = RunLogger.list_logs()
    if not logs:
        return
    with st.expander(f"📜 Daily Run Logs ({len(logs)} run(s))", expanded=False):
        selected = st.selectbox(
            "Select run",
            options=logs,
            format_func=lambda p: p.stem.replace("_", " "),
            key="bulk_log_select",
        )
        if selected:
            st.code(selected.read_text(encoding="utf-8"), language=None)


# ── Processing engine ──────────────────────────────────────────────────────────

def _run_bulk_processing():
    """Run the BulkProcessor and stream results to session state."""
    folder    = Path(st.session_state.bulk_folder)
    app_name  = None if st.session_state.bulk_auto_detect else st.session_state.bulk_app
    recursive = st.session_state.bulk_recursive
    auto_save = st.session_state.bulk_auto_save

    try:
        sdk = BulkProcessor(
            folder_path=folder,
            app_name=app_name,
            recursive=recursive,
            on_progress=lambda msg: st.session_state.bulk_log.append(msg),
        )
    except Exception as e:
        st.error(f"❌ {e}")
        st.session_state.bulk_status = "idle"
        return

    try:
        files = sdk.discover_files()
    except Exception as e:
        st.error(f"❌ Cannot read folder: {e}")
        st.session_state.bulk_status = "idle"
        return

    if not files:
        st.warning("⚠️ No processable files found in the selected folder.")
        st.session_state.bulk_status = "idle"
        return

    total = len(files)
    st.markdown(f"### ⚙️ Processing {total} file(s)…")

    progress_bar = st.progress(0, text="Starting…")
    status_box   = st.empty()
    log_box      = st.empty()

    processed = 0

    for result in sdk.process_all(
        stop_flag=lambda: st.session_state.bulk_cancel
    ):
        processed += 1
        frac = processed / total
        fname = result.file_path.name

        if result.skipped:
            msg = f"⏭️ Skipped (already imported): {fname}"
        elif result.success:
            msg = f"✅ Parsed: {fname}"
            if auto_save and result.data:
                _auto_save_result(result)
            else:
                st.session_state.bulk_review_queue.append(result)
        else:
            msg = f"❌ Failed: {fname} — {result.error}"

        st.session_state.bulk_results.append(result)
        st.session_state.bulk_log.append(msg)

        progress_bar.progress(frac, text=f"{processed}/{total} — {fname}")
        status_box.markdown(f"**{msg}**")

        # Render recent log lines
        recent = st.session_state.bulk_log[-8:]
        log_box.markdown(
            "<div style='font-size:0.8rem; color:#94a3b8; font-family:monospace;"
            "background:#0f172a; padding:0.6rem; border-radius:6px; "
            "max-height:160px; overflow-y:auto;'>"
            + "<br>".join(recent)
            + "</div>",
            unsafe_allow_html=True,
        )

        if st.session_state.bulk_cancel:
            break

    if st.session_state.bulk_cancel:
        st.session_state.bulk_status = "cancelled"
        st.warning("🛑 Import cancelled.")
    else:
        st.session_state.bulk_status = "done"
        st.success(
            f"🎉 Done! {sum(r.success and not r.skipped for r in st.session_state.bulk_results)} "
            f"parsed, {sum(r.skipped for r in st.session_state.bulk_results)} skipped, "
            f"{sum(not r.success and not r.skipped for r in st.session_state.bulk_results)} failed."
        )

    progress_bar.empty()


def _auto_save_result(result):
    """Save a successfully parsed result directly to the DB."""
    data     = result.data
    app_name = result.app_name
    fname    = result.file_path.name
    cat      = APP_CATEGORIES.get(app_name, "other")

    try:
        _, was_dup = insert_order(
            order_date   = data.get("order_date") or str(datetime.date.today()),
            app_name     = app_name,
            app_category = cat,
            order_id     = data.get("order_id") or "",
            total_amount = float(data.get("total_amount") or 0),
            delivery_fee = float(data.get("delivery_fee") or 0),
            discount     = float(data.get("discount") or 0),
            notes        = f"[bulk import] {fname}",
            items        = data.get("items") or [],
        )
        if was_dup:
            st.session_state.bulk_log.append(
                f"⚠️ Duplicate skipped (same order ID + same items): {fname}"
            )
    except Exception as e:
        st.session_state.bulk_log.append(
            f"⚠️ DB save failed for {fname}: {e}"
        )


# ── Results summary panel ──────────────────────────────────────────────────────

def _render_results():
    results = st.session_state.bulk_results
    if not results:
        return

    st.divider()
    st.markdown("### 📊 Batch Results")

    total   = len(results)
    success = sum(r.success and not r.skipped for r in results)
    skipped = sum(r.skipped for r in results)
    failed  = sum(not r.success and not r.skipped for r in results)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Files",  total)
    c2.metric("✅ Parsed",    success)
    c3.metric("⏭️ Skipped",   skipped)
    c4.metric("❌ Failed",    failed)

    if failed:
        with st.expander("❌ Failed files"):
            for r in results:
                if not r.success and not r.skipped:
                    st.error(f"**{r.file_path.name}** — {r.error}")

    with st.expander("📋 Full log"):
        log_text = "\n".join(st.session_state.bulk_log)
        st.code(log_text, language=None)


# ── Manual review queue ────────────────────────────────────────────────────────

def _render_review_queue():
    queue = st.session_state.bulk_review_queue
    if not queue:
        return

    st.divider()
    st.markdown(f"### 🔍 Review Queue — {len(queue)} order(s) pending")
    st.caption("Review each parsed order, edit if needed, then save or discard.")

    to_remove = []

    for idx, result in enumerate(queue):
        data  = result.data or {}
        fname = result.file_path.name
        app   = result.app_name
        label, color = APP_DISPLAY.get(app, (app.title(), "#6366f1"))

        with st.expander(
            f"🧾 {fname}  ·  {label}  ·  ₹{data.get('total_amount', '?')}",
            expanded=(idx == 0),
        ):
            with st.form(key=f"review_form_{idx}"):
                rc1, rc2, rc3 = st.columns(3)
                with rc1:
                    date_val = _safe_date(data.get("order_date"))
                    order_date = st.date_input("Order Date", value=date_val,
                                               key=f"rq_date_{idx}")
                with rc2:
                    order_id_val = st.text_input("Order ID",
                                                 value=data.get("order_id") or "",
                                                 key=f"rq_oid_{idx}")
                with rc3:
                    cat = APP_CATEGORIES.get(app, "other")
                    st.text_input("Category", value=cat.title(), disabled=True,
                                  key=f"rq_cat_{idx}")

                rc4, rc5, rc6 = st.columns(3)
                with rc4:
                    total_amount = st.number_input(
                        "Total Paid (₹)",
                        value=float(data.get("total_amount") or 0),
                        min_value=0.0, step=0.5, key=f"rq_total_{idx}"
                    )
                with rc5:
                    delivery_fee = st.number_input(
                        "Delivery Fee (₹)",
                        value=float(data.get("delivery_fee") or 0),
                        min_value=0.0, step=0.5, key=f"rq_df_{idx}"
                    )
                with rc6:
                    discount = st.number_input(
                        "Discount (₹)",
                        value=float(data.get("discount") or 0),
                        min_value=0.0, step=0.5, key=f"rq_disc_{idx}"
                    )

                notes = st.text_area("Notes", value=f"[bulk import] {fname}",
                                     height=50, key=f"rq_notes_{idx}")

                # Items (collapsed by default)
                st.markdown("**Items**")
                items = data.get("items", [])
                edited_items = []
                for iidx, item in enumerate(items):
                    with st.expander(
                        f"  {item.get('name', f'Item {iidx+1}')} — ₹{item.get('total_price', 0)}",
                        expanded=False,
                    ):
                        ia, ib, ic = st.columns(3)
                        with ia:
                            i_name = st.text_input("Name", value=item.get("name", ""),
                                                   key=f"rq_n_{idx}_{iidx}")
                        with ib:
                            i_qty = st.text_input("Qty", value=item.get("quantity", ""),
                                                  key=f"rq_q_{idx}_{iidx}")
                        with ic:
                            i_total = st.number_input(
                                "Price (₹)", value=float(item.get("total_price", 0) or 0),
                                min_value=0.0, key=f"rq_tp_{idx}_{iidx}"
                            )
                        edited_items.append({
                            "name":        i_name,
                            "brand":       item.get("brand", ""),
                            "category":    item.get("category", "Other"),
                            "quantity":    i_qty,
                            "unit_price":  float(item.get("unit_price", 0) or 0),
                            "total_price": i_total,
                        })

                save_col, discard_col = st.columns(2)
                save_btn    = save_col.form_submit_button(
                    "💾 Save", type="primary", width="stretch")
                discard_btn = discard_col.form_submit_button(
                    "🗑️ Discard", width="stretch")

                if save_btn:
                    try:
                        _, was_dup = insert_order(
                            order_date   = str(order_date),
                            app_name     = app,
                            app_category = cat,
                            order_id     = order_id_val,
                            total_amount = total_amount,
                            delivery_fee = delivery_fee,
                            discount     = discount,
                            notes        = notes,
                            items        = edited_items,
                        )
                        if was_dup:
                            st.warning(
                                f"⚠️ **Duplicate detected** for `{fname}` — an order with "
                                "the same Order ID and identical items already exists. "
                                "Edit item names above if these are genuinely different items."
                            )
                        else:
                            st.success(f"✅ Saved: {fname}")
                            to_remove.append(idx)
                    except Exception as e:
                        st.error(f"❌ Save failed: {e}")

                if discard_btn:
                    st.info(f"🗑️ Discarded: {fname}")
                    to_remove.append(idx)

    # Remove processed entries (in reverse to preserve indices)
    for idx in sorted(set(to_remove), reverse=True):
        try:
            st.session_state.bulk_review_queue.pop(idx)
        except IndexError:
            pass

    if to_remove:
        st.rerun()


def _safe_date(date_str: str | None) -> datetime.date:
    if not date_str:
        return datetime.date.today()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except Exception:
            pass
    return datetime.date.today()
