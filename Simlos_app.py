# ==========================================
# DEPLOYMENT FILE: simlos_app.py (GitHub / Streamlit Cloud entry point)
# This filename is now stable — do not rename per-change. Paste future
# updates directly into this file. Internal version history is tracked
# here in comments (newest last); a separately-named dev copy
# (Sim_verNN.py) is kept per change for local diffing/rollback.
#
# VERSION HISTORY
#   ver24        — designated stable baseline (as Sim_ver24.py)
#   ver25        — fix: os.path.basename(scenario_obs_source) TypeError
#                  when scenario_obs_source is a Streamlit UploadedFile
#                  rather than a path string (crashed the sidebar
#                  auto-load success/warning message). Added
#                  source_display_name() helper; also routed
#                  _source_tag() through it for consistency.
#   simlos_app   — renamed from Sim_ver2.py (the prior GitHub filename)
#                  to this stable name, content = ver25. No code changes
#                  in this step, filename only.
#   ver26        — Dashboard redesign (dark/amber "ops console" look):
#                  - New forced dark theme (KM_BG/KM_PANEL/KM_AMBER
#                    palette) replacing the old light-blue accent theme.
#                  - Tabs renamed to short-code + label ("SES · Session
#                    Setup", "ENV · Environment & IOS", etc.) with amber
#                    active-tab styling.
#                  - Session Setup tab restructured into a two-column
#                    dashboard: left = Slot Configuration, Session
#                    Metadata & Device Setup (+ new Aircraft/Program/
#                    Duration fields), Data Sources, Document
#                    References; right = Session Summary (live stats),
#                    Competency Coverage (9 badges, amber-highlighted
#                    for whichever competencies the current slot plan
#                    actually targets), and the Build Session Plan CTA.
#                  - Top header (logo, title, Session/Candidate,
#                    DATA/DRAFT/SYNCED status pills) now renders via a
#                    st.empty() placeholder created at the very top of
#                    the script and filled in once session/data-source
#                    state exists further down.
#                  - Fixed a latent crash: match_stats.get(...) was
#                    called unconditionally, but load_scenario_database()
#                    returns match_stats as a plain error string (not a
#                    dict) when Scenarios.csv can't be loaded at all —
#                    now guarded.
#                  - Verified with py_compile, ast.parse, and
#                    streamlit.testing.v1.AppTest (full script execution,
#                    zero exceptions) before shipping.
#   ver27        — Typeface changed to Geist Mono app-wide: global
#                  font-family (was Inter) plus both inline 'monospace'
#                  fallbacks (.jepp-card, live METAR feed block) now
#                  specify 'Geist Mono' explicitly, loaded via
#                  @fontsource CDN import.
#   ver28        — UI polish pass per instructor feedback on ver26/27:
#                  - Font size set to 10px app-wide (base rule only, not
#                    !important on font-size — so .km-title/.stat-value/
#                    etc. keep their own larger explicit sizes; only
#                    elements with no explicit size pick up the 10px
#                    default).
#                  - Fixed Competency Coverage badges: they were lit
#                    from each slot's 'Target Competency' FILTER dropdown
#                    (almost always "Any", so badges barely lit
#                    regardless of the actual plan) instead of the real
#                    per-event COMPETENCIES data resolve_competencies()
#                    already computes elsewhere in this file. Now sourced
#                    from st.session_state.final_df once a plan is built;
#                    falls back to the filter-based preview before that.
#                  - Fixed native Streamlit header/toolbar bar clipping
#                    the custom .km-header: block-container's padding-top
#                    (0.8rem) was smaller than the native fixed header's
#                    height, so the top of the custom header rendered
#                    underneath it. Hidden the native header/toolbar
#                    entirely (stHeader, stToolbar) — this is a fully
#                    custom-branded console page, not a generic Streamlit
#                    app, so the default chrome (hamburger/Deploy/running
#                    man) wasn't wanted anyway.
#                  - Added :root CSS variable overrides (--text-color,
#                    --background-color, --secondary-background-color,
#                    --primary-color, --font) so native widgets AND the
#                    older var(--...)-based helpers (competency Venn SVG,
#                    OB flow cards) render dark instead of defaulting to
#                    Streamlit's light theme — this was the source of the
#                    "white background" patches.
#                  - Added .streamlit/config.toml (new file) with a
#                    matching dark theme, for the widgets CSS overrides
#                    alone don't reliably reach (dataframe internals,
#                    some BaseWeb portal-rendered menus).
#                  NOTE: header-cutoff and white-background diagnoses were
#                  made from source review only (no screenshot available)
#                  — please confirm both are actually resolved after
#                  deploying, since there could be a second contributing
#                  cause I couldn't see from code alone.
#   ver29        — Follow-up fixes from instructor testing of ver28:
#                  - Competency Coverage badges were still showing 0/9
#                    right after clicking "Build Session Plan". Root
#                    cause: the panel is rendered EARLIER in script order
#                    than the generation block that sets
#                    st.session_state.final_df, so on the click's own
#                    rerun it still saw stale/empty state. Added
#                    st.rerun() right after final_df is set (plus a
#                    just_generated flag so the success toast still shows
#                    on the next pass) — verified end-to-end with a test
#                    Scenarios.csv + AppTest button click: coverage note
#                    now correctly reads "N of 9 ... actually targeted"
#                    on the very click that builds the plan.
#                  - Found (via that same test) a PRE-EXISTING crash,
#                    unrelated to the above: clicking "Build Session
#                    Plan" with no Scenarios.csv loaded raised
#                    TypeError: 'NoneType' object is not subscriptable.
#                    Generation block now guarded with an
#                    if df is None or df.empty check and a friendly
#                    st.warning() instead.
#                  - Font size: the ver28 attempt (10px, no !important)
#                    only shrank plain unstyled text — Streamlit's own
#                    CSS sets font-size directly on native widgets
#                    (buttons/inputs/tabs/dataframe) with higher
#                    specificity than a plain html/body rule, so those
#                    stayed at Streamlit's default, an inconsistent mix
#                    reported as "too small / unreadable". Bumped to
#                    14px and added !important so it actually takes
#                    hold app-wide. Trade-off: this also flattens this
#                    file's own smaller/larger custom classes (.km-title
#                    16px, .stat-value 17px, .comp-badge 11px, etc.)
#                    to 14px too, since none of them use !important
#                    themselves — full size hierarchy can be restored on
#                    request by adding !important to those specific
#                    classes.
#                  Naming convention change per instructor request: from
#                  this version on, every delivered file is named
#                  Sim_verNN.py with NN increasing sequentially — no more
#                  parallel simlos_app.py copy each turn. Copy this
#                  file's contents into simlos_app.py on GitHub manually
#                  when ready to deploy it.
#   ver30        — Restored data-source detail counts that silently
#                  disappeared in the ver26 "Data Sources" panel redesign:
#                  that redesign collapsed the old informative status line
#                  ("Scenarios.csv — 282 scenario/phase rows", "Keypams —
#                  cross-matched 64/124 events (52%)", "Scenario OBs — 34
#                  profile(s)") down to a bare LOADED/OPTIONAL flag with
#                  no numbers. Added a .ds-detail line under each LOADED
#                  row showing the real count/match-rate again, using
#                  data (match_stats, len(df), len(SCENARIO_OB_LIBRARY))
#                  that was already being computed — just never
#                  re-displayed after the redesign. Verified end-to-end
#                  with AppTest + a test Scenarios.csv: correctly renders
#                  "9 scenario/phase rows" / "35 scenario-specific
#                  profile(s)" and correctly omits the detail line for
#                  Keypams.xlsx when it isn't loaded (OPTIONAL, no file).
#   ver31        — Follow-up polish + a full ver25→ver26 audit:
#                  - .ds-detail text (the counts restored in ver30) is
#                    now KM_GREEN instead of muted gray, for legibility.
#                  - Header showed only F/O as "Candidate" — but the
#                    app's own data model (save_session_to_history)
#                    already tracks BOTH capt_id and fo_id as separate
#                    candidates. This wasn't a ver26 regression (ver25
#                    never had this branded header at all to regress
#                    from) — just an incomplete first pass. Header now
#                    shows two meta fields: "Candidate · Capt" and
#                    "Candidate · F/O".
#                  - Ran a full audit, not just a spot-check: compared
#                    every function definition ver25 vs ver26 (ast-level,
#                    none dropped), every quoted UI label string in the
#                    Session Setup tab (all present, only 3 cosmetic
#                    renames of hidden file-uploader captions), and did a
#                    byte-for-byte diff of every OTHER tab's code
#                    (tab_history, tab_standard, tab_env, tab_orca,
#                    tab_selector, tab_debrief) — all identical, zero
#                    diff. Conclusion: ver26's redesign was scoped
#                    exactly to Session Setup + header as its own
#                    changelog claimed; the two regressions already found
#                    and fixed (ver30's detail counts, this version's
#                    dual-candidate header) were the complete list, not
#                    a sample of more still hiding elsewhere.
#   ver32        — Fixed a real Streamlit Cloud bug: after updating
#                  Scenario_Observable_Behaviours.xlsx and Keypams.xlsx
#                  and syncing to GitHub, the deployed app kept reporting
#                  stale counts (e.g. 34 profiles) while a fresh local
#                  run correctly showed 47 — same file, stale result.
#                  Root cause: load_scenario_obs_library() and
#                  load_scenario_database() are @st.cache_data, and their
#                  real argument for an auto-loaded (non-uploaded) file
#                  is a plain bundled-file PATH STRING — st.cache_data
#                  keys on argument VALUE, not file content, so replacing
#                  what's at that path doesn't necessarily bust the
#                  cache, especially if Streamlit Cloud does a
#                  soft git-pull-and-rerun rather than a full process
#                  restart on a data-only file change.
#                  Fix: added _file_cache_token(source) (file mtime when
#                  source is a path) as an extra argument to both cached
#                  functions, so any on-disk replacement changes the
#                  effective cache key too. First attempt at this named
#                  the parameter "_cache_token" — which st.cache_data
#                  silently EXCLUDES from its hash entirely (any
#                  underscore-prefixed parameter is, by design, meant for
#                  passing unhashable objects like DB connections through
#                  the cache safely) — so that version compiled fine and
#                  looked correct but did precisely nothing. Caught this
#                  by reproducing the exact failure in an isolated
#                  two-line repro before and after the rename, then
#                  re-verified against the real app: same AppTest
#                  instance, bundled file swapped mid-session (no new
#                  process), profile count now correctly moves from 3→9
#                  and Scenarios.csv row count from 5→11 without any
#                  manual "Reboot app". Renamed to cache_token /
#                  cache_token_a / cache_token_b throughout.
# ==========================================
import streamlit as st
import pandas as pd
import io
import re
import os
import sys
import sqlite3
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
# HISTORICAL DATA STORE — CANDIDATE SESSION HISTORY
#
# Field-testing implementation: SQLite, a single file, zero external
# infrastructure. This is deliberately NOT the final shared/online store —
# it's built so that becomes a small change later, not a rewrite:
#   - every function below takes a connection and uses plain parameterized
#     SQL (no SQLite-only syntax beyond AUTOINCREMENT), so swapping
#     get_db_connection() for a psycopg2/SQLAlchemy Postgres connection is
#     the only thing that needs to change to move onto a shared online DB
#   - the schema is candidate-centric (staff number as the real identity
#     key, not name) specifically so history retrieval works across
#     sessions and typos in a name field
#
# NOT a replacement for Pelesys or any official system of record — this is
# a local convenience log for this app's own retrieval/reporting during
# field testing.
# ==========================================
DB_PATH = os.environ.get("EBT_HISTORY_DB_PATH", "ebt_session_history.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db_connection()
    conn.executescript("""
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
    """)
    conn.commit()
    conn.close()


def get_or_create_candidate(conn, staff_number, full_name):
    """Staff number is the real identity key. If it's blank, the candidate
    isn't saved to history at all — a name alone isn't a reliable match
    across sessions (typos, duplicates), so we don't silently create a
    record that history lookup can't actually find later."""
    staff_number = (staff_number or "").strip()
    full_name = (full_name or "").strip()
    if not staff_number:
        return None
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
                             fo_staff_no, fo_name, total_dod, max_dod_threshold, source_workflow,
                             slots):
    """Insert or update one session's full record. slots is a list of dicts:
    {slot_number, event_title, phase_number, dod, role_focus, instructor_grade,
     instructor_notes, competencies: [{code, grade, observed, note}, ...]}.
    Re-saving the same session (existing_session_id set) replaces its slot
    data rather than appending duplicates — repeated exports during one
    grading session shouldn't multiply history rows."""
    conn = get_db_connection()
    try:
        capt_id = get_or_create_candidate(conn, capt_staff_no, capt_name)
        fo_id = get_or_create_candidate(conn, fo_staff_no, fo_name)

        if existing_session_id:
            conn.execute(
                """UPDATE training_sessions SET sim_id=?, session_mode=?, captain_candidate_id=?, fo_candidate_id=?,
                   total_dod=?, max_dod_threshold=?, updated_at=datetime('now') WHERE session_id=?""",
                (sim_id, session_mode, capt_id, fo_id, total_dod, max_dod_threshold, existing_session_id)
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
    """Every session a candidate (by staff number) appears in, either seat,
    with per-competency grades — the actual retrieval this whole feature
    is for."""
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT candidate_id, full_name FROM candidates WHERE staff_number = ?", (staff_number.strip(),))
        row = cur.fetchone()
        if not row:
            return None, None
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
st.set_page_config(
    page_title="EBT Session Optimizer",
    page_icon="✈️",
    layout="wide"
)

init_db()

# ==========================================
# DASHBOARD THEME — dark/amber "ops console" look
#
# Forced (not var(--...)) dark palette so the app reads the same
# regardless of the viewer's OS/browser theme — this is a branded
# console, not a document that should follow light/dark preference.
# ==========================================
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
        /* Streamlit's native theme variables default to a LIGHT theme
        unless a .streamlit/config.toml [theme] section overrides them.
        Several older helper functions in this file (SVG competency
        Venn diagram, OB flow cards) still render color via var(--...)
        rather than the KM_* constants — overriding the variables here
        means those elements go dark too, without editing every call
        site individually. */
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
    /* Streamlit's own generated CSS sets font-size directly on many native
    widgets (buttons, inputs, tab labels, dataframe cells) with selectors
    more specific than a plain html/body rule — so the earlier
    non-!important attempt only shrank plain unstyled text and left those
    widgets at Streamlit's default, an inconsistent mix rather than a
    uniform, readable size. !important here forces one base size
    app-wide, INCLUDING this file's own smaller/larger custom classes
    below (.km-title 16px, .stat-value 17px, .comp-badge 11px, etc.) —
    none of those have !important of their own, so this rule beats them
    regardless of their higher selector specificity. Net effect: the
    whole app reads at a uniform 14px now rather than the mixed/tiny
    result before. If the size hierarchy (bigger titles, smaller badges)
    is wanted back, say so and !important can be added to those specific
    classes individually so they win over this rule again. */

    /* ---------- Hide Streamlit's native header/toolbar chrome ----------
    This is a custom-branded console, not a generic Streamlit page — the
    default header bar (hamburger menu / Deploy button / running-man) sat
    directly on top of .km-header below because block-container's
    padding-top is much smaller than that bar's native height, clipping
    the top of the custom header. Hiding it removes the overlap and the
    stray chrome at once; block-container's own small top padding is
    enough breathing room once it's gone. */
    [data-testid="stHeader"] {{
        display: none !important;
    }}
    [data-testid="stToolbar"] {{
        visibility: hidden !important;
    }}
    .stApp {{
        background-color: {KM_BG} !important;
    }}
    .block-container {{
        padding-top: 0.8rem !important;
        padding-bottom: 1.0rem !important;
        max-width: 97% !important;
    }}
    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: {KM_BG} !important;
    }}
    p, li, span, label, div {{ color: {KM_TEXT}; }}

    h1, h2, h3, h4 {{ color: {KM_TEXT} !important; font-weight: 700 !important; margin-top: 6px !important; margin-bottom: 6px !important;}}

    /* ---------- Top app header ---------- */
    .km-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background-color: {KM_PANEL};
        border: 1px solid {KM_BORDER};
        border-radius: 12px;
        padding: 14px 22px;
        margin-bottom: 14px;
        flex-wrap: wrap;
        gap: 14px;
    }}
    .km-header-left {{ display: flex; align-items: center; gap: 14px; }}
    .km-logo {{
        width: 42px; height: 42px; border-radius: 10px;
        background: {KM_AMBER};
        display: flex; align-items: center; justify-content: center;
        font-size: 20px; flex-shrink: 0;
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
        display: flex; align-items: center; gap: 6px;
        background-color: {KM_PANEL_ALT};
        border: 1px solid {KM_BORDER};
        border-radius: 20px;
        padding: 5px 11px;
        font-size: 10px; font-weight: 700; letter-spacing: 0.05em;
        color: {KM_TEXT_MUTED};
    }}
    .km-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
    .km-dot-green {{ background-color: {KM_GREEN}; }}
    .km-dot-amber {{ background-color: {KM_AMBER}; }}
    .km-dot-gray {{ background-color: {KM_GRAY_DOT}; }}

    /* ---------- Tab bar (short-code + label pills) ---------- */
    div[data-baseweb="tab-list"] {{
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 4px !important;
        overflow-x: visible !important;
        background-color: {KM_PANEL} !important;
        border: 1px solid {KM_BORDER} !important;
        border-radius: 10px !important;
        padding: 5px !important;
    }}
    div[data-baseweb="tab"] {{
        white-space: normal !important;
        height: auto !important;
        min-height: 34px !important;
        padding: 6px 14px !important;
        border-radius: 7px !important;
        color: {KM_TEXT_MUTED} !important;
    }}
    div[data-baseweb="tab"] p {{ font-size: 12.5px !important; font-weight: 700 !important; letter-spacing: 0.02em; }}
    div[data-baseweb="tab"][aria-selected="true"] {{
        background-color: {KM_AMBER_DIM} !important;
        color: {KM_AMBER} !important;
    }}
    div[data-baseweb="tab"][aria-selected="true"] p {{ color: {KM_AMBER} !important; }}
    div[data-baseweb="tab-highlight"] {{ background-color: {KM_AMBER} !important; }}

    /* ---------- Cards / panels ---------- */
    div[data-testid="stMetric"], .ios-card {{
        background-color: {KM_PANEL} !important;
        border: 1px solid {KM_BORDER} !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
    }}
    div[data-testid="stMetricLabel"] * {{ color: {KM_TEXT_MUTED} !important; font-weight: 700 !important; text-transform: uppercase; font-size: 10.5px !important; letter-spacing: 0.05em; }}
    div[data-testid="stMetricValue"] * {{ color: {KM_TEXT} !important; font-weight: 800 !important; }}
    [data-testid="stVerticalBlockBorderWrapper"] > div {{ background-color: {KM_PANEL}; border-radius: 10px; }}
    div[data-testid="stExpander"] {{ background-color: {KM_PANEL} !important; border: 1px solid {KM_BORDER} !important; border-radius: 10px !important; }}

    .ios-label {{
        font-size: 11px; color: {KM_TEXT_MUTED}; text-transform: uppercase;
        letter-spacing: 0.05em; font-weight: 700;
    }}

    /* ---------- Panel header: small amber code chip + uppercase title ---------- */
    .panel-head {{ display: flex; align-items: center; gap: 9px; margin-bottom: 12px; }}
    .panel-code {{
        background-color: {KM_AMBER_DIM}; color: {KM_AMBER};
        font-size: 10px; font-weight: 800; letter-spacing: 0.06em;
        padding: 3px 7px; border-radius: 5px; border: 1px solid rgba(245,166,35,0.3);
    }}
    .panel-title-text {{ font-size: 12.5px; font-weight: 800; letter-spacing: 0.04em; color: {KM_TEXT}; text-transform: uppercase; }}

    /* ---------- Session Summary stat blocks ---------- */
    .stat-label {{ font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.07em; color: {KM_TEXT_MUTED}; font-weight: 700; margin-bottom: 2px; }}
    .stat-value {{ font-size: 17px; font-weight: 800; color: {KM_TEXT}; }}
    .stat-value-accent {{ color: {KM_AMBER}; }}
    .stat-value-green {{ color: {KM_GREEN}; }}

    /* ---------- Competency badges ---------- */
    .comp-badge {{
        display: inline-block; font-size: 11px; font-weight: 800;
        padding: 4px 10px; border-radius: 5px; margin: 2px 4px 2px 0;
        letter-spacing: 0.03em;
    }}
    .comp-badge-active {{ background-color: {KM_AMBER}; color: #1A1206; border: 1px solid {KM_AMBER}; }}
    .comp-badge-inactive {{ background-color: transparent; color: {KM_GRAY_DOT}; border: 1px solid {KM_BORDER}; }}

    /* ---------- Data source / doc reference rows ---------- */
    .ds-row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 9px 12px; background-color: {KM_PANEL_ALT};
        border: 1px solid {KM_BORDER}; border-radius: 7px; margin-bottom: 7px; font-size: 12.5px;
        font-weight: 600;
    }}
    .ds-status-loaded {{ color: {KM_GREEN}; font-size: 10px; font-weight: 800; letter-spacing: 0.05em; }}
    .ds-status-optional {{ color: {KM_TEXT_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 0.05em; }}
    .ds-detail {{ font-size: 10.5px; color: {KM_GREEN}; margin: -4px 0 7px 12px; }}
    .doc-ref-row {{ font-size: 12px; color: {KM_TEXT_MUTED}; margin-bottom: 4px; }}
    .doc-ref-tag {{ color: {KM_AMBER}; font-weight: 700; }}

    .jepp-card {{
        background-color: {KM_PANEL_ALT};
        border: 2px solid {KM_AMBER};
        border-radius: 6px;
        padding: 14px;
        font-family: 'Geist Mono', monospace;
        color: {KM_TEXT};
        margin-top: 10px;
        margin-bottom: 12px;
    }}
    .jepp-header {{
        font-size: 14px;
        font-weight: 700;
        color: {KM_AMBER};
        border-bottom: 1px dashed rgba(255,255,255,0.15);
        padding-bottom: 4px;
        margin-bottom: 8px;
    }}

    .status-badge-ok {{
        background-color: rgba(52, 211, 153, 0.15);
        color: {KM_GREEN};
        border: 1px solid rgba(52, 211, 153, 0.3);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        text-align: center;
    }}
    .status-badge-warn {{
        background-color: {KM_AMBER_DIM};
        color: {KM_AMBER};
        border: 1px solid rgba(245, 166, 35, 0.3);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        text-align: center;
    }}

    /* Secondary (default) buttons — ghost/outline, e.g. + Add / - Remove */
    .stButton>button {{
        background-color: transparent;
        color: {KM_TEXT};
        border-radius: 7px;
        font-weight: 700;
        border: 1px solid {KM_BORDER};
        padding: 0.45rem 0.9rem;
        transition: all 0.15s ease;
    }}
    .stButton>button:hover {{
        border-color: {KM_AMBER};
        color: {KM_AMBER};
    }}
    /* Primary buttons — solid amber CTA, e.g. Build Session Plan */
    .stButton>button[kind="primary"] {{
        background-color: {KM_AMBER};
        color: #1A1206;
        border: none;
        font-weight: 800;
        padding: 0.65rem 1rem;
    }}
    .stButton>button[kind="primary"]:hover {{
        background-color: #ffb945;
        color: #1A1206;
        transform: translateY(-1px);
    }}
    .thin-divider {{
        margin: 12px 0;
        border-bottom: 1px solid {KM_BORDER};
    }}
    .ref-badge {{
        font-size: 10.5px;
        background-color: {KM_AMBER_DIM};
        color: {KM_AMBER};
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 6px;
        font-weight: 700;
        border: 1px solid rgba(245,166,35,0.3);
    }}
</style>
""", unsafe_allow_html=True)

# Reserved slot for the top app header. It's rendered later (once
# candidate/session/data-source state actually exists), but st.empty()
# keeps its position pinned here at the very top of the page regardless
# of where in the script it's filled in — see the "render header" call
# near the data-loading section below.
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

# ==========================================
# CENTRALIZED DATA DICTIONARIES & PROGRAM MODULES
# ==========================================

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

# ==========================================
# ATA-CHAPTER-FAMILY GENERIC FALLBACKS
# Real per-scenario OB banks used by other operators aren't publicly
# available — they're proprietary internal training material tied to each
# operator's own SOPs, so there's no legitimate "look up what other
# airlines use" source to draw from. What IS usable is the ATA chapter
# already present in Scenarios.csv: rather than one single generic OB set
# for every unscripted scenario, group by system family and weight each
# family's competency emphasis appropriately (e.g. a hydraulics failure
# genuinely stresses FPM/degraded handling more than an electrical bus
# failure does). This is a domain-reasoned construction grounded in ICAO
# Doc 9995's competency definitions and standard A320 system knowledge —
# not sourced from any specific operator's proprietary material — but it's
# a meaningfully better fallback than one undifferentiated generic entry.
# ==========================================
ATA_TO_FAMILY = {
    21: "AIR_SYS", 30: "AIR_SYS", 35: "AIR_SYS", 36: "AIR_SYS", 31: "AIR_SYS",
    22: "AUTOFLT",
    24: "ELEC",
    27: "FLTCTRL",
    28: "FUEL",
    29: "HYD",
    32: "GEAR",
    34: "NAV",
    26: "PWR", 52: "PWR", 54: "PWR", 57: "PWR",
    70: "PWR", 71: "PWR", 72: "PWR", 73: "PWR", 74: "PWR", 75: "PWR", 76: "PWR", 77: "PWR", 78: "PWR", 79: "PWR", 80: "PWR",
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


SCENARIO_OB_LIBRARY = {}  # populated after sidebar upload — normalized event name -> {"pta":, "sequence":, "cbta_focus":}


def _file_cache_token(source):
    """Extra cache-key input for the @st.cache_data loaders below, whose
    real argument is often a plain bundled-file PATH STRING (e.g.
    "Scenario_Observable_Behaviours.xlsx" from find_bundled_file) rather
    than an uploaded-file object. st.cache_data keys its cache on the
    argument's VALUE — for a path string that's just the path text, not
    the file's actual bytes on disk. So replacing what's AT that path
    (e.g. a `git push` to Streamlit Cloud that updates the file without
    necessarily forcing a full process restart) can silently keep
    serving a stale cached read, because from the cache's point of view
    the argument never changed. This has already caused a real, hard
    to diagnose bug: after updating Scenario_Observable_Behaviours.xlsx
    and syncing to GitHub, the deployed app kept reporting an old
    profile count (34) while a fresh local run correctly showed 47 —
    same file, stale cache.
    Passing this token alongside the path means any on-disk replacement
    changes the effective cache key too, forcing a fresh read
    automatically — no manual "Reboot app" needed. Uploaded-file-widget
    objects don't need this: Streamlit's cache_data already hashes those
    by their actual bytes, not by identity/path.

    IMPORTANT: this token must be received as a parameter WITHOUT a
    leading underscore wherever it's used (see cache_token below, and
    cache_token_a/cache_token_b on load_scenario_database). st.cache_data
    silently EXCLUDES any underscore-prefixed parameter from its hash key
    entirely (that's the documented mechanism for passing unhashable
    objects like DB connections through the cache safely) — this
    function's first version named it "_cache_token", which meant the
    fix did nothing at all despite the token itself correctly changing
    on every call. Confirmed by reproducing the exact failure in
    isolation (a trivial cache_data test with an underscore-prefixed
    parameter) before renaming.
    """
    try:
        return os.path.getmtime(source) if isinstance(source, (str, os.PathLike)) and os.path.exists(source) else None
    except Exception:
        return None


@st.cache_data(show_spinner="Loading scenario-specific Observable Behaviours...")
def load_scenario_obs_library(source, cache_token=None):
    """Load a Scenario_Observable_Behaviours.xlsx (built from the template)
    into a lookup usable by get_exercise_for_event. Rows with no OB text
    filled in are skipped entirely, so an event with an empty row still
    correctly falls through to the ATA-family/generic fallback rather than
    resolving to an empty sequence."""
    try:
        try:
            df_obs = pd.read_excel(source, sheet_name="Scenario OBs")
        except ValueError:
            # Uploaded file doesn't use the template's sheet name — fall
            # back to whichever sheet pandas reads by default.
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
            if not obs:
                continue  # nothing filled in for this event yet — leave it to the fallback chain
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
    """Resolve the OB sequence to display/grade for a given event, in
    priority order:
      1. A dedicated, hand-authored syllabus exercise if its keywords match
         (major maneuvers like EFATO, engine fire, etc.)
      2. A scenario-specific entry from an uploaded
         Scenario_Observable_Behaviours.xlsx, if the training department
         has authored one for this exact event (fuzzy-matched by name).
      3. An ATA-chapter-family generic set if the event's ATA chapter maps
         to one.
      4. The fully generic fallback.
    Without tier 2, every event sharing an ATA chapter showed IDENTICAL
    OB text regardless of which specific failure it actually was — this
    is the fix for that: it lets the training team author real,
    scenario-specific content incrementally via a spreadsheet, without
    needing a code change per scenario."""
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
            if close:
                entry = SCENARIO_OB_LIBRARY[close[0]]
        if entry:
            return f"Scenario-Specific: {event_title}", entry["sequence"], entry["cbta_focus"]

    if ata is not None:
        try:
            family = ATA_TO_FAMILY.get(int(ata))
        except (TypeError, ValueError):
            family = None
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

# ==========================================
# KM MALTA AIRLINES OFFICIAL GRADING SYSTEM
# Sourced directly from Operations Manual Part D, §3.1.1.1 "Grading
# System" (Issue 03, Rev 00/02) — this replaces an earlier, generic
# EASA-style approximation with the company's actual adopted scale,
# labels, and per-competency Key Performance Indicators. This is the
# single most authoritative source available for this tool: it's the
# document instructors are already required to grade against.
# ==========================================
GRADE_LABELS = {5: "Excellent", 4: "Very Good", 3: "Good", 2: "Minimum Acceptable Level", 1: "Unsatisfactory"}

GRADE_DESCRIPTORS = {
    5: "The pilot always demonstrates all the required behavioural indicators in an effective and efficient manner. Safety is significantly enhanced.",
    4: "The pilot demonstrated effective knowledge, skill and attitudes by demonstrating all the required behavioural markers in a regular manner. Safety is always enhanced.",
    3: "The pilot demonstrated adequate knowledge, skill and attitude by demonstrating all the required behavioural markers in a frequent manner, resulting in a safe operation.",
    2: "The pilot demonstrated knowledge, skill and attitude at a minimum acceptable level by only occasionally demonstrating some of the behavioural markers when required, but never resulting in an unsafe situation.",
    1: "The pilot did not demonstrate the necessary knowledge, skill and attitude in any of the behavioural indicators when required, which resulted in an unsafe situation.",
}

# Official Key Performance Indicators per competency (OM-D §3.1.1.1).
# These are the actual behavioural markers instructors observe against —
# far more specific than the one-line competency names above.
COMPETENCY_KPIS = {
    "APK": [
        "Follows SOPs unless a higher degree of safety dictates otherwise",
        "Identifies and applies all operating instructions in a timely manner",
        "Correctly uses aircraft systems, controls and instruments",
        "Safely manages the aircraft to achieve best value for the operation, including fuel, the environment, passenger comfort and punctuality",
        "Identifies the source of operating instructions",
    ],
    "COM": [
        "Knows what, how, where, when, how much and with whom he or she needs to communicate",
        "Ensures the recipient is ready and able to receive the information",
        "Conveys messages and information clearly, accurately, timely and adequately",
        "Confirms that the recipient correctly understands important information",
        "Listens actively, patiently and demonstrates understanding when receiving information",
        "Asks relevant and effective questions and offers suggestions",
        "Uses appropriate body language, eye contact and tone, and correctly interprets non-verbal communication of others",
        "Is receptive to other people's views and is willing to compromise",
    ],
    "FPA": [
        "Controls the aircraft using automation with accuracy and smoothness as appropriate to the situation",
        "Detects deviations from the desired aircraft trajectory and takes appropriate action",
        "Contains the aircraft within the normal flight envelope",
        "Manages the flight path to achieve optimum operational performance",
        "Maintains the desired flight path during flight using automation whilst managing other tasks and distractions",
        "Selects appropriate level and mode of automation in a timely manner considering phase of flight and workload",
        "Effectively monitors automation, including engagement and automatic mode transitions",
    ],
    "FPM": [
        "Controls the aircraft manually with accuracy and smoothness as appropriate to the situation",
        "Detects deviations from the desired aircraft trajectory and takes appropriate action",
        "Contains the aircraft within the normal flight envelope",
        "Controls the aircraft safely using only the relationship between aircraft attitude, speed and thrust",
        "Manages the flight path to achieve optimum operational performance",
        "Maintains the desired flight path during manual flight whilst managing other tasks and distractions",
        "Selects appropriate level and mode of flight guidance systems in a timely manner considering phase of flight and workload",
        "Effectively monitors flight guidance systems, including engagement and automatic mode transitions",
    ],
    "KNO": [
        "Demonstrates practical and applicable knowledge of limitations and systems and their interaction",
        "Demonstrates required knowledge of published operating instructions",
        "Demonstrates knowledge of the physical environment, the air traffic environment including routing, weather, airports and operational infrastructure",
        "Demonstrates appropriate knowledge of applicable legislation",
        "Knows where to source required information",
        "Demonstrates a positive interest in acquiring knowledge",
        "Is able to apply knowledge effectively",
    ],
    "LTW": [
        "Understands and agrees with the crew's roles and objectives",
        "Is approachable, enthusiastic, motivating and considerate of others",
        "Uses initiative, gives direction and takes responsibility when required",
        "Anticipates other crew members' needs and carries out instructions when directed",
        "Is open and honest about thoughts, concerns and intentions",
        "Gives and receives both criticism and praise well and admits mistakes",
        "Confidently says and does what is important for safety",
        "Demonstrates empathy, respect and tolerance for other people",
        "Involves others in planning and allocates activities fairly and appropriately to abilities",
    ],
    "PSD": [
        "Identifies and verifies why things have gone wrong and does not jump to conclusions or makes uninformed assumptions",
        "Seeks accurate and adequate information from appropriate sources",
        "Perseveres in working through a problem without reducing safety",
        "Uses appropriate agreed and timely decision-making processes",
        "Applies essential and desirable criteria and prioritises",
        "Considers as many options as practicable",
        "Makes decisions when needed, reviews and changes them if required",
        "Considers risks but does not take unnecessary risks",
        "Improvises appropriately when faced with unforeseen circumstances to achieve the safest outcome",
    ],
    "SAW": [
        "Is aware of the state of the aircraft and its systems",
        "Is aware of where the aircraft is and its environment",
        "Keeps track of time and fuel",
        "Is aware of the condition of people involved in the operation including passengers",
        "Develops \"what if\" scenarios and plans for contingencies",
        "Identifies threats to the safety of the aircraft and people, and takes appropriate action",
    ],
    "WLM": [
        "Is calm, relaxed, careful and not impulsive",
        "Plans, prepares, prioritises and schedules tasks effectively",
        "Manages time efficiently when carrying out tasks",
        "Offers and accepts assistance, delegates when necessary and asks for help early",
        "Reviews, monitors and cross-checks actions conscientiously",
        "Ensures tasks are completed",
        "Manages interruptions, distractions, variations and failures effectively",
    ],
}

# Official per-competency, per-grade descriptor text (OM-D §3.1.1.1) —
# what instructors actually grade against, rather than the generic
# 1-5 scale text applied uniformly across every competency.
COMPETENCY_GRADE_TEXT = {
    "APK": {
        5: "The pilot applied procedures very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot applied procedures effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot applied procedures adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot applied procedures at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not apply procedures correctly, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "COM": {
        5: "The pilot communicated very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot communicated effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot communicated adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot communicated at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not communicate effectively, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "FPA": {
        5: "The pilot managed the automation very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot managed the automation effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot managed the automation adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot managed the automation at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not manage the automation effectively, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "FPM": {
        5: "The pilot controlled the aircraft very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot controlled the aircraft effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot controlled the aircraft adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot controlled the aircraft at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not control the aircraft effectively, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "KNO": {
        5: "The pilot showed exemplary knowledge, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot showed effective knowledge, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot showed adequate knowledge, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot showed knowledge to a minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not show adequate knowledge, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "LTW": {
        5: "The pilot led and worked as a team member very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot led and worked as a team member effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot led and worked as a team member adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot led and worked as a team member at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not lead or work as a team member, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "PSD": {
        5: "The pilot solved problems and made decisions very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot solved problems and made decisions effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot solved problems and made decisions adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot solved problems and made decisions at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not solve problems and make decisions effectively, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "SAW": {
        5: "The pilot's situation awareness was excellent, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot's situation awareness was very good, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot's situation awareness was adequate, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot's situation awareness was at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot's situation awareness was not adequate, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
    "WLM": {
        5: "The pilot managed workload very effectively, by always demonstrating all of the performance indicators to a high standard when required, which significantly enhanced safety, effectiveness and efficiency.",
        4: "The pilot managed workload effectively, by regularly demonstrating all of the performance indicators when required, which enhanced safety.",
        3: "The pilot managed workload very adequately, by regularly demonstrating most of the performance indicators when required, which resulted in a safe operation.",
        2: "The pilot managed workload at the minimum acceptable level, by only occasionally demonstrating some of the performance indicators when required, but which did not result in an unsafe situation.",
        1: "The pilot did not manage workload effectively, by rarely demonstrating any of the performance indicators when required, which resulted in an unsafe situation.",
    },
}

# OM-D §3.1.1.1 Flight Phase definitions, used for the Grading Standard reference tab.
PHASE_DEFINITIONS = {
    1: "Flight preparation to completion of line-up.",
    2: "From the application of take-off thrust until the completion of flap and slat retraction.",
    3: "From the completion of flap and slat retraction until top of climb.",
    4: "From top of climb until top of descent.",
    5: "From top of descent until the earlier of first slat/flap extension or crossing the initial approach fix.",
    6: "From the earlier of first slat/flap extension or crossing the initial approach fix until 15 m (50 ft) AAL, including go-around.",
    7: "From 15 m (50 ft) AAL until reaching taxi speed.",
    8: "From reaching taxi speed until engine shutdown.",
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

def apply_competency_filter(cands, target_competency):
    """The sidebar's 'Target Competency' selector was being collected into
    slot_configurations but this function didn't exist yet, so the filter
    was pure decoration — every slot ignored it regardless of selection."""
    if target_competency == "Any" or cands.empty:
        return cands
    return cands[cands["COMPETENCIES"].apply(lambda c: target_competency in c)]

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

# Fixed color per competency so the same code always reads the same
# way across the flow diagram, chips, and any future chart — a stable
# visual vocabulary rather than a color picked per-render.
COMPETENCY_COLORS = {
    "APK": "#0284C7", "COM": "#7C3AED", "FPA": "#0891B2", "FPM": "#059669",
    "KNO": "#CA8A04", "LTW": "#DB2777", "PSD": "#DC2626", "SAW": "#EA580C", "WLM": "#4F46E5",
}


def build_ob_flow_html(sequence_data):
    """Render a scenario's phase sequence as a connected flow — one card per
    phase, each showing its target action and OB chips colored by
    competency, joined by a vertical connector. This draws the exact same
    PROGRAM_SYLLABUS_EXERCISES / SCENARIO_OB_LIBRARY structure the app
    already grades against; it's a rendering change, not a new data model."""
    n = len(sequence_data)
    parts = ["<div style='padding:4px 0;'>"]
    for idx, step in enumerate(sequence_data):
        obs_html = ""
        for ob in step["obs"]:
            color = COMPETENCY_COLORS.get(ob.get("comp"), "#64748B")
            ref_title = DOCUMENT_REFERENCES.get(ob.get("ref"), ob.get("ref", ""))
            obs_html += (
                f"<div style='display:flex; gap:8px; align-items:flex-start; margin-bottom:6px;'>"
                f"<span style='flex-shrink:0; background:{color}1A; color:{color}; border:1px solid {color}55; "
                f"padding:1px 7px; border-radius:10px; font-size:10.5px; font-weight:700; margin-top:1px;'>{ob.get('comp','')}</span>"
                f"<span style='font-size:13px; color:var(--text-color);' title='{ref_title}'>{ob['text']}</span>"
                f"</div>"
            )
        parts.append(f"""
        <div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.25);
                    border-left:4px solid #0284C7; border-radius:8px; padding:14px 16px; margin-bottom:4px;'>
            <div style='font-size:14.5px; font-weight:600; color:var(--text-color); margin-bottom:6px;'>{step['phase_name']}</div>
            <div style='font-size:12.5px; opacity:0.8; margin-bottom:10px;'><b>Target action:</b> {step['pta']}</div>
            {obs_html}
        </div>
        """)
        if idx < n - 1:
            parts.append("<div style='text-align:center; font-size:16px; color:#0284C7; margin:2px 0 8px 0;'>&#8595;</div>")
    parts.append("</div>")
    return "".join(parts)


def build_competency_venn_svg(sets_dict):
    """A true 2- or 3-circle Venn comparing the competencies exercised by
    2-3 chosen slots. Only geometrically valid for 2-3 sets — a 4th circle
    cannot represent every possible overlap correctly, so callers should
    cap selection at 3 and use the session-wide bar chart for full
    coverage instead."""
    labels = list(sets_dict.keys())
    n = len(labels)
    if n not in (2, 3):
        return "<div style='font-size:12.5px; opacity:0.7;'>Select exactly 2 or 3 slots to compare.</div>"

    colors = ["#378ADD", "#1D9E75", "#D85A30"]
    if n == 2:
        centers = [(220, 180), (340, 180)]
        r = 130
        A, B = sets_dict[labels[0]], sets_dict[labels[1]]
        only_a, only_b, both = sorted(A - B), sorted(B - A), sorted(A & B)
        circles = "".join(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colors[i]}" fill-opacity="0.28" stroke="{colors[i]}" stroke-width="1"/>'
            for i, (cx, cy) in enumerate(centers)
        )
        text = (
            f'<text x="150" y="70" font-size="14" font-weight="600" fill="var(--text-color)">{labels[0]}</text>'
            f'<text x="410" y="70" font-size="14" font-weight="600" fill="var(--text-color)" text-anchor="end">{labels[1]}</text>'
            f'<text x="175" y="185" font-size="13" fill="var(--text-color)" text-anchor="middle">{", ".join(only_a) or "—"}</text>'
            f'<text x="385" y="185" font-size="13" fill="var(--text-color)" text-anchor="middle">{", ".join(only_b) or "—"}</text>'
            f'<text x="280" y="185" font-size="13" font-weight="700" fill="var(--text-color)" text-anchor="middle">{", ".join(both) or "—"}</text>'
        )
        vh = 280
    else:
        centers = [(270, 190), (410, 190), (340, 310)]
        r = 130
        A, B, C = sets_dict[labels[0]], sets_dict[labels[1]], sets_dict[labels[2]]
        only_a, only_b, only_c = sorted(A - B - C), sorted(B - A - C), sorted(C - A - B)
        ab, ac, bc = sorted((A & B) - C), sorted((A & C) - B), sorted((B & C) - A)
        abc = sorted(A & B & C)
        circles = "".join(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colors[i]}" fill-opacity="0.28" stroke="{colors[i]}" stroke-width="1"/>'
            for i, (cx, cy) in enumerate(centers)
        )
        text = (
            f'<text x="185" y="65" font-size="14" font-weight="600" fill="var(--text-color)">{labels[0]}</text>'
            f'<text x="495" y="65" font-size="14" font-weight="600" fill="var(--text-color)" text-anchor="end">{labels[1]}</text>'
            f'<text x="340" y="450" font-size="14" font-weight="600" fill="var(--text-color)" text-anchor="middle">{labels[2]}</text>'
            f'<text x="220" y="175" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(only_a) or "—"}</text>'
            f'<text x="460" y="175" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(only_b) or "—"}</text>'
            f'<text x="340" y="390" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(only_c) or "—"}</text>'
            f'<text x="340" y="150" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(ab) or "—"}</text>'
            f'<text x="255" y="330" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(ac) or "—"}</text>'
            f'<text x="425" y="330" font-size="12" fill="var(--text-color)" text-anchor="middle">{", ".join(bc) or "—"}</text>'
            f'<text x="340" y="255" font-size="12" font-weight="700" fill="var(--text-color)" text-anchor="middle">{", ".join(abc) or "—"}</text>'
        )
        vh = 480

    return f'<svg width="100%" viewBox="0 0 680 {vh}">{circles}{text}</svg>'

# ==========================================
# NAVIGATION TABS
# (tabs are created here, but only their labels/order are fixed by this
# call — the tab_session/tab_env split below runs their *bodies* wherever
# execution order actually requires, same pattern already used for
# tab_selector/tab_sql_schema elsewhere in this file.)
# ==========================================
tab_session, tab_env, tab_orca, tab_selector, tab_standard, tab_debrief, tab_history = st.tabs([
    "SES · Session Setup",
    "ENV · Environment & IOS",
    "ORC · OPC & ORCA Workflow",
    "SCN · Scenario Selector",
    "GRD · Grading Standard",
    "DBF · Session Debrief",
    "HST · Candidate History"
])

# SLOT CONFIGURATION & DATA SOURCES
# Moved out of the sidebar and into the Session Setup tab — this is the
# only tab these controls are ever used from, and removing the sidebar
# entirely gives every tab (especially the ORCA per-OB rows) the full
# window width to work with instead of losing a fixed slice of it
# permanently to a panel most tabs never touch.
# ==========================================
with tab_session:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>SES</span><span class='panel-title-text'>Slot Configuration</span></div>", unsafe_allow_html=True)

            if "slot_list" not in st.session_state:
                st.session_state.slot_list = [
                    {"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False},
                    {"phase": 2, "dod": 2, "role": "PF Focus", "type": "Any", "mandatory": True},
                    {"phase": 6, "dod": 2, "role": "PM Focus", "type": "Any", "mandatory": False},
                    {"phase": 7, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False}
                ]

            btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 4])
            with btn_c1:
                if st.button("➕ Add", use_container_width=True):
                    if len(st.session_state.slot_list) < 12:
                        st.session_state.slot_list.append({"phase": 1, "dod": 1, "role": "PF Focus", "type": "Any", "mandatory": False})
                        st.rerun()
            with btn_c2:
                if st.button("➖ Remove", use_container_width=True):
                    if len(st.session_state.slot_list) > 1:
                        st.session_state.slot_list.pop()
                        st.rerun()

            hdr_cols = st.columns([0.5, 1.3, 0.8, 1.1, 1.5, 1.3, 1.6, 0.9])
            for col, label in zip(hdr_cols, ["Slot", "Phase", "DOD", "Role", "Category", "ATA", "Competency", "Pin"]):
                col.markdown(f"<div style='font-size:11px; opacity:0.65; font-weight:600;'>{label}</div>", unsafe_allow_html=True)

            slot_configurations = []
            for i in range(len(st.session_state.slot_list)):
                slot_data = st.session_state.slot_list[i]
                row_cols = st.columns([0.5, 1.3, 0.8, 1.1, 1.5, 1.3, 1.6, 0.9])
                with row_cols[0]:
                    st.markdown(f"<div style='padding-top:8px; font-weight:600;'>{i+1}</div>", unsafe_allow_html=True)
                with row_cols[1]:
                    p_val = st.selectbox("Phase", options=ALL_PHASE_KEYS, index=ALL_PHASE_KEYS.index(slot_data["phase"]) if slot_data["phase"] in ALL_PHASE_KEYS else 0, format_func=lambda x: f"Ph {x}: {PHASE_NAMES[x].split('–')[1].strip()}", key=f"phase_sel_{i}", label_visibility="collapsed")
                with row_cols[2]:
                    d_val = st.selectbox("DOD", options=[1, 2, 3], index=slot_data["dod"]-1, format_func=lambda x: f"DOD {x}", key=f"dod_sel_{i}", label_visibility="collapsed")
                with row_cols[3]:
                    role_val = st.selectbox("Role", options=ROLE_OPTIONS, index=ROLE_OPTIONS.index(slot_data["role"]) if slot_data["role"] in ROLE_OPTIONS else 0, key=f"role_sel_{i}", label_visibility="collapsed")
                with row_cols[4]:
                    type_val = st.selectbox("Category", options=["Any", "Technical Failure", "Non-Technical / CRM (Non-ATA)", "ATA Specific"], key=f"type_sel_{i}", label_visibility="collapsed")
                with row_cols[5]:
                    ata_val = st.number_input("ATA Chapter", min_value=11, max_value=80, key=f"ata_sel_{i}", label_visibility="collapsed") if type_val == "ATA Specific" else None
                    if type_val != "ATA Specific":
                        st.markdown("<div style='opacity:0.4; font-size:12px; padding-top:8px;'>—</div>", unsafe_allow_html=True)
                with row_cols[6]:
                    comp_val = st.selectbox("Target Competency", options=["Any"] + list(COMPETENCY_KEYS.keys()), format_func=lambda x: x if x == "Any" else f"{x} – {COMPETENCY_KEYS[x]}", key=f"comp_sel_{i}", label_visibility="collapsed")
                with row_cols[7]:
                    is_mandatory = st.checkbox("Pin", value=slot_data.get("mandatory", False), key=f"mand_sel_{i}", label_visibility="collapsed")

                slot_configurations.append({"slot": i + 1, "phase": int(p_val), "dod": int(d_val), "role": role_val, "type": type_val, "ata": ata_val, "competency": comp_val, "mandatory": is_mandatory})

        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>SES</span><span class='panel-title-text'>Session Metadata & Device Setup</span></div>", unsafe_allow_html=True)
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                session_mode = st.selectbox("Training Focus / Mode", ["EBT Evaluation & Coaching", "EBT Line-Oriented Assessment", "Recurrent Check (LPC/OPC)"], key="session_mode")
            with m_col2:
                capt_name = st.text_input("Captain Name", key="capt_name")
                capt_staff_no = st.text_input("Captain Staff No.", value="", placeholder="e.g. KM10234", help="Used to match this candidate's record across sessions in the history database — a name alone isn't reliable for that (typos, duplicates).")
            with m_col3:
                fo_name = st.text_input("First Officer Name", key="fo_name")
                fo_staff_no = st.text_input("F/O Staff No.", value="", placeholder="e.g. KM10567")
            with m_col4:
                sim_id = st.text_input("Sim / Device ID", key="sim_id")

            p_col1, p_col2, p_col3, p_col4 = st.columns(4)
            with p_col1:
                aircraft_type = st.text_input("Aircraft Type", key="aircraft_type")
            with p_col2:
                program_code = st.text_input("Program", key="program_code")
            with p_col3:
                session_duration_h = st.number_input("Duration (h)", min_value=0.5, max_value=12.0, step=0.5, key="session_duration_h")
            with p_col4:
                max_dod_threshold = st.number_input("Total DOD Ceiling", min_value=1, max_value=30, value=6, step=1)
            allow_fallback = st.checkbox("Enable Smart Fallback (use closest available DOD if exact match missing)", value=True)

        ds_col, doc_col = st.columns(2)
        with ds_col:
            with st.container(border=True):
                st.markdown("<div class='panel-head'><span class='panel-code'>CSV</span><span class='panel-title-text'>Data Sources</span></div>", unsafe_allow_html=True)
                uploaded_scen = st.file_uploader("Scenarios.csv", type=["csv"], label_visibility="collapsed")
                uploaded_comp = st.file_uploader("Keypams.xlsx (optional)", type=["xlsx"], label_visibility="collapsed", help="Per-event competency flags.")
                uploaded_scenario_obs = st.file_uploader("Scenario_Observable_Behaviours.xlsx (optional)", type=["xlsx"], label_visibility="collapsed", help="Per-event PTA and Observable Behaviours authored by your training team — takes priority over the generic ATA-family fallback for any event it covers.")
                ds_status_placeholder = st.empty()
        with doc_col:
            with st.container(border=True):
                st.markdown("<div class='panel-head'><span class='panel-code'>DOC</span><span class='panel-title-text'>Document References</span></div>", unsafe_allow_html=True)
                for tag, title in DOCUMENT_REFERENCES.items():
                    st.markdown(f"<div class='doc-ref-row'><span class='doc-ref-tag'>[{tag}]</span> {title}</div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: left; font-size: 10.5px; color: rgba(255,255,255,0.35); margin-top: 10px;'>Designed by Shawn Abela · v5.0 2026</div>", unsafe_allow_html=True)

    # ==========================================
    # DATA SOURCE RESOLUTION & SCENARIO DATABASE LOADING
    # Runs here — inside col_left's part of this tab, after the
    # file_uploader widgets above, and before col_right below — because
    # the Session Summary / Competency Coverage / Generate panels on the
    # right all need `df` to exist first.
    # ==========================================
    def resource_path(relative_path):
        try: base_path = sys._MEIPASS
        except Exception: base_path = os.path.dirname(os.path.abspath(__file__))
        local_path = os.path.join(base_path, relative_path)
        if os.path.exists(local_path): return local_path
        parent_path = os.path.join(os.path.dirname(base_path), relative_path)
        return parent_path if os.path.exists(parent_path) else local_path

    def find_bundled_file(candidate_names):
        """Check each candidate filename (in order) next to the script and
        return the first one that actually exists. Used so a working file
        doesn't have to be renamed exactly to auto-load — e.g. the
        Scenario_Observable_Behaviours template still gets picked up whether
        it's saved with or without a '_TEMPLATE' suffix."""
        for name in candidate_names:
            path = resource_path(name)
            if os.path.exists(path):
                return path
        return None

    def source_display_name(source):
        """Best-effort human-readable filename for a 'source' value that may be
        a Streamlit UploadedFile (has a .name attribute, not path-like), a
        plain path string/Path from find_bundled_file/resource_path, or None.
        os.path.basename() alone only handles the string/Path case and raises
        TypeError on an UploadedFile — this covers all three cases."""
        if source is None:
            return None
        name = getattr(source, "name", None)
        if name:
            return os.path.basename(name)
        return os.path.basename(str(source))

    scenarios_source = uploaded_scen if uploaded_scen is not None else (find_bundled_file(["Scenarios.csv"]) or resource_path("Scenarios.csv"))
    competency_source = uploaded_comp if uploaded_comp is not None else find_bundled_file(["Keypams.xlsx"])
    scenario_obs_source = uploaded_scenario_obs if uploaded_scenario_obs is not None else find_bundled_file([
        "Scenario_Observable_Behaviours.xlsx",
        "Scenario_Observable_Behaviours_TEMPLATE.xlsx",
    ])

    if scenario_obs_source is not None:
        SCENARIO_OB_LIBRARY, scenario_obs_err = load_scenario_obs_library(scenario_obs_source, _file_cache_token(scenario_obs_source))
        if scenario_obs_err:
            st.warning(f"Could not read {source_display_name(scenario_obs_source)}: {scenario_obs_err}")

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

            def resolve_competencies(ev, phase, ata):
                codes = set()
                ev_upper = str(ev).replace("\xa0", " ").upper()
                for ex_key, ex_data in PROGRAM_SYLLABUS_EXERCISES.items():
                    if ex_key == "EX-00_GENERIC":
                        continue
                    if any(kw in ev_upper for kw in ex_data["keywords"]):
                        codes.update(ex_data["cbta_focus"])
                if codes:
                    return sorted(codes)

                # A training-team-authored scenario-specific entry is more
                # authoritative than the blunter Keypams.xlsx flags, so it's
                # checked before Keypams, not after.
                if SCENARIO_OB_LIBRARY:
                    norm_ev_lib = _normalize_event_name(ev)
                    lib_entry = SCENARIO_OB_LIBRARY.get(norm_ev_lib)
                    if lib_entry is None:
                        close_lib = difflib.get_close_matches(norm_ev_lib, list(SCENARIO_OB_LIBRARY.keys()), n=1, cutoff=0.72)
                        if close_lib:
                            lib_entry = SCENARIO_OB_LIBRARY[close_lib[0]]
                    if lib_entry:
                        return sorted(lib_entry["cbta_focus"])

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
                if codes:
                    return sorted(codes)
                # No keyword, scenario-library, or Keypams match — fall back to
                # the ATA-chapter family generic (more specific than the fully
                # generic set) when the event's ATA chapter maps to one.
                _, _, fallback_focus = get_exercise_for_event(ev, ata)
                return sorted(fallback_focus)

            df["COMPETENCIES"] = df.apply(lambda r: resolve_competencies(r["EVENT"], r["PHASES"], r.get("ATA")), axis=1)
            match_stats["matched_events"] = len(matched_events)
            return df, match_stats
        except Exception as e:
            return None, str(e)

    df, match_stats = load_scenario_database(scenarios_source, competency_source, _file_cache_token(scenarios_source), _file_cache_token(competency_source))

    def _source_tag(source, uploaded_widget_value):
        if uploaded_widget_value is not None:
            return "uploaded this session"
        if source is not None:
            return f"auto-loaded from `{source_display_name(source)}`"
        return "not supplied"

    with ds_status_placeholder.container():
        # load_scenario_database() returns (None, "<error string>") on
        # failure (e.g. Scenarios.csv missing/unreadable) — match_stats is
        # only guaranteed to be a dict when df loaded successfully, so
        # every status line below must guard on that first.
        #
        # The ver26 redesign collapsed this to a bare LOADED/OPTIONAL flag
        # per source, dropping the actual counts/match-rate detail that
        # used to be shown (row counts, Keypams match %, OB profile count)
        # — restoring that detail as a second line under each status row,
        # since it's genuinely useful diagnostic info (e.g. a low Keypams
        # match % usually means an event-naming mismatch worth checking).
        scen_ok = df is not None and not df.empty
        scen_status = "LOADED" if scen_ok else "MISSING"
        scen_cls = "ds-status-loaded" if scen_ok else "ds-status-optional"
        st.markdown(f"<div class='ds-row'><span>Scenarios.csv</span><span class='{scen_cls}'>{scen_status}</span></div>", unsafe_allow_html=True)
        if scen_ok:
            st.markdown(f"<div class='ds-detail'>{len(df)} scenario/phase rows</div>", unsafe_allow_html=True)
        elif isinstance(match_stats, str):
            st.caption(f"⚠️ {match_stats}")

        comp_status = "LOADED" if (scen_ok and match_stats.get("keypams_loaded")) else "OPTIONAL"
        comp_cls = "ds-status-loaded" if comp_status == "LOADED" else "ds-status-optional"
        st.markdown(f"<div class='ds-row'><span>Keypams.xlsx</span><span class='{comp_cls}'>{comp_status}</span></div>", unsafe_allow_html=True)
        if comp_status == "LOADED":
            _total = match_stats.get("total_events", 0)
            _matched = match_stats.get("matched_events", 0)
            _pct = (_matched / _total * 100) if _total else 0
            st.markdown(f"<div class='ds-detail'>cross-matched {_matched}/{_total} events ({_pct:.0f}%)</div>", unsafe_allow_html=True)

        obs_status = "LOADED" if (scenario_obs_source is not None and SCENARIO_OB_LIBRARY) else "OPTIONAL"
        obs_cls = "ds-status-loaded" if obs_status == "LOADED" else "ds-status-optional"
        st.markdown(f"<div class='ds-row'><span>Scenario_Observable_Behaviours.xlsx</span><span class='{obs_cls}'>{obs_status}</span></div>", unsafe_allow_html=True)
        if obs_status == "LOADED":
            st.markdown(f"<div class='ds-detail'>{len(SCENARIO_OB_LIBRARY)} scenario-specific profile(s)</div>", unsafe_allow_html=True)

        st.caption(f"Scenarios: {_source_tag(scenarios_source, uploaded_scen)} · Keypams: {_source_tag(competency_source, uploaded_comp)} · Scenario OBs: {_source_tag(scenario_obs_source, uploaded_scenario_obs)}")

    with col_right:
        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>SUM</span><span class='panel-title-text'>Session Summary</span></div>", unsafe_allow_html=True)
            mandatory_count = sum(1 for c in slot_configurations if c.get("mandatory"))
            dur_h = float(st.session_state.session_duration_h)
            dur_str = f"{int(dur_h):02d}:{int(round((dur_h % 1) * 60)):02d} h"
            sum_c1, sum_c2 = st.columns(2)
            with sum_c1:
                st.markdown(f"<div class='stat-label'>Slots</div><div class='stat-value stat-value-accent'>{len(slot_configurations)} / 12</div>", unsafe_allow_html=True)
            with sum_c2:
                st.markdown(f"<div class='stat-label'>Mandatory</div><div class='stat-value stat-value-green'>{mandatory_count:02d}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            sum_c3, sum_c4 = st.columns(2)
            with sum_c3:
                st.markdown(f"<div class='stat-label'>Aircraft</div><div class='stat-value'>{st.session_state.aircraft_type}</div>", unsafe_allow_html=True)
            with sum_c4:
                st.markdown(f"<div class='stat-label'>Program</div><div class='stat-value'>{st.session_state.program_code}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            sum_c5, sum_c6 = st.columns(2)
            with sum_c5:
                st.markdown(f"<div class='stat-label'>Session Type</div><div class='stat-value stat-value-accent'>{SESSION_MODE_SHORT.get(st.session_state.session_mode, st.session_state.session_mode)}</div>", unsafe_allow_html=True)
            with sum_c6:
                st.markdown(f"<div class='stat-label'>Duration</div><div class='stat-value'>{dur_str}</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>COV</span><span class='panel-title-text'>Competency Coverage</span></div>", unsafe_allow_html=True)
            # Previously sourced from each slot's 'Target Competency' filter
            # dropdown — which most slots leave on "Any", so badges barely
            # lit regardless of what was actually generated. Now sourced
            # from the real per-event COMPETENCIES (resolve_competencies())
            # of the generated session when one exists, falling back to the
            # filter-based preview only before a plan has been built.
            _generated_df = st.session_state.get("final_df")
            if _generated_df is not None and not _generated_df.empty and "COMPETENCIES" in _generated_df.columns:
                active_comps = set()
                for codes in _generated_df["COMPETENCIES"]:
                    if isinstance(codes, (list, tuple, set)):
                        active_comps.update(codes)
                coverage_note = f"{len(active_comps)} of 9 core competencies actually targeted by the {len(_generated_df)} scenario(s) in the built session."
            else:
                active_comps = {c["competency"] for c in slot_configurations if c.get("competency") and c["competency"] != "Any"}
                coverage_note = f"{len(active_comps)} of 9 core competencies pinned via slot filters so far — build the session plan to see real per-scenario coverage."
            comp_order = ["APK", "COM", "FPA", "FPM", "KNO", "LTW", "PSD", "SAW", "WLM"]
            badges_html = "".join(
                f"<span class='comp-badge {'comp-badge-active' if code in active_comps else 'comp-badge-inactive'}' "
                f"title='{COMPETENCY_KEYS.get(code, code)}'>{code}</span>"
                for code in comp_order
            )
            st.markdown(f"<div>{badges_html}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:11px; color:{KM_TEXT_MUTED}; margin-top:8px;'>{coverage_note}</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("<div class='panel-head'><span class='panel-code'>GEN</span><span class='panel-title-text'>Generate</span></div>", unsafe_allow_html=True)
            if st.button("📄  Build Session Plan", type="primary", use_container_width=True):
                st.session_state.trigger_generation = True

    if st.session_state.get("trigger_generation", False):
        if df is None or df.empty:
            st.session_state.trigger_generation = False
            st.warning("Can't build a session plan — Scenarios.csv isn't loaded. Upload it in Data Sources above, or check the auto-load status there.")
        else:
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
            st.session_state.trigger_generation = False
            st.session_state.db_session_id = None  # a freshly generated profile is a new history record, not an update to the last one
            st.session_state.just_generated = True  # shown once on the rerun below, then cleared
            # The Competency Coverage panel above reads st.session_state.final_df,
            # but it's rendered EARLIER in script order than this block (Streamlit
            # runs top-to-bottom on every interaction) — so on the very click that
            # builds the plan, that panel still saw the old/empty final_df and
            # showed 0/9. Forcing an immediate rerun means the next pass renders
            # the panel with final_df already populated, instead of only catching
            # up on some later, unrelated interaction.
            st.rerun()

    if st.session_state.pop("just_generated", False):
        st.success("Session Profile Generated!")

    # ---- Render the top header now that session/candidate/data-source
    # state actually exists (header_placeholder was created at the very
    # top of the script, before any of this was known — see PAGE CONFIG
    # & DASHBOARD THEME section). ----
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
                <div class="km-subtitle">A320 · Evidence-Based Training · Competency Planner</div>
            </div>
        </div>
        <div class="km-header-right">
            <div class="km-meta">
                <div class="km-meta-label">Session</div>
                <div class="km-meta-value km-meta-value-accent">{_session_label}</div>
            </div>
            <div class="km-meta">
                <div class="km-meta-label">Candidate · Capt</div>
                <div class="km-meta-value">{st.session_state.capt_name}</div>
            </div>
            <div class="km-meta">
                <div class="km-meta-label">Candidate · F/O</div>
                <div class="km-meta-value">{st.session_state.fo_name}</div>
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
        
        _, seq_data, _ = get_exercise_for_event(row['EVENT'], row.get('ATA'))

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

# ==========================================
# (Former standalone data-source status banner removed — this info
# now lives in the Session Setup > Data Sources panel above, with its
# own LOADED/OPTIONAL pill per file, computed right where the panel
# is rendered.)
# ==========================================

with tab_history:
    st.markdown("#### 🗂️ Candidate Session History")
    st.markdown(
        "Looks up every session a candidate has been graded in, by staff number — across both the "
        "Session Setup and Uploaded Syllabus workflows. This is a **local field-testing log**, not a "
        "replacement for any official system of record."
    )
    lookup_staff_no = st.text_input("Staff Number", value="", placeholder="e.g. KM10234", key="history_lookup_staff_no")
    if lookup_staff_no.strip():
        candidate_info, grade_rows = get_candidate_history(lookup_staff_no)
        if candidate_info is None:
            st.warning(f"No candidate found with staff number '{lookup_staff_no.strip()}'. They may not have been graded in a saved session yet, or the number doesn't match what was entered at the time.")
        else:
            st.success(f"✓ {candidate_info['full_name']} — {len(candidate_info['sessions'])} session(s) on record.")

            sessions_df = pd.DataFrame(candidate_info["sessions"], columns=["Session ID", "Date", "Sim/Device", "Mode", "Workflow", "Seat"])
            st.markdown("<b>Sessions</b>", unsafe_allow_html=True)
            st.dataframe(sessions_df, use_container_width=True, hide_index=True)

            comp_grades_history = {}
            for _, _, _, grade, comp_code, comp_grade, observed, _ in grade_rows:
                if comp_code and observed:
                    comp_grades_history.setdefault(comp_code, []).append(comp_grade if comp_grade is not None else grade)

            if comp_grades_history:
                st.markdown("<b>Average Grade by Competency (all sessions on record)</b>", unsafe_allow_html=True)
                trend_df = pd.DataFrame({
                    "Competency": list(comp_grades_history.keys()),
                    "Avg Grade": [sum(v) / len(v) for v in comp_grades_history.values()],
                    "Times Graded": [len(v) for v in comp_grades_history.values()],
                }).set_index("Competency")
                st.bar_chart(trend_df["Avg Grade"])
                st.dataframe(trend_df, use_container_width=True)

                low_grades = [(s_id, ev, g) for s_id, _, ev, g, _, _, _, _ in grade_rows if g is not None and g <= 2]
                if low_grades:
                    st.markdown("<b>Below-Standard Items (Grade ≤2) Across History</b>", unsafe_allow_html=True)
                    low_df = pd.DataFrame(low_grades, columns=["Session ID", "Event", "Grade"]).drop_duplicates()
                    st.dataframe(low_df, use_container_width=True, hide_index=True)
            else:
                st.info("No competency-level grades recorded yet for this candidate.")
    else:
        st.info("Enter a staff number above to retrieve that candidate's session history.")

with tab_standard:
    st.markdown("#### 📐 KM Malta Airlines Official Grading Standard")
    st.markdown("Sourced directly from **Operations Manual Part D, §3.1.1.1 (Grading System)**. Reference this before and during grading — every instructor grading against the same published wording is what makes grading consistent across the training department.")

    st.markdown("<b>1–5 Grading Scale</b>", unsafe_allow_html=True)
    for g in [5, 4, 3, 2, 1]:
        badge = "status-badge-ok" if g >= 2 else "status-badge-warn"
        st.markdown(f"""
        <div style="display:flex; gap:10px; align-items:flex-start; margin-bottom:6px;">
            <div class="{badge}" style="min-width:150px;">Grade {g} ({GRADE_LABELS[g]})</div>
            <div style="font-size:12.5px; opacity:0.9;">{GRADE_DESCRIPTORS[g]}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("<div style='font-size:11px; opacity:0.65; margin-top:4px;'>Grade 2 is a pass, not a fail — but OM-D requires it to be reviewed by DCT. Grade 1 triggers the Below Adequate Grading process (APP.5.1.11 during training/LIFUS, APP.5.1.12 during a check).</div>", unsafe_allow_html=True)

    st.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
    st.markdown("<b>Core Competencies & Key Performance Indicators (KPIs)</b>", unsafe_allow_html=True)
    sel_comp_ref = st.selectbox("View KPIs and per-grade wording for:", options=list(COMPETENCY_KEYS.keys()), format_func=lambda x: f"{x} – {COMPETENCY_KEYS[x]}", key="grading_standard_comp_select")
    st.markdown("<div style='font-size:11.5px; opacity:0.7; margin-bottom:6px;'>Key Performance Indicators:</div>", unsafe_allow_html=True)
    for kpi in COMPETENCY_KPIS.get(sel_comp_ref, []):
        st.markdown(f"<div style='font-size:12.5px; margin-bottom:3px;'>• {kpi}</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    for g in [5, 4, 3, 2, 1]:
        badge = "status-badge-ok" if g >= 2 else "status-badge-warn"
        st.markdown(f"""
        <div style="display:flex; gap:10px; align-items:flex-start; margin-bottom:6px;">
            <div class="{badge}" style="min-width:64px;">Grade {g}</div>
            <div style="font-size:12px; opacity:0.9;">{COMPETENCY_GRADE_TEXT.get(sel_comp_ref, {}).get(g, '')}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
    st.markdown("<b>Flight Phase Definitions</b>", unsafe_allow_html=True)
    for p, desc in PHASE_DEFINITIONS.items():
        st.markdown(f"<div style='font-size:12px; margin-bottom:3px;'><b>{PHASE_NAMES[p]}:</b> {desc}</div>", unsafe_allow_html=True)

# NOTE: tab_env's inputs are collected here, BEFORE tab_session, even
# though tab_session is visually the first tab (visual order is fixed by
# the st.tabs([...]) call above, not by code execution order). This
# matters: tab_session's PDF export needs the real IOS/weather values
# (aircraft weights, airport, wind, RCAM, visibility) to build an accurate
# session record, and TEM threat/error tagging needs the real weather to
# tag scenarios correctly. Previously this code ran in the opposite
# order, so both the PDF's "IOS Setup Config" line and every scenario's
# TEM_THREAT/TEM_ERROR were silently built from hardcoded placeholder
# values (a fixed LMML/dry/CAVOK stub) regardless of what was actually
# configured in the Environment & IOS tab.
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
            <div style="font-family: 'Geist Mono', monospace; color: #0284C7; font-size: 13px; margin-top: 4px;">{live_metar_str}</div>
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

if df is not None:
    df["TEM_THREAT"], df["TEM_ERROR"] = zip(*df.apply(lambda r: derive_tem_tags(r["EVENT"], r["PHASES"], wind_spd, wind_gust, rcam_code, vis_rvr_str), axis=1))

with tab_session:
    # (Session Metadata & Device Setup, the Generate button, and the
    # session-generation logic now live at the top of this tab, in the
    # two-column dashboard — see the Session Summary / Competency
    # Coverage / Generate panels above.)

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
                # A swapped-in scenario has its own ATA chapter and
                # competency profile — refresh both from the master matrix
                # so the OB display, competency chips, and grading grid
                # match the event actually selected, not the one it
                # replaced.
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
        
        instructor_grades = {}
        instructor_notes = {}
        slot_competencies = {}
        
        for idx, row in final_df.iterrows():
            slot_num = int(row['SLOT'])
            event_title = row['EVENT']
            dod = int(row['DOD'])
            phase_num = int(row['PHASES'])
            role = row.get('ROLE', 'PF Focus')
            
            exercise_title, sequence_data, _ = get_exercise_for_event(event_title, row.get('ATA'))

            with st.expander(f"Slot #{slot_num:02d} — {row['PHASE_NAME']} | DOD {dod} | {event_title} ({role})", expanded=False):
                st.markdown(f"<div style='font-size:11px; opacity:0.65; margin-bottom:6px;'>OB profile: <b>{exercise_title}</b></div>", unsafe_allow_html=True)

                # Manual scenario swap: lets the instructor pick a different
                # event for this slot, constrained to the same Phase and DOD
                # so it stays compatible with the slot's sidebar configuration
                # and doesn't disturb the rest of the session's DOD balance.
                # This existed in an earlier iteration and was lost — the
                # underlying st.session_state.slot_overrides mechanism was
                # still being *read* elsewhere in the file, but nothing
                # ever *wrote* to it, so overrides could never actually
                # happen.
                swap_pool = df[(df["PHASES"] == phase_num) & (df["DOD"] == dod)]
                swap_options = sorted(swap_pool["EVENT"].unique().tolist())
                if event_title not in swap_options:
                    swap_options = [event_title] + swap_options
                current_idx = swap_options.index(event_title)
                swap_choice = st.selectbox(
                    f"🔁 Swap Event (Slot #{slot_num:02d}) — same Phase & DOD",
                    options=swap_options,
                    index=current_idx,
                    key=f"swap_event_{slot_num}",
                    help="Pick a different event if the auto-selected one doesn't fit well alongside the other slots — only events matching this slot's Phase and DOD are offered, so the session's DOD balance stays valid."
                )
                if swap_choice != event_title:
                    st.session_state.slot_overrides[slot_num] = {"EVENT": swap_choice, "DOD": dod}
                    st.rerun()

                st.markdown("<div style='font-size:11px; opacity:0.6; margin-bottom:6px;'>&#9201;&#65039; Phase sequence &amp; OB markers</div>", unsafe_allow_html=True)
                st.markdown(build_ob_flow_html(sequence_data), unsafe_allow_html=True)

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
                        format_func=lambda x: f"Grade {x} ({GRADE_LABELS[x]})",
                        key=f"grade_slot_{slot_num}"
                    )
                    grade_now_for_display = instructor_grades[slot_num]
                    st.markdown(f"<div style='font-size:11px; opacity:0.7; font-style:italic; margin-top:-6px;'>{GRADE_DESCRIPTORS[grade_now_for_display]}</div>", unsafe_allow_html=True)
                    if demonstrated:
                        with st.expander("📐 Official per-competency wording at this grade (OM-D §3.1.1.1)", expanded=False):
                            for code in demonstrated:
                                st.markdown(f"<div style='font-size:11px; margin-bottom:6px;'><b style='color:#0284C7;'>{code}</b> — {COMPETENCY_GRADE_TEXT.get(code, {}).get(grade_now_for_display, '')}</div>", unsafe_allow_html=True)
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

        # ==========================================
        # AUTO-SAVE TO HISTORY DATABASE
        # Saves automatically on every render of this block (i.e. whenever
        # grading changes) rather than requiring a separate button — but
        # upserts against the same DB session_id once one exists, so
        # repeated reruns update the record instead of multiplying rows.
        # A session with no staff number on either seat still gets
        # recorded (for later reference by sim/date), it just won't be
        # retrievable by candidate history — that requires the identity
        # key.
        # ==========================================
        slots_for_db = []
        for _, row in final_df.iterrows():
            s_num = int(row["SLOT"])
            grade = instructor_grades.get(s_num)
            demonstrated = slot_competencies.get(s_num, [])
            slots_for_db.append({
                "slot_number": s_num,
                "event_title": row["EVENT"],
                "phase_number": int(row["PHASES"]),
                "dod": int(row["DOD"]),
                "role_focus": row.get("ROLE", ""),
                "instructor_grade": grade,
                "instructor_notes": instructor_notes.get(s_num, ""),
                "competencies": [{"code": c, "grade": grade, "observed": True, "note": ""} for c in demonstrated],
            })
        saved_session_id, linked_candidate = save_session_to_history(
            st.session_state.get("db_session_id"), sim_id, session_mode,
            capt_staff_no, capt_name, fo_staff_no, fo_name,
            int(total_dod), int(max_dod_threshold), "session_setup", slots_for_db
        )
        st.session_state.db_session_id = saved_session_id
        if linked_candidate:
            st.caption(f"✓ Saved to history database (session #{saved_session_id}, linked to staff number).")
        else:
            st.caption(f"✓ Saved to history database (session #{saved_session_id}) — add a Captain/F.O. staff number above to make this retrievable by candidate history.")

with tab_orca:
    st.markdown("#### 📋 OPC & ORCA Workflow Suite (Uploaded Syllabus Analysis & Debrief)")
    st.markdown("Upload your operator simulator syllabus PDF to analyze structured syllabus exercises. Each Observable Behaviour below gets its own Observe → Record → Classify/Assess entry, tied to the same published 1-5 grading scale used elsewhere in the app — the exercise-level grade is derived from these, not picked separately.")

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
            select_all_ex = st.checkbox("Select All Uploaded Exercises", value=True, key="select_all_uploaded_ex")
            
        with col_sel_multi:
            default_selected = parsed_exercise_keys if select_all_ex else parsed_exercise_keys[:2]
            selected_ex_keys = st.multiselect(
                "Uploaded Syllabus Exercises to Evaluate:",
                options=parsed_exercise_keys,
                default=default_selected,
                format_func=lambda x: PROGRAM_SYLLABUS_EXERCISES[x]["title"],
                key="multiselect_uploaded_ex",
                label_visibility="collapsed"
            )

    if selected_ex_keys:
        total_obs_count = sum(
            len(step["obs"]) 
            for k in selected_ex_keys 
            for step in PROGRAM_SYLLABUS_EXERCISES[k]["sequence"]
        )

        # Real counts from the new Observe/Classify-Assess controls —
        # replaces the old tally of four generic ticks that captured
        # nothing about what was actually observed or graded.
        observed_count = 0
        all_ob_grades = []
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
        st.markdown(f"<div style='font-size:10.5px; opacity:0.6; margin-top:-4px;'>Average grade across observed OBs: {avg_ob_grade:.1f}/5. This reflects actual per-OB grading this session — not concordance (inter-rater reliability) between instructors, which EASA tracks separately via an Instructor Concordance Assurance Programme (ICAP) across multiple raters and reference scenarios.</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("##### 📌 Granular 4-Phase Uploaded Syllabus Exercise Breakdown & ORCA Workflow")

        uploaded_grades = {}
        uploaded_notes = {}
        uploaded_comp_mapping = {}

        for e_key in selected_ex_keys:
            ex_data = PROGRAM_SYLLABUS_EXERCISES[e_key]
            with st.container(border=True):
                st.markdown(f"#### ✈️ {ex_data['title']}")
                st.markdown(f"<div style='font-size: 13px; margin-bottom: 4px;'><b>Uploaded Syllabus Stressor / Failure:</b> {ex_data['stressor']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 13px; color: #0284C7; font-weight: 600; margin-bottom: 12px;'>🎯 CBTA Competency Targets: {', '.join(ex_data['cbta_focus'])}</div>", unsafe_allow_html=True)

                for s_idx, step in enumerate(ex_data["sequence"]):
                    st.markdown(f"<b style='color: #0284C7; font-size: 14px;'>{step['phase_name']}</b>", unsafe_allow_html=True)
                    st.markdown(f"<div style='margin-left: 10px; border-left: 3px solid #0284C7; padding-left: 12px; margin-bottom: 16px; margin-top: 4px;'>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 13px; opacity: 0.9; margin-bottom: 8px;'><b>Primary Target Action (PTA):</b> <i>{step['pta']}</i></div>", unsafe_allow_html=True)

                    st.markdown("<b style='font-size:12px; opacity:0.8;'>Observable Behaviors — Observe, Record, Classify &amp; Assess:</b>", unsafe_allow_html=True)
                    for ob_idx, ob in enumerate(step["obs"]):
                        comp_tag = ob.get("comp", extract_ob_competency(ob["text"]) or "GEN")
                        obs_key = f"orc_observed_{e_key}_{s_idx}_{ob_idx}"
                        grade_key = f"orc_grade_{e_key}_{s_idx}_{ob_idx}"
                        note_key = f"orc_note_{e_key}_{s_idx}_{ob_idx}"

                        # Text on its own full-width line, controls on a
                        # separate compact row below — a single 4-column
                        # row (checkbox + long OB text + grade + note) only
                        # fit on very wide screens; on anything narrower
                        # Streamlit stacks the columns and the layout breaks.
                        with st.container(border=True):
                            st.markdown(
                                f"<div style='font-size: 13px; margin-bottom:6px;'>{ob['text']} "
                                f"<span class='ref-badge'>{ob['ref']}</span> "
                                f"<span style='background:rgba(16,185,129,0.12); color:#10B981; border:1px solid rgba(16,185,129,0.3); padding:1px 5px; border-radius:4px; font-size:10px; font-weight:700;'>{comp_tag}</span></div>",
                                unsafe_allow_html=True
                            )
                            ob_cols = st.columns([1, 2, 3])
                            with ob_cols[0]:
                                observed = st.checkbox("Observed", key=obs_key, help="Observe: was this behaviour actually witnessed this run? Leave unticked if the item wasn't triggered/applicable — it won't count against grading.")
                            with ob_cols[1]:
                                ob_grade = st.selectbox(
                                    "Classify & assess", options=[5, 4, 3, 2, 1], index=2,
                                    format_func=lambda x: f"{x} ({GRADE_LABELS[x]})",
                                    key=grade_key, disabled=not observed, label_visibility="collapsed",
                                    help="Classify & assess: which band this specific behaviour fell into, using the same published 1-5 scale as the rest of the app."
                                )
                            with ob_cols[2]:
                                st.text_input("Record", value="", key=note_key, disabled=not observed, label_visibility="collapsed", placeholder="Record: note (optional)")
                    st.markdown("</div>", unsafe_allow_html=True)

                # The exercise-level grade is DERIVED from the per-OB
                # entries above — the controlling (lowest) grade among
                # observed OBs — rather than picked independently. This is
                # the actual fix for what was wrong before: the ORCA ticks
                # and the exercise grade were two unconnected data points.
                ex_ob_grades = []
                for s_idx, step in enumerate(ex_data["sequence"]):
                    for ob_idx in range(len(step["obs"])):
                        if st.session_state.get(f"orc_observed_{e_key}_{s_idx}_{ob_idx}"):
                            ex_ob_grades.append(st.session_state.get(f"orc_grade_{e_key}_{s_idx}_{ob_idx}", 3))

                up_g, up_n = st.columns([1, 2])
                with up_g:
                    if ex_ob_grades:
                        controlling_grade = min(ex_ob_grades)
                        uploaded_grades[e_key] = controlling_grade
                        st.markdown(f"<div style='font-size:13px;'><b>Controlling grade: {controlling_grade} ({GRADE_LABELS[controlling_grade]})</b></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:10.5px; opacity:0.7;'>Lowest grade among the {len(ex_ob_grades)}/{sum(len(s['obs']) for s in ex_data['sequence'])} OBs marked Observed.</div>", unsafe_allow_html=True)
                    else:
                        uploaded_grades[e_key] = 3
                        st.info("Mark at least one OB as Observed above to derive a grade.")
                with up_n:
                    up_phrase = st.selectbox(
                        f"Standardized Comment ({ex_data['title'][:25]}...)",
                        options=get_standard_phrase_options(uploaded_grades[e_key]),
                        key=f"up_phrase_{e_key}"
                    )
                    if up_phrase == "Custom (type below)":
                        uploaded_notes[e_key] = st.text_input(f"Custom Note ({ex_data['title'][:25]}...)", value="", key=f"up_note_{e_key}")
                    else:
                        up_extra = st.text_input(f"Optional detail ({ex_data['title'][:25]}...)", value="", key=f"up_note_extra_{e_key}")
                        uploaded_notes[e_key] = f"{up_phrase} {up_extra.strip()}" if up_extra.strip() else up_phrase
                uploaded_comp_mapping[e_key] = ex_data["cbta_focus"]

        # Persist so the main Session Debrief tab (which runs later in the
        # script) can fold this workflow's grades into the same
        # competency-coverage picture instead of only ever showing data
        # from the Session Setup / random-scenario workflow.
        st.session_state.uploaded_grades_data = {
            "grades": uploaded_grades, "comp_mapping": uploaded_comp_mapping
        }

        # Dedicated Debrief & Export for Uploaded Program Failures
        st.markdown("---")
        st.markdown("#### 📊 Uploaded Syllabus Session Debrief & Export Suite")
        
        up_recs = []
        for ek in selected_ex_keys:
            ed = PROGRAM_SYLLABUS_EXERCISES[ek]
            up_recs.append({
                "Module / Failure": ed["title"],
                "Stressor / Failure Type": ed["stressor"],
                "Grade": uploaded_grades.get(ek, 3),
                "Debrief Notes": uploaded_notes.get(ek, ""),
                "Competencies": ", ".join(uploaded_comp_mapping.get(ek, []))
            })
        df_uploaded_session = pd.DataFrame(up_recs)
        st.dataframe(df_uploaded_session, use_container_width=True, hide_index=True)

        col_up_csv, col_up_pdf = st.columns(2)
        with col_up_csv:
            csv_up_export = df_uploaded_session.to_csv(index=False)
            st.download_button(label="📥 Download Uploaded Syllabus Schedule (CSV)", data=csv_up_export, file_name="uploaded_syllabus_session_report.csv", mime="text/csv", use_container_width=True, key="dl_up_csv")
        with col_up_pdf:
            pdf_up_data = generate_pdf_briefing(
                pd.DataFrame([{
                    "SLOT": i+1,
                    "PHASE_NAME": f"Syllabus Ph {PROGRAM_SYLLABUS_EXERCISES[k]['phase']}",
                    "EVENT": PROGRAM_SYLLABUS_EXERCISES[k]["title"],
                    "DOD": 2,
                    "ROLE": "PF / PM"
                } for i, k in enumerate(selected_ex_keys)]),
                {i+1: uploaded_grades[k] for i, k in enumerate(selected_ex_keys)},
                {i+1: uploaded_notes[k] for i, k in enumerate(selected_ex_keys)},
                {i+1: uploaded_comp_mapping[k] for i, k in enumerate(selected_ex_keys)},
                len(selected_ex_keys) * 2, len(selected_ex_keys) * 3,
                "Syllabus Program Evaluation", capt_name, fo_name, sim_id, "Uploaded PDF Syllabus Review"
            )
            st.download_button(label="📄 Download Uploaded Syllabus EBT PDF Report", data=pdf_up_data, file_name="uploaded_syllabus_ebt_record.pdf", mime="application/pdf", use_container_width=True, key="dl_up_pdf")

        # Auto-save to history database — same pattern as the Session Setup
        # workflow, but with real per-OB grades/notes rather than one
        # grade per exercise repeated across its competencies.
        slots_for_db_up = []
        for i, k in enumerate(selected_ex_keys):
            ex_data = PROGRAM_SYLLABUS_EXERCISES[k]
            comp_entries = []
            for s_idx, step in enumerate(ex_data["sequence"]):
                for ob_idx, ob in enumerate(step["obs"]):
                    observed = st.session_state.get(f"orc_observed_{k}_{s_idx}_{ob_idx}", False)
                    if observed:
                        comp_entries.append({
                            "code": ob.get("comp", "GEN"),
                            "grade": st.session_state.get(f"orc_grade_{k}_{s_idx}_{ob_idx}", 3),
                            "observed": True,
                            "note": st.session_state.get(f"orc_note_{k}_{s_idx}_{ob_idx}", ""),
                        })
            slots_for_db_up.append({
                "slot_number": i + 1,
                "event_title": ex_data["title"],
                "phase_number": ex_data.get("phase"),
                "dod": None,
                "role_focus": "PF / PM",
                "instructor_grade": uploaded_grades.get(k),
                "instructor_notes": uploaded_notes.get(k, ""),
                "competencies": comp_entries,
            })
        saved_up_session_id, linked_up_candidate = save_session_to_history(
            st.session_state.get("db_session_id_uploaded"), sim_id, "Uploaded Syllabus Review",
            capt_staff_no, capt_name, fo_staff_no, fo_name,
            len(selected_ex_keys) * 2, len(selected_ex_keys) * 3, "uploaded_syllabus", slots_for_db_up
        )
        st.session_state.db_session_id_uploaded = saved_up_session_id
        if linked_up_candidate:
            st.caption(f"✓ Saved to history database (session #{saved_up_session_id}, linked to staff number).")
        else:
            st.caption(f"✓ Saved to history database (session #{saved_up_session_id}) — add a Captain/F.O. staff number in Session Setup to make this retrievable by candidate history.")

    else:
        st.info("Select at least one exercise from the uploaded program syllabus above to view the detailed OB & ORCA analysis and debrief suite.")

with tab_selector:
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
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=450)
    else:
        st.warning("Scenario database not loaded.")

with tab_debrief:
    st.markdown("#### 📊 Session Debrief — Competency Coverage & Standardized Summary")
    has_main_session = "final_df" in st.session_state
    has_uploaded_session = "uploaded_grades_data" in st.session_state

    if has_main_session or has_uploaded_session:
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
                    if c in comp_grades:
                        comp_grades[c].append(g)
            source_count += len(up_data["grades"])

        st.caption(f"Aggregating {source_count} graded item(s) across {'both the Session Setup and Uploaded Syllabus workflows' if has_main_session and has_uploaded_session else ('the Session Setup workflow' if has_main_session else 'the Uploaded Syllabus workflow')}.")

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
                f"<div class='status-badge-warn'>⚠️ Not graded this session: {', '.join(uncovered)}</div>"
                f"<div style='font-size:11.5px; opacity:0.75; margin-top:4px;'>ICAO Doc 9995 recommends EBT sessions build broad competency coverage over a training cycle — worth checking these are picked up in a future session.</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown("<div class='status-badge-ok'>✓ All 9 core competencies graded this session</div>", unsafe_allow_html=True)

        if has_main_session and len(final_df) >= 2:
            st.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
            st.markdown("<b>Slot Competency Overlap (Venn)</b>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:11.5px; opacity:0.7; margin-bottom:8px;'>A true Venn only works geometrically for 2-3 sets, so this compares a handful of slots at a time rather than the whole session — use it to spot whether two or three scenarios are exercising the same competencies (redundant) or genuinely different ones (complementary). For whole-session coverage across all 9 competencies, use the bar chart above instead.</div>", unsafe_allow_html=True)
            slot_options = {f"Slot {int(r['SLOT']):02d}: {r['EVENT']}": int(r['SLOT']) for _, r in final_df.iterrows()}
            venn_choice = st.multiselect(
                "Compare slots",
                options=list(slot_options.keys()),
                default=list(slot_options.keys())[:min(3, len(slot_options))],
                max_selections=3,
                key="venn_slot_choice"
            )
            if len(venn_choice) in (2, 3):
                sets_dict = {}
                for label in venn_choice:
                    s_num = slot_options[label]
                    demonstrated = set(st.session_state.get(f"comp_demo_{s_num}", []))
                    short_label = label.split(":")[0]
                    sets_dict[short_label] = demonstrated
                st.markdown(build_competency_venn_svg(sets_dict), unsafe_allow_html=True)
            else:
                st.info("Select exactly 2 or 3 slots above to compare.")
    else:
        st.info("Generate a session profile in the **Session Setup** workflow area to populate debrief analytics.")
