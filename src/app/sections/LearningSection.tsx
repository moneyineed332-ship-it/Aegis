import { useCallback, useEffect, useState } from "react";
import { BookOpen, TrendingUp, Trophy, BarChart3, RefreshCw } from "lucide-react";
import { Card, CardHeader, Badge, Stat, EmptyState, Skeleton } from "../components/ui";
import { useToast } from "../components/Toast";
import {
  getLearningSummary,
  getStrategyStats,
  getTradeOutcomes,
  type LearningSummary,
  type StrategyStats,
  type TradeOutcome,
} from "../../lib/api";

export default function LearningSection() {
  const { success, error: toastError } = useToast();
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [strategies, setStrategies] = useState<StrategyStats[]>([]);
  const [trades, setTrades] = useState<TradeOutcome[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [sum, stats, outcomes] = await Promise.allSettled([
        getLearningSummary(),
        getStrategyStats(),
        getTradeOutcomes(30),
      ]);
      if (sum.status === "fulfilled") setSummary(sum.value);
      if (stats.status === "fulfilled") setStrategies(stats.value);
      if (outcomes.status === "fulfilled") setTrades(outcomes.value);
      setLastUpdated(new Date());
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await fetchAll();
      success("Donnees actualisees");
    } catch {
      toastError("Erreur lors de l'actualisation");
    } finally {
      setLoading(false);
    }
  };

  if (!summary) return <Card><EmptyState icon={<BookOpen className="w-8 h-8" />} title="Chargement..." description="Recuperation des donnees d'apprentissage" /></Card>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Apprentissage" icon={<BookOpen className="w-4 h-4" />} color="#00d4ff" action={<button onClick={handleRefresh} disabled={loading} className="p-1.5 rounded-lg hover:bg-white/5 transition-colors" aria-label="Actualiser"><RefreshCw className={`w-4 h-4 text-muted-foreground ${loading ? "animate-spin" : ""}`} /></button>} />
        {lastUpdated && <p className="text-xs text-muted-foreground/60 mb-4">Derniere MAJ: {lastUpdated.toLocaleTimeString("fr-FR")}</p>}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Strategies suivies" value={summary.strategies_tracked} />
          <Stat label="Total trades" value={summary.total_trades} />
          <Stat label="Win rate global" value={`${(summary.overall_win_rate * 100).toFixed(1)}%`} />
          <Stat label="PnL realise" value={`${summary.total_realized_pnl.toFixed(2)} USDT`} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Performance par strategie" icon={<Trophy className="w-4 h-4" />} color="#fbbf24" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground border-b border-border">
                <th className="text-left py-2 px-3">Strategie</th>
                <th className="text-right py-2 px-3">Score</th>
                <th className="text-right py-2 px-3">Trades</th>
                <th className="text-right py-2 px-3">Win Rate</th>
                <th className="text-right py-2 px-3">PF</th>
                <th className="text-right py-2 px-3">PnL</th>
              </tr>
            </thead>
            <tbody>
              {strategies.length === 0 ? (
                <tr><td colSpan={6} className="py-8 text-center text-muted-foreground/60">Aucune donnee de strategie</td></tr>
              ) : strategies.map((s) => (
                <tr key={s.strategy_id} className="border-b border-border/50 hover:bg-card/30">
                  <td className="py-2 px-3 font-mono text-foreground">{s.strategy_id}</td>
                  <td className="py-2 px-3 text-right">
                    <Badge variant={s.score >= 60 ? "success" : s.score >= 30 ? "warning" : "danger"}>{s.score.toFixed(0)}</Badge>
                  </td>
                  <td className="py-2 px-3 text-right text-foreground/80">{s.total_trades}</td>
                  <td className="py-2 px-3 text-right text-foreground/80">{(s.win_rate * 100).toFixed(0)}%</td>
                  <td className="py-2 px-3 text-right text-foreground/80">{s.profit_factor.toFixed(1)}</td>
                  <td className={`py-2 px-3 text-right font-mono ${s.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>{s.total_pnl >= 0 ? "+" : ""}{s.total_pnl.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardHeader title="Derniers trades" icon={<BarChart3 className="w-4 h-4" />} color="#8b5cf6" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground border-b border-border">
                <th className="text-left py-2 px-3">Symbol</th>
                <th className="text-left py-2 px-3">Strategie</th>
                <th className="text-left py-2 px-3">Side</th>
                <th className="text-right py-2 px-3">Entree</th>
                <th className="text-right py-2 px-3">Sortie</th>
                <th className="text-right py-2 px-3">PnL %</th>
                <th className="text-left py-2 px-3">Statut</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr><td colSpan={7} className="py-8 text-center text-muted-foreground/60">Aucun trade enregistre</td></tr>
              ) : trades.map((t) => (
                <tr key={t.id} className="border-b border-border/50 hover:bg-card/30">
                  <td className="py-2 px-3 text-foreground">{t.symbol}</td>
                  <td className="py-2 px-3 font-mono text-muted-foreground text-xs">{t.strategy}</td>
                  <td className="py-2 px-3"><Badge variant={t.side === "buy" ? "success" : "danger"}>{t.side}</Badge></td>
                  <td className="py-2 px-3 text-right text-foreground/80">{t.entry_price.toFixed(2)}</td>
                  <td className="py-2 px-3 text-right text-foreground/80">{t.exit_price?.toFixed(2) ?? "—"}</td>
                  <td className={`py-2 px-3 text-right font-mono ${(t.pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct.toFixed(2)}%` : "—"}
                  </td>
                  <td className="py-2 px-3"><Badge variant={t.status === "open" ? "info" : "default"}>{t.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
