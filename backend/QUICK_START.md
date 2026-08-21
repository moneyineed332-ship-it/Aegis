# ICT/SMC Trading Bot - Quick Start Guide

Guide rapide pour démarrer avec le bot de trading ICT/SMC.

Pour une documentation complète, voir [README.md](../README.md).

---

## 🚀 Étapes Rapides

### 1. Validation des Modules

```bash
cd backend
python test_ict_validation.py
```

Résultat attendu: `8/8 tests passed`

### 2. Test d'Intégration

```bash
python test_integration.py
```

Résultat attendu: `INTEGRATION TEST COMPLETE - ALL TESTS PASSED`

### 3. Backtesting Simulé

```bash
# Test EUR/USD
python run_simulated_backtest.py --instrument EURUSD

# Test tous les instruments
python run_simulated_backtest.py --instrument ALL
```

### 4. Démarrer le Serveur Backend

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Accéder à l'API

- **Dashboard Summary**: http://localhost:8000/api/ict/dashboard/summary
- **Capital**: http://localhost:8000/api/ict/dashboard/capital
- **Risk**: http://localhost:8000/api/ict/dashboard/risk
- **Journal**: http://localhost:8000/api/ict/dashboard/journal
- **Documentation**: http://localhost:8000/docs

---

## 📊 Présets de Configuration

- **Conservative**: 0.3% risque, très sélectif
- **Moderate**: 0.5% risque, équilibré (recommandé)
- **Aggressive**: 1.0% risque, plus de trades
- **Scalping**: 0.2% risque, trades fréquents
- **Gold Conservative**: Spécifique XAU/USD

---

## 🎯 Instruments Configurés

- **EUR/USD**: 0.5% risque, 1.5:1 min RR, 2 trades/session
- **GBP/USD**: 0.5% risque, 1.5:1 min RR, 2 trades/session
- **XAU/USD**: 0.5% risque, 1.5:1 min RR, 1 trade/session (conservateur)

---

## 🔧 Modules ICT/SMC

- **ICT Config**: Configuration centralisée
- **Forex Indicators**: Calculs Forex spécifiques
- **ICT Risk Manager**: Gestion de risque centralisée
- **Position Manager**: 4 modes de gestion de position
- **Trade Journal**: Journal conforme cahier des charges
- **ICT Backtester**: Moteur de backtesting complet
- **Indicators**: Détection ICT/SMC (structure, liquidité, FVG, OB)

---

## 📝 Pour Plus d'Informations

Voir [README.md](../README.md) pour:
- Architecture détaillée
- Installation complète
- Configuration avancée
- API documentation
- Troubleshooting
- Cahier des charges conformité

---

**Note**: Ce système respecte le principe fondamental:
> « Le bot ne doit jamais chercher à gagner à tout prix. Il doit d'abord chercher à ne pas perdre excessivement. »
