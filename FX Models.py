import os
import pandas as pd
import plotly.express as px
import streamlit as st
from fredapi import Fred
import requests

# ---------- Config ----------
st.set_page_config(page_title="FX Valuation — Models", layout="wide")

DARK_BG = "#0e1014"
PRIMARY_TEXT = "#e5e7eb"

st.markdown(
    f"""
    <style>
      .stApp {{ background-color: {DARK_BG}; color: {PRIMARY_TEXT}; }}
      .sidebar .sidebar-content {{ background-color: {DARK_BG}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Load FRED Key (Env or File) ----------
KEYS_PATH = r"C:\\Users\\nilee\\OneDrive\\Documents\\keys.txt"
fkey = os.getenv("FRED_API_KEY", "")
if not fkey:
    try:
        with open(KEYS_PATH, "r") as f:
            fkey = f.read().strip()
    except Exception as e:
        fkey = ""
        st.error(f"Could not read FRED key from env or {KEYS_PATH}: {e}")

if not fkey:
    st.stop()

fred = Fred(api_key=fkey)

# ---------- Define Indicators (with corrected IDs) ----------
indicators = {
    "Nominal USD/CAD": "DEXCAUS",   # CAD per USD
    "US CPI": "CPIAUCSL",          # US Consumer Price Index
    "Canada CPI": "CANCPIALLMINMEI",  # Canada CPI (monthly, OECD via FRED)
    "US 2Y Yield": "DGS2",         # US 2-Year Treasury Yield
    # Canada 2Y Yield not in FRED directly, using 3-month T-bill as proxy
    "Canada 3M Yield": "IR3TIB01CAM156N",  
    "US Current Account": "BOPBCA", # US Current Account Balance
    "US GDP": "GDP",                # US GDP (quarterly, billions USD)
    "US Unemployment": "UNRATE",    # US Unemployment Rate
    "ISM PMI": "NAPMPI",            # ISM Manufacturing PMI
    "Federal Deficit": "MTSDS133FMS" # Federal Surplus or Deficit
}

# ---------- Functions ----------
@st.cache_data
def fetch_fred_series(series_id, label):
    try:
        data = fred.get_series(series_id)
        df = data.reset_index()
        df.columns = ["Date", label]
        return df
    except Exception as e:
        st.warning(f"Series {series_id} ({label}) not available: {e}")
        return pd.DataFrame(columns=["Date", label])

@st.cache_data
def get_all_indicators():
    df_combined = None
    for label, series_id in indicators.items():
        df = fetch_fred_series(series_id, label)
        df_combined = df if df_combined is None else pd.merge(df_combined, df, on="Date", how="outer")
    df_combined.sort_values("Date", inplace=True)
    return df_combined

# ---------- StatCan API for Canada Current Account ----------
STATCAN_WDS = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorByReferencePeriodRange"

def get_statcan_vector(vector_code: str, start: str, end: str) -> pd.DataFrame:
    vid = str(int(str(vector_code).lower().replace("v", "").strip()))
    params = {"vectorIds": vid, "startRefPeriod": start, "endReferencePeriod": end}
    r = requests.get(STATCAN_WDS, params=params, timeout=30)
    r.raise_for_status()
    resp = r.json()
    entry = resp[0] if isinstance(resp, list) and resp else resp
    obj = entry.get("object", {}) if isinstance(entry, dict) else {}
    datapoints = obj.get("vectorDataPoint", []) if isinstance(obj, dict) else []
    rows = []
    for dp in datapoints:
        ref = dp.get("refPer") or dp.get("refPeriod") or dp.get("REF_DATE")
        val = dp.get("value") or dp.get("VAL") or dp.get("VALUE")
        if ref and val is not None:
            rows.append((pd.to_datetime(ref[:10]), pd.to_numeric(val, errors="coerce")))
    return pd.DataFrame(rows, columns=["Date", vector_code]).dropna()

# (Rest of the valuation models and layout remain unchanged)

# ---------- Valuation Models ----------
def compute_rer(df):
    df = df.dropna(subset=["Nominal USD/CAD", "US CPI", "Canada CPI"])
    us_cpi = (df["US CPI"] / df["US CPI"].iloc[0]) * 100
    ca_cpi = (df["Canada CPI"] / df["Canada CPI"].iloc[0]) * 100
    df["RER_USD/CAD"] = df["Nominal USD/CAD"] * (ca_cpi / us_cpi)
    return df

def compute_ppp(df):
    df = df.dropna(subset=["US CPI", "Canada CPI"])
    df["PPP_USD/CAD"] = df["Canada CPI"] / df["US CPI"]
    return df

def compute_beer(df):
    if "US 2Y Yield" in df.columns and "Canada 2Y Yield" in df.columns:
        spread = df["US 2Y Yield"] - df["Canada 2Y Yield"]
        df["BEER_USD/CAD"] = df["Nominal USD/CAD"].mean() * (1 + spread / 100)
    return df

def compute_feer(df, ca_us, gdp_us, ca_ca):
    df_feer = df.copy()
    if not ca_us.empty and not gdp_us.empty:
        ca_us = pd.merge(ca_us, gdp_us, on="Date", how="inner")
        ca_us["US_CA_pct_GDP"] = (ca_us["US Current Account"] / ca_us["US GDP"]) * 100
        latest_gap = -2 - ca_us["US_CA_pct_GDP"].iloc[-1]
        adj = 1 + (latest_gap * 0.2 / 100)
        df_feer["FEER_USD/CAD"] = df_feer["Nominal USD/CAD"] * adj
        df_feer = pd.merge(df_feer, ca_us[["Date", "US_CA_pct_GDP"]], on="Date", how="left")
    if not ca_ca.empty:
        ca_ca.rename(columns={ca_ca.columns[1]: "Canada_CA"}, inplace=True)
        df_feer = pd.merge(df_feer, ca_ca, on="Date", how="left")
    return df_feer

def compute_yield_spread_model(df):
    if "US 2Y Yield" in df.columns and "Canada 2Y Yield" in df.columns:
        spread = df["US 2Y Yield"] - df["Canada 2Y Yield"]
        if spread.iloc[-1] != 0:
            df["Yield_Spread_Model"] = df["Nominal USD/CAD"].mean() * (1 + spread / 100)
        else:
            df["Yield_Spread_Model"] = None
    return df

# ---------- Date Config ----------
st.sidebar.header("Date Configuration")
manual_start = st.sidebar.text_input("Insert Start Date (YYYY-MM-DD)", "2024-01-01")
manual_end = st.sidebar.text_input("Insert End Date (YYYY-MM-DD)", pd.to_datetime("today").strftime("%Y-%m-%d"))

try:
    start_date = pd.to_datetime(manual_start)
    end_date = pd.to_datetime(manual_end)
except Exception:
    st.error("Invalid date format. Please use YYYY-MM-DD.")
    st.stop()

# ---------- Sidebar Model Selection ----------
st.sidebar.header("Model Selection")
model_choice = st.sidebar.multiselect(
    "Select valuation models to include:",
    ["RER", "PPP", "BEER", "FEER", "Yield_Spread_Model"],
    default=["RER", "PPP"]
)

# ---------- Main Layout ----------
st.title("💱 FX Valuation Dashboard — USD/CAD")
st.markdown("Compare Nominal FX with valuation models: RER, PPP, BEER, FEER, Yield Spread.")

# ---------- Data ----------
with st.spinner("Fetching data from FRED and StatCan..."):
    df = get_all_indicators()
    df = df[(df["Date"] >= start_date) & (df["Date"] <= end_date)]

    ca_us = fetch_fred_series("BOPBCA", "US Current Account")
    gdp_us = fetch_fred_series("GDP", "US GDP")
    ca_ca = get_statcan_vector("498153", start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    if "RER" in model_choice:
        df = compute_rer(df)
    if "PPP" in model_choice:
        df = compute_ppp(df)
    if "BEER" in model_choice:
        df = compute_beer(df)
    if "FEER" in model_choice:
        df = compute_feer(df, ca_us, gdp_us, ca_ca)
    if "Yield_Spread_Model" in model_choice:
        df = compute_yield_spread_model(df)

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Data Table", "Download", "Economics", "Yield Model"])

with tab1:
    cols_to_plot = ["Nominal USD/CAD"] + [c for c in df.columns if any(m in c for m in model_choice)]
    fig = px.line(
        df, x="Date", y=cols_to_plot,
        labels={"value": "Rate", "Date": "Date", "variable": "Series"}
    )
    fig.update_layout(template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.dataframe(df.tail(24))

with tab3:
    st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode("utf-8"), "usd_cad_valuation.csv", "text/csv")

with tab4:
    st.subheader("🌍 Economic Indicators")
    econ_series = ["US GDP", "US Unemployment", "US CPI", "ISM PMI", "Federal Deficit"]
    for series in econ_series:
        if series in df.columns:
            sub_df = df[["Date", series]].dropna()
            sub_df = sub_df[(sub_df["Date"] >= start_date) & (sub_df["Date"] <= end_date)]
            if not sub_df.empty:
                fig_econ = px.line(sub_df, x="Date", y=series, title=series)
                fig_econ.update_layout(template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG)
                st.plotly_chart(fig_econ, use_container_width=True)

    ca_us = ca_us[(ca_us["Date"] >= start_date) & (ca_us["Date"] <= end_date)]
    if not ca_us.empty:
        fig_ca = px.line(ca_us, x="Date", y="US Current Account", title="US Current Account (Billions USD)")
        fig_ca.update_layout(template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG)
        st.plotly_chart(fig_ca, use_container_width=True)
    ca_ca = ca_ca[(ca_ca["Date"] >= start_date) & (ca_ca["Date"] <= end_date)]
    if not ca_ca.empty:
        fig_ca2 = px.line(ca_ca, x="Date", y=ca_ca.columns[1], title="Canada Current Account (Millions CAD)")
        fig_ca2.update_layout(template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG)
        st.plotly_chart(fig_ca2, use_container_width=True)

with tab5:
    st.subheader("📊 Yield Spread Model")
    if "Yield_Spread_Model" in df.columns and df["Yield_Spread_Model"].notna().any():
        fig_yield = px.line(df, x="Date", y="Yield_Spread_Model", title="USD/CAD Valuation from Yield Spread")
        fig_yield.update_layout(template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG)
        st.plotly_chart(fig_yield, use_container_width=True)
        st.dataframe(df[["Date", "Yield_Spread_Model"]].dropna().tail(24))
    else:
        st.warning("Yield spread model not available (spread = 0).")

# ---------- Project Notes ----------
st.markdown("---")
st.subheader("📋 Project Task Notes")
task1 = st.checkbox("Refine BEER regression with oil, productivity, NFA data")
task2 = st.checkbox("Enhance FEER with dynamic trade elasticities")
task3 = st.checkbox("Add more FX pairs (EUR/USD, GBP/USD, etc.)")

if task1:
    st.success("BEER model regression refinement task checked!")
