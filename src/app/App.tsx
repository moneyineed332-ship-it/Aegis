import { useState, useEffect, useCallback, useMemo, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, useNavigate, useLocation, Navigate } from "react-router-dom";
import { activateEmergencyStop, getDashboard, getSupervisor, refreshFearGreed, refreshFundingRates, refreshHistory, refreshMarketData, resumeSupervisor, type DashboardSnapshot, type SupervisorStatus } from "../lib/api";
import { ErrorBoundary } from "./components/ErrorBoundary";
import BackToTop from "./components/BackToTop";
import Sidebar from "./components/dashboard/Sidebar";
import DashboardHero from "./components/dashboard/DashboardHero";
import DashboardGrid from "./components/dashboard/DashboardGrid";
import { GlowOrb, Button, Skeleton } from "./components/ui";
import { ToastProvider, useToast } from "./components/Toast";
import { AlertWebSocketProvider } from "./components/AlertWebSocketProvider";

const LandingPage = lazy(() => import("./sections/LandingPage"));
const PortfolioSection = lazy(() => import("./sections/PortfolioSection"));
const RiskSection = lazy(() => import("./sections/RiskSection"));
const MLRegimeSection = lazy(() => import("./sections/MLRegimeSection"));
const AlertsSection = lazy(() => import("./sections/AlertsSection"));
const AdvancedBacktestSection = lazy(() => import("./sections/AdvancedBacktestSection"));
const BinanceTestnetSection = lazy(() => import("./sections/BinanceTestnetSection"));
const MultiAssetSection = lazy(() => import("./sections/MultiAssetSection"));
const OptimizerSection = lazy(() => import("./sections/OptimizerSection"));
const AIAnalystSection = lazy(() => import("./sections/AIAnalystSection"));
const FreeApisSection = lazy(() => import("./sections/FreeApisSection"));
const JournalSection = lazy(() => import("./sections/JournalSection"));
const EngineSection = lazy(() => import("./sections/EngineSection"));
const LearningSection = lazy(() => import("./sections/LearningSection"));
const PositionMonitorSection = lazy(() => import("./sections/PositionMonitorSection"));
const SecuritySection = lazy(() => import("./sections/SecuritySection"));
const OperationsSection = lazy(() => import("./sections/OperationsSection"));
const SMCSection = lazy(() => import("./sections/SMCSection"));
import {
  Activity,
  AlertTriangle,
  Menu,
} from "lucide-react";

const VALID_SECTIONS = new Set([
  "overview", "portfolio", "risk", "regime", "ai", "backtest",
  "optimizer", "alerts", "testnet", "multi-asset", "free-apis", "journal", "engine",
  "learning", "positions", "security", "operations", "smc",
]);

// --- Transitions ---
function PageTransition({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
    // Focus main content for accessibility on route change
    const main = document.getElementById("main-content");
    if (main) main.focus();
  }, [location.pathname]);
  return (
    <div key={location.pathname} className="animate-[fadeIn_0.3s_ease-out]">
      {children}
    </div>
  );
}

// --- Routes ---
function AppRoutes() {
  const navigate = useNavigate();
  return (
    <Routes>
      <Route path="/" element={<PageTransition><Suspense fallback={<Skeleton className="h-screen" />}><LandingPage onEnter={() => navigate("/dashboard")} /></Suspense></PageTransition>} />
      <Route path="/dashboard" element={<Navigate to="/dashboard/overview" replace />} />
      <Route path="/dashboard/:section" element={<PageTransition><DashboardLayout /></PageTransition>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// --- Dashboard Layout ---
function DashboardLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const urlSection = location.pathname.split("/").pop() ?? "overview";
  const activeSection = VALID_SECTIONS.has(urlSection) ? urlSection : "overview";

  const [dashboard, setDashboard] = useState<DashboardSnapshot | null>(null);
  const [apiOnline, setApiOnline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [operation, setOperation] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [supervisor, setSupervisor] = useState<SupervisorStatus | null>(null);

  const refreshDashboard = useCallback(async () => {
    try {
      const snapshot = await getDashboard();
      setDashboard(snapshot);
      setApiOnline(true);
    } catch {
      setApiOnline(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshDashboard();
    const id = window.setInterval(() => void refreshDashboard(), 15_000);
    return () => window.clearInterval(id);
  }, [refreshDashboard]);

  useEffect(() => {
    void getSupervisor().then(setSupervisor).catch(() => setSupervisor(null));
  }, []);

  const runResearchAction = useCallback(async (label: string, action: () => Promise<unknown>) => {
    setOperation(label);
    setOperationError(null);
    setLoading(true);
    try {
      await action();
      await refreshDashboard();
      setSupervisor(await getSupervisor());
      setApiOnline(true);
      toast.success(`${label} terminé`);
    } catch {
      setOperationError("Action impossible : vérifie que l'API AEGIS est lancée.");
      toast.error("Action impossible : vérifie que l'API AEGIS est lancée.");
    } finally {
      setOperation(null);
      setLoading(false);
    }
  }, [refreshDashboard, toast]);

  const handleNavigate = useCallback((section: string) => {
    navigate(`/dashboard/${section}`, { replace: true });
  }, [navigate]);

  const overviewSection = useMemo(() => (
    <div className="space-y-6">
      <ErrorBoundary>
        <DashboardHero data={dashboard} onRefresh={refreshDashboard} loading={loading} />
      </ErrorBoundary>
      <ErrorBoundary>
        <DashboardGrid data={dashboard} activeSection={activeSection} onNavigate={handleNavigate} />
      </ErrorBoundary>
    </div>
  ), [dashboard, loading, activeSection, handleNavigate, refreshDashboard]);

  const sectionContent = useMemo(() => ({
    overview: overviewSection,
    portfolio: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><PortfolioSection /></Suspense></ErrorBoundary>,
    risk: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><RiskSection /></Suspense></ErrorBoundary>,
    regime: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><MLRegimeSection /></Suspense></ErrorBoundary>,
    ai: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><AIAnalystSection /></Suspense></ErrorBoundary>,
    backtest: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><AdvancedBacktestSection /></Suspense></ErrorBoundary>,
    optimizer: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><OptimizerSection /></Suspense></ErrorBoundary>,
    alerts: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><AlertsSection /></Suspense></ErrorBoundary>,
    testnet: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><BinanceTestnetSection /></Suspense></ErrorBoundary>,
    "multi-asset": <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><MultiAssetSection /></Suspense></ErrorBoundary>,
    "free-apis": <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><FreeApisSection /></Suspense></ErrorBoundary>,
    journal: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><JournalSection /></Suspense></ErrorBoundary>,
    engine: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><EngineSection onRefresh={refreshDashboard} /></Suspense></ErrorBoundary>,
    learning: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><LearningSection /></Suspense></ErrorBoundary>,
    positions: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><PositionMonitorSection /></Suspense></ErrorBoundary>,
    security: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><SecuritySection /></Suspense></ErrorBoundary>,
    operations: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><OperationsSection /></Suspense></ErrorBoundary>,
    smc: <ErrorBoundary><Suspense fallback={<Skeleton className="h-64" />}><SMCSection /></Suspense></ErrorBoundary>,
  }), [overviewSection]);

  // Memoize inline styles to avoid re-creation on every render
  const fontFamilyStyle = useMemo(() => ({ fontFamily: "Inter, sans-serif" }), []);
  const headerStyle = useMemo(() => ({ background: "rgba(4,8,15,0.85)" }), []);
  const operationStyle = useMemo(() => ({ background: "rgba(0,212,255,0.05)" }), []);
  const errorStyle = useMemo(() => ({ background: "rgba(255,51,102,0.05)" }), []);

  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden" style={fontFamilyStyle}>
      {/* Skip navigation for accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-primary focus:text-white focus:rounded-lg"
      >
        Aller au contenu principal
      </a>

      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <GlowOrb x="20%" y="30%" size="600px" color="#0057ff" opacity={0.06} />
        <GlowOrb x="80%" y="70%" size="500px" color="#00d4ff" opacity={0.04} />
        <GlowOrb x="50%" y="10%" size="400px" color="#8b5cf6" opacity={0.03} />
      </div>

      {/* Sidebar */}
      <ErrorBoundary fallback={<div className="w-16 h-screen bg-background border-r border-border" />}>
        <Sidebar
          data={dashboard}
          activeSection={activeSection}
          onNavigate={handleNavigate}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          mobileOpen={mobileMenuOpen}
          onMobileClose={() => setMobileMenuOpen(false)}
        />
      </ErrorBoundary>

      {/* Main Content */}
      <div
        className="relative z-10 min-h-screen dashboard-layout"
        style={{ "--sidebar-w": sidebarCollapsed ? "68px" : "240px" } as React.CSSProperties}
      >
        <div className="dashboard-main">
          {/* Top Bar */}
          <header className="sticky top-0 z-30 h-12 flex items-center justify-between px-4 sm:px-6 border-b border-border backdrop-blur-xl" style={headerStyle}>
            <div className="flex items-center gap-3">
              {/* Mobile menu button */}
              <button
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Ouvrir le menu"
                className="lg:hidden p-1.5 rounded-lg border border-border hover:border-primary/30 transition-all"
              >
                <Menu className="w-4 h-4 text-muted-foreground" />
              </button>
              <div className="flex items-center gap-2">
                <span className="font-['Rajdhani'] font-bold text-sm text-foreground tracking-wider">AEGIS</span>
                <span className="font-['JetBrains_Mono'] text-[10px] text-primary/60 tracking-widest hidden sm:inline">AI QUANT V1</span>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              {/* Operation status */}
              {operation && (
                <div className="flex items-center gap-2 px-2 py-1 rounded-lg border border-primary/20" style={operationStyle}>
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  <span className="font-['JetBrains_Mono'] text-[12px] text-primary hidden sm:inline">{operation}...</span>
                </div>
              )}
              {operationError && (
                <div className="flex items-center gap-2 px-2 py-1 rounded-lg border border-destructive/20" style={errorStyle}>
                  <AlertTriangle className="w-3 h-3 text-destructive" />
                  <span className="font-['JetBrains_Mono'] text-[12px] text-destructive hidden sm:inline">ERREUR</span>
                </div>
              )}

              {/* Quick actions */}
              <div className="hidden sm:flex items-center gap-1">
                <Button size="sm" variant="ghost" aria-label="Rafraîchir les prix" onClick={() => void runResearchAction("Mise à jour marché", refreshMarketData)} disabled={Boolean(operation)} loading={operation === "Mise à jour marché"}>
                  PRIX
                </Button>
                <Button size="sm" variant="ghost" aria-label="Charger l'historique OHLCV" onClick={() => void runResearchAction("Historique", refreshHistory)} disabled={Boolean(operation)} loading={operation === "Historique"}>
                  OHLCV
                </Button>
                <Button size="sm" variant="ghost" aria-label="Rafraîchir le Fear & Greed Index" onClick={() => void runResearchAction("Fear & Greed", refreshFearGreed)} disabled={Boolean(operation)} loading={operation === "Fear & Greed"}>
                  F&G
                </Button>
                <Button size="sm" variant="ghost" aria-label="Rafraîchir les Funding Rates" onClick={() => void runResearchAction("Funding Rate", () => refreshFundingRates())} disabled={Boolean(operation)} loading={operation === "Funding Rate"}>
                  FUND
                </Button>
              </div>

              {/* Status */}
              <div className="flex items-center gap-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${apiOnline ? "bg-success" : "bg-destructive animate-pulse"}`} />
                <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground hidden sm:inline">
                  {apiOnline ? "API OK" : "API OFF"}
                </span>
              </div>

              {/* Emergency controls */}
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="danger"
                  aria-label="Activer l'arrêt d'urgence"
                  onClick={() => {
                    if (window.confirm("Activer l'arrêt d'urgence ? Toutes les positions seront liquidées."))
                      void runResearchAction("Arrêt d'urgence", activateEmergencyStop);
                  }}
                  disabled={Boolean(operation) || supervisor?.kill_switch_active}
                >
                  STOP
                </Button>
                <Button
                  size="sm"
                  variant="success"
                  aria-label="Reprendre le trading"
                  onClick={() => void runResearchAction("Reprise", resumeSupervisor)}
                  disabled={Boolean(operation) || !supervisor?.kill_switch_active}
                >
                  RESUME
                </Button>
              </div>
            </div>
          </header>

          {/* Main Content Area */}
          <main id="main-content" className="p-4 sm:p-6" tabIndex={-1}>
            <div key={activeSection} className="animate-[sectionFadeIn_0.2s_ease-out]">
              {sectionContent[activeSection] ?? sectionContent.overview}
            </div>
          </main>

          {/* Footer */}
          <footer className="border-t border-border py-6 px-4 sm:px-6">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="relative w-5 h-5">
                  <div className="absolute inset-0 rounded border border-primary/60" style={{ transform: "rotate(45deg)" }} />
                  <Activity className="absolute inset-0 m-auto w-2.5 h-2.5 text-primary" />
                </div>
                <span className="font-['Rajdhani'] font-bold text-[12px] tracking-[0.12em] text-foreground">
                  AEGIS <span className="text-primary">AI QUANT</span>
                </span>
              </div>
              <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground/40">
                © 2026 AEGIS AI QUANT V1 — CONFIDENTIEL
              </div>
            </div>
          </footer>
        </div>
      </div>

      <BackToTop />
    </div>
  );
}

// --- Root ---
export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AlertWebSocketProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AlertWebSocketProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
