"""views/history.py — Browsable, searchable, editable order history."""

import streamlit as st
import pandas as pd
from database import get_orders_df, get_items_df, get_order_items, delete_order, update_order_and_items

APP_ICONS = {
    "zepto": "⚡", "blinkit": "💛", "instamart": "🟠",
    "bigbasket": "🟢", "jiomart": "🔵", "swiggy": "🍊", "zomato": "🔴",
}

ITEM_CATEGORIES = [
    "Fruits & Vegetables", "Dairy & Eggs", "Grains & Pulses",
    "Snacks", "Beverages", "Personal Care", "Household",
    "Meat & Seafood", "Bakery", "Spices & Condiments",
    "Ready to Eat", "Restaurant Food", "Other",
]


def render_history():
    st.markdown("## 📋 Order History")

    orders_df = get_orders_df()
    if orders_df.empty:
        st.info("No orders yet. Upload your first receipt!")
        return

    orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])

    # ── Filters ───────────────────────────────────────────────────────────────
    with st.expander("🔍 Filter & Search", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            apps = ["All"] + sorted(orders_df["app_name"].unique().tolist())
            sel_app = st.selectbox("App", apps)
        with fc2:
            cats = ["All"] + sorted(orders_df["app_category"].unique().tolist())
            sel_cat = st.selectbox("Category", cats)
        with fc3:
            date_range = st.date_input(
                "Date range",
                value=(orders_df["order_date"].min().date(), orders_df["order_date"].max().date()),
            )

    filtered = orders_df.copy()
    if sel_app != "All":
        filtered = filtered[filtered["app_name"] == sel_app]
    if sel_cat != "All":
        filtered = filtered[filtered["app_category"] == sel_cat]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered["order_date"].dt.date >= start) &
            (filtered["order_date"].dt.date <= end)
        ]

    st.markdown(f"**{len(filtered)} order(s) found**")

    # ── Order list ────────────────────────────────────────────────────────────
    for _, row in filtered.iterrows():
        icon = APP_ICONS.get(row["app_name"], "🛒")
        with st.expander(
            f"{icon} **{row['app_name'].title()}** — "
            f"{row['order_date'].strftime('%d %b %Y')} — "
            f"₹{row['total_amount']:,.2f}",
            expanded=False,
        ):
            items = get_order_items(row["id"])

            # Show items table
            if items:
                items_df = pd.DataFrame(items)
                display_cols = ["name", "brand", "category", "quantity", "total_price"]
                display_cols = [c for c in display_cols if c in items_df.columns]
                items_df_display = items_df[display_cols].copy()
                items_df_display.columns = [c.replace("_", " ").title() for c in display_cols]
                if "Total Price" in items_df_display.columns:
                    items_df_display["Total Price"] = items_df_display["Total Price"].map("₹{:,.2f}".format)
                st.dataframe(items_df_display, width="stretch", hide_index=True)

            # Summary
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Total Paid", f"₹{row['total_amount']:,.2f}")
            sc2.metric("Delivery Fee", f"₹{row['delivery_fee']:,.2f}")
            sc3.metric("Discount", f"₹{row['discount']:,.2f}")

            if row["notes"]:
                st.caption(f"Notes: {row['notes']}")

            # Action buttons
            col_edit, col_del = st.columns([1, 1])
            with col_edit:
                if st.button("✏️ Edit", key=f"edit_{row['id']}"):
                    st.session_state[f"editing_{row['id']}"] = True

            with col_del:
                if st.button("🗑️ Delete", key=f"del_{row['id']}", type="secondary"):
                    st.session_state[f"confirm_del_{row['id']}"] = True

            # Delete confirmation
            if st.session_state.get(f"confirm_del_{row['id']}"):
                st.warning("⚠️ Are you sure? This will delete the order and all its items.")
                cd1, cd2 = st.columns(2)
                with cd1:
                    if st.button("✅ Yes, Delete", key=f"confirm_yes_{row['id']}", type="primary"):
                        delete_order(row["id"])
                        st.session_state.pop(f"confirm_del_{row['id']}", None)
                        st.success("Deleted!")
                        st.rerun()
                with cd2:
                    if st.button("❌ Cancel", key=f"cancel_del_{row['id']}"):
                        st.session_state.pop(f"confirm_del_{row['id']}", None)
                        st.rerun()

            # Edit form
            if st.session_state.get(f"editing_{row['id']}"):
                _render_edit_form(row, items)


def _render_edit_form(row, items: list):
    import datetime
    st.markdown("---")
    st.markdown("#### ✏️ Edit Order")
    with st.form(f"edit_form_{row['id']}"):
        ec1, ec2 = st.columns(2)
        with ec1:
            new_date = st.date_input(
                "Order Date", value=row["order_date"].date()
            )
            new_total = st.number_input(
                "Total Paid (₹)", value=float(row["total_amount"]), min_value=0.0
            )
        with ec2:
            new_order_id = st.text_input("Order ID", value=row["order_id"] or "")
            new_delivery = st.number_input(
                "Delivery Fee (₹)", value=float(row["delivery_fee"]), min_value=0.0
            )
        new_discount = st.number_input(
            "Discount (₹)", value=float(row["discount"]), min_value=0.0
        )
        new_notes = st.text_area("Notes", value=row["notes"] or "")

        st.markdown("##### Items")
        edited_items = []
        for idx, item in enumerate(items):
            ic1, ic2, ic3, ic4, ic5 = st.columns([3, 2, 2, 2, 2])
            with ic1:
                iname = st.text_input("Name", value=item["name"], key=f"en{row['id']}_{idx}")
            with ic2:
                ibrand = st.text_input("Brand", value=item.get("brand",""), key=f"eb{row['id']}_{idx}")
            with ic3:
                iqty = st.text_input("Qty", value=item.get("quantity",""), key=f"eq{row['id']}_{idx}")
            with ic4:
                iup = st.number_input("Unit ₹", value=float(item.get("unit_price",0) or 0), min_value=0.0, key=f"eu{row['id']}_{idx}")
            with ic5:
                itp = st.number_input("Total ₹", value=float(item.get("total_price",0) or 0), min_value=0.0, key=f"et{row['id']}_{idx}")
            cat_val = item.get("category","Other")
            if cat_val not in ITEM_CATEGORIES:
                cat_val = "Other"
            icat = st.selectbox("Category", ITEM_CATEGORIES, index=ITEM_CATEGORIES.index(cat_val), key=f"ec{row['id']}_{idx}")
            edited_items.append({
                "name": iname, "brand": ibrand, "category": icat,
                "quantity": iqty, "unit_price": iup, "total_price": itp,
            })

        save_edit = st.form_submit_button("💾 Save Changes", type="primary")
        cancel_edit = st.form_submit_button("✖ Cancel")

        if save_edit:
            update_order_and_items(
                row["id"],
                {
                    "order_date": str(new_date),
                    "app_name": row["app_name"],
                    "app_category": row["app_category"],
                    "order_id": new_order_id,
                    "total_amount": new_total,
                    "delivery_fee": new_delivery,
                    "discount": new_discount,
                    "notes": new_notes,
                },
                edited_items,
            )
            st.session_state.pop(f"editing_{row['id']}", None)
            st.success("Saved!")
            st.rerun()

        if cancel_edit:
            st.session_state.pop(f"editing_{row['id']}", None)
            st.rerun()
