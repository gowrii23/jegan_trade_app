# Native Android APK Upgrade Plan — Jegan Straddle Paper Trading App

## 1. Current Limitations (Streamlit App)
- **Not Mobile Native:** Built using Streamlit, which is designed for web/desktop.
- **No Direct APK:** Cannot be directly converted to a native Android APK.
- **Volatile State:** Relies on session state (data is lost after app restart).
- **No Local DB:** Lacks a local database for persistent storage.
- **Limited Analytics:** Missing comprehensive trade analytics.
- **Broker Dependency:** Heavily relies on Kite API (makes paper trading without it difficult).

## 2. Recommended Tech Stack
- **Frontend (Mobile App):** Flutter (Fast UI, works offline, lightweight, excellent charts, native APK).
- **Backend/Logic:** Dart service layer (local, no cloud needed initially).
- **Local Database:** SQLite (using `sqflite` package).
- **Market Data:** `yfinance` (free), NSE unofficial APIs (`nsepython`, `nselib`), or fallback cached data.
- **Charts:** `fl_chart` package.
- **State Management:** Riverpod or Provider.

## 3. Core Features to Add
### Paper Trading Engine
- Support for Buy CE/PE, Sell CE/PE, and Multi-leg straddle.
- PnL tracking, MTM calculation.
- Virtual capital, brokerage, and slippage simulation.
- Risk calculation.

### Local Database (SQLite Tables)
1. **`trades`**: `id`, `symbol`, `strike`, `option_type`, `side`, `qty`, `entry_price`, `exit_price`, `pnl`, `timestamp`, `status`
2. **`positions`**: `id`, `symbol`, `qty`, `avg_price`, `current_price`, `pnl`
3. **`portfolio`**: `capital`, `margin_used`, `realized_pnl`, `unrealized_pnl`

## 4. Mobile UI Screens
1. **Dashboard:** Total capital, Today's PnL, Unrealized PnL, Active positions, Win ratio, Margin used, Strategy health.
2. **Trade Screen:** Buttons for Buy/Sell CE/PE, Square Off, Auto Hedge.
3. **Analytics Screen:** Equity curve, Daily PnL, Monthly return, Win/Loss pie chart, Drawdown graph.
4. **Trade History:** Filter by date/strategy, Export CSV, Search trades.

## 5. Better Trading Logic & Strike Selection
- **Dynamic Entry:** VIX stable, opening range confirmed, theta favorable, premium > threshold, RR acceptable, neutral trend.
- **Dynamic Strikes:** Use delta, premium, IV percentile, or support/resistance instead of fixed ATM.
  - *Market Neutral:* Sell ATM CE/PE, Buy far OTM CE/PE as hedge.
- **Dynamic Stop Loss:** SL = Premium × Volatility Factor (e.g., wider SL if VIX is high).
- **Risk-Based Position Sizing:** `Position Size = (Capital × Risk %) / Stop Loss Amount`
- **Daily Loss Protection:** Stop all trades and disable entries if Daily loss > 3%.

## 6. Suggested Folder Structure (Flutter)
```text
lib/
 ├── main.dart
 ├── screens/
 │    ├── dashboard_screen.dart
 │    ├── trade_screen.dart
 │    ├── analytics_screen.dart
 │    └── history_screen.dart
 ├── models/
 │    ├── trade.dart
 │    ├── position.dart
 │    └── portfolio.dart
 ├── services/
 │    ├── market_service.dart
 │    ├── strategy_service.dart
 │    ├── db_service.dart
 │    └── pnl_service.dart
 ├── database/
 │    └── sqlite_helper.dart
 └── widgets/
      ├── pnl_card.dart
      ├── trade_tile.dart
      └── chart_widget.dart
```

## 7. Build Instructions (Flutter)
To generate the release APK once the code is implemented:
```bash
flutter build apk --release
```
Output will be located at: `build/app/outputs/flutter-apk/app-release.apk`

## 8. Rollout Strategy
- **Version 1:** Flutter app with SQLite, paper trading only (using `yfinance`).
- **Version 2:** Integrate broker APIs (Zerodha Kite, Upstox, AngelOne), real order execution, AI analytics, cloud sync.
- **Version 3:** Fully automated trading engine, ML-based strategy adaptation, advanced Greeks analytics.
