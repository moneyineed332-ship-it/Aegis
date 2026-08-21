import { useState, useEffect } from "react";
import { getBinanceTestnetStatus, getBinanceTestnetPrice, type BinanceTestnetStatus, type BinanceTestnetPrice } from "../../lib/api";
import { Skeleton } from "../components/ui";
import { DataTimestamp } from "../components/DataTimestamp";
import { RefreshCw } from "lucide-react";

export default function BinanceTestnetSection() {
  const [status, setStatus] = useState<BinanceTestnetStatus | null>(null);
  const [btcPrice, setBtcPrice] = useState<BinanceTestnetPrice | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    await Promise.all([
      getBinanceTestnetStatus().then(setStatus).catch(() => setStatus(null)),
      getBinanceTestnetPrice().then(setBtcPrice).catch(() => setBtcPrice(null)),
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
    <section id="testnet" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">11 — BINANCE TESTNET</div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Trading <span className="text-primary">Testnet</span></h2>
              <DataTimestamp lastUpdated={lastUpdated} />
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <button onClick={() => void handleRefresh()} disabled={refreshing} className="border border-primary/30 px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] text-primary disabled:opacity-50 hover:bg-primary/5 transition-all flex items-center gap-1.5">
              <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
              RAFRAÎCHIR
            </button>
            <div className="flex items-center gap-1.5 sm:gap-2">
            <span className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${status?.connected ? "bg-green-400" : "bg-red-400"}`} />
            <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-muted-foreground">{status?.connected ? "CONNECTÉ" : "DÉCONNECTÉ"}</span>
          </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4">
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-2 sm:mb-3">CONNECTION</div>
            <div className="space-y-1.5 sm:space-y-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status</span>
                <span className={status?.connected ? "text-green-400" : "text-red-400"}>{status?.connected ? "OK" : "ERROR"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Testnet</span>
                <span className="text-foreground">{status?.testnet ? "OUI" : "NON"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Clés API</span>
                <span className={status?.has_keys ? "text-green-400" : "text-yellow-400"}>{status?.has_keys ? "CONFIGURÉES" : "MANQUANTES"}</span>
              </div>
            </div>
          </div>

          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-2 sm:mb-3">PRIX BTC</div>
            {btcPrice?.price ? (
              <div className="font-['Rajdhani'] text-2xl sm:text-3xl font-700 text-foreground">
                ${parseFloat(btcPrice.price).toLocaleString("fr-FR", { maximumFractionDigits: 0 })}
              </div>
            ) : (
              <Skeleton className="h-4 w-24" />
            )}
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground mt-1.5 sm:mt-2">Source: Binance Testnet</div>
          </div>

          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-2 sm:mb-3">INFO</div>
            <div className="font-['Inter'] text-[12px] sm:text-xs text-muted-foreground leading-relaxed">
              Configurez vos clés API testnet dans les variables d'environnement :
            </div>
            <div className="mt-1.5 sm:mt-2 font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-primary">
              BINANCE_TESTNET_API_KEY=...<br />
              BINANCE_TESTNET_API_SECRET=...
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}