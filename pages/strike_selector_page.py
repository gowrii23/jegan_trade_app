"""
pages/strike_selector_page.py
THE CORE PAGE — Shows exactly which strikes to BUY / SELL for Jegan's strategy
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.kite_engine import KiteEngine, StraddleStrategy, get_config


def get_next_expiries(symbol: str) -> list[date]:
    """Return next 4 weekly expiry dates (approx Thu/Fri)."""
    today = date.today()
    expiries = []
    d = today
    for _ in range(30):
        d += timedelta(days=1)
        # Nifty: Thursday | BankNifty: Wednesday | others: Thursday
        target_wd = {"BANKNIFTY": 2, "SENSEX": 4}.get(symbol, 3)
        if d.weekday() == target_wd:
            expiries.append(d)
        if len(expiries) >= 4:
            break
    return expiries


def color_action(val):
    if val == "SELL":
        return "background-color: rgba(255,77,109,0.15); color: #ff4d6d; font-weight: bold;"
    elif val == "BUY":
        return "background-color: rgba(0,229,160,0.12); color: #00e5a0; font-weight: bold;"
    return ""


def render():
    st.markdown("""
    <div style='margin-bottom:8px;'>
        <span style='font-family:Syne,sans-serif; font-size:26px; font-weight:800; letter-spacing:-1px;'>
            🎯 Strike Selector
        </span>
    </div>
    <div style='color:#6b7fa8; font-size:11px; letter-spacing:1.5px; margin-bottom:24px;'>
        EXACT STRIKES TO BUY & SELL · HEDGED STRADDLE SETUP
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.get("authenticated"):
        st.warning("⚠ Connect to Kite first → go to API Setup")
        return

    cfg = get_config()
    kite: KiteEngine = st.session_state.kite
    strat = StraddleStrategy(cfg["capital"], cfg.get("hedge_budget_per_lot", 4.0))

    # ── Controls ─────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    with c1:
        symbol = st.selectbox("Instrument", cfg.get("instruments", ["NIFTY", "BANKNIFTY"]))
    with c2:
        expiries = get_next_expiries(symbol)
        expiry = st.selectbox("Expiry", expiries, format_func=lambda d: d.strftime("%d %b %Y (%a)"))
    with c3:
        mode = st.radio("Mode", ["Hedged", "Naked"], index=0)
    with c4:
        hedge_budget = st.number_input("Hedge Budget ₹", min_value=0.5, max_value=20.0,
                                        value=float(cfg.get("hedge_budget_per_lot", 4.0)), step=0.5)

    strat.hedge_budget = hedge_budget

    if st.button("🔄  Fetch Option Chain & Compute Strikes", use_container_width=False, type="primary"):
        st.session_state.chain_loaded = True
        st.session_state.chain_symbol = symbol
        st.session_state.chain_expiry = expiry
        st.session_state.chain_mode = mode.lower()

    st.divider()

    if not st.session_state.get("chain_loaded"):
        st.info("👆 Select instrument, expiry and click **Fetch Option Chain**")
        _show_how_it_works()
        return

    # ── Fetch ────────────────────────────────────────────────
    use_symbol = st.session_state.chain_symbol
    use_expiry = st.session_state.chain_expiry
    use_mode = st.session_state.chain_mode

    with st.spinner(f"Loading {use_symbol} option chain for {use_expiry}..."):
        chain = kite.get_option_chain(use_symbol, use_expiry)

    spot_quote = kite.get_quote([f"NSE:{use_symbol} 50" if use_symbol == "NIFTY" else f"NSE:NIFTY BANK"])
    spot = list(spot_quote.values())[0]["last_price"]

    # ── Spot Header ──────────────────────────────────────────
    days_to_expiry = (use_expiry - date.today()).days

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("Spot", f"₹{spot:,.0f}")
    col_s2.metric("Expiry", use_expiry.strftime("%d %b"), delta=f"{days_to_expiry}d away")
    col_s3.metric("Capital", f"₹{cfg['capital']/100000:.1f}L")
    col_s4.metric("Mode", use_mode.upper(), delta="2x lots" if use_mode == "hedged" else "1x lots")

    st.divider()

    # ── Build Legs ───────────────────────────────────────────
    legs = strat.build_strategy_legs(spot, chain, use_symbol, use_expiry,
                                      mode="hedge" if use_mode == "hedged" else "naked")

    # ══════════════════════════════════════════════════════
    # STRATEGY SETUP TABLE — THE MAIN OUTPUT
    # ══════════════════════════════════════════════════════
    st.markdown("""
    <div style='font-family:Syne,sans-serif; font-size:18px; font-weight:800; color:#00e5a0; margin-bottom:12px;'>
        📋 Your Trade Setup
    </div>
    """, unsafe_allow_html=True)

    leg_rows = []
    for leg in legs:
        is_sell = leg["action"] == "SELL"
        action_label = "🔴 SELL" if is_sell else "🟢 BUY"
        pnl_sign = "+" if is_sell else "-"
        credit = leg["ltp"] * leg["quantity"]

        leg_rows.append({
            "ACTION": leg["action"],
            "TYPE": leg["type"],
            "STRIKE": f"₹{leg['strike']:,.0f}",
            "SYMBOL (NFO)": leg["symbol"],
            "LTP": f"₹{leg['ltp']:.2f}",
            "QUANTITY": leg["quantity"],
            "LOTS": leg["lots"],
            "CREDIT/DEBIT": f"{pnl_sign}₹{credit:,.0f}",
            "ROLE": leg["role"],
        })

    df_legs = pd.DataFrame(leg_rows)

    # Style the dataframe
    def style_row(row):
        if row["ACTION"] == "SELL":
            return ["background-color: rgba(255,77,109,0.08)"] * len(row)
        else:
            return ["background-color: rgba(0,229,160,0.05)"] * len(row)

    styled = df_legs.style.apply(style_row, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Net Position Summary ─────────────────────────────────
    net_credit = sum(
        leg["ltp"] * leg["quantity"] * (1 if leg["action"] == "SELL" else -1)
        for leg in legs
    )
    sell_legs = [l for l in legs if l["action"] == "SELL"]
    buy_legs = [l for l in legs if l["action"] == "BUY"]
    gross_credit = sum(l["ltp"] * l["quantity"] for l in sell_legs)
    hedge_cost = sum(l["ltp"] * l["quantity"] for l in buy_legs)

    st.markdown("---")
    n1, n2, n3, n4, n5 = st.columns(5)
    n1.metric("Gross Credit (SELL)", f"₹{gross_credit:,.0f}", help="Premium collected from selling ATM straddle")
    n2.metric("Hedge Cost (BUY)", f"-₹{hedge_cost:,.0f}", help="Cost of buying OTM protection")
    n3.metric("Net Credit", f"₹{net_credit:,.0f}", delta="receivable", delta_color="normal")
    n4.metric("Daily Target", f"₹{strat.lots_hedged * cfg['target_per_lot']:,}" if use_mode == "hedged" else f"₹{strat.lots_naked * cfg['target_per_lot']:,}")
    n5.metric("Est. Margin", f"₹{(strat.MARGIN_HEDGED if use_mode=='hedged' else strat.MARGIN_NAKED) * (strat.lots_hedged if use_mode=='hedged' else strat.lots_naked)/100000:.1f}L")

    st.divider()

    # ── Option Chain Viewer ───────────────────────────────────
    st.markdown("#### 📊 Option Chain")
    atm_info = strat.find_atm_strike(spot, chain)

    ce_chain = chain[chain["instrument_type"] == "CE"][["strike","ltp","oi","iv","tradingsymbol"]].copy()
    pe_chain = chain[chain["instrument_type"] == "PE"][["strike","ltp","oi","iv","tradingsymbol"]].copy()

    # Merge CE and PE
    merged = ce_chain.rename(columns={"ltp":"CE LTP","oi":"CE OI","iv":"CE IV","tradingsymbol":"CE Symbol"}).merge(
        pe_chain.rename(columns={"ltp":"PE LTP","oi":"PE OI","iv":"PE IV","tradingsymbol":"PE Symbol"}),
        on="strike"
    )

    # Mark ATM and hedge strikes
    atm_strike = atm_info["strike"]
    hedge_info = strat.find_hedge_strikes(spot, chain, atm_strike)

    ce_hedge_strike = hedge_info.get("ce_hedge", {}).get("strike", None)
    pe_hedge_strike = hedge_info.get("pe_hedge", {}).get("strike", None)

    def flag_row(row):
        if row["strike"] == atm_strike:
            return ["background-color: rgba(245,200,66,0.15); font-weight:bold;"] * len(row)
        if row["strike"] == ce_hedge_strike:
            return ["background-color: rgba(0,229,160,0.1);"] * len(row)
        if row["strike"] == pe_hedge_strike:
            return ["background-color: rgba(0,229,160,0.1);"] * len(row)
        return [""] * len(row)

    merged["TAG"] = merged["strike"].apply(lambda s: (
        "⭐ ATM SELL" if s == atm_strike
        else ("🟢 CE HEDGE BUY" if s == ce_hedge_strike
              else ("🟢 PE HEDGE BUY" if s == pe_hedge_strike else ""))
    ))

    # Show ±10 strikes around ATM
    merged_display = merged[abs(merged["strike"] - atm_strike) <= 10 * 50].copy()
    styled_chain = merged_display.style.apply(flag_row, axis=1)
    st.dataframe(styled_chain, use_container_width=True, hide_index=True, height=350)

    st.divider()

    # ── Payoff Diagram ────────────────────────────────────────
    st.markdown("#### 📈 Payoff at Expiry")
    _plot_payoff(spot, legs, use_mode)

    st.divider()

    # ── Place Orders ──────────────────────────────────────────
    _place_orders_section(legs, kite, cfg, use_mode)


def _plot_payoff(spot: float, legs: list, mode: str):
    """Plot P&L at expiry using Streamlit's chart."""
    from utils.kite_engine import StraddleStrategy
    strat_temp = StraddleStrategy(1000000)

    spots_range = np.linspace(spot * 0.88, spot * 1.12, 200)
    pnls_naked = []
    pnls_hedged = []

    for s in spots_range:
        total = 0
        for leg in legs:
            K = leg["strike"]
            qty = leg["quantity"]
            if leg["type"] == "CE":
                intrinsic = max(s - K, 0)
            else:
                intrinsic = max(K - s, 0)
            if leg["action"] == "SELL":
                total += (leg["ltp"] - intrinsic) * qty
            else:
                total += (intrinsic - leg["ltp"]) * qty
        pnls_hedged.append(total)
        pnls_naked.append(total)  # same scale for comparison

    df_payoff = pd.DataFrame({
        "Spot at Expiry": spots_range.round(0).astype(int),
        "P&L (₹)": [round(p) for p in pnls_hedged],
    })
    df_payoff = df_payoff.set_index("Spot at Expiry")

    st.line_chart(df_payoff, color=["#00e5a0"])
    st.caption("⬆ Payoff shows P&L across spot prices at expiry. Peak = max profit near ATM; wings = hedge kicks in on big moves.")


def _place_orders_section(legs: list, kite: KiteEngine, cfg: dict, mode: str):
    """Order placement UI."""
    st.markdown("#### 🚀 Place Orders")

    trade_mode = cfg.get("trade_mode", "paper")
    mode_badge = "PAPER TRADE" if trade_mode == "paper" else "⚠ LIVE TRADE"
    badge_color = "#f5c842" if trade_mode == "paper" else "#ff4d6d"
    st.markdown(f'<span style="background:rgba(245,200,66,0.15); color:{badge_color}; border:1px solid {badge_color}40; padding:3px 12px; border-radius:20px; font-size:10px; letter-spacing:1px;">{mode_badge}</span>', unsafe_allow_html=True)
    st.markdown("")

    col_buy, col_info = st.columns([1, 2])
    with col_info:
        st.markdown(f"""
        <div style='background:#0f1a2e; border:1px solid #1a2840; border-radius:8px; padding:12px; font-size:12px; color:#8fa3c0;'>
        <b style='color:#dce8f5;'>{len(legs)} orders</b> will be placed simultaneously<br>
        <span style='color:#6b7fa8;'>Mode: {mode.upper()} · {'2x lots with OTM hedge' if mode == 'hedged' else '1x lots unhedged'}</span>
        </div>
        """, unsafe_allow_html=True)

    with col_buy:
        if st.button("⚡  EXECUTE STRATEGY", use_container_width=True, type="primary"):
            with st.spinner("Placing orders..."):
                results = []
                for leg in legs:
                    result = kite.place_order(
                        symbol=leg["symbol"],
                        exchange="NFO",
                        transaction_type=leg["action"],
                        quantity=leg["quantity"],
                        price=leg["ltp"],
                        order_type="MARKET",
                        product="NRML",
                        tag="jegan_straddle",
                    )
                    results.append({**result, "symbol": leg["symbol"], "action": leg["action"], "ltp": leg["ltp"]})
                    # Add to active positions
                    st.session_state.active_positions.append({
                        "symbol": leg["symbol"],
                        "action": leg["action"],
                        "strike": leg["strike"],
                        "ltp_entry": leg["ltp"],
                        "quantity": leg["quantity"],
                        "role": leg["role"],
                        "order_id": result.get("order_id", ""),
                    })

                st.success(f"✓ {len(results)} orders placed in {trade_mode.upper()} mode")
                for r in results:
                    status_color = "#00e5a0" if "COMPLETE" in r.get("status","") or "PLACED" in r.get("status","") else "#ff4d6d"
                    st.markdown(f'<div style="font-size:11px; color:{status_color};">✓ {r["action"]} {r["symbol"]} @ ₹{r["ltp"]} → {r.get("status","")}</div>', unsafe_allow_html=True)


def _show_how_it_works():
    st.markdown("""
    <div style='background:#0f1a2e; border:1px solid #1a2840; border-radius:12px; padding:20px; margin-top:16px;'>
        <div style='font-family:Syne,sans-serif; font-weight:700; font-size:15px; color:#f5c842; margin-bottom:12px;'>
            ⚡ How Jegan's Hedge Strategy Works
        </div>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:16px; font-size:12px; color:#8fa3c0;'>
            <div>
                <div style='color:#ff4d6d; font-weight:600; margin-bottom:6px;'>🔴 SELL ATM Straddle</div>
                Sell 1 ATM Call + 1 ATM Put at same strike.<br>
                Collect full premium. Profit if market stays flat.<br>
                <br><b style='color:#dce8f5;'>Risk: Unlimited</b> on big moves.
            </div>
            <div>
                <div style='color:#00e5a0; font-weight:600; margin-bottom:6px;'>🟢 BUY OTM Hedge (₹1–4)</div>
                Buy far OTM Call + far OTM Put (1–4 rupee options).<br>
                This HALVES your margin: ₹3L → ₹1.5L per lot.<br>
                <br><b style='color:#dce8f5;'>Result: 2× lots, limited tail risk</b>
            </div>
        </div>
        <div style='margin-top:14px; padding:10px; background:rgba(0,229,160,0.06); border-radius:6px; font-size:11px; color:#00e5a0;'>
            💡 Same ₹10L capital → 3 lots naked (₹60K/yr) vs 6 lots hedged (₹1L/yr after hedge cost) = <b>33% ROI target</b>
        </div>
    </div>
    """, unsafe_allow_html=True)
