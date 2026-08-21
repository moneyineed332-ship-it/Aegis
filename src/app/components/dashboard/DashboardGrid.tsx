import { memo, useEffect } from "react";
import {
  Cpu,
  Brain,
  Shield,
  AlertTriangle,
  FlaskConical,
  Database,
  BookOpen,
  BarChart2,
  ChevronRight,
  Target,
} from "lucide-react";
import type { DashboardSnapshot } from "../../lib/api";
import { Card, CardHeader, Badge, EmptyState } from "../ui";
import { useAlertWebSocket } from "../AlertWebSocketProvider";

interface DashboardGridProps {
  data: DashboardSnapshot | null;
  activeSection: string;
  onNavigate: (section: string) => void;
}

const regimeLabels: Record<string, string> = {
  bull_trend: "Tendance Haussière",
  bear_trend: "Tendance Baissière",
  range: "Marché Latéral",
  high_volatility: "Haute Volatilité",
  low_volatility: "Basse Volatilité",
  capitulation: "Capitulation",
  euphoria: "Euphorie",
};

const regimeColors: Record<string, string> = {
  bull_trend: "var(--success)",
  bear_trend: "var(--destructive)",
  range: "var(--warning)",
  high_volatility: "#ff6b35",
  low_volatility: "var(--primary)",
  capitulation: "var(--destructive)",
  euphoria: "var(--success)",
};

function DashboardGrid({ data, activeSection: _activeSection, onNavigate }: DashboardGridProps) {
  const { connected: wsConnected, lastAlert } = useAlertWebSocket();
  const lastAlertMessage = lastAlert?.message ?? null;

  const regime = data?.market_analysis?.regime;
  const features = data?.market_analysis?.features;
  const risk = data?.risk;
  const backtests = data?.recent_backtests ?? [];
  const stressTest = data?.stress_test;
  const strategies = data?.strategy_registry ?? [];
  const journal = data?.journal;
  const memory = data?.memory;
  const supervisor = data?.supervisor;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {/* Market Regime */}
      <Card hoverable onClick={() => onNavigate("regime")}>
        <CardHeader
          title="RÉGIME DE MARCHÉ"
          icon={<Cpu className="w-4 h-4" />}
          color={regimeColors[regime?.regime ?? "range"] ?? "var(--primary)"}
          action={<ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />}
        />
        {regime ? (
          <div>
            <div className="flex items-baseline gap-2 mb-2">
              <span
                className="font-['Rajdhani'] font-bold text-lg"
                style={{ color: regimeColors[regime.regime] ?? "var(--primary)" }}
              >
                {regimeLabels[regime.regime] ?? regime.regime}
              </span>
              <Badge variant="info">{regime.confidence != null ? `${(regime.confidence * 100).toFixed(0)}% conf.` : "conf. N/A"}</Badge>
            </div>
            {features && (
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] text-muted-foreground">RSI(14)</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{features.rsi_14 != null ? features.rsi_14.toFixed(1) : "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] text-muted-foreground">Volatilité</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{features.volatility_20 != null ? (features.volatility_20 * 100).toFixed(1) + "%" : "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] text-muted-foreground">Momentum</span>
                  <span className={`font-['JetBrains_Mono'] text-[12px] ${(features.momentum_20 ?? 0) >= 0 ? "text-success" : "text-destructive"}`}>
                    {features.momentum_20 != null ? ((features.momentum_20) * 100).toFixed(2) + "%" : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] text-muted-foreground">ATR(14)</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{features.atr_14 != null ? `$${features.atr_14.toFixed(0)}` : "—"}</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyState title="Aucune donnée disponible" />
        )}
      </Card>

      {/* Risk Assessment */}
      <Card hoverable onClick={() => onNavigate("risk")}>
        <CardHeader
          title="ÉVALUATION DES RISQUES"
          icon={<Shield className="w-4 h-4" />}
          color="var(--primary)"
          action={<ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />}
        />
        {risk ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Value at Risk (95%)</span>
              <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">${risk.value_at_risk.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">CVaR (95%)</span>
              <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">${risk.conditional_value_at_risk.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Volatilité Annualisée</span>
              <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{(risk.annualized_volatility * 100).toFixed(1)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Max Drawdown</span>
              <span className="font-['JetBrains_Mono'] text-[12px] text-destructive">{risk.max_drawdown_pct.toFixed(2)}%</span>
            </div>
            {stressTest && (
              <div className="pt-2 mt-2 border-t border-border/50">
                <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground/60 tracking-wider mb-1.5">STRESS TEST</div>
                <div className="flex items-center justify-between">
                  <span className="font-['Inter'] text-[12px] text-muted-foreground">Pire Jour</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-destructive">{stressTest.worst_day_return != null ? `${stressTest.worst_day_return.toFixed(2)}%` : "—"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-['Inter'] text-[12px] text-muted-foreground">Pire Semaine</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-destructive">{stressTest.worst_week_return != null ? `${stressTest.worst_week_return.toFixed(2)}%` : "—"}</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyState title="Aucune donnée" />
        )}
      </Card>

      {/* Strategy Registry */}
      <Card hoverable onClick={() => onNavigate("optimizer")}>
        <CardHeader
          title="STRATÉGIES DISPONIBLES"
          icon={<Target className="w-4 h-4" />}
          color="var(--accent)"
          action={<ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />}
        />
        <div className="space-y-1.5">
          {strategies.slice(0, 5).map((s) => (
            <div key={s.id} className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                <span className="font-['Inter'] text-[12px] text-foreground">{s.name}</span>
              </div>
              <Badge>{s.type}</Badge>
            </div>
          ))}
          {strategies.length > 5 && (
            <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground/50 text-center pt-1">
              +{strategies.length - 5} autres
            </div>
          )}
        </div>
      </Card>

      {/* Recent Backtests */}
      <Card hoverable onClick={() => onNavigate("backtest")}>
        <CardHeader
          title="DERNIERS BACKTESTS"
          icon={<FlaskConical className="w-4 h-4" />}
          color="var(--chart-4)"
          action={<ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />}
        />
        {backtests.length > 0 ? (
          <div className="space-y-2">
            {backtests.slice(0, 3).map((bt) => (
              <div key={bt.id} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
                <div>
                  <div className="font-['Inter'] text-[12px] text-foreground">{bt.strategy}</div>
                  <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">{bt.symbol} · {bt.interval}</div>
                </div>
                <div className="text-right">
                  <div className={`font-['JetBrains_Mono'] text-[12px] ${(bt.metrics.total_return ?? 0) >= 0 ? "text-success" : "text-destructive"}`}>
                    {((bt.metrics.total_return ?? 0) * 100).toFixed(1)}%
                  </div>
                  <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">
                    Sharpe: {(bt.metrics.sharpe_ratio ?? 0).toFixed(2)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="Aucun backtest récent" />
        )}
      </Card>

      {/* Alerts & WebSocket */}
      <Card hoverable onClick={() => onNavigate("alerts")}>
        <CardHeader
          title="SYSTÈME D'ALERTES"
          icon={<AlertTriangle className="w-4 h-4" />}
          color="var(--warning)"
          action={<ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />}
        />
        <div className="space-y-2.5">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${wsConnected ? "bg-success animate-pulse" : "bg-destructive"}`} />
            <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">
              WebSocket: {wsConnected ? "CONNECTÉ" : "DÉCONNECTÉ"}
            </span>
          </div>
          {lastAlertMessage && (
            <div className="rounded-lg p-2 border border-primary/10" style={{ background: "rgba(0,212,255,0.03)" }}>
              <div className="font-['JetBrains_Mono'] text-[12px] text-primary/60 tracking-wider mb-0.5">DERNIÈRE ALERTE</div>
              <div className="font-['Inter'] text-[12px] text-foreground line-clamp-2">{lastAlertMessage}</div>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="font-['Inter'] text-[12px] text-muted-foreground">Superviseur</span>
            <Badge variant={supervisor?.kill_switch_active ? "danger" : "success"}>
              {supervisor?.kill_switch_active ? "ARRÊT D'URGENCE" : "ACTIF"}
            </Badge>
          </div>
        </div>
      </Card>

      {/* Decision Journal */}
      <Card hoverable onClick={() => onNavigate("journal")}>
        <CardHeader
          title="JOURNAL DE DÉCISIONS"
          icon={<BookOpen className="w-4 h-4" />}
          color="var(--success)"
          action={<ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />}
        />
        {journal ? (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg p-2 border border-border/50" style={{ background: "rgba(0,255,136,0.03)" }}>
                <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground/60">PRÉCISION</div>
                <div className="font-['Rajdhani'] font-bold text-lg text-success">{((journal.accuracy ?? 0) * 100).toFixed(0)}%</div>
              </div>
              <div className="rounded-lg p-2 border border-border/50" style={{ background: "rgba(0,87,255,0.03)" }}>
                <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground/60">DÉCISIONS</div>
                <div className="font-['Rajdhani'] font-bold text-lg text-foreground">{journal.total_decisions}</div>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">PnL Moyen</span>
              <span className={`font-['JetBrains_Mono'] text-[12px] ${(journal.avg_pnl ?? 0) >= 0 ? "text-success" : "text-destructive"}`}>
                {(journal.avg_pnl ?? 0) >= 0 ? "+" : ""}{((journal.avg_pnl ?? 0) * 100).toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">PnL Total</span>
              <span className={`font-['JetBrains_Mono'] text-[12px] ${(journal.total_pnl ?? 0) >= 0 ? "text-success" : "text-destructive"}`}>
                {(journal.total_pnl ?? 0) >= 0 ? "+" : ""}{((journal.total_pnl ?? 0) * 100).toFixed(2)}%
              </span>
            </div>
          </div>
        ) : (
          <EmptyState title="Aucune décision enregistrée" />
        )}
      </Card>

      {/* Memory */}
      <Card>
        <CardHeader
          title="MÉMOIRE ÉPISODIQUE"
          icon={<Brain className="w-4 h-4" />}
          color="#9945ff"
        />
        {memory ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Épisodes totaux</span>
              <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{memory.total_episodes}</span>
            </div>
            {memory.strategies_used.length > 0 && (
              <div className="space-y-1">
                {memory.strategies_used.slice(0, 3).map((s) => (
                  <div key={s.strategy} className="flex items-center justify-between">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">{s.strategy}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">{s.count}x</span>
                      <span className={`font-['JetBrains_Mono'] text-[12px] ${s.win_rate >= 0.5 ? "text-success" : "text-destructive"}`}>
                        {(s.win_rate * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {memory.best_fingerprint && (
              <div className="flex items-center justify-between pt-1 border-t border-border/30">
                <span className="font-['Inter'] text-[12px] text-muted-foreground">Meilleur pattern</span>
                <span className="font-['JetBrains_Mono'] text-[12px] text-primary truncate max-w-[100px]">{memory.best_fingerprint}</span>
              </div>
            )}
          </div>
        ) : (
          <EmptyState title="Aucune donnée" />
        )}
      </Card>

      {/* Data Quality */}
      <Card>
        <CardHeader
          title="QUALITÉ DES DONNÉES"
          icon={<Database className="w-4 h-4" />}
          color="var(--primary)"
        />
        {data?.data_quality ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant={data.data_quality.valid ? "success" : "danger"}>
                {data.data_quality.valid ? "VALIDÉ" : "ERREURS"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Candles</span>
              <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{data.data_quality.candle_count}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Lacunes</span>
              <Badge variant={data.data_quality.gap_count > 0 ? "warning" : "success"}>
                {data.data_quality.gap_count}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Candles invalides</span>
              <Badge variant={data.data_quality.invalid_candle_count > 0 ? "warning" : "success"}>
                {data.data_quality.invalid_candle_count}
              </Badge>
            </div>
          </div>
        ) : (
          <EmptyState title="Aucune donnée" />
        )}
      </Card>

      {/* Market Indicators */}
      <Card hoverable onClick={() => onNavigate("free-apis")}>
        <CardHeader
          title="INDICATEURS DE MARCHÉ"
          icon={<BarChart2 className="w-4 h-4" />}
          color="var(--warning)"
          action={<ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />}
        />
        <div className="space-y-2">
          {data?.fear_greed && data.fear_greed.length > 0 && (
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Fear & Greed</span>
              <div className="flex items-center gap-1.5">
                <div
                  className="w-6 h-1.5 rounded-full"
                  style={{
                    background: `linear-gradient(90deg, var(--destructive) 0%, var(--warning) 50%, var(--success) 100%)`,
                    opacity: 0.3,
                  }}
                />
                <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{data.fear_greed[0].value}</span>
              </div>
            </div>
          )}
          {data?.funding_rates && data.funding_rates.length > 0 && (
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Funding Rate</span>
              <span className={`font-['JetBrains_Mono'] text-[12px] ${(data.funding_rates[0].funding_rate ?? 0) >= 0 ? "text-success" : "text-destructive"}`}>
                {((data.funding_rates[0].funding_rate ?? 0) * 100).toFixed(4)}%
              </span>
            </div>
          )}
          {data?.open_interest && data.open_interest.length > 0 && (
            <div className="flex items-center justify-between">
              <span className="font-['Inter'] text-[12px] text-muted-foreground">Open Interest</span>
              <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">
                {data.open_interest[0].open_interest_usd != null ? `$${(data.open_interest[0].open_interest_usd / 1_000_000).toFixed(1)}M` : "—"}
              </span>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export default memo(DashboardGrid);
