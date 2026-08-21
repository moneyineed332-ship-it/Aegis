import { useState, useEffect, useCallback } from "react";
import { Shield, AlertTriangle, RefreshCw } from "lucide-react";
import { getDashboard, type DashboardSnapshot } from "../../lib/api";
import { Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";

export default function RiskSection() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setSnapshot(await getDashboard());
    } catch {
      toast.error("Erreur lors du chargement des données de risque");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { void load(); }, [load]);

  const risk = snapshot?.risk;
  const stressTest = snapshot?.stress_test;
  const correlation = snapshot?.correlation;
  const concentration = snapshot?.concentration;

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(0,212,255,0.1)" }}>
            <Shield className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="font-['Rajdhani'] font-bold text-2xl text-foreground">Évaluation des Risques</h2>
            <p className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">VaR, stress test, corrélation, concentration</p>
          </div>
        </div>
        <button onClick={() => void load()} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary/30 font-['JetBrains_Mono'] text-[12px] text-primary hover:bg-primary/5 transition-all disabled:opacity-50">
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Rafraîchir
        </button>
      </div>

      {loading ? (
        <div className="space-y-3"><Skeleton className="h-32 w-full" /><Skeleton className="h-32 w-full" /></div>
      ) : !snapshot ? (
        <div className="text-center py-12 rounded-xl border border-border" style={{ background: "rgba(11,18,32,0.5)" }}>
          <p className="font-['Inter'] text-sm text-muted-foreground">API indisponible</p>
        </div>
      ) : (
        <>
          {/* Core Risk Metrics */}
          <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-4 h-4 text-primary" />
              <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-wider">MÉTRIQUES DE RISQUE</span>
            </div>
            {risk ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="rounded-lg p-3 border border-border/50" style={{ background: "rgba(0,212,255,0.03)" }}>
                  <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 mb-1">VALUE AT RISK (95%)</div>
                  <div className="font-['Rajdhani'] font-bold text-xl text-foreground">{(risk.value_at_risk * 100).toFixed(2)}%</div>
                </div>
                <div className="rounded-lg p-3 border border-border/50" style={{ background: "rgba(0,87,255,0.03)" }}>
                  <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 mb-1">CVaR (95%)</div>
                  <div className="font-['Rajdhani'] font-bold text-xl text-foreground">{(risk.conditional_value_at_risk * 100).toFixed(2)}%</div>
                </div>
                <div className="rounded-lg p-3 border border-border/50" style={{ background: "rgba(0,255,136,0.03)" }}>
                  <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 mb-1">VOLATILITÉ ANN.</div>
                  <div className="font-['Rajdhani'] font-bold text-xl text-foreground">{(risk.annualized_volatility * 100).toFixed(1)}%</div>
                </div>
                <div className="rounded-lg p-3 border border-border/50" style={{ background: "rgba(255,51,102,0.03)" }}>
                  <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 mb-1">MAX DRAWDOWN</div>
                  <div className="font-['Rajdhani'] font-bold text-xl text-red-400">{(risk.max_drawdown_pct * 100).toFixed(2)}%</div>
                </div>
              </div>
            ) : (
              <p className="font-['Inter'] text-sm text-muted-foreground">Historique insuffisant pour calculer le risque</p>
            )}
          </div>

          {/* Stress Test + Correlation + Concentration */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Stress Test */}
            <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span className="font-['JetBrains_Mono'] text-xs text-amber-400 tracking-wider">STRESS TEST</span>
              </div>
              {stressTest ? (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">Pire jour</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] text-red-400">{stressTest.worst_day_return.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">Pire semaine</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] text-red-400">{stressTest.worst_week_return.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">Pire mois</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] text-red-400">{stressTest.worst_month_return.toFixed(1)}%</span>
                  </div>
                  <div className="border-t border-border pt-2 mt-2 space-y-1">
                    {stressTest.scenarios.slice(0, 3).map((s) => (
                      <div key={s.name} className="flex justify-between py-0.5">
                        <span className="font-['Inter'] text-[11px] text-muted-foreground">{s.name}</span>
                        <span className="font-['JetBrains_Mono'] text-[11px] text-red-400">${Math.abs(s.portfolio_impact).toFixed(0)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="font-['Inter'] text-[12px] text-muted-foreground/50">Pas de données</p>
              )}
            </div>

            {/* Correlation */}
            <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-4">
                <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-wider">CORRÉLATION</span>
              </div>
              {correlation ? (
                <div className="space-y-2">
                  <div className="flex justify-between mb-2">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">Moyenne</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{correlation.avg_correlation?.toFixed(2) ?? "—"}</span>
                  </div>
                  <div className="font-['Inter'] text-[11px] text-muted-foreground mb-2">{correlation.interpretation}</div>
                  <div className="space-y-1.5">
                    {correlation.symbols.flatMap((sym, i) =>
                      correlation.symbols.slice(i + 1).map((other) => (
                        <div key={`${sym}-${other}`} className="flex items-center gap-2">
                          <span className="font-['JetBrains_Mono'] text-[11px] text-foreground w-20">{sym.replace("USDT", "")}-{other.replace("USDT", "")}</span>
                          <div className="flex-1 h-1.5 rounded-full" style={{ background: "rgba(0,212,255,0.1)" }}>
                            <div className="h-full rounded-full" style={{ width: `${Math.abs((correlation.matrix[sym]?.[other] ?? 0)) * 100}%`, background: "#00d4ff" }} />
                          </div>
                          <span className="font-['JetBrains_Mono'] text-[11px] text-muted-foreground w-10 text-right">{(correlation.matrix[sym]?.[other] ?? 0).toFixed(2)}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : (
                <p className="font-['Inter'] text-[12px] text-muted-foreground/50">Pas de données</p>
              )}
            </div>

            {/* Concentration */}
            <div className="rounded-xl border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="flex items-center gap-2 mb-4">
                <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-wider">CONCENTRATION</span>
              </div>
              {concentration && concentration.position_count > 0 ? (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">Exposition totale</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">${concentration.total_exposure.toLocaleString("fr-FR")}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">HHI</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{concentration.herfindahl.toFixed(3)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-['Inter'] text-[12px] text-muted-foreground">Max concentration</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{concentration.max_concentration.toFixed(1)}%</span>
                  </div>
                  <div className="border-t border-border pt-2 mt-2 space-y-1">
                    {concentration.positions.map((p, idx) => (
                      <div key={`${p.symbol}-${idx}`} className="flex justify-between">
                        <span className="font-['JetBrains_Mono'] text-[11px] text-foreground">{p.symbol}</span>
                        <span className="font-['JetBrains_Mono'] text-[11px] text-muted-foreground">{p.weight}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="font-['Inter'] text-[12px] text-muted-foreground/50">Aucune position ouverte</p>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
