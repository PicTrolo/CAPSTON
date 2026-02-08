import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date

st.set_page_config(page_title="Rent Payment Record", page_icon="🧾", layout="centered")

st.title("🧾 Rent Payment Record")
st.write(
    "Pakisagutan ang form na ito pagkatapos magbayad ng renta. "
    "Ito ay para maitala nang maayos ang inyong bayad. "
    "Kung nahihirapan, maaari pong humingi ng tulong sa kapamilya."
)


# Google Sheets Connection (Streamlit Cloud via st.secrets)
def connect_to_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # st.secrets["SERVICE_ACCOUNT_JSON"] should be a JSON string
    service_account_info = dict(st.secrets["google_service_account"])
    creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    client = gspread.authorize(creds)

    sheet_id = st.secrets["SHEET_ID"]
    worksheet_name = st.secrets["WORKSHEET_NAME"]

    sh = client.open_by_key(sheet_id)  # e.g. "1LeB7qqbe7rBRbz60qWCS2cf2zdIK6yYn1_2mL2-awto"
    return sh.worksheet(worksheet_name) # e.g. "Tracker"

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
        "Upload Photo of Receipt / Screenshot",
        type=["png", "jpg", "jpeg"]
    )

    notes = st.text_area(
        "Notes (optional)",
        placeholder="Example: Partial payment, paid via relative, etc."
    )

    submitted = st.form_submit_button("Submit Payment")


# Submit Logic
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

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # If you haven't implemented Drive upload yet, keep this blank
    proof_file_url = ""

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
