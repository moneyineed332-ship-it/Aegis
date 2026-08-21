import { useState, useEffect, useCallback } from "react";
import { BookOpen, RefreshCw, Download, TrendingUp, TrendingDown, Minus, Target, Zap, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { getJournalAnalysis, exportDashboardCSV, exportDashboardJSON, type JournalAnalysis, type JournalOutcome } from "../../lib/api";
import { Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";

function actionLabel(action: string): string {
  const map: Record<string, string> = { buy: "ACHAT", sell: "VENTE", long: "LONG", short: "SHORT", wait: "ATTENTE", research: "RECHERCHE", unknown: "INCONNU" };
  return map[action] ?? action.toUpperCase();
}

function actionColor(action: string): string {
  if (["buy", "long"].includes(action)) return "text-emerald-400 bg-emerald-400/10";
  if (["sell", "short"].includes(action)) return "text-red-400 bg-red-400/10";
  if (action === "wait") return "text-amber-400 bg-amber-400/10";
  return "text-cyan-400 bg-cyan-400/10";
}

function outcomeIcon(outcome: string) {
  if (outcome === "correct_entry" || outcome === "good_wait") return <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />;
  if (outcome === "wrong_entry" || outcome === "missed_opportunity") return <XCircle className="w-3.5 h-3.5 text-red-400" />;
  return <Minus className="w-3.5 h-3.5 text-muted-foreground" />;
}

function outcomeLabel(outcome: string): string {
  const map: Record<string, string> = {
    correct_entry: "Correct", wrong_entry: "Incorrect", neutral_entry: "Neutre",
    good_wait: "Bon attente", missed_opportunity: "Manqué", neutral_wait: "Neutre", unknown: "Inconnu",
  };
  return map[outcome] ?? outcome;
}

function gradeColor(grade: string): string {
  if (grade.startsWith("A")) return "text-emerald-400";
  if (grade.startsWith("B")) return "text-cyan-400";
  if (grade.startsWith("C")) return "text-amber-400";
  if (grade.startsWith("D")) return "text-red-400";
  return "text-muted-foreground";
}

export default function JournalSection() {
  const [data, setData] = useState<JournalAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getJournalAnalysis();
      setData(result);
    } catch {
      toast.error("Erreur lors du chargement du journal");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleExportCSV = async () => {
    try {
      const blob = await exportDashboardCSV();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aegis-journal-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("CSV exporté");
    } catch {
      toast.error("Erreur lors de l'export CSV");
    }
  };

  const handleExportJSON = async () => {
    try {
      const blob = await exportDashboardJSON();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aegis-journal-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("JSON exporté");
    } catch {
      toast.error("Erreur lors de l'export JSON");
    }
  };

  const outcomes = data?.outcomes ?? [];
  const byAction = data?.by_action ?? {};
  const feedback = data?.feedback;

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(0,255,136,0.1)" }}>
            <BookOpen className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className="font-['Rajdhani'] font-bold text-2xl text-foreground">Journal de Décisions</h2>
            <p className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Analyse des performances et historique des trades</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleExportCSV} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border hover:border-primary/30 font-['JetBrains_Mono'] text-[12px] text-muted-foreground hover:text-foreground transition-all">
            <Download className="w-3 h-3" /> CSV
          </button>
          <button onClick={handleExportJSON} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border hover:border-primary/30 font-['JetBrains_Mono'] text-[12px] text-muted-foreground hover:text-foreground transition-all">
            <Download className="w-3 h-3" /> JSON
          </button>
          <button onClick={() => void load()} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary/30 font-['JetBrains_Mono'] text-[12px] text-primary hover:bg-primary/5 transition-all disabled:opacity-50">
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Rafraîchir
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" />
          </div>
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : data ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-xl p-4 border border-border" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider mb-2">PRÉCISION</div>
              <div className="font-['Rajdhani'] font-bold text-3xl text-emerald-400">{data.accuracy != null ? `${(data.accuracy * 100).toFixed(0)}%` : "—"}</div>
              <div className="font-['Inter'] text-[12px] text-muted-foreground mt-1">{data.total_decisions} décisions</div>
            </div>
            <div className="rounded-xl p-4 border border-border" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider mb-2">PNL MOYEN</div>
              <div className={`font-['Rajdhani'] font-bold text-3xl ${(data.avg_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {data.avg_pnl != null ? `${data.avg_pnl >= 0 ? "+" : ""}${(data.avg_pnl * 100).toFixed(2)}%` : "—"}
              </div>
            </div>
            <div className="rounded-xl p-4 border border-border" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider mb-2">PNL TOTAL</div>
              <div className={`font-['Rajdhani'] font-bold text-3xl ${(data.total_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {data.total_pnl != null ? `${data.total_pnl >= 0 ? "+" : ""}${(data.total_pnl * 100).toFixed(2)}%` : "—"}
              </div>
            </div>
            <div className="rounded-xl p-4 border border-border" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider mb-2">ÉVALUATION</div>
              <div className={`font-['Rajdhani'] font-bold text-2xl ${gradeColor(feedback?.grade ?? "")}`}>{feedback?.grade ?? "N/A"}</div>
            </div>
          </div>

          {/* Feedback */}
          {feedback && (feedback.strengths.length > 0 || feedback.weaknesses.length > 0) && (
            <div className="rounded-xl p-4 border border-border" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider mb-3">RETOUR D'ANALYSE</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {feedback.strengths.length > 0 && (
                  <div>
                    <div className="font-['JetBrains_Mono'] text-[11px] text-emerald-400 mb-2 flex items-center gap-1.5"><TrendingUp className="w-3 h-3" /> Points forts</div>
                    <ul className="space-y-1">
                      {feedback.strengths.map((s, i) => (
                        <li key={i} className="font-['Inter'] text-[12px] text-muted-foreground flex items-start gap-2">
                          <CheckCircle className="w-3 h-3 text-emerald-400 mt-0.5 shrink-0" />{s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {feedback.weaknesses.length > 0 && (
                  <div>
                    <div className="font-['JetBrains_Mono'] text-[11px] text-red-400 mb-2 flex items-center gap-1.5"><AlertTriangle className="w-3 h-3" /> Points faibles</div>
                    <ul className="space-y-1">
                      {feedback.weaknesses.map((w, i) => (
                        <li key={i} className="font-['Inter'] text-[12px] text-muted-foreground flex items-start gap-2">
                          <XCircle className="w-3 h-3 text-red-400 mt-0.5 shrink-0" />{w}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* By-Action Breakdown */}
          {Object.keys(byAction).length > 0 && (
            <div className="rounded-xl p-4 border border-border" style={{ background: "rgba(11,18,32,0.7)" }}>
              <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider mb-3">RÉPARTITION PAR ACTION</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(byAction).map(([action, stats]) => (
                  <div key={action} className="rounded-lg p-3 border border-border/50" style={{ background: "rgba(11,18,32,0.5)" }}>
                    <div className={`font-['JetBrains_Mono'] text-[11px] font-medium mb-2 ${actionColor(action).split(" ")[0]}`}>{actionLabel(action)}</div>
                    <div className="space-y-1">
                      <div className="flex justify-between">
                        <span className="font-['Inter'] text-[10px] text-muted-foreground/60">Nombre</span>
                        <span className="font-['JetBrains_Mono'] text-[11px] text-foreground">{stats.count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="font-['Inter'] text-[10px] text-muted-foreground/60">Précision</span>
                        <span className="font-['JetBrains_Mono'] text-[11px] text-foreground">{(stats.accuracy * 100).toFixed(0)}%</span>
                      </div>
                      {stats.avg_pnl != null && (
                        <div className="flex justify-between">
                          <span className="font-['Inter'] text-[10px] text-muted-foreground/60">PnL moy.</span>
                          <span className={`font-['JetBrains_Mono'] text-[11px] ${stats.avg_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {stats.avg_pnl >= 0 ? "+" : ""}{(stats.avg_pnl * 100).toFixed(2)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Decision History */}
          <div className="rounded-xl border border-border overflow-hidden" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="p-4 border-b border-border">
              <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">HISTORIQUE DES DÉCISIONS</div>
            </div>
            {outcomes.length === 0 ? (
              <div className="text-center py-12">
                <BookOpen className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                <p className="font-['Inter'] text-sm text-muted-foreground">Aucune décision enregistrée</p>
                <p className="font-['Inter'] text-[11px] text-muted-foreground/50 mt-1">Les décisions apparaîtront ici une fois que l'agent aura pris des positions</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">HEURE</th>
                      <th className="text-left p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">SYMBOLE</th>
                      <th className="text-left p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">ACTION</th>
                      <th className="text-left p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">STRATÉGIE</th>
                      <th className="text-left p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">RÉGIME</th>
                      <th className="text-right p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">PRIX D'ENTRÉE</th>
                      <th className="text-right p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">PNL</th>
                      <th className="text-center p-3 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/60 tracking-wider">RÉSULTAT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outcomes.map((o: JournalOutcome) => (
                      <tr key={o.decision_id} className="border-b border-border/50 hover:bg-white/[0.02] transition-colors">
                        <td className="p-3 font-['JetBrains_Mono'] text-[11px] text-muted-foreground">
                          {o.decision_time ? new Date(o.decision_time).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"}
                        </td>
                        <td className="p-3 font-['JetBrains_Mono'] text-[11px] text-foreground font-medium">{o.symbol}</td>
                        <td className="p-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-['JetBrains_Mono'] text-[10px] font-medium ${actionColor(o.action)}`}>
                            {["buy", "long"].includes(o.action) ? <TrendingUp className="w-2.5 h-2.5" /> : ["sell", "short"].includes(o.action) ? <TrendingDown className="w-2.5 h-2.5" /> : <Minus className="w-2.5 h-2.5" />}
                            {actionLabel(o.action)}
                          </span>
                        </td>
                        <td className="p-3 font-['JetBrains_Mono'] text-[11px] text-cyan-400">{o.strategy ?? "—"}</td>
                        <td className="p-3 font-['JetBrains_Mono'] text-[11px] text-muted-foreground">{o.regime ?? "—"}</td>
                        <td className="p-3 text-right font-['JetBrains_Mono'] text-[11px] text-foreground">
                          {o.entry_price != null ? `$${o.entry_price.toLocaleString()}` : "—"}
                        </td>
                        <td className="p-3 text-right font-['JetBrains_Mono'] text-[11px] font-medium">
                          {o.pnl_since_decision != null ? (
                            <span className={o.pnl_since_decision >= 0 ? "text-emerald-400" : "text-red-400"}>
                              {o.pnl_since_decision >= 0 ? "+" : ""}{(o.pnl_since_decision * 100).toFixed(2)}%
                            </span>
                          ) : "—"}
                        </td>
                        <td className="p-3 text-center">
                          <span className="inline-flex items-center gap-1.5">
                            {outcomeIcon(o.outcome)}
                            <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground">{outcomeLabel(o.outcome)}</span>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="text-center py-12 rounded-xl border border-border" style={{ background: "rgba(11,18,32,0.5)" }}>
          <BookOpen className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
          <p className="font-['Inter'] text-sm text-muted-foreground">Aucune donnée disponible</p>
        </div>
      )}
    </section>
  );
}
