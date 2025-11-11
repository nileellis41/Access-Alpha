# FRED vs StatCan — CFA Econ Dashboard (Streamlit)
# -------------------------------------------------
# Install deps (first run):
#   pip install streamlit requests pandas numpy plotly python-dateutil
# 
# How to run:
#   streamlit run fred_statcan_cfa.py
# 
# Notes:
# - Set your FRED API key via environment variable FRED_API_KEY or the sidebar input.
# - StatCan WDS (Web Data Service) does not require an API key.
# - Charts default to a dark theme.
# - This dashboard compares classic CFA macro indicators between the U.S. (FRED) and Canada (StatCan vectors).
#   You can keep extending the SERIES_MAP below — or use the "extra vectors" box to overlay any StatCan vector(s).

import os
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.express as px

# ---------- Page Config & Dark Styling ----------
st.set_page_config(page_title="FRED vs StatCan — CFA Econ Dashboard", layout="wide")

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

# ---------- Helper: Plotly dark template ----------

def _darken(fig, title=None):
    fig.update_layout(template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG)
    if title:
        fig.update_layout(title=title)
    return fig

# ---------- Data access: FRED ----------
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES_META = "https://api.stlouisfed.org/fred/series"

@st.cache_data(show_spinner=False)
def fred_observations(series_id: str, start: str, end: str, api_key: str) -> pd.DataFrame:
    """Fetch monthly observations for a FRED series. start/end: 'YYYY-MM' strings."""
    params = {
        "series_id": series_id,
        "api_key": fred_key,
        "observation_start": f"{start}-01",
        "observation_end": f"{end}-28",
        "frequency": "m",
        "file_type": "json",
        "units": "lin",
    }
    r = requests.get(FRED_BASE, params=params, timeout=30)
    r.raise_for_status()
    j = r.json()
    obs = pd.DataFrame(j.get("observations", []))
    if obs.empty:
        return pd.DataFrame(columns=["date", "value"]).assign(source="FRED", series=series_id)
    obs["date"] = pd.to_datetime(obs["date"]).dt.tz_localize(None)
    # Numeric coercion; FRED sometimes uses '.' for missing values
    obs["value"] = pd.to_numeric(obs["value"], errors="coerce")
    obs = obs[["date", "value"]].rename(columns={"value": series_id}).set_index("date").sort_index()
    obs["source"] = "FRED"
    obs["series"] = series_id
    return obs

@st.cache_data(show_spinner=False)
def fred_series_title(series_id: str, api_key: str) -> str:
    try:
        params = {"series_id": series_id, "api_key": fred_key, "file_type": "json"}
        r = requests.get(FRED_SERIES_META, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        items = j.get("seriess", []) or j.get("series", [])
        if items:
            return items[0].get("title", series_id)
    except Exception:
        pass
    return series_id

# ---------- Data access: Statistics Canada WDS (Vectors) ----------
# Docs: https://www.statcan.gc.ca/en/developers/wds/user-guide  
# Method used: getDataFromVectorByReferencePeriodRange
STATCAN_WDS = "https://www150.statcan.gc.ca/t1/wds/rest"

@st.cache_data(show_spinner=False)
def statcan_vector_by_ref_period(vector_code: str, start: str, end: str) -> pd.DataFrame:
    """Fetch StatCan *vector* data for a reference period range (YYYY-MM to YYYY-MM).
    Accepts vectors like 'v41690973' or '41690973'. Returns DataFrame indexed by datetime.
    """
    # sanitize vector id -> digits only string (StatCan expects without the 'v')
    vid = str(int(str(vector_code).lower().replace("v", "").strip()))

    def _norm_ref(s: str) -> str:
        # WDS expects YYYY-MM-DD; use first of month if YYYY-MM
        s = s.strip()
        if len(s) == 7:
            return s + "-01"
        if len(s) == 10:
            return s
        if len(s) == 4:
            return s + "-01-01"
        return s

    params = {
        "vectorIds": vid,
        "startRefPeriod": _norm_ref(start),
        "endReferencePeriod": _norm_ref(end),
    }

    url = f"{STATCAN_WDS}/getDataFromVectorByReferencePeriodRange"
    try:
        r = requests.get(url, params=params, timeout=30)
        # During ~00:00–08:30 ET some methods may return 409 while tables are locked
        if r.status_code == 409:
            raise RuntimeError(
                "StatCan WDS temporarily unavailable (HTTP 409) during nightly update window. Try again after 08:30 ET."
            )
        r.raise_for_status()
        resp = r.json()
    except Exception as e:
        raise RuntimeError(f"StatCan request failed: {e}")

    entry = resp[0] if isinstance(resp, list) and resp else resp
    obj = entry.get("object", {}) if isinstance(entry, dict) else {}
    datapoints = obj.get("vectorDataPoint", []) if isinstance(obj, dict) else []

    rows = []
    for dp in datapoints:
        ref = dp.get("refPer") or dp.get("refPeriod") or dp.get("REF_DATE")
        val = dp.get("value") or dp.get("VAL") or dp.get("VALUE")
        if not ref:
            continue
        try:
            dt = datetime.strptime(ref[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        rows.append((dt, pd.to_numeric(val, errors="coerce")))

    df = pd.DataFrame(rows, columns=["date", vector_code]).dropna()
    if df.empty:
        return pd.DataFrame(columns=[vector_code]).assign(source="StatCan").set_index(pd.to_datetime([]))
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df.set_index("date").sort_index()
    df["source"] = "StatCan"
    return df

# ---------- CFA helpers ----------

def pct_yoy(s: pd.Series) -> pd.Series:
    return (s / s.shift(12) - 1.0) * 100.0


def pct_qoq_annualized(s: pd.Series) -> pd.Series:
    # For monthly series, use 3m/3m annualized; for quarterly series it's QoQ annualized
    return ((s / s.shift(3)) ** 4 - 1.0) * 100.0


def rebase_100(s: pd.Series) -> pd.Series:
    base = s.dropna().iloc[0] if not s.dropna().empty else np.nan
    return (s / base) * 100.0 if pd.notna(base) else s


def cross_correlation(a: pd.Series, b: pd.Series, max_lag: int = 12):
    """Return DataFrame of lags (negative = a leads b) and correlations."""
    out = []
    a, b = a.dropna(), b.dropna()
    idx = a.index.intersection(b.index)
    a, b = a.loc[idx], b.loc[idx]
    for lag in range(-max_lag, max_lag + 1):
        if lag > 0:
            corr = a.corr(b.shift(lag))
        else:
            corr = a.shift(-lag).corr(b)
        out.append({"lag": lag, "corr": corr})
    df = pd.DataFrame(out)
    best = df.iloc[df["corr"].abs().argmax()] if not df.empty else {"lag": np.nan, "corr": np.nan}
    return df, best


def rolling_zscore(s: pd.Series, window: int = 13) -> pd.Series:
    m = s.rolling(window).mean()
    sd = s.rolling(window).std()
    return (s - m) / sd


def rolling_corr(a: pd.Series, b: pd.Series, window: int = 24) -> pd.Series:
    idx = a.index.intersection(b.index)
    return a.loc[idx].rolling(window).corr(b.loc[idx])

# ---------- Default mappings (extensible) ----------
# Verified vectors/series:
#  - Canada CPI all-items:            v41690973  (StatCan; CPI all-items)  
#  - Canada Unemployment rate:        v2062815   (StatCan; LFS, SA)  
#  - Canada Participation rate:       v2062816   (StatCan; LFS, SA)  
#  - Canada Bank rate (monthly):      v122530    (BoC/StatCan)  
#  - Canada 10Y benchmark yield (m):  v122543    (BoC benchmark monthly)  
#  - Canada 2Y benchmark yield (m):   v122538    (BoC benchmark monthly)  
#  - Canada 3M T-bill (monthly):      v122531    (BoC/StatCan)  
#  - US CPI:                          CPIAUCSL  
#  - US Unemployment Rate:            UNRATE  
#  - US Participation Rate:           CIVPART  
#  - US Fed Funds:                    FEDFUNDS  
#  - US 10Y:                          DGS10  
#  - US 2Y:                           DGS2  
#  - US 3M T-bill:                    TB3MS  
#  - US 10Y-2Y spread:                T10Y2Y

SERIES_MAP = {
    "Inflation (CPI, all items)": {
        "US_FRED": "CPIAUCSL",
        "CA_STATCAN": "v41690973",
        "transform": "yoy",
    },
    "Unemployment rate": {
        "US_FRED": "UNRATE",
        "CA_STATCAN": "v2062815",
        "transform": "level",
    },
    "Participation rate": {
        "US_FRED": "CIVPART",
        "CA_STATCAN": "v2062816",
        "transform": "level",
    },
    "Policy rate (Fed Funds vs BoC bank rate)": {
        "US_FRED": "FEDFUNDS",
        "CA_STATCAN": "v122530",
        "transform": "level",
    },
    "10Y government yield": {
        "US_FRED": "DGS10",
        "CA_STATCAN": "v122543",
        "transform": "level",
    },
    "2Y government yield": {
        "US_FRED": "DGS2",
        "CA_STATCAN": "v122538",
        "transform": "level",
    },
    "3M T-bill": {
        "US_FRED": "TB3MS",
        "CA_STATCAN": "v122531",
        "transform": "level",
    },
    "Yield curve (10Y–2Y spread)": {
        "US_FRED": "T10Y2Y",   # percentage points
        "CA_STATCAN": "v122543_minus_v122538",  # handled specially below
        "transform": "level",
    },
}

CFA_NOTES = {
    "Inflation (CPI, all items)": (
        "Headline CPI is usually coincident/lagging. Use YoY and 3m/3m annualized to spot turning points; compare breadth across baskets if needed."
    ),
    "Unemployment rate": (
        "Lagging indicator; often peaks after recessions. Pair with CPI to sketch a simple Phillips-curve view over the last 3–5 years."
    ),
    "Participation rate": (
        "Structural participation shifts can distort unemployment signals; tracking participation helps interpret labour-market slack."
    ),
    "Policy rate (Fed Funds vs BoC bank rate)": (
        "Policy rates transmit via bank funding costs, mortgage rates, FX and risk premia. Diverging stances can pressure USD/CAD."
    ),
    "10Y government yield": (
        "Long rates embed term premia + expected short-rate paths. US–Canada 10Y spreads reflect growth/inflation differentials and capital flows."
    ),
    "2Y government yield": (
        "2Y is a clean proxy for policy path expectations; compare levels/changes to read the policy-rate outlook gap."
    ),
    "3M T-bill": (
        "Short bills anchor the front end of the curve and track policy closely; use with 10Y to assess curve slope/steepening vs inversion."
    ),
    "Yield curve (10Y–2Y spread)": (
        "The 10s–2s slope (pp) is a popular recession signal once sustained inversion occurs; compare timing vs subsequent labour-market weakness."
    ),
}

# ---------- Sidebar Controls ----------
st.sidebar.title("⚙️ Controls")
module = st.sidebar.selectbox("Metric", list(SERIES_MAP.keys()))
transform_default = SERIES_MAP[module]["transform"]
transform = st.sidebar.selectbox(
    "Transform", ["level", "yoy", "3m/3m ann."], index=["level", "yoy", "3m/3m ann."].index(transform_default)
)

# ---------- Load FRED Key (Env, File, or Sidebar Input) ----------
st.sidebar.markdown("### 🔑 FRED API Key")

# Define a safe default first — so it's always defined
fred_key = ""

# 1️⃣ Try loading from environment variable
if os.getenv("FRED_API_KEY"):
    fred_key = os.getenv("FRED_API_KEY")

# 2️⃣ Try loading from file if not found
else:
    try:
        KEYS_PATH = os.path.expanduser(r"C:\Users\nilee\Sharia\keys.txt")  # cross-platform safe path
        if os.path.exists(KEYS_PATH):
            with open(KEYS_PATH, "r") as f:
                fred_key = f.read().strip()
    except Exception as e:
        st.sidebar.warning(f"Error reading key file: {e}")

# 3️⃣ Let user manually input or override via sidebar
fred_key = st.sidebar.text_input(
    "Enter your FRED API Key",
    value=fred_key or st.session_state.get("fred_key", ""),
    type="password",
    help="Paste your FRED API key here. You can get one from https://fred.stlouisfed.org/"
)

# 4️⃣ Save to Streamlit session state
if fred_key:
    st.session_state["fred_key"] = fred_key

# 5️⃣ Stop app if no valid key
if not fred_key:
    st.sidebar.error("⚠️ Please enter your FRED API key to continue.")
    st.stop()

st.sidebar.checkbox("Smooth (3-month MA)", key="smooth3", value=False)

min_start = date(1990, 1, 1)
end_default = date.today().replace(day=1)
start_default = end_default - relativedelta(years=10)

start_date = st.sidebar.date_input("Start (YYYY-MM)", value=start_default, min_value=min_start, max_value=end_default)
end_date = st.sidebar.date_input("End (YYYY-MM)", value=end_default, min_value=min_start, max_value=end_default)


st.sidebar.markdown("---")
user_vectors = st.sidebar.text_input(
    "StatCan extra vectors (comma-separated v#)",
    value="",
    help="Optional: add more Canadian vectors to overlay (e.g., v41690973).",
)

# ---------- Data fetch ----------
period_start = start_date.strftime("%Y-%m")
period_end = end_date.strftime("%Y-%m")

us_id = SERIES_MAP[module]["US_FRED"]
ca_key = SERIES_MAP[module]["CA_STATCAN"]

if not fred_key:
    st.warning("Enter your FRED API key in the sidebar to fetch US series.")

# Fetch US
us_df = fred_observations(us_id, period_start, period_end, fred_key) if fred_key else pd.DataFrame()
if not us_df.empty:
    us_title = fred_series_title(us_id, fred_key)
else:
    us_title = us_id

# Fetch Canada (handle special modules if needed)
if module == "Yield curve (10Y–2Y spread)":
    # Canada 10Y minus 2Y using StatCan vectors
    ca10 = statcan_vector_by_ref_period("v122543", period_start, period_end)
    ca02 = statcan_vector_by_ref_period("v122538", period_start, period_end)
    cad = (
        pd.concat([ca10["v122543"], ca02["v122538"]], axis=1)
        .rename(columns={"v122543": "CA10", "v122538": "CA02"})
    )
    cad["Canada"] = cad["CA10"] - cad["CA02"]
    ca_df = cad[["Canada"]]
    ca_vec_label = "10Y-2Y (pp)"
else:
    ca_df = statcan_vector_by_ref_period(ca_key, period_start, period_end)
    ca_vec_label = ca_key

# Optional extra Canadian vectors
extra = []
if user_vectors.strip():
    for vec in [v.strip() for v in user_vectors.split(",") if v.strip()]:
        try:
            extra.append(statcan_vector_by_ref_period(vec, period_start, period_end))
        except Exception as e:
            st.sidebar.error(f"Failed to fetch {vec}: {e}")

# ---------- Transformations ----------

def apply_transform(df: pd.DataFrame, series_col: str, mode: str) -> pd.Series:
    s = df[series_col].astype(float)
    if st.session_state.get("smooth3"):
        s = s.rolling(3).mean()
    if mode == "yoy":
        return pct_yoy(s)
    if mode == "3m/3m ann.":
        return pct_qoq_annualized(s)
    return s

main_col, side_col = st.columns([0.72, 0.28])

# Title
with main_col:
    st.markdown(f"### 🇺🇸 vs 🇨🇦  {module}")

# Compose combined DF
frames = []
if not us_df.empty:
    frames.append(apply_transform(us_df, us_id, transform).rename("US"))

# Canada main series (or spread)
if module == "Yield curve (10Y–2Y spread)":
    frames.append(apply_transform(ca_df, "Canada", transform).rename("Canada"))
else:
    frames.append(apply_transform(ca_df, ca_vec_label, transform).rename("Canada"))

# Extra Canadian vectors from sidebar
for dfv in extra:
    if not dfv.empty:
        label = dfv.columns[0]
        frames.append(apply_transform(dfv, label, transform).rename(label))

combo = pd.concat(frames, axis=1).sort_index()

# ---------- Charts ----------
if combo.dropna(how="all").empty:
    st.error("No data to display with the current settings.")
else:
    # Decide if metric is rate-like (avoid rebasing) for level plots
    is_rate_like = any(w in module.lower() for w in ["rate", "yield", "bill", "curve", "spread"]) or (
        transform != "level"
    )

    if transform == "level" and not is_rate_like:
        plot_df = combo.apply(rebase_100)
        ylab = "Index (start=100)"
    else:
        plot_df = combo
        if module == "Yield curve (10Y–2Y spread)":
            ylab = "pp (10y - 2y)"
        elif transform == "level" and is_rate_like:
            ylab = "%"
        else:
            ylab = "%"

    tab_over, tab_div, tab_rcorr, tab_scatter, tab_table = st.tabs(
        ["Overview", "Divergence", "Rolling Corr", "Scatter", "Table"]
    )

    # --- Overview (main timeseries) ---
    with tab_over:
        fig = px.line(
            plot_df.reset_index(),
            x="date",
            y=plot_df.columns,
            labels={"value": ylab, "date": "Date", "variable": "Series"},
        )
        subtitle = (
            f"{module} — {transform}{' (3m MA)' if st.session_state.get('smooth3') else ''}"
        )
        st.plotly_chart(_darken(fig, title=subtitle), use_container_width=True)

        # Lead/Lag bar (US vs CA)
        if "US" in combo.columns and "Canada" in combo.columns:
            corr_df, best = cross_correlation(combo["US"], combo["Canada"], max_lag=12)
            bl = int(best["lag"]) if not pd.isna(best["lag"]) else 0
            bc = float(best["corr"]) if not pd.isna(best["corr"]) else np.nan
            c1, c2 = st.columns([0.6, 0.4])
            with c1:
                lf = px.bar(corr_df, x="lag", y="corr")
                st.plotly_chart(_darken(lf), use_container_width=True)
            with c2:
                st.metric("Max |corr|", f"{bc:.2f}", help="Correlation at lag with highest absolute value")
                st.caption("Positive lag ⇒ Canada lags US")

    # --- Divergence (rolling z-score spread) ---
    with tab_div:
        if "US" in combo.columns and "Canada" in combo.columns:
            if transform == "level" and not is_rate_like:
                s_us = rebase_100(combo["US"]) 
                s_ca = rebase_100(combo["Canada"]) 
            else:
                s_us, s_ca = combo["US"], combo["Canada"]
            zu, zc = rolling_zscore(s_us), rolling_zscore(s_ca)
            spread = (zu - zc)
            fig2 = px.line(
                pd.DataFrame({"date": spread.index, "z-spread": spread.values}),
                x="date",
                y="z-spread",
            )
            st.plotly_chart(_darken(fig2, title="US–Canada z-score spread (13m)"), use_container_width=True)
            latest = spread.dropna().iloc[-1] if not spread.dropna().empty else np.nan
            st.metric("Current z-spread", f"{latest:.2f}")
        else:
            st.info("Need both US and Canada series for divergence.")

    # --- Rolling correlation ---
    with tab_rcorr:
        if "US" in combo.columns and "Canada" in combo.columns:
            rc = rolling_corr(combo["US"], combo["Canada"], window=24)
            rc_fig = px.line(rc.reset_index(), x="date", y=0, labels={"0": "corr (24m)", "date": "Date"})
            st.plotly_chart(_darken(rc_fig, title="Rolling correlation (24 months)"), use_container_width=True)
        else:
            st.info("Need both US and Canada series for rolling correlation.")

    # --- Scatter (Phillips curve) ---
    with tab_scatter:
        # Only meaningful if we can pair CPI (yoy) vs Unemployment (level)
        try:
            need = {
                "US": {"infl": ("CPIAUCSL", "yoy"), "unemp": ("UNRATE", "level")},
                "CA": {"infl": ("v41690973", "yoy"), "unemp": ("v2062815", "level")},
            }
            dfs = {}
            if fred_key:
                us_infl = apply_transform(
                    fred_observations(need["US"]["infl"][0], period_start, period_end, fred_key),
                    need["US"]["infl"][0],
                    "yoy",
                )
                us_un = apply_transform(
                    fred_observations(need["US"]["unemp"][0], period_start, period_end, fred_key),
                    need["US"]["unemp"][0],
                    "level",
                )
                dfs["US"] = pd.concat([us_infl.rename("Inflation"), us_un.rename("Unemployment")], axis=1).dropna()
            ca_infl = apply_transform(
                statcan_vector_by_ref_period(need["CA"]["infl"][0], period_start, period_end),
                need["CA"]["infl"][0],
                "yoy",
            )
            ca_un = apply_transform(
                statcan_vector_by_ref_period(need["CA"]["unemp"][0], period_start, period_end),
                need["CA"]["unemp"][0],
                "level",
            )
            dfs["Canada"] = pd.concat([ca_infl.rename("Inflation"), ca_un.rename("Unemployment")], axis=1).dropna()

            cols = st.columns(2)
            if "US" in dfs:
                figu = px.scatter(dfs["US"], x="Unemployment", y="Inflation", trendline="ols")
                cols[0].plotly_chart(_darken(figu, title="Phillips: US (YoY CPI vs Unemployment)"), use_container_width=True)
            figc = px.scatter(dfs["Canada"], x="Unemployment", y="Inflation", trendline="ols")
            cols[1].plotly_chart(_darken(figc, title="Phillips: Canada (YoY CPI vs Unemployment)"), use_container_width=True)
            st.caption("OLS trendline is illustrative only; not a causal estimate.")
        except Exception as e:
            st.info(f"Phillips curve requires CPI YoY and Unemployment; {e}")

    # --- Table ---
    with tab_table:
        st.dataframe(plot_df.tail(24), use_container_width=True)

    # Stats box
    with side_col:
        st.markdown("#### Quick Stats")
        last = combo.dropna().iloc[-1] if not combo.dropna().empty else None
        if last is not None:
            for k, v in last.items():
                st.metric(label=f"Latest — {k}", value=f"{v:.2f}")

# ---------- CFA Notes ----------
st.markdown("---")
st.subheader("CFA Takeaways")
st.write(CFA_NOTES.get(module, ""))

# ---------- Data Export ----------
st.download_button(
    label="⬇️ Download data (CSV)",
    data=combo.to_csv(index=True).encode("utf-8"),
    file_name=f"fred_statcan_{module.replace(' ','_').lower()}_{transform}.csv",
    mime="text/csv",
)

# ---------- Footer: Sources ----------
st.caption(
    "Sources: FRED API (Federal Reserve Bank of St. Louis), Statistics Canada Web Data Service (WDS); Bank of Canada benchmarks.\n"
    "Notes: Canada 10Y monthly vector v122543; 2Y v122538; 3M T-bill v122531; Bank rate v122530; CPI all-items v41690973; Unemployment v2062815; Participation v2062816."
)
