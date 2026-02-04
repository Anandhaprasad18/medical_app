import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai

# --- AI CONFIGURATION ---
st.set_page_config(page_title="Medi-CoPilot AI", layout="wide")

# Sidebar for API Key
with st.sidebar:
    st.title("⚙️ Settings")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize Database
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = []

# --- REAL AI FUNCTIONS ---

def get_ai_analysis(notes, vitals_summary):
    """Calls Gemini to get both clinical alerts and patient summary in one go."""
    if not api_key:
        return ["⚠️ Please enter API Key in sidebar"], "API Key missing. AI cannot translate."
    
    prompt = f"""
    You are a dual-purpose medical AI. 
    INPUT:
    Clinical Notes: {notes}
    Patient Vitals: {vitals_summary}

    TASK:
    1. Generate 'Clinical Alerts' for a doctor (Drug interactions, high risks, or guideline reminders).
    2. Generate a 'Patient Summary' in very simple, friendly English (6th-grade level).

    FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
    ALERTS: [List each alert starting with a bullet]
    SUMMARY: [The simple explanation]
    """
    
    try:
        response = model.generate_content(prompt)
        full_text = response.text
        
        # Split the response into Alerts and Summary
        alerts_part = full_text.split("ALERTS:")[1].split("SUMMARY:")[0].strip()
        summary_part = full_text.split("SUMMARY:")[1].strip()
        
        alerts_list = [a.strip() for a in alerts_part.split("\n") if a.strip()]
        return alerts_list, summary_part
    except Exception as e:
        return [f"❌ AI Error: {str(e)}"], "Could not generate summary."

# --- UI LOGIC ---
st.sidebar.markdown("---")
role = st.sidebar.radio("Login As:", ["Doctor (Provider)", "Patient"])

if role == "Doctor (Provider)":
    st.title("👨‍⚕️ Clinician Dashboard")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 New Consultation")
        p_name = st.text_input("Patient Name")
        bp_sys = st.number_input("Systolic BP", value=120)
        manual_notes = st.text_area("Clinical Notes (Rx, Symptoms, Labs)", 
                                   "Patient prescribed Warfarin. Also taking Aspirin for pain.")

    with col2:
        st.subheader("🤖 AI Intelligence")
        if st.button("Run AI Analysis"):
            with st.spinner("Analyzing medical data..."):
                vitals_info = f"BP: {bp_sys}"
                alerts, summary = get_ai_analysis(manual_notes, vitals_info)
                
                st.session_state['current_alerts'] = alerts
                st.session_state['current_summary'] = summary
                
                st.info("### 🩺 Clinical Alerts")
                for a in alerts:
                    st.write(a)
                
                st.success("### 🗣️ Patient Translation")
                st.write(summary)

                # Save record
                st.session_state['patient_db'].append({
                    "name": p_name,
                    "date": datetime.date.today(),
                    "notes": manual_notes,
                    "alerts": alerts,
                    "explanation": summary
                })

elif role == "Patient":
    st.title("👤 Patient Portal")
    if not st.session_state['patient_db']:
        st.warning("No records found.")
    else:
        names = [p['name'] for p in st.session_state['patient_db']]
        sel = st.selectbox("Select Profile", names)
        rec = next(p for p in st.session_state['patient_db'] if p['name'] == sel)
        
        st.header(f"Welcome, {rec['name']}")
        st.info(f"Your doctor's visit on {rec['date']}")
        st.markdown("### 🔍 What this means for you:")
        st.write(rec['explanation'])
        
        with st.expander("Technical Details"):
            st.text(rec['notes'])
