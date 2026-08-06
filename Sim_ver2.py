import streamlit as st
import pandas as pd
import io
import re
import os
import sys
import difflib

# ReportLab imports for PDF briefing generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# PAGE CONFIG & MODERN EXECUTIVE STYLING
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
        padding-top: 1.5rem !important;
        padding-bottom: 1.5rem !important;
        max-width: 96% !important;
    }
    .main {
        background-color: #F8FAFC;
    }
    h1 {
        color: #0F172A !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }
    h4 {
        color: #1E293B !important;
        font-weight: 600 !important;
        margin-top: 6px !important;
        margin-bottom: 6px !important;
    }
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0E2A47;
        color: #FFFFFF;
        min-width: 275px !important; 
        max-width: 275px !important;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown {
        color: #FFFFFF !important;
    }
    .slot-card {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 6px;
        padding: 6px 10px;
        margin-bottom: 6px;
    }
    .phase-badge {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
        font-size: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    /* Button enhancements */
    .stButton>button {
        background-color: #0E2A47;
        color: #FFFFFF;
        border-radius: 6px;
        font-weight: 600;
        border: none;
        padding: 0.45rem 0.9rem;
        transition: all 0.15s ease;
    }
    .stButton>button:hover {
        background-color: #1E3A8A;
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
st.title("✈️ Simulator Session Plan & EBT Competency Builder")
st.markdown("<p style='color: #64748B; font-size: 14px; margin-top: -8px; font-weight: 500;'>Advanced Flight Training & Evidence-Based Training (EBT) Scenario Optimizer</p>", unsafe_allow_html=True)

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

# Reference Guide
with st.expander("📖 Reference Guide: 8 EBT Flight Phases", expanded=False):
    st.markdown("<div class='phase-badge'>", unsafe_allow_html=True)
    p_cols = st.columns(4)
    for idx, (p_num, p_desc) in enumerate(PHASE_NAMES.items()):
        with p_cols[idx % 4]:
            st.markdown(f"**{p_desc}**")
    st.markdown("</div>", unsafe_allow_html=True)

# Global Session Controls
with st.container(border=True):
    p_col1, p_col2 = st.columns([1.5, 3.5])
    with p_col1:
        max_dod_threshold = st.number_input("Total DOD Ceiling", min_value=1, max_value=30, value=6, step=1)
    with p_col2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        allow_fallback = st.checkbox("Enable Smart Fallback (use closest available DOD if exact match missing)", value=True)

# ==========================================
# SIDEBAR: SLOTS CONFIGURATION
# ==========================================
st.sidebar.markdown("<h3 style='margin-top: 0px; margin-bottom: 5px;'>📍 Slots Config</h3>", unsafe_allow_html=True)

if "slot_list" not in st.session_state:
    st.session_state.slot_list = [
        {"phase": 1, "dod": 1, "type": "Any", "mandatory": False},
        {"phase": 2, "dod": 2, "type": "Any", "mandatory": False},
        {"phase": 6, "dod": 2, "type": "Any", "mandatory": False},
        {"phase": 7, "dod": 1, "type": "Any", "mandatory": False}
    ]

c_b1, c_b2 = st.sidebar.columns(2)
if c_b1.button("➕ Add Slot"):
    if len(st.session_state.slot_list) < 12:
        st.session_state.slot_list.append({"phase": 1, "dod": 1, "type": "Any", "mandatory": False})
        st.rerun()

if c_b2.button("❌ Rm Slot"):
    if len(st.session_state.slot_list) > 1:
        st.session_state.slot_list.pop()
        st.rerun()

st.sidebar.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)

slot_configurations = []

for i, slot_data in enumerate(st.session_state.slot_list):
    st.sidebar.markdown(f"<div class='slot-card'><b style='font-size:11px; color:#94A3B8;'>SLOT #{i+1}</b>", unsafe_allow_html=True)
    sc1, sc2 = st.sidebar.columns([3, 2])
    with sc1:
        p_val = st.selectbox(
            f"P{i}",
            options=ALL_PHASE_KEYS,
            index=ALL_PHASE_KEYS.index(slot_data["phase"]) if slot_data["phase"] in ALL_PHASE_KEYS else 0,
            format_func=lambda x: f"Ph {x}",
            key=f"phase_sel_{i}",
            label_visibility="collapsed"
        )
    with sc2:
        d_val = st.selectbox(
            f"D{i}",
            options=[1, 2, 3],
            index=[1, 2, 3].index(slot_data["dod"]),
            key=f"dod_sel_{i}",
            label_visibility="collapsed"
        )
    
    with st.sidebar.expander(f"⚙️ Details #{i+1}", expanded=False):
        type_val = st.selectbox(
            "Category",
            options=["Any", "Technical Failure", "Non-Technical / CRM", "ATA Specific"],
            index=["Any", "Technical Failure", "Non-Technical / CRM", "ATA Specific"].index(slot_data.get("type", "Any")),
            key=f"type_sel_{i}"
        )
        ata_val = None
        if type_val == "ATA Specific":
            ata_val = st.number_input("ATA", min_value=11, max_value=80, value=22, key=f"ata_sel_{i}")
        is_mandatory = st.checkbox("Pin Mandatory", value=slot_data.get("mandatory", False), key=f"mand_sel_{i}")

    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    st.session_state.slot_list[i] = {
        "phase": p_val,
        "dod": d_val,
        "type": type_val,
        "ata": ata_val,
        "mandatory": is_mandatory
    }
    
    slot_configurations.append({
        "slot": i + 1,
        "phase": p_val,
        "dod": d_val,
        "type": type_val,
        "ata": ata_val,
        "mandatory": is_mandatory
    })

configured_total_dod = sum(item["dod"] for item in slot_configurations)
if configured_total_dod > max_dod_threshold:
    st.sidebar.warning(f"⚠️ Target DOD ({configured_total_dod}) > Ceiling ({max_dod_threshold})")
else:
    st.sidebar.success(f"✓ Target DOD: {configured_total_dod} / {max_dod_threshold}")

st.sidebar.markdown("<div class='thin-divider'></div>", unsafe_allow_html=True)
st.sidebar.markdown("<div style='text-align: center; font-size: 11px; color: #94A3B8;'>Designed by Shawn Abela Ver v2.3 2026</div>", unsafe_allow_html=True)

# ==========================================
# OPTIMIZED DATA LOADING & CACHING
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_best_match(scen_title, comp_titles):
    if not scen_title or pd.isna(scen_title): return None
    s_clean = re.sub(r'\(Ref:[^)]+\)', '', str(scen_title), flags=re.IGNORECASE)
    s_clean = re.sub(r'[^A-Z0-9\s]', ' ', s_clean.upper())
    s_clean = re.sub(r'\s+', ' ', s_clean).strip()
    
    if scen_title in comp_titles: return scen_title
    
    comp_map = {re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9\s]', ' ', str(c).upper())).strip(): c for c in comp_titles}
    if s_clean in comp_map:
        return comp_map[s_clean]
        
    s_words = set(s_clean.split())
    for c_clean, orig in comp_map.items():
        if len(s_words) > 1 and s_words.issubset(set(c_clean.split())):
            return orig

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

        while len(df_raw.columns) < 10:
            df_raw[f"Col_{len(df_raw.columns)}"] = None

        records = []
        phase_col_indices = list(range(2, 10))  # Columns C through J -> Phases 1 through 8
        
        for idx, row in df_raw.iterrows():
            event = row.iloc[0]
            dod = row.iloc[1]
            ata = row['ATA'] if 'ATA' in row and pd.notna(row['ATA']) else None
            
            if pd.isna(event) or pd.isna(dod):
                continue
            event_str = str(event).strip()
            if len(event_str) == 1 and event_str.isalpha():
                continue
            
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
                                    except (ValueError, TypeError):
                                        pass
                    comp_loaded = True
            except Exception:
                pass

        df["scenario_id"] = [f"SC-{i+1:02d}" for i in range(len(df))]
        return df, comp_loaded
    except Exception as e:
        return None, str(e)

def generate_pdf_briefing(df_session, total_dod, max_dod, comp_scores):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=13, leading=15, textColor=colors.HexColor('#0E2A47'), alignment=0)
    subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#555555'))
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=7.5, leading=9.5)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontSize=7.5, leading=9.5, fontName='Helvetica-Bold')

    elements = [
        Paragraph("FLIGHT SIMULATOR SESSION BRIEFING & EBT PROFILE", title_style),
        Paragraph(f"Generated Session Schedule | Total DOD: <b>{total_dod} / {max_dod}</b> &nbsp;&nbsp;|&nbsp;&nbsp; <i>Designed by Shawn Abela for KMMA 2026</i>", subtitle_style),
        Spacer(1, 3),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0E2A47'), spaceAfter=6)
    ]

    table_data = [[
        Paragraph("<b>Slot</b>", cell_bold), Paragraph("<b>Phase</b>", cell_bold),
        Paragraph("<b>Event / Scenario Title</b>", cell_bold), Paragraph("<b>DOD</b>", cell_bold),
        Paragraph("<b>Competencies Flagged</b>", cell_bold)
    ]]

    for _, row in df_session.iterrows():
        active_comps = [col for col in COMPETENCY_KEYS.keys() if col in row and pd.notna(row[col]) and float(row[col]) >= 1.0]
        comps_str = ", ".join(active_comps) if active_comps else "Standard"
        table_data.append([
            Paragraph(str(row["SLOT"]), cell_style), Paragraph(str(row["PHASE_NAME"]), cell_style),
            Paragraph(str(row["EVENT"]), cell_style), Paragraph(str(row["DOD"]), cell_style),
            Paragraph(comps_str, cell_style)
        ])

    t = Table(table_data, colWidths=[25, 110, 240, 28, 161])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F4F8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0E2A47')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5), ('TOPPADDING', (0, 0), (-1, -1), 2.5),
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
        st.success(f"✓ Matrix Loaded. {'(Keypams Competency Matrix Active)' if comp_loaded else ''}")

        # Sorted Internal Matrix View
        with st.expander("📋 View Parsed Internal Scenario Matrix (Sorted by Phase)", expanded=False):
            active_comp_cols = [k for k in COMPETENCY_KEYS.keys() if k in df.columns]
            disp_cols = ["scenario_id", "PHASES", "DOD", "EVENT"] + active_comp_cols
            
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

            for cfg in slot_configurations:
                slot_num = cfg["slot"]
                target_p = cfg["phase"]
                target_d = cfg["dod"]
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

                if not candidates.empty:
                    picked = candidates.sample(n=1).iloc[0].to_dict()
                    picked["SLOT"] = slot_num
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
                
                ft_col1, ft_col2 = st.columns([1, 1.8])
                with ft_col1:
                    override_slot_idx = st.selectbox(
                        "Select Slot to Modify:",
                        options=range(len(final_df)),
                        format_func=lambda i: f"Slot #{final_df.loc[i, 'SLOT']} – Phase {final_df.loc[i, 'PHASES']} | {final_df.loc[i, 'EVENT'][:22]}..."
                    )
                
                curr_row = final_df.loc[override_slot_idx]
                slot_num_to_modify = int(curr_row["SLOT"])
                curr_phase = int(curr_row["PHASES"])

                phase_filtered_df = df[df["PHASES"] == curr_phase].drop_duplicates(subset=["EVENT"]).reset_index(drop=True)

                with ft_col2:
                    if phase_filtered_df.empty:
                        st.warning(f"⚠️ No scenarios found for Phase {curr_phase}.")
                    else:
                        new_event_title = st.selectbox(
                            f"Choose Replacement Event (Phase {curr_phase}):",
                            options=phase_filtered_df["EVENT"].tolist(),
                            format_func=lambda ev_title: f"[DOD {phase_filtered_df[phase_filtered_df['EVENT'] == ev_title].iloc[0]['DOD']}] {ev_title}"
                        )
                
                if not phase_filtered_df.empty:
                    if st.button("🔄 Apply Event Override to Slot", type="primary"):
                        match_row = phase_filtered_df[phase_filtered_df["EVENT"] == new_event_title].iloc[0].to_dict()

                        final_df.loc[override_slot_idx, "EVENT"] = match_row["EVENT"]
                        final_df.loc[override_slot_idx, "DOD"] = match_row["DOD"]
                        final_df.loc[override_slot_idx, "PHASES"] = match_row["PHASES"]
                        final_df.loc[override_slot_idx, "PHASE_NAME"] = PHASE_NAMES[curr_phase]
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
                final_df[["SLOT", "EVENT", "DOD", "PHASES", "PHASE_NAME", "DURATION", "MATCH_TYPE"]],
                use_container_width=True
            )

            col_exp1, col_exp2 = st.columns(2)
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
                pdf_data = generate_pdf_briefing(final_df, total_dod, max_dod_threshold, comp_scores)
                st.download_button(
                    label="📄 Download Printable PDF Briefing Sheet",
                    data=pdf_data,
                    file_name=f"sim_briefing_DOD_{max_dod_threshold}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
