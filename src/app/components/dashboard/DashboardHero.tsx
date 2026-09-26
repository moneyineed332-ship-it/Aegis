import { memo, lazy, Suspense, type ComponentType } from "react";
import {
  BarChart2,
  RefreshCw,
  Wallet,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
} from "lucide-react";
import type { DashboardSnapshot } from "../../../lib/api";

interface ChartData {
  t: string;
  v: number;
}

const LazyEquityChart = lazy(() =>
  import("recharts").then((m) => {
    const ChartComponent: ComponentType<{ data: ChartData[] }> = ({ data }) => (
      <m.ResponsiveContainer width="100%" height="100%">
        <m.AreaChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
          <defs>
            <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.4} />
              <stop offset="50%" stopColor="#00d4ff" stopOpacity={0.1} />
              <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#0057ff" />
              <stop offset="50%" stopColor="#00d4ff" />
              <stop offset="100%" stopColor="#00ff88" />
            </linearGradient>
          </defs>
          <m.CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.03)"
            vertical={false}
          />
          <m.XAxis
            dataKey="t"
            tick={{ fill: "#5a6d88", fontSize: 9, fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <m.YAxis
            tick={{ fill: "#5a6d88", fontSize: 9, fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `$${v}`}
            width={45}
          />
          <m.Tooltip
            contentStyle={{
              background: "rgba(10,16,32,0.95)",
              border: "1px solid rgba(0,212,255,0.3)",
              borderRadius: 12,
              padding: "10px 14px",
              boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            }}
            labelStyle={{ color: "#8899b0", fontFamily: "JetBrains Mono", fontSize: 10 }}
            itemStyle={{ color: "#00d4ff", fontFamily: "JetBrains Mono", fontSize: 13, fontWeight: 700 }}
            formatter={(v: number) => [`$${v.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, "Equity"]}
            cursor={{ stroke: "rgba(0,212,255,0.15)", strokeWidth: 1 }}
          />
          <m.Area
            type="monotone"
            dataKey="v"
            stroke="url(#lineGrad)"
            strokeWidth={2.5}
            fill="url(#equityGrad)"
            dot={false}
            activeDot={{
              r: 5,
              fill: "#00d4ff",
              stroke: "#0b1220",
              strokeWidth: 3,
              style: { filter: "drop-shadow(0 0 6px rgba(0,212,255,0.5))" },
            }}
          />
        </m.AreaChart>
      </m.ResponsiveContainer>
    );
    return { default: ChartComponent };
  })
);

interface DashboardHeroProps {
  data: DashboardSnapshot | null;
  onRefresh: () => void;
  loading: boolean;
}

function DashboardHero({ data, onRefresh, loading }: DashboardHeroProps) {
  const equity = data?.current_equity ?? 20;
  const capital = data?.capital ?? 20;
  const pnl = data?.realized_pnl ?? 0;
  const pnlPct = capital > 0 ? ((equity / capital - 1) * 100) : 0;
  const exposure = data?.exposure ?? 0;
  const maxExposure = data?.max_exposure ?? 20;
  const positions = data?.positions ?? [];
  const equityCurve = data?.equity_curve ?? [];
  const timeSpan = equityCurve.length >= 2
    ? new Date(equityCurve[equityCurve.length - 1].time).getTime() - new Date(equityCurve[0].time).getTime()
    : 0;
  const lessThanADay = timeSpan < 86_400_000;
  const chartData = equityCurve.map((p) => ({
    t: lessThanADay
      ? new Date(p.time).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
      : new Date(p.time).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }),
    v: p.equity,
  }));

  const fg = data?.fear_greed?.[0];
  const risk = data?.risk;

  return (
    <div className="space-y-4">
      {/* Top Row: Portfolio Value + Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main Portfolio Card */}
        <div
          className="lg:col-span-2 rounded-2xl p-5 sm:p-6 border border-border relative overflow-hidden"
          style={{ background: "linear-gradient(135deg, rgba(0,212,255,0.04) 0%, rgba(10,16,32,0.9) 50%, rgba(0,87,255,0.04) 100%)" }}
        >
          {/* Decorative glow */}
          <div className="absolute -top-20 -right-20 w-40 h-40 rounded-full opacity-20" style={{ background: "radial-gradient(circle, rgba(0,212,255,0.3), transparent 70%)" }} />

          <div className="relative z-10">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(0,212,255,0.1)" }}>
                    <Wallet className="w-3.5 h-3.5 text-primary" />
                  </div>
                  <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground tracking-wider">PORTEFEUILLE TOTAL</span>
                </div>
                <div className="flex items-baseline gap-3">
                  <span className="font-['Rajdhani'] font-bold text-3xl sm:text-4xl text-foreground">
                    ${equity.toLocaleString("fr-FR", { minimumFractionDigits: 2 })}
                  </span>
                  <span className={`flex items-center gap-1 font-['JetBrains_Mono'] text-sm ${pnl >= 0 ? "text-emerald-400" : "text-destructive"}`}>
                    {pnl >= 0 ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                    {pnl >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                  </span>
                </div>
              </div>
              <button
                onClick={onRefresh}
                disabled={loading}
                aria-label="Rafraîchir les données du portefeuille"
                className="p-2 rounded-lg border border-border hover:border-primary/30 hover:bg-primary/5 transition-all disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 text-muted-foreground ${loading ? "animate-spin" : ""}`} />
              </button>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-3 gap-2 sm:gap-3 mb-4">
              <div className="rounded-xl p-2 sm:p-3 border border-border" style={{ background: "rgba(0,212,255,0.03)" }}>
                <div className="font-['JetBrains_Mono'] text-[8px] sm:text-[9px] text-muted-foreground/60 tracking-wider mb-1">CAPITAL INITIAL</div>
                <div className="font-['Rajdhani'] font-bold text-base sm:text-lg text-foreground">${capital.toLocaleString("fr-FR")}</div>
              </div>
              <div className="rounded-xl p-2 sm:p-3 border border-border" style={{ background: "rgba(0,255,136,0.03)" }}>
                <div className="font-['JetBrains_Mono'] text-[8px] sm:text-[9px] text-muted-foreground/60 tracking-wider mb-1">PNL RÉALISÉ</div>
                <div className={`font-['Rajdhani'] font-bold text-base sm:text-lg ${pnl >= 0 ? "text-emerald-400" : "text-destructive"}`}>
                  {pnl >= 0 ? "+" : ""}${Math.abs(pnl).toFixed(2)}
                </div>
              </div>
              <div className="rounded-xl p-2 sm:p-3 border border-border" style={{ background: "rgba(0,87,255,0.03)" }}>
                <div className="font-['JetBrains_Mono'] text-[8px] sm:text-[9px] text-muted-foreground/60 tracking-wider mb-1">EXPOSITION</div>
                <div className="font-['Rajdhani'] font-bold text-base sm:text-lg text-foreground">
                  ${exposure.toFixed(0)}
                  <span className="text-[10px] sm:text-[11px] text-muted-foreground font-normal"> / ${maxExposure.toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* Mini chart */}
            {chartData.length > 0 && (
              <div className="h-32 sm:h-40 rounded-xl border border-border overflow-hidden" style={{ background: "rgba(0,0,0,0.2)" }}>
                <Suspense fallback={
                  <div className="w-full h-full flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                  </div>
                }>
                  <LazyEquityChart data={chartData} />
                </Suspense>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Quick Stats */}
        <div className="space-y-4">
          {/* Fear & Greed */}
          <div className="rounded-2xl p-4 border border-border" style={{ background: "rgba(10,16,32,0.9)" }}>
            <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground tracking-wider mb-3">SENTIMENT MARCHÉ</div>
            {fg ? (
              <div className="flex items-center gap-3">
                <div className="relative w-14 h-14">
                  <svg className="w-14 h-14 -rotate-90" viewBox="0 0 36 36">
                    <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                    <circle
                      cx="18" cy="18" r="15" fill="none"
                      stroke={fg.value > 60 ? "#00ff88" : fg.value > 40 ? "#f7931a" : "#ff3366"}
                      strokeWidth="3"
                      strokeDasharray={`${(fg.value / 100) * 94.2} 94.2`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="font-['Rajdhani'] font-bold text-sm text-foreground">{fg.value}</span>
                  </div>
                </div>
                <div>
                  <div className="font-['Rajdhani'] font-bold text-sm text-foreground capitalize">{fg.classification}</div>
                  <div className="font-['JetBrains_Mono'] text-[9px] text-muted-foreground">Fear & Greed Index</div>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground font-['Inter'] text-xs">Chargement...</div>
            )}
          </div>

          {/* Risk Gauge */}
          <div className="rounded-2xl p-4 border border-border" style={{ background: "rgba(10,16,32,0.9)" }}>
            <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground tracking-wider mb-3">MÉTRIQUES DE RISQUE</div>
            {risk ? (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-['Inter'] text-[11px] text-muted-foreground">VaR (95%)</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">${risk.value_at_risk.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-['Inter'] text-[11px] text-muted-foreground">CVaR (95%)</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">${risk.conditional_value_at_risk.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-['Inter'] text-[11px] text-muted-foreground">Volatilité Ann.</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{(risk.annualized_volatility * 100).toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-['Inter'] text-[11px] text-muted-foreground">Max Drawdown</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-destructive">{risk.max_drawdown_pct.toFixed(2)}%</span>
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground font-['Inter'] text-xs">Aucune donnée</div>
            )}
          </div>

          {/* Active Positions */}
          <div className="rounded-2xl p-4 border border-border" style={{ background: "rgba(10,16,32,0.9)" }}>
            <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground tracking-wider mb-3">POSITIONS ACTIVES</div>
            {positions.length > 0 ? (
              <div className="space-y-2">
                {positions.map((p, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: "rgba(0,212,255,0.1)" }}>
                        <span className="font-['JetBrains_Mono'] text-[8px] text-primary">{p.symbol.slice(0, 3)}</span>
                      </div>
                      <div>
                        <div className="font-['Inter'] text-[11px] text-foreground">{p.symbol}</div>
                        <div className="font-['JetBrains_Mono'] text-[9px] text-muted-foreground">{p.quantity.toFixed(4)}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-['JetBrains_Mono'] text-[11px] text-foreground">${(p.quantity * p.average_price).toFixed(2)}</div>
                      <div className="font-['JetBrains_Mono'] text-[9px] text-muted-foreground">@{p.average_price.toFixed(2)}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-3">
                <div className="font-['Inter'] text-xs text-muted-foreground">Aucune position</div>
                <div className="font-['JetBrains_Mono'] text-[9px] text-muted-foreground/50 mt-1">Mode paper trading</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default memo(DashboardHero);
