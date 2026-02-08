# pages/1_Dashboard.py
import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

# Dashboard Password Gate
DASHBOARD_PASSWORD = "capstonoplantalaan"

if "dashboard_auth" not in st.session_state:
    st.session_state.dashboard_auth = False

if not st.session_state.dashboard_auth:
    st.set_page_config(page_title="Dashboard (Locked)", page_icon="🔒", layout="wide")
    st.title("🔒 Admin Access Required")
    pwd = st.text_input("Enter dashboard password", type="password")

    if pwd == DASHBOARD_PASSWORD:
        st.session_state.dashboard_auth = True
        st.rerun()
    else:
        st.stop()

# Page Config
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

APP_TZ = timezone(timedelta(hours=8))  # Asia/Manila

SHEET_ID = st.secrets["SHEET_ID"]
WORKSHEET_NAME = st.secrets.get("WORKSHEET_NAME", "Tracker")
GOOGLE_SA = dict(st.secrets["google_service_account"])

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@st.cache_resource(show_spinner=False)
def get_gspread_client():
    creds = Credentials.from_service_account_info(GOOGLE_SA, scopes=SCOPES)
    return gspread.authorize(creds)


def load_tracker_df() -> pd.DataFrame:
    client = get_gspread_client()
    ws = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)

    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()

    headers = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=headers)


def to_float_safe(x):
    try:
        if x is None:
            return 0.0
        s = str(x).replace("₱", "").replace(",", "").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


st.title("📊 Rent Payments Dashboard")

df = load_tracker_df()

if df.empty:
    st.info("No data found yet in the Tracker sheet.")
    st.stop()

# Column mapping (match your Sheet headers)
# Expected headers:
# Timestamp | Unit Number | Full Name | Amount | Date | Mode | Proof URL | Notes
COL_TIMESTAMP = "Timestamp"
COL_UNIT = "Unit Number"
COL_NAME = "Full Name"
COL_AMOUNT = "Amount"
COL_DATE = "Date"
COL_MODE = "Mode"
COL_PROOF = "Proof URL"
COL_NOTES = "Notes"

# Fallback mapping in case your header text differs slightly
headers_lower = {str(c).strip().lower(): c for c in df.columns}

def col_or_fallback(primary, fallbacks):
    if primary in df.columns:
        return primary
    for f in fallbacks:
        key = str(f).strip().lower()
        if key in headers_lower:
            return headers_lower[key]
    return primary  # last resort (may KeyError later if truly missing)

COL_TIMESTAMP = col_or_fallback(COL_TIMESTAMP, ["timestamp", "submitted timestamp", "time"])
COL_UNIT = col_or_fallback(COL_UNIT, ["unit", "unit number", "unit_no"])
COL_NAME = col_or_fallback(COL_NAME, ["full name", "name", "tenant name"])
COL_AMOUNT = col_or_fallback(COL_AMOUNT, ["amount", "amount paid", "amount (₱)"])
COL_DATE = col_or_fallback(COL_DATE, ["date", "payment date", "date of payment"])
COL_MODE = col_or_fallback(COL_MODE, ["mode", "payment mode"])
COL_PROOF = col_or_fallback(COL_PROOF, ["proof", "proof url", "receipt", "receipt link"])
COL_NOTES = col_or_fallback(COL_NOTES, ["notes", "remarks"])

# Clean + type conversions
df[COL_AMOUNT] = df[COL_AMOUNT].apply(to_float_safe)

df["_payment_date"] = pd.to_datetime(df[COL_DATE], errors="coerce").dt.date
df["_unit_clean"] = df[COL_UNIT].astype(str).str.strip()

# This month filter
today = datetime.now(APP_TZ).date()
month_start = today.replace(day=1)

df_month = df[
    df["_payment_date"].notna()
    & (df["_payment_date"] >= month_start)
    & (df["_payment_date"] <= today)
].copy()

# Filter by unit
units = sorted([u for u in df["_unit_clean"].dropna().unique() if str(u).strip() != ""])
selected_unit = st.selectbox("Filter by Unit (optional)", ["All"] + units, index=0)

if selected_unit != "All":
    df_filtered = df[df["_unit_clean"] == selected_unit].copy()
else:
    df_filtered = df.copy()

# KPIs
total_collected_all = float(df[COL_AMOUNT].sum())
total_collected_month = float(df_month[COL_AMOUNT].sum())

k1, k2 = st.columns(2)
k1.metric("Collections this month", f"₱ {total_collected_month:,.2f}")
k2.metric("Total collected (all time)", f"₱ {total_collected_all:,.2f}")

st.divider()

# Payment Table
st.subheader("Payment Table")

display_cols = []
for c in [COL_TIMESTAMP, COL_UNIT, COL_NAME, COL_AMOUNT, COL_DATE, COL_MODE, COL_PROOF, COL_NOTES]:
    if c in df_filtered.columns:
        display_cols.append(c)

table_df = df_filtered[display_cols].copy()

# Sort by timestamp (best-effort)
if COL_TIMESTAMP in table_df.columns:
    table_df["_ts_sort"] = pd.to_datetime(table_df[COL_TIMESTAMP], errors="coerce")
    table_df = table_df.sort_values("_ts_sort", ascending=False).drop(columns=["_ts_sort"])

st.dataframe(table_df, use_container_width=True, hide_index=True)

# Export CSV
csv_bytes = table_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Export CSV",
    data=csv_bytes,
    file_name=f"rent_payments_{today.isoformat()}.csv",
    mime="text/csv",
)
