import streamlit as st
import pandas as pd
import io
import re
import os
import sys
import difflib
import urllib.request

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

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
    
    h1, h2, h3, h4 { color: #0284C7 !important; font-weight: 700 !important; margin-top: 6px !important; margin-bottom: 6px !important;}
    
    div[data-baseweb="tab-list"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 4px !important;
        overflow-x: visible !important;
    }
    div[data-baseweb="tab"] {
        white-space: normal !important;
        height: auto !important;
        min-height: 38px !important;
        padding: 6px 12px !important;
    }

    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stMetricLabel"] * {
        color: var(--text-color) !important;
        opacity: 0.8 !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] * {
        color: var(--text-color) !important;
        font-weight: 700 !important;
    }

    .ios-card {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .ios-label {
        font-size: 11px;
        color: var(--text-color);
        opacity: 0.7;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }

    .jepp-card {
        background-color: var(--secondary-background-color);
        border: 2px solid #0284C7;
        border-radius: 6px;
        padding: 14px;
        font-family: monospace;
        color: var(--text-color);
        margin-top: 10px;
        margin-bottom: 12px;
    }
    .jepp-header {
        font-size: 14px;
        font-weight: 700;
        color: #0284C7;
        border-bottom: 1px dashed rgba(128, 128, 128, 0.4);
        padding-bottom: 4px;
        margin-bottom: 8px;
    }

    section[data-testid="stSidebar"] {
        min-width: 310px !important; 
        max-width: 310px !important;
    }
    
    section[data-testid="stSidebar"] div[data-baseweb="select"] * {
        font-size: 11.5px !important;
    }
    
    .sidebar-header {
        font-size: 13px;
        font-weight: 700;
        color: #0284C7;
        letter-spacing: 0.04em;
        margin-bottom: 6px;
    }
    .status-badge-ok {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-align: center;
    }
    .status-badge-warn {
        background-color: rgba(245, 158, 11, 0.15);
        color: #F59E0B;
        border: 1px solid rgba(245, 158, 11, 0.3);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-align: center;
    }

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
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    }
    .ref-badge {
        font-size: 10.5px;
        background-color: rgba(2, 132, 199, 0.15);
        color: #0284C7;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 6px;
        font-weight: 600;
        border: 1px solid rgba(2, 132, 199, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.title("✈️ Simulator Session Plan & EBT Competency Optimizer")
st.markdown("<p style='color: var(--text-color); opacity: 0.7; font-size: 14px; margin-top: -8px; font-weight: 500;'>KM Malta A320 STD2.2 / Advanced Evidence-Based Training (EBT) & CBTA / OPC / LPC IRR Suite</p>", unsafe_allow_html=True)

# ==========================================
# CENTRALIZED DATA DICTIONARIES & PROGRAM MODULES
# ==========================================

DOCUMENT_REFERENCES = {
    "EASA_EBT": "EASA ED Decision 2021/002/R (Evidence-Based Training)",
    "FCOM_PRO": "Airbus A320 Flight Crew Operating Manual - Standard Procedures",
    "FCTM_ABN": "Airbus A320 Flight Crew Training Manual - Abnormal Operations",
    "QRH": "Airbus A320 Quick Reference Handbook",
    "ICAO_9995": "ICAO Doc 9995 - Manual of Evidence-based Training",
    "OM_A": "Airline Operations Manual Part A (General/Basic)",
    "OM_B": "Airline Operations Manual Part B (A320)"
}

PROGRAM_SYLLABUS_EXERCISES = {
    "EX-01_EFATO": {
        "title": "Exercise 01: Engine Failure After Take-Off (EFATO) / V1 Cut",
        "keywords": ["EFATO", "V1 CUT", "ENGINE FAILURE", "V1"],
        "phase": 2,
        "stressor": "Critical Engine 1 failure at V1 + 2 kt leading to asymmetric thrust and single-engine climb profile.",
        "cbta_focus": ["FPM", "APK", "PSD", "SAW"],
        "sequence": [
            {
                "phase_name": "Phase 1: Flight Path Stabilization (Take-off & Initial Climb)",
                "pta": "Maintain directional control with rudder and establish single-engine climb pitch attitude.",
                "obs": [
                    {"text": "OB FPM 3.1: Immediate rudder input to counter asymmetric yaw; roll kept within ±5°; SRS pitch target (~12.5°) achieved.", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB FPM 3.2: PM actively calls out FMA changes and monitors V2 trend.", "ref": "FCOM_PRO", "comp": "FPM"},
                    {"text": "OB FPM 3.3: Smoothly references Beta Target (blue trapezoid on PFD) to optimize sideslip.", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB SAW 6.2: Maintains awareness of Engine-Out SID (EO SID) and terrain clearance profile.", "ref": "OM_B", "comp": "SAW"}
                ]
            },
            {
                "phase_name": "Phase 2: Core Systems Management (ECAM Execution)",
                "pta": "Manage thrust levers symmetrically before calling memory items; execute ECAM actions systematically above 400 ft AGL.",
                "obs": [
                    {"text": "OB APK 1.4: Strict ECAM discipline loop. PM reads line, touches switch, asks confirmation before actuation.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB APK 1.2: Adheres to approved procedures; allows ECAM to guide chronologically without premature fire pushbutton actuation.", "ref": "FCOM_PRO", "comp": "APK"},
                    {"text": "OB COM 2.4: Clear closed-loop verification callouts before moving primary switches.", "ref": "EASA_EBT", "comp": "COM"},
                    {"text": "OB WLM 8.1: PF isolates attention strictly to primary flight parameters while delegating ECAM management to PM.", "ref": "OM_A", "comp": "WLM"}
                ]
            },
            {
                "phase_name": "Phase 3: Strategic Assessment & Diversion Planning",
                "pta": "Evaluate diversion options utilizing structured risk mitigation (FORDEC/DODAR), secure aircraft systems, and coordinate with ATC/Cabin.",
                "obs": [
                    {"text": "OB PSD 5.1: Identifies secondary threats caused by failure (reduced electrical/hydraulic redundancies).", "ref": "ICAO_9995", "comp": "PSD"},
                    {"text": "OB PSD 5.3: Implements formal decision matrix (FORDEC/DODAR): weighs returning vs. diverting.", "ref": "OM_A", "comp": "PSD"},
                    {"text": "OB SAW 6.1: Actively monitors remaining fuel flow and single-engine performance calculations.", "ref": "EASA_EBT", "comp": "SAW"},
                    {"text": "OB COM 2.5: Delivers structured MAYDAY declaration to ATC and NITS briefing to cabin crew.", "ref": "OM_A", "comp": "COM"}
                ]
            },
            {
                "phase_name": "Phase 4: Approach and Landing (Single Engine Terminal Environment)",
                "pta": "Prepare for single-engine approach, program FMGS performance pages, and manage CRM authority gradients.",
                "obs": [
                    {"text": "OB FPA 4.1: Programs FMGS correctly for diversion airport and activates single-engine performance pages.", "ref": "FCTM_ABN", "comp": "FPA"},
                    {"text": "OB LTW 7.1: Captain actively seeks First Officer input during single-engine landing briefing.", "ref": "OM_A", "comp": "LTW"},
                    {"text": "OB APK 1.1: PM accurately references QRH Single-Engine Landing Performance Tables for flap/landing distance adjustments.", "ref": "QRH", "comp": "APK"}
                ]
            }
        ]
    },
    "EX-02_ENG_FIRE": {
        "title": "Exercise 02: Engine Fire & Severe Mechanical Damage in Flight",
        "keywords": ["FIRE", "DAMAGE", "ENGINE FIRE"],
        "phase": 3,
        "stressor": "Engine 2 Fire warning during climb phase with high vibration indications.",
        "cbta_focus": ["APK", "COM", "WLM", "PSD"],
        "sequence": [
            {
                "phase_name": "Phase 1: Fault Identification & Flight Path Control",
                "pta": "Maintain flight path stability and announce malfunction clearly before initiating ECAM.",
                "obs": [
                    {"text": "OB SAW 6.1: Rapidly identifies fire warning and cross-checks engine parameters.", "ref": "FCOM_PRO", "comp": "SAW"},
                    {"text": "OB FPA 4.2: Maintains autopilot/flight director guidance during initial malfunction callout.", "ref": "FCTM_ABN", "comp": "FPA"}
                ]
            },
            {
                "phase_name": "Phase 2: ECAM Fire Checklist & Extinguishing Agent Discharge",
                "pta": "Perform confirm procedure for Engine Master and Engine Fire Pushbutton before discharge.",
                "obs": [
                    {"text": "OB APK 1.4: Strict execution of confirm procedure for Engine Master 2 and AGENT 1/2 buttons.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB COM 2.4: Clear closed-loop response between PF and PM during critical switch guarding.", "ref": "EASA_EBT", "comp": "COM"},
                    {"text": "OB WLM 8.3: Avoids task saturation and maintains steady monitoring of aircraft altitude.", "ref": "ICAO_9995", "comp": "WLM"}
                ]
            },
            {
                "phase_name": "Phase 3: Overweight / Immediate Land Decision",
                "pta": "Assess aircraft landing weight versus max structural landing weight and evaluate fuel jettison/overweight landing procedures.",
                "obs": [
                    {"text": "OB PSD 5.4: Makes timely decision regarding immediate return vs. holding for overweight landing checklist.", "ref": "OM_A", "comp": "PSD"},
                    {"text": "OB APK 1.1: References Overweight Landing Checklist in QRH when applicable.", "ref": "QRH", "comp": "APK"}
                ]
            }
        ]
    },
    "EX-03_DUAL_GEN": {
        "title": "Exercise 03: Dual Generator Failure / Emergency Electrical Configuration",
        "keywords": ["DUAL GEN", "ELECTRICAL", "EMER ELEC", "RAT"],
        "phase": 3,
        "stressor": "Total loss of main AC buses (Generators 1 & 2 failed), triggering automatic RAT extension and emergency bus reversion.",
        "cbta_focus": ["APK", "SAW", "FPA", "COM"],
        "sequence": [
            {
                "phase_name": "Phase 1: Emergency Reversion & RAT Deployment Verification",
                "pta": "Verify RAT extension and emergency generator coupling while maintaining flight parameters on standby instruments.",
                "obs": [
                    {"text": "OB SAW 6.1: Rapidly recognizes loss of primary display units and confirms RAT deployment.", "ref": "FCOM_PRO", "comp": "SAW"},
                    {"text": "OB FPM 3.1: Stabilizes pitch and roll manually during display power transition.", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB APK 1.2: Executes Emergency Electrical Configuration procedures without delay.", "ref": "QRH", "comp": "APK"}
                ]
            },
            {
                "phase_name": "Phase 2: Communication & Systems Management",
                "pta": "Restore communication using RMP 1 on VHF 1 and manage load shedding.",
                "obs": [
                    {"text": "OB COM 2.1: Establishes VHF 1 emergency communications using audio control panel 1.", "ref": "OM_A", "comp": "COM"},
                    {"text": "OB WLM 8.1: Systematically delegates QRH management while maintaining raw-data navigation tracking.", "ref": "ICAO_9995", "comp": "WLM"}
                ]
            },
            {
                "phase_name": "Phase 3: Emergency Descent & Landing Setup",
                "pta": "Plan visual or ILS CAT I approach with gravity gear extension procedures.",
                "obs": [
                    {"text": "OB APK 1.4: Strict execution of Gravity Gear Extension memory items at specified speed limits.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB PSD 5.3: Evaluates weather limits for non-availability of CAT II/III capability.", "ref": "OM_B", "comp": "PSD"}
                ]
            }
        ]
    },
    "EX-04_SE_ILS": {
        "title": "Exercise 04: Single Engine ILS Precision Approach & Missed Approach Profile",
        "keywords": ["ILS", "APPROACH", "SINGLE ENGINE ILS", "MISSED APPROACH"],
        "phase": 6,
        "stressor": "Single-engine precision ILS approach in low visibility conditions (CAT I) with crosswind and option for go-around.",
        "cbta_focus": ["FPM", "FPA", "LTW", "SAW"],
        "sequence": [
            {
                "phase_name": "Phase 1: Arrival & Descent Preparation",
                "pta": "Conduct single-engine approach briefing, review VAPP increments, and set FCU target speeds.",
                "obs": [
                    {"text": "OB LTW 7.1: Captain actively encourages First Officer input during single-engine approach briefing.", "ref": "OM_A", "comp": "LTW"},
                    {"text": "OB FPA 4.4: Correctly programs FMGS landing parameters and verifies ILS frequency/ident.", "ref": "FCOM_PRO", "comp": "FPA"}
                ]
            },
            {
                "phase_name": "Phase 2: Final Approach Intercept & Stabilization",
                "pta": "Intercept Localizer and Glide Slope in Flap 3 configuration with single-engine thrust management.",
                "obs": [
                    {"text": "OB FPM 3.1: Smooth application of rudder trim and manual thrust control (if autothrust OFF).", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB SAW 6.3: Proactive monitoring of energy state, sink rate, and wind corrections down to DA.", "ref": "FCOM_PRO", "comp": "SAW"}
                ]
            },
            {
                "phase_name": "Phase 3: Flare & Touchdown / Go-Around Execution",
                "pta": "Execute single-engine landing alignment or decisive single-engine go-around callout (TOGA / Flaps).",
                "obs": [
                    {"text": "OB FPM 3.1: Decisive rudder control during flare to align nose wheel with runway centerline.", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB COM 2.4: Clear 'TOGA SRS' and 'Flaps One Step' callouts if go-around is initiated.", "ref": "FCOM_PRO", "comp": "COM"}
                ]
            }
        ]
    },
    "EX-05_WINDSHEAR": {
        "title": "Exercise 05: Windshear / Severe Microburst Escape Maneuver",
        "keywords": ["WINDSHEAR", "TURBULENCE", "GUST", "ESCAPE"],
        "phase": 2,
        "stressor": "Predictive or Reactive Windshear warning during takeoff roll or initial climb phase.",
        "cbta_focus": ["FPM", "SAW", "APK", "PSD"],
        "sequence": [
            {
                "phase_name": "Phase 1: Windshear Recognition & Immediate Action",
                "pta": "Recognize windshear warning or rapid air-speed drop and set TOGA thrust immediately.",
                "obs": [
                    {"text": "OB SAW 6.4: Rapidly recognizes reactive windshear synthetic voice warning ('WINDSHEAR').", "ref": "FCTM_ABN", "comp": "SAW"},
                    {"text": "OB FPM 3.1: Decisive application of TOGA thrust and pitch tracking to SRS/full stick pitch limit without overcontrolling.", "ref": "QRH", "comp": "FPM"}
                ]
            },
            {
                "phase_name": "Phase 2: Flight Path Recovery & Configuration Retention",
                "pta": "Maintain configuration (gear/flaps unchanged) until clear of windshear condition.",
                "obs": [
                    {"text": "OB APK 1.4: Refrains from changing gear or flap settings while in shear conditions.", "ref": "FCOM_PRO", "comp": "APK"},
                    {"text": "OB COM 2.1: Calls out terrain/altitude trend and reports windshear escape maneuver to ATC once clear.", "ref": "OM_A", "comp": "COM"}
                ]
            }
        ]
    },
    "EX-06_EMER_DESCENT": {
        "title": "Exercise 06: Rapid Cabin Depressurization & Emergency Descent Profile",
        "keywords": ["DEPRESSURIZATION", "EMERGENCY DESCENT", "OXYGEN", "DESCENT"],
        "phase": 4,
        "stressor": "Loss of cabin pressure at FL370 requiring oxygen mask donning and rapid descent to FL100/MORA.",
        "cbta_focus": ["APK", "COM", "FPA", "WLM"],
        "sequence": [
            {
                "phase_name": "Phase 1: Immediate Survival Memory Items",
                "pta": "Don crew oxygen masks (100%), establish flight deck intercom, and turn on seat belt signs.",
                "obs": [
                    {"text": "OB APK 1.4: Rapid donning of oxygen masks within 5 seconds and setting regulators to 100%.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB COM 2.1: Establishes clear intra-cockpit interphone communication with mask microphones ON.", "ref": "FCOM_PRO", "comp": "COM"}
                ]
            },
            {
                "phase_name": "Phase 2: Emergency Descent Execution",
                "pta": "Turn off airways, select target altitude (FL100/MORA), pull ALT, pull HDG, pull SPD, and extend Speedbrakes.",
                "obs": [
                    {"text": "OB FPA 4.4: Rapid manipulation of FCU controls to establish maximum rate descent.", "ref": "FCTM_ABN", "comp": "FPA"},
                    {"text": "OB WLM 8.3: Smoothly deploys Speedbrakes to full without exceeding structural VMO/MMO limits.", "ref": "ICAO_9995", "comp": "WLM"}
                ]
            },
            {
                "phase_name": "Phase 3: ATC Mayday & Passenger Safety Management",
                "pta": "Broadcast MAYDAY, notify cabin crew, and monitor high terrain altitude clearances.",
                "obs": [
                    {"text": "OB COM 2.5: Transmits MAYDAY call specifying emergency descent and target level.", "ref": "OM_A", "comp": "COM"},
                    {"text": "OB SAW 6.2: Verifies MORA/MSA on navigation display to prevent CFIT during descent.", "ref": "OM_B", "comp": "SAW"}
                ]
            }
        ]
    }
}

PHASE_NAMES = {
    1: "Phase 1 – Pre-flight and Taxi", 2: "Phase 2 – Take-off", 3: "Phase 3 – Climb",
    4: "Phase 4 – Cruise", 5: "Phase 5 – Descent", 6: "Phase 6 – Approach",
    7: "Phase 7 – Landing", 8: "Phase 8 – Taxi and post-flight"
}

ALL_PHASE_KEYS = [1, 2, 3, 4, 5, 6, 7, 8]
ROLE_OPTIONS = ["PF Focus", "PM Focus", "Both / CRM", "Instructor Choice"]

EUROPEAN_AIRPORTS = {
    "LMML (Malta Luqa)": {"icao": "LMML", "elev": 293, "rwy": ["13", "31"], "ils": "110.50 (13)"},
    "LFPG (Paris Charles de Gaulle)": {"icao": "LFPG", "elev": 392, "rwy": ["08R/26L", "08L/26R", "09R/27L", "09L/27R"], "ils": "109.50 (26L)"},
    "EGLL (London Heathrow)": {"icao": "EGLL", "elev": 83, "rwy": ["09L/27R", "09R/27L"], "ils": "110.30 (27R)"},
    "EDDF (Frankfurt)": {"icao": "EDDF", "elev": 364, "rwy": ["07C/25C", "07R/25L", "18", "07L/25R"], "ils": "111.15 (25C)"},
    "EHAM (Amsterdam Schiphol)": {"icao": "EHAM", "elev": -11, "rwy": ["06/24", "09/27", "18C/36C", "18L/36R", "18R/36L"], "ils": "108.50 (24)"}
}

COMPETENCY_KEYS = {
    "APK": "Application of Procedures",
    "COM": "Communication",
    "FPM": "Flight Path Management – Manual",
    "FPA": "Flight Path Management – Automation",
    "KNO": "Knowledge",
    "LTW": "Leadership & Teamwork",
    "PSD": "Problem Solving & Decision Making",
    "SAW": "Situational Awareness",
    "WLM": "Workload Management",
}

GRADE_DESCRIPTORS = {
    5: "Highly effective performance. No errors observed; deviations, if any, were trivial and self-detected before any effect on the flight path or safety margins.",
    4: "Effective performance. Minor errors occurred but were self-identified and self-corrected without any need for intervention or coaching.",
    3: "Effective performance overall — meets the operational standard. Any errors present had no safety-relevant effect and did not require instructor intervention.",
    2: "Marginally effective performance. Errors required instructor intervention or coaching to mitigate; performance is below standard and needs focused follow-up.",
    1: "Ineffective / unsafe performance. Immediate intervention was required to maintain safety margins; represents an unacceptable standard of performance.",
}

STANDARD_PHRASE_BANK = {
    5: [
        "No errors observed; execution exceeded the published standard throughout.",
        "Handled proactively with clear anticipation of downstream consequences.",
        "Exemplary crew coordination and workload distribution under pressure.",
    ],
    4: [
        "Minor deviation(s) noted; self-identified and corrected without prompting.",
        "Solid adherence to SOPs with only trivial timing/sequencing imperfections.",
        "Effective performance; a small refinement would bring this to exemplary.",
    ],
    3: [
        "Met the operational standard; no safety-relevant errors observed.",
        "Standard, competent handling consistent with line operations.",
        "Acceptable performance; no intervention required at any point.",
    ],
    2: [
        "Required instructor prompt/intervention to bring performance back to standard.",
        "Below standard; errors were safety-relevant but were mitigated in time.",
        "Task saturation observed; workload management needs focused follow-up.",
    ],
    1: [
        "Immediate instructor intervention required to maintain safety margins.",
        "Unsafe practice observed; this item must be re-briefed and re-flown.",
        "Standard not met; formal remedial training is recommended.",
    ],
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def fetch_live_metar(icao_code):
    try:
        url = f"https://aviationweather.gov/api/data/metar?ids={icao_code}&format=raw"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            metar = response.read().decode('utf-8').strip()
            return metar if metar else "No live METAR data returned."
    except Exception:
        return "METAR connection unavailable (offline mode)."

def derive_tem_tags(event_title, phase_num, w_spd, w_gust, rcam, vis):
    threats, errors = [], []
    if w_spd > 20 or w_gust > 25: threats.append("High Surface Wind / Gusts")
    if "1/1/1" in rcam or "2/2/2" in rcam: threats.append("Contaminated Runway")
    if not threats: threats.append("Standard Operational Threat")
    if phase_num in [2, 6, 7]: errors.append("Flight Path Control")
    else: errors.append("SOP / QRH Execution")
    return " | ".join(threats), " | ".join(errors)

def extract_ob_competency(ob_text):
    m = re.match(r"OB\s+([A-Z]{2,3})\s", str(ob_text))
    return m.group(1) if m and m.group(1) in COMPETENCY_KEYS else None

def apply_category_filter(cands, cfg):
    cat = cfg.get("type", "Any")
    if cat == "Technical Failure":
        return cands[cands["ATA"].notna()]
    if cat == "Non-Technical / CRM (Non-ATA)":
        return cands[cands["ATA"].isna()]
    if cat == "ATA Specific" and cfg.get("ata") is not None:
        return cands[cands["ATA"] == cfg["ata"]]
    return cands

def _normalize_event_name(name):
    s = str(name).upper()
    s = re.sub(r'\(REF:[^)]+\)', '', s)
    for ch in ['(', ')', '–', '—', '-', ':', ',', '/', '.', '\xa0', '_', '+']:
        s = s.replace(ch, ' ')
    return " ".join(s.split())

def competency_chip_row(codes):
    if not codes:
        return "<span style='opacity:0.6; font-size:12px;'>No competency data matched</span>"
    return "".join(
        f"<span style='background:rgba(2,132,199,0.12); color:#0284C7; border:1px solid rgba(2,132,199,0.35); "
        f"padding:2px 7px; border-radius:10px; font-size:11px; font-weight:600; margin-right:5px;'>{c}</span>"
        for c in codes
    )

def get_standard_phrase_options(grade):
    return STANDARD_PHRASE_BANK.get(grade, []) + ["Custom (type below)"]

# ==========================================
# SIDEBAR CONFIGURATION (DEFINED FIRST TO AVOID NAMEERROR)
# ==========================================
st.sidebar.markdown("<div class='sidebar-header'>📍 SLOT CONFIGURATION</div>", unsafe_allow_html=True)

if "slot_list" not in st.session_state:
    st.session_state.slot_list = [
        {"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False},
        {"phase": 2, "dod": 2, "role": "PF Focus", "type": "Any", "mandatory": True},
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
        st.session_state.slot_list.pop()
        st.rerun()

slot_configurations = []
for i in range(len(st.session_state.slot_list)):
    slot_data = st.session_state.slot_list[i]
    p_val = st.sidebar.selectbox("Phase", options=ALL_PHASE_KEYS, index=ALL_PHASE_KEYS.index(slot_data["phase"]) if slot_data["phase"] in ALL_PHASE_KEYS else 0, format_func=lambda x: f"Ph {x}: {PHASE_NAMES[x].split('–')[1].strip()}", key=f"phase_sel_{i}", label_visibility="collapsed")
    d_val = st.sidebar.selectbox("DOD", options=[1, 2, 3], index=slot_data["dod"]-1, format_func=lambda x: f"DOD {x}", key=f"dod_sel_{i}", label_visibility="collapsed")
    role_val = st.sidebar.selectbox("Role", options=ROLE_OPTIONS, index=ROLE_OPTIONS.index(slot_data["role"]) if slot_data["role"] in ROLE_OPTIONS else 0, key=f"role_sel_{i}", label_visibility="collapsed")
    type_val = st.sidebar.selectbox("Category", options=["Any", "Technical Failure", "Non-Technical / CRM (Non-ATA)", "ATA Specific"], key=f"type_sel_{i}", label_visibility="collapsed")
    
    ata_val = st.sidebar.number_input("ATA Chapter", min_value=11, max_value=80, key=f"ata_sel_{i}") if type_val == "ATA Specific" else None
    comp_val = st.sidebar.selectbox("Target Competency", options=["Any"] + list(COMPETENCY_KEYS.keys()), format_func=lambda x: x if x == "Any" else f"{x} – {COMPETENCY_KEYS[x]}", key=f"comp_sel_{i}", label_visibility="collapsed")
    is_mandatory = st.sidebar.checkbox("Pin Exercise", value=slot_data.get("mandatory", False), key=f"mand_sel_{i}")
    
    slot_configurations.append({"slot": i + 1, "phase": int(p_val), "dod": int(d_val), "role": role_val, "type": type_val, "ata": ata_val, "competency": comp_val, "mandatory": is_mandatory})

st.sidebar.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
uploaded_scen = st.sidebar.file_uploader("Upload Scenarios.csv", type=["csv"])
uploaded_comp = st.sidebar.file_uploader("Upload Keypams.xlsx (optional)", type=["xlsx"], help="Per-event competency flags.")

st.sidebar.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='sidebar-header'>📚 DOCUMENT REFERENCES</div>", unsafe_allow_html=True)
for tag, title in DOCUMENT_REFERENCES.items():
    st.sidebar.markdown(f"<div style='font-size: 11px; color: var(--text-color); opacity: 0.75; margin-bottom: 2px;'><b>[{tag}]</b> {title}</div>", unsafe_allow_html=True)

st.sidebar.markdown("<div style='text-align: center; font-size: 11px; color: var(--text-color); opacity: 0.6; margin-top: 10px;'>Designed by Shawn Abela Ver v4.7 2026</div>", unsafe_allow_html=True)

# ==========================================
# NAVIGATION TABS
# ==========================================
tab_session, tab_env, tab_orca, tab_selector, tab_debrief = st.tabs([
    "⚙️ Session Setup", 
    "🌐 Environment & IOS", 
    "📋 OPC & ORCA Workflow",
    "🎯 Scenario Selector",
    "📊 Session Debrief"
])

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

    with st.container(border=True):
        st.markdown("#### ⚡ Scenario Generator & Program Suite")
        st.markdown("Configure your slot parameters via the sidebar on the left, then generate the sequenced simulator session and EBT competency rubric below.")
        if st.button("⚡ Generate Simulator Profile", type="primary", use_container_width=True):
            st.session_state.trigger_generation = True

with tab_env:
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
        st.markdown("#### 🏛️ Major European Airport Selection & Jeppesen Layout")
        sel_apt_key = st.selectbox("Select European Aerodrome", options=list(EUROPEAN_AIRPORTS.keys()))
        apt_data = EUROPEAN_AIRPORTS[sel_apt_key]
        
        ac1, ac2 = st.columns(2)
        with ac1:
            apt_ref = st.text_input("Reference Airport / Active Rwy", value=f"{apt_data['icao']} / {apt_data['rwy'][0]}")
            ils_ident = st.text_input("ILS Ident / Freq", value=apt_data['ils'])
        with ac2:
            loc_course = st.number_input("Loc Course (°M)", min_value=0, max_value=360, value=241)
            apt_elev = st.number_input("Airport Elev (ft)", min_value=-100, max_value=14000, value=apt_data['elev'])

        st.markdown(f"""
        <div class="jepp-card">
            <div class="jepp-header">✈️ JEPPESEN SCHEMATIC LAYOUT & BRIEFING — {sel_apt_key.upper()}</div>
            <b>ICAO:</b> {apt_data['icao']} &nbsp;&nbsp;|&nbsp;&nbsp; <b>ELEV:</b> {apt_data['elev']} FT &nbsp;&nbsp;|&nbsp;&nbsp; <b>ILS / LOC:</b> {apt_data['ils']}<br/>
            <b>PUBLISHED RUNWAYS:</b> {' | '.join(apt_data['rwy'])}<br/>
            <b>SCHEMATIC ALIGNMENT:</b> [RWY {apt_data['rwy'][0]}] <==============================> [ILS GLIDESLOPE 3.0°]
        </div>
        """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### 🌐 IOS Current Conditions & Live METAR Integration")
        live_metar_str = fetch_live_metar(apt_data['icao'])
        st.markdown(f"""
        <div class="ios-card" style="border-left: 3px solid #0284C7;">
            <div class="ios-label">Live METAR Feed ({apt_data['icao']})</div>
            <div style="font-family: monospace; color: #0284C7; font-size: 13px; margin-top: 4px;">{live_metar_str}</div>
        </div>
        """, unsafe_allow_html=True)

        w_card1, w_card2 = st.columns(2)
        with w_card1:
            st.markdown("<b style='color:#0284C7;'>🌬️ Surface Wind & Atmosphere</b>", unsafe_allow_html=True)
            wc1, wc2, wc3 = st.columns(3)
            with wc1: wind_dir = st.number_input("Wind Dir (°M)", min_value=0, max_value=360, value=360, step=10)
            with wc2: wind_spd = st.number_input("Wind Speed (kt)", min_value=0, max_value=70, value=0)
            with wc3: wind_gust = st.number_input("Wind Gust (kt)", min_value=0, max_value=90, value=0)
            
            wind_str = f"{wind_dir:03d}°M / {wind_spd} kt" + (f" G {wind_gust} kt" if wind_gust > 0 else "")

            tc1, tc2, tc3 = st.columns(3)
            with tc1: oat_temp = st.number_input("Aircraft OAT (°C)", min_value=-40, max_value=50, value=14)
            with tc2:
                isa_standard = 15 - (2 * (apt_elev / 1000))
                isa_dev_calc = int(oat_temp - isa_standard)
                isa_dev = st.number_input("ISA Dev (°C)", min_value=-30, max_value=30, value=isa_dev_calc)
            with tc3: qnh_weather = st.number_input("QNH Ref (hPa)", min_value=950, max_value=1050, value=1013)

        with w_card2:
            st.markdown("<b style='color:#0284C7;'>🌧️ Runway Surface & Visibility Parameters</b>", unsafe_allow_html=True)
            rc1, rc2 = st.columns(2)
            with rc1:
                rcam_code = st.selectbox("Runway Cnd Ref (RCAM x/x/x)", [
                    "6/6/6 – Dry", "5/5/5 – Good (Frost / Wet <= 3mm)", "4/4/4 – Good to Medium",
                    "3/3/3 – Medium", "2/2/2 – Medium to Poor", "1/1/1 – Poor (Ice)", "0/0/0 – Less than Poor"
                ])
            with rc2:
                precip_ref = st.selectbox("Precipitation Ref", ["None", "Light Rain", "Moderate Rain", "Heavy Rain", "Light Snow", "Moderate Snow"])

            vc1, vc2 = st.columns(2)
            with vc1:
                vis_rvr_str = st.selectbox("Visibility / RVR", ["250.00 km (CAVOK)", "10.00 km", "5000 m", "1500 m", "550 m (CAT I)", "300 m (CAT II)", "125 m (CAT III B)"], index=0)
            with vc2:
                rwy_lighting = st.selectbox("Runway Lighting", ["Off (0)", "Level 1", "Level 2", "Level 3 (High / Standard)", "Level 4 (Max / LVO)"], index=3)

    ios_env_summary_str = f"Wind: {wind_str} | OAT: {oat_temp}°C (ISA {isa_dev:+d}°C) | QNH: {qnh_weather} hPa | Rwy Cnd: {rcam_code.split('–')[0].strip()} | Precip: {precip_ref} | Vis: {vis_rvr_str}"
    ios_summary_str = f"Apt: {apt_ref} | GW: {gw_val}t (CG {gw_cg}%) | ZFW: {zfw_val}t | Fuel: {total_fuel}t | QNH: {qnh_val}hPa | Env: {ios_env_summary_str}"

with tab_orca:
    st.markdown("#### 📋 OPC & ORCA Workflow Suite (Syllabus Auto-Extraction & CBTA Analysis)")
    st.markdown("Upload your simulator syllabus PDF below. The program automatically extracts distinct exercises, generating complete **4-phase EASA Observable Behaviors (OBs)**, primary target actions, and interactive **ORCA (Observation, Recording, Classification, Assessment)** toolkits.")

    with st.container(border=True):
        st.markdown("##### 📄 Simulator Program PDF Uploader & Exercise Detection")
        if not HAS_PYPDF:
            st.warning("⚠️ `pypdf` library is not installed in your current environment. Running in default exercise mode.")
        
        uploaded_prog_pdf = st.file_uploader("Upload Operator Simulator Syllabus / Lesson Plan (PDF)", type=["pdf"], key="prog_pdf_uploader_main")
        
        parsed_exercise_keys = list(PROGRAM_SYLLABUS_EXERCISES.keys())
        
        if uploaded_prog_pdf is not None and HAS_PYPDF:
            try:
                reader = pypdf.PdfReader(uploaded_prog_pdf)
                pdf_text = ""
                for page in reader.pages:
                    pdf_text += page.extract_text() or ""
                st.success(f"✓ Parsed {len(reader.pages)} page(s) from uploaded syllabus PDF.")
                
                detected_keys = []
                for e_key, e_data in PROGRAM_SYLLABUS_EXERCISES.items():
                    if any(kw in pdf_text.upper() for kw in e_data["keywords"]):
                        detected_keys.append(e_key)
                
                if detected_keys:
                    parsed_exercise_keys = detected_keys
                    st.info(f"Identified {len(detected_keys)} specific exercise profiles directly from PDF content.")
            except Exception as e:
                st.error(f"Error reading PDF content: {e}")

        st.markdown("<b>Select Exercises from Syllabus for Full OB & ORCA Analysis:</b>", unsafe_allow_html=True)
        col_sel_all, col_sel_multi = st.columns([1, 4])
        with col_sel_all:
            select_all_ex = st.checkbox("Select All Exercises", value=True)
            
        with col_sel_multi:
            default_selected = parsed_exercise_keys if select_all_ex else parsed_exercise_keys[:2]
            selected_ex_keys = st.multiselect(
                "Syllabus Exercises to Evaluate:",
                options=parsed_exercise_keys,
                default=default_selected,
                format_func=lambda x: PROGRAM_SYLLABUS_EXERCISES[x]["title"],
                label_visibility="collapsed"
            )

    if selected_ex_keys:
        total_obs_count = sum(
            len(step["obs"]) 
            for k in selected_ex_keys 
            for step in PROGRAM_SYLLABUS_EXERCISES[k]["sequence"]
        )
        
        checked_o = sum(1 for k in st.session_state if k.startswith("orc_o_") and st.session_state[k])
        checked_r = sum(1 for k in st.session_state if k.startswith("orc_r_") and st.session_state[k])
        checked_c = sum(1 for k in st.session_state if k.startswith("orc_c_") and st.session_state[k])
        checked_a = sum(1 for k in st.session_state if k.startswith("orc_a_") and st.session_state[k])
        
        orca_completion_pct = int((checked_o + checked_r + checked_c + checked_a) / (total_obs_count * 4) * 100) if total_obs_count > 0 else 0
        irr_score = min(100, int((checked_o * 0.35 + checked_r * 0.25 + checked_c * 0.20 + checked_a * 0.20) / (total_obs_count or 1) * 100))

        st.markdown("##### 📊 Automated ORCA & CBTA Real-Time Metrics")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Selected Modules", f"{len(selected_ex_keys)} Exercises")
        with m2: st.metric("Target OBs Tracked", f"{total_obs_count} Behaviors")
        with m3: st.metric("ORCA Completion", f"{orca_completion_pct}%")
        with m4: st.metric("IRR Concordance Index", f"{irr_score}%")

        st.markdown("---")
        st.markdown("##### 📌 Granular 4-Phase Exercise Breakdown & ORCA Checklist")

        for e_key in selected_ex_keys:
            ex_data = PROGRAM_SYLLABUS_EXERCISES[e_key]
            with st.container(border=True):
                st.markdown(f"#### ✈️ {ex_data['title']}")
                st.markdown(f"<div style='font-size: 13px; margin-bottom: 4px;'><b>Operational Stressor:</b> {ex_data['stressor']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 13px; color: #0284C7; font-weight: 600; margin-bottom: 12px;'>🎯 CBTA Competency Targets: {', '.join(ex_data['cbta_focus'])}</div>", unsafe_allow_html=True)

                for s_idx, step in enumerate(ex_data["sequence"]):
                    st.markdown(f"<b style='color: #0284C7; font-size: 14px;'>{step['phase_name']}</b>", unsafe_allow_html=True)
                    st.markdown(f"<div style='margin-left: 10px; border-left: 3px solid #0284C7; padding-left: 12px; margin-bottom: 16px; margin-top: 4px;'>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 13px; opacity: 0.9; margin-bottom: 8px;'><b>Primary Target Action (PTA):</b> <i>{step['pta']}</i></div>", unsafe_allow_html=True)
                    
                    st.markdown("<b style='font-size:12px; opacity:0.8;'>Observable Behaviors (OBs) & ORCA Protocol:</b>", unsafe_allow_html=True)
                    for ob_idx, ob in enumerate(step["obs"]):
                        cols = st.columns([0.06, 0.06, 0.06, 0.06, 0.76])
                        with cols[0]: st.checkbox("O", key=f"orc_o_{e_key}_{s_idx}_{ob_idx}", help="Observation: Behavior clearly observed")
                        with cols[1]: st.checkbox("R", key=f"orc_r_{e_key}_{s_idx}_{ob_idx}", help="Recording: FSTD telemetry / note logged")
                        with cols[2]: st.checkbox("C", key=f"orc_c_{e_key}_{s_idx}_{ob_idx}", help="Classification: Linked to core competency")
                        with cols[3]: st.checkbox("A", key=f"orc_a_{e_key}_{s_idx}_{ob_idx}", help="Assessment: Graded against EASA standard")
                        with cols[4]:
                            comp_tag = ob.get("comp", extract_ob_competency(ob["text"]) or "GEN")
                            st.markdown(
                                f"<span style='font-size: 13px;'>{ob['text']} "
                                f"<span class='ref-badge'>{ob['ref']}</span> "
                                f"<span style='background:rgba(16,185,129,0.12); color:#10B981; border:1px solid rgba(16,185,129,0.3); padding:1px 5px; border-radius:4px; font-size:10px; font-weight:700;'>{comp_tag}</span></span>", 
                                unsafe_allow_html=True
                            )
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Select at least one exercise from the uploaded program syllabus above to view the detailed OB & ORCA analysis.")

with tab_selector:
    st.markdown("#### 🎯 Interactive Simulator Scenario Builder & Selector")
    st.markdown("Configure slots via the sidebar, then browse the full scenario matrix here once it loads below — filter it, and see exactly which competencies each scenario targets before you generate a session.")

with tab_debrief:
    st.markdown("#### 📊 Session Debrief — Competency Coverage & Standardized Summary")
    if "final_df" in st.session_state:
        final_df = st.session_state.final_df
        total_dod = final_df["DOD"].sum()
        
        comp_grades = {c: [] for c in COMPETENCY_KEYS}
        for _, row in final_df.iterrows():
            slot_num = int(row["SLOT"])
            g = st.session_state.get(f"grade_slot_{slot_num}", 3)
            for c in st.session_state.get("slot_competencies", {}).get(slot_num, []):
                if g is not None: comp_grades[c].append(g)

        cov_col1, cov_col2 = st.columns([1.3, 1])
        with cov_col1:
            st.markdown("<b>Average Grade by Competency</b>", unsafe_allow_html=True)
            chart_df = pd.DataFrame({
                "Competency": list(COMPETENCY_KEYS.keys()),
                "Avg Grade": [sum(v) / len(v) if v else 0 for v in comp_grades.values()],
                "Times Demonstrated": [len(v) for v in comp_grades.values()],
            }).set_index("Competency")
            st.bar_chart(chart_df["Avg Grade"])
        with cov_col2:
            st.markdown("<b>Coverage Count</b>", unsafe_allow_html=True)
            st.dataframe(chart_df, use_container_width=True)
    else:
        st.info("Generate a session profile in the **Session Setup** workflow area to populate debrief analytics.")

# ==========================================
# DATA LOADING & GENERATION LOGIC (RUNS AFTER SIDEBAR)
# ==========================================
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(base_path, relative_path)
    if os.path.exists(local_path): return local_path
    parent_path = os.path.join(os.path.dirname(base_path), relative_path)
    return parent_path if os.path.exists(parent_path) else local_path

scenarios_source = uploaded_scen if uploaded_scen is not None else resource_path("Scenarios.csv")
competency_source = uploaded_comp if uploaded_comp is not None else (resource_path("Keypams.xlsx") if os.path.exists(resource_path("Keypams.xlsx")) else None)

@st.cache_data(show_spinner="Loading and caching matrix scenarios...")
def load_scenario_database(s_source, c_source):
    try:
        df_raw = pd.read_csv(s_source, encoding="cp1252") if os.path.exists(str(s_source)) or hasattr(s_source, 'read') else pd.read_csv(s_source, encoding="utf-8")
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        while len(df_raw.columns) < 10: df_raw[f"Col_{len(df_raw.columns)}"] = None

        records = []
        for idx, row in df_raw.iterrows():
            event, dod, ata = row.iloc[0], row.iloc[1], row.get('ATA', None)
            if pd.isna(event) or pd.isna(dod) or len(str(event).strip()) <= 2: continue
            for p_idx, col_idx in enumerate(range(2, 10)):
                if col_idx < len(row):
                    val = row.iloc[col_idx]
                    if pd.notna(val) and str(val).strip() != "":
                        records.append({"EVENT": str(event).strip(), "DOD": int(float(dod)), "PHASES": p_idx + 1, "ATA": int(float(ata)) if pd.notna(ata) else None, "DURATION": 15})
        df = pd.DataFrame(records)
        df["scenario_id"] = [f"SC-{i+1:02d}" for i in range(len(df))]

        match_stats = {"keypams_loaded": False, "matched_events": 0, "total_events": df["EVENT"].nunique() if not df.empty else 0}

        comp_lookup = {}
        if c_source is not None:
            try:
                df_comp = pd.read_excel(c_source)
                df_comp.columns = [str(c).strip() for c in df_comp.columns]
                if "SA" in df_comp.columns and "SAW" not in df_comp.columns:
                    df_comp = df_comp.rename(columns={"SA": "SAW"})
                comp_cols = [c for c in COMPETENCY_KEYS.keys() if c in df_comp.columns]
                if comp_cols and "Event" in df_comp.columns:
                    for _, crow in df_comp.iterrows():
                        k_event = str(crow["Event"])
                        norm_k = _normalize_event_name(k_event)
                        active_comps = [c for c in comp_cols if pd.notna(crow[c]) and float(crow[c]) >= 1]
                        comp_lookup[norm_k] = active_comps
                    match_stats["keypams_loaded"] = True
            except Exception:
                pass

        norm_keys = list(comp_lookup.keys())
        matched_events = set()

        def resolve_competencies(ev, phase):
            codes = set()
            ev_upper = str(ev).upper()
            for ex_key, ex_data in PROGRAM_SYLLABUS_EXERCISES.items():
                if any(kw in ev_upper for kw in ex_data["keywords"]):
                    codes.update(ex_data["cbta_focus"])
            
            if comp_lookup:
                norm_ev = _normalize_event_name(ev)
                hit = comp_lookup.get(norm_ev)
                if hit is None:
                    tokens_ev = set(norm_ev.split())
                    for k in norm_keys:
                        tokens_k = set(k.split())
                        if len(tokens_ev & tokens_k) >= 2 and len(tokens_ev & tokens_k) / max(len(tokens_ev), len(tokens_k)) > 0.45:
                            hit = comp_lookup[k]
                            break
                if hit is None:
                    close = difflib.get_close_matches(norm_ev, norm_keys, n=1, cutoff=0.5)
                    if close:
                        hit = comp_lookup[close[0]]
                if hit:
                    matched_events.add(ev)
                    codes.update(hit)
            return sorted(codes) if codes else ["FPM", "APK"]

        df["COMPETENCIES"] = df.apply(lambda r: resolve_competencies(r["EVENT"], r["PHASES"]), axis=1)
        match_stats["matched_events"] = len(matched_events)
        return df, match_stats
    except Exception as e:
        return None, str(e)

def generate_pdf_briefing(df_session, grades_dict, notes_dict, comp_dict, total_dod, max_dod, mode, capt, fo, sim_id_val, ios_info):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=11, leading=13, textColor=colors.HexColor('#0284C7'))
    subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontSize=7.5, leading=9, textColor=colors.HexColor('#555555'))
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=6.5, leading=8.5)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontSize=6.5, leading=8.5, fontName='Helvetica-Bold')

    elements = [
        Paragraph(f"KM MALTA AIRLINES — SIMULATOR PERFORMANCE & EBT GRADING RECORD ({mode.upper()})", title_style),
        Paragraph(f"<b>Crew:</b> {capt} & {fo} &nbsp;|&nbsp; <b>Device:</b> {sim_id_val} &nbsp;|&nbsp; <b>Total DOD:</b> {total_dod}/{max_dod}", subtitle_style),
        Paragraph(f"<b>IOS Setup Config:</b> <i>{ios_info}</i>", subtitle_style),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0284C7'), spaceAfter=4)
    ]

    table_data = [[
        Paragraph("<b>Slot</b>", cell_bold), Paragraph("<b>Phase / Event</b>", cell_bold),
        Paragraph("<b>Role / DOD</b>", cell_bold), Paragraph("<b>Target Actions & Observable Behaviors (OBs)</b>", cell_bold),
        Paragraph("<b>Grade (1-5) & Notes</b>", cell_bold)
    ]]

    for _, row in df_session.iterrows():
        slot_id = int(row["SLOT"])
        
        seq_data = PROGRAM_SYLLABUS_EXERCISES.get("EX-01_EFATO", {})["sequence"]
        for ex_key, ex_val in PROGRAM_SYLLABUS_EXERCISES.items():
            if any(kw in str(row['EVENT']).upper() for kw in ex_val["keywords"]):
                seq_data = ex_val["sequence"]
                break

        combined_details = ""
        for step in seq_data:
            combined_details += f"<b>{step['phase_name']}</b><br/><i>Action:</i> {step['pta']}<br/>"
            for ob in step['obs']:
                combined_details += f"<font color='#006600'>✓ {ob['text']}</font> <i>[{ob['ref']}]</i><br/>"
            combined_details += "<br/>"

        phase_event_str = f"<b>{row['PHASE_NAME']}</b><br/>{row['EVENT']}"
        role_dod_str = f"{row.get('ROLE','PF')}<br/>DOD {row['DOD']}"
        
        grade_val = grades_dict.get(slot_id, 3)
        note_val = notes_dict.get(slot_id, "Standard performance.")
        comps_val = comp_dict.get(slot_id, [])
        comps_str = ", ".join(comps_val) if comps_val else "—"
        grade_str = f"<b>Grade: {grade_val}/5</b><br/><i>{GRADE_DESCRIPTORS.get(grade_val, '')}</i><br/><b>Competencies:</b> {comps_str}<br/><b>Notes:</b> {note_val}"

        table_data.append([
            Paragraph(str(slot_id), cell_style),
            Paragraph(phase_event_str, cell_style),
            Paragraph(role_dod_str, cell_style),
            Paragraph(combined_details, cell_style),
            Paragraph(grade_str, cell_style)
        ])

    t = Table(table_data, colWidths=[24, 105, 52, 195, 162])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F4F8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0284C7')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
    ]))
    elements.extend([t])

    doc.build(elements)
    buffer.seek(0)
    return buffer

df, match_stats = load_scenario_database(scenarios_source, competency_source)
if df is not None:
    df["TEM_THREAT"], df["TEM_ERROR"] = zip(*df.apply(lambda r: derive_tem_tags(r["EVENT"], r["PHASES"], 0, 0, rcam_code, vis_rvr_str), axis=1))
    
    if st.session_state.get("trigger_generation", False):
        selected_events = []
        used_titles = set()
        for cfg in slot_configurations:
            if cfg.get("mandatory") and cfg["phase"] == 2:
                forced_match = df[(df["PHASES"] == 2) & (df["DOD"] == cfg["dod"])]
                if not forced_match.empty:
                    picked = forced_match.iloc[0].to_dict()
                else:
                    picked = {"EVENT": "Engine Failure After V1 (SIM-EFATO-01)", "DOD": cfg["dod"], "PHASES": 2, "scenario_id": "SC-FORCED", "COMPETENCIES": ["FPM", "APK", "PSD"]}
                picked["SLOT"] = cfg["slot"]
                picked["ROLE"] = cfg["role"]
                picked["PHASE_NAME"] = PHASE_NAMES[cfg["phase"]]
                selected_events.append(picked)
                used_titles.add(picked["EVENT"])
                continue

            cands = df[(df["PHASES"] == cfg["phase"]) & (df["DOD"] == cfg["dod"]) & (~df["EVENT"].isin(used_titles))]
            cands = apply_category_filter(cands, cfg)
            if cands.empty and allow_fallback:
                cands = df[(df["PHASES"] == cfg["phase"]) & (df["DOD"] == cfg["dod"]) & (~df["EVENT"].isin(used_titles))]
            if not cands.empty:
                picked = cands.sample(n=1).iloc[0].to_dict()
                picked["SLOT"] = cfg["slot"]
                picked["ROLE"] = cfg["role"]
                picked["PHASE_NAME"] = PHASE_NAMES[cfg["phase"]]
                selected_events.append(picked)
                used_titles.add(picked["EVENT"])
        st.session_state.final_df = pd.DataFrame(selected_events).sort_values("SLOT").reset_index(drop=True)
        st.session_state.slot_overrides = {}
        st.session_state.slot_competencies = {}
        st.session_state.trigger_generation = False
        st.success("Session Profile Generated!")

    if "final_df" in st.session_state:
        with tab_session:
            if "slot_overrides" not in st.session_state:
                st.session_state.slot_overrides = {}

            final_df = st.session_state.final_df
            for idx, row in final_df.iterrows():
                s_id = int(row["SLOT"])
                if s_id in st.session_state.slot_overrides:
                    ov_data = st.session_state.slot_overrides[s_id]
                    final_df.loc[idx, "EVENT"] = ov_data["EVENT"]
                    final_df.loc[idx, "DOD"] = ov_data["DOD"]

            total_dod = final_df["DOD"].sum()
            
            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1: st.metric(label="Active Session Slots", value=f"{len(final_df)} Modules")
            with m_col2: st.metric(label="Cumulative Session DOD", value=f"{total_dod} / {max_dod_threshold} Target")
            with m_col3:
                compliance_status = "Within Ceiling" if total_dod <= max_dod_threshold else "Exceeds Ceiling"
                st.metric(label="DOD Compliance Status", value=compliance_status)

            st.markdown("#### ✈️ Sequenced Simulator Session & EBT Competency Rubric")
            
            instructor_grades = {}
            instructor_notes = {}
            slot_competencies = {}
            
            for idx, row in final_df.iterrows():
                slot_num = int(row['SLOT'])
                event_title = row['EVENT']
                dod = int(row['DOD'])
                phase_num = int(row['PHASES'])
                role = row.get('ROLE', 'PF Focus')
                
                sequence_data = PROGRAM_SYLLABUS_EXERCISES.get("EX-01_EFATO", {})["sequence"]
                for ex_key, ex_val in PROGRAM_SYLLABUS_EXERCISES.items():
                    if any(kw in str(event_title).upper() for kw in ex_val["keywords"]):
                        sequence_data = ex_val["sequence"]
                        break

                with st.expander(f"Slot #{slot_num:02d} — {row['PHASE_NAME']} | DOD {dod} | {event_title} ({role})", expanded=False):
                    st.markdown("""
                    <div style='background-color: var(--secondary-background-color); padding: 18px; border-radius: 8px; border: 1px solid rgba(128,128,128,0.2);'>
                        <h5 style='color: #0284C7; margin-top: 0; margin-bottom: 16px;'>⏱️ Chronological Execution Sequence & OB Markers</h5>
                    """, unsafe_allow_html=True)
                    
                    for step in sequence_data:
                        st.markdown(f"<b style='color: var(--text-color); font-size: 15px;'>{step['phase_name']}</b>", unsafe_allow_html=True)
                        st.markdown(f"<div style='margin-left: 14px; border-left: 3px solid #0284C7; padding-left: 14px; margin-bottom: 18px; margin-top: 6px;'>", unsafe_allow_html=True)
                        st.markdown(f"<div style='color: var(--text-color); font-size: 13.5px; margin-bottom: 10px; opacity: 0.85;'><b>Target Action (PTA):</b> {step['pta']}</div>", unsafe_allow_html=True)
                        for ob in step['obs']:
                            st.markdown(f"<div style='color: #10B981; font-size: 13.5px; font-weight: 600; margin-bottom: 4px;'>✓ {ob['text']} <span class='ref-badge' title='{DOCUMENT_REFERENCES.get(ob['ref'], ob['ref'])}'>{ob['ref']}</span></div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:11.5px; opacity:0.7; margin-bottom:4px;'>Competencies exercised by this scenario:</div>{competency_chip_row(row.get('COMPETENCIES', []))}", unsafe_allow_html=True)
                    demonstrated = st.multiselect(
                        f"✅ Competencies Actually Demonstrated (Slot #{slot_num:02d})",
                        options=list(COMPETENCY_KEYS.keys()),
                        default=list(row.get("COMPETENCIES", [])),
                        format_func=lambda x: f"{x} – {COMPETENCY_KEYS[x]}",
                        key=f"comp_demo_{slot_num}"
                    )
                    slot_competencies[slot_num] = demonstrated

                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                    g_col1, g_col2 = st.columns([1, 2])
                    with g_col1:
                        instructor_grades[slot_num] = st.selectbox(
                            f"KM Malta Grade (Slot #{slot_num:02d})",
                            options=[5, 4, 3, 2, 1],
                            index=2,
                            format_func=lambda x: {
                                5: "Grade 5 (Excellent)",
                                4: "Grade 4 (Very Good)",
                                3: "Grade 3 (Good / Standard)",
                                2: "Grade 2 (Min Acceptable - Review)",
                                1: "Grade 1 (Unsatisfactory)"
                            }[x],
                            key=f"grade_slot_{slot_num}"
                        )
                    with g_col2:
                        grade_now = instructor_grades[slot_num]
                        phrase_choice = st.selectbox(
                            f"Standardized Comment (Slot #{slot_num:02d})",
                            options=get_standard_phrase_options(grade_now),
                            key=f"phrase_slot_{slot_num}"
                        )
                        if phrase_choice == "Custom (type below)":
                            instructor_notes[slot_num] = st.text_input(f"Custom Note (Slot #{slot_num:02d})", value="", key=f"note_slot_{slot_num}")
                        else:
                            extra_detail = st.text_input(f"Optional detail (Slot #{slot_num:02d})", value="", key=f"note_extra_{slot_num}")
                            instructor_notes[slot_num] = f"{phrase_choice} {extra_detail.strip()}" if extra_detail.strip() else phrase_choice

            st.session_state.slot_competencies = slot_competencies
            st.markdown("---")
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                csv_export = final_df.to_csv(index=False)
                st.download_button(label="📥 Download Session Schedule (CSV)", data=csv_export, file_name=f"sim_session_DOD_{max_dod_threshold}.csv", mime="text/csv", use_container_width=True, key="download_csv_button")
            with col_exp2:
                pdf_data = generate_pdf_briefing(final_df, instructor_grades, instructor_notes, slot_competencies, total_dod, max_dod_threshold, session_mode, capt_name, fo_name, sim_id, ios_summary_str)
                st.download_button(label="📄 Download Completed KM Malta EBT PDF Record", data=pdf_data, file_name=f"km_malta_ebt_record_{max_dod_threshold}.pdf", mime="application/pdf", use_container_width=True, key="download_pdf_button")
