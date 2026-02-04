import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai

# --- 1. SETUP & AUTH ---
st.set_page_config(page_title="Medi-Safe Portal", layout="wide")

# Secure API Key handling
# Locally: uses sidebar. Online: uses Streamlit Secrets.
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize Session Database
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = {} # Dictionary {PatientName: [Records]}

# --- 2. THE DOCTOR PORTAL ---
st.title("👨‍⚕️ Clinician Smart-Entry Dashboard")

# Patient Management
target_patient = st.sidebar.text_input("Patient Name", "John Doe")
if target_patient not in st.session_state['patient_db']:
    st.session_state['patient_db'][target_patient] = []

tab_entry, tab_history = st.tabs(["🆕 New Entry", "📜 Patient History"])

with tab_entry:
    col_input, col_ai = st.columns([2, 1])
    
    with col_input:
        st.subheader("Consultation Details")
        doc_report = st.text_area("Electronic Medical Report (Typed)", height=250, 
                                 placeholder="Type clinical findings and prescriptions here...")
        
        st.markdown("---")
        st.subheader("📁 Attachments")
        # Handwritten Archive (No AI analysis as requested)
        handwritten_file = st.file_uploader("Upload Handwritten Rx (For Reference)", type=['jpg', 'png', 'pdf'])
        if handwritten_file:
            st.success("Handwritten file attached to record.")

    with col_ai:
        st.subheader("🤖 AI Clinical Review")
        if doc_report and api_key:
            if st.button("Analyze for Safety"):
                with st.spinner("Reviewing medical logic..."):
                    prompt = f"Review these doctor notes for drug interactions or missing clinical steps. Be brief: {doc_report}"
                    response = model.generate_content(prompt)
                    st.info(f"**AI Feedback:**\n{response.text}")
        else:
            st.write("Enter notes and API key to see AI suggestions.")

    # 3. Confirmation Logic
    st.markdown("---")
    if st.button("✅ Commit to Patient Database", use_container_width=True):
        if doc_report:
            new_record = {
                "Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Report": doc_report,
                "Has_Handwritten_Copy": "Yes" if handwritten_file else "No"
            }
            st.session_state['patient_db'][target_patient].append(new_record)
            st.balloons()
            st.success(f"Securely saved to {target_patient}'s file.")
        else:
            st.error("Cannot save empty notes.")

with tab_history:
    st.subheader(f"Medical History for {target_patient}")
    if st.session_state['patient_db'][target_patient]:
        df = pd.DataFrame(st.session_state['patient_db'][target_patient])
        st.table(df)
    else:
        st.write("No previous records found.")
