"""
pages/dashboard_page.py
Live Dashboard — Spot, IV, Position P&L, Daily Target Tracker
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.kite_engine import KiteEngine, StraddleStrategy, get_config


def render():
    st.markdown("""
    <div style='margin-bottom:8px;'>
        <span style='font-family:Syne,sans-serif; font-size:26px; font-weight:800; letter-spacing:-1px;'>
            📊 Live Dashboard
        </span>
    </div>
    <div style='color:#6b7fa8; font-size:11px; letter-spacing:1.5px; margin-bottom:24px;'>
        REAL-TIME P&L MONITOR · TARGET TRACKER · MARKET OVERVIEW
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("⚠ Connect to Kite first → go to API Setup")
        return

    cfg = get_config()
    kite: KiteEngine = st.session_state.kite
    strat = StraddleStrategy(cfg["capital"], cfg.get("hedge_budget_per_lot", 4.0))

    # ── Auto-refresh ─────────────────────────────────────────
    col_ref, col_time = st.columns([1, 3])
    with col_ref:
        auto = st.toggle("Auto Refresh (30s)", value=False)
    with col_time:
        st.markdown(f'<div style="color:#6b7fa8; font-size:11px; margin-top:8px;">Last updated: {datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

    if auto:
        import time; time.sleep(30); st.rerun()

    if st.button("🔄 Refresh Now"):
        st.rerun()

    st.divider()

    # ── Market Quotes ────────────────────────────────────────
    st.markdown("#### Market Overview")

    instruments_map = {
        "NIFTY": "NSE:NIFTY 50",
        "BANKNIFTY": "NSE:NIFTY BANK",
    }
    quotes = kite.get_quote(list(instruments_map.values()))

    q_cols = st.columns(len(instruments_map))
    for i, (name, inst) in enumerate(instruments_map.items()):
        q = quotes.get(inst, {})
        ltp = q.get("last_price", 0)
        chg = q.get("change", 0)
        with q_cols[i]:
            st.metric(
                label=name,
                value=f"₹{ltp:,.2f}",
                delta=f"{chg:+.2f}%",
                delta_color="normal",
            )

    st.divider()

    # ── Strategy Summary ─────────────────────────────────────
    st.markdown("#### Today's Strategy Setup")

    capital = cfg["capital"]
    target_per_lot = cfg.get("target_per_lot", 600)
    lots_naked = strat.lots_naked
    lots_hedged = strat.lots_hedged

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Capital", f"₹{capital/100000:.1f}L")
    c2.metric("Naked Lots", lots_naked, help="Without hedge @ ₹3L margin")
    c3.metric("Hedged Lots", lots_hedged, help="With hedge @ ₹1.5L margin — Jegan's way")
    c4.metric("Daily Target (Naked)", f"₹{lots_naked * target_per_lot:,}")
    c5.metric("Daily Target (Hedged)", f"₹{lots_hedged * target_per_lot:,}")
    c6.metric("Annual Target", f"₹{lots_hedged * target_per_lot * 100 / 1000:.0f}K",
              delta=f"~{lots_hedged * target_per_lot * 100 / capital * 100:.1f}% ROI")

    st.divider()

    # ── Active Positions P&L ─────────────────────────────────
    st.markdown("#### Active Positions")
    positions = kite.get_positions()

    if isinstance(positions, pd.DataFrame) and not positions.empty:
        # Try to calculate MTM P&L
        if "unrealised" in positions.columns:
            total_mtm = positions["unrealised"].sum()
            st.metric("Total Unrealised P&L", f"₹{total_mtm:,.0f}",
                      delta_color="normal" if total_mtm >= 0 else "inverse")

        display_cols = [c for c in ["tradingsymbol", "buy_quantity", "sell_quantity",
                                     "average_price", "last_price", "unrealised", "pnl"]
                        if c in positions.columns]
        if display_cols:
            st.dataframe(positions[display_cols], use_container_width=True, hide_index=True)
        else:
            st.dataframe(positions, use_container_width=True, hide_index=True)
    elif st.session_state.get("active_positions"):
        # Show paper positions
        pos_df = pd.DataFrame(st.session_state.active_positions)

        # Mock MTM using random noise
        if not pos_df.empty:
            pos_df["current_ltp"] = pos_df["ltp_entry"].apply(
                lambda x: round(x * (1 + np.random.normal(0, 0.05)), 2)
            )
            pos_df["mtm_pnl"] = pos_df.apply(
                lambda r: round(
                    (r["ltp_entry"] - r["current_ltp"]) * r["quantity"]
                    if r["action"] == "SELL"
                    else (r["current_ltp"] - r["ltp_entry"]) * r["quantity"],
                    2
                ),
                axis=1
            )
            total_paper_pnl = pos_df["mtm_pnl"].sum()

            pnl_color = "#00e5a0" if total_paper_pnl >= 0 else "#ff4d6d"
            st.markdown(f"""
            <div style='background:#0f1a2e; border:1px solid #1a2840; border-radius:8px; padding:12px; margin-bottom:12px;'>
                <span style='color:#6b7fa8; font-size:10px; letter-spacing:1px;'>PAPER MTM P&L</span><br>
                <span style='font-family:Syne,sans-serif; font-size:28px; font-weight:800; color:{pnl_color};'>
                    {"+" if total_paper_pnl >= 0 else ""}₹{total_paper_pnl:,.0f}
                </span>
                <span style='color:#6b7fa8; font-size:11px; margin-left:8px;'>of ₹{cfg.get("target_per_lot", 600) * lots_hedged:,} target</span>
            </div>
            """, unsafe_allow_html=True)

            # Progress bar toward target
            target_today = cfg.get("target_per_lot", 600) * lots_hedged
            progress = min(max(total_paper_pnl / target_today, 0), 1) if target_today > 0 else 0
            st.progress(progress, text=f"Daily target progress: {progress * 100:.1f}%")

            st.dataframe(pos_df[["symbol","action","strike","role","ltp_entry","current_ltp","mtm_pnl"]],
                         use_container_width=True, hide_index=True)
    else:
        st.info("No active positions. Go to **Strike Selector** to set up a trade.")

    st.divider()

    # ── Stop Loss Monitor ─────────────────────────────────────
    st.markdown("#### 🛡 Portfolio Stop Loss")
    sl_pct = cfg.get("stop_loss_pct", 1.5)
    sl_value = capital * sl_pct / 100

    col_sl1, col_sl2 = st.columns(2)
    with col_sl1:
        st.markdown(f"""
        <div style='background:#0f1a2e; border:1px solid rgba(255,77,109,0.3); border-radius:8px; padding:14px;'>
            <div style='color:#6b7fa8; font-size:10px; letter-spacing:1px;'>PORTFOLIO STOP LOSS</div>
            <div style='font-family:Syne,sans-serif; font-size:24px; font-weight:800; color:#ff4d6d;'>-₹{sl_value:,.0f}</div>
            <div style='color:#6b7fa8; font-size:11px;'>{sl_pct}% of ₹{capital/100000:.1f}L capital</div>
        </div>
        """, unsafe_allow_html=True)
    with col_sl2:
        st.markdown(f"""
        <div style='background:#0f1a2e; border:1px solid #1a2840; border-radius:8px; padding:14px;'>
            <div style='color:#6b7fa8; font-size:10px; letter-spacing:1px;'>MARGIN USED (EST.)</div>
            <div style='font-family:Syne,sans-serif; font-size:24px; font-weight:800; color:#f5c842;'>
                ₹{strat.MARGIN_HEDGED * lots_hedged / 100000:.1f}L
            </div>
            <div style='color:#6b7fa8; font-size:11px;'>for {lots_hedged} hedged lots</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── IV Snapshot ───────────────────────────────────────────
    st.markdown("#### Implied Volatility Snapshot")
    from datetime import timedelta
    today = date.today()
    expiry_guess = today + timedelta(days=(3 - today.weekday()) % 7 + 1)

    try:
        chain = kite.get_option_chain("NIFTY", expiry_guess)
        if not chain.empty and "iv" in chain.columns:
            atm_info = strat.find_atm_strike(
                list(quotes.get("NSE:NIFTY 50", {}).values())[0] if quotes else 24000,
                chain
            )
            atm_iv = chain[chain["strike"] == atm_info["strike"]]["iv"].mean()

            iv_col1, iv_col2, iv_col3 = st.columns(3)
            iv_col1.metric("NIFTY ATM IV", f"{atm_iv:.1f}%")
            iv_col2.metric("Expected Move (1-day)", f"±{atm_iv/100 * 24000 * (1/252)**0.5:.0f} pts")
            iv_col3.metric("IV Regime", "HIGH" if atm_iv > 16 else "NORMAL" if atm_iv > 12 else "LOW",
                           delta="Favour selling" if atm_iv > 14 else "Caution")
    except Exception as e:
        st.caption(f"IV data: {e}")
