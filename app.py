import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="TDH Funnel & UTM Attribution Dashboard",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 The Divine Hour: Ad Attribution & Funnel Analytics")
st.markdown(
    "Analyze Front-End Workshop Leads (`₹199`) and automatically attribute High-Ticket Back-End Sales (`₹7,999`) "
    "back to their exact **UTM Source, Campaign, Ad Set (`utm_medium`), and Ad Creative (`utm_content`)**."
)

# --- HELPER FUNCTIONS ---
def clean_phone(series):
    """Normalizes phone numbers to the last 10 digits for reliable cross-file matching."""
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str[-10:]
    )

def clean_email(series):
    """Normalizes email addresses to lowercase trimmed strings."""
    return series.astype(str).str.strip().str.lower()

@st.cache_data
def load_file(uploaded_file):
    if uploaded_file.name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)

# --- SIDEBAR: FILE UPLOADERS ---
st.sidebar.header("📁 1. Upload Funnel Files")
leads_file = st.sidebar.file_uploader(
    "Upload Front-End Leads (Tagmango XLSX/CSV)",
    type=["xlsx", "xls", "csv"],
    key="leads"
)
sales_file = st.sidebar.file_uploader(
    "Upload Back-End High-Ticket Sales (CSV/XLSX)",
    type=["csv", "xlsx", "xls"],
    key="sales"
)

st.sidebar.divider()
st.sidebar.header("💰 2. Optional Ad Spend (ROAS)")
total_ad_spend = st.sidebar.number_input(
    "Enter Total Ad Spend (₹) for ROAS/CPL:",
    min_value=0.0,
    value=0.0,
    step=5000.0
)

if leads_file is not None:
    df_leads = load_file(leads_file)

    # Standardize Lead Columns
    df_leads["clean_email"] = clean_email(df_leads["email"])
    df_leads["clean_phone"] = clean_phone(df_leads["phone"])
    df_leads["Order_DT"] = pd.to_datetime(df_leads["Order Date"], format="%d/%m/%Y %I:%M %p", errors="coerce")
    if df_leads["Order_DT"].isna().all():
        df_leads["Order_DT"] = pd.to_datetime(df_leads["Order Date"], dayfirst=True, errors="coerce")

    df_leads["Mango Price(Sub)"] = pd.to_numeric(df_leads["Mango Price(Sub)"], errors="coerce").fillna(0)

    utm_cols = ["utm_source", "utm_campaign", "utm_medium", "utm_content", "utm_term", "Mango Name", "device_type", "initiated_platform"]
    for col in utm_cols:
        if col in df_leads.columns:
            df_leads[col] = df_leads[col].fillna("Unattributed / Direct").astype(str)
        else:
            df_leads[col] = "Unattributed / Direct"

    # --- SIDEBAR FILTERS ---
    st.sidebar.divider()
    st.sidebar.header("🔍 3. Funnel Filters")

    if df_leads["Order_DT"].notna().any():
        min_d = df_leads["Order_DT"].min().date()
        max_d = df_leads["Order_DT"].max().date()
        date_range = st.sidebar.date_input("Lead Order Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        if len(date_range) == 2:
            df_leads = df_leads[(df_leads["Order_DT"].dt.date >= date_range[0]) & (df_leads["Order_DT"].dt.date <= date_range[1])]

    mango_options = sorted(df_leads["Mango Name"].unique().tolist())
    selected_mangos = st.sidebar.multiselect("Filter Workshop (Mango Name)", mango_options, default=mango_options)
    if selected_mangos:
        df_leads = df_leads[df_leads["Mango Name"].isin(selected_mangos)]

    source_options = sorted(df_leads["utm_source"].unique().tolist())
    selected_sources = st.sidebar.multiselect("Filter UTM Source", source_options, default=source_options)
    if selected_sources:
        df_leads = df_leads[df_leads["utm_source"].isin(selected_sources)]

    # --- CROSS-MATCHING BACK-END SALES TO FRONT-END LEADS ---
    has_sales = sales_file is not None
    if has_sales:
        df_sales = load_file(sales_file)
        df_sales["clean_email"] = clean_email(df_sales["Email"])
        df_sales["clean_phone"] = clean_phone(df_sales["Mobile"])
        df_sales["Amount"] = pd.to_numeric(df_sales["Amount"], errors="coerce").fillna(0)
        df_sales["Sale_DT"] = pd.to_datetime(df_sales["Date"], format="%d/%m/%Y %I:%M:%S %p", errors="coerce")
        if df_sales["Sale_DT"].isna().all():
            df_sales["Sale_DT"] = pd.to_datetime(df_sales["Date"], dayfirst=True, errors="coerce")

        # Deduplicate leads (earliest registration wins for first-touch attribution)
        leads_email_map = df_leads.sort_values("Order_DT").drop_duplicates("clean_email", keep="first")
        leads_phone_map = df_leads.sort_values("Order_DT").drop_duplicates("clean_phone", keep="first")

        merge_Select = ["Mango Name", "Mango Price(Sub)", "utm_source", "utm_campaign", "utm_medium", "utm_content", "utm_term", "device_type", "Order_DT"]

        # Step 1: Match by Email
        sales_attributed = df_sales.merge(
            leads_email_map[["clean_email"] + merge_Select],
            on="clean_email",
            how="left"
        )

        # Step 2: Fallback Match by 10-Digit Phone Number
        unmatched_mask = sales_attributed["Order_DT"].isna()
        if unmatched_mask.any():
            phone_matched = df_sales[unmatched_mask].merge(
                leads_phone_map[["clean_phone"] + merge_Select],
                on="clean_phone",
                how="left"
            )
            for col in merge_Select:
                sales_attributed.loc[unmatched_mask, col] = phone_matched[col].values

        sales_attributed["Matched_Status"] = np.where(sales_attributed["Order_DT"].notna(), "Matched to Lead", "Unmatched (Not in Filtered Leads)")
        sales_attributed["Days_to_Convert"] = (sales_attributed["Sale_DT"] - sales_attributed["Order_DT"]).dt.total_seconds() / 86400.0

        for col in ["utm_source", "utm_campaign", "utm_medium", "utm_content", "utm_term", "Mango Name"]:
            sales_attributed[col] = sales_attributed[col].fillna("Unmatched Buyer")
    else:
        sales_attributed = pd.DataFrame()

    # --- EXECUTIVE SUMMARY KPIs ---
    total_leads = len(df_leads)
    fe_revenue = df_leads["Mango Price(Sub)"].sum()

    if has_sales:
        matched_sales_df = sales_attributed[sales_attributed["Matched_Status"] == "Matched to Lead"]
        total_be_sales = len(sales_attributed)
        matched_be_sales = len(matched_sales_df)
        be_revenue = sales_attributed["Amount"].sum()
        matched_be_revenue = matched_sales_df["Amount"].sum()
        conv_rate = (matched_be_sales / total_leads * 100) if total_leads > 0 else 0.0
        avg_days = matched_sales_df["Days_to_Convert"].mean()
    else:
        total_be_sales = matched_be_sales = 0
        be_revenue = matched_be_revenue = conv_rate = avg_days = 0.0

    combined_revenue = fe_revenue + be_revenue

    st.subheader("📊 Executive Funnel Summary")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Front-End Leads (₹199)", f"{total_leads:,}", f"Rev: ₹{fe_revenue:,.0f}")
    k2.metric("High-Ticket Sales (₹7,999)", f"{total_be_sales:,}", f"Matched: {matched_be_sales} ({ (matched_be_sales/total_be_sales*100) if total_be_sales else 0:.1f}%)")
    k3.metric("Back-End Revenue", f"₹{be_revenue:,.0f}", f"Matched Rev: ₹{matched_be_revenue:,.0f}")
    k4.metric("Total Funnel Revenue", f"₹{combined_revenue:,.0f}", f"Lead-to-Sale CVR: {conv_rate:.2f}%")

    if total_ad_spend > 0:
        s1, s2, s3, s4 = st.columns(4)
        cpl = total_ad_spend / total_leads if total_leads > 0 else 0
        fe_roas = fe_revenue / total_ad_spend
        be_cpa = total_ad_spend / total_be_sales if total_be_sales > 0 else 0
        total_roas = combined_revenue / total_ad_spend
        s1.metric("Cost Per Lead (CPL)", f"₹{cpl:,.2f}")
        s2.metric("Front-End ROAS (Self-Liquidating)", f"{fe_roas:.2f}x")
        s3.metric("Cost Per High-Ticket Sale (CPA)", f"₹{be_cpa:,.2f}")
        s4.metric("Combined Funnel ROAS", f"{total_roas:.2f}x", delta=f"Net: ₹{combined_revenue - total_ad_spend:,.0f}")

    st.divider()

    # --- AGGREGATION BUILDER ---
    def build_attribution_table(dimension):
        lead_grp = df_leads.groupby(dimension, as_index=False).agg(
            Front_End_Leads=("clean_email", "count"),
            Front_End_Revenue=("Mango Price(Sub)", "sum")
        )
        if has_sales:
            sale_grp = sales_attributed[sales_attributed["Matched_Status"] == "Matched to Lead"].groupby(dimension, as_index=False).agg(
                High_Ticket_Sales=("clean_email", "count"),
                Back_End_Revenue=("Amount", "sum"),
                Avg_Days_to_Convert=("Days_to_Convert", "mean")
            )
            merged = pd.merge(lead_grp, sale_grp, on=dimension, how="left").fillna({
                "High_Ticket_Sales": 0,
                "Back_End_Revenue": 0.0,
                "Avg_Days_to_Convert": 0.0
            })
        else:
            merged = lead_grp.copy()
            merged["High_Ticket_Sales"] = 0
            merged["Back_End_Revenue"] = 0.0
            merged["Avg_Days_to_Convert"] = 0.0

        merged["Total_Revenue"] = merged["Front_End_Revenue"] + merged["Back_End_Revenue"]
        merged["Lead_to_Sale_CVR (%)"] = np.where(
            merged["Front_End_Leads"] > 0,
            (merged["High_Ticket_Sales"] / merged["Front_End_Leads"]) * 100,
            0.0
        )
        merged["Revenue_Per_Lead (EPL)"] = np.where(
            merged["Front_End_Leads"] > 0,
            merged["Total_Revenue"] / merged["Front_End_Leads"],
            0.0
        )
        return merged.sort_values(by=["Total_Revenue", "Front_End_Leads"], ascending=[False, False])

    # --- TABS ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 UTM Attribution & ROAS",
        "🎨 Ad Creative (`utm_content`) Deep-Dive",
        "⏱️ Conversion Velocity & Trends",
        "📋 Matched Buyers Explorer"
    ])

    with tab1:
        st.subheader("Full-Funnel Attribution Breakdown")
        dim_map = {
            "UTM Source (Platform / Placement)": "utm_source",
            "UTM Campaign": "utm_campaign",
            "UTM Medium (Ad Set / Audience)": "utm_medium",
            "UTM Content (Ad Creative)": "utm_content",
            "Workshop Funnel (Mango Name)": "Mango Name",
            "Device & Platform": "initiated_platform"
        }
        selected_label = st.selectbox("Group Attribution By:", list(dim_map.keys()))
        dim_col = dim_map[selected_label]

        attr_df = build_attribution_table(dim_col)

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            fig_leads = px.bar(
                attr_df.sort_values("Front_End_Leads", ascending=False).head(12),
                x="Front_End_Leads", y=dim_col, orientation="h",
                title=f"Top 12 {selected_label} by Front-End Leads",
                text_auto=True, color="Front_End_Leads", color_continuous_scale="Blues"
            )
            fig_leads.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_leads, use_container_width=True)

        with col_c2:
            fig_rev = px.bar(
                attr_df.sort_values("Total_Revenue", ascending=False).head(12),
                x=["Front_End_Revenue", "Back_End_Revenue"], y=dim_col, orientation="h",
                title=f"Top 12 {selected_label} by Total Funnel Revenue (FE + BE)",
                labels={"value": "Revenue (₹)", "variable": "Stage"}
            )
            fig_rev.update_layout(yaxis={"categoryorder": "total ascending"}, barmode="stack")
            st.plotly_chart(fig_rev, use_container_width=True)

        st.dataframe(
            attr_df.style.format({
                "Front_End_Leads": "{:,.0f}",
                "Front_End_Revenue": "₹{:,.2f}",
                "High_Ticket_Sales": "{:,.0f}",
                "Back_End_Revenue": "₹{:,.2f}",
                "Total_Revenue": "₹{:,.2f}",
                "Lead_to_Sale_CVR (%)": "{:.2f}%",
                "Revenue_Per_Lead (EPL)": "₹{:,.2f}",
                "Avg_Days_to_Convert": "{:.1f} days"
            }),
            use_container_width=True,
            hide_index=True
        )

    with tab2:
        st.subheader("Winning Ad Creatives (`utm_content`)")
        ad_df = build_attribution_table("utm_content")
        min_leads_filter = st.slider("Minimum Leads per Creative to display in Scatter Matrix:", 5, 200, 20)
        filtered_ads = ad_df[(ad_df["Front_End_Leads"] >= min_leads_filter) & (ad_df["utm_content"] != "Unattributed / Direct")]

        fig_matrix = px.scatter(
            filtered_ads,
            x="Front_End_Leads",
            y="Lead_to_Sale_CVR (%)",
            size="Total_Revenue",
            color="High_Ticket_Sales",
            hover_name="utm_content",
            title="Creative Efficiency Matrix: Lead Volume vs. High-Ticket Conversion Rate (Bubble Size = Total Revenue)",
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_matrix, use_container_width=True)

        st.dataframe(
            ad_df.head(30).style.format({
                "Front_End_Leads": "{:,.0f}",
                "Front_End_Revenue": "₹{:,.2f}",
                "High_Ticket_Sales": "{:,.0f}",
                "Back_End_Revenue": "₹{:,.2f}",
                "Total_Revenue": "₹{:,.2f}",
                "Lead_to_Sale_CVR (%)": "{:.2f}%",
                "Revenue_Per_Lead (EPL)": "₹{:,.2f}",
                "Avg_Days_to_Convert": "{:.1f} days"
            }),
            use_container_width=True,
            hide_index=True
        )

    with tab3:
        st.subheader("Daily Registration Volume & Conversion Velocity")
        if df_leads["Order_DT"].notna().any():
            df_leads["Lead_Date"] = df_leads["Order_DT"].dt.date
            daily_leads = df_leads.groupby("Lead_Date", as_index=False).agg(
                Leads=("clean_email", "count"),
                FE_Revenue=("Mango Price(Sub)", "sum")
            )
            fig_daily = px.area(daily_leads, x="Lead_Date", y="Leads", title="Daily Front-End Workshop Registrations")
            st.plotly_chart(fig_daily, use_container_width=True)

        if has_sales and len(matched_sales_df) > 0:
            c_v1, c_v2 = st.columns(2)
            with c_v1:
                fig_hist = px.histogram(
                    matched_sales_df, x="Days_to_Convert", nbins=15,
                    title="Days from ₹199 Registration to ₹7,999 Purchase",
                    labels={"Days_to_Convert": "Days to Convert"}
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            with c_v2:
                matched_sales_df["Cohort_Lead_Date"] = matched_sales_df["Order_DT"].dt.date
                cohort_df = matched_sales_df.groupby("Cohort_Lead_Date", as_index=False).agg(
                    High_Ticket_Buyers=("clean_email", "count")
                )
                fig_cohort = px.bar(
                    cohort_df, x="Cohort_Lead_Date", y="High_Ticket_Buyers",
                    title="Which Registration Dates Produced the Most ₹7,999 Buyers?"
                )
                st.plotly_chart(fig_cohort, use_container_width=True)

    with tab4:
        if has_sales:
            st.subheader("Attributed High-Ticket Buyers (Customer Journey Table)")
            display_cols = [
                "Name", "Email", "Mobile", "Amount", "Date", "Order_DT",
                "Days_to_Convert", "Matched_Status", "Mango Name",
                "utm_source", "utm_campaign", "utm_medium", "utm_content"
            ]
            st.dataframe(sales_attributed[display_cols], use_container_width=True, hide_index=True)

            csv_bytes = sales_attributed.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Full Attributed Sales Report (CSV)",
                data=csv_bytes,
                file_name="attributed_high_ticket_sales.csv",
                mime="text/csv"
            )
        else:
            st.info("Upload your High-Ticket Sales CSV in the sidebar to inspect individual buyer attribution.")

else:
    st.info("👈 Upload `simplified-1793879554194.xlsx` (Leads) and `Untitled spreadsheet - Sheet1.csv` (High-Ticket Sales) in the sidebar to launch your dashboard.")
