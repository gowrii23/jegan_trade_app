"""
pages/auth_page.py
Kite API Key Configuration & OAuth Login
"""

import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.kite_engine import KiteEngine, load_config, save_config, get_config


def render():
    st.markdown("""
    <div style='margin-bottom:8px;'>
        <span style='font-family:Syne,sans-serif; font-size:26px; font-weight:800; letter-spacing:-1px;'>
            🔑 API Setup & Authentication
        </span>
    </div>
    <div style='color:#6b7fa8; font-size:11px; letter-spacing:1.5px; margin-bottom:24px;'>
        CONFIGURE ZERODHA KITE CONNECT · PAPER OR LIVE TRADING
    </div>
    """, unsafe_allow_html=True)

    cfg = get_config()

    # ── Mode selector ────────────────────────────────────────
    col_mode, col_status = st.columns([2, 1])
    with col_mode:
        trade_mode = st.radio(
            "Trading Mode",
            options=["paper", "live"],
            index=0 if cfg.get("trade_mode") == "paper" else 1,
            horizontal=True,
            help="Paper mode simulates orders. Live mode sends real orders to Zerodha.",
        )
        cfg["trade_mode"] = trade_mode

    with col_status:
        if st.session_state.get("authenticated"):
            st.success("✓ Connected to Kite")
        else:
            st.warning("○ Not Connected")

    st.divider()

    # ── API Credentials ──────────────────────────────────────
    st.markdown("#### Kite Connect Credentials")
    st.markdown('<div style="color:#6b7fa8; font-size:11px; margin-bottom:12px;">Get keys from <a href="https://developers.kite.trade" target="_blank" style="color:#00e5a0;">developers.kite.trade</a> → My Apps</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        api_key = st.text_input(
            "API Key",
            value=cfg.get("api_key", ""),
            type="password",
            placeholder="e.g. abcde12345fghij",
            help="Your Kite Connect App API Key",
        )
    with c2:
        api_secret = st.text_input(
            "API Secret",
            value=cfg.get("api_secret", ""),
            type="password",
            placeholder="e.g. xxxxxxxxxxxxxxxxxx",
            help="Your Kite Connect App API Secret",
        )

    saved_token = st.text_input(
        "Access Token (optional — paste if you already have one)",
        value=cfg.get("access_token", ""),
        type="password",
        placeholder="Paste access token here to skip OAuth flow",
    )

    if st.button("💾  Save Credentials", use_container_width=False):
        cfg["api_key"] = api_key
        cfg["api_secret"] = api_secret
        cfg["access_token"] = saved_token
        save_config(cfg)
        st.session_state.config = cfg
        st.success("Credentials saved to config/kite_config.json")

    st.divider()

    # ── OAuth Login Flow ─────────────────────────────────────
    st.markdown("#### Step-by-Step Login")

    with st.expander("📖 How Kite OAuth works", expanded=False):
        st.markdown("""
        1. **Save your API Key & Secret** above
        2. Click **Open Kite Login** → you'll be redirected to Zerodha
        3. Login with your Zerodha credentials
        4. After login, Zerodha redirects to your app URL with `?request_token=XXXX`
        5. Copy that token and paste it in **Step 3** below
        6. Click **Generate Session** to get your access token
        
        Access token is valid for **one trading day** (resets at 6 AM).
        """)

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("**Step 1: Open Login**")
        if st.button("🌐  Open Kite Login", use_container_width=True):
            if not api_key:
                st.error("Enter API key first")
            else:
                engine = KiteEngine(api_key, api_secret)
                login_url = engine.get_login_url()
                st.markdown(f'<a href="{login_url}" target="_blank" style="color:#00e5a0; text-decoration:none; font-size:12px;">→ Click here to login at Zerodha</a>', unsafe_allow_html=True)
                st.info(f"Login URL: `{login_url}`")

    with col_b:
        st.markdown("**Step 2: Copy request_token**")
        st.markdown('<div style="color:#6b7fa8; font-size:11px;">After Zerodha login,<br>copy token from URL bar</div>', unsafe_allow_html=True)
        request_token = st.text_input("request_token", placeholder="Paste token here", label_visibility="collapsed")

    with col_c:
        st.markdown("**Step 3: Generate Session**")
        if st.button("⚡  Generate Access Token", use_container_width=True):
            if not request_token:
                st.error("Paste request_token first")
            elif not api_key or not api_secret:
                st.error("API Key & Secret required")
            else:
                with st.spinner("Generating session..."):
                    try:
                        engine = KiteEngine(api_key, api_secret)
                        access_token = engine.generate_session(request_token)
                        cfg["access_token"] = access_token
                        save_config(cfg)
                        st.session_state.config = cfg
                        st.session_state.kite = engine
                        st.session_state.authenticated = True
                        st.success(f"✓ Access token generated!")
                        st.code(access_token, language=None)
                    except Exception as e:
                        st.error(f"Session generation failed: {e}")
                        # Paper mode fallback
                        engine = KiteEngine("", "")
                        st.session_state.kite = engine
                        st.session_state.authenticated = True
                        st.warning("Running in Paper Trade mode")

    st.divider()

    # ── Quick Connect (Paper Mode) ───────────────────────────
    st.markdown("#### ⚡ Quick Start (Paper Mode)")
    st.markdown('<div style="color:#6b7fa8; font-size:11px; margin-bottom:8px;">No Kite credentials needed — uses synthetic market data for testing strategy</div>', unsafe_allow_html=True)

    if st.button("🚀  Connect in Paper Mode", use_container_width=False):
        engine = KiteEngine("PAPER_KEY", "PAPER_SECRET", "PAPER_TOKEN")
        engine.paper_mode = True
        st.session_state.kite = engine
        st.session_state.authenticated = True
        cfg["trade_mode"] = "paper"
        st.session_state.config = cfg
        st.success("✓ Paper mode active! Navigate to Dashboard →")
        st.session_state.page = "dashboard"
        st.rerun()

    st.divider()

    # ── Strategy Parameters ──────────────────────────────────
    st.markdown("#### Strategy Parameters")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        capital = st.number_input(
            "Capital (₹)",
            min_value=300000, max_value=10000000,
            value=cfg.get("capital", 1000000),
            step=100000,
            format="%d",
        )
    with c2:
        target = st.number_input(
            "Target per Lot (₹)",
            min_value=200, max_value=2000,
            value=cfg.get("target_per_lot", 600),
            step=50,
        )
    with c3:
        hedge_budget = st.number_input(
            "Max Hedge Premium (₹)",
            min_value=0.5, max_value=20.0,
            value=float(cfg.get("hedge_budget_per_lot", 4.0)),
            step=0.5,
            help="Max price to pay for each OTM hedge option (Jegan: ₹1–4)",
        )
    with c4:
        sl_pct = st.number_input(
            "Portfolio SL (%)",
            min_value=0.5, max_value=5.0,
            value=float(cfg.get("stop_loss_pct", 1.5)),
            step=0.25,
        )

    instruments = st.multiselect(
        "Instruments",
        options=["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY"],
        default=cfg.get("instruments", ["NIFTY", "BANKNIFTY"]),
    )

    if st.button("💾  Save Strategy Config", use_container_width=False):
        cfg.update({
            "capital": int(capital),
            "target_per_lot": int(target),
            "hedge_budget_per_lot": float(hedge_budget),
            "stop_loss_pct": float(sl_pct),
            "instruments": instruments,
        })
        save_config(cfg)
        st.session_state.config = cfg
        st.success("Strategy config saved!")

    # ── Margin Preview ───────────────────────────────────────
    from utils.kite_engine import StraddleStrategy
    strat = StraddleStrategy(capital, hedge_budget)

    st.divider()
    st.markdown("#### Capital Utilisation Preview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Naked Lots", strat.lots_naked, help="Lots without hedge @ ₹3L/lot")
    m2.metric("Hedged Lots", strat.lots_hedged, help="Lots with hedge @ ₹1.5L/lot — 2× more")
    m3.metric("Daily Target (Hedged)", f"₹{strat.lots_hedged * target:,}")
    m4.metric("Annual Target (Hedged)", f"₹{strat.lots_hedged * target * 100 / 1000:.0f}K",
              delta=f"~{strat.lots_hedged * target * 100 / capital * 100:.1f}% ROI")
