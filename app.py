import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import random, string
import datetime
from PIL import Image

# --- 1. APP CONFIG ---
st.set_page_config(page_title="MediCloud AI", layout="wide", page_icon="🏥")

# Connect to Supabase
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Supabase secrets missing.")
    st.stop()

# Configure Gemini
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("Gemini API Key missing.")
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
                except Exception as e:
                    st.error(f"Database Error: {e}")

    elif menu == "Update Records":
        st.subheader("Analyze & Update Patient History")
        patients_res = supabase.table("patients").select("name, login_id").execute()
        
        if not patients_res.data:
            st.write("No patients registered.")
        else:
            p_list = {p['name']: p['login_id'] for p in patients_res.data}
            selected_name = st.selectbox("Select Patient", list(p_list.keys()))
            selected_id = p_list[selected_name]
            
            uploaded_file = st.file_uploader("Upload Medical Report (Image/PDF)", type=['png', 'jpg', 'jpeg', 'pdf'])
            doc_notes = st.text_area("Doctor's Notes", placeholder="E.g., Patient showing signs of fatigue...")
            
            if st.button("Process with AI & Commit"):
                with st.spinner("AI is analyzing image & text..."):
                    try:
                        # --- 1. MODEL SELECTION & FALLBACK ---
                        model = None
                        # Try Flash first (fastest/cheapest), then Pro, then fallback
                        for m_name in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]:
                            try:
                                test_m = genai.GenerativeModel(m_name)
                                model = test_m
                                break
                            except:
                                continue
                        
                        if not model:
                            st.error("Could not connect to Google AI. Please update 'google-generativeai' library.")
                            st.stop()

                        # --- 2. PREPARE CONTENT ---
                        content_parts = []
                        prompt = (
                            "You are a helpful medical assistant. Analyze the attached medical report image "
                            "and the doctor's notes. Create a simple, easy-to-understand summary for the patient. "
                            f"\n\nDoctor's Notes: {doc_notes}"
                        )
                        content_parts.append(prompt)

                        if uploaded_file:
                            # Handling Images specifically for Gemini
                            mime_type = uploaded_file.type
                            if "image" in mime_type:
                                image = Image.open(uploaded_file)
                                content_parts.append(image)
                            else:
                                # For PDFs, we pass the raw bytes
                                content_parts.append({
                                    "mime_type": mime_type,
                                    "data": uploaded_file.getvalue()
                                })

                        # --- 3. GENERATE & SAVE ---
                        response = model.generate_content(content_parts)
                        ai_summary = response.text
                        
                        # Save to Supabase
                        curr = supabase.table("patients").select("medical_history").eq("login_id", selected_id).execute()
                        history = curr.data[0]['medical_history'] or []
                        
                        history.append({
                            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "summary": ai_summary
                        })
                        
                        supabase.table("patients").update({"medical_history": history}).eq("login_id", selected_id).execute()
                        
                        st.success("Analysis Saved!")
                        st.info(ai_summary)

                    except Exception as e:
                        st.error(f"AI Error: {e}")

# --- 4. PATIENT DASHBOARD ---
else:
    st.sidebar.button("Logout", on_click=logout)
    st.title(f"👋 Welcome, {st.session_state.user_data['name']}")
    
    try:
        res = supabase.table("patients").select("medical_history").eq("login_id", st.session_state.user_data['login_id']).execute()
        history = res.data[0]['medical_history']
        
        if not history:
            st.info("No records found.")
        else:
            st.subheader("Your Medical History")
            for entry in reversed(history):
                with st.expander(f"Report: {entry['date']}", expanded=True):
                    st.markdown(entry['summary'])
    except:
        st.error("Could not load history.")
