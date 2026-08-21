import { useState, useEffect } from "react";
import { getAIStatus, aiAnalyzeMarket, aiAssessRisk, aiAnalyzeSentiment, type AIStatus, type AIAnalysis, type AIRiskAssessment, type AISentiment } from "../../lib/api";
import { Brain, Shield, Eye, RefreshCw } from "lucide-react";
import { DataTimestamp } from "../components/DataTimestamp";

export default function AIAnalystSection() {
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [riskAssessment, setRiskAssessment] = useState<AIRiskAssessment | null>(null);
  const [sentiment, setSentiment] = useState<AISentiment | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = async () => {
    await getAIStatus().then(setAiStatus).catch(() => setAiStatus(null));
    setLastUpdated(new Date());
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchStatus();
    setRefreshing(false);
  };

  useEffect(() => {
    void fetchStatus();
  }, []);

  const handleAnalyze = async (type: string) => {
    setLoading(type);
    try {
      if (type === "market") {
        const r = await aiAnalyzeMarket();
        setAnalysis(r);
      } else if (type === "risk") {
        const r = await aiAssessRisk();
        setRiskAssessment(r);
      } else if (type === "sentiment") {
        const r = await aiAnalyzeSentiment();
        setSentiment(r);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur inconnue";
      if (type === "market") setAnalysis({ error: msg });
      else if (type === "risk") setRiskAssessment({ error: msg });
      else if (type === "sentiment") setSentiment({ error: msg });
    }
    setLoading(null);
  };

  return (
    <section id="ai-analyst" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">14 — AI ANALYST</div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">AI <span className="text-primary">Analyst</span></h2>
              <DataTimestamp lastUpdated={lastUpdated} />
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <button onClick={() => void handleRefresh()} disabled={refreshing} className="border border-primary/30 px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] text-primary disabled:opacity-50 hover:bg-primary/5 transition-all flex items-center gap-1.5">
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              RAFRAÎCHIR
            </button>
            <div className="flex items-center gap-1.5 sm:gap-2">
            <span className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${aiStatus?.available ? "bg-green-400" : "bg-red-400"}`} />
            <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">{aiStatus?.available ? aiStatus.provider : "NO KEY"}</span>
          </div>
          </div>
        </div>

        <div className="grid sm:grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-6">
          <button onClick={() => void handleAnalyze("market")} disabled={loading !== null} className="border border-border p-3 sm:p-5 text-left hover:border-primary/30 transition-all disabled:opacity-50" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center gap-2 mb-2 sm:mb-3">
              <Brain className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
              <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">MARCHÉ</span>
            </div>
            <div className="font-['Inter'] text-xs sm:text-sm text-foreground">{loading === "market" ? "Analyse en cours…" : "Analyser le marché"}</div>
          </button>
          <button onClick={() => void handleAnalyze("risk")} disabled={loading !== null} className="border border-border p-3 sm:p-5 text-left hover:border-primary/30 transition-all disabled:opacity-50" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center gap-2 mb-2 sm:mb-3">
              <Shield className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
              <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">RISQUE</span>
            </div>
            <div className="font-['Inter'] text-xs sm:text-sm text-foreground">{loading === "risk" ? "Évaluation en cours…" : "Évaluer les risques"}</div>
          </button>
          <button onClick={() => void handleAnalyze("sentiment")} disabled={loading !== null} className="border border-border p-3 sm:p-5 text-left hover:border-primary/30 transition-all disabled:opacity-50" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center gap-2 mb-2 sm:mb-3">
              <Eye className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
              <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">SENTIMENT</span>
            </div>
            <div className="font-['Inter'] text-xs sm:text-sm text-foreground">{loading === "sentiment" ? "Analyse en cours…" : "Analyser le sentiment"}</div>
          </button>
        </div>

        <div className="grid lg:grid-cols-3 gap-2 sm:gap-4">
          {/* Market Analysis Result */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">ANALYSE MARCHÉ</div>
            {analysis?.error ? (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-red-400">{analysis.error}</div>
            ) : analysis?.regime ? (
              <div className="space-y-2 sm:space-y-3">
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Régime</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">{analysis.regime}</span></div>
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Risque</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs" style={{ color: (analysis.risk_score ?? 5) > 6 ? "#ef4444" : "#22c55e" }}>{analysis.risk_score}/10</span></div>
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Confiance</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">{((analysis.confidence ?? 0) * 100).toFixed(0)}%</span></div>
                {analysis.strategy && <div className="font-['Inter'] text-[12px] sm:text-xs text-foreground mt-2">{analysis.strategy}</div>}
                {analysis.reasoning && <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground/70 mt-1 leading-relaxed">{analysis.reasoning}</div>}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50 py-4 sm:py-6 text-center">Cliquer "MARCHÉ" pour lancer</div>
            )}
          </div>

          {/* Risk Assessment Result */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">ÉVALUATION RISQUE</div>
            {riskAssessment?.error ? (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-red-400">{riskAssessment.error}</div>
            ) : riskAssessment?.overall_risk ? (
              <div className="space-y-2 sm:space-y-3">
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Score</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs" style={{ color: riskAssessment.overall_risk > 6 ? "#ef4444" : "#22c55e" }}>{riskAssessment.overall_risk}/10</span></div>
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Position max</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">{riskAssessment.max_position_pct ?? "—"}%</span></div>
                {riskAssessment.recommendation && <div className="font-['Inter'] text-[12px] sm:text-xs text-foreground mt-2">{riskAssessment.recommendation}</div>}
                {riskAssessment.hedging_suggestion && <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground/70 mt-1">{riskAssessment.hedging_suggestion}</div>}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50 py-4 sm:py-6 text-center">Cliquer "RISQUE" pour lancer</div>
            )}
          </div>

          {/* Sentiment Result */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">SENTIMENT</div>
            {sentiment?.error ? (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-red-400">{sentiment.error}</div>
            ) : sentiment?.overall_sentiment ? (
              <div className="space-y-2 sm:space-y-3">
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Global</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">{sentiment.overall_sentiment}</span></div>
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Confiance</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">{((sentiment.confidence ?? 0) * 100).toFixed(0)}%</span></div>
                {sentiment.fear_greed_interpretation && <div className="font-['Inter'] text-[12px] sm:text-xs text-foreground mt-2">{sentiment.fear_greed_interpretation}</div>}
                {sentiment.volume_analysis && <div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground/70 mt-1">{sentiment.volume_analysis}</div>}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50 py-4 sm:py-6 text-center">Cliquer "SENTIMENT" pour lancer</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}