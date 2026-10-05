export interface JournalByAction {
  count: number;
  accuracy: number;
  avg_pnl: number | null;
}

export interface JournalFeedback {
  message: string;
  grade: string;
  strengths: string[];
  weaknesses: string[];
}

export interface JournalData {
  total_decisions: number;
  accuracy: number | null;
  avg_pnl: number | null;
  total_pnl: number | null;
  by_action: Record<string, JournalByAction>;
  feedback: JournalFeedback;
}

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
  risk: { value_at_risk: number; conditional_value_at_risk: number; confidence?: number; max_drawdown?: number; max_drawdown_pct: number; volatility?: number; annualized_volatility: number } | null;
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
  market_snapshots?: Array<{ id: number; symbol: string; price: number; source: string; collected_at: string }>;
}

export interface SupervisorStatus {
  status: "healthy" | "stopped";
  kill_switch_active: boolean;
  alerts: Array<{ severity: string; message: string; created_at: string }>;
}

export interface OMSOrder {
  id: number;
  order_id: string;
  symbol: string;
  side: string;
  quantity: number;
  reference_price: number;
  fill_price?: number;
  notional: number;
  fee: number;
  status: string;
  mode: string;
  strategy: string;
  reason: string;
  created_at: string;
}

export interface AIStatus {
  available: boolean;
  providers: Record<string, { available: boolean; model: string | null }>;
  provider: string;
  note: string;
}

export interface AIAnalysis {
  regime?: string;
  risk_score?: number;
  confidence?: number;
  strategy?: string;
  reasoning?: string;
  error?: string;
}

export interface AIRiskAssessment {
  overall_risk?: number;
  max_position_pct?: string | number;
  recommendation?: string;
  hedging_suggestion?: string;
  error?: string;
}

export interface BacktestMetrics {
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  trade_count: number;
  win_rate: number;
  profit_factor: number;
}
// --- Optimizer Types ---

export interface OptimizerRankingItem {
  strategy: string;
  sharpe: number;
  return: number;
  drawdown: number;
  trades: number;
}

export interface OptimizerResult {
  strategy: string;
  symbol: string;
  interval: string;
  best_params: Record<string, number>;
  best_sharpe: number;
  best_return: number;
  ranking: OptimizerRankingItem[];
  best_overall: string | null;
  all_results: Array<{
    params: Record<string, number>;
    sharpe: number;
    total_return: number;
    max_drawdown: number;
  }>;
}

const apiBaseUrl = import.meta.env.VITE_API_URL;
if (!apiBaseUrl) {
  throw new Error("VITE_API_URL n'est pas défini. Ajoute-le dans le fichier .env à la racine du projet.");
}

// The dev server must not silently talk to a remote deployment.
//
// Every financial endpoint is authenticated with the single admin token, and
// that token is entered at runtime into localStorage. So a developer running
// `npm run dev` against a remote VITE_API_URL signs in to the real machine and
// the order, emergency-stop and mode endpoints act on it. It looks exactly like
// local work and is not.
//
// This throws at module load in dev only; a production build has DEV=false and
// is unaffected. Pointing dev at a staging host is legitimate but has to be
// asked for explicitly, so the escape hatch is a flag rather than a URL
// someone left in .env.
if (import.meta.env.DEV && !import.meta.env.VITE_ALLOW_REMOTE_API) {
  let host = "";
  try {
    host = new URL(apiBaseUrl).hostname;
  } catch {
    host = apiBaseUrl;
  }
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "[::1]" || host === "::1";
  if (!isLocal) {
    throw new Error(
      `VITE_API_URL pointe sur un hôte distant (${host}) pendant le développement.\n` +
        "Le token admin de ce navigateur agit alors sur ce déploiement : ordres, " +
        "arrêt d'urgence et changement de mode. Pour éviter un accident sur le " +
        "compte réel :\n" +
        "  - mets VITE_API_URL=http://localhost:8000 dans .env pour travailler en local, ou\n" +
        "  - lance le backend en local (AEGIS_API_PORT=8000) et utilise cette URL, ou\n" +
        "  - si tu vises volontairement un environnement de staging, pose " +
        "VITE_ALLOW_REMOTE_API=1.",
    );
  }
}

const TOKEN_STORAGE_KEY = "aegis_admin_token";

export function getAdminToken(): string {
  // The admin token is NEVER baked into the bundle: it is entered by the
  // operator at runtime and kept in localStorage. A VITE_* variable would be
  // inlined into the public JS assets by the Vite build.
  const token = localStorage.getItem(TOKEN_STORAGE_KEY) ?? "";
  // An ENC: blob can never authenticate from the browser (decryption key
  // is server-side) — treat as absent so the UI shows login state, not 401s.
  return token.startsWith("ENC:") ? "" : token;
}

export function setAdminToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token.trim());
}

export function clearAdminToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function hasAdminToken(): boolean {
  return getAdminToken().length > 0;
}

export async function verifyAdminToken(token: string): Promise<boolean> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/verify`, {
    headers: token ? { "X-AEGIS-Admin-Token": token } : {},
  });
  return response.ok;
}

export async function fetchWsTicket(): Promise<string | null> {
  // A one-shot credential for the alerts WebSocket.
  //
  // A WebSocket cannot carry an Authorization header, so the credential has to
  // ride in the URL -- and the URL is what the reverse proxy writes to its access
  // log. The admin token is long-lived and unlocks every financial endpoint, so
  // it must never be that value. This trades it for a code that expires in
  // seconds and is consumed on the first connection attempt, so a log line
  // reading it is worth nothing.
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/ws-ticket`, {
    method: "POST",
    headers: getAdminHeaders(),
  });
  if (!response.ok) return null;
  const body = (await response.json()) as { ticket?: string };
  return body.ticket ?? null;
}

function getAdminHeaders(): Record<string, string> {
  const token = getAdminToken();
  return token ? { "X-AEGIS-Admin-Token": token } : {};
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { headers: getAdminHeaders() });
  if (!response.ok) throw new Error(`API error ${response.status}`);
  return response.json() as Promise<T>;
}

export async function getDashboard(): Promise<DashboardSnapshot> {
  return apiGet<DashboardSnapshot>("/api/v1/dashboard");
}

export interface JournalOutcome {
  decision_id: number;
  action: string;
  strategy: string | null;
  regime: string | null;
  confidence: number | null;
  reason: string | null;
  order_id: string | null;
  decision_time: string;
  entry_price: number | null;
  current_price: number;
  pnl_since_decision: number | null;
  outcome: string;
  symbol: string;
}

export interface JournalAnalysis extends JournalData {
  outcomes: JournalOutcome[];
  feedback: JournalFeedback;
}

export async function getJournalAnalysis(): Promise<JournalAnalysis> {
  return apiGet<JournalAnalysis>("/api/v1/journal/analysis");
}

export async function postApi<T>(path: string, body?: unknown): Promise<T> {
  // Header-only auth: tokens in query strings leak into proxy logs and browser
  // history. The WebSockets are the one exception browsers force, and they use
  // a single-use ticket rather than the admin token (see fetchWsTicket).
  const url = `${apiBaseUrl}${path}`;
  const opts: RequestInit = { method: "POST" };
  if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json", ...getAdminHeaders() };
    opts.body = JSON.stringify(body);
  } else {
    opts.headers = getAdminHeaders();
  }
  const response = await fetch(url, opts);
  if (!response.ok) throw new Error(`AEGIS API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export const refreshMarketData = () => postApi("/api/v1/market-snapshots/refresh");
export const refreshHistory = () => postApi("/api/v1/ohlcv/refresh-history?symbol=EURUSD&interval=1h&batches=4");
export const runSmaWalkForward = () => postApi("/api/v1/backtests/sma-crossover/walk-forward");
export const runDonchianWalkForward = () => postApi("/api/v1/backtests/donchian-breakout/walk-forward");
export const getSupervisor = async (): Promise<SupervisorStatus> => {
  return apiGet<SupervisorStatus>("/api/v1/supervisor");
};
export const activateEmergencyStop = () => postApi("/api/v1/supervisor/emergency-stop");
export const resumeSupervisor = () => postApi("/api/v1/supervisor/resume");

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
  return apiGet<Alert[]>(`/api/v1/alerts/history?limit=${limit}`);
};
export const getAlertThresholds = async () => {
  return apiGet<Record<string, number>>("/api/v1/alerts/thresholds");
};
export const checkAlerts = () => postApi<{ alerts: Alert[] }>("/api/v1/alerts/check");

// Phase 4: Advanced Backtesting
export const runSmcIctBacktest = (symbol: string = "EURUSD", interval: "1h" | "4h" = "1h") =>
  postApi("/api/v1/backtests/smc-ict", { symbol, interval });
export const runMultiTimeframeBacktest = (symbol: string = "EURUSD", interval: "1h" | "4h" = "1h") =>
  postApi("/api/v1/backtests/multi-timeframe", { symbol, interval });
export const runMultiScaleCrossoverBacktest = (symbol: string = "EURUSD", interval: "1h" | "4h" = "1h") =>
  postApi("/api/v1/backtests/multi-scale-crossover", { symbol, interval });

// SMC/ICT + Multi-Timeframe walk-forward
export const runSmcIctWalkForward = (symbol: string = "EURUSD") =>
  postApi(`/api/v1/backtests/smc-ict/walk-forward?symbol=${symbol}`);
export const runMultiTimeframeWalkForward = (symbol: string = "EURUSD") =>
  postApi(`/api/v1/backtests/multi-timeframe/walk-forward?symbol=${symbol}`);

// Phase 4: ML Regime
export interface MLRegimeSummary {
  trained: boolean;
  n_features: number;
  feature_names: string[];
  feature_importance: Record<string, number>;
  n_classes: number;
  classes: string[];
}

export interface MLRegimePrediction {
  symbol: string;
  ml_prediction: {
    regime: string;
    confidence: number;
    probabilities: Record<string, number>;
  };
  rule_based: {
    regime: string;
    confidence: number;
  };
  agreement: boolean;
}

export const trainMLRegime = (symbol: string = "EURUSD", epochs: number = 200) =>
  postApi(`/api/v1/ml/regime/train?symbol=${symbol}&epochs=${epochs}`);
export const predictRegime = async (symbol: string = "EURUSD"): Promise<MLRegimePrediction> => {
  return apiGet<MLRegimePrediction>(`/api/v1/ml/regime/predict?symbol=${symbol}`);
};
export const getMLRegimeSummary = async (): Promise<MLRegimeSummary> => {
  return apiGet<MLRegimeSummary>("/api/v1/ml/regime/summary");
};

// Phase 4: Binance Testnet
// Phase 5: AI Analyst
export const getAIStatus = async () => {
  return apiGet<{ available: boolean; providers: Record<string, { available: boolean; model: string | null }>; provider: string; note: string }>("/api/v1/ai/status");
};
export const aiAnalyzeMarket = (symbol: string = "EURUSD", interval: string = "1h") =>
  postApi<AIAnalysis>(`/api/v1/ai/analyze-market?symbol=${symbol}&interval=${interval}`);
export const aiAssessRisk = (symbol: string = "EURUSD", interval: string = "1h") =>
  postApi<AIRiskAssessment>(`/api/v1/ai/assess-risk?symbol=${symbol}&interval=${interval}`);

export interface EngineStatus {
  status: "running" | "stopped";
  mode: "paper" | "live";
  started_at: string | null;
  cycle_count: number;
  symbols: string[];
  last_prices: Record<string, number>;
  last_analysis: {
    symbol: string;
    regime: string;
    confidence: number;
  } | null;
  last_signal: {
    symbol: string;
    action: string;
    strategy: string | null;
  } | null;
  stats: {
    total_events: number;
    errors: number;
    trades_executed: number;
    signals_generated: number;
    total_cycles: number;
  };
  scheduler: {
    running: boolean;
    tasks: Record<string, {
      interval: number;
      enabled: boolean;
      last_run: number;
      error_count: number;
      last_error: string | null;
    }>;
  };
  intervals: Record<string, number>;
}

export interface EngineLog {
  id: number;
  cycle_id: string;
  event_type: string;
  details: Record<string, unknown> | null;
  severity: string;
  created_at: string;
}

export interface EngineStats {
  total_events: number;
  errors: number;
  trades_executed: number;
  signals_generated: number;
  total_cycles: number;
}

export interface TradeSignal {
  id: number;
  symbol: string;
  strategy: string;
  signal_type: string;
  signal: Record<string, unknown>;
  executed: boolean;
  created_at: string;
}

// --- Export helpers ---

export async function exportDashboardCSV(): Promise<Blob> {
  const data = await getDashboard();
  const rows: string[] = ["Section,Valeur"];

  const flatten = (prefix: string, obj: Record<string, unknown>) => {
    for (const [k, v] of Object.entries(obj)) {
      if (v !== null && typeof v === "object" && !Array.isArray(v)) {
        flatten(`${prefix}.${k}`, v as Record<string, unknown>);
      } else {
        rows.push(`"${prefix}.${k}","${JSON.stringify(v)}"`);
      }
    }
  };

  flatten("equity", { current_equity: data.current_equity, realized_pnl: data.realized_pnl, exposure: data.exposure });
  if (data.risk) flatten("risk", data.risk as Record<string, unknown>);
  if (data.journal) flatten("journal", data.journal as Record<string, unknown>);

  return new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
}

export async function exportDashboardJSON(): Promise<Blob> {
  const data = await getDashboard();
  const exportData = {
    exported_at: new Date().toISOString(),
    equity: { current_equity: data.current_equity, realized_pnl: data.realized_pnl, exposure: data.exposure },
    risk: data.risk,
    journal: data.journal,
    positions: data.positions,
    recent_backtests: data.recent_backtests,
  };
  return new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
}

// --- Engine Control ---

export interface FocusStatus {
  focused_mode: boolean;
  strategy: string;
  strategy_name: string;
  symbols: string[];
  max_positions: number;
  donchian_parameters: { breakout_period: number; exit_period: number };
  mode: "paper" | "live";
  tradable_strategies: string[];
}

export const getFocusStatus = async () => {
  return apiGet<FocusStatus>("/api/v1/focus/status");
};

export const getEngineStatus = async () => {
  return apiGet<EngineStatus>("/api/v1/engine/status");
};
export const startEngine = async () => {
  return postApi<{ status: string; started_at?: string }>("/api/v1/engine/start");
};
export const stopEngine = async () => {
  return postApi<{ status: string; stopped_at?: string }>("/api/v1/engine/stop");
};
export const getEngineLogs = async (limit: number = 50) => {
  return apiGet<EngineLog[]>(`/api/v1/engine/logs?limit=${limit}`);
};
export const getEngineStats = async () => {
  return apiGet<EngineStats>("/api/v1/engine/stats");
};
export const getEngineSignals = async (limit: number = 20) => {
  return apiGet<TradeSignal[]>(`/api/v1/engine/signals?limit=${limit}`);
};
export const triggerEngineTask = async (taskName: string) => {
  return postApi<{ triggered: string }>(`/api/v1/engine/trigger/${taskName}`);
};

// --- Order Management System (OMS) ---

export interface OMSStatus {
  mode: string;
  positions_count: number;
  total_exposure: number;
  max_exposure: number;
  recent_orders: number;
  kill_switch: boolean;
}

export interface OMSMode {
  mode: string;
  exchange: string;
  testnet: boolean;
  max_order_notional: number;
  max_total_exposure: number;
  order_min_notional: number;
}

export const getOMSStatus = async () => {
  return apiGet<OMSStatus>("/api/v1/oms/status");
};
export const getOMSOrders = async (limit: number = 50) => {
  return apiGet<OMSOrder[]>(`/api/v1/oms/orders?limit=${limit}`);
};
export const getOMSMode = async () => {
  return apiGet<OMSMode>("/api/v1/oms/mode");
};
export const setOMSMode = async (mode: string) => {
  return postApi<{ mode: string; message: string }>(`/api/v1/oms/mode?mode=${mode}`);
};

// === Learning & Strategy Performance ===

export interface StrategyStats {
  strategy_id: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  profit_factor: number;
  score: number;
  consecutive_losses: number;
  max_consecutive_losses: number;
  regime_performance: Record<string, { trades: number; wins: number; win_rate: number; total_pnl: number }>;
  updated_at: string;
}

export interface TradeOutcome {
  id: number;
  order_id: string;
  symbol: string;
  strategy: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  pnl: number | null;
  pnl_pct: number | null;
  duration_seconds: number | null;
  regime_at_entry: string | null;
  status: "open" | "closed";
  opened_at: string;
  closed_at: string | null;
}

export interface LearningSummary {
  strategies_tracked: number;
  total_trades: number;
  open_trades: number;
  closed_trades: number;
  overall_win_rate: number;
  total_realized_pnl: number;
  top_strategies: { strategy: string; score: number; win_rate: number }[];
}

export interface MemoryConsolidation {
  symbol: string;
  total_trades: number;
  regime_breakdown: Record<string, { trades: number; wins: number; win_rate: number; total_pnl: number }>;
  strategy_breakdown: Record<string, { trades: number; wins: number; win_rate: number; total_pnl: number }>;
  patterns: { type: string; [key: string]: unknown }[];
}

export const getStrategyStats = async () => {
  return apiGet<StrategyStats[]>("/api/v1/learning/strategies");
};
export const getStrategyDetail = async (id: string) => {
  return apiGet<StrategyStats>(`/api/v1/learning/strategies/${id}`);
};
export const getStrategiesForRegime = async (regime: string) => {
  return apiGet<StrategyStats[]>(`/api/v1/learning/regime/${regime}`);
};
export const getAdaptiveWeights = async (regime: string) => {
  return apiGet<Record<string, number>>(`/api/v1/learning/weights/${regime}`);
};
export const getTradeOutcomes = async (limit: number = 50) => {
  return apiGet<TradeOutcome[]>(`/api/v1/learning/trades?limit=${limit}`);
};
export const getLearningSummary = async () => {
  return apiGet<LearningSummary>("/api/v1/learning/summary");
};
export const getMemoryConsolidation = async (symbol: string) => {
  return apiGet<MemoryConsolidation>(`/api/v1/learning/memory/${symbol}`);
};

// === Position Monitoring ===

export interface PositionDetail {
  symbol: string;
  quantity: number;
  side: string;
  entry_price: number;
  current_price: number;
  notional: number;
  cost_basis: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface PortfolioSummary {
  capital: number;
  equity: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  total_exposure: number;
  exposure_pct: number;
  long_exposure: number;
  short_exposure: number;
  position_count: number;
  positions: PositionDetail[];
  realized_pnl: number;
  total_fees: number;
  total_pnl: number;
  total_pnl_pct: number;
  updated_at: string;
}

export interface PositionRiskAlert {
  type: string;
  severity: string;
  action: string;
  symbol?: string;
  message: string;
  timestamp: string;
  [key: string]: unknown;
}

export const getPositionMonitor = async () => {
  return apiGet<{ portfolio: PortfolioSummary; alerts: PositionRiskAlert[] }>("/api/v1/positions/monitor");
};
export const getPositionPnL = async () => {
  return apiGet<PortfolioSummary>("/api/v1/positions/pnl");
};
export const getPositionRisks = async () => {
  return apiGet<{ alerts: PositionRiskAlert[]; thresholds: Record<string, number>; checked_at: string }>("/api/v1/positions/risks");
};

// === Security ===

export interface SecuritySummary {
  total_events: number;
  auth_failures: number;
  admin_actions: number;
  risk_breaches: number;
  suspicious_activities: number;
  recent_events: { id: number; event_type: string; severity: string; details: Record<string, unknown>; created_at: string }[];
}

export const getSecuritySummary = async () => {
  return apiGet<SecuritySummary>("/api/v1/security/summary");
};

// === Position Closing & Manual Orders ===

export interface ClosePositionResponse {
  closed: boolean;
  order: Record<string, unknown>;
}

export const closePosition = async (symbol: string) => {
  return postApi<ClosePositionResponse>("/api/v1/positions/close", { symbol });
};

export interface ManualOrderRequest {
  symbol: string;
  side: "buy" | "sell";
  order_type?: "market" | "limit";
  quantity: number;
  limit_price?: number;
}

export const placeManualOrder = async (order: ManualOrderRequest) => {
  return postApi<Record<string, unknown>>("/api/v1/orders/manual", order);
};



