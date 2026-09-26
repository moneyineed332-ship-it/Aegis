import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, TrendingUp, TrendingDown, AlertTriangle, Wifi, WifiOff, RefreshCw, XCircle, Plus } from "lucide-react";
import { Card, CardHeader, Badge, Stat, EmptyState } from "../components/ui";
import { useToast } from "../components/Toast";
import {
  getPositionMonitor,
  closePosition,
  placeManualOrder,
  getAdminToken,
  type ManualOrderRequest,
  type PortfolioSummary,
  type PositionDetail,
  type PositionRiskAlert,
} from "../../lib/api";

export default function PositionMonitorSection() {
  const { success: toastSuccess, error: toastError } = useToast();
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [alerts, setAlerts] = useState<PositionRiskAlert[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [closingSymbol, setClosingSymbol] = useState<string | null>(null);
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [orderSymbol, setOrderSymbol] = useState("BTC/USDT");
  const [orderSide, setOrderSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<"market" | "limit">("market");
  const [orderQty, setOrderQty] = useState("0.001");
  const [orderPrice, setOrderPrice] = useState("");
  const [orderLoading, setOrderLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchRest = useCallback(async () => {
    try {
      const result = await getPositionMonitor();
      setPortfolio(result.portfolio);
      setAlerts(result.alerts);
      setLastUpdated(new Date());
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchRest();
    const interval = setInterval(fetchRest, 10000);
    return () => clearInterval(interval);
  }, [fetchRest]);

  // WebSocket for live position updates
  useEffect(() => {
    const baseUrl = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/^http/, "ws");
    const token = getAdminToken();
    const wsUrl = token ? `${baseUrl}/ws/positions?token=${encodeURIComponent(token)}` : `${baseUrl}/ws/positions`;

    let ws: WebSocket;
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimeout = setTimeout(connect, 5000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "position_update" && msg.data) {
            setPortfolio(msg.data);
            setLastUpdated(new Date());
          }
        } catch { /* silent */ }
      };
    };

    connect();
    return () => {
      clearTimeout(reconnectTimeout);
      ws?.close();
    };
  }, []);

  const handleClose = async (symbol: string) => {
    if (!window.confirm(`Fermer la position ${symbol} ?`)) return;
    setClosingSymbol(symbol);
    try {
      const result = await closePosition(symbol);
      if (result.closed) {
        toastSuccess(`Position ${symbol} fermee`);
        await fetchRest();
      } else {
        toastError(`Echec fermeture: ${JSON.stringify(result.order)}`);
      }
    } catch (e) {
      toastError(`Erreur: ${e}`);
    } finally {
      setClosingSymbol(null);
    }
  };

  const handlePlaceOrder = async () => {
    setOrderLoading(true);
    try {
      const qty = parseFloat(orderQty);
      if (isNaN(qty) || qty <= 0) {
        toastError("Quantite invalide");
        return;
      }
      const params: ManualOrderRequest = {
        symbol: orderSymbol,
        side: orderSide,
        order_type: orderType,
        quantity: qty,
      };
      if (orderType === "limit") {
        const limitPrice = parseFloat(orderPrice);
        if (isNaN(limitPrice)) {
          toastError("Prix limite invalide");
          return;
        }
        params.limit_price = limitPrice;
      }
      const result = await placeManualOrder(params);
      if (result.status === "filled" || result.status === "pending") {
        toastSuccess(`Ordre ${orderType} ${orderSide} ${orderSymbol} place`);
        setShowOrderForm(false);
        await fetchRest();
      } else {
        toastError(`Ordre rejete: ${result.reason ?? "inconnu"}`);
      }
    } catch (e) {
      toastError(`Erreur: ${e}`);
    } finally {
      setOrderLoading(false);
    }
  };

  if (!portfolio) return <Card><EmptyState icon={<Activity className="w-8 h-8" />} title="Chargement..." description="Recuperation des positions" /></Card>;

  const pnlColor = portfolio.total_pnl >= 0 ? "text-emerald-400" : "text-red-400";
  const unrealizedColor = portfolio.total_unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Monitor de Positions"
          icon={<Activity className="w-4 h-4" />}
          color="#00d4ff"
          action={
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowOrderForm(!showOrderForm)}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-mono border border-primary/30 text-primary hover:bg-primary/5 transition-all"
              >
                <Plus className="w-3 h-3" /> ORDRE
              </button>
              <Badge variant={wsConnected ? "success" : "danger"}>
                {wsConnected ? <><Wifi className="w-3 h-3 mr-1" /> Live</> : <><WifiOff className="w-3 h-3 mr-1" /> Offline</>}
              </Badge>
              {lastUpdated && <span className="text-xs text-muted-foreground/60">{lastUpdated.toLocaleTimeString("fr-FR")}</span>}
            </div>
          }
        />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Stat label="Equity" value={`${portfolio.equity.toFixed(2)} USDT`} />
          <Stat label="PnL total" value={`${portfolio.total_pnl >= 0 ? "+" : ""}${portfolio.total_pnl.toFixed(2)} USDT`} change={portfolio.total_pnl_pct} />
          <Stat label="PnL unrealise" value={`${portfolio.total_unrealized_pnl >= 0 ? "+" : ""}${portfolio.total_unrealized_pnl.toFixed(2)}`} change={portfolio.total_unrealized_pnl_pct} />
          <Stat label="Exposition" value={`${portfolio.exposure_pct.toFixed(1)}%`} />
          <Stat label="Positions" value={portfolio.position_count} />
        </div>
      </Card>

      {showOrderForm && (
        <Card>
          <CardHeader title="Ordre manuel" icon={<Plus className="w-4 h-4" />} color="#f59e0b" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 p-4">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Symbol</label>
              <select value={orderSymbol} onChange={(e) => setOrderSymbol(e.target.value)} className="w-full bg-card border border-border rounded px-3 py-1.5 text-sm text-foreground font-mono">
                <option>BTC/USDT</option>
                <option>ETH/USDT</option>
                <option>SOL/USDT</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Side</label>
              <div className="flex gap-1">
                <button onClick={() => setOrderSide("buy")} className={`flex-1 py-1.5 text-xs font-mono border transition-all ${orderSide === "buy" ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-400" : "border-border text-muted-foreground hover:bg-white/5"}`}>ACHETER</button>
                <button onClick={() => setOrderSide("sell")} className={`flex-1 py-1.5 text-xs font-mono border transition-all ${orderSide === "sell" ? "bg-red-500/20 border-red-500/50 text-red-400" : "border-border text-muted-foreground hover:bg-white/5"}`}>VENDRE</button>
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Type</label>
              <div className="flex gap-1">
                <button onClick={() => setOrderType("market")} className={`flex-1 py-1.5 text-xs font-mono border transition-all ${orderType === "market" ? "bg-primary/20 border-primary/50 text-primary" : "border-border text-muted-foreground hover:bg-white/5"}`}>MARKET</button>
                <button onClick={() => setOrderType("limit")} className={`flex-1 py-1.5 text-xs font-mono border transition-all ${orderType === "limit" ? "bg-primary/20 border-primary/50 text-primary" : "border-border text-muted-foreground hover:bg-white/5"}`}>LIMIT</button>
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">Quantite</label>
              <input type="number" step="0.001" value={orderQty} onChange={(e) => setOrderQty(e.target.value)} className="w-full bg-card border border-border rounded px-3 py-1.5 text-sm text-foreground font-mono" />
            </div>
            {orderType === "limit" && (
              <div>
                <label className="block text-xs text-muted-foreground mb-1">Prix limite</label>
                <input type="number" step="0.01" value={orderPrice} onChange={(e) => setOrderPrice(e.target.value)} placeholder="USDT" className="w-full bg-card border border-border rounded px-3 py-1.5 text-sm text-foreground font-mono" />
              </div>
            )}
          </div>
          <div className="px-4 pb-4">
            <button onClick={handlePlaceOrder} disabled={orderLoading} className="px-4 py-2 text-xs font-mono border border-primary/30 text-primary hover:bg-primary/5 transition-all disabled:opacity-50">
              {orderLoading ? "ENVOI..." : `PLACER L'ORDRE ${orderSide.toUpperCase()}`}
            </button>
          </div>
        </Card>
      )}

      {portfolio.positions.length > 0 && (
        <Card>
          <CardHeader title="Positions ouvertes" icon={<TrendingUp className="w-4 h-4" />} color="#10b981" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground border-b border-border">
                  <th className="text-left py-2 px-3">Symbol</th>
                  <th className="text-left py-2 px-3">Side</th>
                  <th className="text-right py-2 px-3">Qty</th>
                  <th className="text-right py-2 px-3">Entree</th>
                  <th className="text-right py-2 px-3">Prix actuel</th>
                  <th className="text-right py-2 px-3">Notional</th>
                  <th className="text-right py-2 px-3">PnL</th>
                  <th className="text-right py-2 px-3">PnL %</th>
                  <th className="text-right py-2 px-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.filter((p) => p.quantity !== 0).map((p: PositionDetail) => (
                  <tr key={p.symbol} className="border-b border-border/50 hover:bg-card/30">
                    <td className="py-2 px-3 text-foreground font-medium">{p.symbol}</td>
                    <td className="py-2 px-3"><Badge variant={p.side === "long" ? "success" : "danger"}>{p.side}</Badge></td>
                    <td className="py-2 px-3 text-right text-foreground/80">{Math.abs(p.quantity).toFixed(6)}</td>
                    <td className="py-2 px-3 text-right text-foreground/80">{p.entry_price.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right text-foreground">{p.current_price.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right text-foreground/80">{p.notional.toFixed(2)}</td>
                    <td className={`py-2 px-3 text-right font-mono ${p.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl.toFixed(2)}
                    </td>
                    <td className={`py-2 px-3 text-right font-mono ${p.unrealized_pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {p.unrealized_pnl_pct >= 0 ? "+" : ""}{p.unrealized_pnl_pct.toFixed(2)}%
                    </td>
                    <td className="py-2 px-3 text-right">
                      <button
                        onClick={() => handleClose(p.symbol)}
                        disabled={closingSymbol === p.symbol}
                        className="flex items-center gap-1 px-2 py-1 text-xs font-mono border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-50 ml-auto"
                      >
                        <XCircle className="w-3 h-3" />
                        {closingSymbol === p.symbol ? "..." : "FERMER"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {alerts.length > 0 && (
        <Card>
          <CardHeader title="Alertes de risque" icon={<AlertTriangle className="w-4 h-4" />} color="#ef4444" />
          <div className="space-y-2">
            {alerts.map((a, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm text-red-300">{a.message}</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">{new Date(a.timestamp).toLocaleTimeString("fr-FR")}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {portfolio.positions.length === 0 && (
        <Card>
          <EmptyState icon={<Activity className="w-8 h-8" />} title="Aucune position ouverte" description="Les positions apparaitront ici quand le moteur ouvrira des trades" />
        </Card>
      )}
    </div>
  );
}
