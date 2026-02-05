import streamlit as st
import pandas as pd
import google.generativeai as genai
from supabase import create_client, Client
import random, string
import datetime

# --- 1. APP CONFIG & DB CONNECTION ---
st.set_page_config(page_title="MediCloud AI", layout="wide", page_icon="🏥")

# Connect to Supabase
# Ensure these are set in your Streamlit Cloud Secrets or .streamlit/secrets.toml
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Supabase credentials not found. Please check your secrets.")
    st.stop()

# Configure Gemini
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # --- FIX APPLIED HERE: Using the standard stable model name ---
    model = genai.GenerativeModel("gemini-1.5-flash") 
except Exception as e:
    st.error("Gemini API Key not found. Please check your secrets.")
    st.stop()


# Helper: Generate random credentials
def generate_creds():
    uid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    pwd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"PAT-{uid}", pwd

# --- 2. LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.session_state.user_data = None

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

if not st.session_state.logged_in:
    st.title("🏥 MediCloud Secure Portal")
    role = st.selectbox("I am a...", ["Doctor", "Patient"])
    user_id = st.text_input("Login ID")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        # Doctor Hardcoded Login
        if role == "Doctor" and user_id == "admin" and password == "admin":
            st.session_state.logged_in = True
            st.session_state.user_role = "Doctor"
            st.rerun()
        else:
            # Check Supabase for Patient
            try:
                res = supabase.table("patients").select("*").eq("login_id", user_id).eq("password", password).execute()
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Patient"
                    st.session_state.user_data = res.data[0]
                    st.rerun()
                else:
                    st.error("Invalid Credentials")
            except Exception as e:
                st.error(f"Login Error: {e}")
    st.stop()

# --- 3. DOCTOR DASHBOARD ---
if st.session_state.user_role == "Doctor":
    st.sidebar.button("Logout", on_click=logout)
    st.title("👨‍⚕️ Clinician Control Center")
    
    menu = st.sidebar.radio("Navigation", ["Register New Patient", "Update Records"])
    
    if menu == "Register New Patient":
        st.subheader("Add New Patient to System")
        name = st.text_input("Full Name")
        if st.button("Generate Account"):
            if name:
                login_id, password = generate_creds()
                try:
                    supabase.table("patients").insert({
                        "name": name, 
                        "login_id": login_id, 
                        "password": password,
                        "medical_history": []
                    }).execute()
                    st.success(f"Patient Registered!")
                    st.code(f"ID: {login_id}\nPassword: {password}", language="text")
                    st.info("Copy these credentials for the patient.")
                except Exception as e:
                    st.error(f"Database Error: {e}")
            else:
                st.warning("Please enter a name.")

    elif menu == "Update Records":
        st.subheader("Analyze & Update Patient History")
        # Get all patients
        patients_res = supabase.table("patients").select("name, login_id").execute()
        if not patients_res.data:
            st.write("No patients registered yet.")
        else:
            p_list = {p['name']: p['login_id'] for p in patients_res.data}
            selected_name = st.selectbox("Select Patient", list(p_list.keys()))
            selected_id = p_list[selected_name]
            
            uploaded_file = st.file_uploader("Upload Medical Report (PDF/Image)", type=['pdf', 'png', 'jpg', 'jpeg'])
            doc_notes = st.text_area("Doctor's Additional Notes", placeholder="e.g., Patient feels dizzy, prescribed rest...")
            
            if st.button("Process with AI & Commit"):
                if not uploaded_file and not doc_notes:
                    st.error("Please provide either a file or typed notes.")
                else:
                    with st.spinner("AI is reading the report..."):
                        try:
                            # Prompt setup
                            prompt_text = (
                                "You are a clinical assistant. Analyze this report and doctor's notes. "
                                "Provide a clear, simple summary for the patient explaining what this means. "
                                "Use friendly language and bullet points. "
                                f"Doctor's notes: {doc_notes}"
                            )
                            
                            content_parts = [prompt_text]

                            if uploaded_file:
                                # Reset pointer to start just in case
                                uploaded_file.seek(0)
                                file_data = uploaded_file.read()
                                file_mime = uploaded_file.type
                                
                                # Gemini format for inline data
                                content_parts.append({
                                    "mime_type": file_mime,
                                    "data": file_data
                                })
                            
                            # Generate AI response
                            response = model.generate_content(content_parts)
                            ai_summary = response.text
                            
                            # Fetch existing history to append
                            curr = supabase.table("patients").select("medical_history").eq("login_id", selected_id).execute()
                            history = curr.data[0]['medical_history']
                            if history is None: history = []
                            
                            # Append new entry
                            history.append({
                                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "summary": ai_summary
                            })
                            
                            # Update Database
                            supabase.table("patients").update({"medical_history": history}).eq("login_id", selected_id).execute()
                            
                            st.success("Analysis Complete & Saved to Cloud!")
                            st.markdown("### AI Summary Generated:")
                            st.info(ai_summary)
                            
                        except Exception as e:
                            st.error(f"Error processing AI: {e}")

# --- 4. PATIENT DASHBOARD ---
else:
    st.sidebar.button("Logout", on_click=logout)
    st.title(f"👋 Welcome, {st.session_state.user_data['name']}")
    
    # Refresh data from DB to see latest updates
    try:
        res = supabase.table("patients").select("medical_history").eq("login_id", st.session_state.user_data['login_id']).execute()
        history = res.data[0]['medical_history']
        
        if not history:
            st.info("Your doctor hasn't uploaded any reports yet. They will appear here once processed.")
        else:
            st.subheader("Your Medical History")
            for entry in reversed(history):
                with st.expander(f"Report from {entry['date']}", expanded=True):
                    st.markdown(entry['summary'])
    except Exception as e:
        st.error(f"Error fetching records: {e}")
