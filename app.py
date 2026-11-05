import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Divine Hour Workshop - 3 FB Accounts & L1 Analyzer",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 The Divine Hour Workshop: 3-Day Cohort & Ad Account Analyzer")
st.markdown(
    "Compare **Falgun FB**, **Paarami MMMz**, and **Paarami Suyash** across any **L0 Registration Date Range** "
    "and identify which **Campaign, Ad Set, and Ad Creative** converts `₹199` L0 leads into `₹7,999` L1 buyers."
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

def map_ad_account(row):
    """Maps Tagmango Mango Name & UTM Source to the exact Ad Account Labels."""
    mango = str(row.get("Mango Name", "")).strip()
    src = str(row.get("utm_source", "")).strip().lower()

    if mango == "The Divine Hour Workshop (TDH)":
        return "Falgun FB"
    elif mango == "The Divine Hour Workshop (Brahmmuhurat)":
        return "Paarami MMMz"
    elif mango == "The Divine Hour Workshop (Brahma Muhurat)":
        return "Paarami Suyash"
    elif (
        "google" in src
        or "youtube" in src
        or "yt" in src
        or mango in ["The Divine Hour Workshop (Online)", "The Divine Hour Workshop (YT)"]
    ):
        return "Google Ads Account"
    else:
        return f"Other ({mango})"

@st.cache_data
def load_dataset(uploaded_file):
    if uploaded_file.name.endswith((".xlsx", ".xls")):
        xls = pd.ExcelFile(uploaded_file)
        sheet = "Report" if "Report" in xls.sheet_names else xls.sheet_names[0]
        return pd.read_excel(uploaded_file, sheet_name=sheet)
    return pd.read_csv(uploaded_file)

# --- SIDEBAR: 1. UPLOAD FILES ---
st.sidebar.header("📁 1. Upload Funnel Files")
tm_file = st.sidebar.file_uploader(
    "1️⃣ Upload Tagmango L0 File (XLSX/CSV)",
    type=["xlsx", "xls", "csv"],
    key="tm"
)
l1_file = st.sidebar.file_uploader(
    "2️⃣ Upload L1 (₹7,999) Converted File (CSV/XLSX)",
    type=["csv", "xlsx", "xls"],
    key="l1"
)

if tm_file is not None:
    df_tm_raw = load_dataset(tm_file)

    # Clean & Standardize L0 Data
    df_tm_raw["clean_email"] = clean_email(df_tm_raw["email"])
    df_tm_raw["clean_phone"] = clean_phone(df_tm_raw["phone"])
    df_tm_raw["FE_Price"] = pd.to_numeric(df_tm_raw.get("Mango Price(Sub)", 199.0), errors="coerce").fillna(199.0)

    # Parse Order Date
    df_tm_raw["Order_DT"] = pd.to_datetime(df_tm_raw["Order Date"], format="%d/%m/%Y %I:%M %p", errors="coerce")
    if df_tm_raw["Order_DT"].isna().all():
        df_tm_raw["Order_DT"] = pd.to_datetime(df_tm_raw["Order Date"], dayfirst=True, errors="coerce")

    # Apply Ad Account Labeling
    df_tm_raw["Ad_Account"] = df_tm_raw.apply(map_ad_account, axis=1)

    # Clean UTM Hierarchy Columns
    for col, target in [
        ("utm_campaign", "Campaign"),
        ("utm_medium", "Ad_Set"),
        ("utm_content", "Ad"),
        ("utm_source", "Source")
    ]:
        if col in df_tm_raw.columns:
            df_tm_raw[target] = (
                df_tm_raw[col]
                .fillna("Unattributed / Direct")
                .astype(str)
                .str.strip()
                .replace({"": "Unattributed / Direct", "nan": "Unattributed / Direct", "None": "Unattributed / Direct"})
            )
        else:
            df_tm_raw[target] = "Unattributed / Direct"

    # --- PROCESS L1 FILE FIRST TO HELP AUTO-DETECT COHORT WINDOW ---
    has_l1 = l1_file is not None
    if has_l1:
        df_l1_raw = load_dataset(l1_file)
        name_c = [c for c in df_l1_raw.columns if "name" in c.lower()][0] if any("name" in c.lower() for c in df_l1_raw.columns) else df_l1_raw.columns[0]
        email_c = [c for c in df_l1_raw.columns if "mail" in c.lower()][0] if any("mail" in c.lower() for c in df_l1_raw.columns) else df_l1_raw.columns[1]
        phone_c = [c for c in df_l1_raw.columns if any(k in c.lower() for k in ["mobile", "phone", "contact"])][0] if any(any(k in c.lower() for k in ["mobile", "phone", "contact"]) for c in df_l1_raw.columns) else df_l1_raw.columns[2]
        amt_c = [c for c in df_l1_raw.columns if any(k in c.lower() for k in ["amount", "price", "paid"])]
        date_c = [c for c in df_l1_raw.columns if "date" in c.lower()]

        df_l1_raw["Buyer_Name"] = df_l1_raw[name_c].astype(str)
        df_l1_raw["clean_email"] = clean_email(df_l1_raw[email_c])
        df_l1_raw["clean_phone"] = clean_phone(df_l1_raw[phone_c])
        if amt_c:
            df_l1_raw["L1_Amount"] = pd.to_numeric(df_l1_raw[amt_c[0]].astype(str).str.replace(r"[₹$,\s]", "", regex=True), errors="coerce").fillna(7999.0)
        else:
            df_l1_raw["L1_Amount"] = 7999.0

        if date_c:
            df_l1_raw["L1_DT"] = pd.to_datetime(df_l1_raw[date_c[0]], format="%d/%m/%Y %I:%M:%S %p", errors="coerce")
            if df_l1_raw["L1_DT"].isna().all():
                df_l1_raw["L1_DT"] = pd.to_datetime(df_l1_raw[date_c[0]], dayfirst=True, errors="coerce")
        else:
            df_l1_raw["L1_DT"] = pd.NaT

        # Pre-match against full dataset to find the exact registration dates of L1 buyers
        tm_full_email = df_tm_raw.sort_values("Order_DT").drop_duplicates("clean_email", keep="last")
        tm_full_phone = df_tm_raw.sort_values("Order_DT").drop_duplicates("clean_phone", keep="last")
        pre_m = df_l1_raw.merge(tm_full_email[["clean_email", "Order_DT"]], on="clean_email", how="left")
        unm_pre = pre_m["Order_DT"].isna()
        if unm_pre.any():
            pre_p = df_l1_raw.loc[unm_pre].merge(tm_full_phone[["clean_phone", "Order_DT"]], on="clean_phone", how="left")
            pre_m.loc[unm_pre, "Order_DT"] = pre_p["Order_DT"].values

        cohort_min_dt = pre_m["Order_DT"].min().date() if pre_m["Order_DT"].notna().any() else df_tm_raw["Order_DT"].min().date()
        cohort_max_dt = pre_m["Order_DT"].max().date() if pre_m["Order_DT"].notna().any() else df_tm_raw["Order_DT"].max().date()
    else:
        df_l1_raw = pd.DataFrame()
        cohort_min_dt = df_tm_raw["Order_DT"].min().date()
        cohort_max_dt = df_tm_raw["Order_DT"].max().date()

    # --- SIDEBAR: 2. AD ACCOUNT MODE & FILTER ---
    st.sidebar.divider()
    st.sidebar.header("🎯 2. Ad Account Filter")

    fb_core_accounts = ["Falgun FB", "Paarami MMMz", "Paarami Suyash"]
    account_mode = st.sidebar.radio(
        "Select Analysis Scope:",
        options=[
            "Only 3 FB Ad Accounts (Default)",
            "3 FB Accounts + Google Account",
            "All Landing Pages / Accounts"
        ],
        index=0
    )

    all_detected_accounts = sorted(df_tm_raw["Ad_Account"].unique().tolist())
    if account_mode == "Only 3 FB Ad Accounts (Default)":
        default_accs = [a for a in fb_core_accounts if a in all_detected_accounts]
    elif account_mode == "3 FB Accounts + Google Account":
        default_accs = [a for a in fb_core_accounts + ["Google Ads Account"] if a in all_detected_accounts]
    else:
        default_accs = all_detected_accounts

    selected_accounts = st.sidebar.multiselect(
        "Active Ad Accounts:",
        options=all_detected_accounts,
        default=default_accs
    )

    # --- SIDEBAR: 3. L0 DATE RANGE SELECTOR (3-DAY WORKSHOP COHORT) ---
    st.sidebar.divider()
    st.sidebar.header("📅 3. L0 Registration Date Range")

    overall_min_d = df_tm_raw["Order_DT"].min().date()
    overall_max_d = df_tm_raw["Order_DT"].max().date()

    date_preset = st.sidebar.radio(
        "Quick Date Range Preset:",
        options=[
            "Custom / Manual Date Picker",
            f"Auto-Matched L1 Cohort Window ({cohort_min_dt.strftime('%d %b')} – {cohort_max_dt.strftime('%d %b %Y')})",
            "All Dates in File"
        ],
        index=1 if has_l1 else 2
    )

    if date_preset.startswith("Auto-Matched"):
        default_start, default_end = cohort_min_dt, cohort_max_dt
    elif date_preset == "All Dates in File":
        default_start, default_end = overall_min_d, overall_max_d
    else:
        default_start, default_end = cohort_min_dt, cohort_max_dt

    col_d1, col_d2 = st.sidebar.columns(2)
    start_date = col_d1.date_input("L0 Start Date", value=default_start, min_value=overall_min_d, max_value=overall_max_d)
    end_date = col_d2.date_input("L0 End Date", value=default_end, min_value=overall_min_d, max_value=overall_max_d)

    # Apply Date & Account Filters to L0 DataFrame
    df_tm = df_tm_raw[
        (df_tm_raw["Ad_Account"].isin(selected_accounts))
        & (df_tm_raw["Order_DT"].dt.date >= start_date)
        & (df_tm_raw["Order_DT"].dt.date <= end_date)
    ].copy()

    exclude_unattr = st.sidebar.checkbox("Hide 'Unattributed / Direct' in Charts", value=False)

    # --- SIDEBAR: 4. OPTIONAL AD SPEND PER ACCOUNT ---
    with st.sidebar.expander("💰 4. Optional Ad Spend (For ROAS & CPL)", expanded=False):
        st.caption("Enter Ad Spend (₹) for the selected Date Range:")
        spend_map = {}
        for acc in selected_accounts:
            spend_map[acc] = st.number_input(f"{acc} Spend (₹)", min_value=0.0, value=0.0, step=5000.0, key=f"sp_{acc}")

    # --- MATCH L1 CONVERSIONS TO FILTERED L0 COHORT ---
    if has_l1:
        # Keep latest registration within the selected L0 cohort window for each lead
        tm_sorted = df_tm.sort_values("Order_DT")
        tm_email_map = tm_sorted[tm_sorted["clean_email"] != ""].drop_duplicates("clean_email", keep="last")
        tm_phone_map = tm_sorted[tm_sorted["clean_phone"] != ""].drop_duplicates("clean_phone", keep="last")

        attr_cols = ["Ad_Account", "Mango Name", "Campaign", "Ad_Set", "Ad", "Source", "FE_Price", "Order_DT"]

        # Step 1: Match by Email
        l1_matched = df_l1_raw.merge(tm_email_map[["clean_email"] + attr_cols], on="clean_email", how="left")
        l1_matched["Match_Method"] = np.where(l1_matched["Ad_Account"].notna(), "Email Match", "Unmatched in Window")

        # Step 2: Fallback Match by 10-Digit Mobile
        unm_idx = l1_matched["Ad_Account"].isna()
        if unm_idx.any():
            phone_lookup = df_l1_raw.loc[unm_idx].merge(
                tm_phone_map[["clean_phone"] + attr_cols],
                on="clean_phone",
                how="left"
            )
            for c in attr_cols:
                l1_matched.loc[unm_idx, c] = phone_lookup[c].values
            l1_matched.loc[unm_idx & l1_matched["Ad_Account"].notna(), "Match_Method"] = "Mobile Match"

        l1_matched["Days_to_Convert"] = (l1_matched["L1_DT"] - l1_matched["Order_DT"]).dt.total_seconds() / 86400.0
        l1_valid = l1_matched[l1_matched["Match_Method"] != "Unmatched in Window"].copy()
    else:
        l1_matched = pd.DataFrame()
        l1_valid = pd.DataFrame()

    # --- TOP-LEVEL EXECUTIVE SUMMARY ---
    st.subheader(f"📊 Overall Funnel Summary ({start_date.strftime('%d %b %Y')} ➔ {end_date.strftime('%d %b %Y')})")

    tot_l0_leads = len(df_tm)
    tot_l0_rev = df_tm["FE_Price"].sum()
    tot_l1_all = len(df_l1_raw) if has_l1 else 0
    tot_l1_matched = len(l1_valid) if has_l1 else 0
    tot_l1_rev = l1_valid["L1_Amount"].sum() if has_l1 else 0.0
    tot_combined_rev = tot_l0_rev + tot_l1_rev
    tot_cvr = (tot_l1_matched / tot_l0_leads * 100) if tot_l0_leads > 0 else 0.0
    tot_epl = (tot_combined_rev / tot_l0_leads) if tot_l0_leads > 0 else 0.0
    tot_spend = sum(spend_map.values())

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Selected L0 Leads (₹199)", f"{tot_l0_leads:,}", f"L0 Rev: ₹{tot_l0_rev:,.0f}")
    k2.metric("Attributed L1 Sales (₹7,999)", f"{tot_l1_matched:,}", f"of {tot_l1_all} total L1 buyers")
    k3.metric("L0 ➔ L1 Conversion Rate", f"{tot_cvr:.2f}%", f"1 sale per {int(100/tot_cvr) if tot_cvr > 0 else 0} leads")
    k4.metric("Attributed L1 Revenue", f"₹{tot_l1_rev:,.0f}", f"L0+L1: ₹{tot_combined_rev:,.0f}")
    k5.metric("Earnings Per Lead (EPL)", f"₹{tot_epl:,.1f}", f"ROAS: {(tot_combined_rev/tot_spend):.2f}x" if tot_spend > 0 else "Set Spend in Sidebar")

    # --- ACCOUNT-WISE COMPARISON TABLE (FALGUN FB vs PAARAMI MMMz vs PAARAMI SUYASH) ---
    st.markdown("### 🏢 Ad Account Comparison (`Falgun FB` vs `Paarami MMMz` vs `Paarami Suyash`)")

    acc_l0 = df_tm.groupby(["Ad_Account", "Mango Name"], as_index=False).agg(
        L0_Leads=("clean_email", "count"),
        L0_Revenue=("FE_Price", "sum")
    )
    if has_l1 and not l1_valid.empty:
        acc_l1 = l1_valid.groupby(["Ad_Account", "Mango Name"], as_index=False).agg(
            L1_Conversions=("clean_email", "count"),
            L1_Revenue=("L1_Amount", "sum"),
            Avg_Days_to_Close=("Days_to_Convert", "mean")
        )
        acc_df = pd.merge(acc_l0, acc_l1, on=["Ad_Account", "Mango Name"], how="left").fillna({
            "L1_Conversions": 0, "L1_Revenue": 0.0, "Avg_Days_to_Close": 0.0
        })
    else:
        acc_df = acc_l0.copy()
        acc_df["L1_Conversions"] = 0
        acc_df["L1_Revenue"] = 0.0
        acc_df["Avg_Days_to_Close"] = 0.0

    acc_df["L1_Conv_Rate (%)"] = np.where(acc_df["L0_Leads"] > 0, (acc_df["L1_Conversions"] / acc_df["L0_Leads"]) * 100, 0.0)
    acc_df["Total_Revenue"] = acc_df["L0_Revenue"] + acc_df["L1_Revenue"]
    acc_df["Earnings_Per_Lead"] = np.where(acc_df["L0_Leads"] > 0, acc_df["Total_Revenue"] / acc_df["L0_Leads"], 0.0)
    acc_df["Ad_Spend"] = acc_df["Ad_Account"].map(spend_map).fillna(0.0)
    acc_df["CPL"] = np.where(acc_df["L0_Leads"] > 0, acc_df["Ad_Spend"] / acc_df["L0_Leads"], 0.0)
    acc_df["Total_ROAS"] = np.where(acc_df["Ad_Spend"] > 0, acc_df["Total_Revenue"] / acc_df["Ad_Spend"], 0.0)
    acc_df = acc_df.sort_values(by=["L1_Conversions", "L0_Leads"], ascending=[False, False])

    # Add Overall Summary Row
    summary_row = pd.DataFrame([{
        "Ad_Account": "🔥 OVERALL TOTAL / AVG",
        "Mango Name": "All Selected Landing Pages",
        "L0_Leads": tot_l0_leads,
        "L0_Revenue": tot_l0_rev,
        "L1_Conversions": tot_l1_matched,
        "L1_Conv_Rate (%)": tot_cvr,
        "L1_Revenue": tot_l1_rev,
        "Total_Revenue": tot_combined_rev,
        "Earnings_Per_Lead": tot_epl,
        "Avg_Days_to_Close": l1_valid["Days_to_Convert"].mean() if (has_l1 and not l1_valid.empty) else 0.0,
        "Ad_Spend": tot_spend,
        "CPL": (tot_spend / tot_l0_leads) if tot_l0_leads > 0 else 0.0,
        "Total_ROAS": (tot_combined_rev / tot_spend) if tot_spend > 0 else 0.0
    }])
    acc_display_df = pd.concat([acc_df, summary_row], ignore_index=True)

    base_cols = [
        "Ad_Account", "Mango Name", "L0_Leads", "L0_Revenue",
        "L1_Conversions", "L1_Conv_Rate (%)", "L1_Revenue",
        "Total_Revenue", "Earnings_Per_Lead", "Avg_Days_to_Close"
    ]
    if tot_spend > 0:
        base_cols += ["Ad_Spend", "CPL", "Total_ROAS"]

    st.dataframe(
        acc_display_df[base_cols].style.format({
            "L0_Leads": "{:,.0f}",
            "L0_Revenue": "₹{:,.0f}",
            "L1_Conversions": "{:,.0f}",
            "L1_Conv_Rate (%)": "{:.2f}%",
            "L1_Revenue": "₹{:,.0f}",
            "Total_Revenue": "₹{:,.0f}",
            "Earnings_Per_Lead": "₹{:,.1f}",
            "Avg_Days_to_Close": "{:.1f} d",
            "Ad_Spend": "₹{:,.0f}",
            "CPL": "₹{:,.1f}",
            "Total_ROAS": "{:.2f}x"
        }),
        use_container_width=True,
        hide_index=True
    )

    # Visual Comparison Charts for the Ad Accounts
    ch1, ch2, ch3 = st.columns(3)
    with ch1:
        fig_acc_l0 = px.bar(
            acc_df, x="Ad_Account", y="L0_Leads", color="Ad_Account",
            text_auto=True, title="L0 Leads (₹199) by Ad Account"
        )
        st.plotly_chart(fig_acc_l0, use_container_width=True)
    with ch2:
        fig_acc_l1 = px.bar(
            acc_df, x="Ad_Account", y="L1_Conversions", color="Ad_Account",
            text_auto=True, title="L1 Conversions (₹7,999) by Ad Account"
        )
        st.plotly_chart(fig_acc_l1, use_container_width=True)
    with ch3:
        fig_acc_cvr = px.bar(
            acc_df, x="Ad_Account", y="L1_Conv_Rate (%)", color="Ad_Account",
            text_auto=".2f", title="L0 ➔ L1 Conversion Rate (%) by Ad Account"
        )
        st.plotly_chart(fig_acc_cvr, use_container_width=True)

    st.divider()

    # --- CORE AGGREGATION ENGINE FOR CAMPAIGN / AD SET / AD ---
    def build_perf_table(group_cols, filter_account="All Selected Accounts"):
        if isinstance(group_cols, str):
            group_cols = [group_cols]

        sub_tm = df_tm if filter_account == "All Selected Accounts" else df_tm[df_tm["Ad_Account"] == filter_account]
        sub_l1 = l1_valid if (not has_l1 or l1_valid.empty or filter_account == "All Selected Accounts") else l1_valid[l1_valid["Ad_Account"] == filter_account]

        l0_grp = sub_tm.groupby(group_cols, as_index=False).agg(
            L0_Leads=("clean_email", "count"),
            L0_Revenue=("FE_Price", "sum")
        )
        if has_l1 and not sub_l1.empty:
            l1_grp = sub_l1.groupby(group_cols, as_index=False).agg(
                L1_Conversions=("clean_email", "count"),
                L1_Revenue=("L1_Amount", "sum"),
                Avg_Days=("Days_to_Convert", "mean")
            )
            merged = pd.merge(l0_grp, l1_grp, on=group_cols, how="left").fillna({
                "L1_Conversions": 0, "L1_Revenue": 0.0, "Avg_Days": 0.0
            })
        else:
            merged = l0_grp.copy()
            merged["L1_Conversions"] = 0
            merged["L1_Revenue"] = 0.0
            merged["Avg_Days"] = 0.0

        merged["L1_Conv_Rate (%)"] = np.where(merged["L0_Leads"] > 0, (merged["L1_Conversions"] / merged["L0_Leads"]) * 100, 0.0)
        merged["Total_Revenue"] = merged["L0_Revenue"] + merged["L1_Revenue"]
        merged["EPL (₹/Lead)"] = np.where(merged["L0_Leads"] > 0, merged["Total_Revenue"] / merged["L0_Leads"], 0.0)

        return merged.sort_values(by=["L1_Conversions", "L0_Leads"], ascending=[False, False])

    def format_table(df_in):
        return df_in.style.format({
            "L0_Leads": "{:,.0f}",
            "L0_Revenue": "₹{:,.0f}",
            "L1_Conversions": "{:,.0f}",
            "L1_Conv_Rate (%)": "{:.2f}%",
            "L1_Revenue": "₹{:,.0f}",
            "Total_Revenue": "₹{:,.0f}",
            "EPL (₹/Lead)": "₹{:,.1f}",
            "Avg_Days": "{:.1f} d"
        }).background_gradient(subset=["L1_Conversions", "Total_Revenue"], cmap="Greens")

    # --- DRILL-DOWN FILTER FOR INDIVIDUAL ACCOUNT OR OVERALL ---
    st.subheader("🏆 Winning Ads, Ad Sets & Campaigns Drill-Down")
    account_drill = st.selectbox(
        "Filter Tables & Charts Below by Specific Ad Account:",
        options=["All Selected Accounts"] + selected_accounts,
        index=0
    )

    tab_win_ad, tab_adset, tab_camp, tab_full_tree, tab_daily, tab_buyers = st.tabs([
        "🥇 1. Winning Ads (`utm_content`)",
        "🗂️ 2. Winning Ad Sets (`utm_medium`)",
        "📢 3. Winning Campaigns (`utm_campaign`)",
        "🌳 4. Full Hierarchy (`Account ➔ Campaign ➔ Ad Set ➔ Ad`)",
        "📅 5. Daily L0 Cohort Trend",
        "👥 6. Attributed L1 Buyers List"
    ])

    # --- TAB 1: WINNING ADS ---
    with tab_win_ad:
        st.markdown(f"#### 🥇 Winning Ad Creatives (`utm_content`) — *{account_drill}*")
        ad_df = build_perf_table(["Ad_Account", "Ad"] if account_drill == "All Selected Accounts" else ["Ad"], account_drill)
        plot_ad = ad_df[ad_df["Ad"] != "Unattributed / Direct"] if exclude_unattr else ad_df

        c_a1, c_a2 = st.columns(2)
        with c_a1:
            fig_w_ad = px.bar(
                plot_ad.sort_values("L1_Conversions", ascending=False).head(15),
                x="L1_Conversions", y="Ad",
                color="Ad_Account" if "Ad_Account" in plot_ad.columns else "L1_Conv_Rate (%)",
                orientation="h", text_auto=True,
                title="Top 15 Winning Ads by L1 Conversions (₹7,999 Sales)"
            )
            fig_w_ad.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_w_ad, use_container_width=True)

        with c_a2:
            min_l = st.slider("Minimum L0 Leads for Efficiency Quadrant:", 3, 100, 10)
            q_df = plot_ad[plot_ad["L0_Leads"] >= min_l]
            fig_q = px.scatter(
                q_df, x="L0_Leads", y="L1_Conv_Rate (%)",
                size="Total_Revenue",
                color="Ad_Account" if "Ad_Account" in q_df.columns else "L1_Conversions",
                hover_name="Ad",
                title="Ad Creative Matrix: L0 Volume vs. L1 Conversion Rate % (Size = Total Revenue)"
            )
            st.plotly_chart(fig_q, use_container_width=True)

        # Bleeder Ads Alert
        bleeders = ad_df[(ad_df["L0_Leads"] >= 15) & (ad_df["L1_Conversions"] == 0) & (ad_df["Ad"] != "Unattributed / Direct")]
        if not bleeders.empty:
            with st.expander(f"⚠️ View {len(bleeders)} Non-Converting Ads (15+ L0 Leads in Window, 0 L1 Sales)"):
                st.dataframe(format_table(bleeders), use_container_width=True, hide_index=True)

        st.dataframe(format_table(ad_df), use_container_width=True, hide_index=True)

    # --- TAB 2: WINNING AD SETS ---
    with tab_adset:
        st.markdown(f"#### 🗂️ Ad Set Performance (`utm_medium`) — *{account_drill}*")
        adset_df = build_perf_table(["Ad_Account", "Ad_Set"] if account_drill == "All Selected Accounts" else ["Ad_Set"], account_drill)
        plot_as = adset_df[adset_df["Ad_Set"] != "Unattributed / Direct"] if exclude_unattr else adset_df

        as1, as2 = st.columns(2)
        with as1:
            fig_as1 = px.bar(
                plot_as.sort_values("L1_Conversions", ascending=False).head(15),
                x="L1_Conversions", y="Ad_Set",
                color="Ad_Account" if "Ad_Account" in plot_as.columns else "L1_Conv_Rate (%)",
                orientation="h", text_auto=True,
                title="Top Ad Sets by L1 Conversions"
            )
            fig_as1.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_as1, use_container_width=True)

        with as2:
            fig_as2 = px.bar(
                plot_as.sort_values("L0_Leads", ascending=False).head(15),
                x="L0_Leads", y="Ad_Set",
                color="Ad_Account" if "Ad_Account" in plot_as.columns else "Total_Revenue",
                orientation="h", text_auto=True,
                title="Top Ad Sets by L0 Workshop Leads"
            )
            fig_as2.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_as2, use_container_width=True)

        st.dataframe(format_table(adset_df), use_container_width=True, hide_index=True)

    # --- TAB 3: WINNING CAMPAIGNS ---
    with tab_camp:
        st.markdown(f"#### 📢 Campaign Performance (`utm_campaign`) — *{account_drill}*")
        camp_df = build_perf_table(["Ad_Account", "Campaign"] if account_drill == "All Selected Accounts" else ["Campaign"], account_drill)
        plot_c = camp_df[camp_df["Campaign"] != "Unattributed / Direct"] if exclude_unattr else camp_df

        cp1, cp2 = st.columns(2)
        with cp1:
            fig_cp1 = px.bar(
                plot_c.sort_values("L1_Conversions", ascending=False).head(15),
                x="L1_Conversions", y="Campaign",
                color="Ad_Account" if "Ad_Account" in plot_c.columns else "L1_Conv_Rate (%)",
                orientation="h", text_auto=True,
                title="Top Campaigns by L1 Conversions"
            )
            fig_cp1.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_cp1, use_container_width=True)

        with cp2:
            fig_cp2 = px.bar(
                plot_c.sort_values("Total_Revenue", ascending=False).head(15),
                x=["L0_Revenue", "L1_Revenue"], y="Campaign",
                orientation="h",
                title="Top Campaigns by Total Revenue (L0 + L1)"
            )
            fig_cp2.update_layout(yaxis={"categoryorder": "total ascending"}, barmode="stack")
            st.plotly_chart(fig_cp2, use_container_width=True)

        st.dataframe(format_table(camp_df), use_container_width=True, hide_index=True)

    # --- TAB 4: FULL HIERARCHY ---
    with tab_full_tree:
        st.markdown("#### 🌳 Complete Granular Breakdown (`Ad Account ➔ Campaign ➔ Ad Set ➔ Ad`)")
        hier_df = build_perf_table(["Ad_Account", "Campaign", "Ad_Set", "Ad"], account_drill)

        sun_data = hier_df[hier_df["Total_Revenue"] > 0].copy()
        if exclude_unattr:
            sun_data = sun_data[sun_data["Ad"] != "Unattributed / Direct"]

        if not sun_data.empty:
            fig_sun = px.sunburst(
                sun_data.head(75),
                path=["Ad_Account", "Campaign", "Ad_Set", "Ad"],
                values="Total_Revenue",
                color="L1_Conversions",
                color_continuous_scale="RdYlGn",
                title="Interactive Hierarchy Sunburst (Size = Total Revenue, Color = L1 Sales)"
            )
            fig_sun.update_layout(height=550)
            st.plotly_chart(fig_sun, use_container_width=True)

        st.dataframe(format_table(hier_df), use_container_width=True, hide_index=True)

        csv_hier = hier_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Full Hierarchy Report (CSV)",
            data=csv_hier,
            file_name=f"fb_hierarchy_{start_date}_{end_date}.csv",
            mime="text/csv"
        )

    # --- TAB 5: DAILY COHORT TREND ---
    with tab_daily:
        st.markdown("#### 📅 Daily L0 Registration & L1 Buyer Cohort Trend")
        df_tm["L0_Date"] = df_tm["Order_DT"].dt.date
        daily_l0 = df_tm.groupby(["L0_Date", "Ad_Account"], as_index=False).agg(L0_Leads=("clean_email", "count"))

        fig_d_l0 = px.bar(
            daily_l0, x="L0_Date", y="L0_Leads", color="Ad_Account",
            title="Daily L0 Workshop Registrations by Ad Account", barmode="stack"
        )
        st.plotly_chart(fig_d_l0, use_container_width=True)

        if has_l1 and not l1_valid.empty:
            l1_valid["L0_Reg_Date"] = l1_valid["Order_DT"].dt.date
            daily_l1_cohort = l1_valid.groupby(["L0_Reg_Date", "Ad_Account"], as_index=False).agg(
                L1_Sales=("clean_email", "count")
            )
            fig_d_l1 = px.bar(
                daily_l1_cohort, x="L0_Reg_Date", y="L1_Sales", color="Ad_Account",
                text_auto=True,
                title="Which L0 Registration Dates Produced Your ₹7,999 L1 Buyers? (By Ad Account)"
            )
            st.plotly_chart(fig_d_l1, use_container_width=True)

    # --- TAB 6: ATTRIBUTED L1 BUYERS LIST ---
    with tab_buyers:
        if has_l1:
            st.markdown(f"#### 👥 L1 Buyers Attribution Table ({tot_l1_matched} Matched in Selected Filter / {tot_l1_all} Total)")
            cols_b = [
                "Buyer_Name", "clean_email", "clean_phone", "L1_Amount",
                "Match_Method", "Ad_Account", "Mango Name",
                "Campaign", "Ad_Set", "Ad", "Source",
                "Order_DT", "L1_DT", "Days_to_Convert"
            ]
            show_b = [c for c in cols_b if c in l1_matched.columns]
            st.dataframe(l1_matched[show_b], use_container_width=True, hide_index=True)

            csv_b = l1_matched[show_b].to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Attributed L1 Customers CSV",
                data=csv_b,
                file_name=f"l1_attributed_buyers_{start_date}_{end_date}.csv",
                mime="text/csv"
            )
        else:
            st.info("Upload your L1 Converted Customers file in the sidebar to view customer-level attribution.")

else:
    st.info("👈 Upload your **Tagmango L0 Transaction File** and **L1 (₹7,999) Converted Customers File** in the sidebar to begin.")
