"""views/cleanup.py — Interactive data cleanup: merge duplicate items, fix categories."""

import streamlit as st
import pandas as pd
from database import get_items_df
from normalizer import (
    find_duplicate_clusters,
    save_aliases_bulk,
    get_all_aliases,
    delete_alias,
    CANONICAL_CATEGORY_ORDER,
    init_normalizer_tables,
)

init_normalizer_tables()

APP_ICONS = {
    "zepto": "⚡", "blinkit": "💛", "instamart": "🟠",
    "bigbasket": "🟢", "jiomart": "🔵", "swiggy": "🍊", "zomato": "🔴",
}


def render_cleanup():
    st.markdown("## 🧹 Data Cleanup")
    st.markdown(
        "Fix **duplicate item names** and **wrong categories** so your analytics are accurate. "
        "Saved merges apply to charts & reports immediately — original receipts are untouched."
    )

    tab_dupes, tab_categories, tab_saved = st.tabs([
        "🔀 Duplicate Items",
        "🗂️ Fix Categories",
        "✅ Saved Mappings",
    ])

    with tab_dupes:
        _render_duplicate_tab()

    with tab_categories:
        _render_category_tab()

    with tab_saved:
        _render_saved_tab()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Duplicate Items
# ══════════════════════════════════════════════════════════════════════════════

def _render_duplicate_tab():
    items_df = get_items_df()
    if items_df.empty:
        st.info("No items yet.")
        return

    clusters = find_duplicate_clusters(items_df)

    if not clusters:
        st.success("✅ No suspected duplicates found! Your item data looks clean.")
        return

    st.markdown(
        f"**{len(clusters)} suspected duplicate group(s) found.** "
        "Review each group, edit the canonical name/brand/category, then **Apply Selected**."
    )
    st.caption(
        "Items are grouped when their names are ≥72% similar after stripping brand prefixes and size info."
    )

    st.divider()

    # ── Per-cluster editor ───────────────────────────────────────────────────
    approved: list[tuple] = []   # (raw_name, raw_brand, canon_name, canon_brand, canon_cat)

    for idx, cluster in enumerate(clusters):
        with st.expander(
            f"Group {idx+1}: **{cluster['canonical_name']}**  ·  "
            f"{len(cluster['keys'])} variants",
            expanded=(idx < 5),
        ):
            # Show the variants table
            var_df = pd.DataFrame(cluster["keys"], columns=["Name","Brand","Category"])
            # Count how many times each (name, brand) appears in items
            counts = (
                items_df.groupby(["name","brand"]).size().reset_index(name="count")
            )
            var_df = var_df.merge(
                counts, left_on=["Name","Brand"], right_on=["name","brand"], how="left"
            ).drop(columns=["name","brand"])
            var_df["count"] = var_df["count"].fillna(0).astype(int)
            var_df.columns = ["Item Name","Brand","Current Category","# Orders"]
            st.dataframe(var_df, width="stretch", hide_index=True)

            # Edit canonical values
            st.markdown("**Set canonical (merged) values:**")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                canon_name = st.text_input(
                    "Canonical Name",
                    value=cluster["canonical_name"],
                    key=f"cname_{idx}",
                )
            with cc2:
                canon_brand = st.text_input(
                    "Canonical Brand",
                    value=cluster["canonical_brand"],
                    key=f"cbrand_{idx}",
                )
            with cc3:
                canon_cat = st.selectbox(
                    "Canonical Category",
                    CANONICAL_CATEGORY_ORDER,
                    index=CANONICAL_CATEGORY_ORDER.index(cluster["canonical_cat"])
                          if cluster["canonical_cat"] in CANONICAL_CATEGORY_ORDER else 0,
                    key=f"ccat_{idx}",
                )

            apply = st.checkbox(f"✅ Apply this merge", key=f"apply_{idx}", value=True)
            if apply:
                for raw_name, raw_brand, _ in cluster["keys"]:
                    approved.append((raw_name, raw_brand, canon_name, canon_brand, canon_cat))

    st.divider()

    n_approved = len({(r[0], r[1]) for r in approved})
    btn_label  = f"💾 Save {n_approved} mapping(s)" if n_approved else "💾 Save"
    if st.button(btn_label, type="primary", disabled=(n_approved == 0)):
        save_aliases_bulk(approved)
        st.success(f"✅ Saved {n_approved} item alias(es). Charts will reflect changes immediately.")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Fix Categories
# ══════════════════════════════════════════════════════════════════════════════

def _render_category_tab():
    items_df = get_items_df()
    if items_df.empty:
        st.info("No items yet.")
        return

    st.markdown(
        "Items tagged as **Other** or with a mismatched category can be recategorised here. "
        "Changes are saved as aliases and applied to all analytics."
    )

    # Find items in "Other" and any item with conflicting categories
    other_mask = items_df["category"].isin(["Other", ""])
    other_items = (
        items_df[other_mask]
        .groupby(["name","brand"])
        .agg(count=("name","count"), current_cat=("category","first"))
        .reset_index()
        .sort_values("count", ascending=False)
    )

    # Also find items appearing under multiple categories
    multi_cat = (
        items_df.groupby(["name","brand"])["category"]
        .nunique()
        .reset_index(name="n_cats")
    )
    multi_cat = multi_cat[multi_cat["n_cats"] > 1]
    conflict_items = (
        items_df[items_df[["name","brand"]].apply(tuple, axis=1).isin(
            multi_cat[["name","brand"]].apply(tuple, axis=1)
        )]
        .groupby(["name","brand"])
        .agg(count=("name","count"), cats=("category", lambda x: " / ".join(sorted(set(x)))))
        .reset_index()
    )

    sub_other, sub_conflict = st.tabs([
        f"🏷️ 'Other' Items ({len(other_items)})",
        f"⚠️ Category Conflicts ({len(conflict_items)})",
    ])

    with sub_other:
        if other_items.empty:
            st.success("✅ No items categorised as 'Other'!")
        else:
            _category_editor(other_items, "other", items_df)

    with sub_conflict:
        if conflict_items.empty:
            st.success("✅ No category conflicts detected!")
        else:
            st.dataframe(conflict_items.rename(columns={
                "name":"Item","brand":"Brand","count":"# Orders","cats":"Categories Found"
            }), width="stretch", hide_index=True)
            _category_editor(
                conflict_items.drop(columns=["cats"]).rename(columns={"count":"count","cats":"current_cat"}).assign(current_cat=""),
                "conflict",
                items_df,
            )


def _category_editor(items_df_sub, key_prefix: str, full_items_df):
    """Render an editable table to pick a canonical category per item."""
    st.markdown("Pick the correct category for each item, then save:")

    approved = []
    for i, row in items_df_sub.iterrows():
        c1, c2, c3, c4 = st.columns([4, 2, 3, 1])
        with c1:
            st.text(row["name"][:60] + ("…" if len(row["name"]) > 60 else ""))
        with c2:
            st.text(row.get("brand","") or "")
        with c3:
            # Try to pre-select a smart guess
            existing = full_items_df[
                (full_items_df["name"] == row["name"]) &
                (full_items_df["brand"] == row.get("brand",""))
            ]["category"].value_counts()
            best_guess = (
                existing[existing.index != "Other"].idxmax()
                if (existing.index != "Other").any()
                else "Other"
            )
            default_idx = CANONICAL_CATEGORY_ORDER.index(best_guess) \
                if best_guess in CANONICAL_CATEGORY_ORDER else len(CANONICAL_CATEGORY_ORDER)-1
            new_cat = st.selectbox(
                "Category", CANONICAL_CATEGORY_ORDER,
                index=default_idx,
                key=f"{key_prefix}_cat_{i}",
                label_visibility="collapsed",
            )
        with c4:
            include = st.checkbox("Save", key=f"{key_prefix}_inc_{i}", value=True)

        if include:
            approved.append((row["name"], row.get("brand",""), row["name"], row.get("brand",""), new_cat))

    if st.button(f"💾 Save {len(approved)} category fix(es)", key=f"{key_prefix}_save", type="primary", disabled=not approved):
        save_aliases_bulk(approved)
        st.success(f"✅ Saved {len(approved)} category fix(es).")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — Saved Mappings
# ══════════════════════════════════════════════════════════════════════════════

def _render_saved_tab():
    aliases = get_all_aliases()

    if not aliases:
        st.info("No saved aliases yet. Review duplicate groups or category fixes in the other tabs.")
        return

    st.markdown(f"**{len(aliases)} saved mapping(s)** — these are applied to all analytics views.")

    df = pd.DataFrame(aliases)
    df = df[["raw_name","raw_brand","canonical_name","canonical_brand","canonical_cat","created_at"]]
    df.columns = ["Raw Name","Raw Brand","→ Canonical Name","→ Brand","→ Category","Saved At"]
    st.dataframe(df, width="stretch", hide_index=True)

    st.divider()
    st.markdown("#### 🗑️ Remove a mapping")
    col_n, col_b, col_del = st.columns([4, 2, 1])
    with col_n:
        del_name = st.text_input("Item name to remove", key="del_name")
    with col_b:
        del_brand = st.text_input("Brand (optional)", key="del_brand")
    with col_del:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Delete", key="do_delete", type="secondary"):
            delete_alias(del_name, del_brand)
            st.success("Removed.")
            st.rerun()
