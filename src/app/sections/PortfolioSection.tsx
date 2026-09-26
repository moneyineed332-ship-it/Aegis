import { useState, useEffect, useCallback, lazy, Suspense, type ComponentType } from "react";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Activity,
  RefreshCw,
  Zap,
  Target,
  Clock,
} from "lucide-react";
import {
  getDashboard,
  getEngineSignals,
  getEngineLogs,
  getEngineStatus,
  type DashboardSnapshot,
  type TradeSignal,
} from "../../lib/api";
import { Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";

interface ChartData {
  t: string;
  price: number;
  signal: number;
  confidence: number;
}

const LazyTradeChart = lazy(() =>
  import("recharts").then((m) => {
    const ChartComponent: ComponentType<{ data: ChartData[] }> = ({ data }) => (
      <m.ResponsiveContainer width="100%" height={280}>
        <m.ComposedChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00ff88" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#00ff88" stopOpacity={0} />
            </linearGradient>
          </defs>
          <m.CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
          <m.XAxis
            dataKey="t"
            tick={{ fill: "#5a6d88", fontSize: 9, fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <m.YAxis
            yAxisId="price"
            tick={{ fill: "#5a6d88", fontSize: 9, fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `$${v >= 1000 ? (v / 1000).toFixed(1) + "k" : v.toFixed(0)}`}
            domain={["auto", "auto"]}
          />
          <m.YAxis
            yAxisId="conf"
            orientation="right"
            tick={{ fill: "#5a6d88", fontSize: 9, fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
            domain={[0, 1]}
          />
          <m.Tooltip
            contentStyle={{
              background: "rgba(11,18,32,0.95)",
              border: "1px solid rgba(0,212,255,0.2)",
              borderRadius: 8,
              fontSize: 11,
              fontFamily: "JetBrains Mono",
            }}
            labelStyle={{ color: "#00d4ff", marginBottom: 4 }}
            formatter={(value: number, name: string) => {
              if (name === "price") return [`$${value.toLocaleString()}`, "Prix"];
              if (name === "confidence") return [`${(value * 100).toFixed(1)}%`, "Confiance"];
              return [value, name];
            }}
          />
          <m.Area
            yAxisId="price"
            type="monotone"
            dataKey="price"
            stroke="#00d4ff"
            strokeWidth={2}
            fill="url(#priceGrad)"
          />
          <m.Scatter
            yAxisId="price"
            dataKey="signal"
            fill="#00ff88"
            shape={(props: unknown): React.JSX.Element => {
              const { cx, cy, payload } = props as { cx: number; cy: number; payload: ChartData };
              const isBuy = payload.signal === 1;
              const isSell = payload.signal === -1;
              if (!isBuy && !isSell) return <g />;
              return (
                <g>
                  <circle cx={cx} cy={cy} r={6} fill={isBuy ? "#00ff88" : "#ff4444"} fillOpacity={0.3} />
                  <circle cx={cx} cy={cy} r={3} fill={isBuy ? "#00ff88" : "#ff4444"} />
                </g>
              );
            }}
          />
        </m.ComposedChart>
      </m.ResponsiveContainer>
    );
    return Promise.resolve({ default: ChartComponent });
  })
);

const regimeLabels: Record<string, string> = {
  bull_trend: "Haussier",
  bear_trend: "Baissier",
  range: "Latéral",
  high_volatility: "Haute Vol.",
  low_volatility: "Basse Vol.",
  capitulation: "Capitulation",
  euphoria: "Euphorie",
};

const regimeColors: Record<string, string> = {
  bull_trend: "#00ff88",
  bear_trend: "#ff4444",
  range: "#ffaa00",
  high_volatility: "#ff6b35",
  low_volatility: "#00d4ff",
  capitulation: "#ff4444",
  euphoria: "#00ff88",
};

export default function PortfolioSection() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [signals, setSignals] = useState<TradeSignal[]>([]);
  const [logs, setLogs] = useState<Array<{ event_type: string; details: Record<string, unknown> | null; created_at: string }>>([]);
  const [engineStatus, setEngineStatus] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, sigs, engLogs, status] = await Promise.all([
        getDashboard(),
        getEngineSignals(50),
        getEngineLogs(100),
        getEngineStatus(),
      ]);
      setSnapshot(dash);
      setSignals(sigs);
      setLogs(engLogs as Array<{ event_type: string; details: Record<string, unknown> | null; created_at: string }>);
      setEngineStatus(status as unknown as Record<string, unknown>);
    } catch {
      toast.error("Erreur lors du chargement");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const interval = setInterval(() => void load(), 30000);
    return () => clearInterval(interval);
  }, [load]);

  const chartData: ChartData[] = signals.map((sig) => {
    const details = sig.signal as Record<string, unknown>;
    const regime = (details?.regime as Record<string, unknown>) ?? {};
    const recommendation = (details?.recommendation as Record<string, unknown>) ?? {};
    const price = (details?.price as number) ?? 0;
    const confidence = (recommendation.confidence as number) ?? (regime.confidence as number) ?? 0;
    const action = (recommendation.action as string) ?? sig.signal_type;

    const signalVal = action === "buy" ? 1 : action === "sell" ? -1 : 0;
    const time = new Date(sig.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

    return { t: time, price, signal: signalVal, confidence };
  });

  const latestSnapshots = snapshot?.market_snapshots ?? [];
  const positions = snapshot?.positions ?? [];
  const supervisor = engineStatus?.scheduler as Record<string, unknown> | undefined;

  // Focused mode: show the live symbols actually tracked by the engine.
  const trackedSymbols = Array.from(new Set(latestSnapshots.map((s) => s.symbol)));
  const displaySymbols = trackedSymbols.length > 0 ? trackedSymbols : ["BTCUSDT", "ETHUSDT", "SOLUSDT"];

  const signalStats = {
    total: signals.length,
    buy: signals.filter((s) => s.signal_type === "buy").length,
    sell: signals.filter((s) => s.signal_type === "sell").length,
    research: signals.filter((s) => s.signal_type === "research").length,
  };

  const recentAnalysis = logs
    .filter((l) => l.event_type === "analysis_complete" || l.event_type === "signal_generated")
    .slice(0, 6);

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(0,212,255,0.1)" }}>
            <Wallet className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="font-['Rajdhani'] font-bold text-2xl text-foreground">Portefeuille & Trades</h2>
            <p className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Signaux, prix marché et historique</p>
          </div>
        </div>
        <button onClick={() => void load()} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary/30 font-['JetBrains_Mono'] text-[12px] text-primary hover:bg-primary/5 transition-all disabled:opacity-50">
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Rafraîchir
        </button>
      </div>

      {loading && !snapshot ? (
        <div className="space-y-3">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      ) : !snapshot ? (
        <div className="text-center py-12 rounded-xl border border-border" style={{ background: "rgba(11,18,32,0.5)" }}>
          <p className="font-['Inter'] text-sm text-muted-foreground">API indisponible</p>
        </div>
      ) : (
        <>
          {/* Prix marché en temps réel */}
          <div className="grid grid-cols-3 gap-3">
            {displaySymbols.map((sym) => {
              const snap = latestSnapshots.find((s) => s.symbol === sym);
              const price = snap?.price ?? 0;
              const displaySym = sym.replace("USDT", "");
              return (
                <div key={sym} className="rounded-xl border border-border p-4" style={{ background: "rgba(11,18,32,0.7)" }}>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center" style={{ background: "rgba(0,212,255,0.1)" }}>
                      <span className="font-['JetBrains_Mono'] text-[10px] text-primary font-bold">{displaySym}</span>
                    </div>
                    <span className="font-['Inter'] text-xs text-muted-foreground">/USDT</span>
                  </div>
                  <div className="font-['Rajdhani'] font-bold text-xl text-foreground">
                    ${price >= 1000 ? price.toLocaleString("en-US", { maximumFractionDigits: 0 }) : price.toFixed(2)}
                  </div>
                  <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/50 mt-1">
                    {snap ? new Date(snap.collected_at).toLocaleTimeString("fr-FR") : "—"}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Graphique Signaux + Prix */}
          <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary" />
                <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-wider">SIGNAUX & PRIX MARCHÉ</span>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-[#00ff88]" />
                  <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground">BUY</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-[#ff4444]" />
                  <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground">SELL</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-[#00d4ff]" />
                  <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground">Prix</span>
                </div>
              </div>
            </div>
            {chartData.length > 0 ? (
              <Suspense fallback={<Skeleton className="h-[280px] w-full" />}>
                <LazyTradeChart data={chartData} />
              </Suspense>
            ) : (
              <div className="flex items-center justify-center h-[280px] text-muted-foreground/50">
                <div className="text-center">
                  <Activity className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="font-['Inter'] text-sm">En attente de signaux...</p>
                  <p className="font-['JetBrains_Mono'] text-[11px] mt-1">L'engine génère des signaux toutes les 10 min</p>
                </div>
              </div>
            )}
          </div>

          {/* Stats rapides */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-xl border border-border p-4" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-3.5 h-3.5 text-primary" />
                <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground tracking-wider">SIGNALS</span>
              </div>
              <div className="font-['Rajdhani'] font-bold text-2xl text-foreground">{signalStats.total}</div>
            </div>
            <div className="rounded-xl border border-border p-4" style={{ background: "rgba(0,255,136,0.03)" }}>
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-3.5 h-3.5 text-success" />
                <span className="font-['JetBrains_Mono'] text-[10px] text-success/70 tracking-wider">BUY</span>
              </div>
              <div className="font-['Rajdhani'] font-bold text-2xl text-success">{signalStats.buy}</div>
            </div>
            <div className="rounded-xl border border-border p-4" style={{ background: "rgba(255,68,68,0.03)" }}>
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown className="w-3.5 h-3.5 text-destructive" />
                <span className="font-['JetBrains_Mono'] text-[10px] text-destructive/70 tracking-wider">SELL</span>
              </div>
              <div className="font-['Rajdhani'] font-bold text-2xl text-destructive">{signalStats.sell}</div>
            </div>
            <div className="rounded-xl border border-border p-4" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground tracking-wider">RESEARCH</span>
              </div>
              <div className="font-['Rajdhani'] font-bold text-2xl text-foreground">{signalStats.research}</div>
            </div>
          </div>

          {/* Positions + Régime */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Positions */}
            <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-4">
                <Wallet className="w-4 h-4 text-primary" />
                <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-wider">POSITIONS</span>
              </div>
              {positions.length > 0 ? (
                <div className="space-y-2">
                  {positions.map((p, i) => {
                    const snap = latestSnapshots.find((s) => s.symbol === p.symbol);
                    const currentPrice = snap?.price ?? p.average_price;
                    const pnl = (currentPrice - p.average_price) * p.quantity;
                    const pnlPct = ((currentPrice / p.average_price) - 1) * 100;
                    return (
                      <div key={i} className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: "rgba(0,212,255,0.1)" }}>
                            <span className="font-['JetBrains_Mono'] text-[10px] text-primary font-bold">{p.symbol.slice(0, 3)}</span>
                          </div>
                          <div>
                            <div className="font-['Inter'] text-sm text-foreground">{p.symbol}</div>
                            <div className="font-['JetBrains_Mono'] text-[11px] text-muted-foreground">{p.quantity.toFixed(4)} @ ${p.average_price.toFixed(2)}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`font-['JetBrains_Mono'] text-sm ${pnl >= 0 ? "text-success" : "text-destructive"}`}>
                            {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
                          </div>
                          <div className={`font-['JetBrains_Mono'] text-[11px] ${pnlPct >= 0 ? "text-success" : "text-destructive"}`}>
                            {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-6">
                  <p className="font-['Inter'] text-sm text-muted-foreground">Aucune position</p>
                  <p className="font-['JetBrains_Mono'] text-[11px] text-muted-foreground/50 mt-1">Capital: ${snapshot.capital.toFixed(2)}</p>
                </div>
              )}
            </div>

            {/* Régime & Dernières analyses */}
            <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-4 h-4 text-primary" />
                <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-wider">DERNIÈRES ANALYSES</span>
              </div>
              {recentAnalysis.length > 0 ? (
                <div className="space-y-2">
                  {recentAnalysis.map((log, i) => {
                    const details = log.details ?? {};
                    const symbol = (details.symbol as string) ?? "—";
                    const regime = (details.regime as string) ?? (details.action as string) ?? log.event_type;
                    const confidence = (details.confidence as number) ?? 0;
                    const time = new Date(log.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
                    const color = regimeColors[regime] ?? "#5a6d88";
                    return (
                      <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
                          <span className="font-['JetBrains_Mono'] text-[11px] text-foreground">{symbol}</span>
                          <span className="font-['JetBrains_Mono'] text-[10px] px-1.5 py-0.5 rounded" style={{ background: `${color}15`, color }}>
                            {regimeLabels[regime] ?? regime}
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground">{(confidence * 100).toFixed(0)}%</span>
                          <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/50 ml-2">{time}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-6">
                  <p className="font-['Inter'] text-sm text-muted-foreground">Aucune analyse récente</p>
                </div>
              )}
            </div>
          </div>

          {/* Historique signaux détaillé */}
          {signals.length > 0 && (
            <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-4">
                <Clock className="w-4 h-4 text-primary" />
                <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-wider">HISTORIQUE DES SIGNAUX</span>
              </div>
              <div className="space-y-1.5">
                {signals.slice(0, 10).map((sig) => {
                  const details = sig.signal as Record<string, unknown>;
                  const recommendation = (details.recommendation as Record<string, unknown>) ?? {};
                  const regime = (details.regime as Record<string, unknown>) ?? {};
                  const action = (recommendation.action as string) ?? sig.signal_type;
                  const strategy = (recommendation.strategy as string) ?? sig.strategy;
                  const confidence = (recommendation.confidence as number) ?? (regime.confidence as number) ?? 0;
                  const regimeLabel = (regime.regime as string) ?? "—";
                  const time = new Date(sig.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

                  const actionColor = action === "buy" ? "#00ff88" : action === "sell" ? "#ff4444" : "#ffaa00";
                  const actionIcon = action === "buy" ? <TrendingUp className="w-3 h-3" /> : action === "sell" ? <TrendingDown className="w-3 h-3" /> : <Target className="w-3 h-3" />;

                  return (
                    <div key={sig.id} className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
                      <div className="flex items-center gap-3">
                        <div className="w-6 h-6 rounded flex items-center justify-center" style={{ background: `${actionColor}15`, color: actionColor }}>
                          {actionIcon}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-['JetBrains_Mono'] text-[11px] text-foreground">{sig.symbol}</span>
                            <span className="font-['JetBrains_Mono'] text-[10px] px-1.5 py-0.5 rounded" style={{ background: `${actionColor}15`, color: actionColor }}>
                              {action.toUpperCase()}
                            </span>
                          </div>
                          <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground mt-0.5">
                            {strategy} · {regimeLabels[regimeLabel] ?? regimeLabel}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-['JetBrains_Mono'] text-[11px] text-foreground">{(confidence * 100).toFixed(0)}%</div>
                        <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/50">{time}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Scheduler Status */}
          {supervisor && (
            <div className="rounded-xl border border-border p-4" style={{ background: "rgba(11,18,32,0.5)" }}>
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-3.5 h-3.5 text-primary" />
                <span className="font-['JetBrains_Mono'] text-[10px] text-primary tracking-wider">ENGINE TASKS</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {Object.entries(supervisor.tasks as Record<string, Record<string, unknown>> ?? {}).map(([name, task]) => (
                  <div key={name} className="flex items-center gap-2 py-1">
                    <div className={`w-1.5 h-1.5 rounded-full ${task.error_count === 0 ? "bg-success" : "bg-destructive"}`} />
                    <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground truncate">{name.replace(/_/g, " ")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
