import { useState } from "react";
import { runAdvancedWalkForward, runMonteCarlo, type WalkForwardResult, type MonteCarloResult } from "../../lib/api";

export default function AdvancedBacktestSection() {
  const [walkForward, setWalkForward] = useState<WalkForwardResult | null>(null);
  const [monteCarlo, setMonteCarlo] = useState<MonteCarloResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const handleWalkForward = async () => {
    setLoading("wf");
    try { setWalkForward(await runAdvancedWalkForward()); } finally { setLoading(null); }
  };

  const handleMonteCarlo = async () => {
    setLoading("mc");
    try { setMonteCarlo(await runMonteCarlo()); } finally { setLoading(null); }
  };

  return (
    <section id="backtest" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">10 — BACKTEST AVANCÉ</div>
            <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Walk-Forward & <span className="text-primary">Monte Carlo</span></h2>
          </div>
          <div className="flex gap-1.5 sm:gap-2">
            <button onClick={handleWalkForward} disabled={loading !== null} className="px-3 sm:px-4 py-1.5 sm:py-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary disabled:opacity-50 hover:bg-primary/5 transition-all">
              {loading === "wf" ? "EN COURS…" : "WALK-FORWARD"}
            </button>
            <button onClick={handleMonteCarlo} disabled={loading !== null} className="px-3 sm:px-4 py-1.5 sm:py-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary disabled:opacity-50 hover:bg-primary/5 transition-all">
              {loading === "mc" ? "EN COURS…" : "MONTE CARLO"}
            </button>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-2 sm:gap-4">
          {/* Walk-Forward */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">WALK-FORWARD OPTIMIZATION</div>
            {walkForward ? (
              <div>
                <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-3 sm:mb-4">
                  <div>
                    <div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: walkForward.avg_oos_sharpe > 0 ? "#22c55e" : "#ef4444" }}>
                      {walkForward.avg_oos_sharpe?.toFixed(2) ?? "—"}
                    </div>
                    <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Sharpe OOS</div>
                  </div>
                  <div>
                    <div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: walkForward.avg_oos_return > 0 ? "#22c55e" : "#ef4444" }}>
                      {((walkForward.avg_oos_return ?? 0) * 100).toFixed(2)}%
                    </div>
                    <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Return OOS</div>
                  </div>
                  <div>
                    <div className="font-['Rajdhani'] text-lg sm:text-xl font-700 text-primary">{walkForward.robustness?.toUpperCase() ?? "—"}</div>
                    <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Robustesse</div>
                  </div>
                </div>
                {walkForward.splits?.map((split) => (
                  <div key={split.split} className="flex items-center justify-between py-1 sm:py-1.5 border-b border-border/30">
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">Split {split.split}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">
                      Sharpe: {split.oos_metrics?.sharpe_ratio?.toFixed(2) ?? "—"} · Return: {((split.oos_metrics?.total_return ?? 0) * 100).toFixed(2)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50 py-6 sm:py-8 text-center">Cliquer Walk-Forward pour lancer</div>
            )}
          </div>

          {/* Monte Carlo */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">MONTE CARLO SIMULATION</div>
            {monteCarlo ? (
              <div>
                <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-3 sm:mb-4">
                  <div>
                    <div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: (monteCarlo.probability_of_profit ?? 0) > 0.5 ? "#22c55e" : "#ef4444" }}>
                      {((monteCarlo.probability_of_profit ?? 0) * 100).toFixed(0)}%
                    </div>
                    <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Prob. profit</div>
                  </div>
                  <div>
                    <div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: (monteCarlo.probability_of_ruin ?? 0) > 0.1 ? "#ef4444" : "#22c55e" }}>
                      {((monteCarlo.probability_of_ruin ?? 0) * 100).toFixed(1)}%
                    </div>
                    <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Prob. ruine</div>
                  </div>
                  <div>
                    <div className="font-['Rajdhani'] text-lg sm:text-xl font-700 text-primary">{monteCarlo.n_simulations?.toLocaleString() ?? "—"}</div>
                    <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Simulations</div>
                  </div>
                </div>
                {monteCarlo.return_distribution?.percentiles && (
                  <div className="mt-2 sm:mt-3">
                    <div className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-primary mb-1.5 sm:mb-2">DISTRIBUTION DES RETURNS</div>
                    <div className="flex gap-0.5 sm:gap-1">
                      {Object.entries(monteCarlo.return_distribution.percentiles).map(([p, val]) => (
                        <div key={p} className="flex-1 text-center">
                          <div className="h-8 sm:h-12 relative mx-auto" style={{ background: "rgba(0,212,255,0.06)" }}>
                            <div className="absolute bottom-0 left-0 right-0" style={{ height: `${Math.abs((val as number) * 500)}%`, background: (val as number) > 0 ? "#22c55e" : "#ef4444", opacity: 0.6 }} />
                          </div>
                          <div className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground mt-0.5 sm:mt-1">{p}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50 py-6 sm:py-8 text-center">Cliquer Monte Carlo pour lancer</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}