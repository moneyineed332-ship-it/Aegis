import { useState, useEffect } from "react";
import { getMLRegimeSummary, predictRegime, trainMLRegime, type MLRegimeSummary, type MLRegimePrediction } from "../../lib/api";
import { DataTimestamp } from "../components/DataTimestamp";
import { RefreshCw } from "lucide-react";

export default function MLRegimeSection() {
  const [summary, setSummary] = useState<MLRegimeSummary | null>(null);
  const [prediction, setPrediction] = useState<MLRegimePrediction | null>(null);
  const [training, setTraining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    await Promise.all([
      getMLRegimeSummary().then(setSummary).catch(() => setSummary(null)),
      predictRegime().then(setPrediction).catch(() => setPrediction(null)),
    ]);
    setLastUpdated(new Date());
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    await fetchData();
    setRefreshing(false);
  };

  useEffect(() => {
    void fetchData();
  }, []);

  const handleTrain = async () => {
    setTraining(true);
    setError(null);
    try {
      await trainMLRegime();
      const newSummary = await getMLRegimeSummary();
      setSummary(newSummary);
      const newPrediction = await predictRegime();
      setPrediction(newPrediction);
    } catch {
      setError("Entraînement échoué — données insuffisantes");
    } finally {
      setTraining(false);
    }
  };

  const regimeColors: Record<string, string> = {
    bull_trend: "#22c55e", bear_trend: "#ef4444", range: "#f59e0b",
    high_volatility: "#f97316", low_volatility: "#06b6d4",
    capitulation: "#dc2626", euphoria: "#a855f7",
  };

  return (
    <section id="ml-regime" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">08 — ML RÉGIME</div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Prédiction <span className="text-primary">Machine Learning</span></h2>
              <DataTimestamp lastUpdated={lastUpdated} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => void handleRefresh()} disabled={refreshing} className="border border-primary/30 px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] text-primary disabled:opacity-50 hover:bg-primary/5 transition-all flex items-center gap-1.5">
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              RAFRAÎCHIR
            </button>
            <button onClick={handleTrain} disabled={training} className="px-3 sm:px-4 py-1.5 sm:py-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary disabled:opacity-50 hover:bg-primary/5 transition-all">
              {training ? "ENTRAÎNEMENT…" : "ENTRAÎNER LE MODÈLE"}
            </button>
          </div>
        </div>

        {error && <div className="mb-3 sm:mb-4 p-2 sm:p-3 border border-red-400/30 bg-red-400/5 font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400">{error}</div>}

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-4">
          {/* Model Status */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">MODÈLE</div>
            <div className="flex items-center gap-2 mb-2 sm:mb-3">
              <span className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${summary?.trained ? "bg-green-400" : "bg-muted-foreground/30"}`} />
              <span className="font-['Inter'] text-xs sm:text-sm text-foreground">{summary?.trained ? "Entraîné" : "Non entraîné"}</span>
            </div>
            <div className="space-y-1.5 sm:space-y-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">
              <div>Features: {summary?.n_features ?? 0}</div>
              <div>Classes: {summary?.n_classes ?? 0}</div>
              <div className="truncate">Nom: {summary?.feature_names?.join(", ") ?? "—"}</div>
            </div>
          </div>

          {/* Current Prediction */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">PRÉDICTION ACTUELLE</div>
            {prediction?.ml_prediction ? (
              <div>
                <div className="font-['Rajdhani'] text-2xl sm:text-3xl font-700 mb-1.5 sm:mb-2" style={{ color: regimeColors[prediction.ml_prediction.regime] ?? "#00d4ff" }}>
                  {prediction.ml_prediction.regime?.replace("_", " ").toUpperCase() ?? "N/A"}
                </div>
                <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground mb-2 sm:mb-3">
                  Confiance: {(prediction.ml_prediction.confidence * 100).toFixed(1)}%
                </div>
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">Rule-based:</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs" style={{ color: regimeColors[prediction.rule_based?.regime] ?? "#8899b0" }}>
                    {prediction.rule_based?.regime?.replace("_", " ").toUpperCase() ?? "N/A"}
                  </span>
                  {prediction.agreement ? (
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-green-400">✓</span>
                  ) : (
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-yellow-400">✗</span>
                  )}
                </div>
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de prédiction</div>
            )}
          </div>

          {/* Feature Importance */}
          <div className="border border-border p-3 sm:p-5 sm:col-span-2 lg:col-span-1" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">FEATURE IMPORTANCE</div>
            {summary?.feature_importance && Object.keys(summary.feature_importance).length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {Object.entries(summary.feature_importance)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 6)
                  .map(([name, value]) => (
                    <div key={name} className="flex items-center gap-1.5 sm:gap-2">
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground w-16 sm:w-20 truncate">{name}</span>
                      <div className="flex-1 h-1 sm:h-1.5 rounded-full" style={{ background: "rgba(0,212,255,0.1)" }}>
                        <div className="h-full rounded-full transition-all" style={{ width: `${value * 100}%`, background: "#00d4ff" }} />
                      </div>
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground w-8 sm:w-10 text-right">{(value * 100).toFixed(0)}%</span>
                    </div>
                  ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Entraîner le modèle d'abord</div>
            )}
          </div>
        </div>

        {/* Probability Distribution */}
        {prediction?.ml_prediction?.probabilities && (
          <div className="border border-border p-3 sm:p-5 mt-2 sm:mt-4" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">DISTRIBUTION DES PROBABILITÉS</div>
            <div className="grid grid-cols-7 gap-1 sm:gap-2">
              {Object.entries(prediction.ml_prediction.probabilities).map(([regime, prob]) => (
                <div key={regime} className="text-center">
                  <div className="h-16 sm:h-24 relative mx-auto w-full" style={{ background: "rgba(0,212,255,0.06)", border: "1px solid rgba(0,212,255,0.12)" }}>
                    <div className="absolute bottom-0 left-0 right-0 transition-all" style={{ height: `${(prob as number) * 100}%`, background: regimeColors[regime] ?? "#00d4ff", opacity: 0.7 }} />
                    <div className="absolute inset-0 flex items-center justify-center font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground z-10">{((prob as number) * 100).toFixed(0)}%</div>
                  </div>
                  <div className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground mt-0.5 sm:mt-1 truncate">{regime.replace("_", " ")}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}