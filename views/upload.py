"""views/upload.py — File upload + Gemini parsing + review/edit before saving."""

import streamlit as st
import datetime
from parser import parse_mixed, APP_NAMES, APP_CATEGORIES
from database import insert_order


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


def render_upload():
    st.markdown("## 📤 Upload Invoice / Screenshot")
    st.markdown("Upload receipts from any delivery app — screenshots (JPG/PNG) or PDF invoices.")

    # ── Step 1: Auto-detect or pick App ───────────────────────────────────────
    st.markdown("### Step 1 — App")
    auto_detect = st.checkbox(
        "🤖 Auto-detect the app from the invoice",
        value=True,
        help="The app identifies the seller automatically. Turn OFF to pick manually.",
        key="upload_auto_detect",
    )

    chosen_app = st.session_state.get("chosen_app", None)

    if not auto_detect:
        cols = st.columns(len(APP_DISPLAY))
        for i, (app_key, (label, color)) in enumerate(APP_DISPLAY.items()):
            with cols[i]:
                is_active = chosen_app == app_key
                border = f"3px solid {color}" if is_active else "2px solid #334155"
                bg = f"{color}22" if is_active else "transparent"
                if st.button(
                    label,
                    key=f"app_btn_{app_key}",
                    width="stretch",
                    help=f"Select {label}",
                ):
                    st.session_state.chosen_app = app_key
                    st.session_state.parsed_data = None
                    st.rerun()

        if not chosen_app:
            st.info("☝️ Please select an app above to continue.")
            return

        chosen_label, chosen_color = APP_DISPLAY[chosen_app]
        st.markdown(
            f'<div style="background:{chosen_color}22; border-left:4px solid {chosen_color}; '
            f'padding:0.5rem 1rem; border-radius:6px; margin:0.5rem 0;">'
            f'Selected: <strong>{chosen_label}</strong> — '
            f'<em>{APP_CATEGORIES[chosen_app].title()} app</em></div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("🤖 Auto-detect is ON — just upload your file(s) and the app will figure out the seller.")
        # Manual override is reset when auto-detect is on
        st.session_state.chosen_app = None

    # ── Step 2: Upload files ──────────────────────────────────────────────────
    st.markdown("### Step 2 — Upload files")
    st.caption("You can upload multiple screenshots for a single order + optional PDF invoice.")

    uploaded = st.file_uploader(
        "Screenshots (JPG/PNG) and/or PDF invoice",
        type=["jpg", "jpeg", "png", "pdf"],
        accept_multiple_files=True,
        key="file_uploader",
        label_visibility="collapsed",
    )

    if not uploaded:
        st.info("📎 Upload at least one screenshot or PDF to continue.")
        return

    # Show preview thumbnails
    img_files = [f for f in uploaded if f.type.startswith("image")]
    pdf_files = [f for f in uploaded if f.type == "application/pdf"]

    if img_files:
        st.markdown(f"**{len(img_files)} screenshot(s) uploaded:**")
        thumb_cols = st.columns(min(len(img_files), 4))
        for i, img_f in enumerate(img_files):
            with thumb_cols[i % 4]:
                st.image(img_f.read(), width="stretch")
                img_f.seek(0)

    if pdf_files:
        for pdf_f in pdf_files:
            st.success(f"📄 PDF: {pdf_f.name}")

    # ── Step 3: Parse ─────────────────────────────────────────────────────────
    st.markdown("### Step 3 — Parse with AI")

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        st.warning(
            "⚠️ Gemini API key not set. Go to **Settings** to add it, "
            "or add it to `.env` file as `GEMINI_API_KEY=...`"
        )

    parse_clicked = st.button(
        "🤖 Parse with Gemini AI", type="primary", width="stretch"
    )

    if parse_clicked:
        with st.spinner("🔍 Analysing your receipt with Gemini Vision…"):
            try:
                img_bytes_list = [f.read() for f in img_files]
                pdf_bytes_list = [f.read() for f in pdf_files]
                pdf_name = pdf_files[0].name if pdf_files else ""

                data = parse_mixed(img_bytes_list, pdf_bytes_list, chosen_app, pdf_name)
                st.session_state.parsed_data = data
                st.session_state.upload_app = chosen_app or data.get("_detected_app")
                if not chosen_app:
                    det = data.get("_detected_app")
                    if det:
                        st.success(f"✅ Parsed successfully! Detected app: **{det.title()}**. Review and save below.")
                    else:
                        st.warning("✅ Parsed, but the app could not be detected. Pick it manually below.")
                else:
                    st.success("✅ Parsed successfully! Review and save below.")
            except Exception as e:
                st.error(f"❌ Parsing failed: {e}")
                return

    # ── Step 4: Review & Edit ─────────────────────────────────────────────────
    parsed = st.session_state.get("parsed_data")
    if not parsed:
        return

    st.markdown("### Step 4 — Review & Save")
    st.caption("Edit any fields the AI got wrong before saving.")

    with st.form("review_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            order_date = st.date_input(
                "Order Date",
                value=_parse_date(parsed.get("order_date")),
            )
        with c2:
            order_id_val = st.text_input(
                "Order ID", value=parsed.get("order_id") or ""
            )
        with c3:
            # App selector — pre-filled with detected/app, editable to override
            detected_app = st.session_state.get("upload_app")
            app_keys = list(APP_DISPLAY.keys())
            default_idx = (
                app_keys.index(detected_app)
                if detected_app in app_keys else 0
            )
            chosen_app_edit = st.selectbox(
                "App",
                options=app_keys,
                index=default_idx,
                format_func=lambda k: APP_DISPLAY[k][0],
                key="upload_app_override",
            )
            app_category = APP_CATEGORIES.get(chosen_app_edit, "groceries")
            st.text_input("App Category", value=app_category.title(), disabled=True)

        c4, c5, c6 = st.columns(3)
        with c4:
            total_amount = st.number_input(
                "Total Paid (₹)", value=float(parsed.get("total_amount") or 0),
                min_value=0.0, step=0.5
            )
        with c5:
            delivery_fee = st.number_input(
                "Delivery Fee (₹)", value=float(parsed.get("delivery_fee") or 0),
                min_value=0.0, step=0.5
            )
        with c6:
            discount = st.number_input(
                "Discount (₹)", value=float(parsed.get("discount") or 0),
                min_value=0.0, step=0.5
            )

        notes = st.text_area("Notes (optional)", height=60)

        # Items table
        st.markdown("#### Items")
        items = parsed.get("items", [])

        edited_items = []
        for idx, item in enumerate(items):
            with st.expander(
                f"🛍️ {item.get('name', f'Item {idx+1}')}  —  ₹{item.get('total_price', 0)}",
                expanded=True,
            ):
                ic1, ic2, ic3 = st.columns(3)
                with ic1:
                    i_name = st.text_input("Name", value=item.get("name", ""), key=f"n{idx}")
                    i_brand = st.text_input("Brand", value=item.get("brand", ""), key=f"b{idx}")
                with ic2:
                    i_qty = st.text_input("Quantity", value=item.get("quantity", ""), key=f"q{idx}")
                    cat_default = item.get("category", "Other")
                    if cat_default not in ITEM_CATEGORIES:
                        cat_default = "Other"
                    i_cat = st.selectbox(
                        "Category", ITEM_CATEGORIES,
                        index=ITEM_CATEGORIES.index(cat_default),
                        key=f"c{idx}"
                    )
                with ic3:
                    i_unit = st.number_input(
                        "Unit Price (₹)", value=float(item.get("unit_price", 0) or 0),
                        min_value=0.0, key=f"u{idx}"
                    )
                    i_total = st.number_input(
                        "Total Price (₹)", value=float(item.get("total_price", 0) or 0),
                        min_value=0.0, key=f"t{idx}"
                    )
                edited_items.append({
                    "name": i_name, "brand": i_brand, "category": i_cat,
                    "quantity": i_qty, "unit_price": i_unit, "total_price": i_total,
                })

        save_btn = st.form_submit_button(
            "💾 Save Order", type="primary", width="stretch"
        )
        if save_btn:
            _, was_dup = insert_order(
                order_date=str(order_date),
                app_name=chosen_app_edit,
                app_category=app_category,
                order_id=order_id_val,
                total_amount=total_amount,
                delivery_fee=delivery_fee,
                discount=discount,
                notes=notes,
                items=edited_items,
            )
            if was_dup:
                st.warning(
                    "⚠️ **Duplicate detected** — an order with the same Order ID "
                    "and identical items already exists in the database. "
                    "Nothing was saved. If these are different items, "
                    "edit the item names above and try again."
                )
            else:
                # Clear parsed data and uploaded files
                st.session_state.parsed_data = None
                st.session_state.chosen_app = None
                st.success("✅ Order saved! Go to Dashboard or History to view it.")
                st.balloons()


def _parse_date(date_str):
    """Try to parse date string, fall back to today."""
    if not date_str:
        return datetime.date.today()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except Exception:
            pass
    return datetime.date.today()


import os  # noqa — needed inside function scope
