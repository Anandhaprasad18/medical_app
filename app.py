import streamlit as st
import pandas as pd
import google.generativeai as genai
from supabase import create_client, Client
import random, string
import datetime

# --- 1. APP CONFIG & DB CONNECTION ---
st.set_page_config(page_title="MediCloud AI", layout="wide", page_icon="🏥")

# Connect to Supabase
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
        if role == "Doctor" and user_id == "admin" and password == "admin":
            st.session_state.logged_in = True
            st.session_state.user_role = "Doctor"
            st.rerun()
        else:
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
        patients_res = supabase.table("patients").select("name, login_id").execute()
        if not patients_res.data:
            st.write("No patients registered yet.")
        else:
            p_list = {p['name']: p['login_id'] for p in patients_res.data}
            selected_name = st.selectbox("Select Patient", list(p_list.keys()))
            selected_id = p_list[selected_name]
            
            uploaded_file = st.file_uploader("Upload Medical Report (PDF/Image)", type=['pdf', 'png', 'jpg', 'jpeg'])
            doc_notes = st.text_area("Doctor's Additional Notes", placeholder="e.g., Patient feels dizzy...")
            
            if st.button("Process with AI & Commit"):
                if not uploaded_file and not doc_notes:
                    st.error("Please provide either a file or typed notes.")
                else:
                    with st.spinner("AI is reading the report..."):
                        try:
                            # --- ROBUST MODEL SELECTION ---
                            # We try Flash first, then Pro, then standard Gemini
                            valid_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
                            active_model = None
                            
                            # Simple retry logic to find a working model
                            for m_name in valid_models:
                                try:
                                    test_model = genai.GenerativeModel(m_name)
                                    # Very cheap test call
                                    test_model.generate_content("test")
                                    active_model = test_model
                                    break # Found one that works
                                except:
                                    continue
                            
                            if not active_model:
                                st.error("Could not connect to any Gemini models. Check API Key or Library Version.")
                                st.stop()

                            # Prepare Content
                            prompt_text = (
                                "You are a clinical assistant. Analyze this report and doctor's notes. "
                                "Provide a clear, simple summary for the patient explaining what this means. "
                                "Use friendly language and bullet points. "
                                f"Doctor's notes: {doc_notes}"
                            )
                            content_parts = [prompt_text]

                            if uploaded_file:
                                uploaded_file.seek(0)
                                content_parts.append({
                                    "mime_type": uploaded_file.type,
                                    "data": uploaded_file.read()
                                })
                            
                            # Generate
                            response = active_model.generate_content(content_parts)
                            ai_summary = response.text
                            
                            # Save to Supabase
                            curr = supabase.table("patients").select("medical_history").eq("login_id", selected_id).execute()
                            history = curr.data[0]['medical_history']
                            if history is None: history = []
                            
                            history.append({
                                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "summary": ai_summary
                            })
                            
                            supabase.table("patients").update({"medical_history": history}).eq("login_id", selected_id).execute()
                            
                            st.success("Analysis Complete & Saved!")
                            st.markdown("### AI Summary Generated:")
                            st.info(ai_summary)
                            
                        except Exception as e:
                            st.error(f"Error processing AI: {e}")

# --- 4. PATIENT DASHBOARD ---
else:
    st.sidebar.button("Logout", on_click=logout)
    st.title(f"👋 Welcome, {st.session_state.user_data['name']}")
    
    try:
        res = supabase.table("patients").select("medical_history").eq("login_id", st.session_state.user_data['login_id']).execute()
        history = res.data[0]['medical_history']
        
        if not history:
            st.info("Your doctor hasn't uploaded any reports yet.")
        else:
            st.subheader("Your Medical History")
            for entry in reversed(history):
                with st.expander(f"Report from {entry['date']}", expanded=True):
                    st.markdown(entry['summary'])
    except Exception as e:
        st.error(f"Error fetching records: {e}")
