import { memo, useState } from "react";
import {
  Activity,
  Brain,
  Cpu,
  Database,
  FlaskConical,
  Globe,
  Layers,
  Shield,
  Target,
  Wallet,
  Wifi,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  BookOpen,
  RefreshCw,
  Zap,
  X,
  TrendingUp,
  BarChart3,
  Eye,
} from "lucide-react";
import type { DashboardSnapshot } from "../../../lib/api";

interface SidebarProps {
  data: DashboardSnapshot | null;
  activeSection: string;
  onNavigate: (section: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

const navSections = [
  { id: "overview", label: "Vue d'ensemble", icon: Layers, group: "main" },
  { id: "portfolio", label: "Portefeuille", icon: Wallet, group: "main" },
  { id: "risk", label: "Risques", icon: Shield, group: "main" },
  { id: "engine", label: "Moteur", icon: Zap, group: "main" },
  { id: "positions", label: "Positions", icon: TrendingUp, group: "main" },
  { id: "regime", label: "Régime ML", icon: Cpu, group: "analysis" },
  { id: "ai", label: "Analyste IA", icon: Brain, group: "analysis" },
  { id: "backtest", label: "Backtests", icon: FlaskConical, group: "analysis" },
  { id: "optimizer", label: "Optimiseur", icon: Target, group: "analysis" },
  { id: "learning", label: "Apprentissage", icon: BarChart3, group: "analysis" },
  { id: "smc", label: "SMC / ICT", icon: Target, group: "analysis" },
  { id: "alerts", label: "Alertes", icon: AlertTriangle, group: "tools" },
  { id: "security", label: "Securite", icon: Eye, group: "tools" },
  { id: "testnet", label: "Testnet", icon: Wifi, group: "tools" },
  { id: "multi-asset", label: "Multi-Actifs", icon: Globe, group: "tools" },
  { id: "free-apis", label: "Données Libres", icon: Database, group: "tools" },
  { id: "journal", label: "Journal", icon: BookOpen, group: "tools" },
];

const cryptoPrices = [
  { symbol: "BTC", name: "Bitcoin", color: "#f7931a" },
  { symbol: "ETH", name: "Ethereum", color: "#627eea" },
  { symbol: "SOL", name: "Solana", color: "#9945ff" },
];

function SidebarContent({
  data,
  activeSection,
  onNavigate,
  collapsed,
  onToggle,
}: {
  data: DashboardSnapshot | null;
  activeSection: string;
  onNavigate: (section: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const groups = {
    main: navSections.filter((s) => s.group === "main"),
    analysis: navSections.filter((s) => s.group === "analysis"),
    tools: navSections.filter((s) => s.group === "tools"),
  };

  const getGroupLabel = (g: string) =>
    g === "main" ? "PRINCIPAL" : g === "analysis" ? "ANALYSE" : "OUTILS";

  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 h-14 border-b border-border shrink-0">
        <div className="relative w-8 h-8 flex items-center justify-center shrink-0">
          <div
            className="absolute inset-0 rounded-lg"
            style={{ background: "linear-gradient(135deg, rgba(0,212,255,0.2), rgba(0,87,255,0.2))" }}
          />
          <Activity className="relative w-4 h-4 text-primary" />
        </div>
        {!collapsed && (
          <div className="flex flex-col min-w-0">
            <span className="font-['Rajdhani'] font-bold text-sm text-foreground tracking-wider leading-none">
              AEGIS
            </span>
            <span className="font-['JetBrains_Mono'] text-[10px] text-primary/70 tracking-widest">
              AI QUANT
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav role="navigation" aria-label="Navigation principale" className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {(Object.entries(groups) as [string, typeof navSections][]).map(([groupKey, items]) => (
          <div key={groupKey}>
            {!collapsed && (
              <div className="px-2 mb-1.5 font-['JetBrains_Mono'] text-[10px] text-muted-foreground/50 tracking-widest">
                {getGroupLabel(groupKey)}
              </div>
            )}
            <div className="space-y-0.5">
              {items.map((item) => {
                const Icon = item.icon;
                const active = activeSection === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onNavigate(item.id)}
                    aria-current={active ? "page" : undefined}
                    aria-label={item.label}
                    className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all duration-200 group ${
                      active
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:text-foreground hover:bg-white/[0.03]"
                    }`}
                    title={collapsed ? item.label : undefined}
                  >
                    <Icon
                      className={`w-4 h-4 shrink-0 transition-colors ${
                        active ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                      }`}
                    />
                    {!collapsed && (
                      <span className="font-['Inter'] text-[12px] font-medium truncate">{item.label}</span>
                    )}
                    {active && !collapsed && (
                      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Crypto Prices */}
      {!collapsed && (
        <div className="px-3 py-3 border-t border-border">
          <div className="font-['JetBrains_Mono'] text-[10px] text-muted-foreground/50 tracking-widest mb-2 px-1">
            PRIX CRYPTO
          </div>
          <div className="space-y-1.5">
            {cryptoPrices.map((c) => {
              const snapshot = data?.market_snapshots?.find((s) => s.symbol === `${c.symbol}USDT`);
              const price = snapshot?.price;
              return (
                <div key={c.symbol} className="flex items-center justify-between px-1 py-1.5 rounded-md hover:bg-white/[0.02] transition-colors cursor-default">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold"
                      style={{ background: `${c.color}22`, color: c.color }}
                    >
                      {c.symbol[0]}
                    </div>
                    <span className="font-['Inter'] text-[12px] text-foreground">{c.symbol}</span>
                  </div>
                  <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">
                    {price ? `$${price >= 1000 ? (price / 1000).toFixed(1) + "k" : price.toFixed(0)}` : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Status */}
      <div className="px-3 py-2.5 border-t border-border">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              data?.supervisor?.kill_switch_active ? "bg-destructive animate-pulse" : "bg-emerald-400"
            }`}
          />
          {!collapsed && (
            <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground">
              {data?.supervisor?.kill_switch_active ? "ARRÊT D'URGENCE" : "SYSTÈME ACTIF"}
            </span>
          )}
        </div>
      </div>

      {/* Collapse Toggle (desktop only) */}
      <button
        onClick={onToggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="hidden lg:flex absolute top-16 -right-3 w-6 h-6 rounded-full bg-card border border-border items-center justify-center text-muted-foreground hover:text-primary hover:border-primary/30 transition-all z-50"
      >
        {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
      </button>
    </>
  );
}

function Sidebar({ data, activeSection, onNavigate, collapsed, onToggle, mobileOpen, onMobileClose }: SidebarProps) {
  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className="hidden lg:flex fixed left-0 top-0 bottom-0 z-40 flex-col border-r border-border overflow-hidden transition-all duration-300"
        style={{
          background: "linear-gradient(180deg, #060c18 0%, #0a1020 50%, #060c18 100%)",
          width: collapsed ? "68px" : "240px",
        }}
      >
        <SidebarContent data={data} activeSection={activeSection} onNavigate={onNavigate} collapsed={collapsed} onToggle={onToggle} />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]"
            onClick={onMobileClose}
            aria-hidden="true"
          />

          {/* Drawer */}
          <aside
            className="absolute left-0 top-0 bottom-0 w-[260px] flex flex-col border-r border-border animate-[slideInLeft_0.3s_ease-out]"
            style={{
              background: "linear-gradient(180deg, #060c18 0%, #0a1020 50%, #060c18 100%)",
            }}
          >
            {/* Close button */}
            <button
              onClick={onMobileClose}
              aria-label="Fermer le menu"
              className="absolute top-4 right-3 z-10 p-1.5 rounded-lg border border-border hover:border-primary/30 hover:bg-primary/5 transition-all"
            >
              <X className="w-4 h-4 text-muted-foreground" />
            </button>

            <SidebarContent data={data} activeSection={activeSection} onNavigate={(section) => { onNavigate(section); onMobileClose(); }} collapsed={false} onToggle={onToggle} />
          </aside>
        </div>
      )}
    </>
  );
}

export default memo(Sidebar);
