"""
🎓 Fakibaaz — Gamified Focus & Study Tracker
---------------------------------------------
Point Scoring & Tier Engine:
1. Task Score: Base 10 pts + (Time Saved / Assigned * 10) early bonus OR - (Late / Assigned * 10) deduction.
2. Tier System: Total Score determines Tier (Bronze, Silver, Gold, Platinum, Diamond, Master, Grandmaster).
3. Ranking & Profile System: Complete Task -> Score -> Tier -> Ranking.

Run with:
    .venv/bin/streamlit run study_planner_app.py
"""

import time
import threading
import base64
import html
from pathlib import Path
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import gspread
from google.oauth2.service_account import Credentials

# --------------------------------------------------------------------------------------
# CONFIG & CONSTANTS
# --------------------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "study_data.csv"  # kept only as a local fallback name; primary storage is now Google Sheets
LOGO_PATH = APP_DIR / "logo.jpg"
SHEET_TAB_NAME = "StudyData"
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@st.cache_data(show_spinner=False)
def _logo_base64(path: str) -> str:
    """Read the logo once and cache it as a base64 data URI so it can be
    dropped inline into a single flex HTML block. Using st.image() for the
    header/sidebar logo leaves large built-in top/bottom margins around the
    image element that can't be trimmed with CSS alone — inlining it removes
    that dead space."""
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

DEFAULT_SUBJECTS = [
    "ACHEM - 4121",
    "AGEXT - 4121",
    "ENTOM - 4121",
    "PPATH - 4121",
    "HORT - 4121",
    "CBOT - 4121",
]

COLUMNS = [
    "UserID", "Date", "Subject", "Topic",
    "Assigned Min", "Actual Min",
    "Score", "Rank", "XP", "Timestamp"
]

st.set_page_config(page_title="Fakibaaz · Focus Tracker", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

# --------------------------------------------------------------------------------------
# STYLE — Pure White Background, Vibrant Gradient Buttons & Custom Badges
# --------------------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800;900&display=swap');

:root {
  --bg-app: #ffffff;
  --bg-card: #ffffff;
  --text-main: #1e293b;
  --text-muted: #64748b;
  --border-card: #e2e8f0;
}

.fakibaaz-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 6px 0 4px 0;
}

@media (max-width: 640px) {
  .fakibaaz-header {
    justify-content: center;
  }
}

.fakibaaz-header img {
  height: 46px;
  width: auto;
  display: block;
}

.fakibaaz-brand {
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 28px;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
  padding: 0;
  line-height: 1.1;
}

.brand-divider {
  border: none;
  height: 2px;
  background: linear-gradient(90deg, #6366f1 0%, #06b6d4 50%, #e2e8f0 100%);
  margin: 0 0 14px 0;
  border-radius: 999px;
  opacity: 0.85;
}

/* ID gate (Student ID entry screen) — left-aligned like everything else on
   desktop, but centered on mobile so the logo/heading/input/button all sit
   stacked in the middle of a narrow screen instead of hugging the left edge. */
@media (max-width: 640px) {
  .id-gate-header {
    justify-content: center;
  }
  .id-gate-block {
    text-align: center;
  }
  .id-gate-block [data-testid="stTextInput"],
  .id-gate-block [data-testid="stButton"],
  .id-gate-block [data-testid="stCaptionContainer"] {
    display: flex;
    justify-content: center;
    text-align: center;
  }
  .id-gate-block [data-testid="stTextInput"] > div,
  .id-gate-block [data-testid="stButton"] > button {
    margin: 0 auto;
  }
}

/* Topic header + stats + timer block: left/right split on desktop, but
   everything centered on mobile once the columns stack. */
@media (max-width: 640px) {
  .st-key-session_head [data-testid="stHorizontalBlock"] {
    text-align: center;
  }
  .st-key-session_head [data-testid="stMarkdownContainer"] h3 {
    text-align: center;
  }
  .st-key-session_head .session-stats-block {
    text-align: center !important;
  }
  .st-key-session_head [data-testid="stCaptionContainer"] {
    text-align: center;
    justify-content: center;
  }
}

/* Time elapsed caption under the timer: keep centered on all screen sizes,
   not just mobile. */
.st-key-session_head [data-testid="stCaptionContainer"] {
  text-align: center;
  justify-content: center;
  display: flex;
}

/* Sidebar brand — logo + wordmark inline, no extra vertical gap */
.sidebar-brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 10px 0;
}

.sidebar-brand-row img {
  height: 44px;
  width: auto;
  display: block;
  border-radius: 8px;
}

.sidebar-brand-row .sb-text {
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 19px;
  line-height: 1.15;
  color: #1e293b;
}

.sidebar-brand-row .sb-text span {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.3px;
}

.block-container {
  padding-top: 1.5rem !important;
}

html, body, [class*="css"], [class*="st-"], .stApp, .stApp * {
  font-family: 'Poppins', sans-serif !important;
}

/* Exclude Streamlit's ligature-based icon font (used for the sidebar
   collapse/expand arrows and other built-in icons) from the Poppins
   override above — otherwise the icon ligature text (e.g.
   "keyboard_double_arrow_right") renders as literal text instead of
   the actual glyph. */
[data-testid="stIconMaterial"],
span[class*="material-icons"],
span[class*="material-symbols"] {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

html, body {
  font-size: 15px;
}

.stApp {
  background-color: #ffffff !important;
  background-image: radial-gradient(at 10% 10%, rgba(99, 102, 241, 0.03) 0px, transparent 50%),
                    radial-gradient(at 90% 90%, rgba(16, 185, 129, 0.03) 0px, transparent 50%);
  color: #1e293b;
  font-family: 'Poppins', sans-serif;
}

[data-testid="stSidebar"] {
  background-color: #f8fafc !important;
  border-right: 1px solid #e2e8f0 !important;
}

.timer-container { 
  text-align: center; 
  padding: 16px 0; 
}

.timer-display {
  font-size: 64px; 
  font-weight: 600;
  font-family: 'Poppins', sans-serif;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #4f46e5 0%, #06b6d4 25%, #4f46e5 50%, #06b6d4 75%, #4f46e5 100%);
  background-size: 300% 100%;
  -webkit-background-clip: text; 
  -webkit-text-fill-color: transparent;
  margin: 0; 
  line-height: 1.1;
  filter: drop-shadow(0 4px 12px rgba(79, 70, 229, 0.15));
}

.timer-display.timer-running {
  animation: timerFlow 4s linear infinite;
}

@keyframes timerFlow {
  0% { background-position: 0% 50%; }
  100% { background-position: 300% 50%; }
}

.timer-overtime {
  font-size: 64px; 
  font-weight: 600;
  font-family: 'Poppins', sans-serif;
  background: linear-gradient(90deg, #ef4444 0%, #f97316 25%, #ef4444 50%, #f97316 75%, #ef4444 100%);
  background-size: 300% 100%;
  -webkit-background-clip: text; 
  -webkit-text-fill-color: transparent;
  margin: 0; 
  line-height: 1.1;
  animation: timerFlow 4s linear infinite;
}

/* Tier Badges */
.badge { 
  display: inline-flex; 
  align-items: center; 
  gap: 6px; 
  padding: 6px 18px; 
  border-radius: 999px; 
  font-weight: 700; 
  font-size: 13px; 
}
.badge-gm { background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%); color: #c2410c; border: 1px solid #fdba74; }
.badge-master { background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%); color: #6b21a8; border: 1px solid #d8b4fe; }
.badge-diamond { background: linear-gradient(135deg, #ecfeff 0%, #cffaff 100%); color: #0e7490; border: 1px solid #67e8f9; }
.badge-plat { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); color: #15803d; border: 1px solid #86efac; }
.badge-gold { background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); color: #b45309; border: 1px solid #fde68a; }
.badge-silver { background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); color: #334155; border: 1px solid #cbd5e1; }
.badge-bronze { background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); color: #991b1b; border: 1px solid #fca5a5; }

/* Gradient Buttons */
.stButton>button {
  border-radius: 12px; 
  font-weight: 700; 
  font-size: 14px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  color: #334155; 
  border: 1px solid #cbd5e1;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.stButton>button:hover {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-color: #94a3b8; 
  color: #0f172a;
  transform: translateY(-2px); 
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.stButton>button[kind="primary"] {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #ffffff; 
  border: none;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.35);
}
.stButton>button[kind="primary"]:hover {
  background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
  transform: translateY(-2px);
}

/* Session Breakdown task cards — flex-wrap lets each label:value pair reflow
   onto its own line on narrow/mobile screens instead of being squeezed into
   fixed-width table columns. */
.task-card {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
  padding: 12px 16px;
  margin-bottom: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
}

.task-field {
  display: flex;
  flex-direction: column;
  min-width: 78px;
  flex: 1 1 78px;
}

.tf-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.tf-value {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  word-break: break-word;
}

@media (max-width: 640px) {
  .task-card {
    padding: 10px 12px;
    gap: 6px 14px;
  }
  .task-field {
    min-width: 100px;
    flex: 1 1 42%;
  }
}

/* Delete button next to each task card: vertically centered against the
   card on desktop; auto/compact on mobile where it sits stacked below
   the card instead. */
.st-key-task_rows [data-testid="stHorizontalBlock"] {
  align-items: center;
}
@media (max-width: 640px) {
  .st-key-task_rows [data-testid="stHorizontalBlock"] {
    align-items: flex-start;
  }
}

.footer-card {
  margin: 14px 0 8px;
  padding: 18px 22px;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.06);
}
.tier-range-line {
  text-align: center;
  font-weight: 400;
  font-size: 14px;
  color: #334155;
  line-height: 1.8;
  margin: 14px 0;
}
.tier-footer-divider {
  border: none;
  height: 1px;
  background: #e2e8f0;
  margin: 14px 0;
}
.tier-range-line strong {
  font-weight: 600;
}
.footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: #475569;
}
.footer-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.footer-brand img {
  height: 38px;
  width: auto;
  display: block;
  border-radius: 8px;
}
.footer-brand .footer-brand-text {
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 22px;
  line-height: 1.1;
  background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.footer-meta {
  text-align: right;
  font-size: 13px;
  line-height: 1.7;
}
.footer-meta a {
  color: #4f46e5;
  font-weight: 700;
  text-decoration: none;
}
.footer-stack, .footer-copy {
  color: #64748b;
}
@media (max-width: 640px) {
  .footer-bar {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  .footer-meta {
    text-align: center;
  }
}

</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------------------
# DATA PERSISTENCE — Google Sheets backend, scoped by Student ID
# --------------------------------------------------------------------------------------
# Every row is tagged with the "UserID" the student typed in the sidebar. Whichever
# device (laptop, phone, a different browser) enters the same ID sees the same rows,
# and data survives Streamlit app restarts/redeploys because it lives in the Sheet,
# not on the app's disk.

@st.cache_resource(show_spinner=False)
def _get_worksheet():
    """Returns the gspread Worksheet if Google Sheets credentials are configured and valid,
    or None if credentials are missing or connection fails (triggering CSV fallback)."""
    if "gcp_service_account" not in st.secrets or "sheet_id" not in st.secrets:
        return None
    try:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=SHEETS_SCOPES
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(st.secrets["sheet_id"])
        try:
            ws = sh.worksheet(SHEET_TAB_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=2000, cols=len(COLUMNS) + 2)
            ws.append_row(COLUMNS)
        return ws
    except Exception:
        return None

@st.cache_data(ttl=2, show_spinner=False)
def load_data(user_id: str) -> pd.DataFrame:
    """Load this user's rows from the fast local cache.

    Google Sheets is still used for background backup on save, but the live UI
    reads locally so timer ticks and Finish clicks never wait on network calls.
    If no local cache exists yet, we import from Sheets once.
    """
    df = pd.DataFrame(columns=COLUMNS)
    if DATA_FILE.exists():
        try:
            df = pd.read_csv(DATA_FILE)
        except Exception:
            df = pd.DataFrame(columns=COLUMNS)
    else:
        ws = _get_worksheet()
        if ws is not None:
            try:
                df = pd.DataFrame(ws.get_all_records())
                if not df.empty:
                    for col in COLUMNS:
                        if col not in df.columns:
                            df[col] = ""
                    df[COLUMNS].to_csv(DATA_FILE, index=False)
            except Exception:
                df = pd.DataFrame(columns=COLUMNS)

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    df = df.drop_duplicates(subset=["UserID", "Timestamp"], keep="last")
    df = df[df["UserID"].astype(str) == str(user_id)].reset_index(drop=True)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        numeric_cols = ["Assigned Min", "Actual Min", "Score", "XP"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df[COLUMNS]

def _append_local_row(row: dict):
    df_row = pd.DataFrame([[row.get(c, "") for c in COLUMNS]], columns=COLUMNS)
    if DATA_FILE.exists():
        df_row.to_csv(DATA_FILE, mode="a", header=False, index=False)
    else:
        df_row.to_csv(DATA_FILE, index=False)

def _append_cloud_row(row: dict, creds_info: dict, sheet_id: str):
    try:
        creds = Credentials.from_service_account_info(creds_info, scopes=SHEETS_SCOPES)
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        try:
            ws = sh.worksheet(SHEET_TAB_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=2000, cols=len(COLUMNS) + 2)
            ws.append_row(COLUMNS)
        ws.append_row([str(row.get(c, "")) for c in COLUMNS], value_input_option="USER_ENTERED")
    except Exception:
        pass

def save_row(row: dict, user_id: str) -> bool:
    row = dict(row)
    row["UserID"] = user_id
    if isinstance(row.get("Date"), (pd.Timestamp, date, datetime)):
        row["Date"] = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d")

    try:
        _append_local_row(row)
    except Exception as e:
        st.error(f"Failed to save locally: {e}")
        return False

    load_data.clear()

    if "gcp_service_account" in st.secrets and "sheet_id" in st.secrets:
        creds_info = dict(st.secrets["gcp_service_account"])
        sheet_id = str(st.secrets["sheet_id"])
        thread = threading.Thread(
            target=_append_cloud_row,
            args=(row.copy(), creds_info, sheet_id),
            daemon=True,
        )
        thread.start()
    return True

def delete_row(user_id: str, row_data: dict) -> bool:
    """Delete a specific row matching UserID and Timestamp (or exact attributes).

    The UI (load_data) reads from the local CSV cache whenever it exists, so a
    delete MUST remove the row from that local file — deleting only from the
    Google Sheet left the stale row in the local cache and the "deleted" task
    kept reappearing. We always update the local CSV (the source of truth for
    what's displayed) and additionally mirror the deletion to Sheets when
    configured, best-effort.
    """
    target_ts = str(row_data.get("Timestamp", ""))
    target_sub = str(row_data.get("Subject", ""))
    target_top = str(row_data.get("Topic", ""))

    deleted_local = False
    if DATA_FILE.exists():
        try:
            df = pd.read_csv(DATA_FILE)
            if not df.empty:
                if target_ts and "Timestamp" in df.columns:
                    mask = (df["UserID"].astype(str) == str(user_id)) & (df["Timestamp"].astype(str) == target_ts)
                else:
                    mask = (df["UserID"].astype(str) == str(user_id)) & \
                           (df["Subject"].astype(str) == target_sub) & \
                           (df["Topic"].astype(str) == target_top)

                df_to_keep = df[~mask]
                if len(df_to_keep) < len(df):
                    df_to_keep.to_csv(DATA_FILE, index=False)
                    deleted_local = True
        except Exception as e:
            st.error(f"Error deleting from local cache: {e}")

    deleted_cloud = False
    ws = _get_worksheet()
    if ws is not None:
        try:
            all_values = ws.get_all_values()
            if all_values:
                header = all_values[0]
                if "UserID" in header:
                    user_col = header.index("UserID")
                    ts_col = header.index("Timestamp") if "Timestamp" in header else -1

                    for i, r in enumerate(all_values[1:], start=2):
                        if len(r) > user_col and r[user_col] == str(user_id):
                            match = False
                            if ts_col != -1 and len(r) > ts_col and target_ts:
                                match = (r[ts_col] == target_ts)
                            else:
                                match = (len(r) > 3 and r[2] == target_sub and r[3] == target_top)
                            if match:
                                ws.delete_rows(i)
                                deleted_cloud = True
                                break
        except Exception as e:
            st.error(f"Error deleting from Google Sheets: {e}")

    if deleted_local or deleted_cloud:
        load_data.clear()
        return True
    return False

def export_to_excel(user_id: str, path="Study_Planner_Log.xlsx"):
    df = load_data(user_id)
    if df.empty:
        return None
    export = df.rename(columns={
        "Subject": "Course", "Assigned Min": "Assigned Time", "Actual Min": "Time Taken"
    })
    cols_to_export = [c for c in ["Date", "Course", "Topic", "Assigned Time", "Time Taken", "Score", "Rank"] if c in export.columns]
    export[cols_to_export].to_excel(APP_DIR / path, index=False)
    return str(APP_DIR / path)

def get_export_csv(user_id: str) -> str:
    df = load_data(user_id)
    if df.empty:
        return ""
    export = df.rename(columns={
        "Subject": "Course", "Assigned Min": "Assigned Time", "Actual Min": "Time Taken"
    })
    cols_to_export = [c for c in ["Date", "Course", "Topic", "Assigned Time", "Time Taken", "Score", "Rank"] if c in export.columns]
    return export[cols_to_export].to_csv(index=False)

# --------------------------------------------------------------------------------------
# POINT SCORING, TIER & RANKING SYSTEM
# --------------------------------------------------------------------------------------
def _raw_task_score(assigned_min: float, actual_min: float) -> float:
    """
    🎯 1. Task Score (shared by the live preview and the final saved score):
    - Every task starts with 10 points.
    - Finish early  -> Bonus = (Time Saved / Assigned Time) * 10 ; Score = 10 + Bonus
    - Finish on time -> Score = 10
    - Finish late   -> Deduction = (Late Time / Assigned Time) * 10 ; Score = 10 - Deduction

    Example: a 20-min task finished in 13 min -> time saved 7 -> bonus (7/20)*10 = 3.5
    -> Score = 13.5.

    A small tolerance is used for the "on time" case since actual_min is a
    rounded float (elapsed seconds / 60) and will almost never equal an
    integer assigned_min exactly.
    """
    diff = actual_min - assigned_min
    if abs(diff) < 0.01:
        score = 10.0
    elif diff < 0:
        time_saved = assigned_min - actual_min
        bonus = (time_saved / max(assigned_min, 0.1)) * 10.0
        score = 10.0 + bonus
    else:
        late_time = actual_min - assigned_min
        deduction = (late_time / max(assigned_min, 0.1)) * 10.0
        score = 10.0 - deduction

    return max(0.0, round(score, 1))

def compute_task_score(assigned_min: float, actual_min: float) -> float:
    """
    🎯 1. Task Score upon completion (see _raw_task_score for the formula).
    Minimum 0.5 mins (30s) focus required to earn any score — returns 0.0
    for instant click / exploit attempts.
    """
    if actual_min < 0.5:
        return 0.0
    return _raw_task_score(assigned_min, actual_min)

def compute_tier(total_score: float):
    """
    🏆 4. Tier System (Total Score determines Tier):
    - 🪨 Bronze: 0–99
    - 🥈 Silver: 100–249
    - 🥇 Gold: 250–499
    - 💎 Platinum: 500–999
    - 💠 Diamond: 1,000–1,999
    - 👑 Master: 2,000–3,999
    - 🔥 Grandmaster: 4,000+
    """
    if total_score >= 4000: return "🔥 Grandmaster", "badge-gm"
    if total_score >= 2000: return "👑 Master", "badge-master"
    if total_score >= 1000: return "💠 Diamond", "badge-diamond"
    if total_score >= 500: return "💎 Platinum", "badge-plat"
    if total_score >= 250: return "🥇 Gold", "badge-gold"
    if total_score >= 100: return "🥈 Silver", "badge-silver"
    return "🪨 Bronze", "badge-bronze"

def compute_streak(df: pd.DataFrame, target_date: date = None) -> int:
    if target_date is None:
        target_date = study_day(datetime.now())

    if df.empty:
        days = {target_date}
    else:
        days = set(pd.to_datetime(df["Date"], errors="coerce").dt.date.dropna())
        days.add(target_date)

    streak = 0
    cur = target_date
    while cur in days:
        streak += 1
        cur -= timedelta(days=1)
    return streak

def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def study_day(dt) -> date:
    """
    🌙 Study-day boundary: a study day runs from 7:00 AM to 6:59:59 AM the
    next calendar day, not midnight-to-midnight. Late-night study still
    belongs to the day it started, e.g. anything between 12:00 AM and 7:00 AM
    on 7 Sep counts as 6 Sep.
    """
    if hasattr(dt, "hour"):
        if dt.hour < 7:
            return dt.date() - timedelta(days=1)
        return dt.date()
    return dt

def fmt_clock(dt) -> str:
    """
    🕐 Format a clock time for display. Hours from 12:00 AM up to 6:59 AM are
    labeled "Night" (e.g. "Night 12:00", "Night 1:30") instead of "AM", since
    they still belong to the previous study day. 7:00 AM onward uses normal
    12-hour AM/PM formatting.
    """
    hour, minute = dt.hour, dt.minute
    if hour < 7:
        h12 = 12 if hour == 0 else hour
        return f"Night {h12}:{minute:02d}"
    h12 = hour % 12
    h12 = 12 if h12 == 0 else h12
    suffix = "AM" if hour < 12 else "PM"
    return f"{h12}:{minute:02d} {suffix}"

# --------------------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# --------------------------------------------------------------------------------------
defaults = {
    "running": False,
    "elapsed": 0.0,
    "start_ts": None,
    "session_active": False,
    "custom_subjects": [],
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

def current_elapsed():
    if st.session_state.running and st.session_state.start_ts is not None:
        return st.session_state.elapsed + (time.time() - st.session_state.start_ts)
    return st.session_state.elapsed

# --------------------------------------------------------------------------------------
# STUDENT ID GATE — same ID on any device loads the same saved data
# --------------------------------------------------------------------------------------
# Deliberately rendered in the MAIN page body, not the sidebar, so anything
# essential doesn't depend on the sidebar being open.
if not st.session_state.get("user_id"):
    st.markdown("<br><br>", unsafe_allow_html=True)
    _gate_logo_tag = f'<img src="{_logo_base64(LOGO_PATH)}" alt="Fakibaaz logo">' if LOGO_PATH.exists() else ""
    st.markdown(
        f"""<div class="fakibaaz-header id-gate-header">
            {_gate_logo_tag}
            <div class="fakibaaz-brand">Fakibaaz</div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="id-gate-block">', unsafe_allow_html=True)
    _id_input = st.text_input(
        "🔑 Enter your Student ID (e.g. 2202195)",
        help="Use the same ID on your laptop and phone to see the same saved sessions.",
    )
    st.caption("This ID isn't a password — it's just a lookup key. Anyone who enters the "
               "same ID sees the same data, so pick something only you'd know/use.")
    if st.button("Continue", type="primary"):
        if _id_input.strip():
            st.session_state["user_id"] = _id_input.strip()
            st.rerun()
        else:
            st.warning("Please type an ID first.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

user_id = st.session_state["user_id"]
with st.sidebar:
    st.success(f"Signed in as **{user_id}**")
    ws_check = _get_worksheet()
    if ws_check is not None:
        st.caption("🟢 Storage: Cloud (Google Sheets)")
    else:
        st.caption("📁 Storage: Local CSV (`study_data.csv`)")

    csv_data = get_export_csv(user_id)
    if csv_data:
        st.download_button(
            label="📥 Export Study Log (CSV)",
            data=csv_data,
            file_name=f"Fakibaaz_Study_Log_{user_id}.csv",
            mime="text/csv",
            use_container_width=True
        )

    if st.button("Switch ID"):
        del st.session_state["user_id"]
        st.rerun()

# --------------------------------------------------------------------------------------
# MAIN UI AREA — TOP BRAND HEADER & STRAIGHT LINE DIVIDER
# --------------------------------------------------------------------------------------
st.markdown("<br><br>", unsafe_allow_html=True)
logo_img_tag = f'<img src="{_logo_base64(LOGO_PATH)}" alt="Fakibaaz logo">' if LOGO_PATH.exists() else ""
st.markdown(
    f"""<div class="fakibaaz-header">
        {logo_img_tag}
        <div class="fakibaaz-brand">Fakibaaz</div>
    </div>
    <hr class="brand-divider">""",
    unsafe_allow_html=True,
)

# Show the "Topic Saved!" confirmation + balloons here, on the run AFTER the
# save. Firing them in the same run as the save and then immediately calling
# st.rerun() (as the Finish button used to) meant the rerun tore the page
# down before the browser had a chance to actually paint them — the message
# would flash or skip entirely. Stashing the result in session_state and
# rendering it on this fresh run instead makes it show reliably every time.
_last_result = st.session_state.pop("last_finish_result", None)
if _last_result:
    if _last_result["score"] >= 10.0:
        st.balloons()
    st.success(
        f"Topic Saved! Task Score: {_last_result['score']} pts · "
        f"Tier: {_last_result['rank_label']}"
    )

# --------------------------------------------------------------------------------------
# SESSION SETUP — Date, Subject, Topic & Target Minutes, all on one page
# --------------------------------------------------------------------------------------
st.markdown("##### 📝 Session Setup")
setup_c1, setup_c2, setup_c4, setup_c5 = st.columns([1.1, 1.5, 1.6, 1])

with setup_c1:
    the_date = st.date_input(
        "🗓️ Date",
        value=study_day(datetime.now()),
        help="Study days run 7:00 AM → 6:59 AM the next day, so a late-night "
             "session (e.g. 1 AM) auto-defaults to the previous day. Pick any "
             "date manually to log or view a different day.",
    )

with setup_c2:
    if "selected_subject" not in st.session_state:
        st.session_state["selected_subject"] = DEFAULT_SUBJECTS[0]

    all_subjects = DEFAULT_SUBJECTS + st.session_state.custom_subjects + ["+ Add Custom Subject..."]
    if st.session_state["selected_subject"] not in all_subjects:
        all_subjects.insert(len(all_subjects) - 1, st.session_state["selected_subject"])

    curr_idx = all_subjects.index(st.session_state["selected_subject"]) if st.session_state["selected_subject"] in all_subjects else 0
    subject_choice = st.selectbox("Course Subject", all_subjects, index=curr_idx)

    if subject_choice == "+ Add Custom Subject...":
        new_sub = st.text_input("Enter custom subject name")
        if new_sub and new_sub.strip():
            clean_sub = new_sub.strip()
            if clean_sub not in st.session_state.custom_subjects and clean_sub not in DEFAULT_SUBJECTS:
                st.session_state.custom_subjects.append(clean_sub)
            st.session_state["selected_subject"] = clean_sub
            st.rerun()
        else:
            subject = "General Study"
    else:
        st.session_state["selected_subject"] = subject_choice
        subject = subject_choice

with setup_c4:
    topic = st.text_input("Topic Name", placeholder="e.g. Carcinogenesis / Chapter 3")

with setup_c5:
    assigned_min = st.number_input("Target Min", min_value=1, max_value=360, value=20, step=1, help="Type any duration e.g. 11, 12, 13, 25 mins")

st.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------------------
# STATS (computed up-front so they can sit compactly next to the header,
# instead of a separate full-height side column stretching past the timer)
# --------------------------------------------------------------------------------------
df_all = load_data(user_id).copy()
total_score = float(df_all["Score"].sum()) if not df_all.empty else 0.0
if not df_all.empty:
    df_all_dated = df_all.copy()
    df_all_dated["Date"] = pd.to_datetime(df_all_dated["Date"]).dt.date
    today_rows = df_all_dated[df_all_dated["Date"] == the_date]
else:
    today_rows = pd.DataFrame()
today_total_score = float(today_rows["Score"].sum()) if not today_rows.empty else 0.0
today_tasks = len(today_rows)
today_tier, today_tier_cls = compute_tier(today_total_score)  # Tier now reflects THIS day only

auto_topic_name = f"Topic {today_tasks + 1}"
topic_display = topic if topic else auto_topic_name

session_head_box = st.container(key="session_head")
with session_head_box:
    head_left, head_stats = st.columns([2.0, 3.8])

    with head_left:
        st.markdown(f"### 📖 {subject}  ·  *{topic_display}*")

    with head_stats:
        st.markdown(f"""
        <div class="session-stats-block" style="text-align:right; line-height:1.7; padding-top:4px;">
          <span class="badge {today_tier_cls}" style="font-size:15px; padding:6px 16px;">{today_tier}</span>
          <br>
          <span style="font-size:15px; font-weight:600; color:#1e293b;">✅ {today_tasks} Job{'s' if today_tasks != 1 else ''}</span>
          &nbsp; <span style="font-size:15px; font-weight:600; color:#1e293b;">🎯 {today_total_score:.1f} pts today</span>
          <br>
          <span style="font-size:13px; font-weight:600; color:#94a3b8;">Overall: {total_score:.1f} pts</span>
        </div>
        """, unsafe_allow_html=True)

    elapsed = current_elapsed()

    target_sec = assigned_min * 60
    remaining = target_sec - elapsed

    if remaining >= 0:
        running_cls = " timer-running" if st.session_state.running else ""
        st.markdown(f'<div class="timer-container"><div class="timer-display{running_cls}">{fmt_time(remaining)}</div></div>', unsafe_allow_html=True)
        st.caption(f"⏱ Time remaining · Elapsed: {fmt_time(elapsed)} of {assigned_min}m")
    else:
        st.markdown(f'<div class="timer-container"><div class="timer-overtime">+{fmt_time(-remaining)}</div></div>', unsafe_allow_html=True)
        st.caption("⏰ Over target time — finish up topic to avoid score deduction!")

if st.session_state.running:
    st_autorefresh(interval=1000, key="focus_tick")

# Control buttons
b1, b2, b4 = st.columns(3)
with b1:
    if st.button("▶️ Start Focus", use_container_width=True, disabled=st.session_state.running):
        st.session_state.running = True
        st.session_state.session_active = True
        st.session_state.start_ts = time.time()
        st.rerun()
with b2:
    if st.button("⏸️ Pause", use_container_width=True, disabled=not st.session_state.running):
        st.session_state.elapsed = current_elapsed()
        st.session_state.running = False
        st.session_state.start_ts = None
        st.rerun()
with b4:
    if st.button("🔄 Reset", use_container_width=True):
        st.session_state.running = False
        st.session_state.elapsed = 0.0
        st.session_state.start_ts = None
        st.session_state.session_active = False
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ---- Finish Topic ----
finish_disabled = not (st.session_state.session_active or current_elapsed() >= 10)

# Guard against a double-click firing two saves: Streamlit doesn't block a
# second click while the first is still mid-flight (the Sheets write takes a
# moment), so without this a fast double-tap can append two rows for the
# same topic.
if st.session_state.get("finish_submitting", False):
    finish_disabled = True

if st.button("🏁 Finish & Score Topic", type="primary", use_container_width=True, disabled=finish_disabled):
    st.session_state.finish_submitting = True
    clicked_elapsed = current_elapsed()
    st.session_state.running = False
    st.session_state.elapsed = clicked_elapsed
    st.session_state.start_ts = None
    save_ok = False
    try:
        actual_min = round(clicked_elapsed / 60, 2)
        score = compute_task_score(assigned_min, actual_min)

        total_score_so_far = total_score + score
        rank_label, rank_cls = compute_tier(total_score_so_far)

        row = {
            "Date": the_date.strftime("%Y-%m-%d") if isinstance(the_date, (date, datetime)) else str(the_date),
            "Subject": subject,
            "Topic": topic if topic else auto_topic_name,
            "Assigned Min": assigned_min,
            "Actual Min": actual_min,
            "Score": score,
            "Rank": rank_label,
            "XP": 0,
            "Timestamp": datetime.now().isoformat(timespec="seconds")
        }
        save_ok = save_row(row, user_id)

        if save_ok:
            st.session_state.last_finish_result = {"score": score, "rank_label": rank_label}
            st.session_state.elapsed = 0.0
            st.session_state.session_active = False
            st.rerun()
    finally:
        st.session_state.finish_submitting = False

if finish_disabled:
    st.caption("💡 Press ▶️ Start Focus to enable saving. (Leave Topic Name blank and it'll auto-save as "
               f"\"{auto_topic_name}\".)")

# --------------------------------------------------------------------------------------
# DAY REPORT CARD
# --------------------------------------------------------------------------------------
st.markdown("---")
st.markdown("## 📊 Today's Focus Report Card")

df_all = load_data(user_id).copy()
if not df_all.empty:
    df_all["Date"] = pd.to_datetime(df_all["Date"], errors="coerce").dt.date
    today_df = df_all[df_all["Date"] == the_date]
else:
    today_df = pd.DataFrame()

if today_df.empty:
    st.info("🌱 No sessions finished for today yet.")
else:
    total_assigned = today_df["Assigned Min"].sum()
    total_actual = today_df["Actual Min"].sum()
    today_score = today_df["Score"].sum()
    day_label, day_cls = compute_tier(today_score)  # Tier reflects THIS day's score, not lifetime

    m1, m2, m3 = st.columns(3)
    m1.metric("Tasks Completed", len(today_df))
    m2.metric("Focus Time", f"{total_actual:.1f}m / {total_assigned:.0f}m")
    m3.metric("Today Task Score", f"{today_score:.1f} pts")

    st.markdown(f"<span class='badge {day_cls}' style='font-size:15px; margin-top:8px;'>{day_label} TIER</span>",
                unsafe_allow_html=True)

    st.markdown("#### Session Breakdown")
    display_cols = [c for c in ["Subject", "Topic", "Assigned Min", "Actual Min", "Score"] if c in today_df.columns]

    # Card layout instead of a fixed-width column "table" — a rigid multi-column
    # grid has no room to reflow on narrow/mobile screens and just squishes each
    # column until text wraps or overlaps. Each task is its own card with
    # label:value pairs that wrap naturally at any screen width, so it reads
    # fine on both desktop and mobile. Wrapped in a keyed container so the CSS
    # below can target just these delete buttons.
    with st.container(key="task_rows"):
        for row_idx, row in today_df.iterrows():
            card_col, del_col = st.columns([9, 1])
            with card_col:
                fields_html = "".join(
                    f"""<div class="task-field">
                            <span class="tf-label">{html.escape(str(col_name))}</span>
                            <span class="tf-value">{html.escape(str(row[col_name])) if pd.notna(row[col_name]) and row[col_name] != "" else "—"}</span>
                        </div>"""
                    for col_name in display_cols
                )
                st.markdown(f'<div class="task-card">{fields_html}</div>', unsafe_allow_html=True)
            with del_col:
                btn_key = f"del_today_{row_idx}_{row.get('Timestamp', '')}"
                if st.button("🗑️", key=btn_key, help="Remove this task", use_container_width=True):
                    if delete_row(user_id, row.to_dict()):
                        st.success("Task removed.")
                        st.rerun()
# ─── Footer ────────────────────────────────────────────────────────────────────
st.divider()
footer_logo_tag = f'<img src="{_logo_base64(LOGO_PATH)}" alt="Fakibaaz logo">' if LOGO_PATH.exists() else ""
st.markdown(f"""
<div class="tier-range-line">
    <strong>🪨 Bronze</strong> : 0 - 99 | <strong>🥈 Silver</strong> : 100 - 249 | <strong>🥇 Gold</strong> : 250 - 499 | <strong>💎 Platinum</strong> : 500 - 999 | <strong>💠 Diamond</strong> : 1,000 - 1,999 | <strong>👑 Master</strong> : 2,000 - 3,999 | <strong>🔥 Grandmaster</strong> : 4,000+
</div>
<hr class="tier-footer-divider">
<div class="footer-card">
    <div class="footer-bar">
        <div class="footer-brand">{footer_logo_tag}<div class="footer-brand-text">Fakibaaz</div></div>
        <div class="footer-meta">
            Designed &amp; developed by <a href="https://www.linkedin.com/in/nabiulorko" target="_blank">Nabiul Orko</a><br>
            <span class="footer-stack">Python · Pandas · Streamlit · Google Sheets</span><br>
            <span class="footer-copy">© 2026 All Rights Reserved</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
