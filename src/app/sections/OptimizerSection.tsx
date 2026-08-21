import { useState } from "react";
import { postApi, type OptimizerResult, type OptimizerRankingItem } from "../../lib/api";

export default function OptimizerSection() {
  const [results, setResults] = useState<OptimizerResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleOptimize = async () => {
    setLoading(true);
    try {
      setResults(await postApi<OptimizerResult>("/api/v1/optimizer/compare"));
    } catch {
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section id="optimizer" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">13 — OPTIMIZER</div>
            <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Grid Search <span className="text-primary">Multi-Stratégies</span></h2>
          </div>
          <button onClick={handleOptimize} disabled={loading} className="px-3 sm:px-4 py-1.5 sm:py-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary disabled:opacity-50 hover:bg-primary/5 transition-all">
            {loading ? "OPTIMISATION…" : "OPTIMISER TOUT"}
          </button>
        </div>

        {results?.ranking && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4">
            {results.ranking.map((s: OptimizerRankingItem, i: number) => (
              <div key={s.strategy} className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
                <div className="flex items-center justify-between mb-2 sm:mb-3">
                  <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">#{i + 1}</div>
                  {i === 0 && <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] px-1 sm:px-1.5 py-0.5 bg-primary/20 text-primary">BEST</span>}
                </div>
                <div className="font-['Inter'] text-xs sm:text-sm text-foreground mb-2 sm:mb-3">{s.strategy.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}</div>
                <div className="space-y-1 sm:space-y-1.5 font-['JetBrains_Mono'] text-[12px] sm:text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Sharpe</span>
                    <span style={{ color: s.sharpe > 0 ? "#22c55e" : "#ef4444" }}>{s.sharpe?.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Return</span>
                    <span style={{ color: s.return > 0 ? "#22c55e" : "#ef4444" }}>{((s.return ?? 0) * 100).toFixed(2)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Drawdown</span>
                    <span className="text-red-400">{((s.drawdown ?? 0) * 100).toFixed(2)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Trades</span>
                    <span className="text-foreground">{s.trades}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {results?.best_overall && (
          <div className="mt-3 sm:mt-4 p-3 sm:p-4 border border-primary/30 bg-primary/5 font-['JetBrains_Mono'] text-[12px] sm:text-sm text-primary">
            Meilleure stratégie: {results.best_overall.replace(/_/g, " ").toUpperCase()}
          </div>
        )}
      </div>
    </section>
  );
}