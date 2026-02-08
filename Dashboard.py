# pages/1_Dashboard.py
import streamlit as st
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

# Fail-safe pandas import (prevents bricking)
try:
    import pandas as pd
except Exception as e:
    st.title("📊 Rent Payments Dashboard")
    st.error("Dashboard cannot start because pandas failed to import.")
    st.code(str(e))
    st.stop()

# Secrets fail-safe (prevents bricking)
DASHBOARD_PASSWORD = st.secrets.get("DASHBOARD_PASSWORD", "")
SHEET_ID = st.secrets.get("SHEET_ID", "")
WORKSHEET_NAME = st.secrets.get("WORKSHEET_NAME", "Tracker")
GOOGLE_SA = st.secrets.get("google_service_account", None)

if not DASHBOARD_PASSWORD:
    st.title("📊 Rent Payments Dashboard")
    st.error("Missing secret: DASHBOARD_PASSWORD")
    st.write("Add this in Streamlit Secrets:")
    st.code('DASHBOARD_PASSWORD = "capstonoplantalaan"')
    st.stop()

if not SHEET_ID or not GOOGLE_SA:
    st.title("📊 Rent Payments Dashboard")
    st.error("Missing Google Sheets secrets (SHEET_ID and/or [google_service_account]).")
    st.stop()

# Password gate
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
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@st.cache_resource(show_spinner=False)
def get_gspread_client():
    creds = Credentials.from_service_account_info(dict(GOOGLE_SA), scopes=SCOPES)
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

# Actual sheet headers
COL_TIMESTAMP = "timestamp"
COL_UNIT = "unit_number"
COL_NAME = "tenant_name"
COL_AMOUNT = "amount_paid"
COL_DATE = "payment_date"
COL_MODE = "payment_mode"
COL_PROOF = "proof_file_url"
COL_NOTES = "notes"

# Make sure required columns exist
required = [COL_UNIT, COL_AMOUNT, COL_DATE]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error("Dashboard cannot find required columns in your sheet header row.")
    st.write("Missing columns:", missing)
    st.write("Your sheet columns are:", list(df.columns))
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
