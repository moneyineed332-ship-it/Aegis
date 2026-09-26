import { useState, useEffect } from "react";
import { getAssetClasses, getCommodityPrices, getForexRates, type AssetClasses, type AssetClassEntry, type CommodityPrice, type ForexRates } from "../../lib/api";
import { Skeleton } from "../components/ui";
import { DataTimestamp } from "../components/DataTimestamp";
import { RefreshCw } from "lucide-react";

export default function MultiAssetSection() {
  const [assetClasses, setAssetClasses] = useState<AssetClasses | null>(null);
  const [commodities, setCommodities] = useState<CommodityPrice[]>([]);
  const [forex, setForex] = useState<ForexRates | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    await Promise.all([
      getAssetClasses().then(setAssetClasses).catch(() => setAssetClasses({})),
      getCommodityPrices().then(setCommodities).catch(() => setCommodities([])),
      getForexRates().then(setForex).catch(() => setForex(null)),
    ]);
    setLastUpdated(new Date());
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  useEffect(() => {
    void fetchData();
  }, []);

  return (
    <section id="multi-asset" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="mb-6 sm:mb-10">
          <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">12 — MULTI-ACTIFS</div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Forex, Commodities & <span className="text-primary">Stocks</span></h2>
            <DataTimestamp lastUpdated={lastUpdated} />
            <button onClick={() => void handleRefresh()} disabled={refreshing} className="border border-primary/30 px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] text-primary disabled:opacity-50 hover:bg-primary/5 transition-all flex items-center gap-1.5">
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              RAFRAÎCHIR
            </button>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-4">
          {/* Asset Classes */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">CLASSES D'ACTIFS</div>
            {assetClasses ? (
              <div className="space-y-2.5 sm:space-y-3">
                {Object.entries(assetClasses).map(([key, cls]: [string, AssetClassEntry]) => (
                  <div key={key}>
                    <div className="font-['Inter'] text-xs sm:text-sm text-foreground mb-1">{cls.name}</div>
                    <div className="flex flex-wrap gap-1">
                      {cls.symbols.map((s: string) => (
                        <span key={s} className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] px-1 sm:px-1.5 py-0.5" style={{ background: "rgba(0,212,255,0.06)", color: "#e8edf5", border: "1px solid rgba(0,212,255,0.12)" }}>{s}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Skeleton className="h-4 w-32 mx-auto" />
            )}
          </div>

          {/* Commodities */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">COMMODITIES</div>
            {commodities.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2">
                {commodities.map((c, idx) => (
                  <div key={c.symbol ?? `commodity-${idx}`} className="flex items-center justify-between py-1 sm:py-1.5 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{c.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">${c.price?.toLocaleString("fr-FR") ?? "—"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>

          {/* Forex */}
          <div className="border border-border p-3 sm:p-5 sm:col-span-2 lg:col-span-1" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">FOREX (USD)</div>
            {forex?.rates ? (
              <div className="space-y-1.5 sm:space-y-2">
                {["EUR", "GBP", "JPY", "AUD", "CAD", "CHF"].map((code) => (
                  <div key={code} className="flex items-center justify-between py-1 sm:py-1.5 border-b border-border/30">
                    <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">USD/{code}</span>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">{forex.rates[code]?.toFixed(4) ?? "—"}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}