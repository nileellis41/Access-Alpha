import os
from datetime import date

import streamlit as st
import pandas as pd
import numpy as np

import plotly.express as px
import plotly.graph_objects as go
from fredapi import Fred

# ---------------------------
# Page Config
# ---------------------------
st.set_page_config(
    page_title="Economic Dashboard — Retail Sales & H.8 (Bank Lending)",
    page_icon="📊",
    layout="wide",
)

# Global Plotly template for dark mode
px.defaults.template = "plotly_dark"

# ---------------------------
# Load FRED Key (env or simple file) — simple & direct
# ---------------------------
KEYS_PATH = r"C:\\Users\\nilee\\OneDrive\\Documents\\keys.txt"
fkey = os.getenv("FRED_API_KEY", "")
if not fkey:
    try:
        with open(KEYS_PATH, "r") as f:
            fkey = f.read().strip()
    except Exception:
        fkey = ""

if not fkey:
    st.error("Missing FRED API key. Set FRED_API_KEY env var or place it in keys.txt.")
    st.stop()

fred = Fred(api_key=fkey)

# ---------------------------
# Helpers — keep it simple
# ---------------------------
@st.cache_data(show_spinner=False)
def fetch_fred_series(series_id: str, label: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Fetch a single FRED series (optionally bounded by start/end) and return a 2-col DataFrame [Date, label]."""
    try:
        s = fred.get_series(series_id, observation_start=start, observation_end=end)
        df = s.to_frame(name=label).reset_index()
        df.columns = ["Date", label]
        return df
    except Exception as e:
        st.warning(f"Could not fetch {series_id}: {e}")
        return pd.DataFrame(columns=["Date", label])

@st.cache_data(show_spinner=False)
def fetch_many(series_map: dict[str, str], start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Fetch many FRED series given a dict {label: series_id}. Returns a wide DataFrame indexed by Date."""
    frames = []
    for label, sid in series_map.items():
        df = fetch_fred_series(sid, label, start, end)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for nxt in frames[1:]:
        out = out.merge(nxt, on="Date", how="outer")
    out.sort_values("Date", inplace=True)
    out.set_index("Date", inplace=True)
    return out

def daterange_defaults():
    # default: last 5 years
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=5)
    return start.date(), end.date()

def to_csv_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=True).encode("utf-8")

def growth_rates(df: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for col in df.columns:
        s = df[col].dropna()
        if len(s) < 3:
            continue
        mom = s.pct_change(1) * 100.0
        mom.name = f"{col} — Δ% (prev period)"
        yoy = s.pct_change(12) * 100.0 if s.index.inferred_freq in ("M", "MS") else s.pct_change(52) * 100.0
        yoy.name = f"{col} — Δ% (YoY/YoY*)"
        out[mom.name] = mom
        out[yoy.name] = yoy
    if not out:
        return pd.DataFrame(index=df.index)
    return pd.concat(out.values(), axis=1)

# ---------------------------
# Presets
# ---------------------------
RETAIL_PRESETS = {
    "Advance Retail & Food Services Sales (Total)": "RSAFS",
    "Advance Retail Sales excl. Motor Vehicles & Parts": "RSXFS",
    "Advance Retail Sales: Nonstore Retailers (e-commerce)": "RSEASNRRSA",
    "Advance Retail Sales: Food Services & Drinking Places": "RSEFDPNA",
    "Advance Retail Sales: Gasoline Stations": "RSEASGASS",
    "Advance Retail Sales: General Merchandise Stores": "RSEASGMS",
}

H8_PRESETS = {
    "Total Bank Credit": "TBCBST",
    "Securities (All)": "SABST",
    "Loans & Leases in Bank Credit (Total)": "TOTLL",
    "Commercial & Industrial Loans": "BUSLOANS",
    "Real Estate Loans": "REALLN",
    "Consumer Loans": "CONSUMER",
    "Deposits (Total)": "DPSACBW027SBOG",
    "Cash Assets": "CASACBW027SBOG",
}

# ---------------------------
# Sidebar — simple date inputs wired straight into pulls
# ---------------------------
st.sidebar.title("⚙️ Settings")

# Date range (directly used in fetch functions)
default_start, default_end = daterange_defaults()
start_date = st.sidebar.date_input("Start date", value=default_start, max_value=date.today())
end_date = st.sidebar.date_input("End date", value=default_end, min_value=start_date, max_value=date.today())

# Optional: single as-of date (overrides end if provided)
asof_toggle = st.sidebar.checkbox("Use a single 'as-of' date (ignore start)")
asof_date = None
if asof_toggle:
    asof_date = st.sidebar.date_input("As-of date", value=end_date, max_value=date.today())

# Compute effective bounds
obs_start = None if asof_toggle else str(start_date)
obs_end = str(asof_date if asof_date else end_date)

# ---------------------------
# Header
# ---------------------------
st.title("📊 Economic Dashboard — Retail Spending & Bank Lending (H.8)")
st.caption("Date filters are passed **directly** into the FRED pulls.")

# Tabs
_tab_names = ["Overview", "Retail Sales", "Bank Lending (H.8)", "Compare", "Correlations", "Downloads"]
(tab_overview, tab_retail, tab_h8, tab_compare, tab_corr, tab_downloads) = st.tabs(_tab_names)

# ---------------------------
# Overview
# ---------------------------
with tab_overview:
    st.subheader("Quick Peek")
    colA, colB = st.columns(2)

    with colA:
        st.markdown("**Retail Spotlight**")
        retail_selected = st.multiselect(
            "Retail series (presets)",
            list(RETAIL_PRESETS.keys()),
            default=[
                "Advance Retail & Food Services Sales (Total)",
                "Advance Retail Sales excl. Motor Vehicles & Parts",
            ],
        )
        if retail_selected:
            retail_map = {k: RETAIL_PRESETS[k] for k in retail_selected}
            retail_df = fetch_many(retail_map, obs_start, obs_end)
            if not retail_df.empty:
                fig = px.line(retail_df, labels={"value": "USD (Millions)", "index": "Date"})
                fig.update_layout(height=360, legend_title_text="Series")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(retail_df.tail(6), use_container_width=True)
            else:
                st.info("No retail data for the current date filter.")

    with colB:
        st.markdown("**Bank Lending Spotlight (H.8)**")
        h8_selected = st.multiselect(
            "H.8 series (presets)",
            list(H8_PRESETS.keys()),
            default=[
                "Loans & Leases in Bank Credit (Total)",
                "Commercial & Industrial Loans",
                "Deposits (Total)",
            ],
        )
        if h8_selected:
            h8_map = {k: H8_PRESETS[k] for k in h8_selected}
            h8_df = fetch_many(h8_map, obs_start, obs_end)
            if not h8_df.empty:
                fig = px.line(h8_df, labels={"value": "USD (Billions)", "index": "Date"})
                fig.update_layout(height=360, legend_title_text="Series")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(h8_df.tail(10), use_container_width=True)
            else:
                st.info("No H.8 data for the current date filter.")

    st.markdown("---")
    st.markdown("**Add Custom FRED Series**")
    with st.expander("Add custom series by ID (optional)"):
        custom_ids = st.text_input("Custom FRED IDs (comma-separated)", value="")
        if custom_ids.strip():
            ids = [s.strip() for s in custom_ids.split(",") if s.strip()]
            cmap = {sid: sid for sid in ids}
            # Use IDs as labels for customs
            cdf = fetch_many(cmap, obs_start, obs_end)
            if not cdf.empty:
                st.success(f"Loaded {len(cdf.columns)} custom series.")
                st.dataframe(cdf.tail(10), use_container_width=True)
                cfig = px.line(cdf, labels={"value": "Value", "index": "Date"})
                cfig.update_layout(height=340, legend_title_text="Series")
                st.plotly_chart(cfig, use_container_width=True)
            else:
                st.warning("No data retrieved for the provided IDs.")

# ---------------------------
# Retail Tab
# ---------------------------
with tab_retail:
    st.subheader("Advance Retail & Food Services Sales (Monthly)")
    left, right = st.columns([1, 1])

    with left:
        retail_choices = st.multiselect(
            "Choose retail categories",
            list(RETAIL_PRESETS.keys()),
            default=list(RETAIL_PRESETS.keys())[:3],
        )
        retail_map = {k: RETAIL_PRESETS[k] for k in retail_choices}
        if retail_map:
            rdf = fetch_many(retail_map, obs_start, obs_end)
            if not rdf.empty:
                tabsR = st.tabs(["Levels", "Growth (%)"])
                with tabsR[0]:
                    fig1 = px.line(rdf, labels={"value": "USD (Millions)", "index": "Date"})
                    fig1.update_layout(height=520, legend_title_text="Series")
                    st.plotly_chart(fig1, use_container_width=True)
                    st.caption("Levels are seasonally adjusted where applicable.")
                with tabsR[1]:
                    g = growth_rates(rdf)
                    if not g.empty:
                        fig2 = px.line(g, labels={"value": "%", "index": "Date"})
                        fig2.update_layout(height=520, legend_title_text="Series")
                        st.plotly_chart(fig2, use_container_width=True)
                        st.caption("MoM/YoY computed from adjacent periods; YoY assumes monthly frequency.")
                    else:
                        st.info("Not enough data to compute growth rates.")

    with right:
        st.markdown("**Retail Notes**")
        st.write(
            """
            - *Advance* retail sales data provides an early read on monthly spending trends.
            - Ex-Autos (RSXFS) reduces volatility from vehicle purchases.
            - Nonstore retailers proxy **e-commerce** momentum.
            - Food services & drinking places can proxy discretionary services strength.
            """
        )

# ---------------------------
# H.8 Tab
# ---------------------------
with tab_h8:
    st.subheader("Bank Lending & Balance Sheet (H.8 — All Commercial Banks, Weekly)")
    c1, c2 = st.columns([1, 1])

    with c1:
        h8_choices = st.multiselect(
            "Choose H.8 aggregates",
            list(H8_PRESETS.keys()),
            default=[
                "Loans & Leases in Bank Credit (Total)",
                "Commercial & Industrial Loans",
                "Deposits (Total)",
            ],
        )
        h8_map = {k: H8_PRESETS[k] for k in h8_choices}
        if h8_map:
            h8df = fetch_many(h8_map, obs_start, obs_end)
            if not h8df.empty:
                tabsH = st.tabs(["Levels", "Growth (%)"])
                with tabsH[0]:
                    figh1 = px.line(h8df, labels={"value": "USD (Billions)", "index": "Date"})
                    figh1.update_layout(height=520, legend_title_text="Series")
                    st.plotly_chart(figh1, use_container_width=True)
                with tabsH[1]:
                    gh = growth_rates(h8df)
                    if not gh.empty:
                        figh2 = px.line(gh, labels={"value": "%", "index": "Date"})
                        figh2.update_layout(height=520, legend_title_text="Series")
                        st.plotly_chart(figh2, use_container_width=True)
                        st.caption("YoY proxy uses 52-week change for weekly series.")
                    else:
                        st.info("Not enough data to compute growth rates.")

    with c2:
        st.markdown("**H.8 Notes**")
        st.write(
            """
            - **Loans & Leases** and **C&I Loans** track credit creation to firms.
            - **Deposits** and **Cash Assets** offer color on liquidity conditions.
            - Combine with retail sales to assess the **credit-spend feedback loop**.
            """
        )

# ---------------------------
# Compare Tab
# ---------------------------
with tab_compare:
    st.subheader("Side-by-Side Comparison")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Pick one Retail series**")
        r_opt = st.selectbox("Retail series", list(RETAIL_PRESETS.keys()))
    with col2:
        st.markdown("**Pick one H.8 series**")
        h_opt = st.selectbox("H.8 series", list(H8_PRESETS.keys()))

    r_df = fetch_many({r_opt: RETAIL_PRESETS[r_opt]}, obs_start, obs_end)
    h_df = fetch_many({h_opt: H8_PRESETS[h_opt]}, obs_start, obs_end)
    if not r_df.empty and not h_df.empty:
        joint = pd.concat([r_df, h_df], axis=1).dropna()
        norm = joint / joint.iloc[0] * 100.0
        figC = px.line(norm, labels={"value": "Index (Start=100)", "index": "Date"})
        figC.update_layout(height=520, legend_title_text="Series")
        st.plotly_chart(figC, use_container_width=True)
        st.caption("Both series are indexed to 100 at the first common date to compare trends.")
    else:
        st.info("Missing one or both series for the current date filter.")

# ---------------------------
# Correlations Tab
# ---------------------------
with tab_corr:
    st.subheader("Rolling Correlations (β-style intuition)")
    st.markdown("Select multiple retail and H.8 series, then compute rolling correlations on percent changes.")
    width = st.slider("Rolling window (periods)", min_value=8, max_value=52, value=26, step=2)
    sel_retail = st.multiselect(
        "Retail series for correlation",
        list(RETAIL_PRESETS.keys()),
        default=[
            "Advance Retail & Food Services Sales (Total)",
            "Advance Retail Sales excl. Motor Vehicles & Parts",
        ],
    )
    sel_h8 = st.multiselect(
        "H.8 series for correlation",
        list(H8_PRESETS.keys()),
        default=[
            "Loans & Leases in Bank Credit (Total)",
            "Commercial & Industrial Loans",
            "Deposits (Total)",
        ],
    )

    if sel_retail and sel_h8:
        rmap = {k: RETAIL_PRESETS[k] for k in sel_retail}
        hmap = {k: H8_PRESETS[k] for k in sel_h8}
        r_df = fetch_many(rmap, obs_start, obs_end)
        h_df = fetch_many(hmap, obs_start, obs_end)
        if not r_df.empty and not h_df.empty:
            r_chg = r_df.pct_change().dropna()
            h_chg = h_df.pct_change().dropna()
            al = r_chg.join(h_chg, how="inner")
            corr_series = {}
            for rc in r_df.columns:
                for hc in h_df.columns:
                    pair = al[[rc, hc]].dropna()
                    if len(pair) >= width + 5:
                        roll = pair[rc].rolling(width).corr(pair[hc])
                        roll.name = f"{rc} vs {hc} (rolling {width})"
                        corr_series[roll.name] = roll
            if corr_series:
                corr_df = pd.concat(corr_series.values(), axis=1).dropna(how="all")
                figCorr = px.line(corr_df, labels={"value": "Correlation", "index": "Date"})
                figCorr.update_layout(height=540, legend_title_text="Pairs")
                st.plotly_chart(figCorr, use_container_width=True)
                st.dataframe(corr_df.tail(10), use_container_width=True)
            else:
                st.info("Not enough overlapping history to compute rolling correlations for the chosen window.")
        else:
            st.info("Could not fetch both retail and H.8 selections.")
    else:
        st.info("Add at least one series in each group.")

# ---------------------------
# Downloads Tab
# ---------------------------
with tab_downloads:
    st.subheader("Download Data")
    st.markdown("Pick any mix of retail, H.8, and custom series to export a single CSV.")
    dl_retail = st.multiselect("Retail for export", list(RETAIL_PRESETS.keys()))
    dl_h8 = st.multiselect("H.8 for export", list(H8_PRESETS.keys()))
    dl_custom = st.text_input("Additional FRED IDs (comma-separated)", "")

    if dl_retail or dl_h8 or dl_custom.strip():
        all_map = {}
        all_map.update({k: RETAIL_PRESETS[k] for k in dl_retail})
        all_map.update({k: H8_PRESETS[k] for k in dl_h8})
        custom_ids = [s.strip() for s in dl_custom.split(",") if s.strip()]
        all_map.update({sid: sid for sid in custom_ids})

        df_all = fetch_many(all_map, obs_start, obs_end)
        if not df_all.empty:
            st.dataframe(df_all.tail(12), use_container_width=True)
            st.download_button(
                label="⬇️ Download CSV",
                data=to_csv_download(df_all),
                file_name=f"economic_dashboard_{obs_start or 'START'}_to_{obs_end}.csv",
                mime="text/csv",
            )
        else:
            st.info("Nothing to export for the current date filter.")
    else:
        st.info("Select series to export.")

# ---------------------------
# Footer
# ---------------------------
st.markdown("---")
st.caption("Dates feed directly into FRED calls (observation_start / observation_end). Edit presets at top to add more series.")

# --- Add this near your other PRESETS ---
MACRO_PRESETS = {
    # Prices/Inflation (monthly)
    "CPI (All Items, SA)": "CPIAUCSL",
    "Core CPI (SA)": "CPILFESL",
    "PCE Price Index": "PCEPI",
    "Core PCE": "PCEPILFE",

    # Labor (monthly/weekly)
    "Unemployment Rate": "UNRATE",
    "Nonfarm Payrolls (Total)": "PAYEMS",
    "Initial Claims (Weekly)": "ICSA",

    # Growth/Income/Spending
    "Real GDP (Quarterly, SAAR)": "GDPC1",
    "Real Personal Income ex Transfers": "W875RX1",
    "Real Personal Consumption Expenditures": "PCEC96",

    # Surveys / Sentiment
    "ISM Manufacturing PMI": "NAPM",
    "ISM Services PMI": "NMFBS",
    "UMich Consumer Sentiment": "UMCSENT",

    # Rates / Curve
    "10Y Treasury Yield": "DGS10",
    "2Y Treasury Yield": "DGS2",
}

# --- Update your tab list to include "Macro" ---
(tab_overview, tab_retail, tab_h8, tab_macro, tab_compare, tab_corr, tab_downloads) = st.tabs(
    ["Overview", "Retail Sales", "Bank Lending (H.8)", "Macro", "Compare", "Correlations", "Downloads"]
)

# --- Macro Tab ---
with tab_macro:
    st.subheader("Macro Dashboard")
    c1, c2 = st.columns(2)

    with c1:
        macro_sel = st.multiselect(
            "Select macro indicators",
            list(MACRO_PRESETS.keys()),
            default=[
                "CPI (All Items, SA)",
                "Unemployment Rate",
                "Nonfarm Payrolls (Total)",
                "10Y Treasury Yield",
            ],
        )
        if macro_sel:
            m_map = {k: MACRO_PRESETS[k] for k in macro_sel}
            mdf = fetch_many(m_map, obs_start, obs_end)
            if not mdf.empty:
                lvl_fig = px.line(mdf, labels={"value": "Level", "index": "Date"})
                lvl_fig.update_layout(height=520, legend_title_text="Series")
                st.plotly_chart(lvl_fig, use_container_width=True)
                st.dataframe(mdf.tail(10), use_container_width=True)
            else:
                st.info("No macro data for the current date filter.")

    with c2:
        st.markdown("**Growth & Spreads**")
        if macro_sel:
            m_map = {k: MACRO_PRESETS[k] for k in macro_sel}
            mdf = fetch_many(m_map, obs_start, obs_end)
            if not mdf.empty:
                g = growth_rates(mdf)
                if not g.empty:
                    gfig = px.line(g, labels={"value": "%", "index": "Date"})
                    gfig.update_layout(height=380, legend_title_text="Series")
                    st.plotly_chart(gfig, use_container_width=True)
                else:
                    st.info("Not enough data for growth rates.")

                # Yield curve (10Y - 2Y) if both are available
                if {"10Y Treasury Yield", "2Y Treasury Yield"}.issubset(set(mdf.columns)):
                    curve = (mdf["10Y Treasury Yield"] - mdf["2Y Treasury Yield"]).rename("10Y–2Y Term Spread")
                    cfig = px.line(curve, labels={"value": "Pct Points", "index": "Date"})
                    cfig.update_layout(height=140, legend_title_text="")
                    st.plotly_chart(cfig, use_container_width=True)
                    st.caption("Term spread (DGS10 − DGS2). Negative values indicate inversion.")
            else:
                st.info("No macro data for the current date filter.")
