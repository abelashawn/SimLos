import streamlit as st
import pandas as pd
import io
import re
import os
import sys
import difflib
import urllib.request

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
    
    /* Allow multi-row wrapping for navigation tabs */
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
    div[data-testid="stMetricValue"] {
        background-color: transparent !important;
        border: none !important;
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
st.markdown("<p style='color: var(--text-color); opacity: 0.7; font-size: 14px; margin-top: -8px; font-weight: 500;'>KM Malta A320 STD2.2 / Advanced Evidence-Based Training (EBT) Optimizer</p>", unsafe_allow_html=True)

# ==========================================
# CENTRALIZED DATA DICTIONARIES & MATRICES
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

SCENARIO_OB_MATRIX = {
    "V1_CUT_EFATO": {
        "keywords": ["ENGINE", "V1 CUT", "EFATO"],
        "sequence": [
            {
                "phase": "1. Flight Path Stabilization (Take-off & Initial Climb)",
                "pta": "Maintain directional control with rudder and establish single-engine climb pitch attitude.",
                "obs": [
                    {"text": "OB FPM 3.1: Immediate rudder input to counter asymmetric yaw; roll maintained within ±5°.", "ref": "FCTM_ABN"},
                    {"text": "OB FPM 3.2: PM actively calls out FMA mode changes and monitors V2 trend.", "ref": "FCOM_PRO"},
                    {"text": "OB SAW 6.2: Maintains awareness of Engine-Out SID and terrain clearance profile.", "ref": "OM_B"}
                ]
            },
            {
                "phase": "2. Core Execution & Systems Breakdown (ECAM Cycle)",
                "pta": "Manage thrust levers symmetrically before calling memory items; execute ECAM actions systematically.",
                "obs": [
                    {"text": "OB APK 1.4: Strict ECAM discipline loop (cross-confirmation of Engine Master/Fire Pushbuttons).", "ref": "QRH"},
                    {"text": "OB COM 2.4: Clear closed-loop verification callouts before moving primary switches.", "ref": "EASA_EBT"},
                    {"text": "OB WLM 8.1: PF isolates attention on primary flight path while delegating ECAM management cleanly to the PM.", "ref": "ICAO_9995"}
                ]
            },
            {
                "phase": "3. Strategic Diversion & Decision Making",
                "pta": "Evaluate diversion options, secure aircraft systems, and coordinate with ATC/Cabin.",
                "obs": [
                    {"text": "OB PSD 5.3: Formulates structured risk mitigation utilizing FORDEC or DODAR matrices.", "ref": "OM_A"},
                    {"text": "OB SAW 6.1: Actively monitors remaining fuel flow and single-engine performance data.", "ref": "EASA_EBT"},
                    {"text": "OB COM 2.5: Delivers clear MAYDAY declaration and structured NITS briefing to cabin crew.", "ref": "OM_A"}
                ]
            }
        ]
    },
    "DISPATCH_MEL": {
        "keywords": ["MEL", "CDL", "DISPATCH", "PRE-FLIGHT"],
        "sequence": [
            {
                "phase": "1. Dispatch Review & Threat Assessment",
                "pta": "Review MEL/CDL dispatch conditions, operational procedures, and performance penalties thoroughly.",
                "obs": [
                    {"text": "OB APK 1.1: Accurately identifies correct operational data and documentation (FCOM, QRH, MEL).", "ref": "OM_B"},
                    {"text": "OB SAW 6.4: Correctly anticipates environmental or operational limitations based on the defect.", "ref": "EASA_EBT"}
                ]
            },
            {
                "phase": "2. Cockpit Preparation & Briefing",
                "pta": "Ensure technical log entries and flight deck preparation checks are completed prior to taxi.",
                "obs": [
                    {"text": "OB APK 1.2: Strict adherence to pre-flight procedures and log entry sign-offs.", "ref": "FCOM_PRO"},
                    {"text": "OB COM 2.5: Clearly communicates dispatch limitations and configuration constraints during the departure briefing.", "ref": "ICAO_9995"}
                ]
            },
            {
                "phase": "3. Ground Workload Management",
                "pta": "Distribute pre-flight tasks effectively without cognitive overload.",
                "obs": [
                    {"text": "OB WLM 8.1: Prioritizes and distributes tasks effectively to prevent pre-flight saturation.", "ref": "EASA_EBT"},
                    {"text": "OB LTW 7.1: Establishes a collaborative, supportive flight deck atmosphere from the start.", "ref": "EASA_EBT"}
                ]
            }
        ]
    },
    "APPROACH_LANDING": {
        "keywords": ["APPROACH", "ILS", "LANDING"],
        "sequence": [
            {
                "phase": "1. Profile Intercept & Environmental Monitoring",
                "pta": "Monitor lateral and vertical profile against stable approach criteria below 1,000ft AGL.",
                "obs": [
                    {"text": "OB SAW 6.3: Proactive monitoring of ceiling, visibility, and shifting wind components.", "ref": "OM_A"},
                    {"text": "OB FPA 4.2: Actively monitors and verifies flight path instruments and primary flight displays.", "ref": "FCOM_PRO"}
                ]
            },
            {
                "phase": "2. Configuration & Automation Management",
                "pta": "Actively monitor FMA changes during capture and mode transitions while configuring the aircraft.",
                "obs": [
                    {"text": "OB FPA 4.4: Selects appropriate automation modes for approach and anticipates target transitions.", "ref": "FCTM_ABN"},
                    {"text": "OB APK 1.5: Exhibits precision in manual cockpit actions and configuration timing.", "ref": "EASA_EBT"}
                ]
            },
            {
                "phase": "3. Final Approach Tracking",
                "pta": "Execute timely callouts for DA/MDA, energy state, and runway in sight.",
                "obs": [
                    {"text": "OB COM 2.4: Ensures vital altitude and stable approach callouts are clearly vocalized.", "ref": "FCOM_PRO"},
                    {"text": "OB FPM 3.1: Controls the aircraft smoothly and accurately to touchdown (if manual).", "ref": "EASA_EBT"}
                ]
            }
        ]
    },
    "WINDSHEAR_TURBULENCE": {
        "keywords": ["WIND", "SHEAR", "TURB"],
        "sequence": [
            {
                "phase": "1. Recognition & Immediate Action",
                "pta": "Immediate recognition of meteorological hazard and energy state perturbation.",
                "obs": [
                    {"text": "OB SAW 6.4: Rapidly anticipates or recognizes severe windshear warnings and energy state anomalies.", "ref": "FCTM_ABN"},
                    {"text": "OB PSD 5.1: Identifies the threat instantly without fixation on irrelevant indications.", "ref": "ICAO_9995"}
                ]
            },
            {
                "phase": "2. Escape Maneuver Execution",
                "pta": "Apply EASA/Airbus reactive windshear escape maneuver (TOGA, max pitch attitude, wings level).",
                "obs": [
                    {"text": "OB FPM 3.1: Decisive application of TOGA thrust and maximum reactive pitch tracking without over-controlling.", "ref": "QRH"},
                    {"text": "OB APK 1.4: Defers aircraft configuration changes (gear/flaps) until strictly clear of the hazard.", "ref": "FCOM_PRO"}
                ]
            },
            {
                "phase": "3. Recovery & Communication",
                "pta": "Resume normal flight path once clear and notify ATC.",
                "obs": [
                    {"text": "OB COM 2.1: Immediate, concise declaration of windshear escape maneuver to Air Traffic Control.", "ref": "OM_A"},
                    {"text": "OB WLM 8.1: Manages high-tempo workload safely during the transition back to standard flight logic.", "ref": "EASA_EBT"}
                ]
            }
        ]
    },
    "EMERGENCY_DESCENT": {
        "keywords": ["DEPRESSUR", "EMERGENCY DESCENT"],
        "sequence": [
            {
                "phase": "1. Immediate Survival Actions",
                "pta": "Don oxygen masks promptly and establish flight deck communication.",
                "obs": [
                    {"text": "OB APK 1.4: Rapid, disciplined execution of oxygen mask memory items.", "ref": "QRH"},
                    {"text": "OB COM 2.1: Adjusts audio panels to verify clear, closed-loop inter-cockpit communication.", "ref": "FCOM_PRO"}
                ]
            },
            {
                "phase": "2. Emergency Descent Initiation",
                "pta": "Initiate emergency descent procedure (select target altitude, heading change, and speedbrake).",
                "obs": [
                    {"text": "OB FPA 4.4: Rapidly manipulates FCU to establish aggressive descent vector.", "ref": "FCTM_ABN"},
                    {"text": "OB WLM 8.3: Prioritizes flight path stabilization and altitude capture over non-essential diagnostics.", "ref": "ICAO_9995"}
                ]
            },
            {
                "phase": "3. ATC & Cabin Coordination",
                "pta": "Coordinate ATC emergency notification and evaluate passenger oxygen requirements.",
                "obs": [
                    {"text": "OB COM 2.5: Delivers clear MAYDAY declaration and prompt cabin notifications.", "ref": "OM_A"},
                    {"text": "OB SAW 6.2: Maintains continuous awareness of terrain limitations (MORA/MSA) during the descent profile.", "ref": "OM_B"}
                ]
            }
        ]
    },
    "GENERIC_MALFUNCTION": {
        "keywords": ["DEFAULT"],
        "sequence": [
            {
                "phase": "1. Identification & Verification",
                "pta": "Identify malfunction or specific requirements and cross-check indications.",
                "obs": [
                    {"text": "OB SAW 6.1: Continuous monitoring of aircraft state and operational profile.", "ref": "EASA_EBT"},
                    {"text": "OB PSD 5.1: Identifies operational errors or unexpected malfunctions early.", "ref": "ICAO_9995"}
                ]
            },
            {
                "phase": "2. Procedure Application",
                "pta": "Adhere strictly to company SOPs and normal/abnormal checklists.",
                "obs": [
                    {"text": "OB APK 1.2: Follows SOPs meticulously unless safety dictates otherwise.", "ref": "FCOM_PRO"},
                    {"text": "OB COM 2.4: Ensures vital checklist messages are correctly understood and acknowledged.", "ref": "EASA_EBT"}
                ]
            },
            {
                "phase": "3. Operational Adjustment",
                "pta": "Maintain effective situational awareness and adjust the flight plan as necessary.",
                "obs": [
                    {"text": "OB WLM 8.1: Prioritizes tasks effectively under changing conditions.", "ref": "ICAO_9995"},
                    {"text": "OB PSD 5.4: Decides on an optimal course of action in a timely, safe manner.", "ref": "EASA_EBT"}
                ]
            }
        ]
    }
}

OPC_FAILURE_MATRIX = {
    "V1_CUT_EFATO": {
        "title": "Engine Failure After Take-Off (EFATO) / V1 Cut",
        "phase": 2,
        "stressor": "Catastrophic Engine 1 (Left) Failure at V1 + 2 knots, leading to asymmetric thrust and system degradation.",
        "sequence": [
            {
                "phase_name": "Phase 1: Flight Path Stabilization (Take-off & Initial Climb)",
                "pta": "Maintain directional control with rudder and establish single-engine climb pitch attitude.",
                "obs": [
                    {"text": "OB FPM 3.1: Immediate rudder input to counter asymmetric yaw; roll kept within ±5°; SRS pitch target (~12.5°) achieved.", "ref": "FCTM_ABN"},
                    {"text": "OB FPM 3.2: PM actively calls out FMA changes and monitors speed trends relative to V2.", "ref": "FCOM_PRO"},
                    {"text": "OB SAW 6.2: Maintains awareness of engine-out departure procedure (EO SID) and terrain clearance profile.", "ref": "OM_B"}
                ]
            },
            {
                "phase_name": "Phase 2: Core Execution & Systems Breakdown (ECAM Cycle)",
                "pta": "Manage thrust levers symmetrically before calling memory items; execute ECAM actions systematically above 400 ft AGL.",
                "obs": [
                    {"text": "OB APK 1.4: Strict ECAM discipline loop. PM reads line, touches Engine Master 1, pauses, asks 'Confirm Engine 1?', PF visually verifies and declares 'Confirm' before switch actuation.", "ref": "QRH"},
                    {"text": "OB COM 2.4: Clear closed-loop verification callouts before moving primary switches.", "ref": "EASA_EBT"},
                    {"text": "OB WLM 8.1: PF isolates attention strictly to primary flight parameters while delegating ECAM management completely to the PM.", "ref": "OM_A"}
                ]
            }
        ]
    },
    "DUAL_GEN_FAILURE": {
        "title": "Dual Generator Failure / Emergency Electrical Configuration",
        "phase": 3,
        "stressor": "Total loss of main AC buses (Engines 1 and 2 generator failure), triggering emergency electrical configuration and RAT deployment.",
        "sequence": [
            {
                "phase_name": "Phase 1: System Recognition & Immediate Memory Items",
                "pta": "Recognize bus unpowering, maintain flight path during transient stability loss, and manage electrical load.",
                "obs": [
                    {"text": "OB SAW 6.1: Rapidly identifies loss of primary displays and monitors emergency bus reversion.", "ref": "FCOM_PRO"},
                    {"text": "OB APK 1.2: Adheres strictly to non-normal checklist priorities before attempting optional troubleshooting.", "ref": "QRH"}
                ]
            },
            {
                "phase_name": "Phase 2: Configuration & Communication Management",
                "pta": "Reference QRH for emergency electrical configuration limits and fuel pump management.",
                "obs": [
                    {"text": "OB COM 2.4: Ensures radio communication is established on appropriate VHF/RMP frequencies powered by emergency network.", "ref": "OM_A"},
                    {"text": "OB PSD 5.1: Identifies secondary system degradations early without fixation on single indicators.", "ref": "FCTM_ABN"}
                ]
            }
        ]
    },
    "SE_ILS_APPROACH": {
        "title": "Single Engine ILS Approach with Engine Fire / Severe Damage",
        "phase": 6,
        "stressor": "Terminal area execution of an ILS approach with one engine secured due to a prior fire warning, combined with high crosswind components.",
        "sequence": [
            {
                "phase_name": "Phase 1: Briefing & Stable Approach Setup",
                "pta": "Revise landing briefing accounting for single-engine flap/slat constraints, missed approach routing, and higher approach speeds.",
                "obs": [
                    {"text": "OB LTW 7.1: Captain actively encourages First Officer input during the single-engine landing briefing.", "ref": "OM_A"},
                    {"text": "OB SAW 6.3: Proactive monitoring of energy state, sink rate, and wind corrections along final glide path.", "ref": "FCOM_PRO"}
                ]
            },
            {
                "phase_name": "Phase 2: Flare & Touchdown Execution",
                "pta": "Manage asymmetric thrust during flare, counter drift with wing-low/crab techniques, and deploy ground spoilers/reverse thrust safely.",
                "obs": [
                    {"text": "OB FPM 3.1: Decisive rudder control during flare to ensure touchdown aligned with runway centerline.", "ref": "FCTM_ABN"},
                    {"text": "OB APK 1.5: Precise timing of thrust lever management and directional braking control on rollout.", "ref": "FCOM_PRO"}
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

def get_detailed_scenario_ob_breakdown(event_title, phase_num):
    title_u = str(event_title).upper()
    for key, data in SCENARIO_OB_MATRIX.items():
        if key == "GENERIC_MALFUNCTION": continue
        if any(kw in title_u for kw in data["keywords"]) or (key == "DISPATCH_MEL" and phase_num == 1) or (key == "APPROACH_LANDING" and phase_num in [6,7]):
            return data["sequence"]
    return SCENARIO_OB_MATRIX["GENERIC_MALFUNCTION"]["sequence"]

def extract_ob_competency(ob_text):
    m = re.match(r"OB\s+([A-Z]{2,3})\s", str(ob_text))
    return m.group(1) if m and m.group(1) in COMPETENCY_KEYS else None

def get_scenario_competencies(event_title, phase_num):
    codes = set()
    for step in get_detailed_scenario_ob_breakdown(event_title, phase_num):
        for ob in step["obs"]:
            code = extract_ob_competency(ob["text"])
            if code:
                codes.add(code)
    return sorted(codes)

def apply_category_filter(cands, cfg):
    cat = cfg.get("type", "Any")
    if cat == "Technical Failure":
        return cands[cands["ATA"].notna()]
    if cat == "Non-Technical / CRM (Non-ATA)":
        return cands[cands["ATA"].isna()]
    if cat == "ATA Specific" and cfg.get("ata") is not None:
        return cands[cands["ATA"] == cfg["ata"]]
    return cands

def apply_competency_filter(cands, target_competency):
    if target_competency == "Any":
        return cands
    mask = cands.apply(lambda r: target_competency in get_scenario_competencies(r["EVENT"], r["PHASES"]), axis=1)
    return cands[mask]

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
    st.markdown("#### 📋 OPC & ORCA Workflow Suite (Inter-Rater Reliability)")
    st.markdown("Execute standard Operator Proficiency Check failure scenarios using the standardized **Observation (O) → Recording (R) → Classification (C) → Assessment (A)** protocol.")

    selected_opc_keys = st.multiselect(
        "Select Active OPC Failure Modules:",
        options=list(OPC_FAILURE_MATRIX.keys()),
        default=["V1_CUT_EFATO", "SE_ILS_APPROACH"],
        format_func=lambda x: OPC_FAILURE_MATRIX[x]["title"]
    )

    if selected_opc_keys:
        for f_key in selected_opc_keys:
            mod_data = OPC_FAILURE_MATRIX[f_key]
            with st.container(border=True):
                st.markdown(f"##### 📌 {mod_data['title']} (Phase {mod_data['phase']})")
                st.markdown(f"<div style='font-size: 13px; opacity: 0.85; margin-bottom: 10px;'><b>Stressor:</b> {mod_data['stressor']}</div>", unsafe_allow_html=True)

                for s_idx, step in enumerate(mod_data["sequence"]):
                    st.markdown(f"<b style='color: #0284C7; font-size: 13.5px;'>{step['phase_name']}</b>", unsafe_allow_html=True)
                    st.markdown(f"<div style='margin-left: 10px; border-left: 2px solid #0284C7; padding-left: 10px; margin-bottom: 12px;'>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 12.5px; opacity: 0.8; margin-bottom: 6px;'><b>PTA:</b> {step['pta']}</div>", unsafe_allow_html=True)
                    
                    for ob_idx, ob in enumerate(step["obs"]):
                        cols = st.columns([0.05, 0.05, 0.05, 0.85])
                        with cols[0]: st.checkbox("O", key=f"orc_o_{f_key}_{s_idx}_{ob_idx}", help="Observation")
                        with cols[1]: st.checkbox("R", key=f"orc_r_{f_key}_{s_idx}_{ob_idx}", help="Recording")
                        with cols[2]: st.checkbox("C", key=f"orc_c_{f_key}_{s_idx}_{ob_idx}", help="Classification")
                        with cols[3]: st.markdown(f"<span style='font-size: 13px;'>{ob['text']} <span class='ref-badge'>{ob['ref']}</span></span>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Select at least one OPC failure module above to load the ORCA checklist workflow.")

with tab_selector:
    st.markdown("#### 🎯 Interactive Simulator Scenario Builder & Selector")
    st.markdown("Configure slots via the sidebar, then browse the full scenario matrix here once it loads below — filter it, and see exactly which competencies each scenario targets before you generate a session.")

# ==========================================
# ROBUST SIDEBAR: SLOTS CONFIGURATION & REFERENCES FOOTER
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

current_total_dod = sum([st.session_state.get(f"dod_sel_{i}", st.session_state.slot_list[i]["dod"]) for i in range(len(st.session_state.slot_list))])

if current_total_dod > max_dod_threshold:
    st.sidebar.markdown(f"<div class='status-badge-warn'>⚠️ DOD Ceiling Exceeded ({current_total_dod} / {max_dod_threshold})</div>", unsafe_allow_html=True)
else:
    st.sidebar.markdown(f"<div class='status-badge-ok'>✓ Target DOD: {current_total_dod} / {max_dod_threshold}</div>", unsafe_allow_html=True)

st.sidebar.markdown("<div style='margin: 10px 0; border-bottom: 1px solid rgba(128,128,128,0.2);'></div>", unsafe_allow_html=True)

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

# Document References Footer in the Left Column (Sidebar)
st.sidebar.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='sidebar-header'>📚 DOCUMENT REFERENCES</div>", unsafe_allow_html=True)
for tag, title in DOCUMENT_REFERENCES.items():
    st.sidebar.markdown(f"<div style='font-size: 11px; color: var(--text-color); opacity: 0.75; margin-bottom: 2px;'><b>[{tag}]</b> {title}</div>", unsafe_allow_html=True)

st.sidebar.markdown("<div style='text-align: center; font-size: 11px; color: var(--text-color); opacity: 0.6; margin-top: 10px;'>Designed by Shawn Abela Ver v4.2 2026</div>", unsafe_allow_html=True)

# ==========================================
# DATA LOADING & PDF GENERATION (OPTIMIZED MATCHING)
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
            codes = set(get_scenario_competencies(ev, phase))
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
            return sorted(codes)

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
        sequence_data = get_detailed_scenario_ob_breakdown(row['EVENT'], row['PHASES'])
        
        combined_details = ""
        for step in sequence_data:
            combined_details += f"<b>{step['phase']}</b><br/><i>Action:</i> {step['pta']}<br/>"
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

if uploaded_scen is None and not os.path.exists(resource_path("Scenarios.csv")):
    st.warning("⚠️ `Scenarios.csv` not found. Please upload your scenarios file using the sidebar uploader.")
else:
    df, match_stats = load_scenario_database(scenarios_source, competency_source)
    if df is not None:
        df["TEM_THREAT"], df["TEM_ERROR"] = zip(*df.apply(lambda r: derive_tem_tags(r["EVENT"], r["PHASES"], 0, 0, rcam_code, vis_rvr_str), axis=1))
        if match_stats.get("keypams_loaded"):
            pct = (match_stats["matched_events"] / match_stats["total_events"] * 100) if match_stats["total_events"] else 0
            st.success(f"✓ {len(df)} scenario/phase rows loaded | Keypams.xlsx cross-matched {match_stats['matched_events']}/{match_stats['total_events']} events ({pct:.0f}%).")
        else:
            st.success(f"✓ {len(df)} scenario/phase rows loaded | Competencies auto-derived from each scenario's OB sequence.")

        if st.button("⚡ Generate Simulator Profile", type="primary"):
            selected_events = []
            used_titles = set()
            for cfg in slot_configurations:
                if cfg.get("mandatory") and cfg["phase"] == 2:
                    forced_match = df[(df["PHASES"] == 2) & (df["DOD"] == cfg["dod"])]
                    if not forced_match.empty:
                        picked = forced_match.iloc[0].to_dict()
                    else:
                        picked = {"EVENT": "Engine Failure After V1 (SIM-EFATO-01)", "DOD": cfg["dod"], "PHASES": 2, "scenario_id": "SC-FORCED", "COMPETENCIES": get_scenario_competencies("Engine Failure After V1 (SIM-EFATO-01)", 2)}
                    picked["SLOT"] = cfg["slot"]
                    picked["ROLE"] = cfg["role"]
                    picked["PHASE_NAME"] = PHASE_NAMES[cfg["phase"]]
                    selected_events.append(picked)
                    used_titles.add(picked["EVENT"])
                    continue

                cands = df[(df["PHASES"] == cfg["phase"]) & (df["DOD"] == cfg["dod"]) & (~df["EVENT"].isin(used_titles))]
                cands = apply_category_filter(cands, cfg)
                cands = apply_competency_filter(cands, cfg.get("competency", "Any"))
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
            st.success("Session Profile Generated!")

        if "final_df" in st.session_state:
            if "slot_overrides" not in st.session_state:
                st.session_state.slot_overrides = {}

            final_df = st.session_state.final_df
            
            for idx, row in final_df.iterrows():
                s_id = int(row["SLOT"])
                if s_id in st.session_state.slot_overrides:
                    ov_data = st.session_state.slot_overrides[s_id]
                    final_df.loc[idx, "EVENT"] = ov_data["EVENT"]
                    final_df.loc[idx, "DOD"] = ov_data["DOD"]
                    src_match = df[(df["EVENT"] == ov_data["EVENT"]) & (df["DOD"] == ov_data["DOD"])]
                    if not src_match.empty:
                        final_df.at[idx, "COMPETENCIES"] = src_match.iloc[0]["COMPETENCIES"]

            total_dod = final_df["DOD"].sum()
            
            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.metric(label="Active Session Slots", value=f"{len(final_df)} Modules")
            with m_col2:
                st.metric(label="Cumulative Session DOD", value=f"{total_dod} / {max_dod_threshold} Target")
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
                
                sequence_data = get_detailed_scenario_ob_breakdown(event_title, phase_num)
                
                with st.expander(f"Slot #{slot_num:02d} — {row['PHASE_NAME']} | DOD {dod} | {event_title} ({role})", expanded=False):
                    eligible_cands = df[(df["PHASES"] == phase_num) & (df["DOD"] == dod)]
                    if eligible_cands.empty:
                        eligible_cands = df[df["PHASES"] == phase_num] 
                    
                    cand_options = []
                    event_map = {}
                    for _, cand_row in eligible_cands.iterrows():
                        ev_name = cand_row["EVENT"]
                        ev_dod = int(cand_row["DOD"])
                        label = f"{ev_name}"
                        cand_options.append(label)
                        event_map[label] = {"EVENT": ev_name, "DOD": ev_dod}
                    
                    cand_options = sorted(list(set(cand_options)))
                    
                    default_label = event_title
                    if default_label not in cand_options:
                        cand_options.insert(0, default_label)
                        event_map[default_label] = {"EVENT": event_title, "DOD": dod}
                    
                    default_index = cand_options.index(default_label) if default_label in cand_options else 0
                    
                    chosen_label = st.selectbox(
                        f"🔄 Swap Scenario (Phase {phase_num}, DOD {dod})",
                        options=cand_options,
                        index=default_index,
                        key=f"override_slot_{slot_num}"
                    )
                    
                    selected_ev_data = event_map[chosen_label]
                    if selected_ev_data["EVENT"] != event_title or selected_ev_data["DOD"] != dod:
                        st.session_state.slot_overrides[slot_num] = selected_ev_data
                        st.rerun()

                    st.markdown("""
                    <div style='background-color: var(--secondary-background-color); padding: 18px; border-radius: 8px; border: 1px solid rgba(128,128,128,0.2);'>
                        <h5 style='color: #0284C7; margin-top: 0; margin-bottom: 16px;'>⏱️ Chronological Execution Sequence & OB Markers</h5>
                    """, unsafe_allow_html=True)
                    
                    for step in sequence_data:
                        st.markdown(f"<b style='color: var(--text-color); font-size: 15px;'>{step['phase']}</b>", unsafe_allow_html=True)
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
                        key=f"comp_demo_{slot_num}",
                        help="Defaults to the competencies this scenario's own OB sequence targets."
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
                        st.markdown(f"<div style='font-size:11.5px; opacity:0.75; font-style:italic; margin-top:-6px;'>{GRADE_DESCRIPTORS[instructor_grades[slot_num]]}</div>", unsafe_allow_html=True)
                    with g_col2:
                        grade_now = instructor_grades[slot_num]
                        phrase_choice = st.selectbox(
                            f"Standardized Comment (Slot #{slot_num:02d})",
                            options=get_standard_phrase_options(grade_now),
                            key=f"phrase_slot_{slot_num}",
                            help="Picking from the standard phrase bank."
                        )
                        if phrase_choice == "Custom (type below)":
                            custom_text = st.text_input(
                                f"Custom Note (Slot #{slot_num:02d})",
                                value="",
                                key=f"note_slot_{slot_num}",
                                placeholder="Describe the scenario-specific detail."
                            )
                            instructor_notes[slot_num] = custom_text
                        else:
                            instructor_notes[slot_num] = phrase_choice
                            extra_detail = st.text_input(
                                f"Optional scenario-specific detail (Slot #{slot_num:02d})",
                                value="",
                                key=f"note_extra_{slot_num}",
                                placeholder="Anything specific to this run."
                            )
                            if extra_detail.strip():
                                instructor_notes[slot_num] = f"{phrase_choice} {extra_detail.strip()}"

            st.session_state.slot_competencies = slot_competencies
            st.markdown("---")
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                csv_export = final_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Session Schedule (CSV)",
                    data=csv_export,
                    file_name=f"sim_session_DOD_{max_dod_threshold}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_csv_button"
                )
            with col_exp2:
                pdf_data = generate_pdf_briefing(final_df, instructor_grades, instructor_notes, slot_competencies, total_dod, max_dod_threshold, session_mode, capt_name, fo_name, sim_id, ios_summary_str)
                st.download_button(
                    label="📄 Download Completed KM Malta EBT PDF Record",
                    data=pdf_data,
                    file_name=f"km_malta_ebt_record_{max_dod_threshold}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_pdf_button"
                )

            with tab_debrief:
                st.markdown("#### 📊 Session Debrief — Competency Coverage & Standardized Summary")

                comp_grades = {c: [] for c in COMPETENCY_KEYS}
                for _, row in final_df.iterrows():
                    slot_num = int(row["SLOT"])
                    g = instructor_grades.get(slot_num)
                    for c in slot_competencies.get(slot_num, []):
                        if g is not None:
                            comp_grades[c].append(g)

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

                uncovered = [c for c, v in comp_grades.items() if not v]
                if uncovered:
                    st.markdown(
                        f"<div class='status-badge-warn'>⚠️ Not sampled this session: {', '.join(uncovered)}</div>"
                        f"<div style='font-size:11.5px; opacity:0.75; margin-top:4px;'>ICAO Doc 9995 recommends EBT sessions build broad competency coverage over a training cycle.</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown("<div class='status-badge-ok'>✓ All 9 core competencies sampled this session</div>", unsafe_allow_html=True)

                low_grade_slots = [int(r["SLOT"]) for _, r in final_df.iterrows() if instructor_grades.get(int(r["SLOT"]), 3) <= 2]
                st.markdown("---")
                st.markdown("<b>Standardized Debrief Script</b>", unsafe_allow_html=True)
                st.markdown("<div style='font-size:11.5px; opacity:0.7; margin-bottom:6px;'>Auto-assembled from grade descriptors and standardized comments.</div>", unsafe_allow_html=True)
                script_lines = [f"Session Debrief — {capt_name} & {fo_name} — {sim_id} — Total DOD {total_dod}/{max_dod_threshold}\n"]
                for _, row in final_df.iterrows():
                    slot_num = int(row["SLOT"])
                    g = instructor_grades.get(slot_num, 3)
                    script_lines.append(
                        f"Slot {slot_num:02d} ({row['EVENT']}, {row['PHASE_NAME']}): Grade {g}/5. {instructor_notes.get(slot_num, '')}"
                    )
                if low_grade_slots:
                    script_lines.append(f"\nFollow-up required on slot(s): {', '.join(str(s) for s in low_grade_slots)} — graded 2 or below.")
                st.text_area("Debrief script", value="\n".join(script_lines), height=220, key="debrief_script_area")

        else:
            with tab_debrief:
                st.info("Generate a Simulator Profile in the **Session Setup** area above to populate the debrief summary here.")

        with tab_selector:
            st.markdown("---")
            st.markdown("#### 📚 Full Scenario Matrix")
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                f_phase = st.selectbox("Filter by Phase", options=["Any"] + ALL_PHASE_KEYS, format_func=lambda x: x if x == "Any" else PHASE_NAMES[x], key="sel_filter_phase")
            with f_col2:
                f_dod = st.selectbox("Filter by DOD", options=["Any", 1, 2, 3], key="sel_filter_dod")
            with f_col3:
                f_comp = st.selectbox("Filter by Competency", options=["Any"] + list(COMPETENCY_KEYS.keys()), format_func=lambda x: x if x == "Any" else f"{x} – {COMPETENCY_KEYS[x]}", key="sel_filter_comp")

            view_df = df.copy()
            if f_phase != "Any":
                view_df = view_df[view_df["PHASES"] == f_phase]
            if f_dod != "Any":
                view_df = view_df[view_df["DOD"] == f_dod]
            if f_comp != "Any":
                view_df = view_df[view_df["COMPETENCIES"].apply(lambda c: f_comp in c)]

            st.caption(f"{len(view_df)} of {len(df)} scenario/phase rows match the current filters.")
            display_df = view_df[["EVENT", "PHASES", "DOD", "ATA", "COMPETENCIES"]].copy()
            display_df["PHASES"] = display_df["PHASES"].map(PHASE_NAMES)
            display_df["COMPETENCIES"] = display_df["COMPETENCIES"].apply(lambda c: ", ".join(c) if c else "—")
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=420)
    else:
        st.error(f"⚠️ Could not load the scenario database: {match_stats}")
