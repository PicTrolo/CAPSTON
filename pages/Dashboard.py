# pages/1_Dashboard.py
import streamlit as st
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

import csv
import io
from datetime import datetime, date, timezone, timedelta

import gspread
from google.oauth2.service_account import Credentials


APP_TZ = timezone(timedelta(hours=8))  # Asia/Manila


def must_get_secret(key: str) -> str:
    val = st.secrets.get(key, "")
    if not val:
        st.error(f"Missing secret: {key}")
        st.stop()
    return val


# Password Gate (fail-safe)
DASHBOARD_PASSWORD = must_get_secret("DASHBOARD_PASSWORD")

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


# Google Sheets Connection
SHEET_ID = must_get_secret("SHEET_ID")
WORKSHEET_NAME = st.secrets.get("WORKSHEET_NAME", "Tracker")
GOOGLE_SA = st.secrets.get("google_service_account", None)
if not GOOGLE_SA:
    st.error("Missing secret: [google_service_account] table")
    st.stop()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@st.cache_resource(show_spinner=False)
def get_worksheet():
    creds = Credentials.from_service_account_info(dict(GOOGLE_SA), scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)


def load_rows() -> list[dict]:
    ws = get_worksheet()
    # returns list of dicts using header row as keys
    records = ws.get_all_records()
    return records


def parse_date_safe(s: str) -> date | None:
    try:
        # expected: YYYY-MM-DD
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def to_float_safe(x) -> float:
    try:
        s = str(x).replace("₱", "").replace(",", "").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0

# Dashboard
st.title("📊 Rent Payments Dashboard")

rows = load_rows()
if not rows:
    st.info("No data found yet in the Tracker sheet.")
    st.stop()

# Actual headers (from your sheet screenshot)
COL_TIMESTAMP = "timestamp"
COL_UNIT = "unit_number"
COL_NAME = "tenant_name"
COL_AMOUNT = "amount_paid"
COL_DATE = "payment_date"
COL_MODE = "payment_mode"
COL_PROOF = "proof_file_url"
COL_NOTES = "notes"

# Validate required columns exist in the sheet header
missing_cols = [c for c in [COL_UNIT, COL_AMOUNT, COL_DATE] if c not in rows[0]]
if missing_cols:
    st.error("Dashboard cannot find required columns in your sheet header row.")
    st.write("Missing columns:", missing_cols)
    st.write("Found columns:", list(rows[0].keys()))
    st.stop()

# Normalize + enrich
for r in rows:
    r[COL_UNIT] = str(r.get(COL_UNIT, "")).strip()
    r[COL_AMOUNT] = to_float_safe(r.get(COL_AMOUNT, 0))
    r["_payment_date"] = parse_date_safe(r.get(COL_DATE, ""))

today = datetime.now(APP_TZ).date()
month_start = today.replace(day=1)

rows_month = [
    r for r in rows
    if r["_payment_date"] is not None and month_start <= r["_payment_date"] <= today
]

total_collected_all = sum(r[COL_AMOUNT] for r in rows)
total_collected_month = sum(r[COL_AMOUNT] for r in rows_month)

# Filter by unit
units = sorted({r[COL_UNIT] for r in rows if r[COL_UNIT]})
selected_unit = st.selectbox("Filter by Unit (optional)", ["All"] + units, index=0)

filtered = rows
if selected_unit != "All":
    filtered = [r for r in rows if r[COL_UNIT] == selected_unit]

# KPIs
k1, k2 = st.columns(2)
k1.metric("Collections this month", f"₱ {total_collected_month:,.2f}")
k2.metric("Total collected (all time)", f"₱ {total_collected_all:,.2f}")

st.divider()

# Payment table (drop helper field)
st.subheader("Payment Table")

def sort_key(r):
    # try to sort by timestamp text; if missing, keep bottom
    return str(r.get(COL_TIMESTAMP, ""))

filtered_sorted = sorted(filtered, key=sort_key, reverse=True)

table_rows = []
for r in filtered_sorted:
    table_rows.append({
        COL_TIMESTAMP: r.get(COL_TIMESTAMP, ""),
        COL_UNIT: r.get(COL_UNIT, ""),
        COL_NAME: r.get(COL_NAME, ""),
        COL_AMOUNT: r.get(COL_AMOUNT, 0),
        COL_DATE: r.get(COL_DATE, ""),
        COL_MODE: r.get(COL_MODE, ""),
        COL_PROOF: r.get(COL_PROOF, ""),
        COL_NOTES: r.get(COL_NOTES, ""),
    })

st.dataframe(table_rows, use_container_width=True, hide_index=True)

# Export CSV
output = io.StringIO()
writer = csv.DictWriter(output, fieldnames=list(table_rows[0].keys()) if table_rows else [])
if table_rows:
    writer.writeheader()
    writer.writerows(table_rows)
csv_bytes = output.getvalue().encode("utf-8")

st.download_button(
    "Export CSV",
    data=csv_bytes,
    file_name=f"rent_payments_{today.isoformat()}.csv",
    mime="text/csv",
)