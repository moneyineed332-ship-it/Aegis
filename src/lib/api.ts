export interface DashboardSnapshot {
  mode: "paper";
  capital: number;
  exposure: number;
  max_exposure: number;
  current_equity: number;
  realized_pnl: number;
  equity_curve: Array<{ time: string; equity: number }>;
  positions: Array<{
    symbol: string;
    quantity: number;
    average_price: number;
  }>;
  recent_backtests: Array<{
    id: number;
    strategy: string;
    symbol: string;
    interval: string;
    metrics: {
      total_return?: number;
      max_drawdown?: number;
      sharpe_ratio?: number;
      trade_count?: number;
      win_rate?: number;
      out_of_sample_metrics?: {
        total_return: number;
        max_drawdown: number;
        sharpe_ratio: number;
        trade_count: number;
        win_rate: number;
      };
    };
  }>;
  data_quality: { valid: boolean; candle_count: number; gap_count: number; invalid_candle_count: number };
  market_analysis: { regime: { regime: string; confidence: number }; features: { momentum_20: number; volatility_20: number; rsi_14: number; macd: number; macd_signal: number; atr_14: number; bollinger_upper: number; bollinger_middle: number; bollinger_lower: number } } | null;
  risk: { value_at_risk: number; conditional_value_at_risk: number; confidence: number; max_drawdown: number; max_drawdown_pct: number; volatility: number; annualized_volatility: number } | null;
  stress_test: { current_price: number; position_value: number; capital: number; worst_day_return: number; worst_week_return: number; worst_month_return: number; scenarios: Array<{ name: string; price_impact: number; portfolio_impact: number; description: string }> } | null;
  correlation: { symbols: string[]; matrix: Record<string, Record<string, number>>; avg_correlation: number | null; interpretation: string } | null;
  concentration: { total_exposure: number; herfindahl: number; max_concentration: number; position_count: number; positions: Array<{ symbol: string; value: number; weight: number }> } | null;
  supervisor: { status: string; kill_switch_active: boolean };
  alerts: Array<{ severity: string; message: string; created_at: string }>;
  coach: { reviewed_backtests: number; recommendations: Array<{ action: string; reason?: string }> };
  strategy_registry: Array<{ id: string; name: string; type: string; status: string }>;
  recent_decisions: Array<{ id: number; symbol: string; interval: string; created_at: string; decision: { recommendation?: { action?: string; strategy?: string; reason?: string } } }>;
  fear_greed: Array<{ value: number; classification: string; source: string; collected_at: string }>;
  funding_rates: Array<{ symbol: string; mark_price: number; index_price: number; funding_rate: number; next_funding_time: number; source: string; collected_at: string }>;
  open_interest: Array<{ symbol: string; open_interest: number; open_interest_usd: number; price: number; source: string; collected_at: string }>;
  memory: { total_episodes: number; strategies_used: Array<{ strategy: string; count: number; win_rate: number }>; avg_result: number | null; best_fingerprint: string | null };
  journal: { total_decisions: number; accuracy: number | null; avg_pnl: number | null; total_pnl: number | null; by_action: Record<string, { count: number; accuracy: number; avg_pnl: number | null }>; feedback: { message: string; grade: string; strengths: string[]; weaknesses: string[] } } | null;
}

export interface SupervisorStatus {
  status: "healthy" | "stopped";
  kill_switch_active: boolean;
  alerts: Array<{ severity: string; message: string; created_at: string }>;
}

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function getDashboard(): Promise<DashboardSnapshot> {
  const response = await fetch(`${apiBaseUrl}/api/v1/dashboard`);
  if (!response.ok) {
    throw new Error("AEGIS API unavailable");
  }
  return response.json() as Promise<DashboardSnapshot>;
}

export async function postApi<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { method: "POST" });
  if (!response.ok) throw new Error("AEGIS API request failed");
  return response.json() as Promise<T>;
}

export const refreshMarketData = () => postApi("/api/v1/market-snapshots/refresh");
export const refreshHistory = () => postApi("/api/v1/ohlcv/refresh-history?symbol=BTCUSDT&interval=1h&batches=4");
export const runSmaWalkForward = () => postApi("/api/v1/backtests/sma-crossover/walk-forward");
export const runDonchianWalkForward = () => postApi("/api/v1/backtests/donchian-breakout/walk-forward");
export const getSupervisor = async (): Promise<SupervisorStatus> => {
  const response = await fetch(`${apiBaseUrl}/api/v1/supervisor`);
  if (!response.ok) throw new Error("Supervisor unavailable");
  return response.json() as Promise<SupervisorStatus>;
};
export const activateEmergencyStop = () => postApi("/api/v1/supervisor/emergency-stop");
export const resumeSupervisor = () => postApi("/api/v1/supervisor/resume");
export const runMeanReversionWalkForward = () => postApi("/api/v1/backtests/mean-reversion/walk-forward");
export const runGridWalkForward = () => postApi("/api/v1/backtests/grid/walk-forward");
export const refreshFearGreed = () => postApi("/api/v1/fear-greed/refresh");
export const refreshFundingRates = (symbol: string = "BTCUSDT") => postApi(`/api/v1/funding-rates/refresh?symbol=${symbol}`);
export const refreshOpenInterest = (symbol: string = "BTCUSDT") => postApi(`/api/v1/open-interest/refresh?symbol=${symbol}`);

// Phase 4: Alerts
export interface Alert {
  type: string;
  severity: string;
  message: string;
  value?: number;
  threshold?: number;
  timestamp: string;
}
export const getAlertHistory = async (limit: number = 50): Promise<Alert[]> => {
  const response = await fetch(`${apiBaseUrl}/api/v1/alerts/history?limit=${limit}`);
  return response.json() as Promise<Alert[]>;
};
export const getAlertThresholds = async () => {
  const response = await fetch(`${apiBaseUrl}/api/v1/alerts/thresholds`);
  return response.json();
};
export const checkAlerts = () => postApi<{ alerts: Alert[] }>("/api/v1/alerts/check");

// Phase 4: Advanced Backtesting
export const runAdvancedWalkForward = (symbol: string = "BTCUSDT", nSplits: number = 3) =>
  postApi(`/api/v1/backtests/advanced/walk-forward?symbol=${symbol}&n_splits=${nSplits}`);
export const runMonteCarlo = (symbol: string = "BTCUSDT", nSimulations: number = 1000) =>
  postApi(`/api/v1/backtests/advanced/monte-carlo?symbol=${symbol}&n_simulations=${nSimulations}`);
export const runSensitivity = (symbol: string = "BTCUSDT", paramName: string = "fast_period") =>
  postApi(`/api/v1/backtests/advanced/sensitivity?symbol=${symbol}&param_name=${paramName}`);

// Phase 4: ML Regime
export interface MLRegimeSummary {
  trained: boolean;
  n_features: number;
  feature_names: string[];
  feature_importance: Record<string, number>;
  n_classes: number;
  classes: string[];
}
export const trainMLRegime = (symbol: string = "BTCUSDT", epochs: number = 200) =>
  postApi(`/api/v1/ml/regime/train?symbol=${symbol}&epochs=${epochs}`);
export const predictRegime = async (symbol: string = "BTCUSDT") => {
  const response = await fetch(`${apiBaseUrl}/api/v1/ml/regime/predict?symbol=${symbol}`);
  return response.json();
};
export const getMLRegimeSummary = async (): Promise<MLRegimeSummary> => {
  const response = await fetch(`${apiBaseUrl}/api/v1/ml/regime/summary`);
  return response.json() as Promise<MLRegimeSummary>;
};

// Phase 4: Binance Testnet
export const getBinanceTestnetStatus = async () => {
  const response = await fetch(`${apiBaseUrl}/api/v1/binance/testnet/status`);
  return response.json();
};
export const getBinanceTestnetPrice = async (symbol: string = "BTCUSDT") => {
  const response = await fetch(`${apiBaseUrl}/api/v1/binance/testnet/price?symbol=${symbol}`);
  return response.json();
};

// Phase 4: Multi-Asset
export const getAssetClasses = async () => {
  const response = await fetch(`${apiBaseUrl}/api/v1/assets/classes`);
  return response.json();
};
export const getSupportedSymbols = async (): Promise<string[]> => {
  const response = await fetch(`${apiBaseUrl}/api/v1/assets/symbols`);
  return response.json() as Promise<string[]>;
};
export const getForexRates = async (base: string = "USD") => {
  const response = await fetch(`${apiBaseUrl}/api/v1/assets/forex?base=${base}`);
  return response.json();
};
export const getCommodityPrices = async () => {
  const response = await fetch(`${apiBaseUrl}/api/v1/assets/commodities`);
  return response.json();
};
