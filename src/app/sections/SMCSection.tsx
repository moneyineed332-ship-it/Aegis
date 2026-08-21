import { useState } from "react";
import { runSmcIctBacktest, runMultiTimeframeBacktest, runMultiScaleCrossoverBacktest, runSmcIctWalkForward, runMultiTimeframeWalkForward } from "../../lib/api";
import { Skeleton } from "../components/ui";
import { TrendingUp, TrendingDown, Minus, Target, Shield, Zap, Layers, RefreshCw } from "lucide-react";

interface BacktestResult {
  strategy: string;
  final_equity: number;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  trade_count: number;
  win_rate: number;
  avg_trade_return: number;
}

export default function SMCSection() {
  const [smcResult, setSmcResult] = useState<BacktestResult | null>(null);
  const [mtfResult, setMtfResult] = useState<BacktestResult | null>(null);
  const [mscResult, setMscResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState<"BTCUSDT" | "ETHUSDT" | "SOLUSDT">("BTCUSDT");
  const [interval, setInterval] = useState<"1h" | "4h">("1h");

  const handleSmcIct = async () => {
    setLoading("smc");
    setError(null);
    try {
      const result = await runSmcIctBacktest(symbol, interval);
      setSmcResult(result as BacktestResult);
    } catch {
      setError("Erreur lors du backtest SMC/ICT");
    } finally {
      setLoading(null);
    }
  };

  const handleMultiTimeframe = async () => {
    setLoading("mtf");
    setError(null);
    try {
      const result = await runMultiTimeframeBacktest(symbol, interval);
      setMtfResult(result as BacktestResult);
    } catch {
      setError("Erreur lors du backtest Multi-Timeframe");
    } finally {
      setLoading(null);
    }
  };

  const handleMultiScale = async () => {
    setLoading("msc");
    setError(null);
    try {
      const result = await runMultiScaleCrossoverBacktest(symbol, interval);
      setMscResult(result as BacktestResult);
    } catch {
      setError("Erreur lors du backtest Multi-Scale Crossover");
    } finally {
      setLoading(null);
    }
  };

  const handleRunAll = async () => {
    setLoading("all");
    setError(null);
    try {
      const [smc, mtf, msc] = await Promise.all([
        runSmcIctBacktest(symbol, interval),
        runMultiTimeframeBacktest(symbol, interval),
        runMultiScaleCrossoverBacktest(symbol, interval),
      ]);
      setSmcResult(smc as BacktestResult);
      setMtfResult(mtf as BacktestResult);
      setMscResult(msc as BacktestResult);
    } catch {
      setError("Erreur lors des backtests SMC/ICT");
    } finally {
      setLoading(null);
    }
  };

  const renderResult = (result: BacktestResult, label: string, icon: React.ReactNode, color: string) => (
    <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
      <div className="flex items-center gap-2 mb-3 sm:mb-4">
        <span style={{ color }}>{icon}</span>
        <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs" style={{ color }}>{label}</div>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-3 sm:mb-4">
        <div>
          <div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: result.total_return > 0 ? "#22c55e" : "#ef4444" }}>
            {result.total_return > 0 ? "+" : ""}{(result.total_return * 100).toFixed(2)}%
          </div>
          <div className="font-['Inter'] text-[12px] text-muted-foreground">Return</div>
        </div>
        <div>
          <div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: result.sharpe_ratio > 0 ? "#22c55e" : "#ef4444" }}>
            {result.sharpe_ratio.toFixed(2)}
          </div>
          <div className="font-['Inter'] text-[12px] text-muted-foreground">Sharpe</div>
        </div>
        <div>
          <div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: "#ef4444" }}>
            {(result.max_drawdown * 100).toFixed(2)}%
          </div>
          <div className="font-['Inter'] text-[12px] text-muted-foreground">Max DD</div>
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between py-1 border-b border-border/30">
          <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Equité finale</span>
          <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">${result.final_equity.toLocaleString("fr-FR")}</span>
        </div>
        <div className="flex items-center justify-between py-1 border-b border-border/30">
          <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Trades</span>
          <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{result.trade_count}</span>
        </div>
        <div className="flex items-center justify-between py-1 border-b border-border/30">
          <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Win Rate</span>
          <span className="font-['JetBrains_Mono'] text-[12px]" style={{ color: result.win_rate > 0.5 ? "#22c55e" : "#ef4444" }}>
            {(result.win_rate * 100).toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center justify-between py-1 border-b border-border/30">
          <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Sortino</span>
          <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{result.sortino_ratio.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between py-1 border-b border-border/30">
          <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Calmar</span>
          <span className="font-['JetBrains_Mono'] text-[12px] text-foreground">{result.calmar_ratio.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between py-1">
          <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">Avg Trade</span>
          <span className="font-['JetBrains_Mono'] text-[12px]" style={{ color: result.avg_trade_return > 0 ? "#22c55e" : "#ef4444" }}>
            {(result.avg_trade_return * 100).toFixed(2)}%
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <section id="smc" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">SMC / ICT</div>
            <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Smart Money Concepts & <span className="text-primary">ICT</span></h2>
            <p className="font-['Inter'] text-xs sm:text-sm text-muted-foreground mt-2">Market Structure, Order Blocks, Fair Value Gaps, Liquidity Zones, Multi-Timeframe Confluence</p>
          </div>
          <div className="flex gap-1.5 sm:gap-2">
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value as "BTCUSDT" | "ETHUSDT" | "SOLUSDT")}
              className="px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary bg-transparent"
            >
              <option value="BTCUSDT">BTCUSDT</option>
              <option value="ETHUSDT">ETHUSDT</option>
              <option value="SOLUSDT">SOLUSDT</option>
            </select>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value as "1h" | "4h")}
              className="px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary bg-transparent"
            >
              <option value="1h">1H</option>
              <option value="4h">4H</option>
            </select>
            <button
              onClick={handleRunAll}
              disabled={loading !== null}
              className="px-3 sm:px-4 py-1.5 sm:py-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary disabled:opacity-50 hover:bg-primary/5 transition-all flex items-center gap-1.5"
            >
              {loading === "all" ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <Zap className="w-3 h-3" />
              )}
              {loading === "all" ? "EN COURS…" : "TOUS LES BACKTESTS"}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 border border-red-500/30 bg-red-500/5 font-['JetBrains_Mono'] text-[12px] text-red-400">
            {error}
          </div>
        )}

        {/* Strategy Cards */}
        <div className="grid lg:grid-cols-3 gap-2 sm:gap-4 mb-6">
          {/* SMC/ICT */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-cyan-400" />
              <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-cyan-400">SMC/ICT STRATEGY</div>
            </div>
            <p className="font-['Inter'] text-[12px] text-muted-foreground mb-3">
              Market Structure (BOS/CHoCH), Order Blocks, Fair Value Gaps, Liquidity Sweeps
            </p>
            <button
              onClick={handleSmcIct}
              disabled={loading !== null}
              className="w-full px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] border border-cyan-400/30 text-cyan-400 disabled:opacity-50 hover:bg-cyan-400/5 transition-all"
            >
              {loading === "smc" ? "EN COURS…" : "LANCER SMC/ICT"}
            </button>
          </div>

          {/* Multi-Timeframe */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center gap-2 mb-2">
              <Layers className="w-4 h-4 text-violet-400" />
              <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-violet-400">MULTI-TIMEFRAME</div>
            </div>
            <p className="font-['Inter'] text-[12px] text-muted-foreground mb-3">
              Confluence 1H/4H/1D, Trend Alignment, Weighted Scoring
            </p>
            <button
              onClick={handleMultiTimeframe}
              disabled={loading !== null}
              className="w-full px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] border border-violet-400/30 text-violet-400 disabled:opacity-50 hover:bg-violet-400/5 transition-all"
            >
              {loading === "mtf" ? "EN COURS…" : "LANCER MTF"}
            </button>
          </div>

          {/* Multi-Scale Crossover */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-4 h-4 text-emerald-400" />
              <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-emerald-400">MULTI-SCALE CROSSOVER</div>
            </div>
            <p className="font-['Inter'] text-[12px] text-muted-foreground mb-3">
              SMA Multi-Échelle, ADX Filter, Score Composite
            </p>
            <button
              onClick={handleMultiScale}
              disabled={loading !== null}
              className="w-full px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] border border-emerald-400/30 text-emerald-400 disabled:opacity-50 hover:bg-emerald-400/5 transition-all"
            >
              {loading === "msc" ? "EN COURS…" : "LANCER MSC"}
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="grid lg:grid-cols-3 gap-2 sm:gap-4">
          {loading ? (
            <>
              <Skeleton className="h-64" />
              <Skeleton className="h-64" />
              <Skeleton className="h-64" />
            </>
          ) : (
            <>
              {smcResult ? renderResult(smcResult, "SMC/ICT", <Target className="w-4 h-4" />, "#06b6d4") : (
                <div className="border border-border p-5 text-center font-['Inter'] text-[12px] text-muted-foreground/50 py-12">
                  Cliquer "LANCER SMC/ICT" pour lancer le backtest
                </div>
              )}
              {mtfResult ? renderResult(mtfResult, "MULTI-TIMEFRAME", <Layers className="w-4 h-4" />, "#8b5cf6") : (
                <div className="border border-border p-5 text-center font-['Inter'] text-[12px] text-muted-foreground/50 py-12">
                  Cliquer "LANCER MTF" pour lancer le backtest
                </div>
              )}
              {mscResult ? renderResult(mscResult, "MULTI-SCALE CROSSOVER", <Shield className="w-4 h-4" />, "#10b981") : (
                <div className="border border-border p-5 text-center font-['Inter'] text-[12px] text-muted-foreground/50 py-12">
                  Cliquer "LANCER MSC" pour lancer le backtest
                </div>
              )}
            </>
          )}
        </div>

        {/* Comparison Table */}
        {smcResult && mtfResult && mscResult && (
          <div className="mt-6 border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">COMPARAISON DES STRATÉGIES</div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="text-left font-['JetBrains_Mono'] text-[12px] text-muted-foreground py-2 pr-4">Métrique</th>
                    <th className="text-right font-['JetBrains_Mono'] text-[12px] text-cyan-400 py-2 px-4">SMC/ICT</th>
                    <th className="text-right font-['JetBrains_Mono'] text-[12px] text-violet-400 py-2 px-4">MTF</th>
                    <th className="text-right font-['JetBrains_Mono'] text-[12px] text-emerald-400 py-2 pl-4">MSC</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: "Return", key: "total_return", format: (v: number) => `${v > 0 ? "+" : ""}${(v * 100).toFixed(2)}%` },
                    { label: "Sharpe", key: "sharpe_ratio", format: (v: number) => v.toFixed(2) },
                    { label: "Max DD", key: "max_drawdown", format: (v: number) => `${(v * 100).toFixed(2)}%` },
                    { label: "Win Rate", key: "win_rate", format: (v: number) => `${(v * 100).toFixed(1)}%` },
                    { label: "Trades", key: "trade_count", format: (v: number) => v.toString() },
                    { label: "Sortino", key: "sortino_ratio", format: (v: number) => v.toFixed(2) },
                    { label: "Calmar", key: "calmar_ratio", format: (v: number) => v.toFixed(2) },
                  ].map(({ label, key, format }) => (
                    <tr key={key} className="border-b border-border/30">
                      <td className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground py-1.5 pr-4">{label}</td>
                      <td className="text-right font-['JetBrains_Mono'] text-[12px] text-cyan-400 py-1.5 px-4">{format(smcResult[key as keyof BacktestResult] as number)}</td>
                      <td className="text-right font-['JetBrains_Mono'] text-[12px] text-violet-400 py-1.5 px-4">{format(mtfResult[key as keyof BacktestResult] as number)}</td>
                      <td className="text-right font-['JetBrains_Mono'] text-[12px] text-emerald-400 py-1.5 pl-4">{format(mscResult[key as keyof BacktestResult] as number)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
