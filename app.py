import streamlit as st
import pandas as pd
from groq import Groq
from supabase import create_client, Client
import random, string, datetime, base64
from PIL import Image
import io

# --- 1. APP CONFIG & CONNECTIONS ---
st.set_page_config(page_title="MediCloud AI (Llama 4)", layout="wide", page_icon="🏥")

# Supabase Setup
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception:
    st.error("Check Supabase Secrets.")
    st.stop()

# Groq Setup
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("Groq API Key not found in secrets.")
    st.stop()

# Helper: Encode image to base64
def encode_image(image_file):
    return base64.b64encode(image_file.read()).decode('utf-8')

def generate_creds():
    uid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    pwd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"PAT-{uid}", pwd

# --- 2. LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in, st.session_state.user_role = False, None

if not st.session_state.logged_in:
    st.title("🏥 MediCloud Portal (Powered by Llama 4)")
    role = st.selectbox("Role", ["Doctor", "Patient"])
    user_id = st.text_input("ID")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if role == "Doctor" and user_id == "admin" and password == "admin":
            st.session_state.update({"logged_in": True, "user_role": "Doctor"})
            st.rerun()
        else:
            res = supabase.table("patients").select("*").eq("login_id", user_id).eq("password", password).execute()
            if res.data:
                st.session_state.update({"logged_in": True, "user_role": "Patient", "user_data": res.data[0]})
                st.rerun()
            else: st.error("Invalid Login")
    st.stop()

# --- 3. DOCTOR DASHBOARD ---
if st.session_state.user_role == "Doctor":
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
    st.title("👨‍⚕️ Clinician Dashboard")
    
    menu = st.sidebar.radio("Menu", ["Register Patient", "Upload & Analyze"])
    
    if menu == "Register Patient":
        name = st.text_input("Patient Name")
        if st.button("Create Account"):
            lid, pwd = generate_creds()
            supabase.table("patients").insert({"name": name, "login_id": lid, "password": pwd, "medical_history": []}).execute()
            st.success(f"Created! ID: {lid} | Pwd: {pwd}")

    elif menu == "Upload & Analyze":
        p_res = supabase.table("patients").select("name, login_id").execute()
        patients = {p['name']: p['login_id'] for p in p_res.data}
        target = st.selectbox("Select Patient", list(patients.keys()))
        
        file = st.file_uploader("Upload Medical Scan/Report", type=['png', 'jpg', 'jpeg'])
        notes = st.text_area("Observations")
        
        if st.button("Analyze with Llama 4"):
            with st.spinner("Llama 4 Scout is processing..."):
                try:
                    # Content structure for Llama 4 Multimodal
                    content = [{"type": "text", "text": f"Analyze this medical image and these notes: {notes}. Provide a patient-friendly summary."}]
                    
                    if file:
                        base64_image = encode_image(file)
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })

                    completion = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{"role": "user", "content": content}],
                        temperature=0.1, # Keep temperature low for medical accuracy
                        max_tokens=2048
                    )
                    
                    summary = completion.choices[0].message.content
                    
                    # Update DB
                    hist = supabase.table("patients").select("medical_history").eq("login_id", patients[target]).execute().data[0]['medical_history'] or []
                    hist.append({"date": str(datetime.date.today()), "summary": summary})
                    supabase.table("patients").update({"medical_history": hist}).eq("login_id", patients[target]).execute()
                    
                    st.success("Analysis Complete!")
                    st.info(summary)
                except Exception as e:
                    st.error(f"Groq Error: {e}")

# --- 4. PATIENT VIEW ---
else:
    st.title(f"Record for {st.session_state.user_data['name']}")
    history = supabase.table("patients").select("medical_history").eq("login_id", st.session_state.user_data['login_id']).execute().data[0]['medical_history']
    for item in reversed(history or []):
        with st.expander(f"Report: {item['date']}"):
            st.markdown(item['summary'])
