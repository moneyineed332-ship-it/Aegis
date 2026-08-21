# AEGIS AI Quant - ICT/SMC Forex Trading Bot

Bot de trading automatisé ICT/SMC pour Forex (EUR/USD, GBP/USD, XAU/USD) avec gestion de risque centralisée et backtesting complet.

## 📋 Table des Matières

- [Vue d'ensemble](#vue-densemble)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Démarrage Rapide](#démarrage-rapide)
- [Modules ICT/SMC](#modules-ictsmc)
- [Tests](#tests)
- [API Dashboard](#api-dashboard)
- [Backtesting](#backtesting)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Vue d'ensemble

AEGIS AI Quant est un bot de trading ICT/SMC professionnel conçu pour:

- **Instruments**: EUR/USD, GBP/USD, XAU/USD
- **Capital Initial**: 50€
- **Timeframes**: H4/H1 (contexte), M15 (setup), M5 (confirmation)
- **Gestion de Risque**: Centralisée, anti-martingale, anti-revenge trading
- **Détection ICT/SMC**: Structure de marché, liquidité, FVG, Order Blocks
- **Backtesting**: Statistiques complètes, out-of-sample, forward testing

### Principe Fondamental

> « Le bot ne doit jamais chercher à gagner à tout prix. Il doit d'abord chercher à ne pas perdre excessivement. »

---

## 🏗️ Architecture

```
AEGIS AI Quant/
├── backend/
│   ├── app/
│   │   ├── ict_config.py           # Configuration instruments
│   │   ├── forex_indicators.py     # Calculs Forex spécifiques
│   │   ├── ict_risk_manager.py     # Risk Manager centralisé
│   │   ├── position_manager.py     # 4 modes de gestion de position
│   │   ├── trade_journal.py        # Journal des trades
│   │   ├── ict_backtester.py       # Moteur de backtesting
│   │   ├── indicators.py           # ICT/SMC indicators
│   │   ├── mt5_connector.py        # Connecteur MT5
│   │   ├── market_data.py          # Données de marché
│   │   ├── storage.py              # Persistance SQLite
│   │   ├── presets.py              # Presets de configuration
│   │   └── routers/
│   │       └── ict_dashboard.py    # API REST Dashboard
│   ├── test_ict_validation.py      # Validation des modules
│   ├── test_integration.py          # Test d'intégration
│   ├── run_simulated_backtest.py   # Backtesting simulé
│   └── QUICK_START.md              # Guide de démarrage
├── src/                            # Frontend React
└── README.md                       # Cette documentation
```

### Flux de Données

```
MT5 Data → Market Data → ICT Indicators → Risk Manager → Position Manager → Trade Journal
                                                                   ↓
                                                            Dashboard API
```

---

## 📦 Installation

### Prérequis

- Python 3.10+
- MetaTrader 5 (pour données réelles)
- FastAPI, Uvicorn
- SQLite (inclu avec Python)

### Étapes d'Installation

1. **Cloner le projet**
```bash
cd E:\web_app\projrt\AEGIS AI
```

2. **Installer les dépendances Python**
```bash
cd backend
pip install -r requirements.txt
```

3. **Configuration MT5 (optionnel)**
```bash
# Editer .env.example et renommer en .env
cp .env.example .env
```

Variables requises dans `.env`:
```env
MT5_LOGIN=your_mt5_login
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_mt5_server
```

---

## ⚙️ Configuration

### Instruments Configurés

#### EUR/USD
- Pip value: 0.0001
- Contract size: 100,000
- Risk per trade: 0.5%
- Min RR: 1.5, Target RR: 2.0
- Max trades/session: 2
- Sessions: London, New York, Overlap

#### GBP/USD
- Pip value: 0.0001
- Contract size: 100,000
- Risk per trade: 0.5%
- Min RR: 1.5, Target RR: 2.0
- Max trades/session: 2
- Volatilité plus élevée

#### XAU/USD (Gold)
- Pip value: 0.01
- Contract size: 100
- Risk per trade: 0.5%
- Min RR: 1.5, Target RR: 2.0
- Max trades/session: 1 (conservateur)
- Volatilité très élevée

### Presets de Configuration

Disponibles dans `app/presets.py`:

- **Conservative**: 0.3% risque, 2:1 min RR, très sélectif
- **Moderate**: 0.5% risque, 1.5:1 min RR, équilibré (recommandé)
- **Aggressive**: 1.0% risque, 1.2:1 min RR, plus de trades
- **Scalping**: 0.2% risque, trades fréquents, timeframes courts
- **Gold Conservative**: Spécifique XAU/USD

---

## 🚀 Démarrage Rapide

### 1. Validation des Modules

```bash
cd backend
python test_ict_validation.py
```

Résultat attendu:
```
SUMMARY: 8/8 tests passed
[OK] All ICT/SMC modules validated successfully!
```

### 2. Test d'Intégration

```bash
python test_integration.py
```

Résultat attendu:
```
INTEGRATION TEST COMPLETE - ALL TESTS PASSED
The ICT/SMC system is fully operational!
```

### 3. Backtesting Simulé

```bash
python run_simulated_backtest.py --instrument EURUSD
python run_simulated_backtest.py --instrument ALL
```

### 4. Démarrer le Serveur Backend

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Accéder à l'API:
- Dashboard: http://localhost:8000/api/ict/dashboard/summary
- Documentation: http://localhost:8000/docs

---

## 🔧 Modules ICT/SMC

### 1. ICT Config (`ict_config.py`)

Configuration centralisée pour tous les instruments.

**Fonctions principales**:
- `get_instrument_config(instrument)` - Récupérer configuration
- `calculate_position_size()` - Calcul taille de position
- `calculate_rr_ratio()` - Calcul ratio Risk/Reward
- `validate_rr_ratio()` - Validation RR ratio

### 2. Forex Indicators (`forex_indicators.py`)

Calculs spécifiques Forex.

**Fonctions principales**:
- `get_pip_value()` - Valeur pip par instrument
- `price_to_pips_forex()` - Conversion prix → pips
- `calculate_forex_position_size()` - Calcul lots
- `forex_atr()` - ATR Forex spécifique

### 3. ICT Risk Manager (`ict_risk_manager.py`)

Gestion de risque centralisée - **ne peut être contourné**.

**Validations**:
- Limite de risque par trade
- Drawdown journalier et total
- Pertes consécutives maximum
- Nombre de trades par session
- Positions simultanées maximum
- Ratio Risk/Reward minimum
- Validation placement SL
- Filtres session, news, volatilité
- Protection anti-martingale
- Protection anti-revenge trading

**Fonctions principales**:
- `check_all_limits()` - Validation complète avant trade
- `register_trade_entry()` - Enregistrement ouverture
- `register_trade_exit()` - Enregistrement fermeture
- `lock_position_size()` - Verrouillage taille après pertes

### 4. Position Manager (`position_manager.py`)

4 modes de gestion de position:

- **Mode A (fixed_tp)**: TP fixe standard
- **Mode B (partial)**: Fermeture partielle à 1R
- **Mode C (breakeven)**: Déplacement SL après progression
- **Mode D (trailing_structural)**: SL suit structure du marché

**Fonctions principales**:
- `open_position()` - Ouverture position
- `close_position()` - Fermeture position
- `update_position()` - Mise à jour (SL/TP, trailing)
- `check_sl_tp_hit()` - Vérification SL/TP touchés

### 5. Trade Journal (`trade_journal.py`)

Journal conforme au cahier des charges.

**Format**: "Date | Instrument | Direction | Setup | Timeframe | Entrée | SL | TP | Risque | Résultat | R/R | Drawdown"

**Fonctions principales**:
- `add_trade_entry()` - Ajouter trade
- `add_rejected_trade()` - Ajouter trade rejeté
- `get_statistics()` - Statistiques
- `export_to_csv()` - Export CSV
- `export_to_json()` - Export JSON
- `get_cahier_format_lines()` - Format cahier des charges

### 6. ICT Backtester (`ict_backtester.py`)

Moteur de backtesting complet.

**Phases**:
- In-sample: Données historiques
- Out-of-sample: Validation sur période différente
- Forward testing: Simulation en temps réel

**Statistiques**:
- Total trades, win rate
- Average R-multiple, expectancy
- Maximum drawdown
- Profit factor, Sharpe ratio
- Distribution des trades
- Breakdown par instrument/timeframe/setup

### 7. Indicators (`indicators.py`)

Détection ICT/SMC:

- **Market Structure**: HH, HL, LH, LL, BOS, CHoCH
- **Liquidity Zones**: Equal Highs/Lows, sweeps
- **Order Blocks**: Bullish/Bearish avec fill status
- **Fair Value Gaps**: Bullish/Bearish avec fill status
- **Confluence Scoring**: Score de confluence pour les setups

---

## 🧪 Tests

### Validation des Modules

```bash
python test_ict_validation.py
```

Tests tous les modules ICT/SMC:
- ICT Config
- Forex Indicators
- ICT Risk Manager
- Position Manager
- Trade Journal
- ICT Backtester
- ICT Dashboard Router
- Enhanced Indicators

### Test d'Intégration

```bash
python test_integration.py
```

Test l'intégration de tous les modules:
- Configuration instruments
- Risk Manager
- Position Manager
- Trade Journal
- Indicateurs ICT/SMC
- Exports CSV/JSON
- Format cahier des charges

### Backtesting Simulé

```bash
# Single instrument
python run_simulated_backtest.py --instrument EURUSD

# All instruments
python run_simulated_backtest.py --instrument ALL
```

Génère des données OHLCV simulées et exécute un backtest complet.

---

## 📊 API Dashboard

### Endpoints Principaux

#### Capital Metrics
```
GET /api/ict/dashboard/capital
```
Retourne:
- Initial capital
- Current capital
- Profit/Loss (valeur et %)
- Drawdown (valeur et %)

#### Market Metrics
```
GET /api/ict/dashboard/market/{instrument}
```
Retourne:
- Instrument, current price
- Trend (bullish/bearish/neutral)
- Structure (HH, HL, LH, LL, BOS, CHoCH)
- Liquidity zones, sweeps
- FVG, Order Blocks
- Current signal et strength

#### Risk Metrics
```
GET /api/ict/dashboard/risk
```
Retourne:
- Next-trade risk (valeur et %)
- Daily loss (valeur et %)
- Drawdown (valeur et %)
- Trades today, consecutive losses
- Open positions, max trades remaining
- Can trade status + blocking reasons

#### Trade Journal
```
GET /api/ict/dashboard/journal
GET /api/ict/dashboard/journal/statistics
GET /api/ict/dashboard/journal/export?format=csv
GET /api/ict/dashboard/journal/cahier-format
```

#### Positions
```
GET /api/ict/dashboard/positions
GET /api/ict/dashboard/positions/{position_id}
```

#### Summary
```
GET /api/ict/dashboard/summary
```
Résumé complet: capital, market, risk, positions.

### Démarrage du Serveur

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Accéder à:
- API: http://localhost:8000/api/ict/dashboard/summary
- Documentation Swagger: http://localhost:8000/docs
- Documentation ReDoc: http://localhost:8000/redoc

---

## 📈 Backtesting

### Avec Données Simulées

```bash
python run_simulated_backtest.py --instrument EURUSD
```

### Avec Données MT5 (requiert MT5 installé)

1. Connecter MT5:
```python
from app.mt5_connector import MT5Connector
connector = MT5Connector()
connector.connect()
```

2. Récupérer données:
```python
candles = connector.get_candles("EURUSD", "M15", 1000)
```

3. Exécuter backtest:
```python
from app.ict_backtester import IctBacktester
backtester = IctBacktester(initial_capital=50.0)
report = backtester.run_backtest(
    instrument="EURUSD",
    candles=candles,
    start_date=start_date,
    end_date=end_date,
    phase=BacktestPhase.IN_SAMPLE
)
```

### Analyse des Résultats

Le backtester génère:
- **Statistiques**: Win rate, expectancy, drawdown, profit factor
- **Distribution**: Distribution des trades par taille
- **Breakdown**: Par instrument, timeframe, setup
- **Comparison**: In-sample vs out-of-sample
- **Recommandation**: Validé ou caution

---

## 🔍 Troubleshooting

### Erreur: "cannot import name 'TradeRecord'"

**Cause**: Import circulaire entre modules

**Solution**: Les modules utilisent des imports optionnels avec fallback. Vérifiez que les modules sont dans le bon dossier.

### Erreur: "can't compare offset-naive and offset-aware times"

**Cause**: Problème de timezone dans session_filter.py

**Solution**: Le problème a été corrigé. Assurez-vous d'utiliser la version la plus récente.

### Erreur: "Position size trop petite"

**Cause**: Capital trop faible pour calcul de position valide

**Solution**: Augmenter le capital initial dans les tests (ex: 1000€ au lieu de 50€)

### MT5 Non Connecté

**Cause**: MT5 non installé ou credentials incorrects

**Solution**:
1. Vérifier que MT5 est installé
2. Vérifier credentials dans `.env`
3. Tester avec `python test_mt5_connection.py`

### Module Validation Failed

**Cause**: Dépendances manquantes

**Solution**:
```bash
pip install -r requirements.txt
```

### API Endpoint Not Found

**Cause**: Router non inclus dans main.py

**Solution**: Vérifier que `app.include_router(ict_dashboard_router.router)` est dans `main.py`

---

## 📝 Cahier des Charges Conformité

### §7 - Gestion du Risque
- ✅ Risk Manager centralisé (contournement impossible)
- ✅ Anti-martingale enforcement
- ✅ Anti-revenge trading enforcement
- ✅ Pas d'augmentation automatique après pertes

### §18 - Validation Risque
- ✅ 12 validations obligatoires implémentées
- ✅ Limites par instrument (XAU/USD conservateur)
- ✅ Filtres session, news, volatilité

### §20 - Journal des Trades
- ✅ Format strict cahier des charges
- ✅ Confluence reasons, rejection reasons
- ✅ Export CSV/JSON

### §21 - Statistiques Backtesting
- ✅ Métriques complètes (win rate, expectancy, drawdown, etc.)
- ✅ Validation out-of-sample
- ✅ Anti-over-optimization

---

## 🤝 Contribution

Le projet est conçu pour être modulaire et extensible. Pour contribuer:

1. Respecter les conventions de code existantes
2. Ajouter des tests pour nouvelles fonctionnalités
3. Mettre à jour la documentation
4. Maintenir la conformité au cahier des charges

---

## 📄 Licence

Projet propriétaire - Tous droits réservés.

---

## 📞 Support

Pour le support technique:
- Vérifier la section Troubleshooting
- Consulter QUICK_START.md
- Exécuter les tests de validation

---

## 🎯 Prochaines Étapes

1. **Backtesting avec données MT5 réelles**
2. **Validation de performance par instrument**
3. **Forward testing en environnement virtuel**
4. **Adaptation frontend React**
5. **Tests de performance et robustesse**

---

**Date de création**: 2025-01-XX  
**Version**: 1.0  
**Statut**: Opérationnel - Prêt pour backtesting et validation
