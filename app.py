import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(page_title="Rent Payment Record", page_icon="🧾", layout="centered")

st.title("🧾 Rent Payment Record")
st.write(
    "Pakisagutan ang form na ito pagkatapos magbayad ng renta. "
    "Ito ay para maitala nang maayos ang inyong bayad. "
    "Kung nahihirapan, maaari pong humingi ng tulong sa kapamilya."
)


# 1) Read settings from .env
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")


# 2) Connect to Google Sheets
    # authenticates using your service account JSON file.

def connect_to_sheet():
    # Permissions ("scopes") your app is requesting.
    # spreadsheets: lets the app read/write Google Sheets
    scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=scopes
    )
    client = gspread.authorize(creds)

    # opens Google Sheet by name, then use the first worksheet (tab).
    sheet = client.open(SHEET_NAME).sheet1
    return sheet


# 3) Helper: Append one row to Google Sheet

def append_payment_row(sheet, row_values):
    # Appends the row to the bottom of the sheet.
    # "adding a new submission record".
    sheet.append_row(row_values, value_input_option="USER_ENTERED")

# 4) Build a simple, elderly-friendly form
    # Streamlit's st.form groups inputs and adds a single Submit button.

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


# 5) Validate + write to Google Sheet
if submitted:
    # Basic validation: strict but friendly.
    if not unit_number.strip():
        st.error("Please enter your Unit Number.")
        st.stop()

    if not tenant_name.strip():
        st.error("Please enter your Full Name.")
        st.stop()

    if amount_paid <= 0:
        st.error("Please enter a valid Amount Paid (greater than 0).")
        st.stop()

    # Timestamp helps with tracking and sorting records.
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # For now, we will store proof_file_url as blank.
    # Next section, shows how to upload the image to Drive
    # and put the link here.
    proof_file_url = ""

    # Prepare row in the SAME order as your sheet headers.
    row = [
        timestamp,
        unit_number.strip(),
        tenant_name.strip(),
        float(amount_paid),
        payment_date.strftime("%Y-%m-%d"),
        payment_mode,
        proof_file_url,
        notes.strip()
    ]

    try:
        sheet = connect_to_sheet()
        append_payment_row(sheet, row)

        st.success("Salamat po! Naitala na ang inyong bayad.")
        st.info("You do not need to submit again.")
    except Exception as e:
        st.error("Something went wrong while saving your payment.")
        st.write("Error details (for debugging):")
        st.write(e)
