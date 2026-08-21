import { useState, useEffect, useCallback } from "react";
import { checkAlerts, getAlertHistory, getAlertThresholds, type Alert } from "../../lib/api";
import { Skeleton } from "../components/ui";
import { DataTimestamp } from "../components/DataTimestamp";
import { RefreshCw } from "lucide-react";
import { useAlertWebSocket } from "../components/AlertWebSocketProvider";

export default function AlertsSection() {
  const { connected: wsConnected, subscribe } = useAlertWebSocket();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [thresholds, setThresholds] = useState<Record<string, number>>({});
  const [liveAlerts, setLiveAlerts] = useState<Array<{ type: string; message: string; timestamp: string }>>([]);
  const [checking, setChecking] = useState(false);
  const [refreshingHistory, setRefreshingHistory] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    Promise.all([
      getAlertHistory().then(setAlerts).catch(() => setAlerts([])),
      getAlertThresholds().then(setThresholds).catch(() => setThresholds({})),
    ]).then(() => setLastUpdated(new Date()));
  }, []);

  useEffect(() => {
    return subscribe((alert) => {
      setLiveAlerts((prev) => [alert as { type: string; message: string; timestamp: string }, ...prev].slice(0, 50));
    });
  }, [subscribe]);

  const handleCheck = async () => {
    setChecking(true);
    try {
      const result = await checkAlerts();
      if (result.alerts) {
        setLiveAlerts((prev) => [...result.alerts, ...prev].slice(0, 50));
      }
      const history = await getAlertHistory();
      setAlerts(history);
    } finally {
      setChecking(false);
    }
  };

  const severityColors: Record<string, string> = {
    critical: "#ef4444", warning: "#f59e0b", info: "#00d4ff",
  };

  return (
    <section id="alertes" className="relative py-16 sm:py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3 sm:gap-4 mb-6 sm:mb-10">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-2 sm:mb-3">09 — ALERTES TEMPS RÉEL</div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-4xl text-foreground">Monitoring <span className="text-primary">WebSocket</span></h2>
              <DataTimestamp lastUpdated={lastUpdated} />
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <span className={`flex items-center gap-1 sm:gap-1.5 text-[12px] sm:text-xs font-['JetBrains_Mono'] ${wsConnected ? "text-green-400" : "text-muted-foreground/60"}`}>
              <span className={`w-1 sm:w-1.5 h-1 sm:h-1.5 rounded-full ${wsConnected ? "bg-green-400 animate-pulse" : "bg-muted-foreground"}`} />{wsConnected ? "WS LIVE" : "WS OFF"}
            </span>
            <button onClick={handleCheck} disabled={checking} className="px-3 sm:px-4 py-1.5 sm:py-2 font-['JetBrains_Mono'] text-[12px] sm:text-xs border border-primary/30 text-primary disabled:opacity-50 hover:bg-primary/5 transition-all">
              {checking ? "VÉRIFICATION…" : "VÉRIFIER"}
            </button>
            <button onClick={async () => { setRefreshingHistory(true); try { const h = await getAlertHistory(); setAlerts(h); } finally { setRefreshingHistory(false); } }} disabled={refreshingHistory} className="border border-primary/30 px-3 py-1.5 font-['JetBrains_Mono'] text-[12px] text-primary disabled:opacity-50 hover:bg-primary/5 transition-all flex items-center gap-1.5">
              <RefreshCw className={`w-3 h-3 ${refreshingHistory ? "animate-spin" : ""}`} />
              RAFRAÎCHIR HISTORIQUE
            </button>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-2 sm:gap-4">
          {/* Live Alerts Feed */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">FLUX TEMPS RÉEL</div>
            {liveAlerts.length > 0 ? (
              <div className="space-y-1.5 sm:space-y-2 max-h-60 sm:max-h-80 overflow-y-auto">
                {liveAlerts.map((alert, i) => (
                  <div key={i} className="flex items-start gap-1.5 sm:gap-2 p-1.5 sm:p-2 border border-border/50">
                    <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full shrink-0 mt-0.5 sm:mt-1" style={{ background: severityColors[alert.type?.split("_")[0] ?? "info"] ?? "#8899b0" }} />
                    <div className="flex-1 min-w-0">
                      <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-foreground truncate">{alert.message}</div>
                      <div className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground">{alert.timestamp?.split("T")[1]?.split(".")[0] ?? ""}</div>
                    </div>
                    <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] px-1 sm:px-1.5 py-0.5 shrink-0" style={{ background: `${severityColors[alert.type?.split("_")[0] ?? "info"]}20`, color: severityColors[alert.type?.split("_")[0] ?? "info"] ?? "#8899b0" }}>
                      {alert.type?.split("_")[0]?.toUpperCase() ?? "INFO"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <Skeleton className="h-4 w-48 mx-auto" />
            )}
          </div>

          {/* Thresholds */}
          <div className="border border-border p-3 sm:p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">SEUILS DE DÉCLENCHEMENT</div>
            <div className="space-y-1.5 sm:space-y-2">
              {Object.entries(thresholds).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between py-1 sm:py-1.5 border-b border-border/30 last:border-0">
                  <span className="font-['Inter'] text-[12px] sm:text-xs text-foreground">{key.replace(/_/g, " ")}</span>
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary">{typeof value === "boolean" ? (value ? "ON" : "OFF") : typeof value === "number" ? value.toLocaleString() : String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Alert History */}
        {alerts.length > 0 && (
          <div className="border border-border p-3 sm:p-5 mt-2 sm:mt-4" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-[12px] sm:text-xs text-primary mb-3 sm:mb-4">HISTORIQUE ({alerts.length})</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5 sm:gap-2">
              {alerts.slice(0, 12).map((alert, i) => (
                <div key={i} className="flex items-center gap-1.5 sm:gap-2 p-1.5 sm:p-2 border border-border/30">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: severityColors[alert.severity] ?? "#8899b0" }} />
                  <span className="font-['JetBrains_Mono'] text-[12px] sm:text-[12px] text-muted-foreground truncate">{alert.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}