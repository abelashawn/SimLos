App Overview: Advanced Evidence-Based Training (EBT), Competency-Based Training and Assessment (CBTA), OPC, and LPC IRR training suite designed specifically for KM Malta Airlines Airbus A320 STD2.2 operations.

Core Architecture: Built as a high-performance multi-tab Streamlit application integrating interactive flight deck parameters, automated syllabus text extraction via pypdf, structured Observable Behavior (OB) checklists, and dynamic ReportLab PDF generation.

Tab 1: Session Setup (⚙️ Session Setup)

Configures session metadata including Training Mode, Captain/First Officer names, and Sim/Device ID.

Defines Total Degree of Difficulty (DOD) ceilings and fallback preferences.

Houses the core ⚡ Generate Simulator Profile engine to sequence independent or randomly generated slot scenarios.

Provides interactive scoring rubrics, grade selectors (1-5), and standardized comment bank options per slot.

Includes instant CSV schedule downloads and PDF briefing record generation.

Tab 2: Environment & IOS (🌐 Environment & IOS)

Manages aircraft Mass & Balance parameters (GW, CG, ZFW, Fuel, Initial Altitude, and QNH).

Provides a Major European Aerodrome selection menu (LMML, LFPG, EGLL, EDDF, EHAM) with integrated Jeppesen schematic layout and briefing details.

Features live METAR feed integration via Aviation Weather APIs alongside customizable surface wind, atmospheric temperature, ISA deviation, runway surface condition (RCAM), precipitation, and visibility parameters.

Tab 3: OPC & ORCA Workflow (📋 OPC & ORCA Workflow)

Provides operator simulator syllabus PDF uploading and automated text parsing.

Extracts distinct exercises to generate complete 4-phase EASA Observable Behaviors (OBs), primary target actions, and interactive ORCA (Observation, Recording, Classification, Assessment) checklists.

Includes real-time metrics tracking selected modules, target OBs, ORCA completion percentage, and Inter-Rater Reliability (IRR) concordance indexes.

Features a dedicated debriefing suite and export functions specifically for uploaded syllabus program failures.

Tab 4: Scenario Selector (🎯 Scenario Selector)

Houses the full scenario matrix database loader (Scenarios.csv & Keypams.xlsx).

Provides multi-parameter filtering by Flight Phase, DOD level, and core EASA Competencies before session generation.

Tab 5: Session Debrief (📊 Session Debrief)

Aggregates session-wide competency coverage metrics and demonstration counts.

Visualizes average instructor grades per core competency via dynamic charts and summary tables.

Sidebar Controls (📍 Slot Configuration & References)

Dynamic slot adder/remover supporting up to 12 sequenced training slots.

Per-slot customization of flight phases, DOD levels, CRM crew roles, failure categories, ATA chapters, targeted competencies, and mandatory pin exercises.

Integrated document reference index tracking EASA ED Decision 2021/002/R, FCOM, FCTM, QRH, ICAO Doc 9995, and airline operations manuals.

Future Expansion Roadmap

Feature Slot 1: Advanced telemetry data logging integration from FSTD data exports.

Feature Slot 2: Multi-crew longitudinal historical performance tracking analytics.

Feature Slot 3: Custom airline-specific electronic grading rubric configuration panels.
