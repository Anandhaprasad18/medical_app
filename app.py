import streamlit as st
import pandas as pd
import datetime

# --- CONFIGURATION & MOCK DATABASE ---
st.set_page_config(page_title="Medi-CoPilot", layout="wide")

# We use Streamlit 'Session State' to simulate a database that persists while the app is running.
if 'patient_db' not in st.session_state:
    st.session_state['patient_db'] = []

# Mock "AI" Functions (In a real app, these would call OpenAI/AWS APIs)
def mock_ocr_processing(uploaded_file):
    # Simulates reading a handwritten prescription
    return "Rx: Atorvastatin 80mg, Metformin 500mg. Dx: Hyperlipidemia."

def mock_clinical_alert_system(notes, vitals):
    alerts = []
    # Simple keyword detection to simulate interactions
    if "Atorvastatin" in notes and "Clarithromycin" in notes:
        alerts.append("🔴 CRITICAL: Drug Interaction detected (Statin + Macrolide). Risk of Myopathy.")
    elif "Atorvastatin" in notes:
        alerts.append("🟡 GUIDELINE: Patient on high-dose statin. Monitor LFTs.")
    
    if vitals['bp_sys'] > 140:
        alerts.append("🔴 RISK: Stage 2 Hypertension detected.")
    
    return alerts if alerts else ["✅ No immediate alerts detected."]

def mock_patient_translator(medical_notes):
    # Simulates the LLM converting jargon to simple English
    translation = f"Based on your visit: The doctor has prescribed medication to help lower your cholesterol (Atorvastatin) and manage blood sugar (Metformin). \n\n**Action Plan:** Take pills with dinner. Avoid grapefruit juice as it interacts with your medication."
    return translation

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏥 AI Clinical System")
role = st.sidebar.radio("Login As:", ["Doctor (Provider)", "Patient"])

# --- DOCTOR PORTAL ---
if role == "Doctor (Provider)":
    st.title("👨‍⚕️ Clinician Dashboard")
    st.markdown("---")

    # 1. New Patient Entry
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 New Consultation")
        p_name = st.text_input("Patient Name")
        p_age = st.number_input("Age", min_value=0, max_value=120)
        
        st.markdown("**Vitals Input (EHR Data):**")
        bp_sys = st.number_input("Systolic BP (mmHg)", value=120)
        cholesterol = st.number_input("Total Cholesterol", value=180)
        
        st.markdown("**Medical Inputs:**")
        upload = st.file_uploader("Upload Handwritten Rx (Simulated)", type=['png', 'jpg'])
        
        # If no image, allow manual typing (Simulation of OCR output)
        manual_notes = st.text_area("Or Type Clinical Notes / Prescriptions", 
                                    "Rx: Atorvastatin 80mg daily. Dx: Hyperlipidemia.")

    # 2. AI Analysis & Review
    with col2:
        st.subheader("🤖 AI Real-Time Analysis")
        
        if st.button("Analyze & Generate Report"):
            # Run the "AI"
            alerts = mock_clinical_alert_system(manual_notes, {'bp_sys': bp_sys})
            patient_explanation = mock_patient_translator(manual_notes)
            
            # Display Clinical Alerts (Doctor View)
            st.info("### 🩺 Clinical Decision Support")
            for alert in alerts:
                if "CRITICAL" in alert:
                    st.error(alert)
                elif "RISK" in alert:
                    st.warning(alert)
                else:
                    st.success(alert)
            
            # Display Patient View Preview
            st.success("### 🗣️ Patient-Friendly Explanation")
            st.write(patient_explanation)

            # Save to Database
            new_record = {
                "id": len(st.session_state['patient_db']) + 1,
                "name": p_name,
                "date": datetime.date.today(),
                "notes": manual_notes,
                "alerts": alerts,
                "explanation": patient_explanation
            }
            st.session_state['patient_db'].append(new_record)
            st.toast(f"Record for {p_name} saved to database!")

    # 3. View Database
    st.markdown("---")
    st.subheader("📂 Patient Database")
    if st.session_state['patient_db']:
        df = pd.DataFrame(st.session_state['patient_db'])
        st.dataframe(df[['id', 'name', 'date', 'notes']])
    else:
        st.write("No patients in database yet.")

# --- PATIENT PORTAL ---
elif role == "Patient":
    st.title("👤 Patient Health Portal")
    st.markdown("---")
    
    if not st.session_state['patient_db']:
        st.warning("No records found. Please ask your doctor to submit a report.")
    else:
        # Patient "Login" (Simple dropdown for demo)
        patient_names = [p['name'] for p in st.session_state['patient_db']]
        selected_patient = st.selectbox("Select Your Name to View Report", patient_names)
        
        # Find patient record
        record = next(p for p in st.session_state['patient_db'] if p['name'] == selected_patient)
        
        # Display The Simple Report
        st.header(f"Hello, {record['name']}")
        st.info(f"📅 Report Date: {record['date']}")
        
        st.markdown("### 🔍 Your Visit Summary")
        st.write(record['explanation'])
        
        st.markdown("### 💊 Reminders")
        st.write("- Taking your medication daily reduces heart risk by 25%.")
        st.write("- Please schedule a follow-up in 3 months.")

        with st.expander("Show Original Medical Notes (Technical)"):
            st.text(record['notes'])