import re
import streamlit as st
import gspread
from datetime import datetime, date, timezone, timedelta
from google.oauth2.service_account import Credentials

import cloudinary
import cloudinary.uploader


st.set_page_config(page_title="Rent Payment Record", page_icon="🧾", layout="centered")

st.title("🧾 Rent Payment Record")
st.write(
    "Pakisagutan ang form na ito pagkatapos magbayad ng renta. "
    "Ito ay para maitala nang maayos ang inyong bayad. "
    "Kung nahihirapan, maaari pong humingi ng tulong sa kapamilya."
)

APP_TZ = timezone(timedelta(hours=8))  # Asia/Manila


# Config from Streamlit Secrets
SHEET_ID = st.secrets["SHEET_ID"]
WORKSHEET_NAME = st.secrets["WORKSHEET_NAME"]  # "Tracker"
GOOGLE_SA = dict(st.secrets["google_service_account"])

CLOUDINARY_CLOUD_NAME = st.secrets["CLOUDINARY_CLOUD_NAME"]
CLOUDINARY_API_KEY = st.secrets["CLOUDINARY_API_KEY"]
CLOUDINARY_API_SECRET = st.secrets["CLOUDINARY_API_SECRET"]


# Google Sheets auth + client
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

@st.cache_resource(show_spinner=False)
def get_creds():
    return Credentials.from_service_account_info(GOOGLE_SA, scopes=SCOPES)

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    return gspread.authorize(get_creds())

def connect_to_sheet():
    client = get_gspread_client()
    sh = client.open_by_key(SHEET_ID)
    return sh.worksheet(WORKSHEET_NAME)

def append_payment_row(sheet, row_values):
    sheet.append_row(row_values, value_input_option="USER_ENTERED")


# Cloudinary setup + helpers
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)

def safe_filename(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_\-]", "", text)
    return text or "UNKNOWN_UNIT"

def upload_receipt_to_cloudinary(uploaded_file, unit_number: str, ts_for_name: str) -> str:
    """
    Uploads the Streamlit UploadedFile to Cloudinary and returns a public HTTPS URL.
    Filename format: <UNIT_NUMBER>_<YYYY-MM-DD_HHMMSS>
    Stored under Cloudinary folder: rent_receipts/
    """
    if uploaded_file is None:
        return ""

    unit_safe = safe_filename(unit_number)
    public_id = f"{unit_safe}_{ts_for_name}"

    result = cloudinary.uploader.upload(
        uploaded_file,
        folder="rent_receipts",
        public_id=public_id,
        resource_type="image",
        overwrite=False,
        unique_filename=False,
    )

    return result.get("secure_url", "")


# Form UI
with st.form("payment_form"):
    st.subheader("Payment Details")

    unit_number = st.text_input(
        "Unit Number",
        placeholder="Example: Unit 2A, Room 3, Apartment 5"
    )

    tenant_name = st.text_input(
        "Full Name",
        placeholder="Enter your complete name"
    )

    amount_paid = st.number_input(
        "Amount Paid (₱)",
        min_value=0.0,
        step=100.0
    )

    payment_date = st.date_input(
        "Date of Payment",
        value=date.today()
    )

    payment_mode = st.radio(
        "How did you pay?",
        options=["Cash", "GCash", "Bank Transfer", "Other"]
    )

    proof_file = st.file_uploader(
        "Upload Photo of Receipt / Screenshot (optional)",
        type=["png", "jpg", "jpeg", "webp"]
    )

    notes = st.text_area(
        "Notes (optional)",
        placeholder="Example: Partial payment, paid via relative, etc."
    )

    submitted = st.form_submit_button("Submit Payment")


# Submit logic
if submitted:
    if not unit_number.strip():
        st.error("Please enter your Unit Number.")
        st.stop()

    if not tenant_name.strip():
        st.error("Please enter your Full Name.")
        st.stop()

    if amount_paid <= 0:
        st.error("Please enter a valid Amount Paid (greater than 0).")
        st.stop()

    now_dt = datetime.now(APP_TZ)
    timestamp_display = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_for_filename = now_dt.strftime("%Y-%m-%d_%H%M%S")

    try:
        proof_file_url = upload_receipt_to_cloudinary(
            proof_file,
            unit_number=unit_number.strip(),
            ts_for_name=timestamp_for_filename
        )

        row = [
            timestamp_display,
            unit_number.strip(),
            tenant_name.strip(),
            float(amount_paid),
            payment_date.strftime("%Y-%m-%d"),
            payment_mode,
            proof_file_url,
            notes.strip()
        ]

        sheet = connect_to_sheet()
        append_payment_row(sheet, row)

        st.success("Salamat po! Naitala na ang inyong bayad.")
        st.info("You do not need to submit again.")

        if proof_file_url:
            st.write("Receipt link:")
            st.write(proof_file_url)

    except Exception as e:
        st.error("Something went wrong while saving your payment.")
        st.write("Error details (for debugging):")
        st.write(e)
