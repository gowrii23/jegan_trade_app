"""
pages/backtest_page.py
Monte Carlo Backtest — Naked vs Hedged Straddle across random expiries
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.kite_engine import run_backtest, backtest_summary, get_config


def render():
    st.markdown("""
    <div style='margin-bottom:8px;'>
        <span style='font-family:Syne,sans-serif; font-size:26px; font-weight:800; letter-spacing:-1px;'>
            🔄 Backtest Engine
        </span>
    </div>
    <div style='color:#6b7fa8; font-size:11px; letter-spacing:1.5px; margin-bottom:24px;'>
        MONTE CARLO · NAKED VS HEDGED · RANDOM EXPIRY SAMPLING
    </div>
    """, unsafe_allow_html=True)

    cfg = get_config()

    # ── Config ────────────────────────────────────────────────
    st.markdown("#### Backtest Parameters")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        capital = st.number_input("Capital (₹)", min_value=300000, max_value=10000000,
                                   value=cfg.get("capital", 1000000), step=100000)
    with c2:
        year = st.selectbox("Year", [2022, 2023, 2024, 2025], index=2)
    with c3:
        n_samples = st.slider("# Expiries to Sample", 10, 200, 50, 10)
    with c4:
        hedge_budget = st.number_input("Hedge Budget ₹", min_value=0.5, max_value=20.0,
                                        value=float(cfg.get("hedge_budget_per_lot", 4.0)), step=0.5)
    with c5:
        seed = st.number_input("Random Seed", min_value=1, max_value=9999, value=42)

    if st.button("▶  Run Backtest", type="primary", use_container_width=False):
        with st.spinner(f"Running {n_samples} expiry simulations..."):
            df = run_backtest(capital, year, n_samples, hedge_budget, seed)
            st.session_state.backtest_df = df
            st.session_state.backtest_capital = capital
        st.success(f"✓ Backtest complete — {n_samples} samples")

    if "backtest_df" not in st.session_state:
        _show_info_box()
        return

    df: pd.DataFrame = st.session_state.backtest_df
    cap = st.session_state.backtest_capital
    summary = backtest_summary(df, cap)

    st.divider()

    # ── Scorecard ─────────────────────────────────────────────
    st.markdown("#### Results Summary")
    col_naked, col_hedge = st.columns(2)

    with col_naked:
        st.markdown("""
        <div style='background:#0f1a2e; border:1px solid #1a2840; border-radius:10px; padding:16px; margin-bottom:12px;'>
            <div style='color:#6b7fa8; font-size:10px; letter-spacing:1.5px; margin-bottom:8px;'>NAKED STRADDLE</div>
        """, unsafe_allow_html=True)
        n1, n2 = st.columns(2)
        pnl_color_n = "#00e5a0" if summary["naked_total"] >= 0 else "#ff4d6d"
        n1.metric("Total P&L", f"₹{summary['naked_total']:,.0f}")
        n2.metric("ROI", f"{summary['naked_roi']:.2f}%")
        n3, n4 = st.columns(2)
        n3.metric("Win Rate", f"{summary['naked_win_rate']:.1f}%")
        n4.metric("Worst Day", f"₹{summary['naked_max_loss']:,.0f}")
        st.metric("Sharpe Ratio", f"{summary['sharpe_naked']:.2f}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_hedge:
        st.markdown("""
        <div style='background:#0f1a2e; border:1px solid rgba(0,229,160,0.2); border-radius:10px; padding:16px; margin-bottom:12px;'>
            <div style='color:#00e5a0; font-size:10px; letter-spacing:1.5px; margin-bottom:8px;'>⊕ JEGAN'S HEDGED STRADDLE</div>
        """, unsafe_allow_html=True)
        h1, h2 = st.columns(2)
        h1.metric("Total P&L", f"₹{summary['hedged_total']:,.0f}",
                  delta=f"+₹{summary['hedged_total']-summary['naked_total']:,.0f} vs naked")
        h2.metric("ROI", f"{summary['hedged_roi']:.2f}%",
                  delta=f"+{summary['hedged_roi']-summary['naked_roi']:.2f}%")
        h3, h4 = st.columns(2)
        h3.metric("Win Rate", f"{summary['hedged_win_rate']:.1f}%")
        h4.metric("Worst Day", f"₹{summary['hedged_max_loss']:,.0f}")
        st.metric("Sharpe Ratio", f"{summary['sharpe_hedged']:.2f}",
                  delta=f"+{summary['sharpe_hedged']-summary['sharpe_naked']:.2f}" if summary['sharpe_hedged'] > summary['sharpe_naked'] else None)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Tail events ───────────────────────────────────────────
    tail_df = df[df["is_tail_event"]]
    if not tail_df.empty:
        st.warning(f"⚠ {len(tail_df)} tail events detected ({len(tail_df)/len(df)*100:.1f}% of samples). "
                   f"Naked avg loss on tail: ₹{tail_df['naked_pnl'].mean():,.0f} vs Hedged: ₹{tail_df['hedged_pnl'].mean():,.0f}")

    st.divider()

    # ── P&L per expiry ────────────────────────────────────────
    st.markdown("#### P&L Per Expiry")
    display_df = df[["sample","move_pct","iv_pct","is_tail_event",
                      "naked_lots","hedged_lots","naked_pnl","hedged_pnl","hedge_cost"]].copy()
    display_df.columns = ["#","Move%","IV%","Tail","Naked Lots","Hedged Lots",
                           "Naked P&L","Hedged P&L","Hedge Cost"]

    def color_pnl(val):
        if isinstance(val, (int, float)):
            if val > 0: return "color: #00e5a0; font-weight:600;"
            elif val < 0: return "color: #ff4d6d; font-weight:600;"
        return ""

    def color_tail(val):
        return "color: #ff4d6d; font-weight:600;" if val else "color: #3a4d6a;"

    styled_df = display_df.style \
        .applymap(color_pnl, subset=["Naked P&L", "Hedged P&L"]) \
        .applymap(color_tail, subset=["Tail"])

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── Cumulative P&L Chart ──────────────────────────────────
    st.markdown("#### Cumulative P&L Trajectory")
    df_cumul = pd.DataFrame({
        "Naked": df["naked_pnl"].cumsum(),
        "Hedged": df["hedged_pnl"].cumsum(),
    })
    st.line_chart(df_cumul, color=["#6b7fa8", "#00e5a0"])
    st.caption("Green = Hedged | Grey = Naked. Divergence grows on tail events.")

    st.divider()

    # ── Distribution ─────────────────────────────────────────
    st.markdown("#### P&L Distribution")
    col_hist1, col_hist2 = st.columns(2)
    with col_hist1:
        st.markdown("Naked P&L Distribution")
        hist_n = pd.DataFrame({"Naked P&L": df["naked_pnl"]})
        st.bar_chart(hist_n.value_counts(bins=20).sort_index())
    with col_hist2:
        st.markdown("Hedged P&L Distribution")
        hist_h = pd.DataFrame({"Hedged P&L": df["hedged_pnl"]})
        st.bar_chart(hist_h.value_counts(bins=20).sort_index())

    st.divider()

    # ── Export ────────────────────────────────────────────────
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇  Export Backtest CSV",
        data=csv,
        file_name=f"jegan_backtest_{year}_n{n_samples}_s{seed}.csv",
        mime="text/csv",
    )


def _show_info_box():
    st.markdown("""
    <div style='background:#0f1a2e; border:1px solid #1a2840; border-radius:12px; padding:24px; margin-top:16px;'>
        <div style='font-family:Syne,sans-serif; font-weight:700; font-size:15px; color:#f5c842; margin-bottom:12px;'>
            🎲 Monte Carlo Backtesting Methodology
        </div>
        <div style='color:#8fa3c0; font-size:12px; line-height:2;'>
            • Simulates <b style='color:#dce8f5;'>N random expiry days</b> from a chosen year<br>
            • Each expiry: realistic IV, ATM premium, spot move, tail event probability<br>
            • <b style='color:#dce8f5;'>Tail event</b> (5% chance): 3–8% spot move — tests hedge protection<br>
            • Compares <b style='color:#ff4d6d;'>Naked straddle</b> vs <b style='color:#00e5a0;'>Hedged straddle (2× lots)</b><br>
            • Hedge cost deducted: far OTM CE+PE at ₹1–4 each<br>
            • Change seed to test different random samples
        </div>
    </div>
    """, unsafe_allow_html=True)
