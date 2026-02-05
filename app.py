import streamlit as st
import pandas as pd
from groq import Groq
from supabase import create_client, Client
import random, string, datetime, base64
from PIL import Image
import io

# --- 1. APP CONFIG & CONNECTIONS ---
st.set_page_config(page_title="MediCloud AI (Groq)", layout="wide", page_icon="🏥")

# Supabase Setup
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception:
    st.error("Check Supabase Secrets for URL and KEY.")
    st.stop()

# Groq Setup
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("Groq API Key not found in secrets.")
    st.stop()

# Helper: Encode image to base64 for Groq Vision
def encode_image(image_file):
    return base64.b64encode(image_file.read()).decode('utf-8')

def generate_creds():
    uid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    pwd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"PAT-{uid}", pwd

# --- 2. LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = None

if not st.session_state.logged_in:
    st.title("🏥 MediCloud Portal (Powered by Groq)")
    role = st.selectbox("Role", ["Doctor", "Patient"])
    user_id = st.text_input("ID")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if role == "Doctor" and user_id == "admin" and password == "admin":
            st.session_state.update({"logged_in": True, "user_role": "Doctor"})
            st.rerun()
        else:
            try:
                res = supabase.table("patients").select("*").eq("login_id", user_id).eq("password", password).execute()
                if res.data:
                    st.session_state.update({"logged_in": True, "user_role": "Patient", "user_data": res.data[0]})
                    st.rerun()
                else: 
                    st.error("Invalid Login Credentials")
            except Exception as e:
                st.error(f"Database Error: {e}")
    st.stop()

# --- 3. DOCTOR DASHBOARD ---
if st.session_state.user_role == "Doctor":
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
    st.title("👨‍⚕️ Clinician Dashboard")
    
    menu = st.sidebar.radio("Menu", ["Register Patient", "Upload & Analyze"])
    
    if menu == "Register Patient":
        st.subheader("New Patient Registration")
        name = st.text_input("Patient Full Name")
        if st.button("Create Account"):
            if name:
                lid, pwd = generate_creds()
                supabase.table("patients").insert({
                    "name": name, 
                    "login_id": lid, 
                    "password": pwd, 
                    "medical_history": []
                }).execute()
                st.success(f"Patient Created Successfully!")
                st.code(f"ID: {lid}\nPassword: {pwd}")
            else:
                st.warning("Please enter a name.")

    elif menu == "Upload & Analyze":
        st.subheader("Medical Image Analysis")
        p_res = supabase.table("patients").select("name, login_id").execute()
        
        if not p_res.data:
            st.info("No patients registered yet.")
        else:
            patients = {p['name']: p['login_id'] for p in p_res.data}
            target_name = st.selectbox("Select Patient", list(patients.keys()))
            target_id = patients[target_name]
            
            file = st.file_uploader("Upload Medical Scan (JPG/PNG)", type=['png', 'jpg', 'jpeg'])
            notes = st.text_area("Doctor's Observations/Context")
            
            if st.button("Run AI Analysis"):
                if not file and not notes:
                    st.error("Please provide an image or some notes for the AI.")
                else:
                    with st.spinner("Groq AI is analyzing..."):
                        try:
                            # Constructing the message
                            user_content = [
                                {
                                    "type": "text", 
                                    "text": f"You are a medical assistant. Analyze this report/image and these notes: '{notes}'. Provide a friendly, clear bulleted summary for the patient."
                                }
                            ]
                            
                            if file:
                                base64_image = encode_image(file)
                                user_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                })

                            # Calling Groq with the updated vision model
                            completion = client.chat.completions.create(
                                model="llama-3.2-90b-vision-preview", # Updated to the 90b stable vision model
                                messages=[{"role": "user", "content": user_content}],
                                temperature=0.5,
                                max_tokens=1024
                            )
                            
                            summary = completion.choices[0].message.content
                            
                            # Retrieve and Update Database History
                            curr_data = supabase.table("patients").select("medical_history").eq("login_id", target_id).execute()
                            hist = curr_data.data[0]['medical_history'] or []
                            
                            hist.append({
                                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
                                "summary": summary
                            })
                            
                            supabase.table("patients").update({"medical_history": hist}).eq("login_id", target_id).execute()
                            
                            st.success("Analysis Complete!")
                            st.markdown("### AI Summary for Patient")
                            st.info(summary)
                            
                        except Exception as e:
                            st.error(f"Groq Error: {e}")

# --- 4. PATIENT VIEW ---
else:
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
    st.title(f"👋 Welcome, {st.session_state.user_data['name']}")
    
    # Refresh data from Supabase
    res = supabase.table("patients").select("medical_history").eq("login_id", st.session_state.user_data['login_id']).execute()
    history = res.data[0]['medical_history']
    
    if not history:
        st.info("Your medical records will appear here once your doctor uploads them.")
    else:
        st.subheader("Your Medical History")
        for item in reversed(history):
            with st.expander(f"Report Date: {item['date']}", expanded=True):
                st.markdown(item['summary'])
