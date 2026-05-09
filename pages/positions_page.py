"""
pages/positions_page.py
Active Positions, Order Log, Square-Off Controls
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.kite_engine import KiteEngine, get_config


def render():
    st.markdown("""
    <div style='margin-bottom:8px;'>
        <span style='font-family:Syne,sans-serif; font-size:26px; font-weight:800; letter-spacing:-1px;'>
            📋 Positions & Orders
        </span>
    </div>
    <div style='color:#6b7fa8; font-size:11px; letter-spacing:1.5px; margin-bottom:24px;'>
        LIVE POSITIONS · ORDER HISTORY · SQUARE-OFF
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("⚠ Connect to Kite first → go to API Setup")
        return

    cfg = get_config()
    kite: KiteEngine = st.session_state.kite

    tab1, tab2, tab3 = st.tabs(["📍 Active Positions", "📜 Order Log", "🚪 Square-Off"])

    # ── Tab 1: Active Positions ───────────────────────────────
    with tab1:
        positions = kite.get_positions()

        if isinstance(positions, pd.DataFrame) and not positions.empty:
            st.dataframe(positions, use_container_width=True, hide_index=True)
        elif st.session_state.get("active_positions"):
            pos_df = pd.DataFrame(st.session_state.active_positions)
            st.dataframe(pos_df, use_container_width=True, hide_index=True)

            total_lots = pos_df["quantity"].sum() if "quantity" in pos_df.columns else 0
            st.metric("Total Quantities", f"{total_lots}")
        else:
            st.info("No active positions. Place a trade from **Strike Selector**.")

    # ── Tab 2: Order Log ──────────────────────────────────────
    with tab2:
        orders = kite.get_orders()
        if isinstance(orders, pd.DataFrame) and not orders.empty:
            st.dataframe(orders, use_container_width=True, hide_index=True)
        elif st.session_state.get("trade_log"):
            log_df = pd.DataFrame(st.session_state.trade_log)
            st.dataframe(log_df, use_container_width=True, hide_index=True)

            csv = log_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Export Order Log CSV", csv,
                               file_name=f"orders_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime="text/csv")
        else:
            st.info("No orders placed yet.")

    # ── Tab 3: Square-Off ─────────────────────────────────────
    with tab3:
        st.markdown("#### Close All Positions")
        st.warning("⚠ This will place MARKET orders to close all active positions.")

        positions_exist = (
            (isinstance(kite.get_positions(), pd.DataFrame) and not kite.get_positions().empty) or
            bool(st.session_state.get("active_positions"))
        )

        if not positions_exist:
            st.info("No positions to square off.")
            return

        col_sq1, col_sq2 = st.columns([1, 3])
        with col_sq1:
            if st.button("🚪  SQUARE OFF ALL", type="primary", use_container_width=True):
                with st.spinner("Closing all positions..."):
                    positions_list = st.session_state.get("active_positions", [])
                    closed = []
                    for pos in positions_list:
                        close_action = "BUY" if pos.get("action") == "SELL" else "SELL"
                        result = kite.place_order(
                            symbol=pos["symbol"],
                            exchange="NFO",
                            transaction_type=close_action,
                            quantity=pos["quantity"],
                            price=0,
                            order_type="MARKET",
                            product="NRML",
                            tag="jegan_squareoff",
                        )
                        closed.append(result)

                    st.session_state.active_positions = []
                    st.success(f"✓ {len(closed)} positions closed in {cfg.get('trade_mode','paper').upper()} mode")
                    for r in closed:
                        st.markdown(f'<div style="font-size:11px; color:#00e5a0;">✓ {r.get("symbol","")} → {r.get("status","")}</div>', unsafe_allow_html=True)

        with col_sq2:
            st.markdown("""
            <div style='background:#0f1a2e; border:1px solid rgba(255,77,109,0.2); border-radius:8px; padding:12px; font-size:11px; color:#8fa3c0;'>
            Square-off places reverse MARKET orders for each leg.<br>
            In <b style='color:#f5c842;'>paper mode</b>, orders are logged only — no real execution.<br>
            In <b style='color:#ff4d6d;'>live mode</b>, orders go directly to Zerodha NSE/NFO.
            </div>
            """, unsafe_allow_html=True)
