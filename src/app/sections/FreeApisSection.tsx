import { useState, useEffect } from "react";
import {
  getCoingeckoGlobal, getCoingeckoTrending, getCoingeckoGainers, getCoingeckoLosers,
  getDefillamaTVL, getDefillamaYields, getPerpFinderFunding, getPerpFinderLiquidations,
  getMempoolFees, getPolymarketCrypto,
  type CoingeckoGlobal, type CoingeckoTrending, type CoingeckoGainerLoser,
  type DefillamaTVL, type DefillamaYield, type PerpFinderFunding,
  type PerpFinderLiquidation, type MempoolFees, type PolymarketCrypto,
} from "../../lib/api";
import { Skeleton } from "../components/ui";
import { DataTimestamp } from "../components/DataTimestamp";
import { RefreshCw } from "lucide-react";

export default function FreeApisSection() {
  const [global, setGlobal] = useState<CoingeckoGlobal | null>(null);
  const [trending, setTrending] = useState<CoingeckoTrending[]>([]);
  const [gainers, setGainers] = useState<CoingeckoGainerLoser[]>([]);
  const [losers, setLosers] = useState<CoingeckoGainerLoser[]>([]);
  const [defillama, setDefillama] = useState<DefillamaTVL | null>(null);
  const [yields, setYields] = useState<DefillamaYield[]>([]);
  const [funding, setFunding] = useState<PerpFinderFunding[]>([]);
  const [liquidations, setLiquidations] = useState<PerpFinderLiquidation[]>([]);
  const [mempool, setMempool] = useState<MempoolFees | null>(null);
  const [polymarket, setPolymarket] = useState<PolymarketCrypto[]>([]);
  const [apiError, setApiError] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const settle = <T,>(p: Promise<T>) => p.then((v) => ({ ok: true as const, v })).catch(() => ({ ok: false as const, v: null as T }));

    const [g, tr, ga, lo, df, yf, fd, li, mp, pm] = await Promise.allSettled([
      settle(getCoingeckoGlobal()),
      settle(getCoingeckoTrending()),
      settle(getCoingeckoGainers()),
      settle(getCoingeckoLosers()),
      settle(getDefillamaTVL()),
      settle(getDefillamaYields()),
      settle(getPerpFinderFunding()),
      settle(getPerpFinderLiquidations()),
      settle(getMempoolFees()),
      settle(getPolymarketCrypto()),
    ]);

    const extract = <T,>(r: PromiseSettledResult<{ ok: boolean; v: T }>): T | null =>
      r.status === "fulfilled" && r.value.ok ? r.value.v : null;

    setGlobal(extract(g));
    setTrending(extract(tr) ?? []);
    setGainers(extract(ga) ?? []);
    setLosers(extract(lo) ?? []);
    setDefillama(extract(df));
    setYields(extract(yf) ?? []);
    setFunding(extract(fd) ?? []);
    setLiquidations(extract(li) ?? []);
    setMempool(extract(mp));
    setPolymarket(extract(pm) ?? []);

    const anyFailed = [g, tr, ga, lo, df, yf, fd, li, mp, pm].some((r) => r.status === "rejected" || (r.status === "fulfilled" && !r.value.ok));
    setApiError(anyFailed);
    setLastUpdated(new Date());
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setApiError(false);
    await load();
    setRefreshing(false);
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <section id="free-apis" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="mb-6 sm:mb-10">
          <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">15 — FREE APIs</div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Données <span className="text-primary">En Temps Réel</span></h2>
            <DataTimestamp lastUpdated={lastUpdated} />
            <button onClick={() => void handleRefresh()} disabled={refreshing} className="border border-primary/30 px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] text-primary disabled:opacity-50 hover:bg-primary/5 transition-all flex items-center gap-1.5">
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              RAFRAÎCHIR
            </button>
            {apiError && <span className="font-['JetBrains_Mono'] text-[12px] px-2 py-1 border border-red-400/30 text-red-400 bg-red-400/5">CERTAINES APIS INDISPONIBLES</span>}
          </div>
        </div>

        {/* Row 1: CoinGecko Global + Trending */}
        <div className="grid sm:grid-cols-2 gap-2 sm:gap-4 mb-2 sm:mb-4">
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">COINGECKO GLOBAL</div>
            {global?.total_market_cap_usd ? (
              <div className="grid grid-cols-2 gap-2 sm:gap-4">
                <div><div className="font-['Rajdhani'] text-lg sm:text-xl font-700 text-foreground">${(global.total_market_cap_usd / 1e12).toFixed(2)}T</div><div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Market Cap</div></div>
                <div><div className="font-['Rajdhani'] text-lg sm:text-xl font-700 text-foreground">{global.btc_dominance?.toFixed(1)}%</div><div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">BTC Dom.</div></div>
                <div><div className="font-['Rajdhani'] text-lg sm:text-xl font-700 text-foreground">{global.total_volume_usd != null ? `${(global.total_volume_usd / 1e9).toFixed(1)}B` : "—"}</div><div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">Volume 24h</div></div>
                <div><div className="font-['Rajdhani'] text-lg sm:text-xl font-700" style={{ color: (global.market_cap_change_24h ?? 0) > 0 ? "#22c55e" : "#ef4444" }}>{global.market_cap_change_24h?.toFixed(2)}%</div><div className="font-['Inter'] text-[12px] sm:text-[12px] text-muted-foreground">24h Change</div></div>
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">TENDANCES</div>
            {trending.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {trending.slice(0, 6).map((t, i) => (
                  <div key={i} className="flex items-center justify-between py-0.5 sm:py-1 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{t.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground">Rank #{t.market_cap_rank}</span>
                  </div>
                ))}
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
        </div>

        {/* Row 2: Gainers + Losers */}
        <div className="grid sm:grid-cols-2 gap-2 sm:gap-4 mb-2 sm:mb-4">
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-green-400 mb-3 sm:mb-4">TOP GAINERS 24H</div>
            {gainers.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {gainers.slice(0, 5).map((g, i) => (
                  <div key={i} className="flex items-center justify-between py-0.5 sm:py-1 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{g.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-green-400">+{g.change_24h?.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400 mb-3 sm:mb-4">TOP LOSERS 24H</div>
            {losers.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {losers.slice(0, 5).map((l, i) => (
                  <div key={i} className="flex items-center justify-between py-0.5 sm:py-1 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{l.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-red-400">{l.change_24h?.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
        </div>

        {/* Row 3: DeFi TVL + Yields + PerpFinder */}
        <div className="grid sm:grid-cols-3 gap-2 sm:gap-4 mb-2 sm:mb-4">
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">DeFi TVL</div>
            {defillama?.total_tvl ? (
              <div>
                <div className="font-['Rajdhani'] text-xl sm:text-2xl font-700 text-foreground">${(defillama.total_tvl / 1e9).toFixed(2)}B</div>
                <div className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] mt-1" style={{ color: (defillama.change_pct ?? 0) > 0 ? "#22c55e" : "#ef4444" }}>{defillama.change_pct}% (24h)</div>
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">TOP YIELDS</div>
            {yields.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {yields.slice(0, 5).map((y, i) => (
                  <div key={i} className="flex items-center justify-between py-0.5 sm:py-1 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-[12px] text-foreground">{y.project} · {y.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-primary">{y.apy?.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">FUNDING RATES</div>
            {funding.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {funding.slice(0, 5).map((f, i) => (
                  <div key={i} className="flex items-center justify-between py-0.5 sm:py-1 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-[12px] text-foreground">{f.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px]" style={{ color: (f.rate ?? 0) > 0 ? "#22c55e" : "#ef4444" }}>{((f.rate ?? 0) * 100).toFixed(4)}%</span>
                  </div>
                ))}
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
        </div>

        {/* Row 4: Liquidations + Mempool + Polymarket */}
        <div className="grid sm:grid-cols-3 gap-2 sm:gap-4">
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">LIQUIDATIONS 24H</div>
            {liquidations.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {liquidations.slice(0, 5).map((l, i) => (
                  <div key={i} className="flex items-center justify-between py-0.5 sm:py-1 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-[12px] text-foreground">{l.symbol}</span>
                    <div className="flex gap-2">
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-green-400">L:{l.longs?.toLocaleString()}</span>
                      <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-red-400">S:{l.shorts?.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">BITCOIN MEMPOOL</div>
            {mempool?.fastest_fee ? (
              <div className="space-y-1.5 sm:space-y-2">
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">Rapide</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">{mempool.fastest_fee} sat/vB</span></div>
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">30 min</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">{mempool.half_hour_fee} sat/vB</span></div>
                <div className="flex justify-between"><span className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground">1 heure</span><span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground">{mempool.hour_fee} sat/vB</span></div>
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">POLYMARKET CRYPTO</div>
            {polymarket.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {polymarket.slice(0, 4).map((p, i) => (
                  <div key={i} className="py-0.5 sm:py-1 border-b border-border/30">
                    <div className="font-['Inter'] text-[12px] sm:text-[12px] text-foreground truncate">{p.question}</div>
                    <div className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground">Vol: ${p.volume?.toLocaleString()}</div>
                  </div>
                ))}
              </div>
            ) : <div className="space-y-3"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-3/4" /><Skeleton className="h-3 w-5/6" /></div>}
          </div>
        </div>
      </div>
    </section>
  );
}