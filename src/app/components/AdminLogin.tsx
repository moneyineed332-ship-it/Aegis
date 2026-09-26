import { useCallback, useState } from "react";
import { KeyRound, LogOut, ShieldAlert } from "lucide-react";
import { hasAdminToken, setAdminToken, clearAdminToken, verifyAdminToken } from "../../lib/api";

interface AdminLoginProps {
  onAuthenticated: () => void;
}

/**
 * Gate for the dashboard. The admin token is typed here at runtime instead of
 * being baked into the public bundle through a VITE_* variable.
 */
export default function AdminLogin({ onAuthenticated }: AdminLoginProps) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const submit = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    const candidate = token.trim();
    if (!candidate) {
      setError("Saisis le token administrateur.");
      return;
    }
    setChecking(true);
    setError(null);
    try {
      const ok = await verifyAdminToken(candidate);
      if (!ok) {
        setError("Token refusé par l'API.");
        return;
      }
      setAdminToken(candidate);
      onAuthenticated();
    } catch {
      setError("API injoignable. Vérifie VITE_API_URL.");
    } finally {
      setChecking(false);
    }
  }, [token, onAuthenticated]);

  const logout = useCallback(() => {
    clearAdminToken();
    setToken("");
    onAuthenticated();
  }, [onAuthenticated]);

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center px-4" style={{ fontFamily: "Inter, sans-serif" }}>
      <div className="w-full max-w-sm rounded-xl border border-border p-6" style={{ background: "rgba(11,18,32,0.7)" }}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(0,212,255,0.1)" }}>
            <KeyRound className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="font-['Rajdhani'] font-bold text-xl">Accès administrateur</h1>
            <p className="font-['JetBrains_Mono'] text-[11px] text-muted-foreground">AEGIS AI QUANT V1</p>
          </div>
        </div>

        <p className="font-['Inter'] text-[12px] text-muted-foreground mt-3 mb-5">
          Le token n'est pas stocké dans le code du front. Il reste uniquement dans ce navigateur.
        </p>

        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/70">TOKEN ADMINISTRATEUR</span>
            <input
              type="password"
              value={token}
              autoComplete="current-password"
              onChange={(e) => setToken(e.target.value)}
              aria-label="Token administrateur"
              className="mt-1 w-full px-3 py-2 font-['JetBrains_Mono'] text-[13px] border border-primary/30 bg-transparent text-foreground focus:outline-none focus:border-primary"
            />
          </label>

          {error && (
            <div role="alert" className="flex items-center gap-2 text-[12px] text-destructive">
              <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={checking}
            className="w-full px-3 py-2 font-['JetBrains_Mono'] text-[12px] border border-primary/40 text-primary hover:bg-primary/5 transition-all disabled:opacity-50"
          >
            {checking ? "VÉRIFICATION…" : "DÉVERROUILLER"}
          </button>
        </form>

        {hasAdminToken() && (
          <button
            type="button"
            onClick={logout}
            className="mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 font-['JetBrains_Mono'] text-[11px] text-muted-foreground hover:text-foreground transition-all"
          >
            <LogOut className="w-3 h-3" />
            OUVRIR SANS TOKEN
          </button>
        )}
      </div>
    </div>
  );
}
