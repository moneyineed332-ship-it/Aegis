import { useState, useEffect } from "react";
import { activateEmergencyStop, getDashboard, getSupervisor, postApi, refreshFearGreed, refreshFundingRates, refreshHistory, refreshMarketData, refreshOpenInterest, resumeSupervisor, runDonchianWalkForward, runGridWalkForward, runMeanReversionWalkForward, runSmaWalkForward, type DashboardSnapshot, type SupervisorStatus } from "../lib/api";
import {
  Activity,
  AlertTriangle,
  BarChart2,
  BookOpen,
  Brain,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  Eye,
  FlaskConical,
  GitBranch,
  Globe,
  Layers,
  LineChart,
  Lock,
  Menu,
  RefreshCw,
  Server,
  Shield,
  Target,
  Terminal,
  TrendingUp,
  Wifi,
  X,
  Zap,
} from "lucide-react";
import { LineChart as ReLineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// --- Types ---
interface Module {
  id: number;
  title: string;
  subtitle: string;
  description: string;
  bullets: string[];
  icon: React.ReactNode;
  color: string;
}

// --- Data ---

const modules: Module[] = [
  {
    id: 1,
    title: "Collecteur de données",
    subtitle: "Data Harvesting",
    description: "Le système nerveux. Collecte OHLCV, Order Book, Funding Rate, Open Interest, données macro et internes.",
    bullets: ["OHLCV & Tick Data", "Order Book & Trades", "Fear & Greed Index", "Dominance BTC / Stablecoins"],
    icon: <Globe className="w-5 h-5" />,
    color: "#00d4ff",
  },
  {
    id: 2,
    title: "Validation des données",
    subtitle: "Data Integrity",
    description: "Détecte les données manquantes, valeurs aberrantes, désynchronisations et doublons avant toute décision.",
    bullets: ["Données manquantes", "Valeurs aberrantes", "Désynchronisation", "Doublons"],
    icon: <Shield className="w-5 h-5" />,
    color: "#00d4ff",
  },
  {
    id: 3,
    title: "Feature Engineering",
    subtitle: "Signal Processing",
    description: "Transforme les données brutes en informations exploitables : indicateurs, momentum, profondeur du carnet.",
    bullets: ["Indicateurs techniques", "Volatilité & Momentum", "Profondeur du carnet", "Régimes de volatilité"],
    icon: <Layers className="w-5 h-5" />,
    color: "#3b82f6",
  },
  {
    id: 4,
    title: "IA de marché",
    subtitle: "Market Intelligence",
    description: "Identifie le régime de marché (Range, Bull, Bear, Euphoria, Capitulation) via distribution de probabilités.",
    bullets: ["Range / Bull / Bear", "Forte / Faible volatilité", "Capitulation & Euphoria", "Distribution de probabilités"],
    icon: <Brain className="w-5 h-5" />,
    color: "#8b5cf6",
  },
  {
    id: 5,
    title: "Bibliothèque de stratégies",
    subtitle: "Strategy Library",
    description: "Chaque stratégie est indépendante et produit un sens, un niveau de confiance et un ratio risque/rendement.",
    bullets: ["Grid adaptatif", "Trend Following", "Mean Reversion", "Scalping & Breakout"],
    icon: <BookOpen className="w-5 h-5" />,
    color: "#06b6d4",
  },
  {
    id: 6,
    title: "Conseil IA",
    subtitle: "Multi-Agent Council",
    description: "Chaque agent vote : Analyste, Trader, Gestionnaire du risque, Coach, Chercheur. Le gestionnaire a un droit de veto.",
    bullets: ["Analyste Marché", "Trader & Coach", "Gestionnaire du risque", "Droit de veto"],
    icon: <GitBranch className="w-5 h-5" />,
    color: "#f59e0b",
  },
  {
    id: 7,
    title: "Gestion du risque",
    subtitle: "Risk Management",
    description: "Module prioritaire. Calcule exposition, drawdown, VaR, CVaR, corrélation et effectue des stress tests.",
    bullets: ["VaR & CVaR", "Stress tests extrêmes", "Drawdown monitoring", "Corrélation dynamique"],
    icon: <AlertTriangle className="w-5 h-5" />,
    color: "#ef4444",
  },
  {
    id: 8,
    title: "Exécution intelligente",
    subtitle: "Smart Execution",
    description: "Choisit automatiquement ordre limite, marché ou exécution fractionnée pour réduire slippage et frais.",
    bullets: ["Ordre limite / marché", "Exécution fractionnée", "Réduction du slippage", "Impact marché minimisé"],
    icon: <Zap className="w-5 h-5" />,
    color: "#10b981",
  },
  {
    id: 9,
    title: "Journal intelligent",
    subtitle: "Decision Ledger",
    description: "Chaque décision enregistrée avec contexte, stratégie, score de confiance, décision finale et résultat.",
    bullets: ["Contexte complet", "Score de confiance", "Décision finale", "Traçabilité totale"],
    icon: <Terminal className="w-5 h-5" />,
    color: "#6366f1",
  },
  {
    id: 10,
    title: "Mémoire",
    subtitle: "Episodic Memory",
    description: "Mémorise les configurations rencontrées. Compare avec des cas passés pour enrichir les nouvelles analyses.",
    bullets: ["Configurations passées", "Comparaison contextuelle", "Enrichissement d'analyse", "Apprentissage continu"],
    icon: <Database className="w-5 h-5" />,
    color: "#0ea5e9",
  },
  {
    id: 11,
    title: "Coach IA",
    subtitle: "AI Coaching",
    description: "Analyse erreurs récurrentes, forces des stratégies, périodes d'efficacité et formule des propositions d'amélioration.",
    bullets: ["Erreurs récurrentes", "Forces des stratégies", "Propositions d'amélioration", "Ne modifie jamais directement"],
    icon: <Target className="w-5 h-5" />,
    color: "#f97316",
  },
  {
    id: 12,
    title: "Laboratoire",
    subtitle: "Research Lab",
    description: "Teste toutes les idées via backtests, walk-forward analysis, paper trading et comparaison avec la version actuelle.",
    bullets: ["Backtests", "Walk-forward analysis", "Paper trading", "Validation robuste"],
    icon: <FlaskConical className="w-5 h-5" />,
    color: "#a855f7",
  },
  {
    id: 13,
    title: "Superviseur",
    subtitle: "System Monitor",
    description: "Surveille la santé du système, vérifie les performances, détecte les anomalies et active l'arrêt d'urgence.",
    bullets: ["Santé du système", "Performances temps réel", "Détection d'anomalies", "Arrêt d'urgence"],
    icon: <Eye className="w-5 h-5" />,
    color: "#14b8a6",
  },
  {
    id: 14,
    title: "Tableau de bord",
    subtitle: "Live Dashboard",
    description: "Affiche en temps réel capital, PnL, drawdown, stratégies actives, positions, alertes et performances.",
    bullets: ["Capital & PnL", "Drawdown en direct", "Stratégies actives", "Alertes & performances"],
    icon: <BarChart2 className="w-5 h-5" />,
    color: "#00d4ff",
  },
  {
    id: 15,
    title: "Déploiement sécurisé",
    subtitle: "Safe Deployment",
    description: "Chaque nouvelle version passe par simulation, backtest, walk-forward, paper trading, validation puis déploiement progressif.",
    bullets: ["Simulation complète", "Validation rigoureuse", "Déploiement progressif", "Rollback instantané"],
    icon: <Lock className="w-5 h-5" />,
    color: "#22c55e",
  },
];

const techStack = [
  { category: "BACKEND", items: ["Python", "FastAPI", "CCXT", "WebSockets", "asyncio"], icon: <Server className="w-4 h-4" /> },
  { category: "DATA", items: ["PostgreSQL", "Redis", "Parquet", "pandas", "Polars"], icon: <Database className="w-4 h-4" /> },
  { category: "MACHINE LEARNING", items: ["scikit-learn", "LightGBM", "XGBoost", "CatBoost", "PyTorch"], icon: <Brain className="w-4 h-4" /> },
  { category: "BACKTESTING", items: ["vectorbt", "LEAN"], icon: <LineChart className="w-4 h-4" /> },
  { category: "INFRASTRUCTURE", items: ["Docker", "GitHub Actions", "Prometheus", "Grafana", "Telegram / Discord"], icon: <Cpu className="w-4 h-4" /> },
];

const phases = [
  { id: 1, name: "MVP", label: "PHASE 1", color: "#00d4ff", items: ["Collecte de données", "Une stratégie", "Paper trading", "Tableau de bord"] },
  { id: 2, name: "Extension", label: "PHASE 2", color: "#3b82f6", items: ["Plusieurs stratégies", "Gestion du risque avancée", "Journal complet"] },
  { id: 3, name: "Intelligence", label: "PHASE 3", color: "#8b5cf6", items: ["Détection du régime de marché", "Fusion intelligente des signaux", "Optimisation des paramètres"] },
  { id: 4, name: "Auto-amélioration", label: "PHASE 4", color: "#f59e0b", items: ["Coach IA", "Laboratoire", "Validation automatisée"] },
  { id: 5, name: "Autonomie", label: "PHASE 5", color: "#10b981", items: ["Plateforme auto-évolutive", "Supervision renforcée"] },
];

const pipeline = [
  "INTERNET",
  "Collecteur Multi-Source",
  "Validation & Nettoyage",
  "Feature Engineering",
  "Détection du régime marché",
  "Conseil IA Multi-Agents",
  "Gestion du risque",
  "Exécution intelligente",
  "Journal & Mémoire",
  "Coach IA",
  "Laboratoire",
  "Validation",
  "Déploiement sécurisé",
];

// --- Components ---

function GlowOrb({ x, y, size, color, opacity }: { x: string; y: string; size: string; color: string; opacity: number }) {
  return (
    <div
      className="absolute rounded-full pointer-events-none"
      style={{
        left: x,
        top: y,
        width: size,
        height: size,
        background: color,
        opacity,
        filter: "blur(120px)",
        transform: "translate(-50%, -50%)",
      }}
    />
  );
}

function GridLines() {
  return (
    <div
      className="absolute inset-0 pointer-events-none"
      style={{
        backgroundImage: `
          linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px)
        `,
        backgroundSize: "60px 60px",
      }}
    />
  );
}

function NavBar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", handler);
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const links = ["Vision", "Architecture", "Modules", "Technologies", "Roadmap", "Operations"];

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
      style={{
        background: scrolled ? "rgba(4,8,15,0.92)" : "transparent",
        backdropFilter: scrolled ? "blur(20px)" : "none",
        borderBottom: scrolled ? "1px solid rgba(0,212,255,0.08)" : "none",
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="relative w-8 h-8">
            <div className="absolute inset-0 rounded border border-primary/60" style={{ transform: "rotate(45deg)" }} />
            <div className="absolute inset-1 rounded bg-primary/20" style={{ transform: "rotate(45deg)" }} />
            <Activity className="absolute inset-0 m-auto w-4 h-4 text-primary" />
          </div>
          <span className="font-['Rajdhani'] font-700 text-lg tracking-[0.15em] text-foreground">
            AEGIS <span className="text-primary">AI QUANT</span>
          </span>
        </div>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <a
              key={l}
              href={`#${l.toLowerCase()}`}
              className="font-['Inter'] text-sm text-muted-foreground hover:text-primary transition-colors duration-200 tracking-wide"
            >
              {l}
            </a>
          ))}
        </nav>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-xs font-['JetBrains_Mono'] text-muted-foreground">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            LIVE
          </span>
          <button
            className="px-5 py-2 text-sm font-['Rajdhani'] font-600 tracking-wider transition-all duration-200 hover:scale-105"
            style={{
              background: "linear-gradient(135deg, #00d4ff, #0057ff)",
              color: "#04080f",
              clipPath: "polygon(8px 0%, 100% 0%, calc(100% - 8px) 100%, 0% 100%)",
            }}
          >
            ACCÈS SYSTÈME
          </button>
        </div>

        {/* Mobile burger */}
        <button className="md:hidden text-foreground" onClick={() => setOpen(!open)}>
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t border-border" style={{ background: "rgba(4,8,15,0.98)" }}>
          {links.map((l) => (
            <a
              key={l}
              href={`#${l.toLowerCase()}`}
              className="block px-6 py-3 text-sm font-['Inter'] text-muted-foreground hover:text-primary border-b border-border/50"
              onClick={() => setOpen(false)}
            >
              {l}
            </a>
          ))}
        </div>
      )}
    </header>
  );
}

function HeroSection() {
  const [count, setCount] = useState(0);
  const [dashboard, setDashboard] = useState<DashboardSnapshot | null>(null);
  const [apiOnline, setApiOnline] = useState(false);
  const [operation, setOperation] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [supervisor, setSupervisor] = useState<SupervisorStatus | null>(null);
  const latestBacktest = dashboard?.recent_backtests[0];
  const latestMetrics = latestBacktest?.metrics.out_of_sample_metrics ?? latestBacktest?.metrics;

  useEffect(() => {
    const target = 87.4;
    const step = target / 60;
    let current = 0;
    const t = setInterval(() => {
      current = Math.min(current + step, target);
      setCount(parseFloat(current.toFixed(1)));
      if (current >= target) clearInterval(t);
    }, 30);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    void getSupervisor().then(setSupervisor).catch(() => setSupervisor(null));
  }, []);

  const runResearchAction = async (label: string, action: () => Promise<unknown>) => {
    setOperation(label);
    setOperationError(null);
    try {
      await action();
      setDashboard(await getDashboard());
      setSupervisor(await getSupervisor());
      setApiOnline(true);
    } catch {
      setOperationError("Action impossible : vérifie que l'API AEGIS est lancée et que la source publique est accessible.");
    } finally {
      setOperation(null);
    }
  };

  useEffect(() => {
    let active = true;
    const refreshDashboard = async () => {
      try {
        const snapshot = await getDashboard();
        if (active) {
          setDashboard(snapshot);
          setApiOnline(true);
        }
      } catch {
        if (active) setApiOnline(false);
      }
    };
    void refreshDashboard();
    const intervalId = window.setInterval(() => void refreshDashboard(), 15_000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  return (
    <section id="vision" className="relative min-h-screen flex flex-col justify-center overflow-hidden pt-16">
      <GridLines />
      <GlowOrb x="10%" y="30%" size="600px" color="#0057ff" opacity={0.12} />
      <GlowOrb x="80%" y="60%" size="500px" color="#00d4ff" opacity={0.08} />
      <GlowOrb x="50%" y="10%" size="400px" color="#8b5cf6" opacity={0.06} />

      {/* Vertical scan line */}
      <div
        className="absolute top-0 bottom-0 w-px pointer-events-none"
        style={{
          left: "20%",
          background: "linear-gradient(to bottom, transparent, rgba(0,212,255,0.3), transparent)",
        }}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-6 py-24 grid lg:grid-cols-2 gap-16 items-center">
        {/* Left */}
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-8 border border-primary/30 rounded-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest">VERSION 1.0 — CONFIDENTIEL</span>
          </div>

          <h1 className="font-['Rajdhani'] font-700 text-5xl sm:text-6xl lg:text-7xl leading-none tracking-tight mb-6">
            <span className="text-foreground">AEGIS</span>
            <br />
            <span style={{ color: "#00d4ff" }}>AI QUANT</span>
            <br />
            <span className="text-foreground text-4xl sm:text-5xl lg:text-6xl">V1</span>
          </h1>

          <p className="font-['Inter'] text-base text-muted-foreground leading-relaxed mb-4 max-w-md">
            Système autonome de trading crypto — Observer, comprendre, décider, exécuter et évoluer sans intervention permanente.
          </p>

          <p className="font-['Inter'] text-sm text-muted-foreground/70 italic mb-10 max-w-sm">
            "Robustesse avant tout."
          </p>

          <div className="flex flex-wrap gap-4 mb-12">
            <button
              className="flex items-center gap-2 px-6 py-3 font-['Rajdhani'] font-600 tracking-wider text-sm transition-all duration-200 hover:scale-105"
              style={{
                background: "linear-gradient(135deg, #00d4ff, #0057ff)",
                color: "#04080f",
                clipPath: "polygon(10px 0%, 100% 0%, calc(100% - 10px) 100%, 0% 100%)",
              }}
            >
              DÉCOUVRIR LE SYSTÈME
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              className="flex items-center gap-2 px-6 py-3 font-['Rajdhani'] font-600 tracking-wider text-sm border border-primary/40 text-primary hover:border-primary hover:bg-primary/5 transition-all duration-200"
              style={{ clipPath: "polygon(10px 0%, 100% 0%, calc(100% - 10px) 100%, 0% 100%)" }}
            >
              VOIR L'ARCHITECTURE
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-6">
            {[
              { value: "15", label: "Modules", unit: "" },
              { value: "24/7", label: "Surveillance", unit: "" },
              { value: `${count}%`, label: "Win rate cible", unit: "" },
            ].map((s) => (
              <div key={s.label} className="border-l-2 border-primary/40 pl-4">
                <div className="font-['Rajdhani'] font-700 text-2xl text-primary">{s.value}</div>
                <div className="font-['Inter'] text-xs text-muted-foreground tracking-wider">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right — live PnL card */}
        <div className="relative">
          <div
            className="relative border border-primary/20 p-6"
            style={{
              background: "rgba(11,18,32,0.8)",
              backdropFilter: "blur(20px)",
              clipPath: "polygon(0 0, calc(100% - 20px) 0, 100% 20px, 100% 100%, 20px 100%, 0 calc(100% - 20px))",
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="font-['JetBrains_Mono'] text-xs text-muted-foreground tracking-widest mb-1">PERFORMANCE SIMULÉE</div>
                <div className="font-['Rajdhani'] font-700 text-3xl text-foreground">
                  ${dashboard?.current_equity?.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) ?? dashboard?.capital?.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) ?? "—"}
                </div>
                <div className="font-['Inter'] text-sm text-primary">
                  {dashboard ? (
                    <>
                      Capital paper trading
                      {dashboard.realized_pnl !== 0 && (
                        <span className={`ml-2 ${dashboard.realized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          PnL: {dashboard.realized_pnl >= 0 ? "+" : ""}${dashboard.realized_pnl.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}
                        </span>
                      )}
                    </>
                  ) : "Connexion à l'API…"}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <div className={`flex items-center gap-1.5 text-xs font-['JetBrains_Mono'] ${apiOnline ? "text-green-400" : "text-muted-foreground"}`}>
                  <Wifi className="w-3 h-3" />
                  {apiOnline ? "API EN LIGNE" : "API HORS LIGNE"}
                </div>
                <div className="text-xs text-muted-foreground font-['JetBrains_Mono']">
                  {dashboard ? `EXPOSITION: $${dashboard.exposure.toLocaleString("fr-FR")}` : "MODE: PAPER"}
                </div>
              </div>
            </div>

            {latestBacktest && latestMetrics && (
              <div className="mb-4 border border-primary/20 bg-primary/5 p-3">
                <div className="font-['JetBrains_Mono'] text-xs text-primary">DERNIER BACKTEST — {latestBacktest.symbol} / {latestBacktest.interval}</div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 font-['JetBrains_Mono'] text-xs text-muted-foreground">
                  <span>RENDEMENT: {((latestMetrics.total_return ?? 0) * 100).toFixed(2)}%</span>
                  <span>DRAWDOWN: {((latestMetrics.max_drawdown ?? 0) * 100).toFixed(2)}%</span>
                  <span>SHARPE: {(latestMetrics.sharpe_ratio ?? 0).toFixed(2)}</span>
                  <span>TRADES: {latestMetrics.trade_count ?? 0}</span>
                </div>
              </div>
            )}

            <div className="mb-4 grid grid-cols-2 gap-2">
              <button onClick={() => void runResearchAction("Mise à jour marché", refreshMarketData)} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">PRIX MARCHÉ</button>
              <button onClick={() => void runResearchAction("Historique OHLCV", refreshHistory)} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">CHARGER OHLCV</button>
              <button onClick={() => void runResearchAction("Walk-forward SMA", runSmaWalkForward)} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">TESTER SMA</button>
              <button onClick={() => void runResearchAction("Walk-forward Donchian", runDonchianWalkForward)} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">TESTER DONCHIAN</button>
              <button onClick={() => void runResearchAction("Walk-forward Mean Reversion", runMeanReversionWalkForward)} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">TESTER MEAN REV</button>
              <button onClick={() => void runResearchAction("Walk-forward Grid", runGridWalkForward)} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">TESTER GRID</button>
              <button onClick={() => void runResearchAction("Fear & Greed", refreshFearGreed)} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">FEAR & GREED</button>
              <button onClick={() => void runResearchAction("Funding Rate", () => refreshFundingRates())} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">FUNDING RATE</button>
              <button onClick={() => void runResearchAction("Open Interest", () => refreshOpenInterest())} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">OPEN INTEREST</button>
              <button onClick={() => void runResearchAction("Mémoire", () => postApi("/api/v1/memory/remember"))} disabled={Boolean(operation)} className="border border-primary/30 px-3 py-2 font-['JetBrains_Mono'] text-xs text-primary disabled:opacity-50">MÉMOIRE</button>
            </div>
            {(operation || operationError) && <div className={`mb-4 font-['JetBrains_Mono'] text-xs ${operationError ? "text-red-400" : "text-primary"}`}>{operationError ?? `${operation}…`}</div>}

            <div className="mb-4 border border-border p-3 font-['JetBrains_Mono'] text-xs">
              <div className={supervisor?.kill_switch_active ? "text-red-400" : "text-green-400"}>SUPERVISEUR: {supervisor?.kill_switch_active ? "ARRÊT D'URGENCE ACTIF" : "PAPER TRADING SURVEILLÉ"}</div>
              {supervisor?.alerts[0] && <div className="mt-1 text-muted-foreground">{supervisor.alerts[0].message}</div>}
              <div className="mt-2 flex gap-2">
                <button onClick={() => void runResearchAction("Arrêt d'urgence", activateEmergencyStop)} disabled={Boolean(operation) || supervisor?.kill_switch_active} className="border border-red-400/40 px-2 py-1 text-red-400 disabled:opacity-50">STOP</button>
                <button onClick={() => void runResearchAction("Reprise manuelle", resumeSupervisor)} disabled={Boolean(operation) || !supervisor?.kill_switch_active} className="border border-green-400/40 px-2 py-1 text-green-400 disabled:opacity-50">REPRENDRE</button>
              </div>
            </div>

            {/* Chart */}
            <div className="h-40 mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <ReLineChart data={(dashboard?.equity_curve ?? []).map((p, i) => ({ t: `#${i}`, v: p.equity }))}>
                  <defs>
                    <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#0057ff" />
                      <stop offset="100%" stopColor="#00d4ff" />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="t" tick={{ fill: "#6b7fa3", fontSize: 10, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{ background: "#0b1220", border: "1px solid rgba(0,212,255,0.2)", borderRadius: 4 }}
                    labelStyle={{ color: "#6b7fa3", fontFamily: "JetBrains Mono", fontSize: 10 }}
                    itemStyle={{ color: "#00d4ff", fontFamily: "JetBrains Mono" }}
                    formatter={(v: number) => [`$${v.toLocaleString()}`, "Equity"]}
                  />
                  <Line type="monotone" dataKey="v" stroke="url(#lineGrad)" strokeWidth={2} dot={false} />
                </ReLineChart>
              </ResponsiveContainer>
            </div>

            {/* Live position rows */}
            {dashboard?.positions && dashboard.positions.length > 0 ? (
              dashboard.positions.map((pos) => (
                <div key={pos.symbol} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                  <div>
                    <div className="font-['Inter'] text-xs text-foreground">{pos.symbol.replace("/", " / ")}</div>
                    <div className="font-['JetBrains_Mono'] text-xs text-muted-foreground">Qty: {pos.quantity.toFixed(4)}</div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-['JetBrains_Mono'] text-xs text-muted-foreground">
                      Avg ${pos.average_price.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-2 border-b border-border/50 last:border-0">
                <div className="font-['JetBrains_Mono'] text-xs text-muted-foreground/50">Aucune position ouverte</div>
              </div>
            )}
          </div>

          {/* Corner accents */}
          <div className="absolute -top-px -left-px w-6 h-6 border-t-2 border-l-2 border-primary" />
          <div className="absolute -bottom-px -right-px w-6 h-6 border-b-2 border-r-2 border-primary" />
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-muted-foreground/50">
        <span className="font-['JetBrains_Mono'] text-xs tracking-widest">SCROLL</span>
        <ChevronDown className="w-4 h-4 animate-bounce" />
      </div>
    </section>
  );
}

function ArchitectureSection() {
  return (
    <section id="architecture" className="relative py-32 overflow-hidden">
      <GridLines />
      <GlowOrb x="90%" y="50%" size="500px" color="#0057ff" opacity={0.08} />

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-16 items-start">
          {/* Left — text */}
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">02 — ARCHITECTURE</div>
            <h2 className="font-['Rajdhani'] font-700 text-4xl sm:text-5xl text-foreground mb-6 leading-tight">
              Pipeline<br />
              <span style={{ color: "#00d4ff" }}>linéaire</span><br />
              et déterministe
            </h2>
            <p className="font-['Inter'] text-sm text-muted-foreground leading-relaxed max-w-md mb-8">
              Le système suit un pipeline strict, de la collecte des données brutes jusqu'au déploiement sécurisé,
              en passant par l'analyse, la décision et l'exécution. Chaque étape valide l'étape précédente.
            </p>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Latence totale", value: "<50ms" },
                { label: "Uptime cible", value: "99.9%" },
                { label: "Agents IA", value: "5 votes" },
                { label: "Rollback", value: "Instantané" },
              ].map((m) => (
                <div key={m.label} className="p-4 border border-border" style={{ background: "rgba(11,18,32,0.6)" }}>
                  <div className="font-['Rajdhani'] font-700 text-xl text-primary">{m.value}</div>
                  <div className="font-['Inter'] text-xs text-muted-foreground mt-1">{m.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right — pipeline */}
          <div className="relative">
            <div className="relative flex flex-col gap-0">
              {pipeline.map((step, i) => (
                <div key={step} className="flex items-stretch gap-4">
                  {/* Connector */}
                  <div className="flex flex-col items-center w-8 shrink-0">
                    <div
                      className="w-3 h-3 rounded-sm shrink-0 mt-3"
                      style={{
                        background: i === 0 ? "rgba(107,127,163,0.4)" : "rgba(0,212,255,0.8)",
                        border: `1px solid ${i === 0 ? "rgba(107,127,163,0.5)" : "rgba(0,212,255,0.5)"}`,
                        transform: "rotate(45deg)",
                      }}
                    />
                    {i < pipeline.length - 1 && (
                      <div
                        className="flex-1 w-px my-1"
                        style={{
                          background: "linear-gradient(to bottom, rgba(0,212,255,0.4), rgba(0,212,255,0.1))",
                        }}
                      />
                    )}
                  </div>

                  {/* Label */}
                  <div
                    className="mb-1 px-4 py-2.5 flex-1 border-l-2 transition-all duration-200 hover:border-primary/60 hover:bg-primary/5"
                    style={{
                      borderColor: i === 0 ? "rgba(107,127,163,0.3)" : "rgba(0,212,255,0.25)",
                      background: i === 0 ? "rgba(107,127,163,0.04)" : "rgba(0,212,255,0.04)",
                    }}
                  >
                    <div
                      className="font-['JetBrains_Mono'] text-xs"
                      style={{ color: i === 0 ? "#6b7fa3" : "#e8edf5" }}
                    >
                      {step}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ModulesSection() {
  const [active, setActive] = useState<number | null>(null);

  return (
    <section id="modules" className="relative py-32 overflow-hidden">
      <GlowOrb x="50%" y="50%" size="800px" color="#0057ff" opacity={0.05} />

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div className="text-center mb-16">
          <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">03 — MODULES</div>
          <h2 className="font-['Rajdhani'] font-700 text-4xl sm:text-5xl text-foreground mb-4">
            Les <span style={{ color: "#00d4ff" }}>15 modules</span>
          </h2>
          <p className="font-['Inter'] text-sm text-muted-foreground max-w-lg mx-auto">
            Chaque module est indépendant, spécialisé et traçable. Ensemble ils forment un système autonome complet.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {modules.map((mod) => (
            <div
              key={mod.id}
              className="relative p-5 border cursor-pointer transition-all duration-300 group"
              style={{
                background: active === mod.id ? `${mod.color}08` : "rgba(11,18,32,0.7)",
                borderColor: active === mod.id ? `${mod.color}40` : "rgba(0,212,255,0.08)",
              }}
              onClick={() => setActive(active === mod.id ? null : mod.id)}
            >
              {/* Module number */}
              <div
                className="absolute top-3 right-4 font-['JetBrains_Mono'] text-xs"
                style={{ color: `${mod.color}40` }}
              >
                {String(mod.id).padStart(2, "0")}
              </div>

              {/* Icon + title */}
              <div className="flex items-start gap-3 mb-3">
                <div
                  className="w-9 h-9 flex items-center justify-center shrink-0"
                  style={{ background: `${mod.color}15`, color: mod.color, border: `1px solid ${mod.color}25` }}
                >
                  {mod.icon}
                </div>
                <div>
                  <div className="font-['Rajdhani'] font-700 text-sm text-foreground leading-tight">{mod.title}</div>
                  <div className="font-['JetBrains_Mono'] text-xs mt-0.5" style={{ color: mod.color }}>
                    {mod.subtitle}
                  </div>
                </div>
              </div>

              <p className="font-['Inter'] text-xs text-muted-foreground leading-relaxed mb-3">{mod.description}</p>

              {/* Expandable bullets */}
              {active === mod.id && (
                <div className="border-t pt-3 mt-2" style={{ borderColor: `${mod.color}20` }}>
                  <ul className="space-y-1.5">
                    {mod.bullets.map((b) => (
                      <li key={b} className="flex items-center gap-2 font-['Inter'] text-xs text-muted-foreground">
                        <span className="w-1 h-1 rounded-full shrink-0" style={{ background: mod.color }} />
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex items-center justify-end mt-3">
                <ChevronDown
                  className="w-3.5 h-3.5 transition-transform duration-200"
                  style={{
                    color: mod.color,
                    transform: active === mod.id ? "rotate(180deg)" : "rotate(0deg)",
                  }}
                />
              </div>

              {/* Bottom accent line */}
              <div
                className="absolute bottom-0 left-0 right-0 h-px transition-all duration-300"
                style={{ background: `linear-gradient(90deg, transparent, ${mod.color}${active === mod.id ? "60" : "20"}, transparent)` }}
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TechSection() {
  return (
    <section id="technologies" className="relative py-32 overflow-hidden">
      <GridLines />
      <GlowOrb x="0%" y="70%" size="500px" color="#8b5cf6" opacity={0.08} />

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">04 — TECHNOLOGIES</div>
            <h2 className="font-['Rajdhani'] font-700 text-4xl sm:text-5xl text-foreground mb-6 leading-tight">
              Stack<br />
              <span style={{ color: "#00d4ff" }}>production-grade</span>
            </h2>
            <p className="font-['Inter'] text-sm text-muted-foreground leading-relaxed max-w-md">
              Chaque choix technologique est justifié par des exigences de performance, de fiabilité et de scalabilité.
              Rien de superflu.
            </p>
          </div>

          <div className="space-y-4">
            {techStack.map((cat) => (
              <div
                key={cat.category}
                className="p-5 border border-border transition-all duration-200 hover:border-primary/25"
                style={{ background: "rgba(11,18,32,0.7)" }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary">{cat.icon}</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest">{cat.category}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {cat.items.map((item) => (
                    <span
                      key={item}
                      className="font-['JetBrains_Mono'] text-xs px-2.5 py-1"
                      style={{
                        background: "rgba(0,212,255,0.06)",
                        color: "#e8edf5",
                        border: "1px solid rgba(0,212,255,0.12)",
                      }}
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function RoadmapSection() {
  const [activePhase, setActivePhase] = useState(1);

  return (
    <section id="roadmap" className="relative py-32 overflow-hidden">
      <GlowOrb x="50%" y="50%" size="600px" color="#00d4ff" opacity={0.05} />

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div className="text-center mb-16">
          <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">05 — FEUILLE DE ROUTE</div>
          <h2 className="font-['Rajdhani'] font-700 text-4xl sm:text-5xl text-foreground mb-4">
            5 phases vers <span style={{ color: "#00d4ff" }}>l'autonomie</span>
          </h2>
        </div>

        {/* Phase tabs */}
        <div className="flex flex-wrap justify-center gap-2 mb-12">
          {phases.map((p) => (
            <button
              key={p.id}
              onClick={() => setActivePhase(p.id)}
              className="flex items-center gap-2 px-4 py-2.5 font-['Rajdhani'] font-600 text-sm tracking-wider transition-all duration-200"
              style={{
                background: activePhase === p.id ? `${p.color}15` : "rgba(11,18,32,0.6)",
                color: activePhase === p.id ? p.color : "#6b7fa3",
                border: `1px solid ${activePhase === p.id ? p.color + "40" : "rgba(0,212,255,0.08)"}`,
              }}
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: activePhase === p.id ? p.color : "#6b7fa3" }}
              />
              {p.label}
            </button>
          ))}
        </div>

        {/* Phase detail */}
        {phases.map((p) =>
          p.id === activePhase ? (
            <div key={p.id} className="max-w-2xl mx-auto">
              <div
                className="p-8 border text-center"
                style={{
                  background: `${p.color}06`,
                  borderColor: `${p.color}30`,
                  clipPath: "polygon(0 0, calc(100% - 24px) 0, 100% 24px, 100% 100%, 24px 100%, 0 calc(100% - 24px))",
                }}
              >
                <div className="font-['JetBrains_Mono'] text-xs mb-2" style={{ color: p.color }}>
                  {p.label}
                </div>
                <h3 className="font-['Rajdhani'] font-700 text-3xl text-foreground mb-6">{p.name}</h3>
                <div className="flex flex-wrap justify-center gap-3">
                  {p.items.map((item) => (
                    <div
                      key={item}
                      className="flex items-center gap-2 px-4 py-2 font-['Inter'] text-sm"
                      style={{
                        background: `${p.color}10`,
                        border: `1px solid ${p.color}25`,
                        color: "#e8edf5",
                      }}
                    >
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: p.color }} />
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null
        )}

        {/* Timeline dots */}
        <div className="flex items-center justify-center mt-12 gap-0">
          {phases.map((p, i) => (
            <div key={p.id} className="flex items-center">
              <button
                className="w-3 h-3 rounded-full transition-all duration-200"
                style={{ background: p.id <= activePhase ? p.color : "rgba(107,127,163,0.3)" }}
                onClick={() => setActivePhase(p.id)}
              />
              {i < phases.length - 1 && (
                <div
                  className="w-16 h-px"
                  style={{ background: p.id < activePhase ? phases[i].color : "rgba(107,127,163,0.2)" }}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function WhyDifferentSection() {
  const points = [
    {
      icon: <RefreshCw className="w-5 h-5" />,
      title: "Auto-amélioration contrôlée",
      desc: "Chaque changement est proposé par le Coach IA, testé dans le Laboratoire, validé, puis déployé progressivement — jamais directement.",
    },
    {
      icon: <Shield className="w-5 h-5" />,
      title: "Validation rigoureuse",
      desc: "Aucune amélioration n'est déployée sans démontrer une robustesse réelle. Backtest + Walk-forward + Paper trading.",
    },
    {
      icon: <Eye className="w-5 h-5" />,
      title: "Traçabilité totale",
      desc: "Chaque décision est enregistrée avec son contexte, sa stratégie, son score de confiance et son résultat. Rien n'est opaque.",
    },
    {
      icon: <TrendingUp className="w-5 h-5" />,
      title: "Robustesse avant profit",
      desc: "L'objectif est de maximiser l'espérance de gain sur le long terme, pas de garantir des profits à court terme.",
    },
  ];

  return (
    <section className="relative py-32 overflow-hidden">
      <GridLines />
      <GlowOrb x="50%" y="50%" size="700px" color="#00d4ff" opacity={0.06} />

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <div className="text-center mb-16">
          <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">06 — DIFFÉRENCIATION</div>
          <h2 className="font-['Rajdhani'] font-700 text-4xl sm:text-5xl text-foreground mb-6 leading-tight">
            Ce qui rend<br />
            <span style={{ color: "#00d4ff" }}>AEGIS différent</span>
          </h2>
          <p className="font-['Inter'] text-base text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            L'idée centrale n'est pas de créer un bot qui trade, mais un système qui apprend à construire et améliorer
            ses propres stratégies de manière contrôlée.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-6 mb-20">
          {points.map((p) => (
            <div
              key={p.title}
              className="p-6 border border-border hover:border-primary/30 transition-all duration-300 group"
              style={{ background: "rgba(11,18,32,0.7)" }}
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 flex items-center justify-center text-primary" style={{ background: "rgba(0,212,255,0.1)", border: "1px solid rgba(0,212,255,0.2)" }}>
                  {p.icon}
                </div>
                <h3 className="font-['Rajdhani'] font-700 text-lg text-foreground">{p.title}</h3>
              </div>
              <p className="font-['Inter'] text-sm text-muted-foreground leading-relaxed">{p.desc}</p>
            </div>
          ))}
        </div>

        {/* Final CTA block */}
        <div
          className="relative p-12 text-center border border-primary/20 overflow-hidden"
          style={{
            background: "rgba(0,87,255,0.05)",
            clipPath: "polygon(0 0, calc(100% - 32px) 0, 100% 32px, 100% 100%, 32px 100%, 0 calc(100% - 32px))",
          }}
        >
          <GlowOrb x="50%" y="50%" size="400px" color="#00d4ff" opacity={0.08} />
          <div className="relative z-10">
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">AEGIS AI QUANT V1</div>
            <h2 className="font-['Rajdhani'] font-700 text-4xl sm:text-5xl text-foreground mb-6">
              Robustesse <span style={{ color: "#00d4ff" }}>avant tout</span>
            </h2>
            <p className="font-['Inter'] text-sm text-muted-foreground mb-10 max-w-md mx-auto">
              Système autonome de trading crypto. Version 1.0 — Document technique confidentiel.
            </p>
            <div className="flex flex-wrap gap-4 justify-center">
              <button
                className="px-8 py-3 font-['Rajdhani'] font-700 tracking-wider text-sm transition-all duration-200 hover:scale-105"
                style={{
                  background: "linear-gradient(135deg, #00d4ff, #0057ff)",
                  color: "#04080f",
                  clipPath: "polygon(12px 0%, 100% 0%, calc(100% - 12px) 100%, 0% 100%)",
                }}
              >
                ACCÉDER AU SYSTÈME
              </button>
              <button
                className="px-8 py-3 font-['Rajdhani'] font-700 tracking-wider text-sm border border-primary/30 text-primary hover:bg-primary/5 transition-all duration-200"
                style={{ clipPath: "polygon(12px 0%, 100% 0%, calc(100% - 12px) 100%, 0% 100%)" }}
              >
                DOCUMENTATION
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function OperationsSection() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const data = await getDashboard();
        if (active) {
          setSnapshot(data);
          setError(false);
        }
      } catch {
        if (active) setError(true);
      }
    };
    void refresh();
    const intervalId = window.setInterval(() => void refresh(), 15_000);
    return () => { active = false; window.clearInterval(intervalId); };
  }, []);

  return (
    <section id="operations" className="relative py-24 border-y border-border" style={{ background: "rgba(4,8,15,0.7)" }}>
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-10">
          <div><div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-3">07 — OPÉRATIONS</div><h2 className="font-['Rajdhani'] font-700 text-4xl text-foreground">État <span className="text-primary">AEGIS</span></h2></div>
          <div className={`font-['JetBrains_Mono'] text-xs ${error ? "text-red-400" : "text-green-400"}`}>{error ? "API INDISPONIBLE" : "ACTUALISATION 15s"}</div>
        </div>
        {snapshot && <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Qualité données", value: snapshot.data_quality.valid ? "VALIDE" : "BLOQUÉE", detail: `${snapshot.data_quality.candle_count} bougies · ${snapshot.data_quality.gap_count} trous`, color: snapshot.data_quality.valid ? "#22c55e" : "#ef4444" },
            { label: "Régime marché", value: snapshot.market_analysis?.regime.regime ?? "N/A", detail: `Confiance ${((snapshot.market_analysis?.regime.confidence ?? 0) * 100).toFixed(0)}%`, color: "#00d4ff" },
            { label: "Risque historique", value: snapshot.risk ? `VaR $${snapshot.risk.value_at_risk.toLocaleString("fr-FR")}` : "N/A", detail: snapshot.risk ? `CVaR $${snapshot.risk.conditional_value_at_risk.toLocaleString("fr-FR")}` : "Historique insuffisant", color: "#f59e0b" },
            { label: "Superviseur", value: snapshot.supervisor.kill_switch_active ? "ARRÊT ACTIF" : "SURVEILLÉ", detail: `${snapshot.alerts.length} alertes journalisées`, color: snapshot.supervisor.kill_switch_active ? "#ef4444" : "#22c55e" },
          ].map((card) => <div key={card.label} className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}><div className="font-['JetBrains_Mono'] text-xs text-muted-foreground mb-3">{card.label.toUpperCase()}</div><div className="font-['Rajdhani'] text-2xl font-700" style={{ color: card.color }}>{card.value}</div><div className="font-['Inter'] text-xs text-muted-foreground mt-2">{card.detail}</div></div>)}
        </div>}
        {snapshot && <div className="grid lg:grid-cols-2 gap-4 mt-4">
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">BIBLIOTHÈQUE DE STRATÉGIES</div>
            <div className="space-y-3">{snapshot.strategy_registry.map((strategy) => <div key={strategy.id} className="flex items-center justify-between gap-3"><div><div className="font-['Inter'] text-sm text-foreground">{strategy.name}</div><div className="font-['JetBrains_Mono'] text-xs text-muted-foreground">{strategy.type}</div></div><span className="font-['JetBrains_Mono'] text-xs text-primary">{strategy.status.toUpperCase()}</span></div>)}</div>
          </div>
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">COACH & MÉMOIRE</div>
            <div className="font-['Inter'] text-sm text-foreground mb-3">{snapshot.coach.reviewed_backtests} backtests analysés</div>
            <div className="space-y-2">{snapshot.coach.recommendations.slice(0, 3).map((item, index) => <div key={`${item.action}-${index}`} className="font-['JetBrains_Mono'] text-xs text-muted-foreground">{item.action.replaceAll("_", " ").toUpperCase()} {item.reason ? `— ${item.reason}` : ""}</div>)}</div>
            {snapshot.recent_decisions[0] && <div className="mt-4 border-t border-border pt-3 font-['JetBrains_Mono'] text-xs text-muted-foreground">DERNIÈRE DÉCISION: {snapshot.recent_decisions[0].decision.recommendation?.action?.toUpperCase() ?? "N/A"}</div>}
          </div>
        </div>}
        {snapshot && <div className="grid lg:grid-cols-3 gap-4 mt-4">
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="flex items-center justify-between mb-4">
              <div className="font-['JetBrains_Mono'] text-xs text-primary">FEAR & GREED</div>
              <span className="font-['JetBrains_Mono'] text-xs text-muted-foreground">{snapshot.fear_greed[0]?.value ?? "—"}/100</span>
            </div>
            {snapshot.fear_greed[0] ? (
              <div>
                <div className="font-['Rajdhani'] text-2xl font-700" style={{ color: (snapshot.fear_greed[0].value ?? 50) < 30 ? "#ef4444" : (snapshot.fear_greed[0].value ?? 50) > 70 ? "#22c55e" : "#f59e0b" }}>
                  {snapshot.fear_greed[0].classification}
                </div>
                <div className="font-['Inter'] text-xs text-muted-foreground mt-1">Source: alternative.me</div>
              </div>
            ) : (
              <div className="font-['Inter'] text-xs text-muted-foreground/50">Pas de données — cliquer Refresh</div>
            )}
          </div>
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">FUNDING RATE</div>
            {snapshot.funding_rates.length > 0 ? (
              <div className="space-y-2">
                {snapshot.funding_rates.slice(0, 3).map((fr) => (
                  <div key={fr.symbol} className="flex items-center justify-between">
                    <span className="font-['Inter'] text-xs text-foreground">{fr.symbol}</span>
                    <span className={`font-['JetBrains_Mono'] text-xs ${fr.funding_rate >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {(fr.funding_rate * 100).toFixed(4)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">OPEN INTEREST</div>
            {snapshot.open_interest.length > 0 ? (
              <div className="space-y-2">
                {snapshot.open_interest.slice(0, 3).map((oi) => (
                  <div key={oi.symbol} className="flex items-center justify-between">
                    <span className="font-['Inter'] text-xs text-foreground">{oi.symbol}</span>
                    <span className="font-['JetBrains_Mono'] text-xs text-muted-foreground">
                      ${(oi.open_interest_usd / 1_000_000).toFixed(1)}M
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="font-['Inter'] text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
        </div>}
        {snapshot && <div className="border border-border p-5 mt-4" style={{ background: "rgba(11,18,32,0.7)" }}>
          <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">MÉMOIRE ÉPISODIQUE</div>
          <div className="grid md:grid-cols-3 gap-4">
            <div>
              <div className="font-['Rajdhani'] text-2xl font-700 text-foreground">{snapshot.memory.total_episodes}</div>
              <div className="font-['Inter'] text-xs text-muted-foreground">Épisodes enregistrés</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-2xl font-700 text-foreground">{snapshot.memory.strategies_used.length}</div>
              <div className="font-['Inter'] text-xs text-muted-foreground">Stratégies suivies</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-2xl font-700" style={{ color: (snapshot.memory.avg_result ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                {snapshot.memory.avg_result !== null ? `${(snapshot.memory.avg_result * 100).toFixed(2)}%` : "—"}
              </div>
              <div className="font-['Inter'] text-xs text-muted-foreground">Rendement moyen</div>
            </div>
          </div>
          {snapshot.memory.strategies_used.length > 0 && (
            <div className="mt-4 border-t border-border pt-3 space-y-2">
              {snapshot.memory.strategies_used.map((s) => (
                <div key={s.strategy} className="flex items-center justify-between">
                  <span className="font-['Inter'] text-xs text-foreground">{s.strategy}</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-muted-foreground">
                    {s.count} épisodes · WR {(s.win_rate * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>}
        {snapshot && <div className="grid lg:grid-cols-3 gap-4 mt-4">
          {/* Stress Test */}
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">STRESS TEST</div>
            {snapshot.stress_test ? (
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-xs text-muted-foreground">Pire jour</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-red-400">{snapshot.stress_test.worst_day_return.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-xs text-muted-foreground">Pire semaine</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-red-400">{snapshot.stress_test.worst_week_return.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-xs text-muted-foreground">Pire mois</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-red-400">{snapshot.stress_test.worst_month_return.toFixed(1)}%</span>
                </div>
                <div className="border-t border-border pt-2 mt-2">
                  {snapshot.stress_test.scenarios.slice(0, 3).map((s) => (
                    <div key={s.name} className="flex justify-between py-1">
                      <span className="font-['Inter'] text-xs text-muted-foreground">{s.name}</span>
                      <span className="font-['JetBrains_Mono'] text-xs text-red-400">${Math.abs(s.portfolio_impact).toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="font-['Inter'] text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
          {/* Correlation */}
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">CORRÉLATION</div>
            {snapshot.correlation ? (
              <div className="space-y-2">
                <div className="flex justify-between mb-3">
                  <span className="font-['Inter'] text-xs text-muted-foreground">Moyenne</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-foreground">{snapshot.correlation.avg_correlation?.toFixed(2) ?? "—"}</span>
                </div>
                <div className="font-['Inter'] text-xs text-muted-foreground mb-2">{snapshot.correlation.interpretation}</div>
                <div className="space-y-1">
                  {snapshot.correlation.symbols.map((sym) => (
                    <div key={sym} className="flex items-center gap-2">
                      <span className="font-['JetBrains_Mono'] text-xs text-foreground w-16">{sym.replace("USDT", "")}</span>
                      <div className="flex-1 h-1.5 rounded-full" style={{ background: "rgba(0,212,255,0.1)" }}>
                        <div className="h-full rounded-full" style={{ width: `${Math.abs((snapshot.correlation?.matrix[sym]?.[sym] ?? 1)) * 100}%`, background: "#00d4ff" }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="font-['Inter'] text-xs text-muted-foreground/50">Pas de données</div>
            )}
          </div>
          {/* Concentration */}
          <div className="border border-border p-5" style={{ background: "rgba(11,18,32,0.7)" }}>
            <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">CONCENTRATION</div>
            {snapshot.concentration && snapshot.concentration.position_count > 0 ? (
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-xs text-muted-foreground">Exposition totale</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-foreground">${snapshot.concentration.total_exposure.toLocaleString("fr-FR")}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-xs text-muted-foreground">HHI</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-foreground">{snapshot.concentration.herfindahl.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-['Inter'] text-xs text-muted-foreground">Max concentration</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-foreground">{snapshot.concentration.max_concentration.toFixed(1)}%</span>
                </div>
                <div className="border-t border-border pt-2 mt-2 space-y-1">
                  {snapshot.concentration.positions.map((p) => (
                    <div key={p.symbol} className="flex justify-between">
                      <span className="font-['JetBrains_Mono'] text-xs text-foreground">{p.symbol}</span>
                      <span className="font-['JetBrains_Mono'] text-xs text-muted-foreground">{p.weight}%</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="font-['Inter'] text-xs text-muted-foreground/50">Aucune position ouverte</div>
            )}
          </div>
        </div>}
        {snapshot && snapshot.journal && <div className="border border-border p-5 mt-4" style={{ background: "rgba(11,18,32,0.7)" }}>
          <div className="font-['JetBrains_Mono'] text-xs text-primary mb-4">JOURNAL DE DÉCISIONS</div>
          <div className="grid md:grid-cols-4 gap-4 mb-4">
            <div>
              <div className="font-['Rajdhani'] text-2xl font-700 text-foreground">{snapshot.journal.total_decisions}</div>
              <div className="font-['Inter'] text-xs text-muted-foreground">Décisions totales</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-2xl font-700" style={{ color: (snapshot.journal.accuracy ?? 0) >= 0.5 ? "#22c55e" : "#ef4444" }}>
                {snapshot.journal.accuracy !== null ? `${(snapshot.journal.accuracy * 100).toFixed(0)}%` : "—"}
              </div>
              <div className="font-['Inter'] text-xs text-muted-foreground">Précision</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-2xl font-700" style={{ color: (snapshot.journal.avg_pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                {snapshot.journal.avg_pnl !== null ? `${(snapshot.journal.avg_pnl * 100).toFixed(2)}%` : "—"}
              </div>
              <div className="font-['Inter'] text-xs text-muted-foreground">PnL moyen</div>
            </div>
            <div>
              <div className="font-['Rajdhani'] text-lg font-700 text-primary">{snapshot.journal.feedback.grade}</div>
              <div className="font-['Inter'] text-xs text-muted-foreground">Évaluation</div>
            </div>
          </div>
          {snapshot.journal.feedback.strengths.length > 0 && (
            <div className="mb-3">
              <div className="font-['JetBrains_Mono'] text-xs text-green-400 mb-1">FORCES</div>
              {snapshot.journal.feedback.strengths.map((s, i) => (
                <div key={i} className="font-['Inter'] text-xs text-muted-foreground">+ {s}</div>
              ))}
            </div>
          )}
          {snapshot.journal.feedback.weaknesses.length > 0 && (
            <div>
              <div className="font-['JetBrains_Mono'] text-xs text-red-400 mb-1">POINTS D'AMÉLIORATION</div>
              {snapshot.journal.feedback.weaknesses.map((w, i) => (
                <div key={i} className="font-['Inter'] text-xs text-muted-foreground">- {w}</div>
              ))}
            </div>
          )}
          {Object.keys(snapshot.journal.by_action).length > 0 && (
            <div className="mt-4 border-t border-border pt-3">
              <div className="font-['JetBrains_Mono'] text-xs text-primary mb-2">PAR ACTION</div>
              <div className="space-y-1">
                {Object.entries(snapshot.journal.by_action).map(([action, data]) => (
                  <div key={action} className="flex items-center justify-between">
                    <span className="font-['Inter'] text-xs text-foreground">{action}</span>
                    <span className="font-['JetBrains_Mono'] text-xs text-muted-foreground">
                      {data.count}× · WR {(data.accuracy * 100).toFixed(0)}% {data.avg_pnl !== null ? `· PnL ${(data.avg_pnl * 100).toFixed(2)}%` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>}
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="relative border-t border-border py-12">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="relative w-7 h-7">
              <div className="absolute inset-0 rounded border border-primary/60" style={{ transform: "rotate(45deg)" }} />
              <Activity className="absolute inset-0 m-auto w-3.5 h-3.5 text-primary" />
            </div>
            <span className="font-['Rajdhani'] font-700 text-base tracking-[0.12em] text-foreground">
              AEGIS <span className="text-primary">AI QUANT</span>
            </span>
          </div>

          <div className="flex flex-wrap gap-6">
            {["Vision", "Architecture", "Modules", "Technologies", "Roadmap"].map((l) => (
              <a
                key={l}
                href={`#${l.toLowerCase()}`}
                className="font-['Inter'] text-xs text-muted-foreground hover:text-primary transition-colors"
              >
                {l}
              </a>
            ))}
          </div>

          <div className="font-['JetBrains_Mono'] text-xs text-muted-foreground/50 text-center">
            © 2025 AEGIS AI QUANT V1 — CONFIDENTIEL
          </div>
        </div>
      </div>
    </footer>
  );
}

// --- Root ---
export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden" style={{ fontFamily: "Inter, sans-serif" }}>
      <NavBar />
      <HeroSection />
      <ArchitectureSection />
      <ModulesSection />
      <TechSection />
      <RoadmapSection />
      <WhyDifferentSection />
      <OperationsSection />
      <Footer />
    </div>
  );
}
