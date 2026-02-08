import io
import re
import streamlit as st
import gspread
from datetime import datetime, date
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

st.set_page_config(page_title="Rent Payment Record", page_icon="🧾", layout="centered")

st.title("🧾 Rent Payment Record")
st.write(
    "Pakisagutan ang form na ito pagkatapos magbayad ng renta. "
    "Ito ay para maitala nang maayos ang inyong bayad. "
    "Kung nahihirapan, maaari pong humingi ng tulong sa kapamilya."
)


# Config from Streamlit Secrets
SHEET_ID = st.secrets["SHEET_ID"]  # <-- (in Streamlit Secrets)
WORKSHEET_NAME = st.secrets["WORKSHEET_NAME"]  # <-- (in Streamlit Secrets, "Tracker")
DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]  # <-- (added in Streamlit Secrets)
GOOGLE_SA = st.secrets["google_service_account"]  # <-- (in Streamlit Secrets, already set)


# Google auth + clients
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_creds():
    return Credentials.from_service_account_info(GOOGLE_SA, scopes=SCOPES)

@st.cache_resource
def get_gspread_client():
    return gspread.authorize(get_creds())

@st.cache_resource
def get_drive_service():
    return build("drive", "v3", credentials=get_creds())

def connect_to_sheet():
    client = get_gspread_client()
    sh = client.open_by_key(SHEET_ID)
    return sh.worksheet(WORKSHEET_NAME)


# Helpers
def safe_filename(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_\-]", "", text)
    return text or "UNKNOWN_UNIT"

def upload_receipt_to_drive(uploaded_file, unit_number: str, ts_for_name: str) -> str:
    if not uploaded_file:
        return ""

    drive = get_drive_service()

    original_name = uploaded_file.name or "receipt"
    ext = ""
    if "." in original_name:
        ext = "." + original_name.split(".")[-1].lower()

    unit_safe = safe_filename(unit_number)
    filename = f"{unit_safe}_{ts_for_name}{ext}"

    file_metadata = {
        "name": filename,
        "parents": [DRIVE_FOLDER_ID],
    }

    file_bytes = uploaded_file.getvalue()
    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype=uploaded_file.type or "application/octet-stream",
        resumable=False,
    )

    created = drive.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()

    file_id = created["id"]

    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
        supportsAllDrives=True,
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

def append_payment_row(sheet, row_values):
    sheet.append_row(row_values, value_input_option="USER_ENTERED")


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
        type=["png", "jpg", "jpeg"]
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

    timestamp_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_for_filename = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    try:
        proof_file_url = upload_receipt_to_drive(
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
