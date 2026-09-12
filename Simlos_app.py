# ==========================================
# DEPLOYMENT FILE: simlos_app.py (GitHub / Streamlit Cloud entry point)
# ==========================================
import streamlit as st
import pandas as pd
import io
import re
import os
import sys
import math
import sqlite3
import difflib
import urllib.request
from datetime import datetime, timezone

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# ReportLab imports for PDF briefing generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# HISTORICAL DATA STORE — CANDIDATE SESSION HISTORY
# ==========================================
DB_PATH = os.environ.get("EBT_HISTORY_DB_PATH", "ebt_session_history.db")

_PK_COLUMNS = {
    "candidates": "candidate_id",
    "training_sessions": "session_id",
    "session_slots": "slot_id",
    "slot_competency_grades": "id",
}

class _PGCompatCursor:
    def __init__(self, raw_cursor, lastrowid=None):
        self._cur = raw_cursor
        self.lastrowid = lastrowid
    def fetchone(self): return self._cur.fetchone()
    def fetchall(self): return self._cur.fetchall()

class _PGCompatConnection:
    def __init__(self, raw_conn):
        self._conn = raw_conn
    def execute(self, sql, params=()):
        pg_sql = sql.replace("?", "%s")
        returning_col = None
        if sql.strip().upper().startswith("INSERT INTO"):
            table = sql.split(None, 3)[2]
            returning_col = _PK_COLUMNS.get(table)
            if returning_col and "RETURNING" not in pg_sql.upper():
                pg_sql = pg_sql.rstrip().rstrip(";") + f" RETURNING {returning_col}"
        cur = self._conn.cursor()
        cur.execute(pg_sql, params)
        lastrowid = None
        if returning_col:
            row = cur.fetchone()
            lastrowid = row[0] if row else None
        return _PGCompatCursor(cur, lastrowid)
    def executescript(self, script):
        cur = self._conn.cursor()
        cur.execute(script)
    def commit(self): self._conn.commit()
    def close(self): self._conn.close()

def _get_supabase_db_url():
    try:
        if "SUPABASE_DB_URL" in st.secrets:
            return st.secrets["SUPABASE_DB_URL"]
    except Exception:
        pass
    return os.environ.get("SUPABASE_DB_URL")

def using_postgres():
    return HAS_PSYCOPG2 and bool(_get_supabase_db_url())

def get_db_connection():
    db_url = _get_supabase_db_url()
    if db_url:
        if not HAS_PSYCOPG2:
            raise RuntimeError("psycopg2 package isn't installed")
        raw = psycopg2.connect(db_url)
        return _PGCompatConnection(raw)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

_SQLITE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_number TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS training_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sim_id TEXT,
        session_mode TEXT,
        captain_candidate_id INTEGER REFERENCES candidates(candidate_id),
        fo_candidate_id INTEGER REFERENCES candidates(candidate_id),
        total_dod INTEGER,
        max_dod_threshold INTEGER,
        source_workflow TEXT NOT NULL DEFAULT 'session_setup',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS session_slots (
        slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES training_sessions(session_id) ON DELETE CASCADE,
        slot_number INTEGER NOT NULL,
        event_title TEXT NOT NULL,
        phase_number INTEGER,
        dod INTEGER,
        role_focus TEXT,
        instructor_grade INTEGER,
        instructor_notes TEXT
    );
    CREATE TABLE IF NOT EXISTS slot_competency_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_id INTEGER NOT NULL REFERENCES session_slots(slot_id) ON DELETE CASCADE,
        competency_code TEXT NOT NULL,
        grade INTEGER,
        observed INTEGER NOT NULL DEFAULT 1,
        note TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_capt ON training_sessions(captain_candidate_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_fo ON training_sessions(fo_candidate_id);
    CREATE INDEX IF NOT EXISTS idx_slots_session ON session_slots(session_id);
    CREATE INDEX IF NOT EXISTS idx_comp_grades_slot ON slot_competency_grades(slot_id);
"""

_POSTGRES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id SERIAL PRIMARY KEY,
        staff_number TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS training_sessions (
        session_id SERIAL PRIMARY KEY,
        sim_id TEXT,
        session_mode TEXT,
        captain_candidate_id INTEGER REFERENCES candidates(candidate_id),
        fo_candidate_id INTEGER REFERENCES candidates(candidate_id),
        total_dod INTEGER,
        max_dod_threshold INTEGER,
        source_workflow TEXT NOT NULL DEFAULT 'session_setup',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS session_slots (
        slot_id SERIAL PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES training_sessions(session_id) ON DELETE CASCADE,
        slot_number INTEGER NOT NULL,
        event_title TEXT NOT NULL,
        phase_number INTEGER,
        dod INTEGER,
        role_focus TEXT,
        instructor_grade INTEGER,
        instructor_notes TEXT
    );
    CREATE TABLE IF NOT EXISTS slot_competency_grades (
        id SERIAL PRIMARY KEY,
        slot_id INTEGER NOT NULL REFERENCES session_slots(slot_id) ON DELETE CASCADE,
        competency_code TEXT NOT NULL,
        grade INTEGER,
        observed INTEGER NOT NULL DEFAULT 1,
        note TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_capt ON training_sessions(captain_candidate_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_fo ON training_sessions(fo_candidate_id);
    CREATE INDEX IF NOT EXISTS idx_slots_session ON session_slots(session_id);
    CREATE INDEX IF NOT EXISTS idx_comp_grades_slot ON slot_competency_grades(slot_id);
"""

def init_db():
    conn = get_db_connection()
    conn.executescript(_POSTGRES_SCHEMA if using_postgres() else _SQLITE_SCHEMA)
    conn.commit()
    conn.close()

def get_or_create_candidate(conn, staff_number, full_name):
    staff_number = (staff_number or "").strip()
    full_name = (full_name or "").strip()
    if not staff_number: return None
    cur = conn.execute("SELECT candidate_id, full_name FROM candidates WHERE staff_number = ?", (staff_number,))
    row = cur.fetchone()
    if row:
        candidate_id, stored_name = row
        if full_name and full_name != stored_name:
            conn.execute("UPDATE candidates SET full_name = ? WHERE candidate_id = ?", (full_name, candidate_id))
        return candidate_id
    cur = conn.execute("INSERT INTO candidates (staff_number, full_name) VALUES (?, ?)", (staff_number, full_name or staff_number))
    return cur.lastrowid

def save_session_to_history(existing_session_id, sim_id, session_mode, capt_staff_no, capt_name,
                             fo_staff_no, fo_name, total_dod, max_dod_threshold, source_workflow, slots):
    conn = get_db_connection()
    try:
        capt_id = get_or_create_candidate(conn, capt_staff_no, capt_name)
        fo_id = get_or_create_candidate(conn, fo_staff_no, fo_name)
        if existing_session_id:
            conn.execute(
                """UPDATE training_sessions SET sim_id=?, session_mode=?, captain_candidate_id=?, fo_candidate_id=?,
                   total_dod=?, max_dod_threshold=?, updated_at=? WHERE session_id=?""",
                (sim_id, session_mode, capt_id, fo_id, total_dod, max_dod_threshold, datetime.now(timezone.utc).isoformat(), existing_session_id)
            )
            session_id = existing_session_id
            conn.execute("DELETE FROM session_slots WHERE session_id = ?", (session_id,))
        else:
            cur = conn.execute(
                """INSERT INTO training_sessions (sim_id, session_mode, captain_candidate_id, fo_candidate_id,
                   total_dod, max_dod_threshold, source_workflow) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sim_id, session_mode, capt_id, fo_id, total_dod, max_dod_threshold, source_workflow)
            )
            session_id = cur.lastrowid
        for slot in slots:
            cur = conn.execute(
                """INSERT INTO session_slots (session_id, slot_number, event_title, phase_number, dod,
                   role_focus, instructor_grade, instructor_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, slot["slot_number"], slot["event_title"], slot.get("phase_number"),
                 slot.get("dod"), slot.get("role_focus"), slot.get("instructor_grade"), slot.get("instructor_notes"))
            )
            slot_id = cur.lastrowid
            for comp in slot.get("competencies", []):
                conn.execute(
                    """INSERT INTO slot_competency_grades (slot_id, competency_code, grade, observed, note)
                       VALUES (?, ?, ?, ?, ?)""",
                    (slot_id, comp["code"], comp.get("grade"), int(comp.get("observed", True)), comp.get("note", ""))
                )
        conn.commit()
        return session_id, (capt_id is not None or fo_id is not None)
    finally:
        conn.close()

def get_candidate_history(staff_number):
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT candidate_id, full_name FROM candidates WHERE staff_number = ?", (staff_number.strip(),))
        row = cur.fetchone()
        if not row: return None, None
        candidate_id, full_name = row
        sessions = conn.execute(
            """SELECT ts.session_id, ts.created_at, ts.sim_id, ts.session_mode, ts.source_workflow,
                      CASE WHEN ts.captain_candidate_id = ? THEN 'Captain' ELSE 'First Officer' END AS seat
               FROM training_sessions ts
               WHERE ts.captain_candidate_id = ? OR ts.fo_candidate_id = ?
               ORDER BY ts.created_at DESC""",
            (candidate_id, candidate_id, candidate_id)
        ).fetchall()
        grades = conn.execute(
            """SELECT ts.session_id, ts.created_at, ss.event_title, ss.instructor_grade,
                      scg.competency_code, scg.grade, scg.observed, scg.note
               FROM training_sessions ts
               JOIN session_slots ss ON ss.session_id = ts.session_id
               LEFT JOIN slot_competency_grades scg ON scg.slot_id = ss.slot_id
               WHERE ts.captain_candidate_id = ? OR ts.fo_candidate_id = ?
               ORDER BY ts.created_at DESC""",
            (candidate_id, candidate_id)
        ).fetchall()
        return {"candidate_id": candidate_id, "full_name": full_name, "sessions": sessions}, grades
    finally:
        conn.close()

# ==========================================
# PAGE CONFIG & HYBRID THEME STYLING
# ==========================================
st.set_page_config(page_title="EBT Session Optimizer", page_icon="✈️", layout="wide")

init_db()

# --- NEW: ORCA State Persistence ---
if "orca_state" not in st.session_state:
    st.session_state.orca_state = {}

def update_orca_state(key, value_attr=None):
    """Callback to lock ORCA widget inputs into persistent state immediately."""
    if value_attr:
        st.session_state.orca_state[key] = st.session_state[value_attr]
    else:
        st.session_state.orca_state[key] = st.session_state[key]
# -----------------------------------

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if st.session_state.theme == "light":
    KM_BG = "#F8FAFC"
    KM_PANEL = "#FFFFFF"
    KM_PANEL_ALT = "#F1F5F9"
    KM_BORDER = "#E2E8F0"
    KM_TEXT = "#0F172A"
    KM_TEXT_MUTED = "#64748B"
    KM_AMBER = "#D97706"
    KM_AMBER_DIM = "rgba(217,119,6,0.15)"
    KM_GREEN = "#059669"
    KM_GRAY_DOT = "#94A3B8"
else:
    KM_BG = "#0B0E13"
    KM_PANEL = "#12161D"
    KM_PANEL_ALT = "#171C24"
    KM_BORDER = "rgba(255,255,255,0.08)"
    KM_TEXT = "#E8EAED"
    KM_TEXT_MUTED = "#8B94A3"
    KM_AMBER = "#F5A623"
    KM_AMBER_DIM = "rgba(245,166,35,0.15)"
    KM_GREEN = "#34D399"
    KM_GRAY_DOT = "#5B6472"

st.markdown(f"""
<style>
    @import url('https://cdn.jsdelivr.net/npm/@fontsource/geist-mono/index.css');

    :root {{
        --text-color: {KM_TEXT} !important;
        --background-color: {KM_BG} !important;
        --secondary-background-color: {KM_PANEL} !important;
        --primary-color: {KM_AMBER} !important;
        --font: 'Geist Mono', monospace !important;
    }}

    html, body, [class*="css"] {{
        font-family: 'Geist Mono', 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace !important;
        font-size: 14px !important;
    }}

    [data-testid="stHeader"] {{ display: none !important; }}
    [data-testid="stToolbar"] {{ visibility: hidden !important; }}
    
    /* OVERRIDE BOTH MAIN APP AND SIDEBAR TO FOLLOW TOGGLE STATE */
    .stApp, [data-testid="stAppViewContainer"] {{ 
        background-color: {KM_BG} !important; 
    }}
    
    [data-testid="stSidebar"] {{
        background-color: {KM_PANEL} !important;
        border-right: 1px solid {KM_BORDER} !important;
    }}

    /* Fix Streamlit native input widgets bleeding the dark config in light mode */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {{
        background-color: {KM_PANEL_ALT} !important;
        color: {KM_TEXT} !important;
        border: 1px solid {KM_BORDER} !important;
        opacity: 0.9;
    }}
    .stTextInput input::placeholder {{
        color: {KM_TEXT_MUTED} !important;
        opacity: 0.6;
    }}
    [data-testid="stCheckbox"] {{
        padding-top: 4px;
    }}

    .block-container {{
        padding-top: 0.8rem !important;
        padding-bottom: 1.0rem !important;
        max-width: 97% !important;
    }}
    
    p, li, span, label, div {{ color: {KM_TEXT}; }}

    h1, h2, h3, h4 {{ color: {KM_TEXT} !important; font-weight: 700 !important; margin-top: 6px !important; margin-bottom: 6px !important;}}

    .km-header {{
        display: flex; align-items: center; justify-content: space-between;
        background-color: {KM_PANEL}; border: 1px solid {KM_BORDER};
        border-radius: 12px; padding: 14px 22px; margin-bottom: 14px; flex-wrap: wrap; gap: 14px;
    }}
    .km-header-left {{ display: flex; align-items: center; gap: 14px; }}
    .km-logo {{
        width: 42px; height: 42px; border-radius: 10px; background: {KM_AMBER};
        display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0;
    }}
    .km-title {{ font-size: 16px; font-weight: 800; letter-spacing: 0.03em; color: {KM_TEXT}; line-height: 1.2; }}
    .km-subtitle {{ font-size: 11.5px; color: {KM_TEXT_MUTED}; font-weight: 500; margin-top: 1px; }}
    .km-header-right {{ display: flex; align-items: center; gap: 26px; flex-wrap: wrap; }}
    .km-meta {{ text-align: left; }}
    .km-meta-label {{ font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.08em; color: {KM_TEXT_MUTED}; font-weight: 700; }}
    .km-meta-value {{ font-size: 13px; font-weight: 700; color: {KM_TEXT}; }}
    .km-meta-value-accent {{ color: {KM_AMBER}; }}
    .km-pills {{ display: flex; gap: 8px; }}
    .km-pill {{
        display: flex; align-items: center; gap: 6px; background-color: {KM_PANEL_ALT};
        border: 1px solid {KM_BORDER}; border-radius: 20px; padding: 5px 11px;
        font-size: 10px; font-weight: 700; letter-spacing: 0.05em; color: {KM_TEXT_MUTED};
    }}
    .km-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
    .km-dot-green {{ background-color: {KM_GREEN}; }}
    .km-dot-amber {{ background-color: {KM_AMBER}; }}
    .km-dot-gray {{ background-color: {KM_GRAY_DOT}; }}

    div[data-testid="stMetric"], .ios-card {{
        background-color: {KM_PANEL} !important; border: 1px solid {KM_BORDER} !important;
        border-radius: 10px !important; padding: 12px 16px !important;
    }}
    div[data-testid="stMetricLabel"] * {{ color: {KM_TEXT_MUTED} !important; font-weight: 700 !important; text-transform: uppercase; font-size: 10.5px !important; letter-spacing: 0.05em; }}
    div[data-testid="stMetricValue"] * {{ color: {KM_TEXT} !important; font-weight: 800 !important; }}
    [data-testid="stVerticalBlockBorderWrapper"] > div {{ background-color: {KM_PANEL}; border-radius: 10px; }}
    div[data-testid="stExpander"] {{ background-color: {KM_PANEL} !important; border: 1px solid {KM_BORDER} !important; border-radius: 10px !important; }}

    .ios-label {{ font-size: 11px; color: {KM_TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; }}

    .panel-head {{ display: flex; align-items: center; gap: 9px; margin-bottom: 12px; }}
    .panel-code {{
        background-color: {KM_AMBER_DIM}; color: {KM_AMBER}; font-size: 10px; font-weight: 800;
        letter-spacing: 0.06em; padding: 3px 7px; border-radius: 5px; border: 1px solid rgba(245,166,35,0.3);
    }}
    .panel-title-text {{ font-size: 12.5px; font-weight: 800; letter-spacing: 0.04em; color: {KM_TEXT}; text-transform: uppercase; }}

    .stat-label {{ font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.07em; color: {KM_TEXT_MUTED}; font-weight: 700; margin-bottom: 2px; }}
    .stat-value {{ font-size: 17px; font-weight: 800; color: {KM_TEXT}; }}
    .stat-value-accent {{ color: {KM_AMBER}; }}
    .stat-value-green {{ color: {KM_GREEN}; }}

    .comp-badge {{ display: inline-block; font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 5px; margin: 2px 4px 2px 0; letter-spacing: 0.03em; }}
    .comp-badge-active {{ background-color: {KM_AMBER}; color: #1A1206; border: 1px solid {KM_AMBER}; }}
    .comp-badge-inactive {{ background-color: transparent; color: {KM_GRAY_DOT}; border: 1px solid {KM_BORDER}; }}

    .ds-row {{
        display: flex; justify-content: space-between; align-items: center; padding: 9px 12px;
        background-color: {KM_PANEL_ALT}; border: 1px solid {KM_BORDER}; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px; font-weight: 600;
    }}
    .ds-status-loaded {{ color: {KM_GREEN}; font-size: 10px; font-weight: 800; letter-spacing: 0.05em; }}
    .ds-status-optional {{ color: {KM_TEXT_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 0.05em; }}
    .ds-detail {{ font-size: 10.5px; color: {KM_GREEN}; margin: -4px 0 7px 12px; }}
    .doc-ref-row {{ font-size: 12px; color: {KM_TEXT_MUTED}; margin-bottom: 4px; }}
    .doc-ref-tag {{ color: {KM_AMBER}; font-weight: 700; }}

    .jepp-card {{
        background-color: {KM_PANEL_ALT}; border: 2px solid {KM_AMBER}; border-radius: 6px; padding: 14px;
        font-family: 'Geist Mono', monospace; color: {KM_TEXT}; margin-top: 10px; margin-bottom: 12px;
    }}
    .jepp-header {{ font-size: 14px; font-weight: 700; color: {KM_AMBER}; border-bottom: 1px dashed rgba(255,255,255,0.15); padding-bottom: 4px; margin-bottom: 8px; }}

    .status-badge-ok {{ background-color: rgba(52, 211, 153, 0.15); color: {KM_GREEN}; border: 1px solid rgba(52, 211, 153, 0.3); padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; }}
    .status-badge-warn {{ background-color: {KM_AMBER_DIM}; color: {KM_AMBER}; border: 1px solid rgba(245, 166, 35, 0.3); padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-align: center; }}

    .stButton>button {{
        background-color: transparent; color: {KM_TEXT}; border-radius: 7px; font-weight: 700;
        border: 1px solid {KM_BORDER}; padding: 0.45rem 0.9rem; transition: all 0.15s ease;
    }}
    .stButton>button:hover {{ border-color: {KM_AMBER}; color: {KM_AMBER}; }}
    .stButton>button[kind="primary"] {{ background-color: {KM_AMBER}; color: #1A1206; border: none; font-weight: 800; padding: 0.65rem 1rem; }}
    .stButton>button[kind="primary"]:hover {{ background-color: #ffb945; color: #1A1206; transform: translateY(-1px); }}
    .thin-divider {{ margin: 12px 0; border-bottom: 1px solid {KM_BORDER}; }}
    .ref-badge {{
        font-size: 10.5px; background-color: {KM_AMBER_DIM}; color: {KM_AMBER}; padding: 2px 6px;
        border-radius: 4px; margin-left: 6px; font-weight: 700; border: 1px solid rgba(245,166,35,0.3);
    }}

    /* ── Metric cards (top of workflow pages) ── */
    .km-metric {{
        background: {KM_PANEL};
        border: 1px solid {KM_BORDER};
        border-radius: 8px;
        padding: 14px 16px;
        height: 100%;
    }}
    .km-metric-lbl {{
        font-size: 9px;
        color: {KM_TEXT_MUTED};
        letter-spacing: .10em;
        text-transform: uppercase;
        font-weight: 700;
        margin-bottom: 6px;
    }}
    .km-metric-val {{
        font-size: 24px;
        font-weight: 800;
        color: {KM_AMBER};
        line-height: 1;
        margin-bottom: 4px;
    }}
    .km-metric-sub {{
        font-size: 10px;
        color: {KM_GREEN};
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
</style>
""", unsafe_allow_html=True)

header_placeholder = st.empty()

for _k, _v in {
    "fo_name": "F/O Unassigned",
    "capt_name": "Capt. Unassigned",
    "session_mode": "EBT Evaluation & Coaching",
    "sim_id": "KM Malta A320 STD2.2",
    "aircraft_type": "A320-214",
    "program_code": "EBT-2026",
    "session_duration_h": 4.0,
}.items():
    st.session_state.setdefault(_k, _v)

SESSION_MODE_SHORT = {
    "EBT Evaluation & Coaching": "EBT",
    "EBT Line-Oriented Assessment": "LOE",
    "Recurrent Check (LPC/OPC)": "OPC",
}

DOCUMENT_REFERENCES = {
    "EASA_EBT": "EASA AMC1 ORO.FC.231 (ED Decision 2015/027/R, amended 2021/002/R) – EBT core competencies & grading system",
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
                    {"text": "OB FPM 3.3: Smoothly references Beta Target (blue trapezoid on PFD) to optimize sideslip without chasing it abruptly.", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB FPM 3.4: Bank angle kept within 15° while below manoeuvring speed (F/S/G-DOT), consistent with protection limits in this configuration.", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB SAW 6.2: Maintains awareness of Engine-Out SID (EO SID) and terrain clearance profile; recognizes whether the aircraft is before or after the SID/EOSID divergence point.", "ref": "OM_B", "comp": "SAW"}
                ]
            },
            {
                "phase_name": "Phase 2: Core Systems Management (ECAM Execution)",
                "pta": "Manage thrust levers symmetrically before calling memory items; execute ECAM actions systematically above 400 ft AGL.",
                "obs": [
                    {"text": "OB APK 1.4: Strict ECAM discipline loop. PM reads line, touches switch, asks confirmation before actuation.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB APK 1.2: Adheres to approved procedures; allows ECAM to guide chronologically without premature fire pushbutton actuation, and confirms with PF before MASTER SWITCH OFF / fire P/B actions.", "ref": "FCOM_PRO", "comp": "APK"},
                    {"text": "OB COM 2.4: Clear closed-loop verification callouts before moving primary switches; PM announces ENG FAILURE/FIRE and cancels the aural warning promptly.", "ref": "EASA_EBT", "comp": "COM"},
                    {"text": "OB WLM 8.1: PF isolates attention strictly to primary flight parameters while delegating ECAM management to PM; TOGA use, if selected, is monitored against its time limit (10 min, 5 min FAA).", "ref": "OM_A", "comp": "WLM"}
                ]
            },
            {
                "phase_name": "Phase 3: Strategic Assessment & Diversion Planning",
                "pta": "Evaluate diversion options utilizing structured risk mitigation (FORDEC/DODAR), secure aircraft systems, and coordinate with ATC/Cabin.",
                "obs": [
                    {"text": "OB PSD 5.1: Identifies secondary threats caused by failure (reduced electrical/hydraulic redundancies) and considers possible structural damage cues (vibration, oil quantity/pressure, N1/N2 near zero).", "ref": "ICAO_9995", "comp": "PSD"},
                    {"text": "OB PSD 5.3: Implements formal decision matrix (FORDEC/DODAR): weighs returning vs. diverting, and whether a relight is appropriate once configured and stable.", "ref": "OM_A", "comp": "PSD"},
                    {"text": "OB SAW 6.1: Actively monitors remaining fuel flow, single-engine performance calculations, and minimum safe altitude (MSA).", "ref": "EASA_EBT", "comp": "SAW"},
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
        "keywords": ["ENGINE FIRE", "ENG FIRE", "TAILPIPE FIRE", "MECHANICAL DAMAGE", "SEVERE DAMAGE"],
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
        "keywords": ["DUAL GEN", "ELECTRICAL", "EMER ELEC", "RAT EXTENSION", "RAT EXTENDED", "EMERGENCY GENERATOR"],
        "phase": 3,
        "stressor": "Total loss of main AC buses (Generators 1 & 2 failed), triggering automatic RAT extension and CSM-G/battery-only bus reversion.",
        "cbta_focus": ["APK", "SAW", "FPA", "COM"],
        "sequence": [
            {
                "phase_name": "Phase 1: Emergency Reversion & RAT Deployment Verification",
                "pta": "Verify RAT extension and CSM-G coupling while maintaining flight parameters through the brief battery-only transition.",
                "obs": [
                    {"text": "OB SAW 6.1: Rapidly recognizes loss of primary display units, confirms RAT deployment, and anticipates the ~5 second battery-only period before CSM-G comes on line.", "ref": "FCOM_PRO", "comp": "SAW"},
                    {"text": "OB FPM 3.1: Stabilizes pitch and roll manually during the display power transition.", "ref": "FCTM_ABN", "comp": "FPM"},
                    {"text": "OB APK 1.2: Executes Emergency Electrical Configuration procedures without delay and maintains speed at or above RAT MINI (140 kt) to prevent RAT stall.", "ref": "QRH", "comp": "APK"}
                ]
            },
            {
                "phase_name": "Phase 2: Communication & Systems Management",
                "pta": "Restore communication using RMP 1 on VHF 1, manage the reduced system set available on CSM-G power, and plan for a fully manual, raw-data approach.",
                "obs": [
                    {"text": "OB COM 2.1: Establishes VHF 1 emergency communications using audio control panel 1; briefs that RA-based auto callouts are lost, so PM will call heights manually.", "ref": "OM_A", "comp": "COM"},
                    {"text": "OB WLM 8.1: Systematically delegates QRH management while maintaining raw-data navigation tracking (navaids tuned on RMP1, ND1/FMGC1 loss anticipated depending on RAT type/gear position).", "ref": "ICAO_9995", "comp": "WLM"},
                    {"text": "OB APK 1.3: Recognizes that all approaches must be flown manually with raw data — no AP, FD, or ATHR available in this configuration.", "ref": "FCOM_PRO", "comp": "APK"}
                ]
            },
            {
                "phase_name": "Phase 3: Approach & Landing Setup",
                "pta": "Plan a manual raw-data approach appropriate to the reduced system set, anticipating the flight control law change and loss of normal braking/NWS/reversers.",
                "obs": [
                    {"text": "OB FPA 4.2: Extracts characteristic (VLS/approach) speeds from QRH rather than relying on FAC-computed PFD speeds where affected, and briefs the ALTN-to-DIRECT law transition on gear extension.", "ref": "QRH", "comp": "FPA"},
                    {"text": "OB PSD 5.3: Anticipates loss of normal/alternate braking, NWS, and reversers (BSCU lost); plans a longer landing roll and runway exit strategy accordingly.", "ref": "FCOM_PRO", "comp": "PSD"},
                    {"text": "OB SAW 6.4: Cross-checks whether the operating RAT variant keeps CSM-G on line with gear down (\"new\" RAT) or disconnects it (\"old\" RAT), since this changes available systems on approach.", "ref": "OM_B", "comp": "SAW"}
                ]
            }
        ]
    },
    "EX-04_SE_ILS": {
        "title": "Exercise 04: Single Engine ILS Precision Approach & Missed Approach Profile",
        "keywords": ["SINGLE ENGINE ILS", "SE ILS", "ENGINE OUT ILS", "ENG OUT ILS"],
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
    },
    "EX-07_UNRELIABLE_SPEED": {
        "title": "Exercise 07: Unreliable Speed / Altitude Indication",
        "keywords": ["UNRELIABLE", "ADR 1+3", "ADR 2+3", "AIR DATA"],
        "phase": 4,
        "stressor": "Simultaneous pitot/static disagreement (e.g. dual ADR fault) producing unreliable IAS/altitude with no ECAM warning if all sources are affected equally.",
        "cbta_focus": ["SAW", "FPM", "PSD", "COM"],
        "sequence": [
            {
                "phase_name": "Phase 1: Recognition (Startle Management)",
                "pta": "Recognize the unreliable-indication pattern from correlation cues rather than a single clear warning, and manage the startle response.",
                "obs": [
                    {"text": "OB SAW 6.1: Identifies abnormal correlation between IAS, pitch, thrust and V/S (e.g. undue stall/overspeed warnings, jerky altitude) rather than waiting for a discrete ECAM alert.", "ref": "FCOM_PRO", "comp": "SAW"},
                    {"text": "OB PSD 5.1: Manages startle/surprise without abrupt control inputs; avoids fixating on a single suspect indication before cross-checking others.", "ref": "ICAO_9995", "comp": "PSD"}
                ]
            },
            {
                "phase_name": "Phase 2: Safety Recovery",
                "pta": "Apply the memorized safety recovery: disconnect automation and set the altitude-banded pitch/thrust reference, without hunting on unreliable speed data.",
                "obs": [
                    {"text": "OB APK 1.4: Disconnects AP, A/THR and FD without delay once the safe conduct of the flight is judged to be impacted.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB FPM 3.1: Sets the correct altitude-banded pitch/thrust reference: 15°/TOGA below thrust reduction altitude, 10°/CLB above thrust reduction altitude and below FL100, or 5°/CLB above FL100 — not a single fixed value regardless of phase.", "ref": "QRH", "comp": "FPM"},
                    {"text": "OB APK 1.2: Maintains current configuration if below CONF FULL, or selects and maintains CONF 3 if in CONF FULL; checks speedbrakes retracted and gear up as memorized.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB SAW 6.3: Levels off for troubleshooting once at or above MSA/circuit altitude, rather than continuing to climb or descend on unreliable data.", "ref": "QRH", "comp": "SAW"}
                ]
            },
            {
                "phase_name": "Phase 3: Diagnosis & Continued Safe Flight",
                "pta": "Confirm which parameters remain trustworthy, extract backup pitch/thrust tables, and plan the approach using only validated data.",
                "obs": [
                    {"text": "OB PSD 5.3: Determines whether altitude, speed, or both are affected, and selects the correct backup references accordingly (GPS ALT+GS for altitude; GPS GS/BIRD/other-aircraft-reported wind for speed).", "ref": "QRH", "comp": "PSD"},
                    {"text": "OB COM 2.5: Declares the emergency to ATC (squawk as briefed) and requests any assistance needed (radar-verified altitude, other traffic wind reports).", "ref": "OM_A", "comp": "COM"},
                    {"text": "OB APK 1.1: References the QRH pitch/thrust table for the current configuration and phase rather than reverting to normal PFD guidance prematurely.", "ref": "QRH", "comp": "APK"}
                ]
            }
        ]
    },
    "EX-08_DOUBLE_HYD": {
        "title": "Exercise 08: Double Hydraulic Failure (G+B / G+Y)",
        "keywords": ["(G/Y)", "(G/B)", "(B/Y)", "DOUBLE HYD", "DUAL HYD"],
        "phase": 6,
        "stressor": "Loss of two of three hydraulic systems, causing autopilot loss, degraded flight control law, and an abnormal landing configuration.",
        "cbta_focus": ["FPM", "APK", "PSD", "LTW"],
        "sequence": [
            {
                "phase_name": "Phase 1: Emergency Declaration & Task Allocation",
                "pta": "Declare the emergency (LAND ASAP) and confirm PF/PNF task allocation before starting the extended ECAM/QRH sequence.",
                "obs": [
                    {"text": "OB LTW 7.2: Confirms who will fly for the remainder of the approach and landing; a task handover between crew members is made explicit if it occurs.", "ref": "FCTM_ABN", "comp": "LTW"},
                    {"text": "OB COM 2.5: Declares LAND ASAP / emergency status to ATC promptly given the loss of two hydraulic systems.", "ref": "OM_A", "comp": "COM"}
                ]
            },
            {
                "phase_name": "Phase 2: Configuration & Gravity Extension",
                "pta": "Work the ECAM, QRH abnormal/performance tables, slats/flaps jammed checklist, and gravity gear extension checklist in the correct sequence, early enough to be stable before final descent.",
                "obs": [
                    {"text": "OB APK 1.4: Completes the SLATS/FLAPS JAMMED checklist to establish landing configuration early (downwind or long final), using selected speed throughout.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB APK 1.2: Performs gravity gear extension from the paper checklist, with gear down and stabilized before commencing the final descent.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB FPM 3.2: Anticipates degraded roll control (spoilers lost) and, if pitch trim is affected (G+Y loss), extends the landing gear at VAPP at the earliest point to retain elevator-trim integration.", "ref": "FCTM_ABN", "comp": "FPM"}
                ]
            },
            {
                "phase_name": "Phase 3: Approach, Landing & Rollout",
                "pta": "Fly a stabilized approach at the increased reference speed, brief the go-around from the checklist, and manage rollout with reduced braking/no NWS.",
                "obs": [
                    {"text": "OB PSD 5.4: Calculates the correct VREF increment and landing distance from QRH using the minimum configuration / maximum increment rule when in doubt.", "ref": "QRH", "comp": "PSD"},
                    {"text": "OB LTW 7.1: PM briefs the PF on the go-around procedure from the same checklist before the approach begins, given the abnormal configuration.", "ref": "OM_A", "comp": "LTW"},
                    {"text": "OB FPM 3.3: Maintains a well-stabilized approach with gear down early, avoiding hard pitch inputs that could trigger spurious stall warnings; plans a higher-speed runway exit given loss of normal/alternate braking and NWS.", "ref": "FCTM_ABN", "comp": "FPM"}
                ]
            }
        ]
    },
    "EX-09_ABNORMAL_SLATS_FLAPS": {
        "title": "Exercise 09: Abnormal Slats/Flaps Configuration",
        "keywords": ["SLATS SYS 1+2", "FLAPS LOCKED", "SLATS LOCKED", "F/CTL SLATS", "F/CTL FLAPS"],
        "phase": 6,
        "stressor": "Dual SFCC channel fault or WTB-jammed slats/flaps, producing a frozen high-lift configuration and modified approach references.",
        "cbta_focus": ["APK", "FPA", "SAW"],
        "sequence": [
            {
                "phase_name": "Phase 1: Fault Type Recognition", "pta": "Distinguish between a dual SFCC channel fault (protections/AP/ATHR lost) and a WTB-jammed condition (normal law, AP/ATHR retained to 500 ft) since the consequences differ materially.",
                "obs": [
                    {"text": "OB SAW 6.2: Correctly identifies which case applies (F/CTL SLATS FAULT vs F/CTL FLAPS FAULT vs S/F LOCKED) from the ECAM title and ND/PFD symptoms rather than assuming the more familiar case.", "ref": "FCOM_PRO", "comp": "SAW"}
                ]
            },
            {
                "phase_name": "Phase 2: Configuration & Speed Management", "pta": "Engage selected speed for the achieved configuration promptly and avoid exceeding VFE for the current slat/flap position.",
                "obs": [
                    {"text": "OB APK 1.2: Engages selected speed for the landing configuration as soon as the malfunction is confirmed, per the applicable checklist.", "ref": "QRH", "comp": "APK"},
                    {"text": "OB APK 1.3: Respects VFE-next limits for the current configuration; avoids selecting FLAPS FULL where the checklist prohibits it (dual flap channel fault).", "ref": "FCOM_PRO", "comp": "APK"}
                ]
            },
            {
                "phase_name": "Phase 3: Approach & Landing Data", "pta": "Extract the correct VAPP/ΔVREF and landing distance data from QRH for the achieved configuration, briefing any abnormal pitch attitude effects.",
                "obs": [
                    {"text": "OB FPA 4.3: Determines VAPP/ΔVREF and landing distance from QRH tables for the confirmed slat/flap position rather than assuming a standard-configuration value.", "ref": "QRH", "comp": "FPA"},
                    {"text": "OB PSD 5.2: Where AP/ATHR remain available (WTB-jammed case), plans to disconnect AP by 500 ft AGL as required by the procedure.", "ref": "QRH", "comp": "PSD"}
                ]
            }
        ]
    },
    "EX-10_ZFW_ERROR": {
        "title": "Exercise 10: ZFW / Loadsheet Entry Error",
        "keywords": ["ZFW", "LOADSHEET ERROR", "LOAD SHEET"],
        "phase": 1,
        "stressor": "An erroneous ZFW/FOB entry into the FMGC produces a CHECK GW discrepancy against the FAC-computed gross weight, with knock-on effects on characteristic speeds and SRS guidance.",
        "cbta_focus": ["APK", "SAW", "PSD"],
        "sequence": [
            {
                "phase_name": "Phase 1: Cross-Check Before Departure", "pta": "Cross-check the FMGC-entered ZFW/FOB against the load sheet before accepting performance data.",
                "obs": [
                    {"text": "OB APK 1.1: Cross-checks INIT B page ZFW/ZFWCG and FOB entries against the load sheet before takeoff performance is computed.", "ref": "FCOM_PRO", "comp": "APK"}
                ]
            },
            {
                "phase_name": "Phase 2: CHECK GW Recognition", "pta": "Recognize a CHECK GW amber warning as a discrepancy between FMGC and FAC-computed gross weight and resolve it methodically rather than dismissing it.",
                "obs": [
                    {"text": "OB SAW 6.1: Notices the CHECK GW message and does not dismiss it without cross-checking current GW against the load sheet and ECAM fuel-used values.", "ref": "QRH", "comp": "SAW"},
                    {"text": "OB PSD 5.1: Correctly reasons through which value is likely wrong (FMGC entry vs AOA-derived FAC value) using the comparison procedure, rather than guessing.", "ref": "ICAO_9995", "comp": "PSD"}
                ]
            },
            {
                "phase_name": "Phase 3: Corrective Action", "pta": "Apply the correct fix — amend the FUEL PRED page entry, or use QRH-derived characteristic speeds if the load sheet GW is confirmed correct.",
                "obs": [
                    {"text": "OB APK 1.4: Inserts the corrected GW value on the FUEL PRED page once an obvious entry error is confirmed, or extracts characteristic speeds from QRH chapter 4 if PFD speeds remain suspect.", "ref": "QRH", "comp": "APK"}
                ]
            }
        ]
    },
    "EX-11_DOUBLE_RA": {
        "title": "Exercise 11: Double Radio Altimeter Failure",
        "keywords": ["RA 1+2", "DOUBLE RA", "RADIO ALTIMETER", "DUAL RA"],
        "phase": 6,
        "stressor": "Loss of both radio altimeters removes R/A-dependent flight control law transitions, autoland modes, GPWS/EGPWS, and auto callouts.",
        "cbta_focus": ["SAW", "APK", "COM"],
        "sequence": [
            {
                "phase_name": "Phase 1: System Impact Assessment", "pta": "Recognize the full scope of R/A-dependent systems affected before briefing the approach.",
                "obs": [
                    {"text": "OB SAW 6.3: Identifies that flare/ground law transitions now depend on LGCIU (gear-down/weight-on-wheels) rather than R/A height, and that GPWS/EGPWS and R/A auto callouts are lost.", "ref": "FCOM_PRO", "comp": "SAW"}
                ]
            },
            {
                "phase_name": "Phase 2: Approach Mode Planning", "pta": "Plan a non-autoland, non-managed-height-callout approach; brief that LAND/FLARE/ROLLOUT modes will not engage.", 
                "obs": [
                    {"text": "OB APK 1.2: Selects LOC/APPR modes manually via pushbutton where required, aware that autoland and DH auto-callouts are unavailable.", "ref": "FCOM_PRO", "comp": "APK"}
                ]
            },
            {
                "phase_name": "Phase 3: Manual Callouts & Landing", "pta": "Compensate for lost automation with disciplined manual callouts through flare and landing.",
                "obs": [
                    {"text": "OB COM 2.3: PM calls height/rate manually in the absence of R/A auto callouts, and calls USE MANUAL PITCH TRIM awareness as the aircraft transitions to direct law with gear down.", "ref": "OM_A", "comp": "COM"}
                ]
            }
        ]
    },
    "EX-00_GENERIC": {
        "title": "Generic Malfunction / Standard Operating Procedure Application",
        "keywords": ["DEFAULT"],
        "phase": 1,
        "stressor": "A malfunction or operational requirement not covered by a dedicated syllabus exercise profile.",
        "cbta_focus": ["SAW", "APK", "COM", "PSD", "WLM"],
        "sequence": [
            {
                "phase_name": "Phase 1: Identification & Verification",
                "pta": "Identify the malfunction or specific requirement and cross-check indications before acting.",
                "obs": [
                    {"text": "OB SAW 6.1: Continuous monitoring of aircraft state and operational profile.", "ref": "EASA_EBT", "comp": "SAW"},
                    {"text": "OB PSD 5.1: Identifies operational errors or unexpected malfunctions early, without fixation.", "ref": "ICAO_9995", "comp": "PSD"}
                ]
            },
            {
                "phase_name": "Phase 2: Procedure Application",
                "pta": "Adhere strictly to company SOPs and the applicable normal/abnormal checklist.",
                "obs": [
                    {"text": "OB APK 1.2: Follows SOPs and the applicable checklist meticulously unless safety dictates otherwise.", "ref": "FCOM_PRO", "comp": "APK"},
                    {"text": "OB COM 2.4: Ensures vital checklist messages are correctly understood and acknowledged in closed loop.", "ref": "EASA_EBT", "comp": "COM"}
                ]
            },
            {
                "phase_name": "Phase 3: Operational Adjustment",
                "pta": "Maintain effective situational awareness and adjust the flight plan or workload distribution as necessary.",
                "obs": [
                    {"text": "OB WLM 8.1: Prioritizes and distributes tasks effectively under changing conditions.", "ref": "ICAO_9995", "comp": "WLM"},
                    {"text": "OB PSD 5.4: Decides on an optimal course of action in a timely, safe manner.", "ref": "EASA_EBT", "comp": "PSD"}
                ]
            }
        ]
    }
}

ATA_TO_FAMILY = {
    21: "AIR_SYS", 30: "AIR_SYS", 35: "AIR_SYS", 36: "AIR_SYS", 31: "AIR_SYS",
    22: "AUTOFLT", 24: "ELEC", 27: "FLTCTRL", 28: "FUEL", 29: "HYD", 32: "GEAR", 34: "NAV",
    26: "PWR", 52: "PWR", 54: "PWR", 57: "PWR", 70: "PWR", 71: "PWR", 72: "PWR", 73: "PWR",
    74: "PWR", 75: "PWR", 76: "PWR", 77: "PWR", 78: "PWR", 79: "PWR", 80: "PWR",
}

ATA_FAMILY_GENERIC = {
    "AIR_SYS": {
        "title": "Air Conditioning / Pressurization / Ice & Rain Protection Malfunction",
        "cbta_focus": ["APK", "SAW", "WLM"],
        "sequence": [
            {"phase_name": "Phase 1: Recognition & ECAM Management", "pta": "Identify the affected system and manage the ECAM/checklist without delaying flight path monitoring.",
             "obs": [{"text": "OB SAW 6.1: Cross-checks cabin altitude/differential pressure or bleed/anti-ice indications against expected values.", "ref": "ICAO_9995", "comp": "SAW"},
                     {"text": "OB APK 1.2: Actions the applicable ECAM/QRH procedure methodically and in sequence.", "ref": "FCOM_PRO", "comp": "APK"}]},
            {"phase_name": "Phase 2: Operational Adjustment", "pta": "Adjust altitude, speed, or configuration as the procedure requires while maintaining crew workload balance.",
             "obs": [{"text": "OB WLM 8.1: Delegates monitoring/communication tasks to avoid task saturation during procedure execution.", "ref": "ICAO_9995", "comp": "WLM"}]}
        ]
    },
    "AUTOFLT": {
        "title": "Auto Flight System Malfunction",
        "cbta_focus": ["FPA", "FPM", "SAW", "COM"],
        "sequence": [
            {"phase_name": "Phase 1: Mode Awareness & Recovery", "pta": "Recognize the automation degradation/disconnection and establish manual or alternate guidance without delay.",
             "obs": [{"text": "OB SAW 6.3: Promptly identifies FMA mode changes or automation disconnects.", "ref": "FCOM_PRO", "comp": "SAW"},
                     {"text": "OB FPM 3.1: Smoothly assumes manual control if automation is lost, maintaining flight path within tolerances.", "ref": "FCTM_ABN", "comp": "FPM"}]},
            {"phase_name": "Phase 2: Crew Coordination", "pta": "Communicate the degraded mode/status clearly and agree the operating strategy going forward.",
             "obs": [{"text": "OB COM 2.4: Clear closed-loop callout of the automation state change and agreed handling strategy.", "ref": "EASA_EBT", "comp": "COM"}]}
        ]
    },
    "ELEC": {
        "title": "Electrical System Malfunction",
        "cbta_focus": ["APK", "SAW", "COM"],
        "sequence": [
            {"phase_name": "Phase 1: Bus/Generator Fault Management", "pta": "Identify the affected bus/generator and action the ECAM procedure, monitoring for cascading system loss.",
             "obs": [{"text": "OB SAW 6.1: Anticipates secondary system effects (displays, hydraulics, avionics) of the electrical fault.", "ref": "ICAO_9995", "comp": "SAW"},
                     {"text": "OB APK 1.4: Strict ECAM discipline loop for electrical reconfiguration actions.", "ref": "QRH", "comp": "APK"}]},
            {"phase_name": "Phase 2: Communication & Load Management", "pta": "Coordinate any load-shedding or reconfiguration clearly between PF and PM.",
             "obs": [{"text": "OB COM 2.1: Confirms reconfiguration actions verbally before switch actuation.", "ref": "OM_A", "comp": "COM"}]}
        ]
    },
    "FLTCTRL": {
        "title": "Flight Control System Malfunction",
        "cbta_focus": ["FPM", "APK", "SAW"],
        "sequence": [
            {"phase_name": "Phase 1: Handling Characteristic Assessment", "pta": "Assess the degraded control law/surface and adjust handling technique accordingly.",
             "obs": [{"text": "OB FPM 3.1: Adapts control inputs to the degraded handling characteristics without overcontrolling.", "ref": "FCTM_ABN", "comp": "FPM"},
                     {"text": "OB SAW 6.2: Monitors for any asymmetry or trim requirement resulting from the malfunction.", "ref": "FCOM_PRO", "comp": "SAW"}]},
            {"phase_name": "Phase 2: Procedure & Landing Considerations", "pta": "Apply the applicable checklist and brief any landing distance/approach speed implications.",
             "obs": [{"text": "OB APK 1.1: References QRH for any performance/landing distance adjustment required.", "ref": "QRH", "comp": "APK"}]}
        ]
    },
    "FUEL": {
        "title": "Fuel System Malfunction",
        "cbta_focus": ["APK", "PSD", "SAW", "COM"],
        "sequence": [
            {"phase_name": "Phase 1: Fault Confirmation", "pta": "Confirm the fuel system indication against cross-checks before actioning the procedure.",
             "obs": [{"text": "OB SAW 6.1: Cross-checks fuel quantity/flow indications between systems before acting.", "ref": "FCOM_PRO", "comp": "SAW"}]},
            {"phase_name": "Phase 2: Planning Impact", "pta": "Assess range/endurance impact and adjust the operational plan (diversion, fuel priority) as needed.",
             "obs": [{"text": "OB PSD 5.3: Evaluates fuel state against destination/alternate requirements and decides in good time.", "ref": "OM_A", "comp": "PSD"},
                     {"text": "OB COM 2.5: Communicates fuel status/intentions clearly to ATC if relevant.", "ref": "OM_A", "comp": "COM"}]}
        ]
    },
    "HYD": {
        "title": "Hydraulic System Malfunction",
        "cbta_focus": ["APK", "FPM", "PSD"],
        "sequence": [
            {"phase_name": "Phase 1: System Isolation", "pta": "Identify the affected hydraulic system and action the ECAM procedure to isolate/manage it.",
             "obs": [{"text": "OB APK 1.2: Follows the hydraulic ECAM procedure precisely, including any system isolation steps.", "ref": "QRH", "comp": "APK"}]},
            {"phase_name": "Phase 2: Degraded Handling & Landing Planning", "pta": "Anticipate degraded control/braking/gear characteristics and brief the approach and landing accordingly.",
             "obs": [{"text": "OB FPM 3.1: Anticipates and compensates for any degraded control response.", "ref": "FCTM_ABN", "comp": "FPM"},
                     {"text": "OB PSD 5.1: Identifies landing distance/braking implications early and plans accordingly.", "ref": "ICAO_9995", "comp": "PSD"}]}
        ]
    },
    "GEAR": {
        "title": "Landing Gear System Malfunction",
        "cbta_focus": ["APK", "COM", "PSD", "LTW"],
        "sequence": [
            {"phase_name": "Phase 1: Confirmation & Checklist", "pta": "Confirm the gear indication/fault and action the applicable checklist (including alternate extension if required).",
             "obs": [{"text": "OB APK 1.4: Strict, methodical execution of the gear malfunction / alternate extension checklist.", "ref": "QRH", "comp": "APK"}]},
            {"phase_name": "Phase 2: Decision & Briefing", "pta": "Decide on approach/landing strategy (including possible go-around or diversion) and brief the crew.",
             "obs": [{"text": "OB PSD 5.4: Makes a timely decision on landing strategy given the confirmed gear status.", "ref": "OM_A", "comp": "PSD"},
                     {"text": "OB LTW 7.1: Briefs the crew/cabin clearly on the plan and seeks input before committing.", "ref": "OM_A", "comp": "LTW"}]}
        ]
    },
    "NAV": {
        "title": "Navigation System Malfunction",
        "cbta_focus": ["SAW", "FPA", "PSD"],
        "sequence": [
            {"phase_name": "Phase 1: Cross-Check & Backup", "pta": "Cross-check the affected navigation source against backups and revert to a reliable reference.",
             "obs": [{"text": "OB SAW 6.2: Cross-checks navigation sources and identifies the degraded/failed source promptly.", "ref": "FCOM_PRO", "comp": "SAW"},
                     {"text": "OB FPA 4.1: Reconfigures FMGS/navigation display to a reliable backup source.", "ref": "FCTM_ABN", "comp": "FPA"}]},
            {"phase_name": "Phase 2: Route/Approach Implications", "pta": "Assess any impact on planned routing or approach capability (e.g. RNP, CAT II/III) and adjust.",
             "obs": [{"text": "OB PSD 5.3: Evaluates whether the planned approach/routing remains valid given the degraded navigation capability.", "ref": "OM_B", "comp": "PSD"}]}
        ]
    },
    "PWR": {
        "title": "Powerplant / Engine-Related System Malfunction",
        "cbta_focus": ["APK", "PSD", "COM", "SAW"],
        "sequence": [
            {"phase_name": "Phase 1: Identification & ECAM Actions", "pta": "Identify the affected engine/system and action the ECAM procedure methodically.",
             "obs": [{"text": "OB SAW 6.1: Rapidly identifies the fault and cross-checks engine/system parameters.", "ref": "FCOM_PRO", "comp": "SAW"},
                     {"text": "OB APK 1.4: Strict ECAM discipline loop, including any confirm-procedure switch actuations.", "ref": "QRH", "comp": "APK"}]},
            {"phase_name": "Phase 2: Operational Decision", "pta": "Decide on the appropriate operational response (continue, divert, return) and communicate it clearly.",
             "obs": [{"text": "OB PSD 5.3: Weighs the operational options using a structured decision process (e.g. FORDEC/DODAR).", "ref": "OM_A", "comp": "PSD"},
                     {"text": "OB COM 2.5: Communicates the decision and status clearly to ATC and cabin crew as applicable.", "ref": "OM_A", "comp": "COM"}]}
        ]
    }
}

SCENARIO_OB_LIBRARY = {}

def _file_cache_token(source):
    try:
        return os.path.getmtime(source) if isinstance(source, (str, os.PathLike)) and os.path.exists(source) else None
    except Exception:
        return None

@st.cache_data(show_spinner="Loading scenario-specific Observable Behaviours...")
def load_scenario_obs_library(source, cache_token=None):
    try:
        try:
            df_obs = pd.read_excel(source, sheet_name="Scenario OBs")
        except ValueError:
            df_obs = pd.read_excel(source)
        df_obs.columns = [str(c).strip() for c in df_obs.columns]
        library = {}
        for _, row in df_obs.iterrows():
            event = row.get("EVENT")
            if pd.isna(event) or str(event).strip().upper().startswith("EXAMPLE"):
                continue
            obs = []
            for i in (1, 2, 3, 4):
                comp = row.get(f"OB{i}_COMPETENCY")
                text = row.get(f"OB{i}_TEXT")
                ref = row.get(f"OB{i}_REF")
                if pd.notna(comp) and pd.notna(text) and str(comp).strip() and str(text).strip():
                    comp_clean = str(comp).strip().upper()
                    if comp_clean in COMPETENCY_KEYS:
                        obs.append({
                            "text": f"OB {comp_clean}: {str(text).strip()}",
                            "ref": str(ref).strip() if pd.notna(ref) and str(ref).strip() else "OM_B",
                            "comp": comp_clean,
                        })
            if not obs: continue
            pta = str(row.get("PTA")).strip() if pd.notna(row.get("PTA")) else ""
            norm = _normalize_event_name(event)
            library[norm] = {
                "pta": pta,
                "sequence": [{"phase_name": "Scenario-Specific Observable Behaviours (Training Dept. Authored)", "pta": pta, "obs": obs}],
                "cbta_focus": sorted({o["comp"] for o in obs}),
            }
        return library, None
    except Exception as e:
        return {}, str(e)

def get_exercise_for_event(event_title, ata=None):
    ev_upper = str(event_title).replace("\xa0", " ").upper()
    for ex_key, ex_data in PROGRAM_SYLLABUS_EXERCISES.items():
        if ex_key == "EX-00_GENERIC":
            continue
        if any(kw in ev_upper for kw in ex_data["keywords"]):
            return ex_data["title"], ex_data["sequence"], ex_data["cbta_focus"]
    if SCENARIO_OB_LIBRARY:
        norm_ev = _normalize_event_name(event_title)
        entry = SCENARIO_OB_LIBRARY.get(norm_ev)
        if entry is None:
            close = difflib.get_close_matches(norm_ev, list(SCENARIO_OB_LIBRARY.keys()), n=1, cutoff=0.72)
            if close: entry = SCENARIO_OB_LIBRARY[close[0]]
        if entry:
            return f"Scenario-Specific: {event_title}", entry["sequence"], entry["cbta_focus"]
    if ata is not None:
        try: family = ATA_TO_FAMILY.get(int(ata))
        except (TypeError, ValueError): family = None
        if family and family in ATA_FAMILY_GENERIC:
            fam = ATA_FAMILY_GENERIC[family]
            return fam["title"], fam["sequence"], fam["cbta_focus"]
    generic = PROGRAM_SYLLABUS_EXERCISES["EX-00_GENERIC"]
    return generic["title"], generic["sequence"], generic["cbta_focus"]

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
    "APK": "Application of Procedures", "COM": "Communication", "FPM": "Flight Path Management – Manual",
    "FPA": "Flight Path Management – Automation", "KNO": "Knowledge", "LTW": "Leadership & Teamwork",
    "PSD": "Problem Solving & Decision Making", "SAW": "Situational Awareness", "WLM": "Workload Management",
}

GRADE_LABELS = {5: "Excellent", 4: "Very Good", 3: "Good", 2: "Minimum Acceptable Level", 1: "Unsatisfactory"}
GRADE_DESCRIPTORS = {
    5: "The pilot always demonstrates all the required behavioural indicators in an effective and efficient manner. Safety is significantly enhanced.",
    4: "The pilot demonstrated effective knowledge, skill and attitudes by demonstrating all the required behavioural markers in a regular manner. Safety is always enhanced.",
    3: "The pilot demonstrated adequate knowledge, skill and attitude by demonstrating all the required behavioural markers in a frequent manner, resulting in a safe operation.",
    2: "The pilot demonstrated knowledge, skill and attitude at a minimum acceptable level by only occasionally demonstrating some of the behavioural markers when required, but never resulting in an unsafe situation.",
    1: "The pilot did not demonstrate the necessary knowledge, skill and attitude in any of the behavioural indicators when required, which resulted in an unsafe situation.",
}

COMPETENCY_KPIS = {
    "APK": ["Follows SOPs unless a higher degree of safety dictates otherwise", "Identifies and applies all operating instructions in a timely manner", "Correctly uses aircraft systems, controls and instruments", "Safely manages the aircraft to achieve best value for the operation, including fuel, the environment, passenger comfort and punctuality", "Identifies the source of operating instructions"],
    "COM": ["Knows what, how, where, when, how much and with whom he or she needs to communicate", "Ensures the recipient is ready and able to receive the information", "Conveys messages and information clearly, accurately, timely and adequately", "Confirms that the recipient correctly understands important information", "Listens actively, patiently and demonstrates understanding when receiving information", "Asks relevant and effective questions and offers suggestions", "Uses appropriate body language, eye contact and tone, and correctly interprets non-verbal communication of others", "Is receptive to other people's views and is willing to compromise"],
    "FPA": ["Controls the aircraft using automation with accuracy and smoothness as appropriate to the situation", "Detects deviations from the desired aircraft trajectory and takes appropriate action", "Contains the aircraft within the normal flight envelope", "Manages the flight path to achieve optimum operational performance", "Maintains the desired flight path during flight using automation whilst managing other tasks and distractions", "Selects appropriate level and mode of automation in a timely manner considering phase of flight and workload", "Effectively monitors automation, including engagement and automatic mode transitions"],
    "FPM": ["Controls the aircraft manually with accuracy and smoothness as appropriate to the situation", "Detects deviations from the desired aircraft trajectory and takes appropriate action", "Contains the aircraft within the normal flight envelope", "Controls the aircraft safely using only the relationship between aircraft attitude, speed and thrust", "Manages the flight path to achieve optimum operational performance", "Maintains the desired flight path during manual flight whilst managing other tasks and distractions", "Selects appropriate level and mode of flight guidance systems in a timely manner considering phase of flight and workload", "Effectively monitors flight guidance systems, including engagement and automatic mode transitions"],
    "KNO": ["Demonstrates practical and applicable knowledge of limitations and systems and their interaction", "Demonstrates required knowledge of published operating instructions", "Demonstrates knowledge of the physical environment, the air traffic environment including routing, weather, airports and operational infrastructure", "Demonstrates appropriate knowledge of applicable legislation", "Knows where to source required information", "Demonstrates a positive interest in acquiring knowledge", "Is able to apply knowledge effectively"],
    "LTW": ["Understands and agrees with the crew's roles and objectives", "Is approachable, enthusiastic, motivating and considerate of others", "Uses initiative, gives direction and takes responsibility when required", "Anticipates other crew members' needs and carries out instructions when directed", "Is open and honest about thoughts, concerns and intentions", "Gives and receives both criticism and praise well and admits mistakes", "Confidently says and does what is important for safety", "Demonstrates empathy, respect and tolerance for other people", "Involves others in planning and allocates activities fairly and appropriately to abilities"],
    "PSD": ["Identifies and verifies why things have gone wrong and does not jump to conclusions or makes uninformed assumptions", "Seeks accurate and adequate information from appropriate sources", "Perseveres in working through a problem without reducing safety", "Uses appropriate agreed and timely decision-making processes", "Applies essential and desirable criteria and prioritises", "Considers as many options as practicable", "Makes decisions when needed, reviews and changes them if required", "Considers risks but does not take unnecessary risks", "Improvises appropriately when faced with unforeseen circumstances to achieve the safest outcome"],
    "SAW": ["Is aware of the state of the aircraft and its systems", "Is aware of where the aircraft is and its environment", "Keeps track of time and fuel", "Is aware of the condition of people involved in the operation including passengers", "Develops \"what if\" scenarios and plans for contingencies", "Identifies threats to the safety of the aircraft and people, and takes appropriate action"],
    "WLM": ["Is calm, relaxed, careful and not impulsive", "Plans, prepares, prioritises and schedules tasks effectively", "Manages time efficiently when carrying out tasks", "Offers and accepts assistance, delegates when necessary and asks for help early", "Reviews, monitors and cross-checks actions conscientiously", "Ensures tasks are completed", "Manages interruptions, distractions, variations and failures effectively"],
}

COMPETENCY_GRADE_TEXT = {
    "APK": {5: "The pilot applied procedures very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.", 4: "The pilot applied procedures effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.", 3: "The pilot applied procedures adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.", 2: "The pilot applied procedures at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.", 1: "The pilot did not apply procedures correctly, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation."},
    "COM": {5: "The pilot communicated very effectively...", 4: "The pilot communicated effectively...", 3: "The pilot communicated adequately...", 2: "The pilot communicated at the minimum acceptable level...", 1: "The pilot did not communicate effectively..."},
    "FPA": {5: "The pilot managed the automation very effectively...", 4: "The pilot managed the automation effectively...", 3: "The pilot managed the automation adequately...", 2: "The pilot managed the automation at the minimum acceptable level...", 1: "The pilot did not manage the automation effectively..."},
    "FPM": {5: "The pilot controlled the aircraft very effectively...", 4: "The pilot controlled the aircraft effectively...", 3: "The pilot controlled the aircraft adequately...", 2: "The pilot controlled the aircraft at the minimum acceptable level...", 1: "The pilot did not control the aircraft effectively..."},
    "KNO": {5: "The pilot showed exemplary knowledge...", 4: "The pilot showed effective knowledge...", 3: "The pilot showed adequate knowledge...", 2: "The pilot showed knowledge to a minimum acceptable level...", 1: "The pilot did not show adequate knowledge..."},
    "LTW": {5: "The pilot led and worked as a team member very effectively...", 4: "The pilot led and worked as a team member effectively...", 3: "The pilot led and worked as a team member adequately...", 2: "The pilot led and worked as a team member at the minimum acceptable level...", 1: "The pilot did not lead or work as a team member..."},
    "PSD": {5: "The pilot solved problems and made decisions very effectively...", 4: "The pilot solved problems and made decisions effectively...", 3: "The pilot solved problems and made decisions adequately...", 2: "The pilot solved problems and made decisions at the minimum acceptable level...", 1: "The pilot did not solve problems and make decisions effectively..."},
    "SAW": {5: "The pilot's situation awareness was excellent...", 4: "The pilot's situation awareness was very good...", 3: "The pilot's situation awareness was adequate...", 2: "The pilot's situation awareness was at the minimum acceptable level...", 1: "The pilot's situation awareness was not adequate..."},
    "WLM": {5: "The pilot managed workload very effectively...", 4: "The pilot managed workload effectively...", 3: "The pilot managed workload very adequately...", 2: "The pilot managed workload at the minimum acceptable level...", 1: "The pilot did not manage workload effectively..."},
}

PHASE_DEFINITIONS = {
    1: "Flight preparation to completion of line-up.", 2: "From the application of take-off thrust until the completion of flap and slat retraction.",
    3: "From the completion of flap and slat retraction until top of climb.", 4: "From top of climb until top of descent.",
    5: "From top of descent until the earlier of first slat/flap extension or crossing the initial approach fix.", 6: "From the earlier of first slat/flap extension or crossing the initial approach fix until 15 m (50 ft) AAL, including go-around.",
    7: "From 15 m (50 ft) AAL until reaching taxi speed.", 8: "From reaching taxi speed until engine shutdown.",
}

STANDARD_PHRASE_BANK = {
    5: ["No errors observed; execution exceeded the published standard throughout.", "Handled proactively with clear anticipation of downstream consequences.", "Exemplary crew coordination and workload distribution under pressure."],
    4: ["Minor deviation(s) noted; self-identified and corrected without prompting.", "Solid adherence to SOPs with only trivial timing/sequencing imperfections.", "Effective performance; a small refinement would bring this to exemplary."],
    3: ["Met the operational standard; no safety-relevant errors observed.", "Standard, competent handling consistent with line operations.", "Acceptable performance; no intervention required at any point."],
    2: ["Required instructor prompt/intervention to bring performance back to standard.", "Below standard; errors were safety-relevant but were mitigated in time.", "Task saturation observed; workload management needs focused follow-up."],
    1: ["Immediate instructor intervention required to maintain safety margins.", "Unsafe practice observed; this item must be re-briefed and re-flown.", "Standard not met; formal remedial training is recommended."],
}

def fetch_live_metar(icao_code):
    try:
        url = f"https://aviationweather.gov/api/data/metar?ids={icao_code}&format=raw"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            metar = response.read().decode('utf-8').strip()
            return metar if metar else "No live METAR data returned."
    except Exception: return "METAR connection unavailable (offline mode)."

def parse_metar_to_ios(metar_str):
    """Extracts wind, temp, and QNH from a raw METAR string."""
    parsed = {}
    if not metar_str or "offline" in metar_str.lower() or "No live" in metar_str:
        return parsed
        
    # Wind: e.g., 31015G25KT or VRB05KT
    wind_match = re.search(r'\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT\b', metar_str)
    if wind_match:
        parsed['dir'] = 0 if wind_match.group(1) == 'VRB' else int(wind_match.group(1))
        parsed['spd'] = int(wind_match.group(2))
        parsed['gust'] = int(wind_match.group(3)) if wind_match.group(3) else 0

    # Temp: e.g., 14/08 or M02/M05
    temp_match = re.search(r'\b(M?\d{2})/(M?\d{2})\b', metar_str)
    if temp_match:
        t_str = temp_match.group(1)
        parsed['temp'] = -int(t_str[1:]) if t_str.startswith('M') else int(t_str)

    # QNH: e.g., Q1013 or A2992
    qnh_match = re.search(r'\bQ(\d{4})\b', metar_str)
    if qnh_match:
        parsed['qnh'] = int(qnh_match.group(1))
        
    return parsed

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
    if cat == "Technical Failure": return cands[cands["ATA"].notna()]
    if cat == "Non-Technical / CRM (Non-ATA)": return cands[cands["ATA"].isna()]
    if cat == "ATA Specific" and cfg.get("ata") is not None: return cands[cands["ATA"] == cfg["ata"]]
    return cands

def apply_competency_filter(cands, target_competency):
    if target_competency == "Any" or cands.empty: return cands
    return cands[cands["COMPETENCIES"].apply(lambda c: target_competency in c)]

def _normalize_event_name(name):
    s = str(name).upper()
    s = re.sub(r'\(REF:[^)]+\)', '', s)
    for ch in ['(', ')', '–', '—', '-', ':', ',', '/', '.', '\xa0', '_', '+']: s = s.replace(ch, ' ')
    return " ".join(s.split())

def competency_chip_row(codes):
    if not codes: return "<span style='opacity:0.6; font-size:12px;'>No competency data matched</span>"
    return "".join(f"<span style='background:rgba(2,132,199,0.12); color:#0284C7; border:1px solid rgba(2,132,199,0.35); padding:2px 7px; border-radius:10px; font-size:11px; font-weight:600; margin-right:5px;'>{c}</span>" for c in codes)

COMPETENCY_COLORS = {"APK": "#0284C7", "COM": "#7C3AED", "FPA": "#0891B2", "FPM": "#059669", "KNO": "#CA8A04", "LTW": "#DB2777", "PSD": "#DC2626", "SAW": "#EA580C", "WLM": "#4F46E5"}

def build_ob_flow_html(sequence_data):
    n = len(sequence_data)
    parts = ["<div style='padding:4px 0;'>"]
    for idx, step in enumerate(sequence_data):
        obs_html = ""
        for ob in step["obs"]:
            color = COMPETENCY_COLORS.get(ob.get("comp"), "#64748B")
            ref_title = DOCUMENT_REFERENCES.get(ob.get("ref"), ob.get("ref", ""))
            obs_html += (f"<div style='display:flex; gap:8px; align-items:flex-start; margin-bottom:6px;'>"
                         f"<span style='flex-shrink:0; background:{color}1A; color:{color}; border:1px solid {color}55; padding:1px 7px; border-radius:10px; font-size:10.5px; font-weight:700; margin-top:1px;'>{ob.get('comp','')}</span>"
                         f"<span style='font-size:13px; color:var(--text-color);' title='{ref_title}'>{ob['text']}</span></div>")
        parts.append(f"<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.25); border-left:4px solid #0284C7; border-radius:8px; padding:14px 16px; margin-bottom:4px;'><div style='font-size:14.5px; font-weight:600; color:var(--text-color); margin-bottom:6px;'>{step['phase_name']}</div><div style='font-size:12.5px; opacity:0.8; margin-bottom:10px;'><b>Target action:</b> {step['pta']}</div>{obs_html}</div>")
        if idx < n - 1: parts.append("<div style='text-align:center; font-size:16px; color:#0284C7; margin:2px 0 8px 0;'>&#8595;</div>")
    parts.append("</div>")
    return "".join(parts)

def build_competency_venn_svg(sets_dict):
    labels = list(sets_dict.keys())
    n = len(labels)
    if n not in (2, 3): return "<div style='font-size:12.5px; opacity:0.7;'>Select exactly 2 or 3 slots to compare.</div>"
    colors = ["#378ADD", "#1D9E75", "#D85A30"]
    if n == 2:
        centers = [(220, 180), (340, 180)]
        r = 130
        A, B = sets_dict[labels[0]], sets_dict[labels[1]]
        only_a, only_b, both = sorted(A - B), sorted(B - A), sorted(A & B)
        circles = "".join(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colors[i]}" fill-opacity="0.28" stroke="{colors[i]}" stroke-width="1"/>' for i, (cx, cy) in enumerate(centers))
        text = (f'<text x="150" y="70" font-size="14" font-weight="600" fill="var(--text-color)">{labels[0]}</text>'
                f'<text x="410" y="70" font-size="14" font-weight="600" fill="var(--text-color)" text-anchor="end">{labels[1]}</text>'
                f'<text x="175" y="185" font-size="13" fill="var(--text-color)" text-anchor="middle">{", ".join(only_a) or "—"}</text>'
                f'<text x="385" y="185" font-size="13" fill="var(--text-color)" text-anchor="middle">{", ".join(only_b) or "—"}</text>'
                f'<text x="280" y="185" font-size="13" font-weight="700" fill="var(--text-color)" text-anchor="middle">{", ".join(both) or "—"}</text>')
        vh = 280
    else:
        centers = [(270, 190), (410, 190), (340, 310)]
        r = 130
        A, B, C = sets_dict[labels[0]], sets_dict[labels[1]], sets_dict[labels[2]]
        only_a, only_b, only_c = sorted(A - B - C), sorted(B - A - C), sorted(C - A - B)
        ab, ac, bc, abc = sorted((A & B) - C), sorted((A & C) - B), sorted((B & C) - A), sorted(A & B & C)
        circles = "".join(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colors[i]}" fill-opacity="0.28" stroke="{colors[i]}" stroke-width="1"/>' for i, (cx, cy) in enumerate(centers))
        text = (f'<text x="185" y="65" font-size="14" font-weight="600" fill="var(--text-color)">{labels[0]}</text>'
                f'<text x="495" y="65" font-size="14" font-weight="600" fill="var(--text-color)" text-anchor="end">{labels[1]}</text>'
                f'<text x="340" y="450" font-size="14" font-weight="600" fill="var(--text-color)" text-anchor="middle">{labels[2]}</text>'
                f'<text x="220" y="175" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(only_a) or "—"}</text>'
                f'<text x="460" y="175" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(only_b) or "—"}</text>'
                f'<text x="340" y="390" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(only_c) or "—"}</text>'
                f'<text x="340" y="150" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(ab) or "—"}</text>'
                f'<text x="255" y="330" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(ac) or "—"}</text>'
                f'<text x="425" y="330" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(bc) or "—"}</text>'
                f'<text x="340" y="255" font-size="12" font-weight="700" fill="var(--text-color)" text-anchor="middle">{", ".join(abc) or "—"}</text>')
        vh = 480
    return f'<svg width="100%" viewBox="0 0 680 {vh}">{circles}{text}</svg>'

def get_standard_phrase_options(grade):
    if grade not in STANDARD_PHRASE_BANK: return ["Custom (type below)"]
    return STANDARD_PHRASE_BANK[grade] + ["Custom (type below)"]

_PDF_IDENT_RE = re.compile(r"^Ident:\s*([A-Z][A-Z0-9\-]+)\s+([\d.]+)\s*/\s*(\d{1,2}-[A-Za-z]{3}-\d{2})")
_PDF_PAGE_HEADER_RE = re.compile(r"^FCOM\s+\S.*\d{1,2}:\d{2}:\d{2}\s*[AP]M$")
_PDF_TAB_HEADER_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}.*DocuNet:FCOM$")
_PDF_URL_RE = re.compile(r"^https?://")
_PDF_SUPERSCRIPT_RE = re.compile(r"^L\d+$")
_PDF_PAGENUM_RE = re.compile(r"^\d{1,3}/\d{1,3}$")

def _pdf_is_skippable_noise(line):
    l = line.strip()
    if not l: return True
    if _PDF_PAGE_HEADER_RE.match(l) or _PDF_TAB_HEADER_RE.match(l) or _PDF_URL_RE.match(l): return True
    if _PDF_SUPERSCRIPT_RE.match(l) or _PDF_PAGENUM_RE.match(l): return True
    if l.lower() == "uncontrolled": return True
    return False

def _pdf_looks_like_title(line):
    l = line.strip()
    if _pdf_is_skippable_noise(l): return False
    if not l or len(l) > 90: return False
    if l.lower().startswith(("ident:", "criteria:", "applicable to:", "note:", "if ", "the ", "to ", "when ", "this ", "for ")): return False
    if l.endswith((".", ",", ";")): return False
    letters = [c for c in l if c.isalpha()]
    if not letters: return False
    upper_frac = sum(c.isupper() for c in letters) / len(letters)
    return l.startswith("[") or upper_frac > 0.6

def extract_fcom_procedures(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = full_text.split("\n")
    ident_positions = []
    for i, line in enumerate(lines):
        m = _PDF_IDENT_RE.match(line.strip())
        if m: ident_positions.append((i, m.group(1)))
    blocks = []
    current_title = None
    for idx, (line_i, code) in enumerate(ident_positions):
        j = line_i - 1
        while j >= 0 and _pdf_is_skippable_noise(lines[j]): j -= 1
        title_parts = []
        while j >= 0 and _pdf_looks_like_title(lines[j]):
            title_parts.insert(0, lines[j].strip())
            j -= 1
        if title_parts: current_title = " ".join(title_parts)
        end_line = ident_positions[idx + 1][0] if idx + 1 < len(ident_positions) else len(lines)
        content = "\n".join(lines[line_i:end_line]).strip()
        blocks.append({"title": current_title, "ident_code": code, "content": content})
    grouped = []
    for b in blocks:
        if grouped and grouped[-1]["title"] == b["title"]:
            grouped[-1]["content"] += "\n\n" + b["content"]
            grouped[-1]["ident_codes"].append(b["ident_code"])
        else: grouped.append({"title": b["title"], "content": b["content"], "ident_codes": [b["ident_code"]]})
    return grouped


_LESSON_ITEM_RE = re.compile(r"^\s*(\d{1,2})\s+(.{3,200})$")
_LESSON_SECTION_START_RE = re.compile(r"EXPANDED DETAIL", re.IGNORECASE)
_LESSON_SECTION_END_RE = re.compile(r"MAP OF RISKS", re.IGNORECASE)
_LESSON_BODY_START_RE = re.compile(r"^(\d|ATC|At |As |The |When |Insert|Ref |REFERENCE|Wind |Below |Once |Clear |Cancel )", re.IGNORECASE)

def detect_pdf_format(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    lines = full_text.split("\n")
    if any(_PDF_IDENT_RE.match(l.strip()) for l in lines): return "fcom_abnormal"
    if (re.search(r"lesson plan", full_text, re.IGNORECASE) and re.search(r"\bEBT\b", full_text) and _LESSON_SECTION_START_RE.search(full_text)):
        return "lesson_plan_syllabus"
    return "unknown"

def extract_lesson_plan_items(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    lines = full_text.split("\n")
    starts = [i for i, l in enumerate(lines) if _LESSON_SECTION_START_RE.search(l)]
    ends = [i for i, l in enumerate(lines) if _LESSON_SECTION_END_RE.search(l)]
    best_span, best_len = (0, len(lines)), 0
    for s in starts:
        candidate_ends = [e for e in ends if e > s]
        e = min(candidate_ends) if candidate_ends else len(lines)
        if e - s > best_len: best_len, best_span = e - s, (s, e)
    start_idx, end_idx = best_span
    scoped = lines[start_idx:end_idx]
    item_positions = []
    for i, l in enumerate(scoped):
        m = _LESSON_ITEM_RE.match(l.strip())
        if m:
            num = int(m.group(1))
            if 1 <= num <= 99: item_positions.append((i, num, m.group(2).strip()))
    blocks = []
    for idx, (line_i, num, title) in enumerate(item_positions):
        full_title = title
        next_i = line_i + 1
        if (next_i < len(scoped) and not title.endswith((".", ":", ")", "!")) and not _LESSON_ITEM_RE.match(scoped[next_i].strip())):
            cont = scoped[next_i].strip()
            if cont and len(cont) < 80 and not _LESSON_BODY_START_RE.match(cont):
                full_title = f"{title} {cont}"
        end_line = item_positions[idx + 1][0] if idx + 1 < len(item_positions) else len(scoped)
        content = "\n".join(scoped[line_i:end_line]).strip()
        blocks.append({"title": full_title, "content": content, "ident_codes": [f"ITEM-{num}"]})
    return blocks

def extract_scenarios_auto(pdf_file):
    fmt = detect_pdf_format(pdf_file)
    if hasattr(pdf_file, "seek"): pdf_file.seek(0)
    if fmt == "fcom_abnormal": return fmt, extract_fcom_procedures(pdf_file)
    elif fmt == "lesson_plan_syllabus": return fmt, extract_lesson_plan_items(pdf_file)
    else: return fmt, []

def match_extracted_titles_to_scenarios(extracted_blocks, scenario_events):
    norm_to_event = {_normalize_event_name(e): e for e in scenario_events}
    norm_keys = list(norm_to_event.keys())
    results = []
    for block in extracted_blocks:
        title = block["title"] or ""
        norm_title = _normalize_event_name(title)
        matched_event, confidence = None, None
        if norm_title in norm_to_event:
            matched_event, confidence = norm_to_event[norm_title], "exact"
        else:
            close = difflib.get_close_matches(norm_title, norm_keys, n=1, cutoff=0.85)
            if close: matched_event, confidence = norm_to_event[close[0]], "fuzzy"
        results.append({**block, "matched_event": matched_event, "match_confidence": confidence})
    return results

@st.cache_data(show_spinner="Running data health checks...")
def compute_data_health_report(scenarios_source, competency_source, scenario_obs_source,
                                cache_token_a=None, cache_token_b=None, cache_token_c=None):
    report = {
        "scenarios_ok": False, "scenarios_issues": [], "scenarios_count": 0,
        "keypams_ok": False, "keypams_issues": [], "keypams_count": 0,
        "obs_ok": False, "obs_issues": [], "obs_count": 0,
        "coverage": None,
    }

    scen_events = []
    if scenarios_source is not None:
        try:
            df_raw = pd.read_csv(scenarios_source, encoding="cp1252") if isinstance(scenarios_source, (str, os.PathLike)) else pd.read_csv(scenarios_source, encoding="cp1252")
            for _, row in df_raw.iterrows():
                event, dod = row.iloc[0], row.iloc[1]
                if pd.isna(event) or pd.isna(dod) or len(str(event).strip()) <= 2: continue
                scen_events.append((str(event).strip(), dod))
            report["scenarios_count"] = len(scen_events)
            seen = {}
            for ev, dod in scen_events: seen.setdefault(ev, []).append(dod)
            dupes = {ev: dods for ev, dods in seen.items() if len(dods) > 1}
            if dupes: report["scenarios_issues"].append(("warn", f"{len(dupes)} event name(s) appear more than once: " + ", ".join(dupes.keys())))
            report["scenarios_ok"] = True
        except Exception as e:
            report["scenarios_issues"].append(("error", f"Could not read Scenarios.csv: {e}"))

    comp_lookup = {}
    norm_keys = []
    if competency_source is not None:
        try:
            df_comp = pd.read_excel(competency_source)
            df_comp.columns = [str(c).strip() for c in df_comp.columns]
            if "SA" in df_comp.columns and "SAW" not in df_comp.columns: df_comp = df_comp.rename(columns={"SA": "SAW"})
            comp_cols = [c for c in COMPETENCY_KEYS if c in df_comp.columns]
            report["keypams_count"] = len(df_comp)
            norm_to_originals = {}
            for _, crow in df_comp.iterrows():
                norm_k = _normalize_event_name(crow["Event"])
                active = [c for c in comp_cols if pd.notna(crow[c]) and float(crow[c]) >= 1]
                norm_to_originals.setdefault(norm_k, []).append((crow["Event"], active))
                comp_lookup[norm_k] = active
                norm_keys.append(norm_k)
            report["keypams_ok"] = True
        except Exception as e:
            report["keypams_issues"].append(("error", f"Could not read Keypams.xlsx: {e}"))

    ob_library_for_coverage = {}
    if scenario_obs_source is not None:
        try:
            df_obs = pd.read_excel(scenario_obs_source, sheet_name="Scenario OBs")
            df_obs.columns = [str(c).strip() for c in df_obs.columns]
            filled_count = 0
            for _, row in df_obs.iterrows():
                event = row.get("EVENT")
                if pd.isna(event) or str(event).strip().upper().startswith("EXAMPLE"): continue
                obs_codes = []
                for i in (1, 2, 3, 4):
                    comp, text, ref = row.get(f"OB{i}_COMPETENCY"), row.get(f"OB{i}_TEXT"), row.get(f"OB{i}_REF")
                    if pd.notna(comp) and str(comp).strip() != "" and pd.notna(text) and str(text).strip() != "" and pd.notna(ref) and str(ref).strip() != "":
                        comp_clean = str(comp).strip().upper()
                        if comp_clean in COMPETENCY_KEYS: obs_codes.append(comp_clean)
                pta = row.get("PTA")
                if pd.notna(pta) and str(pta).strip() != "": filled_count += 1
                if obs_codes:
                    norm_k = _normalize_event_name(event)
                    ob_library_for_coverage[norm_k] = event
            report["obs_count"] = filled_count
            report["obs_ok"] = True
        except Exception as e:
            report["obs_issues"].append(("error", f"Could not read Scenario_Observable_Behaviours.xlsx: {e}"))

    if scen_events:
        tiers = {"keyword": [], "obs_library": [], "keypams": [], "none": []}
        unique_events = list(dict.fromkeys(ev for ev, _ in scen_events))
        for ev in unique_events:
            ev_upper = ev.replace("\xa0", " ").upper()
            if any(any(kw in ev_upper for kw in exd["keywords"]) for exk, exd in PROGRAM_SYLLABUS_EXERCISES.items() if exk != "EX-00_GENERIC"):
                tiers["keyword"].append(ev)
                continue
            norm_ev = _normalize_event_name(ev)
            if norm_ev in ob_library_for_coverage or (ob_library_for_coverage and difflib.get_close_matches(norm_ev, list(ob_library_for_coverage.keys()), n=1, cutoff=0.72)):
                tiers["obs_library"].append(ev)
                continue
            hit = comp_lookup.get(norm_ev)
            if hit is None and norm_keys:
                tokens_ev = set(norm_ev.split())
                for k in norm_keys:
                    tokens_k = set(k.split())
                    inter = tokens_ev & tokens_k
                    if len(inter) >= 2 and len(inter) / max(len(tokens_ev), len(tokens_k)) > 0.45:
                        hit = comp_lookup[k]; break
            if hit is None and norm_keys:
                close = difflib.get_close_matches(norm_ev, norm_keys, n=1, cutoff=0.5)
                if close: hit = comp_lookup[close[0]]
            if hit: tiers["keypams"].append(ev)
            else: tiers["none"].append(ev)
        report["coverage"] = tiers

    return report


if "nav_page" not in st.session_state:
    st.session_state.nav_page = "splash"

with st.sidebar:
    _theme_label = "☀️  Light mode" if st.session_state.theme == "dark" else "🌙  Dark mode"
    if st.button(_theme_label, key="theme_toggle"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()
    st.markdown(f"<div style='height:1px;background:{KM_BORDER};margin:10px 0 12px;'></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.10em;font-weight:700;margin-bottom:6px;'>WORKFLOW</div>", unsafe_allow_html=True)
    for _pg, _icon, _lbl in [("splash","🏠","Home / Welcome"),("session","⚙️","Generate EBT Program"), ("orca","📥","Upload Existing Program")]:
        if st.button(f"{_icon}  {_lbl}", key=f"nav_{_pg}"):
            st.session_state.nav_page = _pg; st.rerun()
    st.markdown(f"<div style='height:1px;background:{KM_BORDER};margin:10px 0 12px;'></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.10em;font-weight:700;margin-bottom:6px;'>REFERENCE</div>", unsafe_allow_html=True)
    for _pg, _icon, _lbl in [("history","🗂","Candidate History"),("health","🩺","Data Health"),
                               ("debrief","📊","Session Debrief"),("scenarios","🎯","Scenario Browser"),
                               ("grading","📐","Grading Standard")]:
        if st.button(f"{_icon}  {_lbl}", key=f"nav_{_pg}"):
            st.session_state.nav_page = _pg; st.rerun()
    st.markdown(f"<div style='height:1px;background:{KM_BORDER};margin:12px 0 10px;'></div>", unsafe_allow_html=True)
    _capt = st.session_state.get("capt_name","Capt. Unassigned")
    _fo   = st.session_state.get("fo_name","F/O Unassigned")
    st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.08em;font-weight:700;margin-bottom:3px;'>CAPT. CANDIDATE</div><div style='font-size:11px;color:{KM_TEXT};font-weight:700;margin-bottom:8px;'>{_capt}</div><div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.08em;font-weight:700;margin-bottom:3px;'>F/O CANDIDATE</div><div style='font-size:11px;color:{KM_TEXT};font-weight:700;'>{_fo}</div>", unsafe_allow_html=True)

_page = st.session_state.nav_page

# Global Data Fetching Functions
def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(base_path, relative_path)
    if os.path.exists(local_path): return local_path
    parent_path = os.path.join(os.path.dirname(base_path), relative_path)
    return parent_path if os.path.exists(parent_path) else local_path

def find_bundled_file(candidate_names):
    for name in candidate_names:
        path = resource_path(name)
        if os.path.exists(path): return path
    return None

def source_display_name(source):
    if source is None: return None
    name = getattr(source, "name", None)
    if name: return os.path.basename(name)
    return os.path.basename(str(source))


# Only draw top-level metrics/headers if we are not on the splash screen
if _page != "splash":
    _final_df = st.session_state.get("final_df")
    _n_slots = len(st.session_state.get("slot_configurations_cache",[]))
    _active_comps = set()
    if _final_df is not None and not _final_df.empty and "COMPETENCIES" in _final_df.columns:
        for _codes in _final_df["COMPETENCIES"]:
            if isinstance(_codes,(list,tuple,set)): _active_comps.update(_codes)
    _m1,_m2,_m3,_m4 = st.columns(4)
    with _m1: st.markdown(f"<div class='km-metric'><div class='km-metric-lbl'>Slots</div><div class='km-metric-val'>{_n_slots:02d}</div><div class='km-metric-sub'>of 12 configured</div></div>",unsafe_allow_html=True)
    with _m2: st.markdown(f"<div class='km-metric'><div class='km-metric-lbl'>Competencies</div><div class='km-metric-val'>{len(_active_comps)}/9</div><div class='km-metric-sub'>{' · '.join(sorted(_active_comps)) or 'Build plan to see'}</div></div>",unsafe_allow_html=True)
    _smode_short = {"EBT Evaluation": "EBT", "OPC": "OPC", "LPC": "LPC", "LOE": "LOE", "OBT": "OBT"}.get(st.session_state.get("session_mode","EBT Evaluation"), st.session_state.get("session_mode","EBT")[:6])
    with _m3: st.markdown(f"<div class='km-metric'><div class='km-metric-lbl'>Session Type</div><div class='km-metric-val'>{_smode_short}</div><div class='km-metric-sub'>{st.session_state.get('sim_id','Not set')}</div></div>",unsafe_allow_html=True)
    with _m4: st.markdown(f"<div class='km-metric'><div class='km-metric-lbl'>OB Profiles</div><div class='km-metric-val'>{len(SCENARIO_OB_LIBRARY)}</div><div class='km-metric-sub'>scenario-specific</div></div>",unsafe_allow_html=True)
    st.markdown("<div style='height:8px;'></div>",unsafe_allow_html=True)

if _page == "splash":
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("### ✈️ Welcome to the Optimizer")
    st.markdown("The aim of this program is twofold:")
    st.markdown("""
    **A. Create a Session from Scratch**
    Generate an EBT session by defining phases, DOD levels, and required competencies. The engine will select appropriate independent/random failures.
    
    **B. Use an Existing Program**
    Upload your operator simulator syllabus PDF, parse it, and extract the exercises in order to conduct a standardised OB and ORCA workflow.
    """)
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    c_btn1, c_btn2, _ = st.columns([1, 1, 2])
    with c_btn1:
        if st.button("⚙️ Generate EBT Program", type="primary"):
            st.session_state.nav_page = "session"
            st.rerun()
    with c_btn2:
        if st.button("📥 Upload Existing Program"):
            st.session_state.nav_page = "orca"
            st.rerun()

# ==========================================
# FILE UPLOADERS & GLOBAL DATA LOADING 
# (Only drawn on "session" page, but cache persists)
# ==========================================
ds_status_placeholder = st.empty()

if _page == "session":
    col_left, col_right = st.columns([2, 1])
    with col_left:
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>SES</span><span class='panel-title-text'>SLOT CONFIGURATION</span></div>", unsafe_allow_html=True)
            if "slot_list" not in st.session_state:
                st.session_state.slot_list = [{"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False}, {"phase": 2, "dod": 2, "role": "PF Focus", "type": "Any", "mandatory": True}, {"phase": 6, "dod": 2, "role": "PM Focus", "type": "Any", "mandatory": False}, {"phase": 7, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False}]
            btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 4])
            with btn_c1:
                if st.button("➕ Add"):
                    if len(st.session_state.slot_list) < 12:
                        st.session_state.slot_list.append({"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False})
                        st.rerun()
            with btn_c2:
                if st.button("➖ Remove"):
                    if len(st.session_state.slot_list) > 1:
                        st.session_state.slot_list.pop()
                        st.rerun()

            hdr_cols = st.columns([0.5, 1.3, 0.8, 1.1, 1.5, 1.3, 1.6, 0.9])
            for col, label in zip(hdr_cols, ["Slot", "Phase", "DOD", "Role", "Category", "ATA", "Competency", "Pin"]): col.markdown(f"<div style='font-size:11px; opacity:0.65; font-weight:600;'>{label}</div>", unsafe_allow_html=True)

            slot_configurations = []
            for i in range(len(st.session_state.slot_list)):
                slot_data = st.session_state.slot_list[i]
                row_cols = st.columns([0.5, 1.3, 0.8, 1.1, 1.5, 1.3, 1.6, 0.9])
                with row_cols[0]: st.markdown(f"<div style='padding-top:8px; font-weight:600;'>{i+1}</div>", unsafe_allow_html=True)
                with row_cols[1]: p_val = st.selectbox("Phase", options=ALL_PHASE_KEYS, index=ALL_PHASE_KEYS.index(slot_data["phase"]) if slot_data["phase"] in ALL_PHASE_KEYS else 0, format_func=lambda x: f"Ph {x}: {PHASE_NAMES[x].split('–')[1].strip()}", key=f"phase_sel_{i}", label_visibility="collapsed")
                with row_cols[2]: d_val = st.selectbox("DOD", options=[1, 2, 3], index=slot_data["dod"]-1, format_func=lambda x: f"DOD {x}", key=f"dod_sel_{i}", label_visibility="collapsed")
                with row_cols[3]: role_val = st.selectbox("Role", options=ROLE_OPTIONS, index=ROLE_OPTIONS.index(slot_data["role"]) if slot_data["role"] in ROLE_OPTIONS else 0, key=f"role_sel_{i}", label_visibility="collapsed")
                with row_cols[4]: type_val = st.selectbox("Category", options=["Any", "Technical Failure", "Non-Technical / CRM (Non-ATA)", "ATA Specific"], key=f"type_sel_{i}", label_visibility="collapsed")
                with row_cols[5]:
                    ata_val = st.number_input("ATA Chapter", min_value=11, max_value=80, key=f"ata_sel_{i}", label_visibility="collapsed") if type_val == "ATA Specific" else None
                    if type_val != "ATA Specific": st.markdown("<div style='opacity:0.4; font-size:12px; padding-top:8px;'>—</div>", unsafe_allow_html=True)
                with row_cols[6]: comp_val = st.selectbox("Target Competency", options=["Any"] + list(COMPETENCY_KEYS.keys()), format_func=lambda x: x if x == "Any" else f"{x} – {COMPETENCY_KEYS[x]}", key=f"comp_sel_{i}", label_visibility="collapsed")
                with row_cols[7]: is_mandatory = st.checkbox("Pin", value=slot_data.get("mandatory", False), key=f"mand_sel_{i}", label_visibility="collapsed")
                slot_configurations.append({"slot": i + 1, "phase": int(p_val), "dod": int(d_val), "role": role_val, "type": type_val, "ata": ata_val, "competency": comp_val, "mandatory": is_mandatory})

        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>SES</span><span class='panel-title-text'>Session Metadata & Device Setup</span></div>", unsafe_allow_html=True)
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1: session_mode = st.selectbox("Training Focus / Mode", ["EBT Evaluation & Coaching", "EBT Line-Oriented Assessment", "Recurrent Check (LPC/OPC)"], key="session_mode")
            with m_col2:
                capt_name = st.text_input("Captain Name", key="capt_name")
                capt_staff_no = st.text_input("Captain Staff No.", value="", placeholder="e.g. KM10234")
            with m_col3:
                fo_name = st.text_input("First Officer Name", key="fo_name")
                fo_staff_no = st.text_input("F/O Staff No.", value="", placeholder="e.g. KM10567")
            with m_col4: sim_id = st.text_input("Sim / Device ID", key="sim_id")

            p_col1, p_col2, p_col3, p_col4 = st.columns(4)
            with p_col1: aircraft_type = st.text_input("Aircraft Type", key="aircraft_type")
            with p_col2: program_code = st.text_input("Program", key="program_code")
            with p_col3: session_duration_h = st.number_input("Duration (h)", min_value=0.5, max_value=12.0, step=0.5, key="session_duration_h")
            with p_col4: max_dod_threshold = st.number_input("Total DOD Ceiling", min_value=1, max_value=30, value=6, step=1)
            allow_fallback = st.checkbox("Enable Smart Fallback (use closest available DOD if exact match missing)", value=True)

        ds_col, doc_col = st.columns(2)
        with ds_col:
            with st.container(border=True):
                st.markdown("<div class='panel-head'><span class='panel-code'>CSV</span><span class='panel-title-text'>DATA SOURCES</span></div>", unsafe_allow_html=True)
                
                # Fetching Widgets (and caching to Session State if visible)
                tmp_scen = st.file_uploader("Scenarios.csv", type=["csv"], label_visibility="collapsed")
                tmp_comp = st.file_uploader("Keypams.xlsx (optional)", type=["xlsx"], label_visibility="collapsed")
                tmp_obs = st.file_uploader("Scenario_Observable_Behaviours.xlsx (optional)", type=["xlsx"], label_visibility="collapsed")
                
                if tmp_scen is not None: st.session_state['up_scen_cache'] = tmp_scen
                if tmp_comp is not None: st.session_state['up_comp_cache'] = tmp_comp
                if tmp_obs is not None: st.session_state['up_obs_cache'] = tmp_obs
                
                ds_status_placeholder = st.empty()
        with doc_col:
            with st.container(border=True):
                st.markdown("<div class='panel-head'><span class='panel-code'>DOC</span><span class='panel-title-text'>DOCUMENT REFERENCES</span></div>", unsafe_allow_html=True)
                for tag, title in DOCUMENT_REFERENCES.items():
                    st.markdown(f"<div class='doc-ref-row'><span class='doc-ref-tag'>[{tag}]</span> {title}</div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: left; font-size: 10.5px; color: rgba(255,255,255,0.35); margin-top: 10px;'>Designed by Shawn Abela · v5.0 2026</div>", unsafe_allow_html=True)


# Data Source variables mapped unconditionally using the cache
uploaded_scen = st.session_state.get('up_scen_cache')
uploaded_comp = st.session_state.get('up_comp_cache')
uploaded_scenario_obs = st.session_state.get('up_obs_cache')

scenarios_source = uploaded_scen if uploaded_scen is not None else (find_bundled_file(["Scenarios.csv"]) or resource_path("Scenarios.csv"))
competency_source = uploaded_comp if uploaded_comp is not None else find_bundled_file(["Keypams.xlsx"])
scenario_obs_source = uploaded_scenario_obs if uploaded_scenario_obs is not None else find_bundled_file(["Scenario_Observable_Behaviours.xlsx", "Scenario_Observable_Behaviours_TEMPLATE.xlsx"])

if scenario_obs_source is not None:
    SCENARIO_OB_LIBRARY, scenario_obs_err = load_scenario_obs_library(scenario_obs_source, _file_cache_token(scenario_obs_source))

@st.cache_data(show_spinner="Loading and caching matrix scenarios...")
def load_scenario_database(s_source, c_source, cache_token_a=None, cache_token_b=None):
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
                if "SA" in df_comp.columns and "SAW" not in df_comp.columns: df_comp = df_comp.rename(columns={"SA": "SAW"})
                comp_cols = [c for c in COMPETENCY_KEYS.keys() if c in df_comp.columns]
                if comp_cols and "Event" in df_comp.columns:
                    for _, crow in df_comp.iterrows():
                        k_event = str(crow["Event"])
                        norm_k = _normalize_event_name(k_event)
                        active_comps = [c for c in comp_cols if pd.notna(crow[c]) and float(crow[c]) >= 1]
                        comp_lookup[norm_k] = active_comps
                    match_stats["keypams_loaded"] = True
            except Exception: pass
        norm_keys = list(comp_lookup.keys())
        matched_events = set()
        def resolve_competencies(ev, phase, ata):
            codes = set()
            ev_upper = str(ev).replace("\xa0", " ").upper()
            for ex_key, ex_data in PROGRAM_SYLLABUS_EXERCISES.items():
                if ex_key == "EX-00_GENERIC": continue
                if any(kw in ev_upper for kw in ex_data["keywords"]): codes.update(ex_data["cbta_focus"])
            if codes: return sorted(codes)
            if SCENARIO_OB_LIBRARY:
                norm_ev_lib = _normalize_event_name(ev)
                lib_entry = SCENARIO_OB_LIBRARY.get(norm_ev_lib)
                if lib_entry is None:
                    close_lib = difflib.get_close_matches(norm_ev_lib, list(SCENARIO_OB_LIBRARY.keys()), n=1, cutoff=0.72)
                    if close_lib: lib_entry = SCENARIO_OB_LIBRARY[close_lib[0]]
                if lib_entry: return sorted(lib_entry["cbta_focus"])
            if comp_lookup:
                norm_ev = _normalize_event_name(ev)
                hit = comp_lookup.get(norm_ev)
                if hit is None:
                    tokens_ev = set(norm_ev.split())
                    for k in norm_keys:
                        tokens_k = set(k.split())
                        if len(tokens_ev & tokens_k) >= 2 and len(tokens_ev & tokens_k) / max(len(tokens_ev), len(tokens_k)) > 0.45:
                            hit = comp_lookup[k]; break
                if hit is None:
                    close = difflib.get_close_matches(norm_ev, norm_keys, n=1, cutoff=0.5)
                    if close: hit = comp_lookup[close[0]]
                if hit:
                    matched_events.add(ev); codes.update(hit)
            if codes: return sorted(codes)
            _, _, fallback_focus = get_exercise_for_event(ev, ata)
            return sorted(fallback_focus)
        df["COMPETENCIES"] = df.apply(lambda r: resolve_competencies(r["EVENT"], r["PHASES"], r.get("ATA")), axis=1)
        match_stats["matched_events"] = len(matched_events)
        return df, match_stats
    except Exception as e: return None, str(e)

df, match_stats = load_scenario_database(scenarios_source, competency_source, _file_cache_token(scenarios_source), _file_cache_token(competency_source))

def _source_tag(source, uploaded_widget_value):
    if uploaded_widget_value is not None: return "uploaded this session"
    if source is not None: return f"auto-loaded from `{source_display_name(source)}`"
    return "not supplied"

if _page == "session":
    with ds_status_placeholder.container():
        scen_ok = df is not None and not df.empty
        scen_status = "LOADED" if scen_ok else "MISSING"
        scen_cls = "ds-status-loaded" if scen_ok else "ds-status-optional"
        st.markdown(f"<div class='ds-row'><span>Scenarios.csv</span><span class='{scen_cls}'>{scen_status}</span></div>", unsafe_allow_html=True)
        if scen_ok: st.markdown(f"<div class='ds-detail'>{len(df)} scenario/phase rows</div>", unsafe_allow_html=True)
        elif isinstance(match_stats, str): st.caption(f"⚠️ {match_stats}")

        comp_status = "LOADED" if (scen_ok and match_stats.get("keypams_loaded")) else "OPTIONAL"
        comp_cls = "ds-status-loaded" if comp_status == "LOADED" else "ds-status-optional"
        st.markdown(f"<div class='ds-row'><span>Keypams.xlsx</span><span class='{comp_cls}'>{comp_status}</span></div>", unsafe_allow_html=True)
        if comp_status == "LOADED":
            _total = match_stats.get("total_events", 0); _matched = match_stats.get("matched_events", 0)
            _pct = (_matched / _total * 100) if _total else 0
            st.markdown(f"<div class='ds-detail'>cross-matched {_matched}/{_total} events ({_pct:.0f}%)</div>", unsafe_allow_html=True)

        obs_status = "LOADED" if (scenario_obs_source is not None and SCENARIO_OB_LIBRARY) else "OPTIONAL"
        obs_cls = "ds-status-loaded" if obs_status == "LOADED" else "ds-status-optional"
        st.markdown(f"<div class='ds-row'><span>Scenario_Observable_Behaviours.xlsx</span><span class='{obs_cls}'>{obs_status}</span></div>", unsafe_allow_html=True)
        if obs_status == "LOADED": st.markdown(f"<div class='ds-detail'>{len(SCENARIO_OB_LIBRARY)} scenario-specific profile(s)</div>", unsafe_allow_html=True)
        st.caption(f"Scenarios: {_source_tag(scenarios_source, uploaded_scen)} · Keypams: {_source_tag(competency_source, uploaded_comp)} · Scenario OBs: {_source_tag(scenario_obs_source, uploaded_scenario_obs)}")

    with col_right:
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>SUM</span><span class='panel-title-text'>SESSION SUMMARY</span></div>", unsafe_allow_html=True)
            mandatory_count = sum(1 for c in slot_configurations if c.get("mandatory"))
            dur_h = float(st.session_state.session_duration_h)
            dur_str = f"{int(dur_h):02d}:{int(round((dur_h % 1) * 60)):02d} h"
            sum_c1, sum_c2 = st.columns(2)
            with sum_c1: st.markdown(f"<div class='stat-label'>Slots</div><div class='stat-value stat-value-accent'>{len(slot_configurations)} / 12</div>", unsafe_allow_html=True)
            with sum_c2: st.markdown(f"<div class='stat-label'>Mandatory</div><div class='stat-value stat-value-green'>{mandatory_count:02d}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            sum_c3, sum_c4 = st.columns(2)
            with sum_c3: st.markdown(f"<div class='stat-label'>Aircraft</div><div class='stat-value'>{st.session_state.aircraft_type}</div>", unsafe_allow_html=True)
            with sum_c4: st.markdown(f"<div class='stat-label'>Program</div><div class='stat-value'>{st.session_state.program_code}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            sum_c5, sum_c6 = st.columns(2)
            with sum_c5: st.markdown(f"<div class='stat-label'>Session Type</div><div class='stat-value stat-value-accent'>{SESSION_MODE_SHORT.get(st.session_state.session_mode, st.session_state.session_mode)}</div>", unsafe_allow_html=True)
            with sum_c6: st.markdown(f"<div class='stat-label'>Duration</div><div class='stat-value'>{dur_str}</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>COV</span><span class='panel-title-text'>COMPETENCY COVERAGE</span></div>", unsafe_allow_html=True)
            _generated_df = st.session_state.get("final_df")
            if _generated_df is not None and not _generated_df.empty and "COMPETENCIES" in _generated_df.columns:
                active_comps = set()
                for codes in _generated_df["COMPETENCIES"]:
                    if isinstance(codes, (list, tuple, set)): active_comps.update(codes)
                coverage_note = f"{len(active_comps)} of 9 core competencies actually targeted by the {len(_generated_df)} scenario(s) in the built session."
            else:
                active_comps = {c["competency"] for c in slot_configurations if c.get("competency") and c["competency"] != "Any"}
                coverage_note = f"{len(active_comps)} of 9 core competencies pinned via slot filters so far — build the session plan to see real per-scenario coverage."
            comp_order = ["APK", "COM", "FPA", "FPM", "KNO", "LTW", "PSD", "SAW", "WLM"]
            badges_html = "".join(f"<span class='comp-badge {'comp-badge-active' if code in active_comps else 'comp-badge-inactive'}' title='{COMPETENCY_KEYS.get(code, code)}'>{code}</span>" for code in comp_order)
            st.markdown(f"<div>{badges_html}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:11px; color:{KM_TEXT_MUTED}; margin-top:8px;'>{coverage_note}</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>GEN</span><span class='panel-title-text'>GENERATE</span></div>", unsafe_allow_html=True)
            if st.button("📄  BUILD SESSION PLAN", type="primary"):
                st.session_state.trigger_generation = True

    if st.session_state.get("trigger_generation", False):
        if df is None or df.empty:
            st.session_state.trigger_generation = False
            st.warning("Can't build a session plan — Scenarios.csv isn't loaded.")
        else:
            selected_events = []
            used_titles = set()
            for cfg in slot_configurations:
                if cfg.get("mandatory") and cfg["phase"] == 2:
                    forced_match = df[(df["PHASES"] == 2) & (df["DOD"] == cfg["dod"])]
                    if not forced_match.empty: picked = forced_match.iloc[0].to_dict()
                    else: picked = {"EVENT": "Engine Failure After V1 (SIM-EFATO-01)", "DOD": cfg["dod"], "PHASES": 2, "scenario_id": "SC-FORCED", "COMPETENCIES": ["FPM", "APK", "PSD"]}
                    picked["SLOT"] = cfg["slot"]; picked["ROLE"] = cfg["role"]; picked["PHASE_NAME"] = PHASE_NAMES[cfg["phase"]]
                    selected_events.append(picked); used_titles.add(picked["EVENT"])
                    continue
                cands = df[(df["PHASES"] == cfg["phase"]) & (df["DOD"] == cfg["dod"]) & (~df["EVENT"].isin(used_titles))]
                cands = apply_category_filter(cands, cfg)
                cands = apply_competency_filter(cands, cfg.get("competency", "Any"))
                if cands.empty and allow_fallback:
                    cands = df[(df["PHASES"] == cfg["phase"]) & (df["DOD"] == cfg["dod"]) & (~df["EVENT"].isin(used_titles))]
                if not cands.empty:
                    picked = cands.sample(n=1).iloc[0].to_dict()
                    picked["SLOT"] = cfg["slot"]; picked["ROLE"] = cfg["role"]; picked["PHASE_NAME"] = PHASE_NAMES[cfg["phase"]]
                    selected_events.append(picked); used_titles.add(picked["EVENT"])
            st.session_state.final_df = pd.DataFrame(selected_events).sort_values("SLOT").reset_index(drop=True)
            st.session_state.slot_overrides = {}
            st.session_state.slot_competencies = {}
            st.session_state.trigger_generation = False
            st.session_state.db_session_id = None
            
            # --- NEW: EASA Compliance Matrix ---
            def evaluate_easa_compliance(session_df, total_dod, max_dod):
                flags = []
                phases_present = session_df["PHASES"].tolist()
                
                # Check Core Phase Distribution (Takeoff, Approach/Landing)
                if not any(p in [1, 2] for p in phases_present):
                    flags.append("Missing Phase 1/2 (Pre-flight / Take-off) module.")
                if not any(p in [6, 7] for p in phases_present):
                    flags.append("Missing Phase 6/7 (Approach / Landing) module.")
                    
                # Check Key CBTA Competency Targets
                all_comps = set(c for comp_list in session_df["COMPETENCIES"] for c in comp_list)
                if "FPM" not in all_comps and "FPA" not in all_comps:
                    flags.append("Flight Path Management (FPM/FPA) is not actively targeted in this session.")
                if "PSD" not in all_comps and "WLM" not in all_comps:
                    flags.append("No active targeting of Problem Solving & Decision Making (PSD) or Workload Management (WLM).")
                    
                # Check DOD Thresholds
                if total_dod > max_dod:
                    flags.append(f"Total DOD ({total_dod}) exceeds the recommended maximum ceiling ({max_dod}) for a single evaluation phase.")
                elif total_dod < (max_dod * 0.5):
                    flags.append(f"Total DOD ({total_dod}) is unusually low, risking insufficient evidence gathering.")
                    
                return flags
                
            st.session_state.compliance_flags = evaluate_easa_compliance(
                st.session_state.final_df, 
                st.session_state.final_df["DOD"].sum(), 
                max_dod_threshold
            )
            # -----------------------------------
            
            st.session_state.just_generated = True
            st.rerun()

    if st.session_state.pop("just_generated", False):
        st.success("Session Profile Generated!")
        
        # Display Compliance Matrix
        c_flags = st.session_state.get("compliance_flags", [])
        if not c_flags:
            st.markdown("<div class='status-badge-ok'>✓ EASA AMC1 ORO.FC.231 Assessment Structure: COMPLIANT</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='status-badge-warn'>⚠️ EASA AMC1 ORO.FC.231 Structure Warnings:</div>", unsafe_allow_html=True)
            for flag in c_flags:
                st.markdown(f"<div style='font-size:12px; color:{KM_AMBER}; margin-left:14px;'>• {flag}</div>", unsafe_allow_html=True)


# Persist the km-header block at the very top of EVERY page, including the splash screen
_data_ok = df is not None and not df.empty
_draft_active = ("final_df" in st.session_state) and not st.session_state.get("db_session_id")
_synced_active = bool(st.session_state.get("db_session_id"))
_session_label = f"S-{st.session_state['db_session_id']}" if st.session_state.get("db_session_id") else "DRAFT"

header_placeholder.markdown(f"""
<div class="km-header">
    <div class="km-header-left">
        <div class="km-logo">✈️</div>
        <div>
            <div class="km-title">EBT SESSION OPTIMIZER</div>
            <div class="km-subtitle">{st.session_state.get('aircraft_type', 'A320-214')} · {st.session_state.get('session_mode', 'EBT Evaluation & Coaching')} · {st.session_state.get('program_code', 'EBT-2026')}</div>
        </div>
    </div>
    <div class="km-header-right">
        <div class="km-meta">
            <div class="km-meta-label">Device</div>
            <div class="km-meta-value">{st.session_state.get('sim_id', 'KM Malta A320 STD2.2')[:16]}</div>
        </div>
        <div class="km-meta">
            <div class="km-meta-label">Session</div>
            <div class="km-meta-value km-meta-value-accent">{_session_label}</div>
        </div>
        <div class="km-meta">
            <div class="km-meta-label">Capt</div>
            <div class="km-meta-value">{st.session_state.get('capt_name', 'Unassigned')}</div>
        </div>
        <div class="km-meta">
            <div class="km-meta-label">F/O</div>
            <div class="km-meta-value">{st.session_state.get('fo_name', 'Unassigned')}</div>
        </div>
        <div class="km-pills">
            <div class="km-pill"><span class="km-dot {'km-dot-green' if _data_ok else 'km-dot-gray'}"></span>DATA</div>
            <div class="km-pill"><span class="km-dot {'km-dot-amber' if _draft_active else 'km-dot-gray'}"></span>DRAFT</div>
            <div class="km-pill"><span class="km-dot {'km-dot-green' if _synced_active else 'km-dot-gray'}"></span>SYNCED</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


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
        Spacer(1, 4), HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0284C7'), spaceAfter=4)
    ]
    table_data = [[Paragraph("<b>Slot</b>", cell_bold), Paragraph("<b>Phase / Event</b>", cell_bold), Paragraph("<b>Role / DOD</b>", cell_bold), Paragraph("<b>Target Actions & Observable Behaviors (OBs)</b>", cell_bold), Paragraph("<b>Grade (1-5) & Notes</b>", cell_bold)]]
    for _, row in df_session.iterrows():
        slot_id = int(row["SLOT"])
        _, seq_data, _ = get_exercise_for_event(row['EVENT'], row.get('ATA'))
        combined_details = ""
        for step in seq_data:
            combined_details += f"<b>{step['phase_name']}</b><br/><i>Action:</i> {step['pta']}<br/>"
            for ob in step['obs']: combined_details += f"<font color='#006600'>✓ {ob['text']}</font> <i>[{ob['ref']}]</i><br/>"
            combined_details += "<br/>"
        phase_event_str = f"<b>{row['PHASE_NAME']}</b><br/>{row['EVENT']}"
        role_dod_str = f"{row.get('ROLE','PF')}<br/>DOD {row['DOD']}"
        grade_val = grades_dict.get(slot_id, 3)
        note_val = notes_dict.get(slot_id, "Standard performance.")
        comps_val = comp_dict.get(slot_id, [])
        comps_str = ", ".join(comps_val) if comps_val else "—"
        grade_str = f"<b>Grade: {grade_val}/5</b><br/><i>{GRADE_DESCRIPTORS.get(grade_val, '')}</i><br/><b>Competencies:</b> {comps_str}<br/><b>Notes:</b> {note_val}"
        table_data.append([Paragraph(str(slot_id), cell_style), Paragraph(phase_event_str, cell_style), Paragraph(role_dod_str, cell_style), Paragraph(combined_details, cell_style), Paragraph(grade_str, cell_style)])

    t = Table(table_data, colWidths=[24, 105, 52, 195, 162])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F4F8')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0284C7')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 3), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
    ]))
    
    # --- NEW: Generate and Embed Radar Chart ---
    if HAS_MATPLOTLIB and comp_dict:
        # Calculate session averages for the chart
        comp_totals = {c: [] for c in COMPETENCY_KEYS}
        for s_id, comps in comp_dict.items():
            g = grades_dict.get(s_id, 3)
            for c in comps:
                if c in comp_totals:
                    comp_totals[c].append(g)
        
        avgs = {c: (sum(v)/len(v) if v else 0) for c, v in comp_totals.items()}
        labels = list(avgs.keys())
        values = list(avgs.values())
        
        if any(values):
            # Close the polygon
            values += values[:1]
            angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
            angles += angles[:1]
            
            fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
            ax.fill(angles, values, color='#0284C7', alpha=0.25)
            ax.plot(angles, values, color='#0284C7', linewidth=2)
            ax.set_ylim(0, 5)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_yticks([1, 2, 3, 4, 5])
            ax.set_yticklabels(['1', '2', '3', '4', '5'], color="grey", size=7)
            plt.title("Session Competency Profile", size=10, color="#0284C7", y=1.1)
            
            # Save to memory buffer
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', bbox_inches='tight', dpi=150)
            chart_buffer.seek(0)
            plt.close(fig)
            
            # Append to PDF elements
            elements.append(Spacer(1, 10))
            elements.append(Image(chart_buffer, width=250, height=250))
            elements.append(Spacer(1, 10))
    # -------------------------------------------
    
    elements.extend([t])
    doc.build(elements)
    buffer.seek(0)
    return buffer


if _page == "history":
    # SESSION HISTORY — two-column layout matching design mockup
    # Left: session table  |  Right: grade trend + candidate summary
    h_left, h_right = st.columns([2.1, 1])
    with h_left:
        st.markdown(f"<div class='panel-head'><span class='panel-code'>HST</span><span class='panel-title-text'>SESSION HISTORY</span></div>", unsafe_allow_html=True)
        lookup_staff_no = st.text_input("Staff number", value="", placeholder="e.g. KM10234", key="history_lookup_staff_no", label_visibility="collapsed")
        st.caption("Enter staff number to load candidate history")
        if lookup_staff_no.strip():
            candidate_info, grade_rows = get_candidate_history(lookup_staff_no)
            if candidate_info is None:
                st.warning(f"No candidate found with staff number '{lookup_staff_no}'.")
            else:
                sessions = candidate_info["sessions"]
                table_rows = []
                for s in sessions:
                    s_id, s_date, sim_id, s_type, capt, fo, total_dod, max_dod = s
                    s_grades = [cg for sid, _, _, g, _, cg, obs, _ in grade_rows if sid == s_id and obs and cg is not None]
                    avg_g = round(sum(s_grades)/len(s_grades), 1) if s_grades else None
                    result = "PASS" if (avg_g and avg_g >= 3) else ("RETRAIN" if avg_g else "—")
                    table_rows.append({"SESSION": s_id, "DATE": str(s_date)[:10] if s_date else "—", "CANDIDATE": capt or fo or "—", "TYPE": s_type or "—", "AVG": f"{avg_g}" if avg_g else "—", "RESULT": result})
                if table_rows:
                    hcols = st.columns([1.2, 1.2, 1.4, 0.6, 0.5, 0.8])
                    for col, lbl in zip(hcols, ["SESSION","DATE","CANDIDATE","TYPE","AVG","RESULT"]):
                        with col: st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.08em;font-weight:700;padding:4px 0 6px;border-bottom:1px solid {KM_BORDER};'>{lbl}</div>", unsafe_allow_html=True)
                    for row in table_rows:
                        rcols = st.columns([1.2, 1.2, 1.4, 0.6, 0.5, 0.8])
                        res_color = KM_GREEN if row["RESULT"] == "PASS" else ("#E53E3E" if row["RESULT"] == "RETRAIN" else KM_TEXT_MUTED)
                        res_bg = "rgba(52,211,153,.15)" if row["RESULT"] == "PASS" else ("rgba(229,62,62,.15)" if row["RESULT"] == "RETRAIN" else "transparent")
                        with rcols[0]: st.markdown(f"<div style='padding:8px 0;font-size:12px;font-weight:700;color:{KM_AMBER};border-bottom:1px solid {KM_BORDER};'>{row['SESSION']}</div>", unsafe_allow_html=True)
                        with rcols[1]: st.markdown(f"<div style='padding:8px 0;font-size:12px;color:{KM_TEXT};border-bottom:1px solid {KM_BORDER};'>{row['DATE']}</div>", unsafe_allow_html=True)
                        with rcols[2]: st.markdown(f"<div style='padding:8px 0;font-size:12px;color:{KM_TEXT};border-bottom:1px solid {KM_BORDER};'>{row['CANDIDATE']}</div>", unsafe_allow_html=True)
                        with rcols[3]: st.markdown(f"<div style='padding:8px 0;font-size:12px;color:{KM_TEXT_MUTED};border-bottom:1px solid {KM_BORDER};'>{row['TYPE']}</div>", unsafe_allow_html=True)
                        with rcols[4]: st.markdown(f"<div style='padding:8px 0;font-size:13px;font-weight:700;color:{KM_TEXT};border-bottom:1px solid {KM_BORDER};'>{row['AVG']}</div>", unsafe_allow_html=True)
                        with rcols[5]: st.markdown(f"<div style='padding:6px 0;border-bottom:1px solid {KM_BORDER};'><span style='background:{res_bg};color:{res_color};font-size:9px;font-weight:800;padding:3px 8px;border-radius:4px;border:1px solid {res_color}44;letter-spacing:.05em;'>{row['RESULT']}</span></div>", unsafe_allow_html=True)
                    st.session_state["_hist_rows"] = table_rows
                    st.session_state["_hist_grade_rows"] = grade_rows
                else:
                    st.info("No graded sessions found for this candidate.")
        else:
            st.session_state.pop("_hist_rows", None)
    with h_right:
        st.markdown(f"<div class='panel-head'><span class='panel-code'>TRD</span><span class='panel-title-text'>GRADE TREND</span></div>", unsafe_allow_html=True)
        hist_rows = st.session_state.get("_hist_rows", [])
        if hist_rows:
            avgs = [float(r["AVG"]) for r in reversed(hist_rows) if r["AVG"] != "—"]
            if avgs:
                st.line_chart(pd.DataFrame({"Grade": avgs}), height=180, color=KM_AMBER)
        else:
            st.markdown(f"<div style='height:180px;background:{KM_PANEL};border-radius:6px;border:1px solid {KM_BORDER};display:flex;align-items:center;justify-content:center;'><span style='color:{KM_TEXT_MUTED};font-size:11px;'>No data yet</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='panel-head'><span class='panel-code'>SUM</span><span class='panel-title-text'>CANDIDATE SUMMARY</span></div>", unsafe_allow_html=True)
        if hist_rows:
            n_sessions = len(hist_rows)
            pass_count = sum(1 for r in hist_rows if r["RESULT"] == "PASS")
            retrain_count = sum(1 for r in hist_rows if r["RESULT"] == "RETRAIN")
            pass_rate = f"{round(pass_count/n_sessions*100)}%" if n_sessions else "—"
            all_avgs = [float(r["AVG"]) for r in hist_rows if r["AVG"] != "—"]
            rolling_avg = round(sum(all_avgs)/len(all_avgs), 1) if all_avgs else "—"
            sm1, sm2 = st.columns(2)
            with sm1: st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:3px;'>SESSIONS</div><div style='font-size:22px;font-weight:800;color:{KM_GREEN};'>{n_sessions:02d}</div>", unsafe_allow_html=True)
            with sm2: st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:3px;'>PASS RATE</div><div style='font-size:22px;font-weight:800;color:{KM_GREEN};'>{pass_rate}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='height:10px;'></div>", unsafe_allow_html=True)
            sm3, sm4 = st.columns(2)
            with sm3: st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:3px;'>ROLLING AVG</div><div style='font-size:22px;font-weight:800;color:{KM_AMBER};'>{rolling_avg}</div>", unsafe_allow_html=True)
            with sm4: st.markdown(f"<div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:3px;'>RETRAINS</div><div style='font-size:22px;font-weight:800;color:{KM_TEXT};'>{retrain_count:02d}</div>", unsafe_allow_html=True)
        else:
            st.caption("Enter a staff number to load candidate history.")


if _page == "grading":
    st.markdown("#### 📐 KM Malta Airlines Official Grading Standard")
    st.markdown("Sourced directly from **Operations Manual Part D, §3.1.1.1 (Grading System)**. Reference this before and during grading — every instructor grading against the same published wording is what makes grading consistent across the training department.")
    st.markdown("<b>1–5 Grading Scale</b>", unsafe_allow_html=True)
    for g in [5, 4, 3, 2, 1]:
        badge = "status-badge-ok" if g >= 2 else "status-badge-warn"
        st.markdown(f'<div style="display:flex; gap:10px; align-items:flex-start; margin-bottom:6px;"><div class="{badge}" style="min-width:150px;">Grade {g} ({GRADE_LABELS[g]})</div><div style="font-size:12.5px; opacity:0.9;">{GRADE_DESCRIPTORS[g]}</div></div>', unsafe_allow_html=True)
    st.markdown("<div style='font-size:11px; opacity:0.65; margin-top:4px;'>Grade 2 is a pass, not a fail — but OM-D requires it to be reviewed by DCT. Grade 1 triggers the Below Adequate Grading process (APP.5.1.11 during training/LIFUS, APP.5.1.12 during a check).</div>", unsafe_allow_html=True)
    st.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
    st.markdown("<b>Core Competencies & Key Performance Indicators (KPIs)</b>", unsafe_allow_html=True)
    sel_comp_ref = st.selectbox("View KPIs and per-grade wording for:", options=list(COMPETENCY_KEYS.keys()), format_func=lambda x: f"{x} – {COMPETENCY_KEYS[x]}", key="grading_standard_comp_select")
    st.markdown("<div style='font-size:11.5px; opacity:0.7; margin-bottom:6px;'>Key Performance Indicators:</div>", unsafe_allow_html=True)
    for kpi in COMPETENCY_KPIS.get(sel_comp_ref, []): st.markdown(f"<div style='font-size:12.5px; margin-bottom:3px;'>• {kpi}</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    for g in [5, 4, 3, 2, 1]:
        badge = "status-badge-ok" if g >= 2 else "status-badge-warn"
        st.markdown(f'<div style="display:flex; gap:10px; align-items:flex-start; margin-bottom:6px;"><div class="{badge}" style="min-width:64px;">Grade {g}</div><div style="font-size:12px; opacity:0.9;">{COMPETENCY_GRADE_TEXT.get(sel_comp_ref, {}).get(g, "")}</div></div>', unsafe_allow_html=True)
    st.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
    st.markdown("<b>Flight Phase Definitions</b>", unsafe_allow_html=True)
    for p, desc in PHASE_DEFINITIONS.items(): st.markdown(f"<div style='font-size:12px; margin-bottom:3px;'><b>{PHASE_NAMES[p]}:</b> {desc}</div>", unsafe_allow_html=True)


if _page == "session":
    with st.container(border=True):
        st.markdown("#### ✈️ Aircraft Mass & Balance (IOS Parameters)")
        i_col1, i_col2, i_col3, i_col4, i_col5 = st.columns(5)
        with i_col1:
            gw_val = st.number_input("GW (kg x1000)", min_value=40.0, max_value=79.0, value=54.6, step=0.5)
            gw_cg = st.number_input("GW CG (%)", min_value=15.0, max_value=40.0, value=29.0, step=0.1)
        with i_col2:
            zfw_val = st.number_input("ZFW (kg x1000)", min_value=35.0, max_value=64.3, value=47.0, step=0.5)
            zfw_cg = st.number_input("ZFW CG (%)", min_value=15.0, max_value=40.0, value=31.0, step=0.1)
        with i_col3: total_fuel = st.number_input("Total Fuel (kg x1000)", min_value=1.5, max_value=19.0, value=7.6, step=0.1)
        with i_col4: alt_asl = st.number_input("Init Alt (ft ASL)", min_value=0, max_value=39000, value=293)
        with i_col5: qnh_val = st.number_input("QNH (hPa)", min_value=950, max_value=1050, value=1013)

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

        st.markdown(f'<div class="jepp-card"><div class="jepp-header">✈️ JEPPESEN SCHEMATIC LAYOUT & BRIEFING — {sel_apt_key.upper()}</div><b>ICAO:</b> {apt_data["icao"]} &nbsp;&nbsp;|&nbsp;&nbsp; <b>ELEV:</b> {apt_data["elev"]} FT &nbsp;&nbsp;|&nbsp;&nbsp; <b>ILS / LOC:</b> {apt_data["ils"]}<br/><b>PUBLISHED RUNWAYS:</b> {" | ".join(apt_data["rwy"])}<br/><b>SCHEMATIC ALIGNMENT:</b> [RWY {apt_data["rwy"][0]}] <==============================> [ILS GLIDESLOPE 3.0°]</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### 🌐 IOS Current Conditions & Live METAR Integration")
        live_metar_str = fetch_live_metar(apt_data['icao'])
        st.markdown(f'<div class="ios-card" style="border-left: 3px solid #0284C7;"><div class="ios-label">Live METAR Feed ({apt_data["icao"]})</div><div style="font-family: \'Geist Mono\', monospace; color: #0284C7; font-size: 13px; margin-top: 4px;">{live_metar_str}</div></div>', unsafe_allow_html=True)

        # --- NEW: Parse METAR for defaults ---
        metar_data = parse_metar_to_ios(live_metar_str)
        default_dir = metar_data.get('dir', 360)
        default_spd = metar_data.get('spd', 0)
        default_gust = metar_data.get('gust', 0)
        default_temp = metar_data.get('temp', 14)
        default_qnh = metar_data.get('qnh', 1013)
        # -------------------------------------

        w_card1, w_card2 = st.columns(2)
        with w_card1:
            st.markdown("<b style='color:#0284C7;'>🌬️ Surface Wind & Atmosphere</b>", unsafe_allow_html=True)
            wc1, wc2, wc3 = st.columns(3)
            with wc1: wind_dir = st.number_input("Wind Dir (°M)", min_value=0, max_value=360, value=default_dir, step=10)
            with wc2: wind_spd = st.number_input("Wind Speed (kt)", min_value=0, max_value=70, value=default_spd)
            with wc3: wind_gust = st.number_input("Wind Gust (kt)", min_value=0, max_value=90, value=default_gust)
            wind_str = f"{wind_dir:03d}°M / {wind_spd} kt" + (f" G {wind_gust} kt" if wind_gust > 0 else "")
            tc1, tc2, tc3 = st.columns(3)
            with tc1: oat_temp = st.number_input("Aircraft OAT (°C)", min_value=-40, max_value=50, value=default_temp)
            with tc2:
                isa_standard = 15 - (2 * (apt_elev / 1000))
                isa_dev_calc = int(oat_temp - isa_standard)
                isa_dev = st.number_input("ISA Dev (°C)", min_value=-30, max_value=30, value=isa_dev_calc)
            with tc3: qnh_weather = st.number_input("QNH Ref (hPa)", min_value=950, max_value=1050, value=default_qnh)

        with w_card2:
            st.markdown("<b style='color:#0284C7;'>🌧️ Runway Surface & Visibility Parameters</b>", unsafe_allow_html=True)
            rc1, rc2 = st.columns(2)
            with rc1: rcam_code = st.selectbox("Runway Cnd Ref (RCAM x/x/x)", ["6/6/6 – Dry", "5/5/5 – Good (Frost / Wet <= 3mm)", "4/4/4 – Good to Medium", "3/3/3 – Medium", "2/2/2 – Medium to Poor", "1/1/1 – Poor (Ice)", "0/0/0 – Less than Poor"])
            with rc2: precip_ref = st.selectbox("Precipitation Ref", ["None", "Light Rain", "Moderate Rain", "Heavy Rain", "Light Snow", "Moderate Snow"])
            vc1, vc2 = st.columns(2)
            with vc1: vis_rvr_str = st.selectbox("Visibility / RVR", ["250.00 km (CAVOK)", "10.00 km", "5000 m", "1500 m", "550 m (CAT I)", "300 m (CAT II)", "125 m (CAT III B)"], index=0)
            with vc2: rwy_lighting = st.selectbox("Runway Lighting", ["Off (0)", "Level 1", "Level 2", "Level 3 (High / Standard)", "Level 4 (Max / LVO)"], index=3)

# Default to generic values if fields aren't populated by interaction logic above yet
wind_spd = wind_spd if 'wind_spd' in locals() else 0
wind_gust = wind_gust if 'wind_gust' in locals() else 0
rcam_code = rcam_code if 'rcam_code' in locals() else "6/6/6 – Dry"
vis_rvr_str = vis_rvr_str if 'vis_rvr_str' in locals() else "250.00 km (CAVOK)"
ios_env_summary_str = f"Wind: {wind_str if 'wind_str' in locals() else '360°M/0kt'} | OAT: {oat_temp if 'oat_temp' in locals() else 14}°C (ISA {isa_dev if 'isa_dev' in locals() else 0:+d}°C) | QNH: {qnh_weather if 'qnh_weather' in locals() else 1013} hPa | Rwy Cnd: {rcam_code.split('–')[0].strip()} | Precip: {precip_ref if 'precip_ref' in locals() else 'None'} | Vis: {vis_rvr_str}"
ios_summary_str = f"Apt: {apt_ref if 'apt_ref' in locals() else 'LMML/13'} | GW: {gw_val if 'gw_val' in locals() else 54.6}t (CG {gw_cg if 'gw_cg' in locals() else 29}%) | ZFW: {zfw_val if 'zfw_val' in locals() else 47}t | Fuel: {total_fuel if 'total_fuel' in locals() else 7.6}t | QNH: {qnh_val if 'qnh_val' in locals() else 1013}hPa | Env: {ios_env_summary_str}"

if df is not None: df["TEM_THREAT"], df["TEM_ERROR"] = zip(*df.apply(lambda r: derive_tem_tags(r["EVENT"], r["PHASES"], wind_spd, wind_gust, rcam_code, vis_rvr_str), axis=1))


if _page == "session":
    if "final_df" in st.session_state:
        if "slot_overrides" not in st.session_state: st.session_state.slot_overrides = {}
        final_df = st.session_state.final_df
        for idx, row in final_df.iterrows():
            s_id = int(row["SLOT"])
            if s_id in st.session_state.slot_overrides:
                ov_data = st.session_state.slot_overrides[s_id]
                final_df.loc[idx, "EVENT"] = ov_data["EVENT"]
                final_df.loc[idx, "DOD"] = ov_data["DOD"]
                src_match = df[(df["EVENT"] == ov_data["EVENT"]) & (df["DOD"] == ov_data["DOD"])]
                if not src_match.empty:
                    final_df.loc[idx, "ATA"] = src_match.iloc[0]["ATA"]
                    final_df.at[idx, "COMPETENCIES"] = src_match.iloc[0]["COMPETENCIES"]

        total_dod = final_df["DOD"].sum()
        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1: st.metric(label="Active Session Slots", value=f"{len(final_df)} Modules")
        with m_col2: st.metric(label="Cumulative Session DOD", value=f"{total_dod} / {max_dod_threshold} Target")
        with m_col3:
            compliance_status = "Within Ceiling" if total_dod <= max_dod_threshold else "Exceeds Ceiling"
            st.metric(label="DOD Compliance Status", value=compliance_status)

        st.markdown("#### ✈️ Sequenced Simulator Session & EBT Competency Rubric (Tab 1 Independent/Random Failures)")
        instructor_grades = {}; instructor_notes = {}; slot_competencies = {}
        
        for idx, row in final_df.iterrows():
            slot_num = int(row['SLOT'])
            event_title = row['EVENT']
            dod = int(row['DOD'])
            phase_num = int(row['PHASES'])
            role = row.get('ROLE', 'PF Focus')
            exercise_title, sequence_data, _ = get_exercise_for_event(event_title, row.get('ATA'))

            with st.expander(f"Slot #{slot_num:02d} — {row['PHASE_NAME']} | DOD {dod} | {event_title} ({role})", expanded=False):
                st.markdown(f"<div style='font-size:11px; opacity:0.65; margin-bottom:6px;'>OB profile: <b>{exercise_title}</b></div>", unsafe_allow_html=True)
                swap_pool = df[(df["PHASES"] == phase_num) & (df["DOD"] == dod)]
                swap_options = sorted(swap_pool["EVENT"].unique().tolist())
                if event_title not in swap_options: swap_options = [event_title] + swap_options
                current_idx = swap_options.index(event_title)
                swap_choice = st.selectbox(f"🔁 Swap Event (Slot #{slot_num:02d}) — same Phase & DOD", options=swap_options, index=current_idx, key=f"swap_event_{slot_num}", help="Pick a different event if the auto-selected one doesn't fit well alongside the other slots — only events matching this slot's Phase and DOD are offered, so the session's DOD balance stays valid.")
                if swap_choice != event_title:
                    st.session_state.slot_overrides[slot_num] = {"EVENT": swap_choice, "DOD": dod}
                    st.rerun()
                st.markdown("<div style='font-size:11px; opacity:0.6; margin-bottom:6px;'>&#9201;&#65039; Phase sequence &amp; OB markers</div>", unsafe_allow_html=True)
                st.markdown(build_ob_flow_html(sequence_data), unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:11.5px; opacity:0.7; margin-bottom:4px;'>Competencies exercised by this scenario:</div>{competency_chip_row(row.get('COMPETENCIES', []))}", unsafe_allow_html=True)
                demonstrated = st.multiselect(f"✅ Competencies Actually Demonstrated (Slot #{slot_num:02d})", options=list(COMPETENCY_KEYS.keys()), default=list(row.get("COMPETENCIES", [])), format_func=lambda x: f"{x} – {COMPETENCY_KEYS[x]}", key=f"comp_demo_{slot_num}")
                slot_competencies[slot_num] = demonstrated
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                g_col1, g_col2 = st.columns([1, 2])
                with g_col1:
                    instructor_grades[slot_num] = st.selectbox(f"KM Malta Grade (Slot #{slot_num:02d})", options=[5, 4, 3, 2, 1], index=2, format_func=lambda x: f"Grade {x} ({GRADE_LABELS[x]})", key=f"grade_slot_{slot_num}")
                    grade_now_for_display = instructor_grades[slot_num]
                    st.markdown(f"<div style='font-size:11px; opacity:0.7; font-style:italic; margin-top:-6px;'>{GRADE_DESCRIPTORS[grade_now_for_display]}</div>", unsafe_allow_html=True)
                    if demonstrated:
                        with st.expander("📐 Official per-competency wording at this grade (OM-D §3.1.1.1)", expanded=False):
                            for code in demonstrated: st.markdown(f"<div style='font-size:11px; margin-bottom:6px;'><b style='color:#0284C7;'>{code}</b> — {COMPETENCY_GRADE_TEXT.get(code, {}).get(grade_now_for_display, '')}</div>", unsafe_allow_html=True)
                with g_col2:
                    grade_now = instructor_grades[slot_num]
                    phrase_choice = st.selectbox(f"Standardized Comment (Slot #{slot_num:02d})", options=get_standard_phrase_options(grade_now), key=f"phrase_slot_{slot_num}")
                    if phrase_choice == "Custom (type below)": instructor_notes[slot_num] = st.text_input(f"Custom Note (Slot #{slot_num:02d})", value="", key=f"note_slot_{slot_num}")
                    else:
                        extra_detail = st.text_input(f"Optional detail (Slot #{slot_num:02d})", value="", key=f"note_extra_{slot_num}")
                        instructor_notes[slot_num] = f"{phrase_choice} {extra_detail.strip()}" if extra_detail.strip() else phrase_choice

        st.session_state.slot_competencies = slot_competencies
        st.markdown("---")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv_export = final_df.to_csv(index=False)
            st.download_button(label="📥 Download Session Schedule (CSV)", data=csv_export, file_name=f"sim_session_DOD_{max_dod_threshold}.csv", mime="text/csv", key="download_csv_button")
        with col_exp2:
            pdf_data = generate_pdf_briefing(final_df, instructor_grades, instructor_notes, slot_competencies, total_dod, max_dod_threshold, session_mode, capt_name, fo_name, sim_id, ios_summary_str)
            st.download_button(label="📄 Download Completed KM Malta EBT PDF Record", data=pdf_data, file_name=f"km_malta_ebt_record_{max_dod_threshold}.pdf", mime="application/pdf", key="download_pdf_button")

        slots_for_db = []
        for _, row in final_df.iterrows():
            s_num = int(row["SLOT"]); grade = instructor_grades.get(s_num); demonstrated = slot_competencies.get(s_num, [])
            slots_for_db.append({
                "slot_number": s_num, "event_title": row["EVENT"], "phase_number": int(row["PHASES"]), "dod": int(row["DOD"]),
                "role_focus": row.get("ROLE", ""), "instructor_grade": grade, "instructor_notes": instructor_notes.get(s_num, ""),
                "competencies": [{"code": c, "grade": grade, "observed": True, "note": ""} for c in demonstrated],
            })
        saved_session_id, linked_candidate = save_session_to_history(
            st.session_state.get("db_session_id"), sim_id, session_mode, capt_staff_no, capt_name, fo_staff_no, fo_name,
            int(total_dod), int(max_dod_threshold), "session_setup", slots_for_db
        )
        st.session_state.db_session_id = saved_session_id
        if linked_candidate: st.caption(f"✓ Saved to history database (session #{saved_session_id}, linked to staff number).")
        else: st.caption(f"✓ Saved to history database (session #{saved_session_id}) — add a Captain/F.O. staff number above to make this retrievable by candidate history.")


if _page == "health":
    st.markdown("#### 🩺 Data Health Check")
    st.caption("Runs the same audit previously done by hand on Scenarios.csv, Keypams.xlsx, and Scenario_Observable_Behaviours.xlsx — duplicate/collision detection, dead rows, and a real coverage breakdown. Re-runs automatically whenever any of the three files change.")
    health = compute_data_health_report(scenarios_source, competency_source, scenario_obs_source, _file_cache_token(scenarios_source), _file_cache_token(competency_source), _file_cache_token(scenario_obs_source))

    def _render_issue_list(issues, empty_message):
        if not issues:
            st.markdown(f"<div class='status-badge-ok' style='display:inline-block;'>✓ {empty_message}</div>", unsafe_allow_html=True)
            return
        for severity, msg in issues:
            icon = {"error": "🔴", "warn": "🟠", "info": "⚪"}.get(severity, "⚪")
            st.markdown(f"<div class='ds-row' style='font-weight:400;'>{icon}&nbsp; {msg}</div>", unsafe_allow_html=True)

    hcol1, hcol2 = st.columns(2)
    with hcol1:
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>CSV</span><span class='panel-title-text'>Scenarios.csv</span></div>", unsafe_allow_html=True)
            if health["scenarios_ok"]:
                st.caption(f"{health['scenarios_count']} valid scenario rows checked.")
                _render_issue_list(health["scenarios_issues"], "No duplicates, whitespace issues, or DoD range problems found.")
            else: st.info("Not loaded — nothing to check yet.")
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>XLS</span><span class='panel-title-text'>Scenario Observable Behaviours</span></div>", unsafe_allow_html=True)
            if health["obs_ok"]:
                st.caption(f"{health['obs_count']} filled rows checked.")
                _render_issue_list(health["obs_issues"], "No collisions, partial fills, or invalid competency codes found.")
            else: st.info("Not loaded (optional file) — nothing to check yet.")

    with hcol2:
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>XLS</span><span class='panel-title-text'>Keypams.xlsx</span></div>", unsafe_allow_html=True)
            if health["keypams_ok"]:
                st.caption(f"{health['keypams_count']} rows checked.")
                _render_issue_list(health["keypams_issues"], "No duplicate/collision or dead-flag rows found.")
            else: st.info("Not loaded (optional file) — nothing to check yet.")
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>COV</span><span class='panel-title-text'>Real Coverage Breakdown</span></div>", unsafe_allow_html=True)
            cov = health["coverage"]
            if cov:
                total = sum(len(v) for v in cov.values())
                st.caption(f"How each of the {total} distinct scenarios actually gets its competencies, in priority order.")
                for key, label in [("keyword", "Dedicated hand-built exercises"), ("obs_library", "Scenario Observable Behaviours"), ("keypams", "Keypams.xlsx"), ("none", "Nothing — generic ATA-family fallback")]:
                    n = len(cov[key])
                    pct = (n / total * 100) if total else 0
                    bar_color = KM_GREEN if key != "none" else KM_AMBER
                    st.markdown(f"<div style='margin-bottom:6px;'><div style='display:flex; justify-content:space-between; font-size:12px;'><span>{label}</span><span style='color:{bar_color}; font-weight:700;'>{n} ({pct:.0f}%)</span></div><div style='background:{KM_PANEL_ALT}; border-radius:4px; height:6px; margin-top:3px;'><div style='background:{bar_color}; width:{pct:.0f}%; height:6px; border-radius:4px;'></div></div></div>", unsafe_allow_html=True)
                if cov["none"]:
                    with st.expander(f"See the {len(cov['none'])} event(s) with no specific data anywhere"):
                        for ev in cov["none"]: st.markdown(f"- {ev}")
            else: st.info("Load Scenarios.csv to see a coverage breakdown.")


if _page == "orca":
    st.markdown("#### 📋 OPC & ORCA Workflow Suite (Uploaded Syllabus Analysis & Debrief)")
    st.markdown("Upload your operator simulator syllabus PDF to analyze structured syllabus exercises. Each Observable Behaviour below gets its own Observe → Record → Classify/Assess entry, tied to the same published 1-5 grading scale used elsewhere in the app.")

    with st.container(border=True):
        st.markdown("##### 📄 Simulator Program PDF Uploader & Exercise Detection")
        if not HAS_PYPDF: st.warning("⚠️ `pypdf` library is not installed in your current environment. Running in default exercise mode.")
        uploaded_prog_pdf = st.file_uploader("Upload Operator Simulator Syllabus / Lesson Plan (PDF)", type=["pdf"], key="prog_pdf_uploader_main")
        parsed_exercise_keys = list(PROGRAM_SYLLABUS_EXERCISES.keys())
        
        if uploaded_prog_pdf is not None and HAS_PYPDF:
            try:
                detected_format, extracted_blocks = extract_scenarios_auto(uploaded_prog_pdf)
                pdf_text = "\n".join(b["content"] for b in extracted_blocks) if extracted_blocks else ""
                fallback_page_count = None
                if not pdf_text:
                    uploaded_prog_pdf.seek(0)
                    reader = pypdf.PdfReader(uploaded_prog_pdf)
                    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    fallback_page_count = len(reader.pages)

                if fallback_page_count is not None: st.success(f"✓ Parsed {fallback_page_count} page(s) from uploaded syllabus PDF (layout not recognized by the structured extractor — falling back to plain-text keyword search).")
                else: st.success(f"✓ Parsed via {detected_format} extraction: {len(extracted_blocks)} block(s) found.")

                detected_keys = []
                if extracted_blocks:
                    title_to_key = {v["title"]: k for k, v in PROGRAM_SYLLABUS_EXERCISES.items()}
                    matched_blocks = match_extracted_titles_to_scenarios(extracted_blocks, list(title_to_key.keys()))
                    detected_keys = [title_to_key[m["matched_event"]] for m in matched_blocks if m["matched_event"]]

                for e_key, e_data in PROGRAM_SYLLABUS_EXERCISES.items():
                    if e_key not in detected_keys and any(kw in pdf_text.upper() for kw in e_data["keywords"]): detected_keys.append(e_key)
                if detected_keys:
                    parsed_exercise_keys = detected_keys
                    st.info(f"Identified {len(detected_keys)} specific exercise profiles directly from PDF content.")
            except Exception as e:
                st.error(f"Error reading PDF content: {e}")

        st.markdown("<b>Select Exercises from Syllabus for Full OB & ORCA Analysis:</b>", unsafe_allow_html=True)
        col_sel_all, col_sel_multi = st.columns([1, 4])
        with col_sel_all: select_all_ex = st.checkbox("Select All Uploaded Exercises", value=True, key="select_all_uploaded_ex")
        with col_sel_multi:
            default_selected = parsed_exercise_keys if select_all_ex else parsed_exercise_keys[:2]
            selected_ex_keys = st.multiselect("Uploaded Syllabus Exercises to Evaluate:", options=parsed_exercise_keys, default=default_selected, format_func=lambda x: PROGRAM_SYLLABUS_EXERCISES[x]["title"], key="multiselect_uploaded_ex", label_visibility="collapsed")

    if selected_ex_keys:
        total_obs_count = sum(len(step["obs"]) for k in selected_ex_keys for step in PROGRAM_SYLLABUS_EXERCISES[k]["sequence"])
        observed_count = 0; all_ob_grades = []
        for k in selected_ex_keys:
            for s_idx, step in enumerate(PROGRAM_SYLLABUS_EXERCISES[k]["sequence"]):
                for ob_idx in range(len(step["obs"])):
                    if st.session_state.get(f"orc_observed_{k}_{s_idx}_{ob_idx}"):
                        observed_count += 1
                        all_ob_grades.append(st.session_state.get(f"orc_grade_{k}_{s_idx}_{ob_idx}", 3))
        below_standard_count = sum(1 for g in all_ob_grades if g <= 2)
        avg_ob_grade = (sum(all_ob_grades) / len(all_ob_grades)) if all_ob_grades else 0.0

        st.markdown("##### 📊 Uploaded Program ORCA & CBTA Real-Time Metrics")
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Syllabus Modules", f"{len(selected_ex_keys)} Exercises")
        with m2: st.metric("Target OBs Tracked", f"{total_obs_count} Behaviors")
        with m3: st.metric("OBs Observed & Graded", f"{observed_count}/{total_obs_count}")
        with m4: st.metric("Below-Standard OBs (≤2)", f"{below_standard_count}", delta=None if below_standard_count == 0 else "review", delta_color="inverse")
        st.markdown(f"<div style='font-size:10.5px; opacity:0.6; margin-top:-4px;'>Average grade across observed OBs: {avg_ob_grade:.1f}/5. This reflects actual per-OB grading this session.</div>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("##### 📌 Granular 4-Phase Uploaded Syllabus Exercise Breakdown & ORCA Workflow")

        uploaded_grades = {}; uploaded_notes = {}; uploaded_comp_mapping = {}
        for e_key in selected_ex_keys:
            ex_data = PROGRAM_SYLLABUS_EXERCISES[e_key]
            with st.container(border=True):
                st.markdown(f"#### ✈️ {ex_data['title']}")
                st.markdown(f"<div style='font-size: 13px; margin-bottom: 4px;'><b>Uploaded Syllabus Stressor / Failure:</b> {ex_data['stressor']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 13px; color: #0284C7; font-weight: 600; margin-bottom: 12px;'>🎯 CBTA Competency Targets: {', '.join(ex_data['cbta_focus'])}</div>", unsafe_allow_html=True)
                for s_idx, step in enumerate(ex_data["sequence"]):
                    st.markdown(f"<b style='color: #0284C7; font-size: 14px;'>{step['phase_name']}</b>", unsafe_allow_html=True)
                    st.markdown(f"<div style='background:rgba(2,132,199,0.05); border-radius:4px; border-left: 3px solid #0284C7; padding: 10px 12px; margin-bottom: 16px; margin-top: 4px;'><div style='font-size: 13px; opacity: 0.9; margin-bottom: 6px;'><b>Primary Target Action (PTA):</b> <i>{step['pta']}</i></div><b style='font-size:12px; opacity:0.8;'>Observable Behaviors — Observe, Record, Classify &amp; Assess:</b></div>", unsafe_allow_html=True)
                    
                    for ob_idx, ob in enumerate(step["obs"]):
                        comp_tag = ob.get("comp", extract_ob_competency(ob["text"]) or "GEN")
                        obs_key = f"orc_observed_{e_key}_{s_idx}_{ob_idx}"
                        grade_key = f"orc_grade_{e_key}_{s_idx}_{ob_idx}"
                        note_key = f"orc_note_{e_key}_{s_idx}_{ob_idx}"
                        
                        # --- NEW: Fetch persisted values or defaults ---
                        is_obs = st.session_state.orca_state.get(obs_key, False)
                        cur_grade = st.session_state.orca_state.get(grade_key, 3)
                        cur_note = st.session_state.orca_state.get(note_key, "")
                        
                        with st.container(border=True):
                            ob_row = st.columns([1.5, 1]) 
                            with ob_row[0]:
                                st.markdown(f"<div style='font-size: 13px; line-height: 1.4; padding-top: 4px;'>{ob['text']} <span class='ref-badge'>{ob['ref']}</span> <span style='background:rgba(16,185,129,0.12); color:#10B981; border:1px solid rgba(16,185,129,0.3); padding:1px 5px; border-radius:4px; font-size:10px; font-weight:700;'>{comp_tag}</span></div>", unsafe_allow_html=True)
                            with ob_row[1]:
                                action_cols = st.columns([0.6, 1.2, 1.5])
                                with action_cols[0]: 
                                    observed = st.checkbox("Observed", value=is_obs, key=obs_key, on_change=update_orca_state, args=(obs_key,), label_visibility="collapsed")
                                with action_cols[1]: 
                                    ob_grade = st.selectbox("Grade", options=[5, 4, 3, 2, 1], index=[5,4,3,2,1].index(cur_grade), format_func=lambda x: f"{x} ({GRADE_LABELS[x]})", key=grade_key, on_change=update_orca_state, args=(grade_key,), disabled=not observed, label_visibility="collapsed")
                                with action_cols[2]: 
                                    st.text_input("Note", value=cur_note, key=note_key, on_change=update_orca_state, args=(note_key,), disabled=not observed, label_visibility="collapsed", placeholder="Record notes...")

                ex_ob_grades = []
                for s_idx, step in enumerate(ex_data["sequence"]):
                    for ob_idx in range(len(step["obs"])):
                        if st.session_state.get(f"orc_observed_{e_key}_{s_idx}_{ob_idx}"): ex_ob_grades.append(st.session_state.get(f"orc_grade_{e_key}_{s_idx}_{ob_idx}", 3))
                up_g, up_n = st.columns([1, 2])
                with up_g:
                    if ex_ob_grades:
                        controlling_grade = min(ex_ob_grades); uploaded_grades[e_key] = controlling_grade
                        st.markdown(f"<div style='font-size:13px;'><b>Controlling grade: {controlling_grade} ({GRADE_LABELS[controlling_grade]})</b></div><div style='font-size:10.5px; opacity:0.7;'>Lowest grade among the {len(ex_ob_grades)}/{sum(len(s['obs']) for s in ex_data['sequence'])} OBs marked Observed.</div>", unsafe_allow_html=True)
                    else:
                        uploaded_grades[e_key] = 3
                        st.info("Mark at least one OB as Observed above to derive a grade.")
                with up_n:
                    up_phrase = st.selectbox(f"Standardized Comment ({ex_data['title'][:25]}...)", options=get_standard_phrase_options(uploaded_grades[e_key]), key=f"up_phrase_{e_key}")
                    if up_phrase == "Custom (type below)": uploaded_notes[e_key] = st.text_input(f"Custom Note ({ex_data['title'][:25]}...)", value="", key=f"up_note_{e_key}")
                    else:
                        up_extra = st.text_input(f"Optional detail ({ex_data['title'][:25]}...)", value="", key=f"up_note_extra_{e_key}")
                        uploaded_notes[e_key] = f"{up_phrase} {up_extra.strip()}" if up_extra.strip() else up_phrase
                uploaded_comp_mapping[e_key] = ex_data["cbta_focus"]

        st.session_state.uploaded_grades_data = {"grades": uploaded_grades, "comp_mapping": uploaded_comp_mapping}

        st.markdown("---")
        st.markdown("#### 📊 Uploaded Syllabus Session Debrief & Export Suite")
        up_recs = []
        for ek in selected_ex_keys:
            ed = PROGRAM_SYLLABUS_EXERCISES[ek]
            up_recs.append({"Module / Failure": ed["title"], "Stressor / Failure Type": ed["stressor"], "Grade": uploaded_grades.get(ek, 3), "Debrief Notes": uploaded_notes.get(ek, ""), "Competencies": ", ".join(uploaded_comp_mapping.get(ek, []))})
        df_uploaded_session = pd.DataFrame(up_recs)
        st.dataframe(df_uploaded_session, hide_index=True)

        col_up_csv, col_up_pdf = st.columns(2)
        with col_up_csv:
            csv_up_export = df_uploaded_session.to_csv(index=False)
            st.download_button(label="📥 Download Uploaded Syllabus Schedule (CSV)", data=csv_up_export, file_name="uploaded_syllabus_session_report.csv", mime="text/csv", key="dl_up_csv")
        with col_up_pdf:
            pdf_up_data = generate_pdf_briefing(pd.DataFrame([{"SLOT": i+1, "PHASE_NAME": f"Syllabus Ph {PROGRAM_SYLLABUS_EXERCISES[k]['phase']}", "EVENT": PROGRAM_SYLLABUS_EXERCISES[k]["title"], "DOD": 2, "ROLE": "PF / PM"} for i, k in enumerate(selected_ex_keys)]), {i+1: uploaded_grades[k] for i, k in enumerate(selected_ex_keys)}, {i+1: uploaded_notes[k] for i, k in enumerate(selected_ex_keys)}, {i+1: uploaded_comp_mapping[k] for i, k in enumerate(selected_ex_keys)}, len(selected_ex_keys) * 2, len(selected_ex_keys) * 3, "Syllabus Program Evaluation", capt_name, fo_name, sim_id, "Uploaded PDF Syllabus Review")
            st.download_button(label="📄 Download Uploaded Syllabus EBT PDF Report", data=pdf_up_data, file_name="uploaded_syllabus_ebt_record.pdf", mime="application/pdf", key="dl_up_pdf")

        slots_for_db_up = []
        for i, k in enumerate(selected_ex_keys):
            ex_data = PROGRAM_SYLLABUS_EXERCISES[k]
            comp_entries = []
            for s_idx, step in enumerate(ex_data["sequence"]):
                for ob_idx, ob in enumerate(step["obs"]):
                    observed = st.session_state.get(f"orc_observed_{k}_{s_idx}_{ob_idx}", False)
                    if observed:
                        comp_entries.append({"code": ob.get("comp", "GEN"), "grade": st.session_state.get(f"orc_grade_{k}_{s_idx}_{ob_idx}", 3), "observed": True, "note": st.session_state.get(f"orc_note_{k}_{s_idx}_{ob_idx}", "")})
            slots_for_db_up.append({"slot_number": i + 1, "event_title": ex_data["title"], "phase_number": ex_data.get("phase"), "dod": None, "role_focus": "PF / PM", "instructor_grade": uploaded_grades.get(k), "instructor_notes": uploaded_notes.get(k, ""), "competencies": comp_entries})
        saved_up_session_id, linked_up_candidate = save_session_to_history(st.session_state.get("db_session_id_uploaded"), sim_id, "Uploaded Syllabus Review", capt_staff_no, capt_name, fo_staff_no, fo_name, len(selected_ex_keys) * 2, len(selected_ex_keys) * 3, "uploaded_syllabus", slots_for_db_up)
        st.session_state.db_session_id_uploaded = saved_up_session_id
        if linked_up_candidate: st.caption(f"✓ Saved to history database (session #{saved_up_session_id}, linked to staff number).")
        else: st.caption(f"✓ Saved to history database (session #{saved_up_session_id}) — add a Captain/F.O. staff number in Session Setup to make this retrievable by candidate history.")
    else: st.info("Select at least one exercise from the uploaded program syllabus above to view the detailed OB & ORCA analysis and debrief suite.")

    st.markdown("---")
    st.markdown("### 📥 Program-Wide OB Generation & PTA Check")
    st.caption("Broader than the dedicated-exercise detection above (which only covers the 12 hand-built program exercises) — this section extracts and matches EVERY titled procedure/exercise in the uploaded PDF against the full Scenarios.csv database, and checks matched items against existing Observable Behaviours. Uses the same PDF uploaded above — no second upload needed.")
    
    if not HAS_PYPDF: st.warning("⚠️ `pypdf` isn't installed in this environment, so PDF ingestion can flow here.")
    elif uploaded_prog_pdf is None: st.info("Upload a program PDF above to run the program-wide OB & PTA check.")
    else:
        uploaded_ingest_pdf = uploaded_prog_pdf
        uploaded_ingest_pdf.seek(0)
        if uploaded_ingest_pdf is not None:
            try: detected_format, extracted = extract_scenarios_auto(uploaded_ingest_pdf)
            except Exception as e:
                detected_format, extracted = None, None
                st.error(f"Couldn't read this PDF: {e}")

            if extracted is not None:
                format_labels = {"fcom_abnormal": "FCOM-style abnormal/emergency procedures reference", "lesson_plan_syllabus": "Lesson-plan / training-syllabus document", "unknown": None}
                if detected_format == "unknown": st.warning("Couldn't identify this PDF's layout — it doesn't match either recognized format. Extraction was skipped rather than guessing.")
                else: st.markdown(f"<div class='ds-row'><span>Detected format</span><span class='ds-status-loaded'>{format_labels[detected_format].upper()}</span></div>", unsafe_allow_html=True)
                
                if df is not None and not df.empty:
                    scenario_events = list(df["EVENT"].unique())
                    matched = match_extracted_titles_to_scenarios(extracted, scenario_events)
                else:
                    matched = [{**b, "matched_event": None, "match_confidence": None} for b in extracted]
                    if extracted: st.warning("Scenarios.csv isn't loaded, so matching is skipped — showing extraction only.")
                
                for m in matched: m["existing_ob"] = SCENARIO_OB_LIBRARY.get(_normalize_event_name(m["matched_event"])) if m.get("matched_event") else None

                exact = [m for m in matched if m["match_confidence"] == "exact"]
                fuzzy = [m for m in matched if m["match_confidence"] == "fuzzy"]
                unmatched = [m for m in matched if m["match_confidence"] is None]

                if extracted:
                    st.success(f"✓ Extracted {len(matched)} titled procedure block(s): {len(exact)} exact match, {len(fuzzy)} fuzzy match, {len(unmatched)} no match.")
                    st.session_state.last_ingestion = {"filename": uploaded_ingest_pdf.name, "format": detected_format, "matched": matched}

                def _render_block(m, badge_color, badge_text):
                    title = m["title"] or "(untitled block)"
                    with st.expander(f"{title}  —  {len(m['ident_codes'])} source block(s)"):
                        st.markdown(f"<span class='comp-badge' style='background-color:{badge_color}; color:#1A1206; border:none;'>{badge_text}</span>", unsafe_allow_html=True)
                        if m["matched_event"]: st.markdown(f"**Matched Scenarios.csv event:** {m['matched_event']}")
                        st.markdown(f"**Source reference(s):** {', '.join(m['ident_codes'])}")
                        if m.get("existing_ob"):
                            st.markdown(f"**Existing PTA on file:** {m['existing_ob']['pta']}")
                            st.markdown(f"**Existing competency tags:** {', '.join(m['existing_ob']['cbta_focus'])}")
                        elif m["matched_event"]: st.caption("Matched to a Scenarios.csv event, but no Observable Behaviours exist for it yet (still on the generic fallback) — nothing to check against.")
                        st.text_area("Extracted raw content (from the uploaded program)", m["content"], height=200, key=f"ingest_content_{hash(title)}_{m['ident_codes'][0]}", disabled=True)

                if exact:
                    st.markdown("<div class='panel-head'><span class='panel-code'>OK</span><span class='panel-title-text'>Exact matches</span></div>", unsafe_allow_html=True)
                    for m in exact: _render_block(m, KM_GREEN, "EXACT MATCH")
                if fuzzy:
                    st.markdown("<div class='panel-head'><span class='panel-code'>?</span><span class='panel-title-text'>Fuzzy matches — please confirm</span></div>", unsafe_allow_html=True)
                    for m in fuzzy: _render_block(m, KM_AMBER, "FUZZY MATCH — CHECK")
                if unmatched:
                    st.markdown("<div class='panel-head'><span class='panel-code'>—</span><span class='panel-title-text'>No match — a PDF-internal sub-section, or a scenario not yet in Scenarios.csv</span></div>", unsafe_allow_html=True)
                    for m in unmatched: _render_block(m, KM_GRAY_DOT, "NO MATCH")

    st.markdown("---")
    st.markdown("### 📋 Upload Program Debrief")
    st.markdown("A separate report from the EBT Session Debrief, by design — this one answers *\"does our own program have full Observable Behaviour coverage?\"* rather than *\"how did this crew perform against the session I built\"*. Reflects the program-wide OB check above.")
    _last_ing = st.session_state.get("last_ingestion")
    if not _last_ing: st.info("Nothing ingested yet this session — upload a program PDF above to run the OB & PTA check first.")
    else:
        matched = _last_ing["matched"]
        exact = [m for m in matched if m["match_confidence"] == "exact"]
        fuzzy = [m for m in matched if m["match_confidence"] == "fuzzy"]
        unmatched = [m for m in matched if m["match_confidence"] is None]
        covered = [m for m in matched if m.get("existing_ob")]
        matched_no_ob = [m for m in (exact + fuzzy) if not m.get("existing_ob")]

        st.markdown(f"<div class='ds-row'><span>Source program</span><span class='ds-status-loaded'>{_last_ing['filename'].upper()}</span></div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Items Extracted", len(matched))
        with m2: st.metric("Matched to Scenarios.csv", len(exact) + len(fuzzy))
        with m3: st.metric("With Existing OB Coverage", len(covered))
        with m4: st.metric("Needs Attention", len(matched_no_ob) + len(unmatched), delta=None if not (matched_no_ob or unmatched) else "review", delta_color="inverse")

        st.markdown("---")
        if matched_no_ob:
            st.markdown("<div class='panel-head'><span class='panel-code'>!</span><span class='panel-title-text'>Matched to a scenario, but no OBs exist for it yet</span></div>", unsafe_allow_html=True)
            for m in matched_no_ob: st.markdown(f"- **{m['title']}** → matched *{m['matched_event']}*, generic fallback only")
        if unmatched:
            st.markdown("<div class='panel-head'><span class='panel-code'>?</span><span class='panel-title-text'>Not matched to any known scenario</span></div>", unsafe_allow_html=True)
            for m in unmatched: st.markdown(f"- **{m['title']}** — may be a new scenario worth adding, or a PDF-internal sub-section")
        if covered:
            with st.expander(f"✓ {len(covered)} item(s) with full existing OB coverage — confirmed consistent"):
                for m in covered: st.markdown(f"- **{m['title']}** → *{m['matched_event']}* ({', '.join(m['existing_ob']['cbta_focus'])})")


if _page == "scenarios":
    st.markdown("#### 🎯 Interactive Simulator Scenario Builder & Selector")
    st.markdown("Filter the full scenario matrix below to inspect all available events, DOD levels, and targeted competencies before generating your session.")
    if df is not None:
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1: f_phase = st.selectbox("Filter by Phase", options=["Any"] + ALL_PHASE_KEYS, format_func=lambda x: x if x == "Any" else PHASE_NAMES[x], key="sel_filter_phase")
        with f_col2: f_dod = st.selectbox("Filter by DOD", options=["Any", 1, 2, 3], key="sel_filter_dod")
        with f_col3: f_comp = st.selectbox("Filter by Competency", options=["Any"] + list(COMPETENCY_KEYS.keys()), format_func=lambda x: x if x == "Any" else f"{x} – {COMPETENCY_KEYS[x]}", key="sel_filter_comp")

        view_df = df.copy()
        if f_phase != "Any": view_df = view_df[view_df["PHASES"] == f_phase]
        if f_dod != "Any": view_df = view_df[view_df["DOD"] == f_dod]
        if f_comp != "Any": view_df = view_df[view_df["COMPETENCIES"].apply(lambda c: f_comp in c)]

        st.caption(f"{len(view_df)} of {len(df)} scenario/phase rows match the current filters.")
        display_df = view_df[["EVENT", "PHASES", "DOD", "ATA", "COMPETENCIES"]].copy()
        display_df["PHASES"] = display_df["PHASES"].map(PHASE_NAMES)
        display_df["COMPETENCIES"] = display_df["COMPETENCIES"].apply(lambda c: ", ".join(c) if c else "—")
        st.dataframe(display_df, hide_index=True, height=450)
    else: st.warning("Scenario database not loaded.")


if _page == "debrief":
    # SESSION DEBRIEF — matches design mockup:
    # Left: radar chart + horizontal grade bars
    # Right: session result panel + focus areas + export PDF

    has_main_session   = "final_df" in st.session_state
    has_uploaded_session = "uploaded_grades_data" in st.session_state

    if not (has_main_session or has_uploaded_session):
        st.info("No session data yet. Build a session plan from **Generate EBT Program** or grade an uploaded program.")
    else:
        # ── Aggregate grades across sources ──────────────────────────────────
        comp_grades = {c: [] for c in COMPETENCY_KEYS}
        source_count = 0
        if has_main_session:
            final_df = st.session_state.final_df
            for _, row in final_df.iterrows():
                slot_num = int(row["SLOT"])
                g = st.session_state.get(f"grade_slot_{slot_num}", 3)
                for c in st.session_state.get("slot_competencies", {}).get(slot_num, []):
                    if g is not None: comp_grades[c].append(g)
            source_count += len(final_df)
        if has_uploaded_session:
            up_data = st.session_state.uploaded_grades_data
            for ek, g in up_data["grades"].items():
                for c in up_data["comp_mapping"].get(ek, []):
                    if c in comp_grades: comp_grades[c].append(g)
            source_count += len(up_data["grades"])

        avgs = {c: (sum(v)/len(v) if v else 0) for c, v in comp_grades.items()}
        overall_avg = round(sum(avgs.values())/len([v for v in avgs.values() if v > 0]), 1) if any(avgs.values()) else 0
        graded_count = sum(1 for v in comp_grades.values() if v)
        below_mal    = sum(1 for c, v in comp_grades.items() if v and sum(v)/len(v) < 3)
        result_text  = "PASS" if overall_avg >= 3 else "RETRAIN"
        result_color = KM_GREEN if result_text == "PASS" else "#E53E3E"
        result_bg    = "rgba(52,211,153,.15)" if result_text == "PASS" else "rgba(229,62,62,.15)"
        s_id         = st.session_state.get("sim_id", "—")
        s_type       = st.session_state.get("session_mode", "EBT Evaluation")[:15]

        # ── Layout ────────────────────────────────────────────────────────────
        d_left, d_right = st.columns([2.1, 1])

        with d_left:
            st.markdown(f"<div class='panel-head'><span class='panel-code'>DBF</span><span class='panel-title-text'>COMPETENCY PROFILE</span></div>", unsafe_allow_html=True)

            comp_list = list(COMPETENCY_KEYS.keys())  # APK COM FPM FPA KNO LTW PSD SAW WLM
            n = len(comp_list)
            cx, cy, r_max = 200, 200, 150

            # Radar grid
            grid_paths = ""
            for ring in [1,2,3,4,5]:
                r = r_max * ring / 5
                pts = []
                for j in range(n):
                    angle = math.pi/2 - 2*math.pi*j/n
                    pts.append((cx + r*math.cos(angle), cy - r*math.sin(angle)))
                grid_paths += f"<polygon points='{" ".join(f"{x:.1f},{y:.1f}" for x,y in pts)}' fill='none' stroke='rgba(255,255,255,0.07)' stroke-width='1'/>"

            # Axis lines
            axis_lines = ""
            for j in range(n):
                angle = math.pi/2 - 2*math.pi*j/n
                ex = cx + r_max*math.cos(angle)
                ey = cy - r_max*math.sin(angle)
                axis_lines += f"<line x1='{cx}' y1='{cy}' x2='{ex:.1f}' y2='{ey:.1f}' stroke='rgba(255,255,255,0.10)' stroke-width='1'/>"

            # Data polygon
            data_pts = []
            for j, comp in enumerate(comp_list):
                angle = math.pi/2 - 2*math.pi*j/n
                val   = avgs.get(comp, 0) / 5.0
                px    = cx + r_max * val * math.cos(angle)
                py    = cy - r_max * val * math.sin(angle)
                data_pts.append((px, py))
            poly_pts = " ".join(f"{x:.1f},{y:.1f}" for x,y in data_pts)
            data_poly = f"<polygon points='{poly_pts}' fill='rgba(52,211,153,0.25)' stroke='#34D399' stroke-width='2'/>"
            data_dots = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='#34D399'/>" for x,y in data_pts)

            # Labels
            label_svg = ""
            for j, comp in enumerate(comp_list):
                angle = math.pi/2 - 2*math.pi*j/n
                lx = cx + (r_max + 22) * math.cos(angle)
                ly = cy - (r_max + 22) * math.sin(angle)
                anchor = "middle" if abs(lx-cx) < 10 else ("start" if lx > cx else "end")
                label_svg += f"<text x='{lx:.1f}' y='{ly:.1f}' text-anchor='{anchor}' dominant-baseline='middle' fill='#8B94A3' font-size='11' font-family='monospace'>{comp}</text>"

            radar_svg = f"""<svg width="100%" viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
                {grid_paths}{axis_lines}{data_poly}{data_dots}{label_svg}
            </svg>"""

            # Grade bars
            bar_rows = ""
            for comp in comp_list:
                avg_val = avgs.get(comp, 0)
                pct = avg_val / 5 * 100
                grade_n = round(avg_val) if avg_val else 0
                bar_color = ("#34D399" if avg_val >= 4 else
                             (KM_AMBER if avg_val >= 3 else
                              ("#E53E3E" if avg_val > 0 else "#334155")))
                bar_rows += f"""
                <div style="display:flex;align-items:center;margin-bottom:10px;gap:10px;">
                    <div style="width:36px;font-size:11px;color:{KM_TEXT_MUTED};font-weight:700;flex-shrink:0;">{comp}</div>
                    <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:3px;height:12px;overflow:hidden;">
                        <div style="width:{pct:.0f}%;height:100%;background:{bar_color};border-radius:3px;transition:width .3s;"></div>
                    </div>
                    <div style="width:20px;font-size:13px;font-weight:800;color:{bar_color};text-align:right;">{grade_n if grade_n else "—"}</div>
                </div>"""

            # Combined left panel: radar + bars side by side
            rad_col, bar_col = st.columns([1, 1])
            with rad_col:
                st.markdown(radar_svg, unsafe_allow_html=True)
            with bar_col:
                st.markdown(f"<div style='padding:20px 0;'>{bar_rows}</div>", unsafe_allow_html=True)

            # Inline grade sliders (only for main session)
            if has_main_session:
                st.markdown(f"<div style='height:8px;'></div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:10px;color:{KM_TEXT_MUTED};margin-bottom:8px;'>GRADE EACH SLOT (1–5)</div>", unsafe_allow_html=True)
                final_df = st.session_state.final_df
                for _, row in final_df.iterrows():
                    slot_num = int(row["SLOT"])
                    event = row.get("EVENT", row.get("SCENARIO", f"Slot {slot_num}"))
                    g = st.slider(
                        f"Slot {slot_num}: {str(event)[:50]}",
                        min_value=1, max_value=5,
                        value=st.session_state.get(f"grade_slot_{slot_num}", 3),
                        key=f"grade_slot_{slot_num}"
                    )

        with d_right:
            # SESSION RESULT panel
            st.markdown(f"""
            <div class='panel-head'><span class='panel-code'>RES</span><span class='panel-title-text'>SESSION RESULT</span></div>
            <div style='margin-bottom:12px;'>
                <div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;'>
                    <div>
                        <div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.08em;font-weight:700;margin-bottom:2px;'>OVERALL AVG</div>
                        <div style='font-size:28px;font-weight:800;color:{KM_GREEN};line-height:1;'>{overall_avg}</div>
                    </div>
                    <div style='background:{result_bg};color:{result_color};font-size:11px;font-weight:800;padding:5px 14px;border-radius:5px;border:1px solid {result_color}55;letter-spacing:.05em;margin-top:4px;'>{result_text}</div>
                </div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;padding-top:10px;border-top:1px solid {KM_BORDER};'>
                    <div><div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:2px;'>SESSION</div><div style='font-size:13px;font-weight:700;color:{KM_TEXT};'>{s_id}</div></div>
                    <div><div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:2px;'>TYPE</div><div style='font-size:13px;font-weight:700;color:{KM_AMBER};'>{s_type[:12]}</div></div>
                    <div><div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:2px;'>GRADED</div><div style='font-size:13px;font-weight:700;color:{KM_TEXT};'>{graded_count} / {len(comp_list)}</div></div>
                    <div><div style='font-size:9px;color:{KM_TEXT_MUTED};letter-spacing:.07em;font-weight:700;margin-bottom:2px;'>BELOW MAL</div><div style='font-size:13px;font-weight:700;color:{"#E53E3E" if below_mal else KM_TEXT};'>{below_mal}</div></div>
                </div>
            </div>""", unsafe_allow_html=True)

            # FOCUS AREAS panel
            st.markdown(f"<div class='panel-head'><span class='panel-code'>FOC</span><span class='panel-title-text'>FOCUS AREAS</span></div>", unsafe_allow_html=True)
            focus_items = [(c, round(sum(v)/len(v), 1)) for c, v in comp_grades.items() if v and sum(v)/len(v) < 3]
            focus_items.sort(key=lambda x: x[1])
            if focus_items:
                for comp, avg_val in focus_items[:3]:
                    fc = "#E53E3E" if avg_val < 2.5 else KM_AMBER
                    st.markdown(f"""
                    <div style='display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid {KM_BORDER};'>
                        <div style='display:flex;align-items:center;gap:8px;'>
                            <span style='background:{fc};color:#fff;font-size:11px;font-weight:800;padding:2px 7px;border-radius:4px;'>{round(avg_val, 1)}</span>
                            <span style='font-size:13px;color:{KM_TEXT};font-weight:600;'>{comp}</span>
                        </div>
                        <span style='font-size:9px;font-weight:800;color:{fc};letter-spacing:.06em;'>MAL</span>
                    </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='font-size:11px;color:{KM_GREEN};padding:8px 0;'>All competencies above minimum standard</div>", unsafe_allow_html=True)

            st.markdown(f"<div style='height:10px;'></div>", unsafe_allow_html=True)

            # EXPORT button
            if has_main_session and "pdf_data" in st.session_state:
                st.download_button(
                    label="📄  EXPORT BRIEFING PDF",
                    data=st.session_state.pdf_data,
                    file_name=f"EBT_Debrief_{s_id}.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            else:
                if st.button("📄  EXPORT BRIEFING PDF", type="primary"):
                    st.info("Build a session plan first to generate the PDF export.")
