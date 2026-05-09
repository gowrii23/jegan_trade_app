"""
utils/kite_engine.py
Core Zerodha Kite Connect interface for Jegan's Straddle Strategy
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import math
import json
import os

# ── Try importing kiteconnect (graceful fallback to paper mode) ──
try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════
# CONFIG MANAGER
# ═══════════════════════════════════════════════════════════════

CONFIG_FILE = "config/kite_config.json"

def load_config() -> dict:
    """Load saved Kite config from disk."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "api_key": "",
        "api_secret": "",
        "access_token": "",
        "trade_mode": "paper",       # paper | live
        "capital": 1000000,          # ₹10L default
        "target_per_lot": 600,       # Jegan's target
        "hedge_budget_per_lot": 4,   # max ₹4 for OTM hedge
        "stop_loss_pct": 1.5,        # portfolio SL in %
        "instruments": ["NIFTY", "BANKNIFTY"],
        "auto_hedge": True,
    }

def save_config(cfg: dict):
    os.makedirs("config", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def get_config() -> dict:
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    return st.session_state.config


# ═══════════════════════════════════════════════════════════════
# KITE CONNECT WRAPPER
# ═══════════════════════════════════════════════════════════════

class KiteEngine:
    """Wraps KiteConnect with paper-trade fallback."""

    def __init__(self, api_key: str, api_secret: str, access_token: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.kite = None
        self.paper_mode = not KITE_AVAILABLE

        if KITE_AVAILABLE and api_key:
            self.kite = KiteConnect(api_key=api_key)
            if access_token:
                self.kite.set_access_token(access_token)

    def get_login_url(self) -> str:
        if self.kite:
            return self.kite.login_url()
        return "https://kite.zerodha.com/connect/login?api_key=YOUR_KEY"

    def generate_session(self, request_token: str) -> str:
        """Exchange request token for access token."""
        if self.kite:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            return self.access_token
        return "PAPER_TOKEN_" + request_token[:8]

    def get_profile(self) -> dict:
        if self.kite and not self.paper_mode:
            return self.kite.profile()
        return {"user_name": "Paper Trader", "email": "paper@demo.com", "user_id": "DEMO01"}

    def get_quote(self, instruments: list) -> dict:
        """Get LTP/quote for list of instruments like ['NSE:NIFTY 50']"""
        if self.kite and self.access_token and not self.paper_mode:
            return self.kite.quote(instruments)
        # Synthetic paper quotes
        base = {"NSE:NIFTY 50": 24350, "NSE:NIFTY BANK": 52800}
        result = {}
        for inst in instruments:
            spot = base.get(inst, 24350)
            noise = np.random.normal(0, spot * 0.001)
            result[inst] = {
                "last_price": round(spot + noise, 2),
                "change": round(np.random.normal(0, 0.3), 2),
                "volume": int(np.random.uniform(1e6, 5e6)),
            }
        return result

    def get_option_chain(self, symbol: str, expiry: date) -> pd.DataFrame:
        """Fetch live option chain or generate synthetic one."""
        if self.kite and self.access_token and not self.paper_mode:
            return self._fetch_live_chain(symbol, expiry)
        return self._synthetic_chain(symbol, expiry)

    def _fetch_live_chain(self, symbol: str, expiry: date) -> pd.DataFrame:
        """Live option chain from Kite instruments + quotes."""
        try:
            instruments = self.kite.instruments("NFO")
            df = pd.DataFrame(instruments)
            df = df[
                (df["name"] == symbol) &
                (df["instrument_type"].isin(["CE", "PE"])) &
                (df["expiry"] == expiry)
            ].copy()
            if df.empty:
                return self._synthetic_chain(symbol, expiry)

            trading_symbols = df["tradingsymbol"].tolist()
            # Batch quotes (Kite allows 500/req)
            batch = [f"NFO:{ts}" for ts in trading_symbols[:500]]
            quotes = self.kite.quote(batch)
            df["ltp"] = df["tradingsymbol"].apply(
                lambda ts: quotes.get(f"NFO:{ts}", {}).get("last_price", 0)
            )
            df["oi"] = df["tradingsymbol"].apply(
                lambda ts: quotes.get(f"NFO:{ts}", {}).get("oi", 0)
            )
            return df[["strike", "instrument_type", "tradingsymbol", "ltp", "oi", "expiry"]].sort_values("strike")
        except Exception as e:
            st.warning(f"Live chain fetch failed: {e}. Using synthetic.")
            return self._synthetic_chain(symbol, expiry)

    def _synthetic_chain(self, symbol: str, expiry: date) -> pd.DataFrame:
        """Generate realistic synthetic option chain."""
        spots = {"NIFTY": 24350, "BANKNIFTY": 52800, "SENSEX": 80200}
        spot = spots.get(symbol, 24350)
        lot_sizes = {"NIFTY": 25, "BANKNIFTY": 15, "SENSEX": 10}
        lot = lot_sizes.get(symbol, 25)
        strike_gap = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}.get(symbol, 50)

        # Black-Scholes simplified
        T = max((expiry - date.today()).days / 365, 0.001)
        iv_base = 0.14 + np.random.normal(0, 0.01)

        def bs_price(S, K, T, sigma, opt_type):
            d1 = (math.log(S / K) + (0.065 + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            from scipy.stats import norm
            if opt_type == "CE":
                return S * norm.cdf(d1) - K * math.exp(-0.065 * T) * norm.cdf(d2)
            else:
                return K * math.exp(-0.065 * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        try:
            from scipy.stats import norm
            use_bs = True
        except ImportError:
            use_bs = False

        atm = round(spot / strike_gap) * strike_gap
        strikes = [atm + i * strike_gap for i in range(-15, 16)]

        rows = []
        for K in strikes:
            moneyness = abs(K - spot) / spot
            iv = iv_base + moneyness * 0.8  # smile

            if use_bs:
                ce_ltp = max(bs_price(spot, K, T, iv, "CE"), 0.05)
                pe_ltp = max(bs_price(spot, K, T, iv, "PE"), 0.05)
            else:
                intrinsic_ce = max(spot - K, 0)
                intrinsic_pe = max(K - spot, 0)
                time_val = spot * iv * math.sqrt(T) * 0.4
                ce_ltp = max(intrinsic_ce + time_val * math.exp(-moneyness * 3), 0.05)
                pe_ltp = max(intrinsic_pe + time_val * math.exp(-moneyness * 3), 0.05)

            # OI realistic
            oi_ce = int(np.random.lognormal(12, 1) * (1 + max(0, (K - spot) / spot * 5)))
            oi_pe = int(np.random.lognormal(12, 1) * (1 + max(0, (spot - K) / spot * 5)))

            exp_str = expiry.strftime("%d%b%y").upper()
            ce_sym = f"{symbol}{exp_str}{int(K)}CE"
            pe_sym = f"{symbol}{exp_str}{int(K)}PE"

            rows.append({"strike": K, "instrument_type": "CE", "tradingsymbol": ce_sym,
                         "ltp": round(ce_ltp, 2), "oi": oi_ce, "expiry": expiry, "iv": round(iv * 100, 1), "lot_size": lot})
            rows.append({"strike": K, "instrument_type": "PE", "tradingsymbol": pe_sym,
                         "ltp": round(pe_ltp, 2), "oi": oi_pe, "expiry": expiry, "iv": round(iv * 100, 1), "lot_size": lot})

        return pd.DataFrame(rows).sort_values(["strike", "instrument_type"])

    def get_margins(self, orders: list) -> dict:
        """Get margin for a basket of orders."""
        if self.kite and self.access_token and not self.paper_mode:
            try:
                return self.kite.basket_order_margins(orders)
            except:
                pass
        # Estimate synthetic margins
        return self._estimate_margin(orders)

    def _estimate_margin(self, orders: list) -> dict:
        total = 0
        for o in orders:
            if o.get("transaction_type") == "SELL":
                total += 150000  # ~1.5L per lot with hedge
            else:
                total += o.get("price", 0) * o.get("quantity", 0)
        return {"total": total, "span": total * 0.7, "exposure": total * 0.3}

    def place_order(self, symbol: str, exchange: str, transaction_type: str,
                    quantity: int, price: float, order_type: str = "MARKET",
                    product: str = "NRML", tag: str = "jegan_straddle") -> dict:
        """Place order — live or paper."""
        order_id = f"PAPER_{datetime.now().strftime('%H%M%S%f')}"

        if not self.paper_mode and self.kite and self.access_token:
            try:
                order_id = self.kite.place_order(
                    variety=KiteConnect.VARIETY_REGULAR,
                    exchange=exchange,
                    tradingsymbol=symbol,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    product=product,
                    order_type=order_type,
                    price=price if order_type == "LIMIT" else None,
                    tag=tag,
                )
                return {"order_id": order_id, "status": "LIVE_PLACED", "symbol": symbol}
            except Exception as e:
                return {"order_id": None, "status": "FAILED", "error": str(e)}

        # Paper trade log
        paper_order = {
            "order_id": order_id,
            "status": "PAPER_COMPLETE",
            "symbol": symbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "price": price,
            "timestamp": datetime.now().isoformat(),
            "tag": tag,
        }
        if "trade_log" not in st.session_state:
            st.session_state.trade_log = []
        st.session_state.trade_log.append(paper_order)
        return paper_order

    def get_positions(self) -> pd.DataFrame:
        if self.kite and self.access_token and not self.paper_mode:
            try:
                pos = self.kite.positions()
                return pd.DataFrame(pos.get("net", []))
            except:
                pass
        return self._paper_positions()

    def _paper_positions(self) -> pd.DataFrame:
        if not st.session_state.get("active_positions"):
            return pd.DataFrame()
        return pd.DataFrame(st.session_state.active_positions)

    def get_orders(self) -> pd.DataFrame:
        if self.kite and self.access_token and not self.paper_mode:
            try:
                return pd.DataFrame(self.kite.orders())
            except:
                pass
        return pd.DataFrame(st.session_state.get("trade_log", []))


# ═══════════════════════════════════════════════════════════════
# STRATEGY ENGINE — Strike Selector
# ═══════════════════════════════════════════════════════════════

class StraddleStrategy:
    """
    Jegan's Leveraged Straddle:
    - Sell ATM Straddle (CE + PE)
    - Buy far OTM hedge CE + PE (within budget ₹1–4)
    - Margin halves → 2x lots on same capital
    """

    MARGIN_NAKED = 300_000   # ₹3L per lot (unhedged)
    MARGIN_HEDGED = 150_000  # ₹1.5L per lot (hedged)
    TARGET_PER_LOT = 600     # Jegan's daily target

    def __init__(self, capital: int, hedge_budget: float = 4.0):
        self.capital = capital
        self.hedge_budget = hedge_budget

    @property
    def lots_naked(self) -> int:
        return max(int(self.capital // self.MARGIN_NAKED), 0)

    @property
    def lots_hedged(self) -> int:
        return max(int(self.capital // self.MARGIN_HEDGED), 0)

    def find_atm_strike(self, spot: float, chain: pd.DataFrame) -> dict:
        """Find ATM CE + PE closest to spot."""
        strikes = chain["strike"].unique()
        atm = min(strikes, key=lambda x: abs(x - spot))

        ce = chain[(chain["strike"] == atm) & (chain["instrument_type"] == "CE")]
        pe = chain[(chain["strike"] == atm) & (chain["instrument_type"] == "PE")]

        ce_ltp = ce["ltp"].values[0] if not ce.empty else 0
        pe_ltp = pe["ltp"].values[0] if not pe.empty else 0
        ce_sym = ce["tradingsymbol"].values[0] if not ce.empty else ""
        pe_sym = pe["tradingsymbol"].values[0] if not pe.empty else ""

        return {
            "strike": atm,
            "ce_ltp": ce_ltp,
            "pe_ltp": pe_ltp,
            "ce_symbol": ce_sym,
            "pe_symbol": pe_sym,
            "total_premium": round(ce_ltp + pe_ltp, 2),
            "iv": ce["iv"].values[0] if not ce.empty and "iv" in ce.columns else 0,
        }

    def find_hedge_strikes(self, spot: float, chain: pd.DataFrame,
                           atm_strike: float) -> dict:
        """
        Find cheapest OTM CE + PE within hedge_budget per unit.
        Rule: buy next OTM that is ≤ hedge_budget AND has decent OI (>10k).
        """
        ce_candidates = chain[
            (chain["instrument_type"] == "CE") &
            (chain["strike"] > atm_strike) &
            (chain["ltp"] <= self.hedge_budget) &
            (chain["ltp"] >= 0.5) &
            (chain["oi"] > 5000)
        ].sort_values("strike")

        pe_candidates = chain[
            (chain["instrument_type"] == "PE") &
            (chain["strike"] < atm_strike) &
            (chain["ltp"] <= self.hedge_budget) &
            (chain["ltp"] >= 0.5) &
            (chain["oi"] > 5000)
        ].sort_values("strike", ascending=False)

        def pick_best(candidates):
            if candidates.empty:
                return None
            # Prefer highest OI within budget
            return candidates.sort_values("oi", ascending=False).iloc[0]

        ce_hedge = pick_best(ce_candidates)
        pe_hedge = pick_best(pe_candidates)

        result = {}
        if ce_hedge is not None:
            result["ce_hedge"] = {
                "strike": ce_hedge["strike"],
                "ltp": ce_hedge["ltp"],
                "symbol": ce_hedge["tradingsymbol"],
                "oi": ce_hedge["oi"],
                "distance_pct": round((ce_hedge["strike"] - spot) / spot * 100, 2),
            }
        if pe_hedge is not None:
            result["pe_hedge"] = {
                "strike": pe_hedge["strike"],
                "ltp": pe_hedge["ltp"],
                "symbol": pe_hedge["tradingsymbol"],
                "oi": pe_hedge["oi"],
                "distance_pct": round((spot - pe_hedge["strike"]) / spot * 100, 2),
            }
        return result

    def build_strategy_legs(self, spot: float, chain: pd.DataFrame,
                             symbol: str, expiry: date, mode: str = "hedge") -> list:
        """
        Returns list of legs with action, strike, symbol, ltp, quantity.
        mode: 'naked' | 'hedge'
        """
        lot_size = chain["lot_size"].iloc[0] if "lot_size" in chain.columns else 25
        lots = self.lots_hedged if mode == "hedge" else self.lots_naked
        qty = lots * lot_size

        atm = self.find_atm_strike(spot, chain)
        legs = [
            {
                "action": "SELL", "type": "CE", "strike": atm["strike"],
                "symbol": atm["ce_symbol"], "ltp": atm["ce_ltp"],
                "quantity": qty, "lots": lots, "lot_size": lot_size,
                "role": "ATM SELL",
            },
            {
                "action": "SELL", "type": "PE", "strike": atm["strike"],
                "symbol": atm["pe_symbol"], "ltp": atm["pe_ltp"],
                "quantity": qty, "lots": lots, "lot_size": lot_size,
                "role": "ATM SELL",
            },
        ]

        if mode == "hedge":
            hedges = self.find_hedge_strikes(spot, chain, atm["strike"])
            if "ce_hedge" in hedges:
                h = hedges["ce_hedge"]
                legs.append({
                    "action": "BUY", "type": "CE", "strike": h["strike"],
                    "symbol": h["symbol"], "ltp": h["ltp"],
                    "quantity": qty, "lots": lots, "lot_size": lot_size,
                    "role": f"OTM HEDGE (+{h['distance_pct']}%)",
                    "distance_pct": h["distance_pct"],
                })
            if "pe_hedge" in hedges:
                h = hedges["pe_hedge"]
                legs.append({
                    "action": "BUY", "type": "PE", "strike": h["strike"],
                    "symbol": h["symbol"], "ltp": h["ltp"],
                    "quantity": qty, "lots": lots, "lot_size": lot_size,
                    "role": f"OTM HEDGE (-{h['distance_pct']}%)",
                    "distance_pct": h["distance_pct"],
                })

        # Compute net credit
        net_credit = 0
        for leg in legs:
            mult = -1 if leg["action"] == "BUY" else 1
            net_credit += mult * leg["ltp"] * leg["quantity"]

        for leg in legs:
            leg["net_credit_total"] = round(net_credit, 2)

        return legs

    def pnl_at_expiry(self, spot_entry: float, spot_expiry: float,
                      legs: list) -> dict:
        """Calculate P&L at expiry for a set of legs."""
        total_pnl = 0
        leg_pnls = []
        for leg in legs:
            K = leg["strike"]
            qty = leg["quantity"]
            ltp = leg["ltp"]

            if leg["type"] == "CE":
                intrinsic = max(spot_expiry - K, 0)
            else:
                intrinsic = max(K - spot_expiry, 0)

            if leg["action"] == "SELL":
                leg_pnl = (ltp - intrinsic) * qty
            else:  # BUY
                leg_pnl = (intrinsic - ltp) * qty

            total_pnl += leg_pnl
            leg_pnls.append({**leg, "pnl": round(leg_pnl, 2), "intrinsic": round(intrinsic, 2)})

        return {"total_pnl": round(total_pnl, 2), "leg_pnls": leg_pnls}


# ═══════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════

def run_backtest(capital: int, year: int, n_samples: int,
                 hedge_budget: float, random_seed: int) -> pd.DataFrame:
    """
    Monte Carlo backtest over n_samples random expiries from year.
    Returns DataFrame with results for both naked and hedged.
    """
    np.random.seed(random_seed)
    strategy = StraddleStrategy(capital, hedge_budget)

    base_spot = 24000
    records = []

    for i in range(n_samples):
        iv = np.random.uniform(0.12, 0.20)
        T = 1 / 252  # 1 day expiry
        spot = base_spot * (1 + np.random.normal(0, 0.015))

        # Premium ~ IV-based
        atm_premium = spot * iv * np.sqrt(T) * np.random.uniform(0.8, 1.2) * 2
        hedge_cost = np.random.uniform(0.5, hedge_budget) * 2 * 25  # 2 legs × lot

        # Move at expiry
        is_tail = np.random.random() < 0.05
        if is_tail:
            move_pct = np.random.choice([-1, 1]) * np.random.uniform(0.03, 0.08)
        else:
            move_pct = np.random.normal(0, 0.012)
        spot_expiry = spot * (1 + move_pct)
        intrinsic = abs(spot_expiry - spot) * 25  # per lot

        # Naked P&L
        target = min(atm_premium, strategy.TARGET_PER_LOT) * strategy.lots_naked
        if is_tail:
            naked_pnl = -intrinsic * strategy.lots_naked * 1.5
        else:
            naked_pnl = target - intrinsic * 0.3 * strategy.lots_naked

        # Hedged P&L
        target_h = min(atm_premium, strategy.TARGET_PER_LOT) * strategy.lots_hedged
        hedge_total = hedge_cost * strategy.lots_hedged
        if is_tail:
            hedge_recovery = intrinsic * 0.65 * strategy.lots_hedged
            hedged_pnl = hedge_recovery - hedge_total - target_h * 0.3
        else:
            hedged_pnl = target_h - hedge_total - intrinsic * 0.15 * strategy.lots_hedged

        records.append({
            "sample": i + 1,
            "spot": round(spot),
            "spot_expiry": round(spot_expiry),
            "move_pct": round(move_pct * 100, 2),
            "iv_pct": round(iv * 100, 1),
            "atm_premium": round(atm_premium, 2),
            "is_tail_event": is_tail,
            "naked_lots": strategy.lots_naked,
            "hedged_lots": strategy.lots_hedged,
            "naked_pnl": round(naked_pnl),
            "hedged_pnl": round(hedged_pnl),
            "hedge_cost": round(hedge_total),
            "year": year,
            "seed": random_seed,
        })

    df = pd.DataFrame(records)
    return df


def backtest_summary(df: pd.DataFrame, capital: int) -> dict:
    return {
        "n": len(df),
        "naked_total": df["naked_pnl"].sum(),
        "hedged_total": df["hedged_pnl"].sum(),
        "naked_win_rate": (df["naked_pnl"] > 0).mean() * 100,
        "hedged_win_rate": (df["hedged_pnl"] > 0).mean() * 100,
        "naked_roi": df["naked_pnl"].sum() / capital * 100,
        "hedged_roi": df["hedged_pnl"].sum() / capital * 100,
        "naked_max_loss": df["naked_pnl"].min(),
        "hedged_max_loss": df["hedged_pnl"].min(),
        "tail_count": df["is_tail_event"].sum(),
        "avg_hedge_cost": df["hedge_cost"].mean(),
        "sharpe_naked": df["naked_pnl"].mean() / (df["naked_pnl"].std() + 1),
        "sharpe_hedged": df["hedged_pnl"].mean() / (df["hedged_pnl"].std() + 1),
    }
