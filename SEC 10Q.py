import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

# ──────────────────────────────
# App setup (small‑screen friendly)
# ──────────────────────────────
st.set_page_config(page_title="SEC 10‑Q — Statements Extractor", layout="centered")
st.title("SEC 10‑Q — Balance Sheet, Income, and Cash Flow Extractor")

# ──────────────────────────────
# SEC helpers
# ──────────────────────────────
SEC_HEADERS = {"User-Agent": "YourCompanyName YourEmail@domain.com"}  # <-- replace with yours

@st.cache_data(show_spinner=False)
def get_latest_10q(cik: str):
    """Return (accessionNumber, primaryDocument, filingDate) for latest 10-Q or (None, None, None)."""
    formatted = cik.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{formatted}.json"
    r = requests.get(url, headers=SEC_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json().get("filings", {}).get("recent", {})
    df = pd.DataFrame(data)
    if df.empty:
        return None, None, None
    df10q = df[df["form"] == "10-Q"].sort_values("filingDate", ascending=False)
    if df10q.empty:
        return None, None, None
    row = df10q.iloc[0]
    return row["accessionNumber"], row["primaryDocument"], row["filingDate"]

@st.cache_data(show_spinner=False)
def fetch_soup(cik: str, acc_no: str, doc_name: str):
    """Fetch the main 10‑Q HTML soup."""
    c = cik.lstrip("0")
    a = acc_no.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{c}/{a}/{doc_name}"
    r = requests.get(url, headers=SEC_HEADERS, timeout=60)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

# ──────────────────────────────
# Table parsing with extra context
# ──────────────────────────────
def parse_all_tables_with_context(soup: BeautifulSoup):
    """
    Return list of (df, label_text) for parseable tables, using caption + nearby heading + leading paragraph.
    """
    out = []
    for i, tbl in enumerate(soup.find_all("table")):
        # Parse table
        try:
            df = pd.read_html(str(tbl), header=0, flavor="bs4")[0]
        except Exception:
            continue
        if df.shape[0] == 0:
            continue

        # Build label from multiple hints
        cap = tbl.find("caption")
        cap_text = cap.get_text(" ", strip=True) if cap else ""

        heading = ""
        prev_head = tbl.find_previous(["h1", "h2", "h3", "strong", "b"])
        if prev_head and prev_head.get_text(strip=True):
            heading = prev_head.get_text(" ", strip=True)

        # short preceding paragraph often contains “(Unaudited)” or statement name
        lead = ""
        prev_p = tbl.find_previous("p")
        if prev_p and prev_p.get_text(strip=True):
            lead = prev_p.get_text(" ", strip=True)[:140]  # keep it short

        cols = [str(c) for c in df.columns.tolist()]
        first_col = cols[0] if cols else ""

        label_guess = " | ".join([x for x in [cap_text, heading, lead] if x]) or f"starts with '{first_col}'"
        out.append((df, label_guess))
    return out

# ──────────────────────────────
# Classification rules & scoring
# ──────────────────────────────
DATE_ASOF_RE   = re.compile(r"\bas of\b|\bat\b", re.I)
DATE_PERIOD_RE = re.compile(r"\bfor the (three|six|nine|twelve|\d+)\s+months?\s+ended\b", re.I)

CLASS_RULES = {
    "balance": {
        "caption_patterns": [
            r"\b(condensed\s+)?consolidated\s+balance\s+sheets?\b",
            r"\bstatement[s]?\s+of\s+financial\s+position\b",
            r"\bconsolidated\s+statement[s]?\s+of\s+financial\s+position\b",
            r"\b(balance\s+sheet|financial\s+position)\s*\(unaudited\)\b",
        ],
        "row_tokens": [
            "assets", "current assets", "cash and cash equivalents",
            "short-term investments", "accounts receivable", "inventory",
            "property, plant and equipment", "goodwill", "intangible assets",
            "liabilities", "current liabilities", "long-term debt",
            "total liabilities", "stockholders’ equity", "shareholders’ equity",
            "additional paid-in capital", "retained earnings",
            "accumulated other comprehensive income",
            "total assets", "total liabilities and stockholders’ equity",
        ],
        "anti_patterns": [
            r"changes?\s+in\s+(shareholders’|stockholders’)\s+equity",
            r"\bsegment\b|\bschedule\b|\bnon-gaap\b",
            r"cash\s+flows?",
            r"operations|earnings|income\s+statement|profit|loss",
        ],
        "date_bonus": "asof",
    },
    "income": {
        "caption_patterns": [
            r"\b(condensed\s+)?consolidated\s+statements?\s+of\s+(operations|earnings|income)\b",
            r"\bstatement[s]?\s+of\s+profit(\s*\(?\s*loss\s*\)?)?\b",
            r"\bstatements?\s+of\s+operations\s+and\s+comprehensive\s+income\b",
            r"\bstatements?\s+of\s+comprehensive\s+income\b",
            r"\b(consolidated\s+)?statements?\s+of\s+income\s*\(loss\)\b",
        ],
        "row_tokens": [
            "revenue", "net sales", "sales", "total revenue",
            "cost of goods sold", "cost of revenue", "gross profit",
            "research and development", "selling, general and administrative",
            "operating income", "operating loss",
            "interest income", "interest expense",
            "other income", "other expense",
            "income before income taxes", "provision for income taxes",
            "net income", "net loss",
            "earnings per share", "basic", "diluted", "weighted average shares",
            "comprehensive income", "other comprehensive income",
        ],
        "anti_patterns": [
            r"cash\s+flows?", r"balance\s+sheet", r"financial\s+position",
            r"changes?\s+in\s+(shareholders’|stockholders’)\s+equity",
            r"\bsegment\b|\bschedule\b|\bnon-gaap\b|reconciliation",
        ],
        "date_bonus": "period",
    },
    "cashflow": {
        "caption_patterns": [
            r"\b(condensed\s+)?consolidated\s+statements?\s+of\s+cash\s+flows?\b",
            r"\bstatement[s]?\s+of\s+cash\s+flows?\b",
            r"\bcash\s+flows?\s*\(unaudited\)\b",
        ],
        "row_tokens": [
            "net cash provided by operating activities",
            "net cash used in operating activities",
            "net cash provided by investing activities",
            "net cash used in investing activities",
            "net cash provided by financing activities",
            "net cash used in financing activities",
            "operating activities", "investing activities", "financing activities",
            "effect of exchange rate changes on cash",
            "cash and cash equivalents, beginning of period",
            "cash and cash equivalents, end of period",
            "net increase in cash", "net decrease in cash",
            "net increase (decrease) in cash",
        ],
        "anti_patterns": [
            r"balance\s+sheet", r"financial\s+position",
            r"operations|earnings|income|profit|loss",
            r"changes?\s+in\s+(shareholders’|stockholders’)\s+equity",
            r"\bsegment\b|\bschedule\b|\bnon-gaap\b|reconciliation",
        ],
        "date_bonus": "period",
    }
}

def _score_caption(label: str, patterns):
    t = (label or "").lower()
    score = 0
    for p in patterns:
        if re.search(p, t, flags=re.I):
            score += 5
    return score

def _score_anti(label: str, anti_patterns):
    t = (label or "").lower()
    penalty = 0
    for p in anti_patterns:
        if re.search(p, t, flags=re.I):
            penalty -= 4
    return penalty

def _score_rows(df: pd.DataFrame, row_tokens):
    # Look at first ~10 rows of first column + entire index if already set
    text = ""
    try:
        head = df.astype(str).head(12)
        cols = list(head.columns)
        if cols:
            text += "\n".join(head[cols[0]].tolist())
        text += "\n".join(head.index.astype(str).tolist())
    except Exception:
        pass
    t = text.lower()
    score = 0
    for token in row_tokens:
        if token in t:
            score += 2
    return score

def _score_dates(label: str, df: pd.DataFrame, want: str):
    # want == "asof" boosts Balance; "period" boosts Income/Cash Flow
    lab = (label or "")
    txt = (lab + "\n" + df.to_string()).lower()
    s = 0
    if want == "asof" and DATE_ASOF_RE.search(txt):
        s += 2
    if want == "period" and DATE_PERIOD_RE.search(txt):
        s += 2
    return s

def _numeric_density(df: pd.DataFrame):
    """Share of numeric-looking cells (helps prefer actual statements over narrative tables)."""
    try:
        sub = df.iloc[:, 1:] if df.shape[1] > 1 else df
        total = sub.size
        if total == 0: return 0.0
        s = sub.astype(str).stack()
        num_like = s.str.contains(r"^\(?\$?[\d,]+(\.\d+)?\)?$", na=False).sum()
        return num_like / total
    except Exception:
        return 0.0

def _has_cashflow_sections(df: pd.DataFrame):
    """Bonus if we see Operating/Investing/Financing section anchors in first column."""
    try:
        col0 = df.iloc[:, 0].astype(str).str.lower().str.strip()
        flags = sum(col0.str.contains(x) for x in ["operating activities", "investing activities", "financing activities"])
        return int(flags >= 2)
    except Exception:
        return 0

def classify_tables(tables_with_labels):
    """
    Input: list of (df, label)
    Output: dict with keys 'balance','income','cashflow' -> (df,label) or None
    """
    picks = {"balance": None, "income": None, "cashflow": None}
    best_scores = {k: -1_000 for k in picks.keys()}  # allow negatives

    for df, label in tables_with_labels:
        dens = _numeric_density(df)
        cashflow_sections = _has_cashflow_sections(df)

        for kind, rule in CLASS_RULES.items():
            s  = _score_caption(label, rule["caption_patterns"])
            s += _score_rows(df, rule["row_tokens"])
            s += _score_anti(label, rule["anti_patterns"])
            s += _score_dates(label, df, rule["date_bonus"])

            # generic numeric density bonus
            s += dens * 5.0

            # cash flow structure bonus
            if kind == "cashflow":
                s += cashflow_sections * 3.0

            # mild boost for dollar signs
            try:
                if df.shape[1] > 1:
                    if df.iloc[:, 1:].astype(str).apply(lambda c: c.str.contains(r"\$").any()).any():
                        s += 1
            except Exception:
                pass

            if s > best_scores[kind]:
                best_scores[kind] = s
                picks[kind] = (df, label)

    # Thresholds
    minima = {"balance": 4, "income": 4, "cashflow": 4}
    for k in picks.keys():
        if best_scores[k] < minima[k]:
            picks[k] = None
    return picks

# ──────────────────────────────
# Cleaning utilities
# ──────────────────────────────
NUM_RE = re.compile(r"[,\s]")
PAREN_RE = re.compile(r"^\((.*)\)$")

def to_number(x):
    """Convert cell to float if looks like number with $, commas, and parentheses."""
    if pd.isna(x):
        return x
    s = str(x).strip()
    if s == "" or s.lower() in {"na", "n/a", "--"}:
        return pd.NA
    # remove $ and commas/spaces
    s2 = s.replace("$", "")
    s2 = NUM_RE.sub("", s2)
    # parentheses negative
    m = PAREN_RE.match(s2)
    if m:
        s2 = f"-{m.group(1)}"
    try:
        return float(s2)
    except Exception:
        return x  # leave as-is if not numeric

def clean_statement(df: pd.DataFrame):
    """Basic cleanup: drop all-empty cols, convert numerics, set index to first column if possible."""
    df = df.copy()
    df = df.dropna(axis=1, how="all")
    # Convert numeric-like cells in non-index columns
    for c in df.columns[1:]:
        df[c] = df[c].map(to_number)
    # Drop columns that are entirely non-numeric (except the first descriptive column)
    keep = [df.columns[0]]
    for c in df.columns[1:]:
        if pd.api.types.is_numeric_dtype(df[c]) or df[c].notna().sum() > 0:
            keep.append(c)
    df = df[keep]
    # Set index to first column if it's descriptive
    try:
        df.iloc[:, 0] = df.iloc[:, 0].astype(str)
        df = df.set_index(df.columns[0])
    except Exception:
        pass
    return df

def download_button_csv(df: pd.DataFrame, label: str, file_label: str):
    csv = df.to_csv()
    st.download_button(
        label=label,
        data=csv,
        file_name=f"{file_label}.csv",
        mime="text/csv",
        use_container_width=True
    )

# ──────────────────────────────
# App
# ──────────────────────────────
def main():
    with st.sidebar:
        st.markdown("### Input")
        cik = st.text_input("CIK", "0000320193", help="Enter CIK (e.g., Apple = 0000320193)")
        fetch_btn = st.button("Fetch latest 10‑Q", type="primary")
        st.caption("Set a real User‑Agent in code per SEC guidance.")

    if fetch_btn:
        with st.spinner("Fetching latest 10‑Q metadata..."):
            acc, doc, fdate = get_latest_10q(cik)
        if not acc:
            st.error("No 10‑Q found for this CIK.")
            return

        st.success(f"Latest 10‑Q filing date: {fdate}")
        with st.spinner("Downloading and parsing tables..."):
            soup = fetch_soup(cik, acc, doc)
            tables = parse_all_tables_with_context(soup)

        if not tables:
            st.error("No parseable tables found in the filing.")
            return

        # NEW: classify tables (replaces choose_best_table + pattern constants)
        picks = classify_tables(tables)
        bal = picks["balance"]
        inc = picks["income"]
        cfs = picks["cashflow"]

        # Report what we found
        st.markdown("## Statement Matches")
        def show_match(tag, match):
            if match:
                _, label = match
                st.success(f"{tag} ➜ {label[:120]}")
            else:
                st.warning(f"{tag} ➜ not found")

        show_match("Balance Sheet", bal)
        show_match("Income Statement", inc)
        show_match("Cash Flow", cfs)

        # Display and download (stacked for small screens)
        st.markdown("---")

        if bal:
            bdf_raw, blabel = bal
            bdf = clean_statement(bdf_raw)
            with st.expander("📄 Balance Sheet — preview", expanded=True):
                st.caption(blabel)
                st.dataframe(bdf, use_container_width=True, height=420)
                download_button_csv(bdf, "Download Balance Sheet (CSV)", "balance_sheet")

        if inc:
            idf_raw, ilabel = inc
            idf = clean_statement(idf_raw)
            with st.expander("📄 Income Statement — preview", expanded=False):
                st.caption(ilabel)
                st.dataframe(idf, use_container_width=True, height=420)
                download_button_csv(idf, "Download Income Statement (CSV)", "income_statement")

        if cfs:
            cdf_raw, clabel = cfs
            cdf = clean_statement(cdf_raw)
            with st.expander("📄 Cash Flow Statement — preview", expanded=False):
                st.caption(clabel)
                st.dataframe(cdf, use_container_width=True, height=420)
                download_button_csv(cdf, "Download Cash Flow (CSV)", "cash_flow")

        # Fallback guidance
        if not any([bal, inc, cfs]):
            st.info(
                "Couldn’t confidently auto-detect the statements. "
                "Issuer captions vary — expand patterns or select tables manually in a future version."
            )
    else:
        st.info("Enter a CIK and click **Fetch latest 10‑Q** to extract the three statements.")

if __name__ == "__main__":
    main()
