import { useState, useEffect, useCallback } from "react";
import { Zap, Settings, BarChart3, ArrowRightCircle, Clock, Radio, ScrollText, Play, Square, Target } from "lucide-react";
import { Card, CardHeader, Button, Badge, Stat, EmptyState } from "../components/ui/index";
import { useToast } from "../components/Toast";
import {
  getEngineStatus,
  getFocusStatus,
  startEngine,
  stopEngine,
  getEngineLogs,
  getEngineSignals,
  getOMSStatus,
  getOMSMode,
  setOMSMode,
  type EngineStatus,
  type FocusStatus,
  type EngineLog,
  type TradeSignal,
  type OMSStatus,
  type OMSMode,
} from "../../lib/api";

interface Props {
  onRefresh?: () => void;
}

export default function EngineSection({ onRefresh }: Props) {
  const { success, error: toastError } = useToast();
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [focus, setFocus] = useState<FocusStatus | null>(null);
  const [logs, setLogs] = useState<EngineLog[]>([]);
  const [signals, setSignals] = useState<TradeSignal[]>([]);
  const [omsStatus, setOMS] = useState<OMSStatus | null>(null);
  const [omsMode, setMode] = useState<OMSMode | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [s, l, sig, oms, mode, foc] = await Promise.allSettled([
        getEngineStatus(),
        getEngineLogs(30),
        getEngineSignals(15),
        getOMSStatus(),
        getOMSMode(),
        getFocusStatus(),
      ]);
      if (s.status === "fulfilled") setStatus(s.value);
      if (l.status === "fulfilled") setLogs(l.value);
      if (sig.status === "fulfilled") setSignals(sig.value);
      if (oms.status === "fulfilled") setOMS(oms.value);
      if (mode.status === "fulfilled") setMode(mode.value);
      if (foc.status === "fulfilled") setFocus(foc.value);
      setLastUpdated(new Date());
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleStart = async () => {
    setLoading(true);
    try {
      await startEngine();
      success("Moteur demarre");
      await fetchAll();
      onRefresh?.();
    } catch (e) {
      toastError(`Erreur: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopEngine();
      success("Moteur arrete");
      await fetchAll();
      onRefresh?.();
    } catch (e) {
      toastError(`Erreur: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const handleModeSwitch = async (newMode: string) => {
    if (!confirm(`Passer en mode ${newMode.toUpperCase()} ?`)) return;
    setLoading(true);
    try {
      await setOMSMode(newMode);
      success(`Mode change: ${newMode.toUpperCase()}`);
      await fetchAll();
    } catch (e) {
      toastError(`Erreur: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  if (!status) {
    return (
      <Card>
        <EmptyState icon={<Zap className="w-8 h-8" />} title="Chargement du moteur..." description="Recuperation du statut" />
      </Card>
    );
  }

  const isRunning = status.status === "running";
  const tasks = status.scheduler?.tasks || {};

  return (
    <div className="space-y-6">
      {/* Header + Controls */}
      <Card>
        <CardHeader title="Moteur Autonome" icon={<Zap className="w-4 h-4" />} color="#00d4ff" />
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <Badge variant={isRunning ? "success" : "default"}>
            {isRunning ? "EN MARCHE" : "ARRETE"}
          </Badge>
          <Badge variant={status.mode === "paper" ? "info" : "warning"}>
            MODE: {status.mode.toUpperCase()}
          </Badge>
          <div className="flex gap-2 ml-auto">
            {!isRunning ? (
              <Button variant="success" icon={<Play className="w-3 h-3" />} loading={loading} onClick={handleStart}>
                DEMARRER
              </Button>
            ) : (
              <Button variant="danger" icon={<Square className="w-3 h-3" />} loading={loading} onClick={handleStop}>
                ARRETER
              </Button>
            )}
          </div>
        </div>
        {status.started_at && (
          <p className="text-xs text-muted-foreground/60 mt-2">
            Demarre le: {new Date(status.started_at).toLocaleString("fr-FR")}
          </p>
        )}
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <Stat label="Cycles" value={String(status.cycle_count)} />
        </Card>
        <Card>
          <Stat label="Signaux" value={String(status.stats?.signals_generated || 0)} />
        </Card>
        <Card>
          <Stat label="Trades" value={String(status.stats?.trades_executed || 0)} />
        </Card>
        <Card>
          <Stat label="Erreurs" value={String(status.stats?.errors || 0)} change={status.stats?.errors ? -1 : 1} />
        </Card>
      </div>

      {/* Focused mode (Phase 1): single strategy */}
      {focus?.focused_mode && (
        <Card>
          <CardHeader title="Mode Focus — Strategie Unique" icon={<Target className="w-4 h-4" />} color="#22c55e" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
            <div>
              <div className="text-xs text-muted-foreground">Strategie</div>
              <div className="font-['Rajdhani'] font-bold text-lg text-green-400">{focus.strategy_name}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Symboles ({focus.symbols.length})</div>
              <div className="font-['JetBrains_Mono'] text-sm text-foreground">{focus.symbols.join(" · ")}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Devis max</div>
              <div className="font-['Rajdhani'] font-bold text-lg text-foreground">{focus.max_positions}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Donchian</div>
              <div className="font-['JetBrains_Mono'] text-sm text-foreground">
                {focus.donchian_parameters.breakout_period}/{focus.donchian_parameters.exit_period}
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {focus.tradable_strategies.map((s) => (
              <Badge key={s} variant="success">{s.toUpperCase()}</Badge>
            ))}
          </div>
        </Card>
      )}

      {/* Execution Mode & OMS */}
      <Card>
        <CardHeader title="Mode d'Execution" icon={<Settings className="w-4 h-4" />} color="#f59e0b" />
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <Badge variant={omsMode?.mode === "live" ? "danger" : "info"}>
            {omsMode?.mode?.toUpperCase() || "PAPER"}
          </Badge>
          <span className="text-sm text-muted-foreground">
            Exchange: {omsMode?.exchange || "paper"}
          </span>
          <div className="flex gap-2 ml-auto">
            {omsMode?.mode !== "paper" && (
              <Button variant="secondary" size="sm" loading={loading} onClick={() => handleModeSwitch("paper")}>
                PAPER
              </Button>
            )}
            {omsMode?.mode !== "live" && (
              <Button variant="danger" size="sm" loading={loading} onClick={() => handleModeSwitch("live")}>
                LIVE
              </Button>
            )}
          </div>
        </div>
        {omsStatus && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-3 text-sm">
            <div>
              <p className="text-xs text-muted-foreground/60">Positions</p>
              <p className="font-mono text-foreground">{omsStatus.positions_count}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground/60">Exposition</p>
              <p className="font-mono text-foreground">${omsStatus.total_exposure.toFixed(0)} / ${omsStatus.max_exposure}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground/60">Ordres recents</p>
              <p className="font-mono text-foreground">{omsStatus.recent_orders}</p>
            </div>
          </div>
        )}
      </Card>

      {/* Last Analysis */}
      {status.last_analysis && (
        <Card>
          <CardHeader title="Derniere Analyse" icon={<BarChart3 className="w-4 h-4" />} color="#10b981" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-3">
            <div>
              <p className="text-xs text-muted-foreground/60">Symbole</p>
              <p className="text-sm font-mono text-foreground">{status.last_analysis.symbol}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground/60">Regime</p>
              <p className="text-sm font-mono text-foreground">{status.last_analysis.regime}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground/60">Confiance</p>
              <p className="text-sm font-mono text-foreground">{(status.last_analysis.confidence * 100).toFixed(1)}%</p>
            </div>
          </div>
        </Card>
      )}

      {/* Last Signal */}
      {status.last_signal && (
        <Card>
          <CardHeader title="Dernier Signal" icon={<ArrowRightCircle className="w-4 h-4" />} color="#f59e0b" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-3">
            <div>
              <p className="text-xs text-muted-foreground/60">Symbole</p>
              <p className="text-sm font-mono text-foreground">{status.last_signal.symbol}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground/60">Action</p>
              <Badge variant={status.last_signal.action === "buy" ? "success" : status.last_signal.action === "sell" ? "danger" : "default"}>
                {status.last_signal.action.toUpperCase()}
              </Badge>
            </div>
            <div>
              <p className="text-xs text-muted-foreground/60">Strategie</p>
              <p className="text-sm font-mono text-foreground">{status.last_signal.strategy || "N/A"}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Scheduler Tasks */}
      {Object.keys(tasks).length > 0 && (
        <Card>
          <CardHeader title="Taches Planifiees" icon={<Clock className="w-4 h-4" />} color="#8b5cf6" />
          <div className="mt-3 space-y-2">
            {Object.entries(tasks).map(([name, task]) => (
              <div key={name} className="flex items-center justify-between py-1 border-b border-border last:border-0">
                <div className="flex items-center gap-2">
                  <Badge variant={task.enabled ? "success" : "default"}>{task.enabled ? "ON" : "OFF"}</Badge>
                  <span className="text-sm text-foreground/80 font-mono">{name}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground/60">
                  <span>{task.interval}s</span>
                  {task.error_count > 0 && (
                    <Badge variant="danger">{task.error_count} err</Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recent Signals */}
      {signals.length > 0 && (
        <Card>
          <CardHeader title="Signaux Recents" icon={<Radio className="w-4 h-4" />} color="#06b6d4" />
          <div className="mt-3 space-y-1">
            {signals.slice(0, 10).map((sig) => (
              <div key={sig.id} className="flex flex-wrap items-center gap-2 justify-between py-1 border-b border-border last:border-0 text-sm">
                <span className="font-mono text-foreground/80">{sig.symbol}</span>
                <Badge variant={sig.signal_type === "buy" ? "success" : sig.signal_type === "sell" ? "danger" : "default"}>
                  {sig.signal_type}
                </Badge>
                <span className="text-muted-foreground/60 hidden sm:inline">{sig.strategy}</span>
                <Badge variant={sig.executed ? "success" : "default"}>{sig.executed ? "EXEC" : "EN ATTENTE"}</Badge>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Engine Logs */}
      {logs.length > 0 && (
        <Card>
          <CardHeader title="Journal du Moteur" icon={<ScrollText className="w-4 h-4" />} color="#64748b" />
          <div className="mt-3 max-h-64 overflow-y-auto space-y-1">
            {logs.map((log) => (
              <div key={log.id} className="flex items-start gap-2 py-1 text-xs border-b border-border last:border-0">
                <Badge variant={log.severity === "error" ? "danger" : log.severity === "warning" ? "warning" : "default"}>
                  {log.severity}
                </Badge>
                <span className="text-muted-foreground/60 font-mono shrink-0">{log.cycle_id}</span>
                <span className="text-foreground/80">{log.event_type}</span>
                {log.details && (
                  <span className="text-muted-foreground/40 truncate">{JSON.stringify(log.details).slice(0, 60)}</span>
                )}
                <span className="text-muted-foreground/40 ml-auto shrink-0">
                  {new Date(log.created_at).toLocaleTimeString("fr-FR")}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {lastUpdated && (
        <p className="text-xs text-muted-foreground/40 text-right">
          Mis a jour: {lastUpdated.toLocaleTimeString("fr-FR")}
        </p>
      )}
    </div>
  );
}
