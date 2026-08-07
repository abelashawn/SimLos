"""Simulator Session Plan & IOS Setup Builder.

Single-file build. Organized top-to-bottom into clearly marked sections
(config -> styles -> weather -> history -> data loading -> slot UI ->
scenario builder -> PDF export -> page layout) so it reads like the
multi-module version, just concatenated for easy distribution.

Setup:
    pip install -r requirements.txt
    streamlit run app.py

Expects Scenarios.csv and Keypams.xlsx next to this file.
"""

from __future__ import annotations

import difflib
import io
import json
import logging
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# SECTION 1: CONFIG
# ==========================================
APP_TITLE = "Simulator Session Plan & IOS Setup Builder"
APP_SUBTITLE = "KM Malta A320 STD2.2 / Advanced Evidence-Based Training (EBT) Optimizer"
APP_VERSION = "v3.1 2026"
APP_AUTHOR = "Shawn Abela"

HISTORY_FILE = Path(__file__).parent / "data" / "session_history.json"
HISTORY_MAX_ENTRIES = 20
HISTORY_LOOKBACK_SESSIONS = 5

SCENARIOS_FILENAME = "Scenarios.csv"
COMPETENCY_FILENAME = "Keypams.xlsx"

PHASE_NAMES = {
    1: "Phase 1 - Pre-flight and taxi",
    2: "Phase 2 - Take-off",
    3: "Phase 3 - Climb",
    4: "Phase 4 - Cruise",
    5: "Phase 5 - Descent",
    6: "Phase 6 - Approach",
    7: "Phase 7 - Landing",
    8: "Phase 8 - Taxi and post-flight",
}
ALL_PHASE_KEYS = list(PHASE_NAMES.keys())

COMPETENCY_KEYS = {
    "APK": "Application of Knowledge / Procedures",
    "COM": "Communication",
    "FPM": "Flight Path Management",
    "FPA": "Flight Path Authority / Angle",
    "LTW": "Leadership & Teamwork",
    "PSD": "Problem Solving & Decision Making",
    "SA": "Situational Awareness",
    "WLM": "Workload Management",
}

ROLE_OPTIONS = ["PF Focus", "PM Focus", "Both / CRM", "Instructor Choice"]
SLOT_TYPE_OPTIONS = ["Any", "Technical Failure", "Non-Technical / CRM", "ATA Specific"]

DEFAULT_SLOTS = [
    {"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False},
    {"phase": 2, "dod": 2, "role": "PF Focus", "type": "Any", "mandatory": False},
    {"phase": 6, "dod": 2, "role": "PM Focus", "type": "Any", "mandatory": False},
    {"phase": 7, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False},
]
MAX_SLOTS = 12
MIN_SLOTS = 1

EUROPEAN_AIRPORTS = {
    "LMML (Malta Luqa)": {"icao": "LMML", "elev": 293, "rwy": ["13", "31"], "ils": "110.50 (13)"},
    "LFPG (Paris Charles de Gaulle)": {
        "icao": "LFPG", "elev": 392,
        "rwy": ["08R/26L", "08L/26R", "09R/27L", "09L/27R"], "ils": "109.50 (26L)",
    },
    "EGLL (London Heathrow)": {"icao": "EGLL", "elev": 83, "rwy": ["09L/27R", "09R/27L"], "ils": "110.30 (27R)"},
    "EDDF (Frankfurt)": {
        "icao": "EDDF", "elev": 364, "rwy": ["07C/25C", "07R/25L", "18", "07L/25R"], "ils": "111.15 (25C)",
    },
    "EHAM (Amsterdam Schiphol)": {
        "icao": "EHAM", "elev": -11,
        "rwy": ["06/24", "09/27", "18C/36C", "18L/36R", "18R/36L"], "ils": "108.50 (24)",
    },
    "LIRF (Rome Fiumicino)": {
        "icao": "LIRF", "elev": 14, "rwy": ["16R/34L", "16L/34R", "07/25"], "ils": "109.10 (16R)",
    },
    "LEMD (Madrid Barajas)": {
        "icao": "LEMD", "elev": 2001,
        "rwy": ["18L/36R", "18R/36L", "14L/32R", "14R/32L"], "ils": "109.90 (36R)",
    },
    "LOWW (Vienna Schwechat)": {"icao": "LOWW", "elev": 600, "rwy": ["16/34", "11/29"], "ils": "109.30 (16)"},
    "LSZH (Zurich Kloten)": {"icao": "LSZH", "elev": 1416, "rwy": ["14/32", "16/34", "10/28"], "ils": "109.50 (14)"},
}

RCAM_OPTIONS = [
    "6/6/6 - Dry",
    "5/5/5 - Good (Frost / Wet <= 3mm)",
    "4/4/4 - Good to medium (Compacted snow <= -15C)",
    "3/3/3 - Medium (Slippery wet / dry snow)",
    "2/2/2 - Medium to poor (Standing water / slush)",
    "1/1/1 - Poor (Ice)",
    "0/0/0 - Less than poor",
]
PRECIP_OPTIONS = ["None", "Light rain", "Moderate rain", "Heavy rain", "Light snow", "Moderate snow", "Freezing rain / drizzle"]
VISIBILITY_OPTIONS = ["250.00 km (CAVOK)", "10.00 km", "5000 m", "1500 m", "550 m (CAT I)", "300 m (CAT II)", "125 m (CAT III B)", "75 m (LVTO limit)"]
RUNWAY_LIGHTING_OPTIONS = ["Off (0)", "Level 1 (Low)", "Level 2 (Medium)", "Level 3 (High / Standard)", "Level 4 (Max / LVO)"]
CLOUD_COVERAGE_OPTIONS = ["Clear", "FEW (1-2 octas)", "SCT (3-4 octas)", "BKN (5-7 octas)", "OVC (8 octas)"]
WINDSHEAR_OPTIONS = ["None", "Light windshear", "Moderate microburst", "Severe microburst"]
TURBULENCE_OPTIONS = ["None", "Base 5% (Light)", "Moderate (15%)", "Severe (30%)"]
ICING_OPTIONS = ["None", "Trace / light", "Moderate", "Severe"]
SESSION_MODE_OPTIONS = ["EBT Evaluation & Coaching", "EBT Line-Oriented Assessment", "Recurrent Check (LPC/OPC)"]


# ==========================================
# SECTION 2: STYLES
# ==========================================
COLORS = {
    "bg_page": "#0B1220",
    "bg_panel": "#131B2E",
    "bg_panel_alt": "#0F172A",
    "border": "#26324A",
    "border_strong": "#334155",
    "text_primary": "#E6EDF7",
    "text_secondary": "#94A3B8",
    "accent": "#38BDF8",
    "accent_strong": "#0284C7",
    "accent_hover": "#0369A1",
    "success_bg": "rgba(16, 185, 129, 0.14)",
    "success_text": "#34D399",
    "success_border": "rgba(16, 185, 129, 0.30)",
    "warn_bg": "rgba(245, 158, 11, 0.14)",
    "warn_text": "#FBBF24",
    "warn_border": "rgba(245, 158, 11, 0.30)",
}

_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    .block-container {{ padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 96% !important; }}
    .main {{ background-color: {COLORS['bg_page']}; color: {COLORS['text_primary']}; }}
    h1, h2, h3, h4 {{
        color: {COLORS['accent']} !important; font-weight: 700 !important;
        margin-top: 6px !important; margin-bottom: 6px !important;
    }}

    div[data-testid="stForm"], div[data-testid="stContainer"] {{
        background-color: {COLORS['bg_panel']} !important;
        border: 1px solid {COLORS['border']} !important;
        border-radius: 8px !important;
    }}

    div[data-testid="stMetric"] {{
        background-color: {COLORS['bg_panel']} !important;
        border: 1px solid {COLORS['border']} !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
    }}
    div[data-testid="stMetricLabel"] * {{ color: {COLORS['text_secondary']} !important; font-weight: 600 !important; }}
    div[data-testid="stMetricValue"] {{ background-color: transparent !important; border: none !important; }}
    div[data-testid="stMetricValue"] * {{ color: {COLORS['accent']} !important; font-weight: 700 !important; }}

    .ios-card {{
        background-color: {COLORS['bg_panel']}; border: 1px solid {COLORS['border']};
        border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
    }}
    .ios-label {{
        font-size: 11px; color: {COLORS['text_secondary']}; text-transform: uppercase;
        letter-spacing: 0.05em; font-weight: 600;
    }}
    .ios-value {{ font-size: 18px; color: {COLORS['accent']}; font-weight: 700; }}

    .jepp-card {{
        background-color: {COLORS['bg_panel_alt']}; border: 2px solid {COLORS['accent']};
        border-radius: 6px; padding: 14px; font-family: 'Courier New', monospace;
        color: {COLORS['text_primary']}; margin-top: 10px; margin-bottom: 12px;
    }}
    .jepp-header {{
        font-size: 14px; font-weight: 700; color: {COLORS['accent']};
        border-bottom: 1px dashed {COLORS['border_strong']}; padding-bottom: 4px; margin-bottom: 8px;
    }}

    section[data-testid="stSidebar"] {{
        background-color: #070D1E; color: {COLORS['text_primary']};
        min-width: 310px !important; max-width: 310px !important;
    }}
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown {{ color: {COLORS['text_primary']} !important; }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] * {{ font-size: 11.5px !important; }}

    .sidebar-header {{ font-size: 13px; font-weight: 700; color: {COLORS['accent']}; letter-spacing: 0.04em; margin-bottom: 6px; }}
    .slot-container {{
        background-color: {COLORS['bg_panel']}; border: 1px solid {COLORS['border']};
        border-left: 3px solid {COLORS['accent_strong']}; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px;
    }}
    .slot-title {{ font-size: 11px; font-weight: 700; color: {COLORS['text_secondary']}; text-transform: uppercase; margin-bottom: 4px; }}

    .status-badge-ok {{
        background-color: {COLORS['success_bg']}; color: {COLORS['success_text']};
        border: 1px solid {COLORS['success_border']}; padding: 4px 8px; border-radius: 4px;
        font-size: 11px; font-weight: 600; text-align: center;
    }}
    .status-badge-warn {{
        background-color: {COLORS['warn_bg']}; color: {COLORS['warn_text']};
        border: 1px solid {COLORS['warn_border']}; padding: 4px 8px; border-radius: 4px;
        font-size: 11px; font-weight: 600; text-align: center;
    }}

    .stButton>button {{
        background-color: {COLORS['accent_strong']}; color: #FFFFFF; border-radius: 6px;
        font-weight: 600; border: none; padding: 0.45rem 0.9rem; transition: all 0.15s ease;
    }}
    .stButton>button:hover {{ background-color: {COLORS['accent_hover']}; color: #FFFFFF; transform: translateY(-1px); }}

    .thin-divider {{ margin: 12px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.12); }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ==========================================
# SECTION 3: LIVE WEATHER (cached - was re-fetching on every rerun before)
# ==========================================
METAR_URL_TEMPLATE = "https://aviationweather.gov/api/data/metar?ids={icao}&format=raw"
METAR_TIMEOUT_SECONDS = 3
METAR_CACHE_TTL_SECONDS = 300


@st.cache_data(ttl=METAR_CACHE_TTL_SECONDS, show_spinner=False)
def fetch_live_metar(icao_code: str) -> str:
    url = METAR_URL_TEMPLATE.format(icao=icao_code)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=METAR_TIMEOUT_SECONDS) as response:
            metar = response.read().decode("utf-8").strip()
        return metar if metar else "No live METAR data returned."
    except Exception:
        logger.warning("METAR fetch failed for %s", icao_code, exc_info=True)
        return "METAR connection unavailable (offline mode)."


# ==========================================
# SECTION 4: SESSION HISTORY (errors logged, not swallowed)
# ==========================================
def _load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read session history at %s; starting fresh.", HISTORY_FILE, exc_info=True)
        return []


def get_recent_used_events() -> set[str]:
    history = _load_history()
    recent_events: set[str] = set()
    for session in history[-HISTORY_LOOKBACK_SESSIONS:]:
        recent_events.update(session.get("events", []))
    return recent_events


def save_session_to_history(df_session: pd.DataFrame, mode: str, captain: str, first_officer: str) -> None:
    history = _load_history()
    history.append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "mode": mode,
            "crew": f"{captain} / {first_officer}",
            "events": df_session["EVENT"].tolist(),
        }
    )
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY_FILE.open("w") as f:
            json.dump(history[-HISTORY_MAX_ENTRIES:], f, indent=2)
    except OSError:
        logger.warning("Could not write session history to %s.", HISTORY_FILE, exc_info=True)


# ==========================================
# SECTION 5: SCENARIO MATRIX LOADING & TEM TAGGING
# ==========================================
PHASE_COLUMN_START_INDEX = 2
NUM_PHASE_COLUMNS = 8
DEFAULT_EVENT_DURATION_MINUTES = 15
FUZZY_MATCH_CUTOFF = 0.55

_WEATHER_KEYWORDS = ("WIND", "TURB", "ICE", "SHEAR", "VIS", "FOG", "RAIN", "SNOW")
_SYSTEM_KEYWORDS = ("FAIL", "ELEC", "HYD", "ENG", "FIRE", "BLEED", "PRESS", "GEAR", "FLAP", "NAV")
_ATC_KEYWORDS = ("ATC", "HOLD", "REROUTE", "SLOT", "TAXI", "CONGEST")
_FLIGHT_PATH_PHASES = (2, 6, 7)


def resource_path(relative_path: str) -> str:
    """Resolves a bundled resource path, working both as a plain script and
    as a PyInstaller-frozen executable."""
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def _normalize_title(title: str) -> str:
    cleaned = re.sub(r"\(Ref:[^)]+\)", "", str(title), flags=re.IGNORECASE)
    cleaned = re.sub(r"[^A-Z0-9\s]", " ", cleaned.upper())
    return re.sub(r"\s+", " ", cleaned).strip()


def get_best_match(scenario_title: str, competency_titles: list[str]) -> Optional[str]:
    """Matches a scenario title to the closest competency-matrix title:
    exact match -> normalized exact match -> subset-of-words match -> fuzzy ratio match."""
    if not scenario_title or pd.isna(scenario_title):
        return None

    if scenario_title in competency_titles:
        return scenario_title

    normalized_target = _normalize_title(scenario_title)
    normalized_map = {_normalize_title(c): c for c in competency_titles}

    if normalized_target in normalized_map:
        return normalized_map[normalized_target]

    target_words = set(normalized_target.split())
    if len(target_words) > 1:
        for normalized_candidate, original in normalized_map.items():
            if target_words.issubset(set(normalized_candidate.split())):
                return original

    fuzzy_matches = difflib.get_close_matches(
        normalized_target, list(normalized_map.keys()), n=1, cutoff=FUZZY_MATCH_CUTOFF
    )
    return normalized_map[fuzzy_matches[0]] if fuzzy_matches else None


def derive_tem_tags(event_title: str, phase_num: int, wind_speed: int, wind_gust: int, rcam_code: str, visibility: str) -> tuple[str, str]:
    title_upper = str(event_title).upper()
    threats: list[str] = []
    errors: list[str] = []

    if wind_speed > 20 or wind_gust > 25:
        threats.append("High surface wind / gusts")
    if any(code in rcam_code for code in ("1/1/1", "2/2/2", "3/3/3")):
        threats.append("Contaminated runway / poor friction")
    if any(tag in visibility for tag in ("CAT II", "CAT III", "75 m")):
        threats.append("Low visibility operations (LVO)")
    if any(word in title_upper for word in _WEATHER_KEYWORDS):
        threats.append("Adverse weather / windshear")
    if any(word in title_upper for word in _SYSTEM_KEYWORDS):
        threats.append("Aircraft system failure")
    if any(word in title_upper for word in _ATC_KEYWORDS):
        threats.append("ATC / operational pressure")
    if not threats:
        threats.append("Standard operational threat")

    if phase_num in _FLIGHT_PATH_PHASES:
        errors.append("Flight path control")
    if "FAIL" in title_upper or "PROC" in title_upper:
        errors.append("SOP / QRH execution")
    if not errors:
        errors.append("Communication & CRM")

    return " | ".join(threats), " | ".join(errors)


def _read_scenarios_csv(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="cp1252")
    except (UnicodeDecodeError, LookupError):
        return pd.read_csv(path, encoding="utf-8")


def _extract_scenario_records(df_raw: pd.DataFrame) -> list[dict]:
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    while len(df_raw.columns) < 10:
        df_raw[f"Col_{len(df_raw.columns)}"] = None

    phase_col_indices = list(range(PHASE_COLUMN_START_INDEX, PHASE_COLUMN_START_INDEX + NUM_PHASE_COLUMNS))
    records: list[dict] = []

    for _, row in df_raw.iterrows():
        event, dod = row.iloc[0], row.iloc[1]
        if pd.isna(event) or pd.isna(dod):
            continue

        event_str = str(event).strip()
        if len(event_str) == 1 and event_str.isalpha():
            continue

        ata = row["ATA"] if "ATA" in row and pd.notna(row["ATA"]) else None

        for phase_num, col_idx in enumerate(phase_col_indices, start=1):
            if col_idx >= len(row):
                continue
            val = row.iloc[col_idx]
            if pd.notna(val) and str(val).strip() != "":
                records.append(
                    {
                        "EVENT": event_str,
                        "DOD": int(float(dod)),
                        "PHASES": phase_num,
                        "ATA": int(float(ata)) if ata else None,
                        "DURATION": DEFAULT_EVENT_DURATION_MINUTES,
                    }
                )
    return records


def _attach_competency_scores(df: pd.DataFrame, competency_path: str) -> bool:
    """Mutates df in place, adding one float column per competency code.
    Indexes the competency sheet once by title instead of re-filtering it
    per scenario row (was O(n^2))."""
    for competency_key in COMPETENCY_KEYS:
        df[competency_key] = 0.0

    if not os.path.exists(competency_path):
        return False

    try:
        df_comp = pd.read_excel(competency_path)
    except Exception:
        logger.warning("Could not read competency matrix at %s.", competency_path, exc_info=True)
        return False

    df_comp.columns = [str(c).strip() for c in df_comp.columns]
    event_col_name = df_comp.columns[0]
    comp_cols_present = [c for c in COMPETENCY_KEYS if c in df_comp.columns]
    if not comp_cols_present:
        return False

    competency_titles = df_comp[event_col_name].dropna().tolist()
    df["Matched_Comp_Event"] = df["EVENT"].apply(lambda title: get_best_match(title, competency_titles))

    comp_by_title = df_comp.set_index(event_col_name)

    for idx, matched_title in df["Matched_Comp_Event"].items():
        if not matched_title or matched_title not in comp_by_title.index:
            continue
        match_row = comp_by_title.loc[matched_title]
        for competency_key in comp_cols_present:
            try:
                value = float(match_row[competency_key])
                df.loc[idx, competency_key] = value if pd.notna(value) else 0.0
            except (ValueError, TypeError):
                continue

    return True


@st.cache_data(show_spinner="Loading and caching matrix scenarios...")
def load_scenario_database(scenarios_path: str, competency_path: str) -> tuple[Optional[pd.DataFrame], object]:
    try:
        df_raw = _read_scenarios_csv(scenarios_path)
        records = _extract_scenario_records(df_raw)

        df = pd.DataFrame(records)
        df["DOD"] = pd.to_numeric(df["DOD"], errors="coerce").fillna(1).astype(int)
        df["PHASES"] = pd.to_numeric(df["PHASES"], errors="coerce").fillna(1).astype(int)

        comp_loaded = _attach_competency_scores(df, competency_path)

        df["scenario_id"] = [f"SC-{i + 1:02d}" for i in range(len(df))]
        return df, comp_loaded
    except Exception as exc:
        logger.error("Failed to load scenario database.", exc_info=True)
        return None, str(exc)


# ==========================================
# SECTION 6: SLOT UI + SHARED SCENARIO-APPLY HELPER
# (apply_scenario_to_slot replaces what used to be 3 duplicated field-copy blocks)
# ==========================================
_STATE_KEY_PREFIXES = ("phase_sel_", "dod_sel_", "role_sel_", "type_sel_", "ata_sel_", "mand_sel_")


def _init_slot_state() -> None:
    if "slot_list" not in st.session_state:
        st.session_state.slot_list = [dict(slot) for slot in DEFAULT_SLOTS]


def _add_slot() -> None:
    if len(st.session_state.slot_list) < MAX_SLOTS:
        st.session_state.slot_list.append({"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False})


def _remove_last_slot() -> None:
    if len(st.session_state.slot_list) <= MIN_SLOTS:
        return
    idx = len(st.session_state.slot_list) - 1
    st.session_state.slot_list.pop()
    for prefix in _STATE_KEY_PREFIXES:
        st.session_state.pop(f"{prefix}{idx}", None)


def _current_total_dod() -> int:
    total = 0
    for i, slot in enumerate(st.session_state.slot_list):
        total += st.session_state.get(f"dod_sel_{i}", slot["dod"])
    return total


def _render_dod_status(max_dod_threshold: int) -> None:
    total = _current_total_dod()
    st.sidebar.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
    if total > max_dod_threshold:
        st.sidebar.markdown(
            f"<div class='status-badge-warn'>DOD ceiling exceeded ({total} / {max_dod_threshold})</div>",
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            f"<div class='status-badge-ok'>Target DOD: {total} / {max_dod_threshold}</div>",
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("<div style='margin: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.12);'></div>", unsafe_allow_html=True)


def _render_single_slot(index: int, slot_data: dict) -> dict:
    defaults = {
        f"phase_sel_{index}": slot_data["phase"],
        f"dod_sel_{index}": slot_data["dod"],
        f"role_sel_{index}": slot_data.get("role", "PF Focus"),
        f"type_sel_{index}": slot_data.get("type", "Any"),
        f"ata_sel_{index}": slot_data.get("ata", 22),
        f"mand_sel_{index}": slot_data.get("mandatory", False),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    st.sidebar.markdown(f"<div class='slot-container'><div class='slot-title'>SLOT #{index + 1:02d}</div>", unsafe_allow_html=True)

    row1_col1, row1_col2 = st.sidebar.columns([2.3, 1.7])
    with row1_col1:
        phase_val = st.selectbox(
            "Phase", options=ALL_PHASE_KEYS,
            format_func=lambda p: f"Ph {p}: {PHASE_NAMES[p].split('-')[1].strip()}",
            key=f"phase_sel_{index}", label_visibility="collapsed",
        )
    with row1_col2:
        dod_val = st.selectbox(
            "DOD", options=[1, 2, 3], format_func=lambda d: f"DOD {d}",
            key=f"dod_sel_{index}", label_visibility="collapsed",
        )

    row2_col1, row2_col2 = st.sidebar.columns([1.8, 2.2])
    with row2_col1:
        role_val = st.selectbox("Role", options=ROLE_OPTIONS, key=f"role_sel_{index}", label_visibility="collapsed")
    with row2_col2:
        type_val = st.selectbox("Category", options=SLOT_TYPE_OPTIONS, key=f"type_sel_{index}", label_visibility="collapsed")

    ata_val: Optional[int] = None
    if type_val == "ATA Specific":
        ata_val = st.sidebar.number_input("ATA chapter", min_value=11, max_value=80, key=f"ata_sel_{index}")

    is_mandatory = st.sidebar.checkbox("Pin exercise", key=f"mand_sel_{index}")
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    slot_data.update(phase=phase_val, dod=dod_val, role=role_val, type=type_val, ata=ata_val, mandatory=is_mandatory)
    return {
        "slot": index + 1,
        "phase": int(phase_val),
        "dod": int(dod_val),
        "role": role_val,
        "type": type_val,
        "ata": ata_val,
        "mandatory": is_mandatory,
    }


def render_sidebar_slots(max_dod_threshold: int) -> list[dict]:
    _init_slot_state()
    st.sidebar.markdown("<div class='sidebar-header'>SLOT CONFIGURATION</div>", unsafe_allow_html=True)

    add_col, remove_col = st.sidebar.columns(2)
    if add_col.button("Add slot", use_container_width=True):
        _add_slot()
        st.rerun()
    if remove_col.button("Remove last", use_container_width=True):
        _remove_last_slot()
        st.rerun()

    _render_dod_status(max_dod_threshold)

    return [_render_single_slot(i, slot_data) for i, slot_data in enumerate(st.session_state.slot_list)]


def apply_scenario_to_slot(target_df: pd.DataFrame, row_index: int, scenario: dict, role: str, match_type: str) -> None:
    """Writes a picked scenario's fields onto one row of a session DataFrame,
    in place. The single place that defines what 'assigning a scenario to a
    slot' means - used by generation, the competency-driven injector, and
    manual fine-tuning alike (previously duplicated three times)."""
    phase = int(scenario["PHASES"])
    target_df.loc[row_index, "EVENT"] = scenario["EVENT"]
    target_df.loc[row_index, "DOD"] = scenario["DOD"]
    target_df.loc[row_index, "PHASES"] = phase
    target_df.loc[row_index, "PHASE_NAME"] = PHASE_NAMES[phase]
    target_df.loc[row_index, "TEM_THREAT"] = scenario.get("TEM_THREAT", "")
    target_df.loc[row_index, "TEM_ERROR"] = scenario.get("TEM_ERROR", "")
    target_df.loc[row_index, "ROLE"] = role
    target_df.loc[row_index, "MATCH_TYPE"] = match_type
    target_df.loc[row_index, "DURATION"] = scenario.get("DURATION", 15)
    target_df.loc[row_index, "ATA"] = scenario.get("ATA")

    for competency_key in COMPETENCY_KEYS:
        if competency_key in scenario:
            target_df.loc[row_index, competency_key] = scenario[competency_key]


# ==========================================
# SECTION 7: SCENARIO-BUILDING / SLOT-FILLING ALGORITHM
# ==========================================
def _filter_candidates(df: pd.DataFrame, phase: int, dod: int, slot_type: str, ata: Optional[int], used_titles: set[str]) -> pd.DataFrame:
    candidates = df[(df["PHASES"] == phase) & (df["DOD"] == dod) & (~df["EVENT"].isin(used_titles))].copy()

    if slot_type == "Technical Failure":
        candidates = candidates[candidates["ATA"].notna()]
    elif slot_type == "Non-Technical / CRM":
        candidates = candidates[candidates["ATA"].isna()]
    elif slot_type == "ATA Specific" and ata:
        candidates = candidates[candidates["ATA"] == float(ata)]

    return candidates


def build_session(
    df: pd.DataFrame,
    slot_configurations: list[dict],
    allow_fallback: bool,
    recent_used_events: set[str],
) -> tuple[Optional[pd.DataFrame], list[str], list[str]]:
    """Attempts to fill every requested slot with a scenario. Returns
    (session_df, missing_slot_messages, fallback_warning_messages).
    session_df is None if any slot couldn't be filled."""
    used_event_titles: set[str] = set()
    missing_slots: list[str] = []
    fallback_warnings: list[str] = []

    session_df = pd.DataFrame({"SLOT": [cfg["slot"] for cfg in slot_configurations]})

    for row_index, cfg in enumerate(slot_configurations):
        slot_num, phase, dod = cfg["slot"], int(cfg["phase"]), int(cfg["dod"])
        role, slot_type, ata = cfg["role"], cfg["type"], cfg["ata"]

        candidates = _filter_candidates(df, phase, dod, slot_type, ata, used_event_titles)

        fresh_candidates = candidates[~candidates["EVENT"].isin(recent_used_events)]
        if not fresh_candidates.empty:
            candidates = fresh_candidates

        if not candidates.empty:
            picked = candidates.sample(n=1).iloc[0].to_dict()
            apply_scenario_to_slot(session_df, row_index, picked, role, "Exact")
            used_event_titles.add(picked["EVENT"])
            continue

        if not allow_fallback:
            missing_slots.append(f"Slot #{slot_num}: Phase {phase} with DOD {dod}")
            continue

        phase_candidates = df[(df["PHASES"] == phase) & (~df["EVENT"].isin(used_event_titles))].copy()
        if phase_candidates.empty:
            missing_slots.append(f"Slot #{slot_num}: No events exist in Phase {phase}")
            continue

        phase_candidates["dod_diff"] = (phase_candidates["DOD"] - dod).abs()
        picked = phase_candidates.sort_values("dod_diff").iloc[0].to_dict()
        apply_scenario_to_slot(session_df, row_index, picked, role, f"Fallback (DOD {picked['DOD']})")
        used_event_titles.add(picked["EVENT"])
        fallback_warnings.append(
            f"Slot #{slot_num} (Phase {phase}): target DOD {dod} missing - substituted DOD {picked['DOD']} ('{picked['EVENT']}')"
        )

    if missing_slots:
        return None, missing_slots, fallback_warnings

    session_df = session_df.sort_values("SLOT").reset_index(drop=True)
    return session_df, missing_slots, fallback_warnings


# ==========================================
# SECTION 8: PDF BRIEFING EXPORT
# ==========================================
ACCENT = colors.HexColor("#0284C7")
HEADER_FILL = colors.HexColor("#F0F4F8")
ROW_BORDER = colors.HexColor("#CCCCCC")
NOTES_FILL = colors.HexColor("#EAEAEA")
NOTES_BORDER = colors.HexColor("#999999")

SCHEDULE_COL_WIDTHS = [22, 90, 52, 175, 22, 120, 83]
COMPETENCY_COL_WIDTHS = [40, 364, 60]
NOTES_COL_WIDTHS = [130, 264, 100]

EVALUATION_RUBRIC_ROWS = [
    ("Pre-flight / departure", "SOP compliance, briefings, workload management"),
    ("In-flight / abnormal handling", "Systems knowledge, ECAM/QRH, CRM"),
    ("Approach & landing", "Flight path management, go-around decision"),
]


def _build_pdf_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("DocTitle", parent=base["Heading1"], fontSize=12, leading=14, textColor=ACCENT),
        "subtitle": ParagraphStyle("DocSubTitle", parent=base["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#555555")),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=7.0, leading=9.0),
        "cell_bold": ParagraphStyle("CellB", parent=base["Normal"], fontSize=7.0, leading=9.0, fontName="Helvetica-Bold"),
    }


def _schedule_table(df_session: pd.DataFrame, styles: dict) -> Table:
    header = [
        Paragraph("<b>Slot</b>", styles["cell_bold"]), Paragraph("<b>Phase</b>", styles["cell_bold"]),
        Paragraph("<b>Role</b>", styles["cell_bold"]), Paragraph("<b>Event / scenario title</b>", styles["cell_bold"]),
        Paragraph("<b>DOD</b>", styles["cell_bold"]), Paragraph("<b>Threat & error focus</b>", styles["cell_bold"]),
        Paragraph("<b>Flagged EBT</b>", styles["cell_bold"]),
    ]
    rows = [header]

    for _, row in df_session.iterrows():
        active_competencies = [
            col for col in COMPETENCY_KEYS if col in row and pd.notna(row[col]) and float(row[col]) >= 1.0
        ]
        competencies_str = ", ".join(active_competencies) if active_competencies else "Standard"
        tem_str = f"T: {row.get('TEM_THREAT', 'Standard')}<br/>E: {row.get('TEM_ERROR', 'General')}"

        rows.append(
            [
                Paragraph(str(row["SLOT"]), styles["cell"]), Paragraph(str(row["PHASE_NAME"]), styles["cell"]),
                Paragraph(str(row.get("ROLE", "PF Focus")), styles["cell_bold"]), Paragraph(str(row["EVENT"]), styles["cell"]),
                Paragraph(str(row["DOD"]), styles["cell"]), Paragraph(tem_str, styles["cell"]),
                Paragraph(competencies_str, styles["cell"]),
            ]
        )

    table = Table(rows, colWidths=SCHEDULE_COL_WIDTHS)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
                ("TEXTCOLOR", (0, 0), (-1, 0), ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("GRID", (0, 0), (-1, -1), 0.5, ROW_BORDER),
            ]
        )
    )
    return table


def _competency_table(comp_scores: dict, styles: dict):
    scored = {code: score for code, score in comp_scores.items() if score > 0}
    if not scored:
        return None

    rows = [[Paragraph("<b>Code</b>", styles["cell_bold"]), Paragraph("<b>Competency name</b>", styles["cell_bold"]), Paragraph("<b>Score</b>", styles["cell_bold"])]]
    for code, score in sorted(scored.items(), key=lambda item: item[1], reverse=True):
        rows.append([Paragraph(code, styles["cell_bold"]), Paragraph(COMPETENCY_KEYS.get(code, code), styles["cell"]), Paragraph(str(int(score)), styles["cell_bold"])])

    table = Table(rows, colWidths=COMPETENCY_COL_WIDTHS)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NOTES_FILL),
                ("GRID", (0, 0), (-1, -1), 0.5, NOTES_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _evaluation_rubric_table(styles: dict) -> Table:
    rows = [[Paragraph("<b>Flight phase / event</b>", styles["cell_bold"]), Paragraph("<b>Competency / TEM focus</b>", styles["cell_bold"]), Paragraph("<b>Grade / signature</b>", styles["cell_bold"])]]
    for phase_label, focus_label in EVALUATION_RUBRIC_ROWS:
        rows.append([Paragraph(phase_label, styles["cell"]), Paragraph(focus_label, styles["cell"]), Paragraph("", styles["cell"])])

    table = Table(rows, colWidths=NOTES_COL_WIDTHS)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NOTES_FILL),
                ("GRID", (0, 0), (-1, -1), 0.5, NOTES_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    return table


def generate_pdf_briefing(
    df_session: pd.DataFrame, total_dod: int, max_dod: int, comp_scores: dict,
    mode: str, captain: str, first_officer: str, sim_id: str, ios_info: str,
) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = _build_pdf_styles()

    elements = [
        Paragraph(f"A320 SIMULATOR BRIEFING & IOS SETUP SHEET - {mode.upper()}", styles["title"]),
        Paragraph(
            f"<b>Crew:</b> {captain} (CPT) &amp; {first_officer} (FO) &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Device:</b> {sim_id} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Total DOD:</b> {total_dod}/{max_dod}",
            styles["subtitle"],
        ),
        Paragraph(f"<b>IOS setup config:</b> <i>{ios_info}</i>", styles["subtitle"]),
        Spacer(1, 3),
        HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=5),
        _schedule_table(df_session, styles),
        Spacer(1, 5),
    ]

    competency_table = _competency_table(comp_scores, styles)
    if competency_table is not None:
        elements += [
            Paragraph("<b>EBT COMPETENCY INTENSITY SCORECARD:</b>", styles["cell_bold"]),
            Spacer(1, 2),
            competency_table,
            Spacer(1, 5),
        ]

    elements += [
        Paragraph("<b>INSTRUCTOR NOTES & CREW EVALUATION RUBRIC:</b>", styles["cell_bold"]),
        Spacer(1, 2),
        _evaluation_rubric_table(styles),
    ]

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ==========================================
# SECTION 9: PAGE LAYOUT
# ==========================================
st.set_page_config(page_title=APP_TITLE, page_icon="\u2708\ufe0f", layout="wide")
inject_css()

st.title(f"\u2708\ufe0f {APP_TITLE}")
st.markdown(f"<p style='color: #94A3B8; font-size: 14px; margin-top: -8px; font-weight: 500;'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)

tab_session, tab_ios, tab_weather = st.tabs(["Session & crew setup", "Aircraft & airport parameters", "Environment & weather IOS panel"])

with tab_session:
    with st.container(border=True):
        st.markdown("#### Session metadata & device setup")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        session_mode = m_col1.selectbox("Training focus / mode", SESSION_MODE_OPTIONS)
        capt_name = m_col2.text_input("Captain name", value="Capt. Unassigned")
        fo_name = m_col3.text_input("First officer name", value="F/O Unassigned")
        sim_id = m_col4.text_input("Sim / device ID", value="KM Malta A320 STD2.2")

        p_col1, p_col2 = st.columns([1.5, 3.5])
        max_dod_threshold = p_col1.number_input("Total DOD ceiling", min_value=1, max_value=30, value=6, step=1)
        with p_col2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            allow_fallback = st.checkbox("Enable smart fallback (use closest available DOD if exact match missing)", value=True)

with tab_ios:
    with st.container(border=True):
        st.markdown("#### Aircraft mass & balance (IOS parameters)")
        i_col1, i_col2, i_col3, i_col4, i_col5 = st.columns(5)
        with i_col1:
            gw_val = st.number_input("GW (kg x1000)", min_value=40.0, max_value=79.0, value=54.6, step=0.5)
            gw_cg = st.number_input("GW CG (%)", min_value=15.0, max_value=40.0, value=29.0, step=0.1)
        with i_col2:
            zfw_val = st.number_input("ZFW (kg x1000)", min_value=35.0, max_value=64.3, value=47.0, step=0.5)
            zfw_cg = st.number_input("ZFW CG (%)", min_value=15.0, max_value=40.0, value=31.0, step=0.1)
        with i_col3:
            total_fuel = st.number_input("Total fuel (kg x1000)", min_value=1.5, max_value=19.0, value=7.6, step=0.1)
        with i_col4:
            alt_asl = st.number_input("Init alt (ft ASL)", min_value=0, max_value=39000, value=293)
        with i_col5:
            qnh_val = st.number_input("QNH (hPa)", min_value=950, max_value=1050, value=1013)

    with st.container(border=True):
        st.markdown("#### Major European airport selection & Jeppesen layout")
        sel_apt_key = st.selectbox("Select European aerodrome", options=list(EUROPEAN_AIRPORTS.keys()))
        apt_data = EUROPEAN_AIRPORTS[sel_apt_key]

        ac1, ac2 = st.columns(2)
        with ac1:
            apt_ref = st.text_input("Reference airport / active rwy", value=f"{apt_data['icao']} / {apt_data['rwy'][0]}")
            ils_ident = st.text_input("ILS ident / freq", value=apt_data["ils"])
        with ac2:
            loc_course = st.number_input("Loc course (\u00b0M)", min_value=0, max_value=360, value=241)
            apt_elev = st.number_input("Airport elev (ft)", min_value=-100, max_value=14000, value=apt_data["elev"])

        st.markdown(
            f"""
            <div class="jepp-card">
                <div class="jepp-header">JEPPESEN SCHEMATIC LAYOUT & BRIEFING - {sel_apt_key.upper()}</div>
                <b>ICAO:</b> {apt_data['icao']} &nbsp;&nbsp;|&nbsp;&nbsp; <b>ELEV:</b> {apt_data['elev']} FT &nbsp;&nbsp;|&nbsp;&nbsp; <b>ILS / LOC:</b> {apt_data['ils']}<br/>
                <b>PUBLISHED RUNWAYS:</b> {' | '.join(apt_data['rwy'])}<br/>
                <b>SCHEMATIC ALIGNMENT:</b> [RWY {apt_data['rwy'][0]}] &lt;==============================&gt; [ILS GLIDESLOPE 3.0&deg;]
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_weather:
    st.markdown("#### IOS current conditions & live METAR integration")

    live_metar_str = fetch_live_metar(apt_data["icao"])
    st.markdown(
        f"""
        <div class="ios-card" style="border-left: 3px solid #38BDF8;">
            <div class="ios-label">Live METAR feed ({apt_data['icao']})</div>
            <div style="font-family: monospace; color: #38BDF8; font-size: 13px; margin-top: 4px;">{live_metar_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    w_card1, w_card2 = st.columns(2)
    with w_card1:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>Surface wind & atmosphere</b>", unsafe_allow_html=True)
            wc1, wc2, wc3 = st.columns(3)
            wind_dir = wc1.number_input("Wind dir (\u00b0M)", min_value=0, max_value=360, value=360, step=10)
            wind_spd = wc2.number_input("Wind speed (kt)", min_value=0, max_value=70, value=0)
            wind_gust = wc3.number_input("Wind gust (kt)", min_value=0, max_value=90, value=0)
            wind_str = f"{wind_dir:03d}\u00b0M / {wind_spd} kt" + (f" G {wind_gust} kt" if wind_gust > 0 else "")

            tc1, tc2, tc3 = st.columns(3)
            oat_temp = tc1.number_input("Aircraft OAT (\u00b0C)", min_value=-40, max_value=50, value=14)
            isa_standard = 15 - (2 * (apt_elev / 1000))
            isa_dev_calc = int(oat_temp - isa_standard)
            isa_dev = tc2.number_input("ISA dev (\u00b0C)", min_value=-30, max_value=30, value=isa_dev_calc)
            qnh_weather = tc3.number_input("QNH ref (hPa)", min_value=950, max_value=1050, value=1013)

    with w_card2:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>Runway surface & visibility parameters</b>", unsafe_allow_html=True)
            rc1, rc2 = st.columns(2)
            rcam_code = rc1.selectbox("Runway cnd ref (RCAM x/x/x)", RCAM_OPTIONS)
            precip_ref = rc2.selectbox("Precipitation ref", PRECIP_OPTIONS)

            vc1, vc2 = st.columns(2)
            vis_rvr_str = vc1.selectbox("Visibility / RVR", VISIBILITY_OPTIONS, index=0)
            rwy_lighting = vc2.selectbox("Runway lighting", RUNWAY_LIGHTING_OPTIONS, index=3)

    w_card3, w_card4 = st.columns(2)
    with w_card3:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>Clouds & ceiling reference</b>", unsafe_allow_html=True)
            cc1, cc2 = st.columns(2)
            cloud_coverage = cc1.selectbox("Clouds coverage", CLOUD_COVERAGE_OPTIONS)
            cloud_base = cc2.number_input("Cloud base (ft AGL)", min_value=0, max_value=20000, value=1500 if cloud_coverage != "Clear" else 5000, step=100)

    with w_card4:
        with st.container(border=True):
            st.markdown("<b style='color:#38BDF8;'>Atmospheric hazards & turbulence</b>", unsafe_allow_html=True)
            hc1, hc2, hc3 = st.columns(3)
            windshear_opt = hc1.selectbox("Windshears / microburst", WINDSHEAR_OPTIONS)
            turb_opt = hc2.selectbox("Turbulence at aircraft", TURBULENCE_OPTIONS)
            icing_opt = hc3.selectbox("Icing conditions", ICING_OPTIONS)

    rcam_short = rcam_code.split("-")[0].strip()
    ios_env_summary_str = (
        f"Wind: {wind_str} | OAT: {oat_temp}\u00b0C (ISA {isa_dev:+d}\u00b0C) | QNH: {qnh_weather} hPa | "
        f"Rwy cnd: {rcam_short} | Precip: {precip_ref} | Vis: {vis_rvr_str} | "
        f"Clouds: {cloud_coverage} @ {cloud_base}ft | Rwy lt: {rwy_lighting}"
    )

    st.markdown("<div class='ios-card'>", unsafe_allow_html=True)
    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)
    p_col1.markdown(f"<div class='ios-label'>Wind</div><div class='ios-value'>{wind_str}</div>", unsafe_allow_html=True)
    p_col2.markdown(f"<div class='ios-label'>OAT / ISA</div><div class='ios-value'>{oat_temp}\u00b0C / {isa_dev:+d}\u00b0C</div>", unsafe_allow_html=True)
    p_col3.markdown(f"<div class='ios-label'>RCAM code</div><div class='ios-value'>{rcam_short}</div>", unsafe_allow_html=True)
    p_col4.markdown(f"<div class='ios-label'>Visibility</div><div class='ios-value'>{vis_rvr_str.split(' ')[0]}</div>", unsafe_allow_html=True)
    p_col5.markdown(f"<div class='ios-label'>Precipitation</div><div class='ios-value'>{precip_ref}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

ios_summary_str = f"Apt: {apt_ref} | GW: {gw_val}t (CG {gw_cg}%) | ZFW: {zfw_val}t | Fuel: {total_fuel}t | QNH: {qnh_val}hPa | Env: {ios_env_summary_str}"

# --- Sidebar: slot configuration ---
slot_configurations = render_sidebar_slots(max_dod_threshold)
st.sidebar.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div style='text-align: center; font-size: 11px; color: #94A3B8;'>Designed by {APP_AUTHOR} \u00b7 {APP_VERSION}</div>", unsafe_allow_html=True)

# --- Scenario database ---
scenarios_path = resource_path(SCENARIOS_FILENAME)
competency_path = resource_path(COMPETENCY_FILENAME)

if not os.path.exists(scenarios_path):
    st.error(f"Could not find `{SCENARIOS_FILENAME}` in path `{resource_path('')}`.")
    st.stop()

df, comp_loaded_or_error = load_scenario_database(scenarios_path, competency_path)

if df is None:
    st.error(f"Error reading matrix file: {comp_loaded_or_error}")
    st.stop()

comp_loaded = bool(comp_loaded_or_error)
df["TEM_THREAT"], df["TEM_ERROR"] = zip(
    *df.apply(lambda r: derive_tem_tags(r["EVENT"], r["PHASES"], wind_spd, wind_gust, rcam_code, vis_rvr_str), axis=1)
)

st.success("Matrix loaded." + (" (Keypams competency matrix active)" if comp_loaded else ""))

with st.expander("View parsed internal scenario matrix (sorted by phase)", expanded=False):
    active_comp_cols = [k for k in COMPETENCY_KEYS if k in df.columns]
    disp_cols = ["scenario_id", "PHASES", "DOD", "EVENT", "TEM_THREAT", "TEM_ERROR"] + active_comp_cols

    matrix_display_df = df[disp_cols].sort_values(by=["PHASES", "DOD", "EVENT"]).reset_index(drop=True)
    for col in active_comp_cols:
        matrix_display_df[col] = matrix_display_df[col].astype(int)

    st.dataframe(
        matrix_display_df,
        use_container_width=True,
        column_config={
            "scenario_id": st.column_config.TextColumn("ID", width="small"),
            "PHASES": st.column_config.NumberColumn("Phase", format="Phase %d"),
            "DOD": st.column_config.NumberColumn("DOD", format="DOD %d"),
            "EVENT": st.column_config.TextColumn("Scenario / event title", width="large"),
            "TEM_THREAT": st.column_config.TextColumn("Threat focus", width="medium"),
            "TEM_ERROR": st.column_config.TextColumn("Error focus", width="medium"),
        },
        hide_index=True,
    )

with st.expander("Reverse competency-driven scenario finder & injector", expanded=False):
    c_f1, c_f2 = st.columns([2.2, 1])
    target_comp = c_f1.selectbox("Target EBT competency focus:", options=list(COMPETENCY_KEYS.keys()), format_func=lambda k: f"{k} - {COMPETENCY_KEYS[k]}")
    min_comp_score = c_f2.slider("Min intensity", min_value=1.0, max_value=3.0, value=1.0, step=0.5)

    comp_candidates = df[df[target_comp] >= min_comp_score].copy()

    if comp_candidates.empty:
        st.warning(f"No scenarios found targeting **{target_comp}** >= {min_comp_score}.")
    else:
        chosen_comp_scen_id = st.selectbox(
            f"Matching scenarios ({len(comp_candidates)} found):",
            options=comp_candidates["scenario_id"].tolist(),
            format_func=lambda sid: (
                f"[{target_comp} score: {comp_candidates.loc[comp_candidates['scenario_id'] == sid, target_comp].iloc[0]}] "
                f"Phase {comp_candidates.loc[comp_candidates['scenario_id'] == sid, 'PHASES'].iloc[0]} | "
                f"DOD {comp_candidates.loc[comp_candidates['scenario_id'] == sid, 'DOD'].iloc[0]} - "
                f"{comp_candidates.loc[comp_candidates['scenario_id'] == sid, 'EVENT'].iloc[0]}"
            ),
        )

        if "final_df" in st.session_state:
            c_inj1, c_inj2 = st.columns([2, 1])
            target_slot_to_replace = c_inj1.selectbox(
                "Inject into slot:",
                options=range(len(st.session_state.final_df)),
                format_func=lambda i: f"Slot #{st.session_state.final_df.loc[i, 'SLOT']} - current: {st.session_state.final_df.loc[i, 'EVENT'][:25]}...",
            )
            with c_inj2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("Inject into slot", type="primary"):
                    picked_row = comp_candidates[comp_candidates["scenario_id"] == chosen_comp_scen_id].iloc[0].to_dict()
                    slot_num_val = int(st.session_state.final_df.loc[target_slot_to_replace, "SLOT"])
                    current_role = st.session_state.final_df.loc[target_slot_to_replace, "ROLE"]

                    apply_scenario_to_slot(st.session_state.final_df, target_slot_to_replace, picked_row, current_role, f"Competency ({target_comp})")

                    st.success(f"Slot #{slot_num_val} updated.")
                    st.rerun()

# --- Generate session ---
if st.button("Generate simulator profile", type="primary"):
    recent_used_set = get_recent_used_events()
    session_df, missing_slots, fallback_warnings = build_session(df, slot_configurations, allow_fallback, recent_used_set)

    if missing_slots:
        st.error(f"Could not fulfill profile! Issues found in: {', '.join(missing_slots)}.")
    else:
        st.session_state.final_df = session_df
        save_session_to_history(session_df, session_mode, capt_name, fo_name)

        for warning in fallback_warnings:
            st.warning(warning)
        st.success("Session profile generated successfully.")

if "final_df" in st.session_state:
    final_df = st.session_state.final_df
    total_dod = final_df["DOD"].sum()
    total_time = final_df["DURATION"].sum()

    if total_dod > max_dod_threshold:
        st.warning(f"Generated total DOD ({total_dod}) exceeds session ceiling ({max_dod_threshold}).")

    with st.container(border=True):
        st.markdown("#### Fine-tune session / override slots")

        ft_col1, ft_col2, ft_col3 = st.columns([1, 1, 1.8])
        override_slot_idx = ft_col1.selectbox(
            "Select slot to modify:",
            options=range(len(final_df)),
            format_func=lambda i: f"Slot #{final_df.loc[i, 'SLOT']} - Phase {final_df.loc[i, 'PHASES']} | {final_df.loc[i, 'EVENT'][:18]}...",
        )

        curr_row = final_df.loc[override_slot_idx]
        slot_num_to_modify = int(curr_row["SLOT"])
        curr_phase = int(curr_row["PHASES"])

        new_role_val = ft_col2.selectbox("Update role focus:", options=ROLE_OPTIONS, index=ROLE_OPTIONS.index(curr_row.get("ROLE", "PF Focus")))

        phase_filtered_df = df[df["PHASES"] == curr_phase].drop_duplicates(subset=["EVENT"]).reset_index(drop=True)

        with ft_col3:
            if phase_filtered_df.empty:
                st.warning(f"No scenarios found for Phase {curr_phase}.")
            else:
                new_event_title = st.selectbox(
                    f"Choose replacement event (Phase {curr_phase}):",
                    options=phase_filtered_df["EVENT"].tolist(),
                    format_func=lambda ev: f"[DOD {phase_filtered_df.loc[phase_filtered_df['EVENT'] == ev, 'DOD'].iloc[0]}] {ev}",
                )

        if not phase_filtered_df.empty and st.button("Apply event & role update to slot", type="primary"):
            match_row = phase_filtered_df[phase_filtered_df["EVENT"] == new_event_title].iloc[0].to_dict()
            apply_scenario_to_slot(final_df, override_slot_idx, match_row, new_role_val, "Phase-filtered override")
            st.session_state.final_df = final_df
            st.success(f"Slot #{slot_num_to_modify} updated.")
            st.rerun()

    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selected events", len(final_df))
    m2.metric("Total DOD score", f"{total_dod} / {max_dod_threshold}")
    m3.metric("Est. session time", f"{total_time} mins")
    m4.metric("DOD buffer remaining", max_dod_threshold - total_dod)

    comp_scores = {
        key: float(pd.to_numeric(final_df[key], errors="coerce").fillna(0).sum()) if key in final_df.columns else 0.0
        for key in COMPETENCY_KEYS
    }

    if any(score > 0 for score in comp_scores.values()):
        with st.container(border=True):
            st.markdown("#### EBT competency intensity scorecard")
            chart_df = (
                pd.DataFrame(list(comp_scores.items()), columns=["Competency", "Score"])
                .query("Score > 0")
                .sort_values("Score", ascending=True)
                .set_index("Competency")
            )
            st.bar_chart(chart_df, height=220, use_container_width=True, horizontal=True)

    st.markdown("#### Sequenced simulator session")
    st.dataframe(final_df[["SLOT", "PHASE_NAME", "ROLE", "EVENT", "DOD", "TEM_THREAT", "TEM_ERROR", "MATCH_TYPE"]], use_container_width=True)

    col_exp1, col_exp2, col_exp3 = st.columns(3)
    with col_exp1:
        st.download_button(
            label="Download session schedule (CSV)",
            data=final_df.to_csv(index=False),
            file_name=f"sim_session_DOD_{max_dod_threshold}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_exp2:
        pdf_data = generate_pdf_briefing(final_df, total_dod, max_dod_threshold, comp_scores, session_mode, capt_name, fo_name, sim_id, ios_summary_str)
        st.download_button(
            label="Download printable PDF briefing",
            data=pdf_data,
            file_name=f"sim_briefing_DOD_{max_dod_threshold}.pdf",
            mime="application/pdf",
            use_container_width=True,
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
            "schedule": final_df[["SLOT", "PHASES", "ROLE", "EVENT", "DOD", "TEM_THREAT", "TEM_ERROR"]].to_dict(orient="records"),
        }
        st.download_button(
            label="Export LMS payload (MINT / JSON)",
            data=json.dumps(lms_payload, indent=2),
            file_name=f"lms_payload_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
        )
