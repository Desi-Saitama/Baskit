"""views/dashboard.py — Comprehensive analytics dashboard."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta

from database import get_orders_df, get_items_df
from normalizer import apply_normalization, init_normalizer_tables

init_normalizer_tables()

# ── Brand colours ──────────────────────────────────────────────────────────────
APP_COLORS = {
    "zepto":     "#8b5cf6",
    "blinkit":   "#f59e0b",
    "instamart": "#f97316",
    "bigbasket": "#22c55e",
    "jiomart":   "#3b82f6",
    "swiggy":    "#ea580c",
    "zomato":    "#ef4444",
}
APP_ICONS = {
    "zepto": "⚡", "blinkit": "💛", "instamart": "🟠",
    "bigbasket": "🟢", "jiomart": "🔵", "swiggy": "🍊", "zomato": "🔴",
}
CATEGORY_COLORS = {
    "Fruits & Vegetables": "#22c55e",
    "Dairy & Eggs":        "#f59e0b",
    "Grains & Pulses":     "#f97316",
    "Snacks":              "#ec4899",
    "Beverages":           "#3b82f6",
    "Personal Care":       "#8b5cf6",
    "Household":           "#64748b",
    "Bakery":              "#d97706",
    "Spices & Condiments": "#ef4444",
    "Ready to Eat":        "#06b6d4",
    "Restaurant Food":     "#e11d48",
    "Other":               "#94a3b8",
    "Meat & Seafood":      "#dc2626",
}

PERIOD_OPTIONS = ["Daily (last 30 days)", "Weekly (last 12 weeks)", "Monthly (last 12 months)"]

_CARD = """
<div style="
    background: linear-gradient(135deg,{bg1},{bg2});
    border-radius:14px; padding:1.1rem 1rem;
    border:1px solid {border};
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    text-align:center; height:100%;
">
    <div style="font-size:1.8rem; margin-bottom:0.2rem;">{icon}</div>
    <div style="font-size:1.5rem; font-weight:800; color:{color}; letter-spacing:-0.5px;">{value}</div>
    <div style="font-size:0.7rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px; margin-top:0.2rem;">{label}</div>
    {sub}
</div>
"""


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render_dashboard():
    st.markdown("## 📊 Dashboard")

    orders_df = get_orders_df()
    items_df  = get_items_df()

    if orders_df.empty:
        st.info("📭 No orders yet. Go to **Upload** to add your first receipt!")
        _render_empty_placeholder()
        return

    orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])
    if not items_df.empty:
        items_df["order_date"] = pd.to_datetime(items_df["order_date"])
        items_df = apply_normalization(items_df)  # dedupe names + fix categories

    # ── KPI row ───────────────────────────────────────────────────────────────
    _render_kpis(orders_df)
    st.divider()

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_overview, tab_apps, tab_items, tab_savings = st.tabs([
        "📈 Spending Overview",
        "📱 App-wise Analysis",
        "🛍️ Item Intelligence",
        "💡 Savings & Insights",
    ])

    with tab_overview:
        _render_overview(orders_df, items_df)

    with tab_apps:
        _render_app_analysis(orders_df, items_df)

    with tab_items:
        _render_item_intelligence(items_df)

    with tab_savings:
        _render_savings_insights(orders_df, items_df)


# ══════════════════════════════════════════════════════════════════════════════
#  KPI SECTION
# ══════════════════════════════════════════════════════════════════════════════

def _render_kpis(orders_df: pd.DataFrame):
    today       = pd.Timestamp(date.today())
    week_start  = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    day_spend    = orders_df[orders_df["order_date"].dt.date == today.date()]["total_amount"].sum()
    week_spend   = orders_df[orders_df["order_date"] >= week_start]["total_amount"].sum()
    month_spend  = orders_df[orders_df["order_date"] >= month_start]["total_amount"].sum()
    total_spend  = orders_df["total_amount"].sum()
    total_saved  = orders_df["discount"].sum()
    total_orders = len(orders_df)
    avg_order    = total_spend / total_orders if total_orders else 0
    delivery_fee = orders_df["delivery_fee"].sum()

    cols = st.columns(8)
    _kpi(cols[0], "Today",        f"₹{day_spend:,.0f}",    "🗓️", "#6366f1", "#1e1b4b", "#312e81", "#3730a3")
    _kpi(cols[1], "This Week",    f"₹{week_spend:,.0f}",   "📅", "#8b5cf6", "#1e1b4b", "#2e1065", "#4c1d95")
    _kpi(cols[2], "This Month",   f"₹{month_spend:,.0f}",  "📆", "#a78bfa", "#1e1b4b", "#2e1065", "#4c1d95")
    _kpi(cols[3], "All Time",     f"₹{total_spend:,.0f}",  "💰", "#f59e0b", "#1c1408", "#292524", "#1c1917")
    _kpi(cols[4], "Total Saved",  f"₹{total_saved:,.0f}",  "🏷️", "#22c55e", "#052e16", "#052e16", "#14532d")
    _kpi(cols[5], "Total Orders", f"{total_orders}",        "📦", "#3b82f6", "#0c1a2e", "#1e3a5f", "#1e3a8a")
    _kpi(cols[6], "Avg Order",    f"₹{avg_order:,.0f}",    "📊", "#ec4899", "#1a0a12", "#3b0a1f", "#500724")
    _kpi(cols[7], "Delivery Fees",f"₹{delivery_fee:,.0f}", "🛵", "#ef4444", "#1a0505", "#3b0b0b", "#7f1d1d")


def _kpi(col, label, value, icon, color, bg1, bg2, border_color):
    with col:
        st.markdown(
            _CARD.format(
                icon=icon, value=value, label=label,
                color=color, bg1=bg1, bg2=bg2, border=border_color,
                sub="",
            ),
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

def _render_overview(orders_df: pd.DataFrame, items_df: pd.DataFrame):
    # Period selector
    col_p, _ = st.columns([2, 5])
    with col_p:
        period = st.selectbox("Period", PERIOD_OPTIONS, key="ov_period", label_visibility="collapsed")

    ts_df = _build_timeseries(orders_df, period)

    # Line + bar combo
    fig_ts = go.Figure()
    fig_ts.add_trace(go.Bar(
        x=ts_df["period"], y=ts_df["total_amount"],
        name="Spent", marker_color="#6366f1",
        opacity=0.85,
    ))
    fig_ts.add_trace(go.Scatter(
        x=ts_df["period"], y=ts_df["total_amount"].rolling(3, min_periods=1).mean(),
        name="3-period avg", line=dict(color="#f59e0b", width=2.5, dash="dot"),
        mode="lines",
    ))
    fig_ts.update_layout(
        title="Spending Over Time",
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=50, b=20, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="Amount (₹)",
        hovermode="x unified",
    )
    st.plotly_chart(fig_ts, width="stretch")

    # Food vs Groceries + Category breakdown side by side
    col_split, col_cat = st.columns(2)

    with col_split:
        cat_type = orders_df.groupby("app_category")["total_amount"].sum().reset_index()
        fig_split = px.pie(
            cat_type, names="app_category", values="total_amount",
            color_discrete_sequence=["#6366f1", "#22c55e", "#f59e0b"],
            hole=0.52, template="plotly_dark",
        )
        fig_split.update_traces(
            textposition="inside", textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>₹%{value:,.0f} (%{percent})<extra></extra>",
        )
        fig_split.update_layout(
            title="🍕 Food vs 🛒 Groceries",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=50, b=10, l=0, r=0), showlegend=True,
        )
        st.plotly_chart(fig_split, width="stretch")

    with col_cat:
        if not items_df.empty:
            cat_df = (
                items_df.groupby("category")["total_price"].sum()
                .reset_index().sort_values("total_price", ascending=True)
            )
            cat_df["color"] = cat_df["category"].map(CATEGORY_COLORS).fillna("#64748b")
            fig_cat = go.Figure(go.Bar(
                x=cat_df["total_price"], y=cat_df["category"],
                orientation="h",
                marker=dict(color=cat_df["color"], opacity=0.9),
                text=cat_df["total_price"].map("₹{:,.0f}".format),
                textposition="auto",
            ))
            fig_cat.update_layout(
                title="Spend by Category",
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=50, b=10, l=0, r=0),
                xaxis_title="Amount (₹)", yaxis_title="",
                hovermode="y unified",
            )
            st.plotly_chart(fig_cat, width="stretch")

    # Daily cadence heatmap
    _render_order_calendar(orders_df)


def _render_order_calendar(orders_df: pd.DataFrame):
    """Spending calendar — last 30 days grid."""
    st.markdown("#### 📅 Daily Spending Calendar (Last 30 Days)")
    today  = pd.Timestamp(date.today())
    cutoff = today - timedelta(days=29)
    df     = orders_df[orders_df["order_date"] >= cutoff].copy()
    df["day"] = df["order_date"].dt.date

    day_totals = df.groupby("day")["total_amount"].sum().reset_index()
    day_totals["day"] = pd.to_datetime(day_totals["day"])
    day_totals["week"] = day_totals["day"].dt.isocalendar().week.astype(str)
    day_totals["weekday"] = day_totals["day"].dt.day_name()
    day_totals["label"] = day_totals["day"].dt.strftime("%b %d")

    fig_cal = px.density_heatmap(
        day_totals, x="label", y="weekday", z="total_amount",
        color_continuous_scale="Purples",
        template="plotly_dark",
    ) if not day_totals.empty else None

    if fig_cal:
        fig_cal.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=0, r=0),
            xaxis_title="", yaxis_title="", coloraxis_colorbar_title="₹",
        )
        st.plotly_chart(fig_cal, width="stretch")
    else:
        st.info("No spending data in the last 30 days.")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — APP-WISE
# ══════════════════════════════════════════════════════════════════════════════

def _render_app_analysis(orders_df: pd.DataFrame, items_df: pd.DataFrame):
    app_summary = (
        orders_df.groupby("app_name")
        .agg(
            orders      =("id",            "count"),
            total_spent =("total_amount",  "sum"),
            total_saved =("discount",      "sum"),
            delivery_fee=("delivery_fee",  "sum"),
            avg_order   =("total_amount",  "mean"),
        )
        .reset_index()
        .sort_values("total_spent", ascending=False)
    )
    app_summary["effective_rate"] = (
        app_summary["total_saved"] / (app_summary["total_spent"] + app_summary["total_saved"]) * 100
    ).fillna(0)

    # App metric cards
    st.markdown("#### 📱 App Summary")
    for _, row in app_summary.iterrows():
        app  = row["app_name"]
        icon = APP_ICONS.get(app, "🛒")
        col  = APP_COLORS.get(app, "#64748b")
        c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 2, 2, 2, 2])
        with c1:
            st.markdown(
                f"""<div style="background:#1e293b;border-radius:10px;padding:0.8rem 1rem;
                    border-left:4px solid {col}; margin-bottom:0.5rem;">
                    <span style="font-size:1.4rem;">{icon}</span>
                    <span style="font-size:1.1rem;font-weight:700;color:{col};margin-left:0.5rem;">
                    {app.title()}</span></div>""",
                unsafe_allow_html=True,
            )
        c2.metric("Orders",       f"{int(row['orders'])}")
        c3.metric("Total Spent",  f"₹{row['total_spent']:,.0f}")
        c4.metric("Total Saved",  f"₹{row['total_saved']:,.0f}")
        c5.metric("Avg Order",    f"₹{row['avg_order']:,.0f}")
        c6.metric("Discount Rate",f"{row['effective_rate']:.1f}%")

    st.divider()

    # Charts row
    col_bar, col_donut = st.columns(2)

    with col_bar:
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            name="Total Spent",
            x=app_summary["app_name"],
            y=app_summary["total_spent"],
            marker_color=[APP_COLORS.get(a, "#64748b") for a in app_summary["app_name"]],
            text=app_summary["total_spent"].map("₹{:,.0f}".format),
            textposition="outside",
        ))
        fig_comp.add_trace(go.Bar(
            name="Delivery Fees",
            x=app_summary["app_name"],
            y=app_summary["delivery_fee"],
            marker_color="#ef4444", opacity=0.6,
        ))
        fig_comp.update_layout(
            title="Spend vs Delivery Fees by App",
            barmode="group", template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=50, b=10, l=0, r=0),
        )
        st.plotly_chart(fig_comp, width="stretch")

    with col_donut:
        fig_donut = px.pie(
            app_summary, names="app_name", values="total_spent",
            color="app_name", color_discrete_map=APP_COLORS,
            hole=0.55, template="plotly_dark",
        )
        fig_donut.update_traces(
            textposition="inside", textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<extra></extra>",
        )
        fig_donut.update_layout(
            title="Spend Share by App",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=50, b=10, l=0, r=0),
        )
        st.plotly_chart(fig_donut, width="stretch")

    # Savings bar
    fig_save = px.bar(
        app_summary.sort_values("total_saved", ascending=False),
        x="app_name", y=["total_saved", "delivery_fee"],
        barmode="group",
        color_discrete_map={"total_saved": "#22c55e", "delivery_fee": "#ef4444"},
        labels={"value": "Amount (₹)", "app_name": "App", "variable": ""},
        template="plotly_dark",
        text_auto=".0f",
    )
    fig_save.update_layout(
        title="💚 Savings vs 🔴 Delivery Fees — by App",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=50, b=10, l=0, r=0),
    )
    st.plotly_chart(fig_save, width="stretch")

    # App ordering frequency over time
    if not items_df.empty:
        st.markdown("#### 📦 Items per App")
        app_item_df = (
            items_df.groupby("app_name")
            .agg(
                unique_items=("name", "nunique"),
                total_items =("name", "count"),
                avg_item_price=("unit_price", "mean"),
                total_cat_spend=("total_price", "sum"),
            )
            .reset_index()
            .sort_values("total_items", ascending=False)
        )
        app_item_df.columns = ["App", "Unique Items", "Items Ordered", "Avg Unit Price (₹)", "Total Item Spend (₹)"]
        app_item_df["Avg Unit Price (₹)"]   = app_item_df["Avg Unit Price (₹)"].map("₹{:,.2f}".format)
        app_item_df["Total Item Spend (₹)"] = app_item_df["Total Item Spend (₹)"].map("₹{:,.2f}".format)
        st.dataframe(app_item_df, width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — ITEM INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

def _render_item_intelligence(items_df: pd.DataFrame):
    if items_df.empty:
        st.info("No item-level data yet.")
        return

    # ── Frequency analysis ───────────────────────────────────────────────────
    st.markdown("#### 🔁 Most Frequently Purchased Items")

    freq_df = (
        items_df.groupby(["name", "brand", "category"])
        .agg(
            times_ordered =("name",       "count"),
            total_spent   =("total_price","sum"),
            avg_price     =("unit_price", "mean"),
            min_price     =("unit_price", "min"),
            max_price     =("unit_price", "max"),
        )
        .reset_index()
        .sort_values("times_ordered", ascending=False)
    )

    # Controls
    col_n, col_cat, _ = st.columns([1, 2, 4])
    with col_n:
        top_n = st.slider("Show top", 5, 50, 20, key="freq_n")
    with col_cat:
        cats = ["All"] + sorted(items_df["category"].dropna().unique().tolist())
        sel_cat = st.selectbox("Category", cats, key="freq_cat")

    display_df = freq_df.copy()
    if sel_cat != "All":
        display_df = display_df[display_df["category"] == sel_cat]
    display_df = display_df.head(top_n)

    # Frequency bar chart
    fig_freq = px.bar(
        display_df.sort_values("times_ordered"),
        x="times_ordered", y="name", orientation="h",
        color="category",
        color_discrete_map=CATEGORY_COLORS,
        labels={"times_ordered": "Times Ordered", "name": "", "category": "Category"},
        template="plotly_dark",
        text="times_ordered",
    )
    fig_freq.update_traces(textposition="outside")
    fig_freq.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=10, l=0, r=50),
        height=max(400, len(display_df) * 28),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
    )
    st.plotly_chart(fig_freq, width="stretch")

    # Detailed table
    show_df = display_df.copy()
    show_df["Price Range"] = show_df.apply(
        lambda r: f"₹{r['min_price']:.0f}–₹{r['max_price']:.0f}"
        if r["min_price"] != r["max_price"] else f"₹{r['avg_price']:.0f}", axis=1
    )
    show_df["Avg Price"]    = show_df["avg_price"].map("₹{:,.2f}".format)
    show_df["Total Spent"]  = show_df["total_spent"].map("₹{:,.2f}".format)
    show_df = show_df[["name","brand","category","times_ordered","Avg Price","Price Range","Total Spent"]]
    show_df.columns = ["Item","Brand","Category","Times","Avg Price","Price Range","Total Spent"]
    st.dataframe(show_df, width="stretch", hide_index=True)

    st.divider()

    # ── Top spend by item ────────────────────────────────────────────────────
    st.markdown("#### 💸 Highest Spend Items")
    spend_df = freq_df.sort_values("total_spent", ascending=False).head(top_n)

    col_bubble, col_scatter = st.columns(2)

    with col_bubble:
        fig_spend = px.bar(
            spend_df.sort_values("total_spent"),
            x="total_spent", y="name", orientation="h",
            color="category", color_discrete_map=CATEGORY_COLORS,
            labels={"total_spent": "Total Spent (₹)", "name": ""},
            template="plotly_dark",
            text=spend_df.sort_values("total_spent")["total_spent"].map("₹{:,.0f}".format),
        )
        fig_spend.update_traces(textposition="outside")
        fig_spend.update_layout(
            title="By Total Spend",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=40, b=10, l=0, r=60),
            height=max(400, len(spend_df) * 28),
            showlegend=False,
        )
        st.plotly_chart(fig_spend, width="stretch")

    with col_scatter:
        # Frequency vs spend bubble chart
        fig_bubble = px.scatter(
            freq_df.head(40),
            x="times_ordered", y="total_spent",
            size="avg_price", color="category",
            color_discrete_map=CATEGORY_COLORS,
            hover_name="name",
            labels={"times_ordered":"Times Ordered","total_spent":"Total Spent (₹)","avg_price":"Avg Price"},
            template="plotly_dark",
            size_max=50,
        )
        fig_bubble.update_layout(
            title="Frequency vs Total Spend",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=40, b=10, l=0, r=0),
        )
        st.plotly_chart(fig_bubble, width="stretch")

    st.divider()

    # ── Category breakdown treemap ───────────────────────────────────────────
    st.markdown("#### 🗂️ Category Treemap — Where Your Money Goes")
    cat_item_df = (
        items_df.groupby(["category", "name"])["total_price"].sum()
        .reset_index()
    )
    fig_tree = px.treemap(
        cat_item_df,
        path=["category", "name"],
        values="total_price",
        color="total_price",
        color_continuous_scale="Purples",
        template="plotly_dark",
        hover_data={"total_price": ":.2f"},
    )
    fig_tree.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=0, r=0),
        height=500,
    )
    st.plotly_chart(fig_tree, width="stretch")

    st.divider()

    # ── All items table (searchable) ─────────────────────────────────────────
    st.markdown("#### 📋 All Items — Full List")
    search = st.text_input("🔍 Search item name", key="item_search", placeholder="e.g. Banana, Paneer…")

    all_items = items_df.copy()
    if search:
        all_items = all_items[all_items["name"].str.contains(search, case=False, na=False)]

    all_items_display = all_items[[
        "order_date","app_name","name","brand","category","quantity","unit_price","total_price"
    ]].copy()
    all_items_display["order_date"] = all_items_display["order_date"].dt.strftime("%d %b %Y")
    all_items_display["unit_price"] = all_items_display["unit_price"].map("₹{:,.2f}".format)
    all_items_display["total_price"]= all_items_display["total_price"].map("₹{:,.2f}".format)
    all_items_display.columns = ["Date","App","Item","Brand","Category","Qty","Unit Price","Total"]

    st.dataframe(all_items_display, width="stretch", hide_index=True)
    st.caption(f"Showing {len(all_items_display)} item(s)")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — SAVINGS & INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════

def _render_savings_insights(orders_df: pd.DataFrame, items_df: pd.DataFrame):
    total_spend  = orders_df["total_amount"].sum()
    total_saved  = orders_df["discount"].sum()
    total_fees   = orders_df["delivery_fee"].sum()
    gross_val    = total_spend + total_saved
    save_pct     = (total_saved / gross_val * 100) if gross_val > 0 else 0

    # Headline metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Saved via Discounts", f"₹{total_saved:,.0f}", delta=f"{save_pct:.1f}% of gross")
    c2.metric("Delivery Fees Paid",        f"₹{total_fees:,.0f}",  delta="Cost of convenience", delta_color="inverse")
    c3.metric("Net effective spend",       f"₹{total_spend:,.0f}")
    c4.metric("Savings : Fees ratio",      f"{(total_saved/total_fees):.1f}x" if total_fees else "∞")

    st.divider()

    # ── Savings by app ───────────────────────────────────────────────────────
    st.markdown("#### 💰 Savings & Fees by App")
    app_sv = (
        orders_df.groupby("app_name")
        .agg(spent=("total_amount","sum"), saved=("discount","sum"), fees=("delivery_fee","sum"))
        .reset_index()
    )
    app_sv["save_pct"] = (app_sv["saved"] / (app_sv["spent"] + app_sv["saved"]) * 100).fillna(0)
    app_sv["net_cost"]  = app_sv["fees"] - app_sv["saved"]  # negative = net gain

    col_sv1, col_sv2 = st.columns(2)
    with col_sv1:
        fig_sv = go.Figure()
        fig_sv.add_trace(go.Bar(
            name="Saved", x=app_sv["app_name"], y=app_sv["saved"],
            marker_color="#22c55e", text=app_sv["saved"].map("₹{:,.0f}".format),
            textposition="outside",
        ))
        fig_sv.add_trace(go.Bar(
            name="Delivery Fees", x=app_sv["app_name"], y=app_sv["fees"],
            marker_color="#ef4444", text=app_sv["fees"].map("₹{:,.0f}".format),
            textposition="outside",
        ))
        fig_sv.update_layout(
            title="Savings vs Fees",
            barmode="group", template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=50, b=10, l=0, r=0),
        )
        st.plotly_chart(fig_sv, width="stretch")

    with col_sv2:
        fig_rate = px.bar(
            app_sv.sort_values("save_pct", ascending=False),
            x="app_name", y="save_pct",
            color="save_pct", color_continuous_scale="Greens",
            labels={"app_name": "App", "save_pct": "Discount Rate (%)"},
            template="plotly_dark",
            text=app_sv.sort_values("save_pct", ascending=False)["save_pct"].map("{:.1f}%".format),
        )
        fig_rate.update_traces(textposition="outside")
        fig_rate.update_layout(
            title="Best Discount Rates by App",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=50, b=10, l=0, r=0),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_rate, width="stretch")

    st.divider()

    # ── Cost-reduction recommendations ──────────────────────────────────────
    st.markdown("#### 💡 Where You Can Cut Costs")
    _render_recommendations(orders_df, items_df, app_sv)

    st.divider()

    # ── Price trends for frequent items ─────────────────────────────────────
    if not items_df.empty:
        st.markdown("#### 📈 Price Trends — Frequently Bought Items")
        freq_items = (
            items_df.groupby("name")["name"].count()
            .sort_values(ascending=False).head(8).index.tolist()
        )
        sel_item = st.selectbox("Select item to track price", freq_items, key="price_trend_item")
        trend_df = items_df[items_df["name"] == sel_item].sort_values("order_date")
        if not trend_df.empty:
            fig_pt = px.line(
                trend_df, x="order_date", y="unit_price",
                markers=True, template="plotly_dark",
                labels={"order_date": "Date", "unit_price": "Price (₹)"},
                color_discrete_sequence=["#6366f1"],
            )
            fig_pt.add_hline(
                y=trend_df["unit_price"].mean(),
                line_dash="dot", line_color="#f59e0b",
                annotation_text=f"Avg ₹{trend_df['unit_price'].mean():.0f}",
                annotation_position="bottom right",
            )
            fig_pt.update_layout(
                title=f"Price trend: {sel_item}",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=50, b=10, l=0, r=0),
            )
            st.plotly_chart(fig_pt, width="stretch")

            # Price stats
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("Min Price",  f"₹{trend_df['unit_price'].min():.2f}")
            pc2.metric("Max Price",  f"₹{trend_df['unit_price'].max():.2f}")
            pc3.metric("Avg Price",  f"₹{trend_df['unit_price'].mean():.2f}")
            pc4.metric("Times Bought", str(len(trend_df)))


def _render_recommendations(orders_df, items_df, app_sv):
    """Smart cost-reduction recommendations based on data."""
    recs = []

    # 1. Most expensive app vs cheapest
    if len(app_sv) >= 2:
        sorted_apps = app_sv.sort_values("spent", ascending=False)
        top_app     = sorted_apps.iloc[0]
        recs.append({
            "icon": "🔴",
            "title": f"**{top_app['app_name'].title()}** is your biggest spend",
            "detail": f"You spent ₹{top_app['spent']:,.0f} there. "
                      f"Discount rate: {top_app['save_pct']:.1f}%. "
                      f"Try consolidating orders to hit free-delivery thresholds.",
        })

    # 2. Best discount rate app
    if len(app_sv) >= 1:
        best_disc = app_sv.sort_values("save_pct", ascending=False).iloc[0]
        recs.append({
            "icon": "💚",
            "title": f"**{best_disc['app_name'].title()}** gives the best discounts ({best_disc['save_pct']:.1f}%)",
            "detail": "Shift more grocery orders here to maximise savings.",
        })

    # 3. Delivery fee heavy app
    high_fee_app = app_sv.sort_values("fees", ascending=False).iloc[0] if len(app_sv) else None
    if high_fee_app is not None and high_fee_app["fees"] > 0:
        recs.append({
            "icon": "🛵",
            "title": f"You paid ₹{high_fee_app['fees']:,.0f} in delivery fees on **{high_fee_app['app_name'].title()}**",
            "detail": "Consider a subscription (Zepto Pass, Blinkit One, Swiggy One) to reduce delivery costs.",
        })

    # 4. Items with price variance
    if not items_df.empty:
        price_var = (
            items_df.groupby("name")["unit_price"]
            .agg(["min","max","count"])
            .reset_index()
        )
        price_var = price_var[price_var["count"] >= 2]
        price_var["variance"] = price_var["max"] - price_var["min"]
        price_var = price_var[price_var["variance"] > 0].sort_values("variance", ascending=False)
        if not price_var.empty:
            top_var = price_var.iloc[0]
            recs.append({
                "icon": "📉",
                "title": f"**{top_var['name']}** price varies by ₹{top_var['variance']:.0f}",
                "detail": f"Seen as low as ₹{top_var['min']:.0f} and as high as ₹{top_var['max']:.0f}. "
                           "Buy when price is at the lower end to save.",
            })

        # 5. Top-spend category
        cat_totals = items_df.groupby("category")["total_price"].sum().sort_values(ascending=False)
        if not cat_totals.empty:
            top_cat = cat_totals.index[0]
            recs.append({
                "icon": "🗂️",
                "title": f"**{top_cat}** is your highest-spend category (₹{cat_totals.iloc[0]:,.0f})",
                "detail": "Look for bulk deals or cheaper brands in this category.",
            })

        # 6. Items ordered frequently with high unit price
        high_freq_high_price = (
            items_df.groupby("name")
            .agg(count=("name","count"), avg_price=("unit_price","mean"))
            .reset_index()
            .query("count >= 2 and avg_price >= 100")
            .sort_values("avg_price", ascending=False)
        )
        if not high_freq_high_price.empty:
            item = high_freq_high_price.iloc[0]
            recs.append({
                "icon": "⚡",
                "title": f"**{item['name']}** costs ₹{item['avg_price']:.0f} avg and you buy it often",
                "detail": "Check if a larger pack size or subscription would reduce the per-unit cost.",
            })

    # Render recommendations
    for rec in recs:
        st.markdown(
            f"""<div style="background:#1e293b; border-radius:12px; padding:1rem 1.2rem;
                margin-bottom:0.75rem; border-left:4px solid #6366f1;">
                <span style="font-size:1.3rem;">{rec['icon']}</span>&nbsp;
                {rec['title']}<br>
                <span style="color:#94a3b8; font-size:0.85rem;">{rec['detail']}</span>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── All orders full table ─────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📋 All Orders")
    disp = orders_df.copy()
    disp["order_date"] = disp["order_date"].dt.strftime("%d %b %Y")
    disp = disp[[
        "order_date","app_name","app_category","order_id",
        "total_amount","delivery_fee","discount","notes"
    ]].copy()
    disp["total_amount"]  = disp["total_amount"].map("₹{:,.2f}".format)
    disp["delivery_fee"]  = disp["delivery_fee"].map("₹{:,.2f}".format)
    disp["discount"]      = disp["discount"].map("₹{:,.2f}".format)
    disp.columns = ["Date","App","Type","Order ID","Amount Paid","Delivery Fee","Discount","Notes"]
    st.dataframe(disp, width="stretch", hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_timeseries(df: pd.DataFrame, period: str) -> pd.DataFrame:
    df = df.copy()
    if "Daily" in period:
        cutoff = pd.Timestamp(date.today()) - timedelta(days=30)
        df = df[df["order_date"] >= cutoff]
        df["period"] = df["order_date"].dt.strftime("%b %d")
        return df.groupby("period")["total_amount"].sum().reset_index()
    elif "Weekly" in period:
        cutoff = pd.Timestamp(date.today()) - timedelta(weeks=12)
        df = df[df["order_date"] >= cutoff]
        df["period"] = df["order_date"].dt.to_period("W").dt.start_time.dt.strftime("W %b %d")
        return df.groupby("period")["total_amount"].sum().reset_index()
    else:
        cutoff = pd.Timestamp(date.today()) - timedelta(days=365)
        df = df[df["order_date"] >= cutoff]
        df["period"] = df["order_date"].dt.to_period("M").dt.strftime("%b %Y")
        return df.groupby("period")["total_amount"].sum().reset_index()


def _render_empty_placeholder():
    st.markdown("""
    <div style="text-align:center; padding:3rem; opacity:0.5;">
        <div style="font-size:4rem;">📊</div>
        <p>Charts will appear here once you upload your first receipt.</p>
    </div>
    """, unsafe_allow_html=True)
