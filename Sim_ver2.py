import streamlit as st
import pandas as pd
import io
import re
import os
import sys
import json
import difflib
from datetime import datetime

# ReportLab imports for PDF briefing generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# PAGE CONFIG & HYBRID THEME STYLING
# ==========================================
st.set_page_config(
    page_title="Flight Sim Scenario & EBT Competency Optimizer",
    page_icon="✈️",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .block-container {
        padding-top: 1.0rem !important;
        padding-bottom: 1.0rem !important;
        max-width: 96% !important;
    }
    .main { background-color: #0B132B; color: #F8FAFC; }
    h1, h2, h3, h4 { color: #38BDF8 !important; font-weight: 700 !important; margin-top: 6px !important; margin-bottom: 6px !important;}
    
    /* IOS Card Panel Styling (Dark) */
    div[data-testid="stForm"], div[data-testid="stContainer"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    
    /* Restored Metrics Styling (White Background, Blue Text) */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stMetricLabel"] * {
        color: #64748B !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] {
        background-color: transparent !important;
        border: none !important;
    }
    div[data-testid="stMetricValue"] * {
        color: #0284C7 !important;
        font-weight: 700 !important;
    }

    .ios-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .ios-label {
        font-size: 11px;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    .ios-value {
        font-size: 18px;
        color: #38BDF8;
        font-weight: 700;
    }

    /* Restructured Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #070D1E;
        color: #FFFFFF;
        min-width: 310px !important; 
        max-width: 310px !important;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown {
        color: #FFFFFF !important;
    }
    .sidebar-header {
        font-size: 13px;
        font-weight: 700;
        color: #38BDF8;
        letter-spacing: 0.04em;
        margin-bottom: 6px;
    }
    .slot-container {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-left: 3px solid #0284C7;
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 8px;
    }
    .slot-title {
        font-size: 11px;
        font-weight: 700;
        color: #94A3B8;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .status-badge-ok {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-align: center;
    }
    .status-badge-warn {
        background-color: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.3);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-align: center;
    }

    /* Button enhancements */
    .stButton>button {
        background-color: #0284C7;
        color: #FFFFFF;
        border-radius: 6px;
        font-weight: 600;
        border: none;
        padding: 0.45rem 0.9rem;
        transition: all 0.15s ease;
    }
    .stButton>button:hover {
        background-color: #0369A1;
        color: #FFFFFF;
        transform: translateY(-1px);
    }
    .thin-divider {
        margin: 12px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    }
</style>
""", unsafe_allow_html=True)

# Header Section
st.title("✈️ Simulator Session Plan & IOS Setup Builder")
st.markdown("<p style='color: #94A3B8; font-size: 14px; margin-top: -8px; font-weight: 500;'>KM Malta A320 STD2.2 / Advanced Evidence-Based Training (EBT) Optimizer</p>", unsafe_allow_html=True)

PHASE_NAMES = {
    1: "Phase 1 – Pre-flight and Taxi",
    2: "Phase 2 – Take-off",
    3: "Phase 3 – Climb",
    4: "Phase 4 – Cruise",
    5: "Phase 5 – Descent",
    6: "Phase 6 – Approach",
    7: "Phase 7 – Landing",
    8: "Phase 8 – Taxi and post-flight"
}

COMPETENCY_KEYS = {
    "APK": "Application of Knowledge / Procedures",
    "COM": "Communication",
    "FPM": "Flight Path Management",
    "FPA": "Flight Path Authority / Angle",
    "LTW": "Leadership & Teamwork",
    "PSD": "Problem Solving & Decision Making",
    "SA":  "Situational Awareness",
    "WLM": "Workload Management"
}

ALL_PHASE_KEYS = [1, 2, 3, 4, 5, 6, 7, 8]
ROLE_OPTIONS = ["PF Focus", "PM Focus", "Both / CRM", "Instructor Choice"]

# ==========================================
# ENTERPRISE CONFIGURATION TABS
# ==========================================
tab_session, tab_ios, tab_weather = st.tabs(["⚙️ Session & Crew Setup", "🖥️ Aircraft & Airport Parameters", "🌐 Environment & Weather IOS Panel"])

with tab_session:
    with st.container(border=True):
        st.markdown("#### ⚙️ Session Metadata & Device Setup")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            session_mode = st.selectbox("Training Focus / Mode", ["EBT Evaluation & Coaching", "EBT Line-Oriented Assessment", "Recurrent Check (LPC/OPC)"])
        with m_col2:
            capt_name = st.text_input("Captain Name", value="Capt. Unassigned")
        with m_col3:
            fo_name = st.text_input("First Officer Name", value="F/O Unassigned")
        with m_col4:
            sim_id = st.text_input("Sim / Device ID", value="KM Malta A320 STD2.2")

        p_col1, p_col2 = st.columns([1.5, 3.5])
        with p_col1:
            max_dod_threshold = st.number_input("Total DOD Ceiling", min_value=1, max_value=30, value=6, step=1)
        with p_col2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            allow_fallback = st.checkbox("Enable Smart Fallback (use closest available DOD if exact match missing)", value=True)

with tab_ios:
    with st.container(border=True):
        st.markdown("#### ✈️ Aircraft Mass & Balance (IOS Parameters)")
        i_col1, i_col2, i_col3, i_col4, i_col5 = st.columns(5)
        with i_col1:
            gw_val = st.number_input("GW (kg x1000)", min_value=40.0, max_value=79.0, value=54.6, step=0.5)
            gw_cg = st.number_input("GW CG (%)", min_value=15.0, max_value=40.0, value=29.0, step=0.1)
        with i_col2:
            zfw_val = st.number_input("ZFW (kg x1000)", min_value=35.0, max_value=64.3, value=47.0, step=0.5)
            zfw_cg = st.number_input("ZFW CG (%)", min_value=15.0, max_value=40.0, value=31.0, step=0.1)
        with i_col3:
            total_fuel = st.number_input("Total Fuel (kg x1000)", min_value=1.5, max_value=19.0, value=7.6, step=0.1)
        with i_col4:
            alt_asl = st.number_input("Init Alt (ft ASL)", min_value=0, max_value=39000, value=293)
        with i_col5:
            qnh_val = st.number_input("QNH (hPa)", min_value=950, max_value=1050, value=1013)

    with st.container(border=True):
        st.markdown("#### 🏛️ Airport Diagram & Runways Reference")
        a_col1, a_col2, a_col3, a_col4 = st.columns(4)
        with a_col1:
            apt_ref = st.text_input("Reference Airport / Rwy", value="LFPO / 24")
        with a_col2:
            ils_ident = st.text_input("ILS Ident / Freq", value="OLO / 110.90")
        with a_col3:
            loc_course = st.number_input("Loc Course (°M)", min_value=0, max_value=360, value=241)
        with a_col4:
            apt_elev = st.number_input("Airport Elev (ft)", min_value=-100, max_value=14000, value=284)

with tab_weather:
    st.markdown("#### 🌐 IOS Current Conditions & Environment Setup")
    w_card1, w_card2 = st.columns(2)
    
    with w_card1:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>🌬️ Surface Wind & Atmosphere</b>", unsafe_allow_html=True)
            wc1, wc2, wc3 = st.columns(3)
            with wc1:
                wind_dir = st.number_input("Wind Dir (°M)", min_value=0, max_value=360, value=360, step=10)
            with wc2:
                wind_spd = st.number_input("Wind Speed (kt)", min_value=0, max_value=70, value=0)
            with wc3:
                wind_gust = st.number_input("Wind Gust (kt)", min_value=0, max_value=90, value=0)
            
            wind_str = f"{wind_dir:03d}°M / {wind_spd} kt" + (f" G {wind_gust} kt" if wind_gust > 0 else "")

            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                oat_temp = st.number_input("Aircraft OAT (°C)", min_value=-40, max_value=50, value=14)
            with tc2:
                isa_standard = 15 - (2 * (apt_elev / 1000))
                isa_dev_calc = int(oat_temp - isa_standard)
                isa_dev = st.number_input("ISA Dev (°C)", min_value=-30, max_value=30, value=isa_dev_calc)
            with tc3:
                qnh_weather = st.number_input("QNH Ref (hPa)", min_value=950, max_value=1050, value=1013)

    with w_card2:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>🌧️ Runway Surface & Visibility Parameters</b>", unsafe_allow_html=True)
            rc1, rc2 = st.columns(2)
            with rc1:
                rcam_code = st.selectbox(
                    "Runway Cnd Ref (RCAM x/x/x)",
                    [
                        "6/6/6 – Dry",
                        "5/5/5 – Good (Frost / Wet <= 3mm)",
                        "4/4/4 – Good to Medium (Compacted Snow <= -15°C)",
                        "3/3/3 – Medium (Slippery Wet / Dry Snow)",
                        "2/2/2 – Medium to Poor (Standing Water / Slush)",
                        "1/1/1 – Poor (Ice)",
                        "0/0/0 – Less than Poor"
                    ]
                )
            with rc2:
                precip_ref = st.selectbox(
                    "Precipitation Ref",
                    ["None", "Light Rain", "Moderate Rain", "Heavy Rain", "Light Snow", "Moderate Snow", "Freezing Rain / Drizzle"]
                )

            vc1, vc2 = st.columns(2)
            with vc1:
                vis_rvr_str = st.selectbox(
                    "Visibility / RVR",
                    ["250.00 km (CAVOK)", "10.00 km", "5000 m", "1500 m", "550 m (CAT I)", "300 m (CAT II)", "125 m (CAT III B)", "75 m (LVTO Limit)"],
                    index=0
                )
            with vc2:
                rwy_lighting = st.selectbox(
                    "Runway Lighting",
                    ["Off (0)", "Level 1 (Low)", "Level 2 (Medium)", "Level 3 (High / Standard)", "Level 4 (Max / LVO)"],
                    index=3
                )

    w_card3, w_card4 = st.columns(2)
    with w_card3:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>☁️ Clouds & Ceiling Reference</b>", unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            with cc1:
                cloud_coverage = st.selectbox("Clouds Coverage", ["Clear", "FEW (1-2 octas)", "SCT (3-4 octas)", "BKN (5-7 octas)", "OVC (8 octas)"])
            with cc2:
                cloud_base = st.number_input("Cloud Base (ft AGL)", min_value=0, max_value=20000, value=1500 if cloud_coverage != "Clear" else 5000, step=100)

    with w_card4:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>⚠️ Atmospheric Hazards & Turbulence</b>", unsafe_allow_html=True)
            hc1, hc2, hc3 = st.columns(3)
            with hc1:
                windshear_opt = st.selectbox("Windshears / Microburst", ["None", "Light Windshear", "Moderate Microburst", "Severe Microburst"])
            with hc2:
                turb_opt = st.selectbox("Turbulence at Aircraft", ["None", "Base 5% (Light)", "Moderate (15%)", "Severe (30%)"])
            with hc3:
                icing_opt = st.selectbox("Icing Conditions", ["None", "Trace / Light", "Moderate", "Severe"])

    ios_env_summary_str = f"Wind: {wind_str} | OAT: {oat_temp}°C (ISA {isa_dev:+d}°C) | QNH: {qnh_weather} hPa | Rwy Cnd: {rcam_code.split('–')[0].strip()} | Precip: {precip_ref} | Vis: {vis_rvr_str} | Clouds: {cloud_coverage} @ {cloud_base}ft | Rwy Lt: {rwy_lighting}"

    # Live Telemetry Display
    st.markdown("<div class='ios-card'>", unsafe_allow_html=True)
    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)
    p_col1.markdown(f"<div class='ios-label'>Wind</div><div class='ios-value'>{wind_str}</div>", unsafe_allow_html=True)
    p_col2.markdown(f"<div class='ios-label'>OAT / ISA</div><div class='ios-value'>{oat_temp}°C / {isa_dev:+d}°C</div>", unsafe_allow_html=True)
    p_col3.markdown(f"<div class='ios-label'>RCAM Code</div><div class='ios-value'>{rcam_code.split('–')[0].strip()}</div>", unsafe_allow_html=True)
    p_col4.markdown(f"<div class='ios-label'>Visibility</div><div class='ios-value'>{vis_rvr_str.split(' ')[0]}</div>", unsafe_allow_html=True)
    p_col5.markdown(f"<div class='ios-label'>Precipitation</div><div class='ios-value'>{precip_ref}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

ios_summary_str = f"Apt: {apt_ref} | GW: {gw_val}t (CG {gw_cg}%) | ZFW: {zfw_val}t | Fuel: {total_fuel}t | QNH: {qnh_val}hPa | Env: {ios_env_summary_str}"

# ==========================================
# ROBUST SIDEBAR: SLOTS CONFIGURATION
# ==========================================
st.sidebar.markdown("<div class='sidebar-header'>📍 SLOT CONFIGURATION</div>", unsafe_allow_html=True)

if "slot_list" not in st.session_state:
    st.session_state.slot_list = [
        {"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False},
        {"phase": 2, "dod": 2, "role": "PF Focus", "type": "Any", "mandatory": False},
        {"phase": 6, "dod": 2, "role": "PM Focus", "type": "Any", "mandatory": False},
        {"phase": 7, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False}
    ]

btn_c1, btn_c2 = st.sidebar.columns(2)
if btn_c1.button("➕ Add Slot", use_container_width=True):
    if len(st.session_state.slot_list) < 12:
        st.session_state.slot_list.append({"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False})
        st.rerun()

if btn_c2.button("❌ Remove", use_container_width=True):
    if len(st.session_state.slot_list) > 1:
        idx = len(st.session_state.slot_list) - 1
        st.session_state.slot_list.pop()
        # Clean up session state keys to prevent ghost states
        for key in ["phase_sel_", "dod_sel_", "role_sel_", "type_sel_", "ata_sel_", "mand_sel_"]:
            if f"{key}{idx}" in st.session_state:
                del st.session_state[f"{key}{idx}"]
        st.rerun()

# Dynamic DOD Indicator (calculates from session_state widgets directly)
current_total_dod = 0
for i in range(len(st.session_state.slot_list)):
    current_total_dod += st.session_state.get(f"dod_sel_{i}", st.session_state.slot_list[i]["dod"])

st.sidebar.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

if current_total_dod > max_dod_threshold:
    st.sidebar.markdown(f"<div class='status-badge-warn'>⚠️ DOD Ceiling Exceeded ({current_total_dod} / {max_dod_threshold})</div>", unsafe_allow_html=True)
else:
    st.sidebar.markdown(f"<div class='status-badge-ok'>✓ Target DOD: {current_total_dod} / {max_dod_threshold}</div>", unsafe_allow_html=True)

st.sidebar.markdown("<div style='margin: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.12);'></div>", unsafe_allow_html=True)

slot_configurations = []

# Loop creates robust widgets relying entirely on state keys (Fixes the reset bug)
for i in range(len(st.session_state.slot_list)):
    slot_data = st.session_state.slot_list[i]
    
    # Initialize default state for this slot if it doesn't exist yet
    if f"phase_sel_{i}" not in st.session_state:
        st.session_state[f"phase_sel_{i}"] = slot_data["phase"]
    if f"dod_sel_{i}" not in st.session_state:
        st.session_state[f"dod_sel_{i}"] = slot_data["dod"]
    if f"role_sel_{i}" not in st.session_state:
        st.session_state[f"role_sel_{i}"] = slot_data.get("role", "PF Focus")
    if f"type_sel_{i}" not in st.session_state:
        st.session_state[f"type_sel_{i}"] = slot_data.get("type", "Any")
    if f"ata_sel_{i}" not in st.session_state:
        st.session_state[f"ata_sel_{i}"] = slot_data.get("ata", 22)
    if f"mand_sel_{i}" not in st.session_state:
        st.session_state[f"mand_sel_{i}"] = slot_data.get("mandatory", False)

    st.sidebar.markdown(f"<div class='slot-container'><div class='slot-title'>SLOT #{i+1:02d}</div>", unsafe_allow_html=True)
    
    r1_c1, r1_c2 = st.sidebar.columns([2.6, 1.4])
    with r1_c1:
        p_val = st.selectbox(
            "Phase",
            options=ALL_PHASE_KEYS,
            format_func=lambda x: f"Ph {x}: {PHASE_NAMES[x].split('–')[1].strip()}",
            key=f"phase_sel_{i}",
            label_visibility="collapsed"
        )
    with r1_c2:
        d_val = st.selectbox(
            "DOD",
            options=[1, 2, 3],
            format_func=lambda x: f"DOD {x}",
            key=f"dod_sel_{i}",
            label_visibility="collapsed"
        )

    r2_c1, r2_c2 = st.sidebar.columns([1.8, 2.2])
    with r2_c1:
        role_val = st.selectbox(
            "Role",
            options=ROLE_OPTIONS,
            key=f"role_sel_{i}",
            label_visibility="collapsed"
        )
    with r2_c2:
        type_val = st.selectbox(
            "Category",
            options=["Any", "Technical Failure", "Non-Technical / CRM", "ATA Specific"],
            key=f"type_sel_{i}",
            label_visibility="collapsed"
        )

    ata_val = None
    if type_val == "ATA Specific":
        ata_val = st.sidebar.number_input("ATA Chapter", min_value=11, max_value=80, key=f"ata_sel_{i}")
    
    is_mandatory = st.sidebar.checkbox("Pin Exercise", key=f"mand_sel_{i}")
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # Sync back to our array for logic parsing
    slot_data["phase"] = p_val
    slot_data["dod"] = d_val
    slot_data["role"] = role_val
    slot_data["type"] = type_val
    slot_data["ata"] = ata_val
    slot_data["mandatory"] = is_mandatory
    
    slot_configurations.append({
        "slot": i + 1,
        "phase": int(p_val),
        "dod": int(d_val),
        "role": role_val,
        "type": type_val,
        "ata": ata_val,
        "mandatory": is_mandatory
    })

st.sidebar.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
st.sidebar.markdown("<div style='text-align: center; font-size: 11px; color: #94A3B8;'>Designed by Shawn Abela Ver v3.0 2026</div>", unsafe_allow_html=True)

# ==========================================
# OPTIMIZED DATA LOADING & CACHING
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# Anti-Repetition / History Logic
HISTORY_FILE = "session_history.json"
def get_recent_used_events():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                recent_events = set()
                for sess in history[-5:]:
                    for ev in sess.get("events", []):
                        recent_events.add(ev)
                return recent_events
        except Exception:
            return set()
    return set()

def save_session_to_history(df_session, mode, capt, fo):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            history = []
            
    history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode": mode,
        "crew": f"{capt} / {fo}",
        "events": df_session["EVENT"].tolist()
    })
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-20:], f, indent=2)

def derive_tem_tags(event_title, phase_num, w_spd, w_gust, rcam, vis):
    title_u = str(event_title).upper()
    threats = []
    errors = []

    if w_spd > 20 or w_gust > 25: threats.append("High Surface Wind / Gusts")
    if "1/1/1" in rcam or "2/2/2" in rcam or "3/3/3" in rcam: threats.append("Contaminated Runway / Poor Friction")
    if "CAT II" in vis or "CAT III" in vis or "75 m" in vis: threats.append("Low Visibility Operations (LVO)")

    if any(w in title_u for w in ["WIND", "TURB", "ICE", "SHEAR", "VIS", "FOG", "RAIN", "SNOW"]): threats.append("Adverse Weather / Windshear")
    if any(w in title_u for w in ["FAIL", "ELEC", "HYD", "ENG", "FIRE", "BLEED", "PRESS", "GEAR", "FLAP", "NAV"]): threats.append("Aircraft System Failure")
    if any(w in title_u for w in ["ATC", "HOLD", "REROUTE", "SLOT", "TAXI", "CONGEST"]): threats.append("ATC / Operational Pressure")
    if not threats: threats.append("Standard Operational Threat")

    if phase_num in [2, 6, 7]: errors.append("Flight Path Control")
    if "FAIL" in title_u or "PROC" in title_u: errors.append("SOP / QRH Execution")
    if not errors: errors.append("Communication & CRM")

    return " | ".join(threats), " | ".join(errors)

def get_best_match(scen_title, comp_titles):
    if not scen_title or pd.isna(scen_title): return None
    s_clean = re.sub(r'\(Ref:[^)]+\)', '', str(scen_title), flags=re.IGNORECASE)
    s_clean = re.sub(r'[^A-Z0-9\s]', ' ', s_clean.upper())
    s_clean = re.sub(r'\s+', ' ', s_clean).strip()
    
    if scen_title in comp_titles: return scen_title
    
    comp_map = {re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9\s]', ' ', str(c).upper())).strip(): c for c in comp_titles}
    if s_clean in comp_map: return comp_map[s_clean]
        
    s_words = set(s_clean.split())
    for c_clean, orig in comp_map.items():
        if len(s_words) > 1 and s_words.issubset(set(c_clean.split())): return orig

    f_match = difflib.get_close_matches(s_clean, list(comp_map.keys()), n=1, cutoff=0.55)
    return comp_map[f_match[0]] if f_match else None

@st.cache_data(show_spinner="Loading and caching matrix scenarios...")
def load_scenario_database(s_path, c_path):
    try:
        try:
            df_raw = pd.read_csv(s_path, encoding="cp1252")
        except Exception:
            df_raw = pd.read_csv(s_path, encoding="utf-8")

        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        while len(df_raw.columns) < 10: df_raw[f"Col_{len(df_raw.columns)}"] = None

        records = []
        phase_col_indices = list(range(2, 10))  # Columns C through J -> Phases 1 through 8
        
        for idx, row in df_raw.iterrows():
            event = row.iloc[0]
            dod = row.iloc[1]
            ata = row['ATA'] if 'ATA' in row and pd.notna(row['ATA']) else None
            
            if pd.isna(event) or pd.isna(dod): continue
            event_str = str(event).strip()
            if len(event_str) == 1 and event_str.isalpha(): continue
            
            for p_idx, col_idx in enumerate(phase_col_indices):
                if col_idx < len(row):
                    val = row.iloc[col_idx]
                    if pd.notna(val) and str(val).strip() != "":
                        records.append({
                            "EVENT": event_str,
                            "DOD": int(float(dod)),
                            "PHASES": p_idx + 1,
                            "ATA": int(float(ata)) if ata else None,
                            "DURATION": 15
                        })
                        
        df = pd.DataFrame(records)
        
        # Enforce exact integer types to avoid numpy UFuncNoLoopError
        df["DOD"] = pd.to_numeric(df["DOD"], errors='coerce').fillna(1).astype(int)
        df["PHASES"] = pd.to_numeric(df["PHASES"], errors='coerce').fillna(1).astype(int)

        for c_key in COMPETENCY_KEYS.keys():
            df[c_key] = 0.0

        comp_loaded = False
        if os.path.exists(c_path):
            try:
                df_comp = pd.read_excel(c_path)
                df_comp.columns = [str(c).strip() for c in df_comp.columns]
                event_col_name = df_comp.columns[0]
                comp_cols_present = [c for c in COMPETENCY_KEYS.keys() if c in df_comp.columns]
                
                if comp_cols_present:
                    comp_titles = df_comp[event_col_name].dropna().tolist()
                    df['Matched_Comp_Event'] = df['EVENT'].apply(lambda x: get_best_match(x, comp_titles))
                    
                    for idx, row in df.iterrows():
                        matched_title = row['Matched_Comp_Event']
                        if matched_title:
                            match_row = df_comp[df_comp[event_col_name] == matched_title]
                            if not match_row.empty:
                                for c_key in comp_cols_present:
                                    try:
                                        val = float(match_row.iloc[0][c_key])
                                        df.loc[idx, c_key] = val if pd.notna(val) else 0.0
                                    except (ValueError, TypeError): pass
                    comp_loaded = True
            except Exception: pass

        df["scenario_id"] = [f"SC-{i+1:02d}" for i in range(len(df))]
        return df, comp_loaded
    except Exception as e:
        return None, str(e)

def generate_pdf_briefing(df_session, total_dod, max_dod, comp_scores, mode, capt, fo, sim_id_val, ios_info):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=12, leading=14, textColor=colors.HexColor('#0284C7'), alignment=0)
    subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#555555'))
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=7.0, leading=9.0)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontSize=7.0, leading=9.0, fontName='Helvetica-Bold')

    elements = [
        Paragraph(f"A320 SIMULATOR BRIEFING & IOS SETUP SHEET — {mode.upper()}", title_style),
        Paragraph(f"<b>Crew:</b> {capt} (CPT) & {fo} (FO) &nbsp;&nbsp;|&nbsp;&nbsp; <b>Device:</b> {sim_id_val} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Total DOD:</b> {total_dod}/{max_dod}", subtitle_style),
        Paragraph(f"<b>IOS Setup Config:</b> <i>{ios_info}</i>", subtitle_style),
        Spacer(1, 3),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0284C7'), spaceAfter=5)
    ]

    table_data = [[
        Paragraph("<b>Slot</b>", cell_bold), Paragraph("<b>Phase</b>", cell_bold),
        Paragraph("<b>Role</b>", cell_bold), Paragraph("<b>Event / Scenario Title</b>", cell_bold), 
        Paragraph("<b>DOD</b>", cell_bold), Paragraph("<b>Threat & Error Focus</b>", cell_bold),
        Paragraph("<b>Flagged EBT</b>", cell_bold)
    ]]

    for _, row in df_session.iterrows():
        active_comps = [col for col in COMPETENCY_KEYS.keys() if col in row and pd.notna(row[col]) and float(row[col]) >= 1.0]
        comps_str = ", ".join(active_comps) if active_comps else "Standard"
        tem_str = f"T: {row.get('TEM_THREAT','Standard')}<br/>E: {row.get('TEM_ERROR','General')}"
        
        table_data.append([
            Paragraph(str(row["SLOT"]), cell_style), Paragraph(str(row["PHASE_NAME"]), cell_style),
            Paragraph(str(row.get("ROLE", "PF Focus")), cell_bold), Paragraph(str(row["EVENT"]), cell_style), 
            Paragraph(str(row["DOD"]), cell_style), Paragraph(tem_str, cell_style),
            Paragraph(comps_str, cell_style)
        ])

    t = Table(table_data, colWidths=[22, 90, 52, 175, 22, 120, 83])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F4F8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0284C7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2), ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
    ]))
    elements.extend([t, Spacer(1, 5)])

    if any(score > 0 for score in comp_scores.values()):
        elements.append(Paragraph("<b>EBT COMPETENCY INTENSITY SCORECARD:</b>", cell_bold))
        elements.append(Spacer(1, 2))
        
        comp_table_data = [[Paragraph("<b>Code</b>", cell_bold), Paragraph("<b>Competency Name</b>", cell_bold), Paragraph("<b>Score</b>", cell_bold)]]
        for code, score in sorted(comp_scores.items(), key=lambda item: item[1], reverse=True):
            if score > 0:
                comp_table_data.append([
                    Paragraph(code, cell_bold),
                    Paragraph(COMPETENCY_KEYS.get(code, code), cell_style),
                    Paragraph(str(int(score)), cell_bold)
                ])
            
        t_comp = Table(comp_table_data, colWidths=[40, 364, 60])
        t_comp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAEAEA')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#999999')),
            ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.extend([t_comp, Spacer(1, 5)])

    elements.append(Paragraph("<b>INSTRUCTOR NOTES & CREW EVALUATION RUBRIC:</b>", cell_bold))
    elements.append(Spacer(1, 2))
    notes_box = [
        [Paragraph("<b>Flight Phase / Event</b>", cell_bold), Paragraph("<b>Competency / TEM Focus</b>", cell_bold), Paragraph("<b>Grade / Signature</b>", cell_bold)],
        [Paragraph("Pre-Flight / Departure", cell_style), Paragraph("SOP Compliance, Briefings, Workload Mgmt", cell_style), Paragraph("", cell_style)],
        [Paragraph("In-Flight / Abnormal handling", cell_style), Paragraph("Systems Knowledge, ECAM/QRH, CRM", cell_style), Paragraph("", cell_style)],
        [Paragraph("Approach & Landing", cell_style), Paragraph("Flight Path Management, Go-Around Decision", cell_style), Paragraph("", cell_style)]
    ]
    t_notes = Table(notes_box, colWidths=[130, 264, 100])
    t_notes.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAEAEA')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#999999')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(t_notes)

    doc.build(elements)
    buffer.seek(0)
    return buffer

scenarios_path = resource_path("Scenarios.csv")
competency_path = resource_path("Keypams.xlsx")

if not os.path.exists(scenarios_path):
    st.error(f"❌ Could not find `Scenarios.csv` in path `{resource_path('')}`.")
else:
    df, comp_loaded = load_scenario_database(scenarios_path, competency_path)

    if df is None:
        st.error(f"❌ Error reading matrix file: {comp_loaded}")
    else:
        # Generate TEM variables dynamically after loading data based on UI weather selections
        df["TEM_THREAT"], df["TEM_ERROR"] = zip(*df.apply(lambda r: derive_tem_tags(r["EVENT"], r["PHASES"], wind_spd, wind_gust, rcam_code, vis_rvr_str), axis=1))

        st.success(f"✓ Matrix Loaded. {'(Keypams Competency Matrix Active)' if comp_loaded else ''}")

        # Sorted Internal Matrix View
        with st.expander("📋 View Parsed Internal Scenario Matrix (Sorted by Phase)", expanded=False):
            active_comp_cols = [k for k in COMPETENCY_KEYS.keys() if k in df.columns]
            disp_cols = ["scenario_id", "PHASES", "DOD", "EVENT", "TEM_THREAT", "TEM_ERROR"] + active_comp_cols
            
            matrix_display_df = (
                df[disp_cols]
                .sort_values(by=["PHASES", "DOD", "EVENT"], ascending=[True, True, True])
                .reset_index(drop=True)
            )
            for col in active_comp_cols:
                matrix_display_df[col] = matrix_display_df[col].astype(int)

            st.dataframe(
                matrix_display_df,
                use_container_width=True,
                column_config={
                    "scenario_id": st.column_config.TextColumn("ID", width="small"),
                    "PHASES": st.column_config.NumberColumn("Phase", format="Phase %d"),
                    "DOD": st.column_config.NumberColumn("DOD", format="DOD %d"),
                    "EVENT": st.column_config.TextColumn("Scenario / Event Title", width="large"),
                    "TEM_THREAT": st.column_config.TextColumn("Threat Focus", width="medium"),
                    "TEM_ERROR": st.column_config.TextColumn("Error Focus", width="medium"),
                },
                hide_index=True
            )

        # Reverse Competency Finder
        with st.expander("🎯 Reverse Competency-Driven Scenario Finder & Injector", expanded=False):
            c_f1, c_f2 = st.columns([2.2, 1])
            with c_f1:
                target_comp = st.selectbox(
                    "Target EBT Competency Focus:",
                    options=list(COMPETENCY_KEYS.keys()),
                    format_func=lambda k: f"{k} – {COMPETENCY_KEYS[k]}"
                )
            with c_f2:
                min_comp_score = st.slider("Min Intensity", min_value=1.0, max_value=3.0, value=1.0, step=0.5)

            comp_candidates = df[df[target_comp] >= min_comp_score].copy()

            if comp_candidates.empty:
                st.warning(f"No scenarios found targeting **{target_comp}** >= {min_comp_score}.")
            else:
                chosen_comp_scen_id = st.selectbox(
                    f"Matching Scenarios ({len(comp_candidates)} found):",
                    options=comp_candidates["scenario_id"].tolist(),
                    format_func=lambda sid: f"[{target_comp} Score: {comp_candidates[comp_candidates['scenario_id'] == sid].iloc[0][target_comp]}] Phase {comp_candidates[comp_candidates['scenario_id'] == sid].iloc[0]['PHASES']} | DOD {comp_candidates[comp_candidates['scenario_id'] == sid].iloc[0]['DOD']} – {comp_candidates[comp_candidates['scenario_id'] == sid].iloc[0]['EVENT']}"
                )

                if "final_df" in st.session_state:
                    c_inj1, c_inj2 = st.columns([2, 1])
                    with c_inj1:
                        target_slot_to_replace = st.selectbox(
                            "Inject into Slot:",
                            options=range(len(st.session_state.final_df)),
                            format_func=lambda i: f"Slot #{st.session_state.final_df.loc[i, 'SLOT']} – Current: {st.session_state.final_df.loc[i, 'EVENT'][:25]}..."
                        )
                    with c_inj2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        if st.button("🚀 Inject into Slot", type="primary"):
                            picked_row = comp_candidates[comp_candidates["scenario_id"] == chosen_comp_scen_id].iloc[0].to_dict()
                            slot_num_val = int(st.session_state.final_df.loc[target_slot_to_replace, "SLOT"])
                            
                            st.session_state.final_df.loc[target_slot_to_replace, "EVENT"] = picked_row["EVENT"]
                            st.session_state.final_df.loc[target_slot_to_replace, "DOD"] = picked_row["DOD"]
                            st.session_state.final_df.loc[target_slot_to_replace, "PHASES"] = picked_row["PHASES"]
                            st.session_state.final_df.loc[target_slot_to_replace, "PHASE_NAME"] = PHASE_NAMES[picked_row["PHASES"]]
                            st.session_state.final_df.loc[target_slot_to_replace, "TEM_THREAT"] = picked_row["TEM_THREAT"]
                            st.session_state.final_df.loc[target_slot_to_replace, "TEM_ERROR"] = picked_row["TEM_ERROR"]
                            st.session_state.final_df.loc[target_slot_to_replace, "MATCH_TYPE"] = f"Competency ({target_comp})"
                            
                            for c_k in COMPETENCY_KEYS.keys():
                                if c_k in picked_row:
                                    st.session_state.final_df.loc[target_slot_to_replace, c_k] = picked_row[c_k]
                            
                            st.success(f"✓ Slot #{slot_num_val} updated!")
                            st.rerun()

        # Generation Action
        if st.button("⚡ Generate Simulator Profile", type="primary"):
            selected_events = []
            used_event_titles = set()
            missing_slots = []
            fallback_warnings = []
            recent_used_set = get_recent_used_events()

            for cfg in slot_configurations:
                slot_num = cfg["slot"]
                target_p = int(cfg["phase"])
                target_d = int(cfg["dod"])
                target_role = cfg["role"]
                target_type = cfg["type"]
                target_ata = cfg["ata"]

                candidates = df[
                    (df["PHASES"] == target_p) & 
                    (df["DOD"] == target_d) & 
                    (~df["EVENT"].isin(used_event_titles))
                ].copy()

                if target_type == "Technical Failure":
                    candidates = candidates[candidates["ATA"].notna()]
                elif target_type == "Non-Technical / CRM":
                    candidates = candidates[candidates["ATA"].isna()]
                elif target_type == "ATA Specific" and target_ata:
                    candidates = candidates[candidates["ATA"] == float(target_ata)]

                # Anti-repetition logic check
                fresh_candidates = candidates[~candidates["EVENT"].isin(recent_used_set)]
                if not fresh_candidates.empty:
                    candidates = fresh_candidates

                if not candidates.empty:
                    picked = candidates.sample(n=1).iloc[0].to_dict()
                    picked["SLOT"] = slot_num
                    picked["ROLE"] = target_role
                    picked["PHASE_NAME"] = PHASE_NAMES[target_p]
                    picked["MATCH_TYPE"] = "Exact"
                    selected_events.append(picked)
                    used_event_titles.add(picked["EVENT"])
                
                elif allow_fallback:
                    phase_candidates = df[
                        (df["PHASES"] == target_p) & 
                        (~df["EVENT"].isin(used_event_titles))
                    ].copy()

                    if not phase_candidates.empty:
                        phase_candidates["dod_diff"] = (phase_candidates["DOD"] - target_d).abs()
                        picked = phase_candidates.sort_values("dod_diff").iloc[0].to_dict()
                        
                        picked["SLOT"] = slot_num
                        picked["ROLE"] = target_role
                        picked["PHASE_NAME"] = PHASE_NAMES[target_p]
                        picked["MATCH_TYPE"] = f"Fallback (DOD {picked['DOD']})"
                        selected_events.append(picked)
                        used_event_titles.add(picked["EVENT"])

                        fallback_warnings.append(
                            f"Slot #{slot_num} (Phase {target_p}): Target DOD {target_d} missing → substituted DOD {picked['DOD']} ('{picked['EVENT']}')"
                        )
                    else:
                        missing_slots.append(f"Slot #{slot_num}: No events exist in Phase {target_p}")
                else:
                    missing_slots.append(f"Slot #{slot_num}: Phase {target_p} with DOD {target_d}")

            if missing_slots:
                st.error(f"Could not fulfill profile! Issues found in: {', '.join(missing_slots)}.")
            else:
                st.session_state.final_df = pd.DataFrame(selected_events).sort_values("SLOT").reset_index(drop=True)
                save_session_to_history(st.session_state.final_df, session_mode, capt_name, fo_name)
                
                if fallback_warnings:
                    for warn in fallback_warnings:
                        st.warning(f"ℹ️ {warn}")
                st.success("Session Profile Generated Successfully!")

        # Output Results View
        if "final_df" in st.session_state:
            final_df = st.session_state.final_df
            total_dod = final_df["DOD"].sum()
            total_time = final_df["DURATION"].sum()

            if total_dod > max_dod_threshold:
                st.warning(f"⚠️ Generated Total DOD ({total_dod}) exceeds Session Ceiling ({max_dod_threshold}).")

            # Compact Fine-Tune Section
            with st.container(border=True):
                st.markdown("#### 🔧 Fine-Tune Session / Override Slots")
                
                ft_col1, ft_col2, ft_col3 = st.columns([1, 1, 1.8])
                with ft_col1:
                    override_slot_idx = st.selectbox(
                        "Select Slot to Modify:",
                        options=range(len(final_df)),
                        format_func=lambda i: f"Slot #{final_df.loc[i, 'SLOT']} – Phase {final_df.loc[i, 'PHASES']} | {final_df.loc[i, 'EVENT'][:18]}..."
                    )
                
                curr_row = final_df.loc[override_slot_idx]
                slot_num_to_modify = int(curr_row["SLOT"])
                curr_phase = int(curr_row["PHASES"])

                with ft_col2:
                    new_role_val = st.selectbox(
                        "Update Role Focus:",
                        options=ROLE_OPTIONS,
                        index=ROLE_OPTIONS.index(curr_row.get("ROLE", "PF Focus"))
                    )

                phase_filtered_df = df[df["PHASES"] == curr_phase].drop_duplicates(subset=["EVENT"]).reset_index(drop=True)

                with ft_col3:
                    if phase_filtered_df.empty:
                        st.warning(f"⚠️ No scenarios found for Phase {curr_phase}.")
                    else:
                        new_event_title = st.selectbox(
                            f"Choose Replacement Event (Phase {curr_phase}):",
                            options=phase_filtered_df["EVENT"].tolist(),
                            format_func=lambda ev_title: f"[DOD {phase_filtered_df[phase_filtered_df['EVENT'] == ev_title].iloc[0]['DOD']}] {ev_title}"
                        )
                
                if not phase_filtered_df.empty:
                    if st.button("🔄 Apply Event & Role Update to Slot", type="primary"):
                        match_row = phase_filtered_df[phase_filtered_df["EVENT"] == new_event_title].iloc[0].to_dict()

                        final_df.loc[override_slot_idx, "EVENT"] = match_row["EVENT"]
                        final_df.loc[override_slot_idx, "DOD"] = match_row["DOD"]
                        final_df.loc[override_slot_idx, "ROLE"] = new_role_val
                        final_df.loc[override_slot_idx, "PHASES"] = match_row["PHASES"]
                        final_df.loc[override_slot_idx, "PHASE_NAME"] = PHASE_NAMES[curr_phase]
                        final_df.loc[override_slot_idx, "TEM_THREAT"] = match_row["TEM_THREAT"]
                        final_df.loc[override_slot_idx, "TEM_ERROR"] = match_row["TEM_ERROR"]
                        final_df.loc[override_slot_idx, "MATCH_TYPE"] = "Phase-Filtered Override"
                        
                        for c_key in COMPETENCY_KEYS.keys():
                            if c_key in match_row:
                                final_df.loc[override_slot_idx, c_key] = match_row[c_key]

                        st.session_state.final_df = final_df
                        st.success(f"✓ Slot #{slot_num_to_modify} updated!")
                        st.rerun()

            st.markdown("---")
            # Metrics Row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Selected Events", len(final_df))
            m2.metric("Total DOD Score", f"{total_dod} / {max_dod_threshold}")
            m3.metric("Est. Session Time", f"{total_time} mins")
            m4.metric("DOD Buffer Remaining", max_dod_threshold - total_dod)

            # Competency Intensity Scorecard
            comp_scores = {k: 0.0 for k in COMPETENCY_KEYS.keys()}
            for comp_key in COMPETENCY_KEYS.keys():
                if comp_key in final_df.columns:
                    comp_scores[comp_key] = float(pd.to_numeric(final_df[comp_key], errors='coerce').fillna(0).sum())

            if any(score > 0 for score in comp_scores.values()):
                with st.container(border=True):
                    st.markdown("#### 📊 EBT Competency Intensity Scorecard")
                    chart_col1, chart_col2 = st.columns([1.6, 1.4])
                    with chart_col1:
                        chart_df = pd.DataFrame(list(comp_scores.items()), columns=["Competency", "Score"]).set_index("Competency")
                        st.bar_chart(chart_df, height=200, use_container_width=True)

            st.markdown("#### ✈️ Sequenced Simulator Session")
            st.dataframe(
                final_df[["SLOT", "PHASE_NAME", "ROLE", "EVENT", "DOD", "TEM_THREAT", "TEM_ERROR", "MATCH_TYPE"]],
                use_container_width=True
            )

            # Triple Export Options
            col_exp1, col_exp2, col_exp3 = st.columns(3)
            with col_exp1:
                csv_export = final_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Session Schedule (CSV)",
                    data=csv_export,
                    file_name=f"sim_session_DOD_{max_dod_threshold}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
            with col_exp2:
                pdf_data = generate_pdf_briefing(final_df, total_dod, max_dod_threshold, comp_scores, session_mode, capt_name, fo_name, sim_id, ios_summary_str)
                st.download_button(
                    label="📄 Download Printable PDF Briefing",
                    data=pdf_data,
                    file_name=f"sim_briefing_DOD_{max_dod_threshold}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            with col_exp3:
                lms_payload = {
                    "airline": "KM Malta",
                    "device": sim_id,
                    "mode": session_mode,
                    "crew": {"captain": capt_name, "first_officer": fo_name},
                    "environment": ios_summary_str,
                    "total_dod": int(total_dod),
                    "competency_scores": comp_scores,
                    "schedule": final_df[["SLOT", "PHASES", "ROLE", "EVENT", "DOD", "TEM_THREAT", "TEM_ERROR"]].to_dict(orient="records")
                }
                st.download_button(
                    label="🌐 Export LMS Payload (MINT / JSON)",
                    data=json.dumps(lms_payload, indent=2),
                    file_name=f"lms_payload_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    use_container_width=True
                )
