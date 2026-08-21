import { useState, useEffect, useCallback } from "react";
import { getDashboard, type DashboardSnapshot } from "../../lib/api";
import { DataTimestamp } from "../components/DataTimestamp";
import { useAlertWebSocket } from "../components/AlertWebSocketProvider";

export default function OperationsSection() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const { connected: wsConnected, lastAlert } = useAlertWebSocket();

  const refresh = useCallback(async () => {
    try {
      const data = await getDashboard();
      setSnapshot(data);
      setError(false);
      setLastUpdated(new Date());
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const intervalId = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(intervalId);
  }, [refresh]);

  useEffect(() => {
    if (lastAlert) void refresh();
  }, [lastAlert, refresh]);

  return (
    <section id="operations" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div><div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">07 — OPÉRATIONS</div><div className="flex flex-wrap items-center gap-3"><h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">État <span className="text-primary">AEGIS</span></h2><DataTimestamp lastUpdated={lastUpdated} /></div></div>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${wsConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
              <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground">{wsConnected ? "LIVE" : "OFFLINE"}</span>
            </div>
            {lastAlert && <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-primary/60 max-w-[200px] truncate">{lastAlert.message ?? lastAlert.type}</span>}
          </div>
          <div className={`font-['JetBrains_Mono'] text-[12px] sm:text-xs ${error ? "text-red-400" : "text-green-400"}`}>{error ? "API INDISPONIBLE" : "ACTUALISATION 15s"}</div>
        </div>
        {error && !snapshot && (
          <div className="border border-red-400/30 bg-red-400/5 p-6 text-center">
            <div className="font-['Rajdhani'] font-700 text-lg text-foreground mb-2">API Indisponible</div>
            <div className="font-['Inter'] text-xs text-muted-foreground mb-4">Vérifie que le backend AEGIS est lancé sur le port 8000.</div>
            <button onClick={() => void refresh()} className="px-4 py-2 font-['JetBrains_Mono'] text-xs border border-primary/30 text-primary hover:bg-primary/5 transition-all">RÉESSAYER</button>
          </div>
        )}
        {snapshot && <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4">
          {[
            { label: "Qualité données", value: snapshot.data_quality.valid ? "VALIDE" : "BLOQUÉE", detail: `${snapshot.data_quality.candle_count} bougies · ${snapshot.data_quality.gap_count} trous`, color: snapshot.data_quality.valid ? "#22c55e" : "#ef4444" },
            { label: "Régime marché", value: snapshot.market_analysis?.regime.regime ?? "N/A", detail: `Confiance ${((snapshot.market_analysis?.regime.confidence ?? 0) * 100).toFixed(0)}%`, color: "#00d4ff" },
            { label: "Risque historique", value: snapshot.risk ? `VaR $${snapshot.risk.value_at_risk.toLocaleString("fr-FR")}` : "N/A", detail: snapshot.risk ? `CVaR $${snapshot.risk.conditional_value_at_risk.toLocaleString("fr-FR")}` : "Historique insuffisant", color: "#f59e0b" },
            { label: "Superviseur", value: snapshot.supervisor.kill_switch_active ? "ARRÊT ACTIF" : "SURVEILLÉ", detail: `${snapshot.alerts.length} alertes journalisées`, color: snapshot.supervisor.kill_switch_active ? "#ef4444" : "#22c55e" },
          ].map((card) => <div key={card.label} className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}><div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground mb-2 sm:mb-3">{card.label.toUpperCase()}</div><div className="font-['Rajdhani'] text-lg sm:text-2xl font-700" style={{ color: card.color }}>{card.value}</div><div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground mt-1 sm:mt-2">{card.detail}</div></div>)}
        </div>}
        {snapshot && <div className="grid lg:grid-cols-2 gap-2 sm:gap-4 mt-2 sm:mt-4">
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">BIBLIOTHÈQUE DE STRATÉGIES</div>
            <div className="space-y-2 sm:space-y-3">{snapshot.strategy_registry.map((strategy) => <div key={strategy.id} className="flex items-center justify-between gap-2 sm:gap-3"><div><div className="font-['Inter'] text-xs sm:text-sm text-foreground">{strategy.name}</div><div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">{strategy.type}</div></div><span className={`font-['JetBrains_Mono'] text-[12px] sm:text-xs ${strategy.status === "active" ? "text-green-400" : strategy.status === "disabled" ? "text-muted-foreground/60" : "text-primary"}`}>{strategy.status.toUpperCase()}</span></div>)}</div>
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">COACH & MÉMOIRE</div>
            <div className="font-['Inter'] text-xs sm:text-sm text-foreground mb-2 sm:mb-3">{snapshot.coach.reviewed_backtests} backtests analysés</div>
            <div className="space-y-1.5 sm:space-y-2">{snapshot.coach.recommendations.slice(0, 3).map((item, index) => <div key={`${item.action}-${index}`} className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">{item.action.replaceAll("_", " ").toUpperCase()} {item.reason ? `— ${item.reason}` : ""}</div>)}</div>
            {snapshot.recent_decisions[0] && <div className="mt-3 sm:mt-4 border-t border-border pt-2 sm:pt-3 font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">DERNIÈRE DÉCISION: {snapshot.recent_decisions[0].decision.recommendation?.action?.toUpperCase() ?? "N/A"}</div>}
          </div>
        </div>}
        {snapshot && <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 mt-2 sm:mt-4">
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center justify-between mb-3 sm:mb-4">
              <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">FEAR & GREED</div>
              <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">{snapshot.fear_greed[0]?.value ?? "—"}/100</span>
            </div>
            {snapshot.fear_greed[0] ? (
              <div>
                <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700" style={{ color: (snapshot.fear_greed[0].value ?? 50) < 30 ? "#ef4444" : (snapshot.fear_greed[0].value ?? 50) > 70 ? "#22c55e" : "#f59e0b" }}>
                  {snapshot.fear_greed[0].classification}
                </div>
                <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground mt-1">Source: alternative.me</div>
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de données — cliquer Refresh</div>
            )}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">FUNDING RATE</div>
            {snapshot.funding_rates.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {snapshot.funding_rates.slice(0, 3).map((fr, idx) => (
                  <div key={fr.symbol} className="flex items-center justify-between">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{fr.symbol}</span>
                    <span className={`font-['JetBrains_Mono'] text-[12px] sm:text-xs ${fr.funding_rate >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {(fr.funding_rate * 100).toFixed(4)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">OPEN INTEREST</div>
            {snapshot.open_interest.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {snapshot.open_interest.slice(0, 3).map((oi, idx) => (
                  <div key={oi.symbol} className="flex items-center justify-between">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{oi.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">
                      ${(oi.open_interest_usd / 1_000_000).toFixed(1)}M
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
        </div>}
        {snapshot && <div className="border border-border p-3 sm:p-5 mt-2 sm:mt-4" style={{ background: "rgba(11,18,32,0.7)" }}>
          <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">MÉMOIRE ÉPISODIQUE</div>
          <div className="grid grid-cols-3 gap-2 sm:gap-4">
            <div>
              <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700 text-foreground">{snapshot.memory.total_episodes}</div>
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Épisodes</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700 text-foreground">{snapshot.memory.strategies_used.length}</div>
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Stratégies</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700" style={{ color: (snapshot.memory.avg_result ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                {snapshot.memory.avg_result !== null ? `${(snapshot.memory.avg_result * 100).toFixed(2)}%` : "—"}
              </div>
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Moyen</div>
            </div>
          </div>
          {snapshot.memory.strategies_used.length > 0 && (
            <div className="mt-3 sm:mt-4 border-t border-border pt-2 sm:pt-3 space-y-1.5 sm:space-y-2">
              {snapshot.memory.strategies_used.map((s) => (
                <div key={s.strategy} className="flex items-center justify-between">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{s.strategy}</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">
                    {s.count} épisodes · WR {(s.win_rate * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>}
        {snapshot && <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 mt-2 sm:mt-4">
          {/* Stress Test */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">STRESS TEST</div>
            {snapshot.stress_test ? (
              <div className="space-y-1.5 sm:space-y-2">
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Pire jour</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400">{snapshot.stress_test.worst_day_return.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Pire semaine</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400">{snapshot.stress_test.worst_week_return.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Pire mois</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400">{snapshot.stress_test.worst_month_return.toFixed(1)}%</span>
                </div>
                <div className="border-t border-border pt-1.5 sm:pt-2 mt-1.5 sm:mt-2">
                  {snapshot.stress_test.scenarios.slice(0, 3).map((s) => (
                    <div key={s.name} className="flex justify-between py-0.5 sm:py-1">
                      <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">{s.name}</span>
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400">${Math.abs(s.portfolio_impact).toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
          {/* Correlation */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">CORRÉLATION</div>
            {snapshot.correlation ? (
              <div className="space-y-1.5 sm:space-y-2">
                <div className="flex justify-between mb-2 sm:mb-3">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Moyenne</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">{snapshot.correlation.avg_correlation?.toFixed(2) ?? "—"}</span>
                </div>
                <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground mb-1.5 sm:mb-2">{snapshot.correlation.interpretation}</div>
                <div className="space-y-1">
                  {snapshot.correlation.symbols.map((sym) => (
                    <div key={sym} className="flex items-center gap-1.5 sm:gap-2">
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground w-12 sm:w-16">{sym.replace("USDT", "")}</span>
                      <div className="flex-1 h-1 sm:h-1.5 rounded-full" style={{ background: "rgba(0,212,255,0.1)" }}>
                        <div className="h-full rounded-full" style={{ width: `${Math.abs((snapshot.correlation?.matrix[sym]?.[sym] ?? 1)) * 100}%`, background: "#00d4ff" }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
          {/* Concentration */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">CONCENTRATION</div>
            {snapshot.concentration && snapshot.concentration.position_count > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Exposition totale</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">${snapshot.concentration.total_exposure.toLocaleString("fr-FR")}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">HHI</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">{snapshot.concentration.herfindahl.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Max concentration</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">{snapshot.concentration.max_concentration.toFixed(1)}%</span>
                </div>
                <div className="border-t border-border pt-1.5 sm:pt-2 mt-1.5 sm:mt-2 space-y-1">
                  {snapshot.concentration.positions.map((p, idx) => (
                    <div key={`${p.symbol}-${idx}`} className="flex justify-between">
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">{p.symbol}</span>
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">{p.weight}%</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Aucune position ouverte</div>
            )}
          </div>
        </div>}
        {snapshot && snapshot.journal && <div className="border border-border p-3 sm:p-5 mt-2 sm:mt-4" style={{ background: "rgba(11,18,32,0.7)" }}>
          <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">JOURNAL DE DÉCISIONS</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 mb-3 sm:mb-4">
            <div>
              <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700 text-foreground">{snapshot.journal.total_decisions}</div>
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Décisions</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700" style={{ color: (snapshot.journal.accuracy ?? 0) >= 0.5 ? "#22c55e" : "#ef4444" }}>
                {snapshot.journal.accuracy !== null ? `${(snapshot.journal.accuracy * 100).toFixed(0)}%` : "—"}
              </div>
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Précision</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700" style={{ color: (snapshot.journal.avg_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                {snapshot.journal.avg_pnl !== null ? `${(snapshot.journal.avg_pnl * 100).toFixed(2)}%` : "—"}
              </div>
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">PnL moyen</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-base sm:text-lg font-700 text-primary">{snapshot.journal.feedback?.grade ?? "—"}</div>
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Évaluation</div>
            </div>
          </div>
          {(snapshot.journal.feedback?.strengths?.length ?? 0) > 0 && (
            <div className="mb-2 sm:mb-3">
              <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-green-400 mb-0.5 sm:mb-1">FORCES</div>
              {snapshot.journal.feedback?.strengths?.map((s, i) => (
                <div key={i} className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">+ {s}</div>
              ))}
            </div>
          )}
          {(snapshot.journal.feedback?.weaknesses?.length ?? 0) > 0 && (
            <div>
              <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400 mb-0.5 sm:mb-1">POINTS D'AMÉLIORATION</div>
              {snapshot.journal.feedback?.weaknesses?.map((w, i) => (
                <div key={i} className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">- {w}</div>
              ))}
            </div>
          )}
          {Object.keys(snapshot.journal.by_action).length > 0 && (
            <div className="mt-3 sm:mt-4 border-t border-border pt-2 sm:pt-3">
              <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-1.5 sm:mb-2">PAR ACTION</div>
              <div className="space-y-1">
                {Object.entries(snapshot.journal.by_action).map(([action, data]) => (
                  <div key={action} className="flex items-center justify-between">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{action}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">
                      {data.count}× · WR {(data.accuracy * 100).toFixed(0)}% {data.avg_pnl !== null ? `· PnL ${(data.avg_pnl * 100).toFixed(2)}%` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>}
      </div>
    </section>
  );
}