import streamlit as st
import pandas as pd
import google.generativeai as genai
from supabase import create_client, Client
import random, string

# --- APP CONFIG & DB CONNECTION ---
st.set_page_config(page_title="MediCloud AI", layout="wide")

# Connect to Supabase (Add these to your Streamlit Secrets!)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Configure Gemini
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# Helper: Generate random credentials
def generate_creds():
    uid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    pwd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"PAT-{uid}", pwd

# --- LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.user_data = None

def logout():
    st.session_state.logged_in = False
    st.rerun()

if not st.session_state.logged_in:
    st.title("🏥 MediCloud Secure Portal")
    role = st.selectbox("I am a...", ["Doctor", "Patient"])
    user_id = st.text_input("Login ID")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        # For Hackathon: Hardcoded Doctor login (ID: admin, Pass: admin)
        if role == "Doctor" and user_id == "admin" and password == "admin":
            st.session_state.logged_in = True
            st.session_state.user_role = "Doctor"
            st.rerun()
        else:
            # Check Supabase for Patient
            res = supabase.table("patients").select("*").eq("login_id", user_id).eq("password", password).execute()
            if res.data:
                st.session_state.logged_in = True
                st.session_state.user_role = "Patient"
                st.session_state.user_data = res.data[0]
                st.rerun()
            else:
                st.error("Invalid Credentials")
    st.stop()

# --- DOCTOR DASHBOARD ---
if st.session_state.user_role == "Doctor":
    st.sidebar.button("Logout", on_click=logout)
    st.title("👨‍⚕️ Clinician Control Center")
    
    menu = st.sidebar.radio("Navigation", ["Register New Patient", "Update Records"])
    
    if menu == "Register New Patient":
        name = st.text_input("Full Name")
        if st.button("Generate Account"):
            login_id, password = generate_creds()
            supabase.table("patients").insert({"name": name, "login_id": login_id, "password": password}).execute()
            st.success(f"Patient Registered!\n**ID:** {login_id}  \n**Password:** {password}")

    elif menu == "Update Records":
        patients = supabase.table("patients").select("name, login_id").execute()
        p_list = {p['name']: p['login_id'] for p in patients.data}
        selected_p = st.selectbox("Select Patient", list(p_list.keys()))
        
        uploaded_file = st.file_uploader("Upload Medical Report (PDF/Image)", type=['pdf', 'png', 'jpg'])
        doc_notes = st.text_area("Doctor's Additional Notes")
        
        if st.button("Process & Commit"):
            with st.spinner("AI analyzing multimodal input..."):
                # Handle multimodal AI input (Image/PDF + Text)
                content = ["Analyze this medical report. Extract the findings and translate them into simple English for the patient.", doc_notes]
                if uploaded_file:
                    content.append(uploaded_file)
                
                response = model.generate_content(content)
                summary = response.text
                
                # Update DB
                current_p = supabase.table("patients").select("medical_history").eq("login_id", p_list[selected_p]).execute()
                history = current_p.data[0]['medical_history']
                history.append({"date": str(pd.Timestamp.now()), "summary": summary})
                supabase.table("patients").update({"medical_history": history}).eq("login_id", p_list[selected_p]).execute()
                
                st.success("Record committed to Cloud Database!")
                st.info(f"**AI Summary:** {summary}")

# --- PATIENT DASHBOARD ---
else:
    st.sidebar.button("Logout", on_click=logout)
    st.title(f"👋 Welcome, {st.session_state.user_data['name']}")
    
    history = st.session_state.user_data['medical_history']
    if not history:
        st.write("No medical records available yet.")
    else:
        for entry in reversed(history):
            with st.expander(f"Report from {entry['date']}"):
                st.write(entry['summary'])
