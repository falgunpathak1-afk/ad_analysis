import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Tagmango & L1 Ad Performance Analyzer",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 Campaign, Ad Set & Ad Performance Analyzer (Tagmango ➔ L1)")
st.markdown(
    "Upload your **Tagmango Front-End Leads (with UTMs)** and **L1 Conversion File (Name, Email, Mobile)** "
    "to analyze which **Campaign, Ad Set, and Ad** is driving leads, L1 conversions, and revenue."
)

# --- HELPER FUNCTIONS ---
def clean_phone(series):
    """Normalizes phone numbers to last 10 digits, removing .0, spaces, and +91."""
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str[-10:]
    )

def clean_email(series):
    """Normalizes email addresses to lowercase trimmed strings."""
    return series.astype(str).str.strip().str.lower()

def find_col(columns, candidates, default_idx=0):
    """Finds the best matching column index from a list of candidate names."""
    cols_lower = [c.lower().strip() for c in columns]
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower.index(cand.lower())
    for cand in candidates:
        for i, c in enumerate(cols_lower):
            if cand.lower() in c:
                return i
    return default_idx

@st.cache_data
def load_dataset(uploaded_file):
    if uploaded_file.name.endswith((".xlsx", ".xls")):
        xls = pd.ExcelFile(uploaded_file)
        sheet = "Report" if "Report" in xls.sheet_names else xls.sheet_names[0]
        return pd.read_excel(uploaded_file, sheet_name=sheet)
    return pd.read_csv(uploaded_file)

# --- SIDEBAR: FILE UPLOADERS ---
st.sidebar.header("📁 1. Upload Data Files")
tagmango_file = st.sidebar.file_uploader(
    "Upload Tagmango Leads File (XLSX/CSV)",
    type=["xlsx", "xls", "csv"],
    key="tm_file"
)
l1_file = st.sidebar.file_uploader(
    "Upload L1 Conversions File (CSV/XLSX)",
    type=["csv", "xlsx", "xls"],
    key="l1_file"
)

if tagmango_file is not None:
    df_tm = load_dataset(tagmango_file)
    tm_cols = df_tm.columns.tolist()

    # --- SIDEBAR: COLUMN MAPPING ---
    with st.sidebar.expander("⚙️ 2. Column & UTM Mapping", expanded=False):
        st.caption("**Tagmango File Columns**")
        tm_email_col = st.selectbox("Lead Email", tm_cols, index=find_col(tm_cols, ["email"]))
        tm_phone_col = st.selectbox("Lead Phone/Mobile", tm_cols, index=find_col(tm_cols, ["phone", "mobile", "contact"]))
        tm_price_col = st.selectbox("Front-End Price", ["None"] + tm_cols, index=find_col(["None"] + tm_cols, ["mango price(sub)", "price", "amount"], 0))
        tm_date_col = st.selectbox("Order Date", ["None"] + tm_cols, index=find_col(["None"] + tm_cols, ["order date", "date", "created"], 0))
        tm_mango_col = st.selectbox("Workshop / Mango Name", ["None"] + tm_cols, index=find_col(["None"] + tm_cols, ["mango name", "workshop", "product"], 0))

        st.caption("**Ad Hierarchy (UTM) Columns**")
        utm_camp_col = st.selectbox("Campaign Column", tm_cols, index=find_col(tm_cols, ["utm_campaign", "campaign"]))
        utm_adset_col = st.selectbox("Ad Set Column", tm_cols, index=find_col(tm_cols, ["utm_medium", "utm_term", "adset", "ad_set"]))
        utm_ad_col = st.selectbox("Ad / Creative Column", tm_cols, index=find_col(tm_cols, ["utm_content", "utm_term", "ad"]))
        utm_source_col = st.selectbox("Source / Placement Column", tm_cols, index=find_col(tm_cols, ["utm_source", "source"]))

    # Standardize Tagmango DataFrame
    df_tm["clean_email"] = clean_email(df_tm[tm_email_col])
    df_tm["clean_phone"] = clean_phone(df_tm[tm_phone_col])
    df_tm["FE_Price"] = pd.to_numeric(df_tm[tm_price_col], errors="coerce").fillna(0) if tm_price_col != "None" else 0.0

    if tm_date_col != "None":
        df_tm["Order_DT"] = pd.to_datetime(df_tm[tm_date_col], format="%d/%m/%Y %I:%M %p", errors="coerce")
        if df_tm["Order_DT"].isna().all():
            df_tm["Order_DT"] = pd.to_datetime(df_tm[tm_date_col], dayfirst=True, errors="coerce")
    else:
        df_tm["Order_DT"] = pd.NaT

    df_tm["Campaign"] = df_tm[utm_camp_col].fillna("Unattributed / Direct").astype(str).str.strip()
    df_tm["Ad_Set"] = df_tm[utm_adset_col].fillna("Unattributed / Direct").astype(str).str.strip()
    df_tm["Ad"] = df_tm[utm_ad_col].fillna("Unattributed / Direct").astype(str).str.strip()
    df_tm["Source"] = df_tm[utm_source_col].fillna("Unattributed / Direct").astype(str).str.strip()
    df_tm["Mango_Name"] = df_tm[tm_mango_col].fillna("Default").astype(str) if tm_mango_col != "None" else "All Workshops"

    # Replace empty strings with Unattributed / Direct
    for c in ["Campaign", "Ad_Set", "Ad", "Source"]:
        df_tm[c] = df_tm[c].replace({"": "Unattributed / Direct", "nan": "Unattributed / Direct", "None": "Unattributed / Direct"})

    # --- SIDEBAR FILTERS ---
    st.sidebar.header("🔍 3. Filters")
    if df_tm["Order_DT"].notna().any():
        min_d = df_tm["Order_DT"].min().date()
        max_d = df_tm["Order_DT"].max().date()
        date_range = st.sidebar.date_input("Tagmango Lead Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        if len(date_range) == 2:
            df_tm = df_tm[(df_tm["Order_DT"].dt.date >= date_range[0]) & (df_tm["Order_DT"].dt.date <= date_range[1])]

    sources_list = sorted(df_tm["Source"].unique().tolist())
    sel_sources = st.sidebar.multiselect("Filter UTM Source", sources_list, default=sources_list)
    if sel_sources:
        df_tm = df_tm[df_tm["Source"].isin(sel_sources)]

    mango_list = sorted(df_tm["Mango_Name"].unique().tolist())
    if len(mango_list) > 1:
        sel_mangos = st.sidebar.multiselect("Filter Mango Name", mango_list, default=mango_list)
        if sel_mangos:
            df_tm = df_tm[df_tm["Mango_Name"].isin(sel_mangos)]

    exclude_unattributed = st.sidebar.checkbox("Hide 'Unattributed / Direct' in Charts", value=False)
    default_l1_price = st.sidebar.number_input("Default L1 Ticket Price (₹) (if no Amount column)", value=7999.0, step=500.0)

    # --- L1 CONVERSION FILE PROCESSING & MATCHING ---
    has_l1 = l1_file is not None
    if has_l1:
        df_l1 = load_dataset(l1_file)
        l1_cols = df_l1.columns.tolist()

        with st.sidebar.expander("⚙️ L1 File Column Mapping", expanded=False):
            l1_name_col = st.selectbox("L1 Buyer Name", l1_cols, index=find_col(l1_cols, ["name", "buyer", "customer"]))
            l1_email_col = st.selectbox("L1 Buyer Email", l1_cols, index=find_col(l1_cols, ["email", "mail"]))
            l1_phone_col = st.selectbox("L1 Buyer Mobile", l1_cols, index=find_col(l1_cols, ["mobile", "phone", "contact", "whatsapp"]))
            l1_amt_col = st.selectbox("L1 Amount Paid (Optional)", ["None"] + l1_cols, index=find_col(["None"] + l1_cols, ["amount", "price", "value", "paid"], 0))
            l1_date_col = st.selectbox("L1 Conversion Date (Optional)", ["None"] + l1_cols, index=find_col(["None"] + l1_cols, ["date", "time", "created"], 0))

        df_l1["Buyer_Name"] = df_l1[l1_name_col].astype(str)
        df_l1["clean_email"] = clean_email(df_l1[l1_email_col])
        df_l1["clean_phone"] = clean_phone(df_l1[l1_phone_col])
        if l1_amt_col != "None":
            df_l1["L1_Amount"] = pd.to_numeric(df_l1[l1_amt_col].astype(str).str.replace(r"[₹$,\s]", "", regex=True), errors="coerce").fillna(default_l1_price)
        else:
            df_l1["L1_Amount"] = default_l1_price

        if l1_date_col != "None":
            df_l1["L1_DT"] = pd.to_datetime(df_l1[l1_date_col], format="%d/%m/%Y %I:%M:%S %p", errors="coerce")
            if df_l1["L1_DT"].isna().all():
                df_l1["L1_DT"] = pd.to_datetime(df_l1[l1_date_col], dayfirst=True, errors="coerce")
        else:
            df_l1["L1_DT"] = pd.NaT

        # Deduplicate Tagmango leads for first-touch attribution
        tm_sorted = df_tm.sort_values("Order_DT") if df_tm["Order_DT"].notna().any() else df_tm
        tm_email_map = tm_sorted[tm_sorted["clean_email"] != ""].drop_duplicates("clean_email", keep="first")
        tm_phone_map = tm_sorted[tm_sorted["clean_phone"] != ""].drop_duplicates("clean_phone", keep="first")

        attr_cols = ["Campaign", "Ad_Set", "Ad", "Source", "Mango_Name", "FE_Price", "Order_DT"]

        # 1. Match by Email
        l1_matched = df_l1.merge(tm_email_map[["clean_email"] + attr_cols], on="clean_email", how="left")
        l1_matched["Match_Method"] = np.where(l1_matched["Campaign"].notna(), "Email Match", "Unmatched")

        # 2. Fallback Match by 10-digit Mobile
        unmatched_idx = l1_matched["Campaign"].isna()
        if unmatched_idx.any():
            phone_lookup = df_l1.loc[unmatched_idx].merge(
                tm_phone_map[["clean_phone"] + attr_cols],
                on="clean_phone",
                how="left"
            )
            for col in attr_cols:
                l1_matched.loc[unmatched_idx, col] = phone_lookup[col].values
            l1_matched.loc[unmatched_idx & l1_matched["Campaign"].notna(), "Match_Method"] = "Mobile Match"

        l1_matched["Days_to_Convert"] = (l1_matched["L1_DT"] - l1_matched["Order_DT"]).dt.total_seconds() / 86400.0
        l1_valid = l1_matched[l1_matched["Match_Method"] != "Unmatched"].copy()
    else:
        df_l1 = pd.DataFrame()
        l1_matched = pd.DataFrame()
        l1_valid = pd.DataFrame()

    # --- TOP KPI SUMMARY ---
    total_leads = len(df_tm)
    fe_rev = df_tm["FE_Price"].sum()
    total_l1_buyers = len(df_l1) if has_l1 else 0
    matched_l1_buyers = len(l1_valid) if has_l1 else 0
    l1_rev = df_l1["L1_Amount"].sum() if has_l1 else 0.0
    matched_l1_rev = l1_valid["L1_Amount"].sum() if has_l1 else 0.0
    l1_cvr = (matched_l1_buyers / total_leads * 100) if total_leads > 0 else 0.0
    total_rev = fe_rev + l1_rev

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Tagmango Leads (L0)", f"{total_leads:,}", f"FE Rev: ₹{fe_rev:,.0f}")
    k2.metric("Total L1 Conversions", f"{total_l1_buyers:,}", f"Matched: {matched_l1_buyers} ({(matched_l1_buyers/total_l1_buyers*100) if total_l1_buyers else 0:.1f}%)")
    k3.metric("Lead ➔ L1 Conv. Rate", f"{l1_cvr:.2f}%", f"{matched_l1_buyers} of {total_leads:,} leads")
    k4.metric("L1 Back-End Revenue", f"₹{l1_rev:,.0f}", f"Attributed: ₹{matched_l1_rev:,.0f}")
    k5.metric("Total Funnel Revenue", f"₹{total_rev:,.0f}", f"EPL: ₹{(total_rev/total_leads) if total_leads else 0:,.1f}/lead")

    st.divider()

    # --- CORE AGGREGATION ENGINE ---
    def get_performance_table(group_cols):
        if isinstance(group_cols, str):
            group_cols = [group_cols]

        leads_grp = df_tm.groupby(group_cols, as_index=False).agg(
            Leads=("clean_email", "count"),
            FE_Revenue=("FE_Price", "sum")
        )

        if has_l1 and not l1_valid.empty:
            l1_grp = l1_valid.groupby(group_cols, as_index=False).agg(
                L1_Conversions=("clean_email", "count"),
                L1_Revenue=("L1_Amount", "sum"),
                Avg_Days_to_Close=("Days_to_Convert", "mean")
            )
            perf = pd.merge(leads_grp, l1_grp, on=group_cols, how="left").fillna({
                "L1_Conversions": 0,
                "L1_Revenue": 0.0,
                "Avg_Days_to_Close": 0.0
            })
        else:
            perf = leads_grp.copy()
            perf["L1_Conversions"] = 0
            perf["L1_Revenue"] = 0.0
            perf["Avg_Days_to_Close"] = 0.0

        perf["L1_Conv_Rate (%)"] = np.where(perf["Leads"] > 0, (perf["L1_Conversions"] / perf["Leads"]) * 100, 0.0)
        perf["Total_Revenue"] = perf["FE_Revenue"] + perf["L1_Revenue"]
        perf["Revenue_Per_Lead"] = np.where(perf["Leads"] > 0, perf["Total_Revenue"] / perf["Leads"], 0.0)

        return perf.sort_values(by=["L1_Conversions", "Leads"], ascending=[False, False])

    def style_perf_table(df_in):
        return df_in.style.format({
            "Leads": "{:,.0f}",
            "FE_Revenue": "₹{:,.0f}",
            "L1_Conversions": "{:,.0f}",
            "L1_Conv_Rate (%)": "{:.2f}%",
            "L1_Revenue": "₹{:,.0f}",
            "Total_Revenue": "₹{:,.0f}",
            "Revenue_Per_Lead": "₹{:,.1f}",
            "Avg_Days_to_Close": "{:.1f} d"
        }).background_gradient(subset=["L1_Conversions", "Total_Revenue"], cmap="Greens")

    # --- PERFORMANCE TABS ---
    tab_camp, tab_adset, tab_ad, tab_hier, tab_buyers = st.tabs([
        "📢 1. Campaign Performance",
        "🗂️ 2. Ad Set Performance",
        "🎨 3. Ad (Creative) Performance",
        "🌳 4. Full Hierarchy (Campaign ➔ Ad Set ➔ Ad)",
        "👥 5. Matched L1 Buyers & Unmatched List"
    ])

    # --- TAB 1: CAMPAIGN PERFORMANCE ---
    with tab_camp:
        st.subheader("📢 Campaign Performance (`utm_campaign`)")
        camp_df = get_performance_table("Campaign")
        chart_camp = camp_df[camp_df["Campaign"] != "Unattributed / Direct"] if exclude_unattributed else camp_df

        c1, c2 = st.columns(2)
        with c1:
            fig_c_l1 = px.bar(
                chart_camp.sort_values("L1_Conversions", ascending=False).head(15),
                x="L1_Conversions", y="Campaign", orientation="h",
                color="L1_Conv_Rate (%)", text_auto=True,
                title="Top Campaigns by L1 Conversions (Colored by Conv. Rate %)",
                color_continuous_scale="Viridis"
            )
            fig_c_l1.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_c_l1, use_container_width=True)

        with c2:
            fig_c_leads = px.bar(
                chart_camp.sort_values("Leads", ascending=False).head(15),
                x="Leads", y="Campaign", orientation="h",
                color="Total_Revenue", text_auto=True,
                title="Top Campaigns by Tagmango Leads (Colored by Total Revenue)",
                color_continuous_scale="Blues"
            )
            fig_c_leads.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_c_leads, use_container_width=True)

        st.dataframe(style_perf_table(camp_df), use_container_width=True, hide_index=True)

    # --- TAB 2: AD SET PERFORMANCE ---
    with tab_adset:
        st.subheader("🗂️ Ad Set / Audience Performance (`utm_medium`)")
        adset_df = get_performance_table("Ad_Set")
        chart_adset = adset_df[adset_df["Ad_Set"] != "Unattributed / Direct"] if exclude_unattributed else adset_df

        a1, a2 = st.columns(2)
        with a1:
            fig_as_l1 = px.bar(
                chart_adset.sort_values("L1_Conversions", ascending=False).head(15),
                x="L1_Conversions", y="Ad_Set", orientation="h",
                color="L1_Conv_Rate (%)", text_auto=True,
                title="Top Ad Sets by L1 Conversions",
                color_continuous_scale="Tealgrn"
            )
            fig_as_l1.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_as_l1, use_container_width=True)

        with a2:
            fig_as_rev = px.bar(
                chart_adset.sort_values("Total_Revenue", ascending=False).head(15),
                x=["FE_Revenue", "L1_Revenue"], y="Ad_Set", orientation="h",
                title="Top Ad Sets by Stacked Revenue (Front-End + L1)",
                labels={"value": "Revenue (₹)", "variable": "Stage"}
            )
            fig_as_rev.update_layout(yaxis={"categoryorder": "total ascending"}, barmode="stack")
            st.plotly_chart(fig_as_rev, use_container_width=True)

        st.dataframe(style_perf_table(adset_df), use_container_width=True, hide_index=True)

    # --- TAB 3: AD (CREATIVE) PERFORMANCE ---
    with tab_ad:
        st.subheader("🎨 Ad Creative Performance (`utm_content`)")
        ad_df = get_performance_table("Ad")
        chart_ad = ad_df[ad_df["Ad"] != "Unattributed / Direct"] if exclude_unattributed else ad_df

        ad_c1, ad_c2 = st.columns(2)
        with ad_c1:
            fig_ad_l1 = px.bar(
                chart_ad.sort_values("L1_Conversions", ascending=False).head(15),
                x="L1_Conversions", y="Ad", orientation="h",
                color="L1_Conv_Rate (%)", text_auto=True,
                title="Winning Ads by L1 Conversions",
                color_continuous_scale="Plasma"
            )
            fig_ad_l1.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_ad_l1, use_container_width=True)

        with ad_c2:
            min_leads_q = st.slider("Min Leads for Creative Matrix:", 5, 150, 20)
            quad_df = chart_ad[chart_ad["Leads"] >= min_leads_q]
            fig_quad = px.scatter(
                quad_df, x="Leads", y="L1_Conv_Rate (%)",
                size="Total_Revenue", color="L1_Conversions",
                hover_name="Ad",
                title="Ad Efficiency Matrix: Lead Volume vs. L1 Conv Rate (%)",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig_quad, use_container_width=True)

        # Highlight Bleeders (High Front-End Leads, 0 L1 Conversions)
        bleeders = ad_df[(ad_df["Leads"] >= 30) & (ad_df["L1_Conversions"] == 0) & (ad_df["Ad"] != "Unattributed / Direct")]
        if not bleeders.empty:
            with st.expander(f"⚠️ View {len(bleeders)} 'Non-Converting' Ads (30+ Leads but 0 L1 Sales)"):
                st.dataframe(style_perf_table(bleeders), use_container_width=True, hide_index=True)

        st.dataframe(style_perf_table(ad_df), use_container_width=True, hide_index=True)

    # --- TAB 4: FULL HIERARCHY DRILL-DOWN ---
    with tab_hier:
        st.subheader("🌳 Full Hierarchy Drill-Down (`Campaign ➔ Ad Set ➔ Ad`)")
        hier_df = get_performance_table(["Campaign", "Ad_Set", "Ad"])

        # Interactive Filter by Campaign
        camp_filter = st.multiselect(
            "Filter Hierarchy by Campaign:",
            options=sorted(hier_df["Campaign"].unique().tolist()),
            default=[]
        )
        hier_filtered = hier_df[hier_df["Campaign"].isin(camp_filter)] if camp_filter else hier_df

        # Sunburst visualization of L1 Conversions or Total Revenue
        sun_df = hier_filtered[hier_filtered["Total_Revenue"] > 0].copy()
        if exclude_unattributed:
            sun_df = sun_df[sun_df["Campaign"] != "Unattributed / Direct"]

        if not sun_df.empty:
            fig_sun = px.sunburst(
                sun_df.head(60),
                path=["Campaign", "Ad_Set", "Ad"],
                values="Total_Revenue",
                color="L1_Conversions",
                color_continuous_scale="RdYlGn",
                title="Hierarchy Breakdown (Size = Total Revenue, Color = L1 Conversions)"
            )
            fig_sun.update_layout(height=550)
            st.plotly_chart(fig_sun, use_container_width=True)

        st.dataframe(style_perf_table(hier_filtered), use_container_width=True, hide_index=True)

        csv_hier = hier_filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Campaign-AdSet-Ad Performance CSV",
            data=csv_hier,
            file_name="campaign_adset_ad_performance.csv",
            mime="text/csv"
        )

    # --- TAB 5: MATCHED BUYERS & UNMATCHED LIST ---
    with tab_buyers:
        if has_l1:
            st.subheader(f"✅ Matched L1 Buyers ({len(l1_valid)} of {len(df_l1)} matched)")
            cols_to_show = [
                "Buyer_Name", "clean_email", "clean_phone", "L1_Amount",
                "Match_Method", "Campaign", "Ad_Set", "Ad", "Source",
                "Mango_Name", "Order_DT", "L1_DT", "Days_to_Convert"
            ]
            existing_cols = [c for c in cols_to_show if c in l1_matched.columns]
            st.dataframe(l1_matched[existing_cols], use_container_width=True, hide_index=True)

            unmatched_df = l1_matched[l1_matched["Match_Method"] == "Unmatched"]
            if not unmatched_df.empty:
                st.warning(f"⚠️ {len(unmatched_df)} L1 Buyers did not match any email or 10-digit phone in the filtered Tagmango file:")
                st.dataframe(unmatched_df[["Buyer_Name", "clean_email", "clean_phone", "L1_Amount"]], use_container_width=True, hide_index=True)

            csv_l1 = l1_matched[existing_cols].to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Attributed L1 Buyers List (CSV)",
                data=csv_l1,
                file_name="l1_buyers_with_utm_attribution.csv",
                mime="text/csv"
            )
        else:
            st.info("👈 Upload your L1 Conversion CSV/Excel file in the sidebar to view buyer-level attribution.")

else:
    st.info("👈 Upload your **Tagmango File** and **L1 Conversion File** in the left sidebar to begin.")
