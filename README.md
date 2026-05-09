# ⊕ Jegan's Leveraged Straddle System
### Zerodha Kite Connect · Streamlit · NSE Options Automation

---

## What This Does

Implements **Jegan's Hedged Straddle Strategy**:
- **SELL** ATM Call + ATM Put (collect premium)
- **BUY** far OTM Call + far OTM Put at ₹1–4 (hedge)
- This HALVES margin (₹3L → ₹1.5L), allowing **2× lots on same capital**
- Target: ₹600/lot/day → ₹1,200/day with 2× lots → ~33% ROI/year

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Kite Connect API Keys
1. Go to [developers.kite.trade](https://developers.kite.trade)
2. Create a new app
3. Note your **API Key** and **API Secret**
4. Set Redirect URL to `http://127.0.0.1:8501`

### 3. Run the app
```bash
streamlit run app.py
```

### 4. First-Time Auth
1. Go to **API Setup** page
2. Enter your API Key & Secret → Save
3. Click **Open Kite Login** → login at Zerodha
4. Copy `request_token` from URL after redirect
5. Click **Generate Session**

**OR** click **Quick Start (Paper Mode)** to test without real keys.

---

## App Pages

| Page | Purpose |
|------|---------|
| 🔑 API Setup | Configure Kite keys, paper/live mode, capital settings |
| 📊 Dashboard | Live spot prices, positions P&L, daily target tracker |
| 🎯 Strike Selector | **Core page** — exact strikes to BUY/SELL with payoff chart |
| 🔄 Backtest Engine | Monte Carlo backtest: naked vs hedged across random expiries |
| 📋 Positions | Active positions, order log, square-off controls |

---

## Strike Selector — How to Use

1. Select **NIFTY** or **BANKNIFTY**
2. Select current week's **expiry date**
3. Set **Hedge Budget** (₹1–4 recommended per Jegan)
4. Click **Fetch Option Chain & Compute Strikes**

You'll see a table like:

| ACTION | TYPE | STRIKE | SYMBOL | LTP | QUANTITY | ROLE |
|--------|------|--------|--------|-----|----------|------|
| 🔴 SELL | CE | 24350 | NIFTY...CE | ₹85.5 | 150 | ATM SELL |
| 🔴 SELL | PE | 24350 | NIFTY...PE | ₹82.3 | 150 | ATM SELL |
| 🟢 BUY  | CE | 24650 | NIFTY...CE | ₹3.2 | 150 | OTM HEDGE (+1.23%) |
| 🟢 BUY  | PE | 24050 | NIFTY...PE | ₹3.8 | 150 | OTM HEDGE (-1.23%) |

---

## Config File

Settings are saved to `config/kite_config.json`:

```json
{
  "api_key": "YOUR_KEY",
  "api_secret": "YOUR_SECRET",
  "access_token": "SESSION_TOKEN",
  "trade_mode": "paper",
  "capital": 1000000,
  "target_per_lot": 600,
  "hedge_budget_per_lot": 4.0,
  "stop_loss_pct": 1.5,
  "instruments": ["NIFTY", "BANKNIFTY"]
}
```

**Never commit this file to git** — add `config/` to `.gitignore`.

---

## Risk Disclaimer

This is for educational/paper trading purposes. Options trading involves significant risk.
Jegan's strategy involves selling options — losses can exceed premium collected without hedges.
Always test in paper mode before going live. Consult a SEBI-registered advisor.
