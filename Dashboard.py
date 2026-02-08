import streamlit as st
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

# Fail-safe pandas import so the whole app doesn't brick
try:
    import pandas as pd
except Exception as e:
    st.title("📊 Rent Payments Dashboard")
    st.error("Dashboard dependency missing: pandas failed to import.")
    st.write("Fix: add pandas to requirements.txt and redeploy.")
    st.write("Error details:")
    st.code(str(e))
    st.stop()

# Password gate (reads from secrets)
DASHBOARD_PASSWORD = st.secrets["DASHBOARD_PASSWORD"]

if "dashboard_auth" not in st.session_state:
    st.session_state.dashboard_auth = False

if not st.session_state.dashboard_auth:
    st.title("🔒 Admin Access Required")
    pwd = st.text_input("Enter dashboard password", type="password")
    if pwd == DASHBOARD_PASSWORD:
        st.session_state.dashboard_auth = True
        st.rerun()
    else:
        st.stop()

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
    ws = get_gspread_client().open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])

def to_float_safe(x):
    try:
        s = str(x).replace("₱", "").replace(",", "").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0

st.title("📊 Rent Payments Dashboard")

df = load_tracker_df()
if df.empty:
    st.info("No data found yet in the Tracker sheet.")
    st.stop()

# Find columns by expected headers
COL_TIMESTAMP = "timestamp"
COL_UNIT = "unit_number"
COL_NAME = "tenant_name"
COL_AMOUNT = "amount_paid"
COL_DATE = "payment_date"
COL_MODE = "payment_mode"
COL_PROOF = "proof_file_url"
COL_NOTES = "notes"

headers_lower = {str(c).strip().lower(): c for c in df.columns}

def col_or_fallback(primary, fallbacks):
    if primary in df.columns:
        return primary
    for f in fallbacks:
        key = str(f).strip().lower()
        if key in headers_lower:
            return headers_lower[key]
    return primary

COL_TIMESTAMP = col_or_fallback(COL_TIMESTAMP, ["timestamp", "submitted timestamp", "time"])
COL_UNIT = col_or_fallback(COL_UNIT, ["unit", "unit number", "unit_no"])
COL_NAME = col_or_fallback(COL_NAME, ["full name", "name", "tenant name"])
COL_AMOUNT = col_or_fallback(COL_AMOUNT, ["amount", "amount paid", "amount (₱)"])
COL_DATE = col_or_fallback(COL_DATE, ["date", "payment date", "date of payment"])
COL_MODE = col_or_fallback(COL_MODE, ["mode", "payment mode"])
COL_PROOF = col_or_fallback(COL_PROOF, ["proof", "proof url", "receipt", "receipt link"])
COL_NOTES = col_or_fallback(COL_NOTES, ["notes", "remarks"])

# If any key columns are missing, show a helpful message (instead of crashing)
required = [COL_UNIT, COL_AMOUNT, COL_DATE]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error("Dashboard cannot find required columns in your sheet header row.")
    st.write("Missing columns:")
    st.write(missing)
    st.write("Your sheet columns are:")
    st.write(list(df.columns))
    st.stop()

df[COL_AMOUNT] = df[COL_AMOUNT].apply(to_float_safe)
df["_payment_date"] = pd.to_datetime(df[COL_DATE], errors="coerce").dt.date
df["_unit_clean"] = df[COL_UNIT].astype(str).str.strip()

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

df_filtered = df.copy()
if selected_unit != "All":
    df_filtered = df[df["_unit_clean"] == selected_unit].copy()

# KPIs
total_collected_all = float(df[COL_AMOUNT].sum())
total_collected_month = float(df_month[COL_AMOUNT].sum())

k1, k2 = st.columns(2)
k1.metric("Collections this month", f"₱ {total_collected_month:,.2f}")
k2.metric("Total collected (all time)", f"₱ {total_collected_all:,.2f}")

st.divider()
st.subheader("Payment Table")

display_cols = [c for c in [COL_TIMESTAMP, COL_UNIT, COL_NAME, COL_AMOUNT, COL_DATE, COL_MODE, COL_PROOF, COL_NOTES] if c in df_filtered.columns]
table_df = df_filtered[display_cols].copy()

if COL_TIMESTAMP in table_df.columns:
    table_df["_ts_sort"] = pd.to_datetime(table_df[COL_TIMESTAMP], errors="coerce")
    table_df = table_df.sort_values("_ts_sort", ascending=False).drop(columns=["_ts_sort"])

st.dataframe(table_df, use_container_width=True, hide_index=True)

csv_bytes = table_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Export CSV",
    data=csv_bytes,
    file_name=f"rent_payments_{today.isoformat()}.csv",
    mime="text/csv",
)