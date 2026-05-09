"""
╔══════════════════════════════════════════════════════════════╗
║   Jegan's Leveraged Straddle Strategy — Zerodha Kite App    ║
║   Author: Built for Gowrishankar | NSE Options Automation   ║
╚══════════════════════════════════════════════════════════════╝
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime

# ── Page config ─────────────────────────────────────────────
st.set_page_config(
    page_title="Jegan Straddle Trader",
    page_icon="⊕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Syne:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'JetBrains Mono', monospace;
    background-color: #080d16;
    color: #dce8f5;
}
.stApp { background: #080d16; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0d1525 !important;
    border-right: 1px solid #1a2840;
}
[data-testid="stSidebar"] .stMarkdown p { color: #8fa3c0; font-size: 11px; letter-spacing: 1px; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #0f1a2e;
    border: 1px solid #1a2840;
    border-radius: 10px;
    padding: 14px !important;
}
[data-testid="stMetricValue"] { color: #00e5a0 !important; font-family: 'Syne', sans-serif !important; }
[data-testid="stMetricLabel"] { color: #6b7fa8 !important; font-size: 10px !important; letter-spacing: 1.5px !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #00e5a0, #00a875);
    color: #080d16;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    letter-spacing: 0.5px;
    transition: all 0.2s;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(0,229,160,0.3); }

/* Danger button */
.danger-btn > button {
    background: linear-gradient(135deg, #ff4d6d, #cc2244) !important;
    color: white !important;
}

/* DataFrames */
[data-testid="stDataFrame"] { border: 1px solid #1a2840; border-radius: 10px; }
.stDataFrame thead tr th { background: #0d1525 !important; color: #6b7fa8 !important; font-size: 11px !important; letter-spacing: 1px !important; }

/* Expanders */
.streamlit-expanderHeader {
    background: #0f1a2e !important;
    border: 1px solid #1a2840 !important;
    border-radius: 8px !important;
    color: #8fa3c0 !important;
    font-size: 12px !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: #0d1525; border-radius: 8px; border: 1px solid #1a2840; }
.stTabs [data-baseweb="tab"] { color: #6b7fa8; font-size: 12px; letter-spacing: 1px; }
.stTabs [aria-selected="true"] { color: #00e5a0 !important; border-bottom: 2px solid #00e5a0 !important; }

/* Input widgets */
.stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div {
    background: #0d1525 !important;
    border: 1px solid #1a2840 !important;
    color: #dce8f5 !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px !important;
}
.stSlider > div > div > div { background: #00e5a0 !important; }

/* Alert boxes */
.stAlert { border-radius: 8px; font-size: 12px; }

/* Headers */
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }

/* Divider */
hr { border-color: #1a2840; }

/* Status badges */
.badge-live { background: rgba(0,229,160,0.15); color: #00e5a0; border: 1px solid rgba(0,229,160,0.3); padding: 2px 10px; border-radius: 20px; font-size: 10px; letter-spacing: 1px; }
.badge-paper { background: rgba(245,200,66,0.15); color: #f5c842; border: 1px solid rgba(245,200,66,0.3); padding: 2px 10px; border-radius: 20px; font-size: 10px; letter-spacing: 1px; }

/* Table cells colored */
.profit { color: #00e5a0; font-weight: 600; }
.loss { color: #ff4d6d; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Session State Init ───────────────────────────────────────
if "kite" not in st.session_state:
    st.session_state.kite = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "trade_log" not in st.session_state:
    st.session_state.trade_log = []
if "active_positions" not in st.session_state:
    st.session_state.active_positions = []

# ── Navigation ───────────────────────────────────────────────
from pages import auth_page, dashboard_page, strike_selector_page, backtest_page, positions_page

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style='text-align:center; padding: 16px 0 8px 0;'>
            <div style='font-family:Syne,sans-serif; font-size:20px; font-weight:800; color:#00e5a0; letter-spacing:-0.5px;'>⊕ JEGAN STRADDLE</div>
            <div style='font-size:9px; letter-spacing:2px; color:#6b7fa8; margin-top:2px;'>LEVERAGED OPTIONS SYSTEM</div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Connection status
        if st.session_state.authenticated:
            st.markdown('<div style="text-align:center"><span class="badge-live">● KITE CONNECTED</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="text-align:center"><span class="badge-paper">○ NOT CONNECTED</span></div>', unsafe_allow_html=True)

        st.markdown("")

        pages = {
            "🔑  API Setup & Auth": "auth",
            "📊  Live Dashboard": "dashboard",
            "🎯  Strike Selector": "strikes",
            "🔄  Backtest Engine": "backtest",
            "📋  Positions & Orders": "positions",
        }

        if "page" not in st.session_state:
            st.session_state.page = "auth"

        for label, key in pages.items():
            is_active = st.session_state.page == key
            btn_style = "background:#0f2a1a; border:1px solid #00e5a040; color:#00e5a0;" if is_active else "background:transparent; border:1px solid #1a2840; color:#6b7fa8;"
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key

        st.divider()
        st.markdown("""
        <div style='font-size:9px; color:#3a4d6a; letter-spacing:1px; text-align:center; line-height:1.8;'>
        TARGET: ₹600/LOT/DAY<br>
        HEDGE: FAR OTM (₹1–4)<br>
        MARGIN BENEFIT: 2x LOTS<br>
        ROI TARGET: 33%/yr
        </div>
        """, unsafe_allow_html=True)

render_sidebar()

# ── Page Router ──────────────────────────────────────────────
page = st.session_state.get("page", "auth")

if page == "auth":
    auth_page.render()
elif page == "dashboard":
    dashboard_page.render()
elif page == "strikes":
    strike_selector_page.render()
elif page == "backtest":
    backtest_page.render()
elif page == "positions":
    positions_page.render()
