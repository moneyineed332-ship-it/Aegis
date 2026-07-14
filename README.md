
# AEGIS AI Quant

Socle MVP d'une plateforme de recherche crypto et de **paper trading**. Aucune clé d'exchange et aucune exécution réelle ne sont prises en charge à ce stade.

## Démarrer

Frontend : `npm install`, puis `npm run dev`.

API simulée : créez un environnement Python, installez `backend/requirements.txt`, puis exécutez `uvicorn app.main:app --app-dir backend --reload`.

Déploiement local conteneurisé : `docker compose up --build`. Le frontend est ensuite servi sur `http://localhost:5173` et l'API sur `http://localhost:8000`.

Compose démarre aussi PostgreSQL et Redis pour préparer la migration production. Le stockage applicatif actuel reste SQLite tant que la migration de la couche `storage` n'est pas réalisée.

Pour les tests API : `python -m pip install -r backend/requirements-dev.txt`.

L'API est disponible sur `http://localhost:8000` et sa documentation interactive sur `/docs`.
Le frontend utilise cette adresse par défaut ; pour la modifier, copiez `.env.example` vers `.env` et ajustez `VITE_API_URL`.

La configuration backend est centralisée dans `backend/.env.example`. Le mode doit rester `paper` ; AEGIS ne charge aucune clé exchange.

## Garde-fous MVP

- Mode paper trading uniquement.
- Limite par ordre et limite d'exposition totale appliquées par l'API.
- Ordres et positions persistés localement dans SQLite (`backend/data/aegis.db`).
- Cotations Spot publiques BTC/ETH/SOL collectées manuellement depuis Binance, sans clé API.
- Aucun secret, compte exchange ou ordre de marché réel.

## Périmètre livré

Le dashboard permet de rafraîchir les prix publics, charger l'historique OHLCV et lancer les validations walk-forward SMA ou Donchian. Les actions restent de la recherche quantitative et du paper trading : un résultat positif ne constitue pas une validation de production ni un conseil financier.

## Rafraîchir les cotations

Lorsque l'API est démarrée, envoyez une requête `POST` à `http://localhost:8000/api/v1/market-snapshots/refresh`.
Les derniers snapshots sont lisibles avec `GET /api/v1/market-snapshots`.

## Alimenter le premier backtest

Rafraîchissez des bougies via `POST /api/v1/ohlcv/refresh?symbol=BTCUSDT&interval=1h&limit=200`.
Les bougies persistées sont lisibles via `GET /api/v1/ohlcv?symbol=BTCUSDT&interval=1h`.

## Premier backtest

`POST /api/v1/backtests/sma-crossover` lance un croisement SMA long/flat sur les bougies déjà stockées. Il intègre frais, slippage, allocation maximale et produit rendement, drawdown, Sharpe, taux de réussite et nombre de trades. Les résultats et paramètres sont conservés dans SQLite.

Pour limiter le surapprentissage, chargez davantage d'historique avec `POST /api/v1/ohlcv/refresh-history?symbol=BTCUSDT&interval=1h&batches=4`, puis lancez `POST /api/v1/backtests/sma-crossover/walk-forward`. La sélection se fait sur 500 bougies d'entraînement et l'évaluation sur 200 bougies hors échantillon.

Le comparateur Donchian utilise les mêmes données et coûts : `POST /api/v1/backtests/donchian-breakout/walk-forward`. Il compare trois canaux de breakout long/flat avec un filtre de volatilité minimal.

Avant chaque backtest, AEGIS contrôle automatiquement l'intégrité OHLCV. Le rapport est aussi disponible via `GET /api/v1/data-quality/ohlcv?symbol=BTCUSDT&interval=1h`.

La synthèse de risque historique (VaR/CVaR 95 %) est disponible via `GET /api/v1/risk/summary?symbol=BTCUSDT&interval=1h`. Elle informe la recherche et ne remplace pas les stress tests de production.

`GET /api/v1/market-analysis?symbol=BTCUSDT&interval=1h` expose les SMA 20/50, momentum, volatilité, range et un régime explicable (`bull_trend`, `bear_trend`, `range`, `high_volatility`).

`POST /api/v1/decisions/recommendation` crée une recommandation de recherche auditée dans SQLite. Elle ne crée aucun ordre, même en mode paper trading.

## Supervision locale

`POST /api/v1/supervisor/emergency-stop` active un arrêt d'urgence persistant et bloque les nouveaux ordres paper. Seul `POST /api/v1/supervisor/resume` reprend manuellement le service. L'état et les alertes sont visibles via `GET /api/v1/supervisor`.
  
