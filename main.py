# lead_followup_app.py
import os
import pickle
from datetime import datetime
import streamlit as st

from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from langchain.agents import initialize_agent, Tool
from langchain_google_genai import ChatGoogleGenerativeAI


# ------------------- Config ---------------------
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1asB1-aXLOqTaNYLckrxkM02GnYF3QETn6edAy-iAGHw'
SHEET_NAME = 'Sheet1'
RANGE_NAME = f'{SHEET_NAME}!A2:L'
SHEET_ID = 0  # Usually 0 for first sheet

# 🔐 SET YOUR GEMINI API KEY HERE OR IN ENV
GOOGLE_API_KEY = "AIzaSyAyTROySd2T8pN4P3NeLPJwvGTzSuG7eZk"  # 🔁 Paste your Gemini API Key here
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# ------------------ Auth Setup ------------------
def get_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('sheets', 'v4', credentials=creds)

# ------------------ LLM Tool --------------------
def get_today_leads_and_highlight(_: str) -> str:
    service = get_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    rows = result.get('values', [])

    today = datetime.now().strftime('%Y-%m-%d')
    followups = []
    highlight_requests = []

    for idx, row in enumerate(rows):
        row += [''] * (12 - len(row))  # Pad missing columns
        follow_up_date = row[8].strip()

        try:
            if datetime.strptime(follow_up_date, '%Y-%m-%d').strftime('%Y-%m-%d') == today:
                followups.append({
                    'Lead Name': row[0],
                    'Company': row[1],
                    'Phone': row[3],
                    'Email': row[4],
                    'Next Action': row[11]
                })

                # Add row highlight
                highlight_requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": SHEET_ID,
                            "startRowIndex": idx + 1,
                            "endRowIndex": idx + 2
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {
                                    "red": 1.0,
                                    "green": 1.0,
                                    "blue": 0.6
                                }
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                })
        except:
            continue

    # Apply highlight if any
    if highlight_requests:
        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": highlight_requests}
        ).execute()

    if not followups:
        return "✅ No leads scheduled for follow-up today."

    # Generate summary
    summary = f"📌 You have {len(followups)} leads to follow up today:\n"
    for lead in followups:
        summary += (
            f"\n🔹 {lead['Lead Name']} ({lead['Company']})\n"
            f"    📞 {lead['Phone']} | ✉️ {lead['Email']}\n"
            f"    📋 Next Action: {lead['Next Action']}\n"
        )
    return summary.strip()

# ------------------ LangChain Agent --------------------
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",
    temperature=0.3,
    google_api_key=GOOGLE_API_KEY
)

tools = [
    Tool(
        name="CheckLeadsToday",
        func=get_today_leads_and_highlight,
        description="Checks Google Sheet for leads needing follow-up today and highlights them."
    )
]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="zero-shot-react-description",
    verbose=True
)

# ------------------ Streamlit UI --------------------
st.set_page_config(page_title="Lead Follow-Up", page_icon="📞")
st.title("📞 Lead Follow-Up Checker")
st.markdown("This tool checks your Google Sheet for follow-up leads **today** and highlights them automatically.")

if st.button("🔍 Check Follow-Ups Now"):
    with st.spinner("Talking to Gemini and checking sheet..."):
        response = agent.run("Check if I have any leads to follow up today")
        st.success("✅ Done!")
        st.markdown("### 📝 Gemini Summary:")
        st.markdown(response.replace("\n", "  \n"))
