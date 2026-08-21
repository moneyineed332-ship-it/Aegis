import { useCallback, useEffect, useState } from "react";
import { Shield, AlertTriangle, UserCheck, Eye, RefreshCw } from "lucide-react";
import { Card, CardHeader, Badge, Stat, EmptyState } from "../components/ui";
import { useToast } from "../components/Toast";
import { getSecuritySummary, type SecuritySummary } from "../../lib/api";

export default function SecuritySection() {
  const { success, error: toastError } = useToast();
  const [data, setData] = useState<SecuritySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const result = await getSecuritySummary();
      setData(result);
      setLastUpdated(new Date());
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await fetchAll();
      success("Donnees securite actualisees");
    } catch {
      toastError("Erreur lors de l'actualisation");
    } finally {
      setLoading(false);
    }
  };

  if (!data) return <Card><EmptyState icon={<Shield className="w-8 h-8" />} title="Chargement..." description="Recuperation des donnees de securite" /></Card>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Securite"
          icon={<Shield className="w-4 h-4" />}
          color="#ef4444"
          action={
            <button onClick={handleRefresh} disabled={loading} className="p-1.5 rounded-lg hover:bg-white/5 transition-colors" aria-label="Actualiser">
              <RefreshCw className={`w-4 h-4 text-muted-foreground ${loading ? "animate-spin" : ""}`} />
            </button>
          }
        />
        {lastUpdated && <p className="text-xs text-muted-foreground/60 mb-4">Derniere MAJ: {lastUpdated.toLocaleTimeString("fr-FR")}</p>}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Evenements totaux" value={data.total_events} />
          <Stat label="Echecs auth" value={data.auth_failures} />
          <Stat label="Actions admin" value={data.admin_actions} />
          <Stat label="Breaches risque" value={data.risk_breaches} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Evenements recents" icon={<Eye className="w-4 h-4" />} color="#8b5cf6" />
        {data.recent_events.length === 0 ? (
          <EmptyState icon={<Shield className="w-8 h-8" />} title="Aucun evenement" description="Les evenements de securite apparaitront ici" />
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {data.recent_events.map((event) => (
              <div key={event.id} className="flex items-start gap-3 p-3 rounded-lg bg-card/30 border border-border">
                <div className="mt-0.5">
                  {event.severity === "critical" ? (
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                  ) : event.severity === "warning" ? (
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                  ) : (
                    <UserCheck className="w-4 h-4 text-emerald-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge variant={event.severity === "critical" ? "danger" : event.severity === "warning" ? "warning" : "success"}>
                      {event.event_type.replace("security_", "")}
                    </Badge>
                    <span className="text-xs text-muted-foreground/60">{new Date(event.created_at).toLocaleTimeString("fr-FR")}</span>
                  </div>
                  {event.details && (
                    <pre className="mt-1 text-xs text-muted-foreground overflow-x-auto">{JSON.stringify(event.details, null, 2)}</pre>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
