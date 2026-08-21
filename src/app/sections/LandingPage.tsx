import { useState, useEffect } from "react";
import {
  Activity,
  ArrowRight,
  Brain,
  Shield,
  TrendingUp,
  Zap,
  BarChart2,
  Lock,
  Eye,
} from "lucide-react";

function GlowOrb({
  x,
  y,
  size,
  color,
  opacity,
}: {
  x: string;
  y: string;
  size: string;
  color: string;
  opacity: number;
}) {
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

const benefits = [
  {
    icon: <Brain className="w-6 h-6" />,
    title: "IA Quant Multi-Agents",
    description:
      "5 agents IA collaborent : analyste, trader, gestionnaire du risque, coach et chercheur. Chaque décision est débattue et validée.",
    color: "#8b5cf6",
  },
  {
    icon: <Shield className="w-6 h-6" />,
    title: "Risques Maîtrisés",
    description:
      "VaR, CVaR, stress tests, drawdown monitoring. Le gestionnaire du risque a un droit de veto sur chaque trade.",
    color: "#ef4444",
  },
  {
    icon: <TrendingUp className="w-6 h-6" />,
    title: "Auto-Apprentissage",
    description:
      "Le système analyse ses erreurs, optimise ses paramètres et évolue sans intervention. Chaque backtest enrichit la mémoire.",
    color: "#22c55e",
  },
];

const features = [
  {
    icon: <Activity className="w-5 h-5" />,
    title: "15 modules spécialisés",
    description: "Collecte, validation, features, IA, stratégies, exécution, journal, mémoire, coach, labo, supervision.",
  },
  {
    icon: <BarChart2 className="w-5 h-5" />,
    title: "6 stratégies testées",
    description: "SMA, Donchian, Mean Reversion, Grid adaptatif, avec walk-forward analysis et Monte Carlo.",
  },
  {
    icon: <Zap className="w-5 h-5" />,
    title: "Paper Trading 24/7",
    description: "Exécution simulée sur Binance Testnet. Zéro risque réel, toutes les conditions réelles.",
  },
  {
    icon: <Lock className="w-5 h-5" />,
    title: "Arrêt d'urgence",
    description: "Superviseur intelligent qui coupe le système si les drawdowns ou les anomalies dépassent les seuils.",
  },
  {
    icon: <Eye className="w-5 h-5" />,
    title: "Traçabilité totale",
    description: "Chaque décision enregistrée avec contexte, score de confiance, résultat. Journal complet et auditable.",
  },
  {
    icon: <Brain className="w-5 h-5" />,
    title: "AI Analyst intégré",
    description: "Analyse de marché, évaluation des risques, review de stratégies — tout en un clic via OpenCode Zen + OpenRouter.",
  },
];

const steps = [
  {
    num: "01",
    title: "Collecte & Analyse",
    description: "Le système récupère les données en temps réel et calcule 15+ indicateurs techniques.",
  },
  {
    num: "02",
    title: "Décision IA",
    description: "Les 5 agents IA débattent et votent. Le gestionnaire du risque valide ou vetto.",
  },
  {
    num: "03",
    title: "Exécution & Apprentissage",
    description: "Le trade est exécuté, journalisé, et le système apprend du résultat.",
  },
];

export default function LandingPage({ onEnter }: { onEnter: () => void }) {
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const handler = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden" style={{ fontFamily: "Inter, sans-serif" }}>
      {/* ── NAV ── */}
      <header
        className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
        style={{
          background: scrollY > 40 ? "rgba(4,8,15,0.92)" : "transparent",
          backdropFilter: scrollY > 40 ? "blur(20px)" : "none",
          borderBottom: scrollY > 40 ? "1px solid rgba(0,212,255,0.08)" : "none",
        }}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
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
          <button
            onClick={onEnter}
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
      </header>

      {/* ── HERO ── */}
      <section className="relative min-h-screen flex flex-col justify-center overflow-hidden pt-16">
        <GridLines />
        <GlowOrb x="10%" y="30%" size="600px" color="#0057ff" opacity={0.12} />
        <GlowOrb x="80%" y="60%" size="500px" color="#00d4ff" opacity={0.08} />
        <GlowOrb x="50%" y="10%" size="400px" color="#8b5cf6" opacity={0.06} />

        <div className="absolute top-0 bottom-0 w-px pointer-events-none" style={{ left: "20%", background: "linear-gradient(to bottom, transparent, rgba(0,212,255,0.3), transparent)" }} />

        <div className="relative z-10 max-w-7xl mx-auto px-6 py-24 grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-8 border border-primary/30 rounded-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              <span className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest">PAPER TRADING ACTIF</span>
            </div>

            <h1 className="font-['Rajdhani'] font-700 text-5xl lg:text-7xl leading-none tracking-tight mb-6">
              <span className="text-foreground">Trading Crypto</span>
              <br />
              <span style={{ color: "#00d4ff" }}>Piloté par l'IA</span>
            </h1>

            <p className="font-['Inter'] text-base text-muted-foreground leading-relaxed mb-4 max-w-lg">
              AEGIS AI Quant est un système autonome qui observe le marché, prend des décisions et apprend de ses erreurs — sans intervention permanente.
            </p>

            <p className="font-['Inter'] text-sm text-muted-foreground/70 italic mb-10 max-w-md">
              "Robustesse avant tout. Zéro argent réel. Toute la rigueur."
            </p>

            <div className="flex flex-wrap gap-4 mb-12">
              <button
                onClick={onEnter}
                className="flex items-center gap-2 px-6 py-3 font-['Rajdhani'] font-600 tracking-wider text-sm transition-all duration-200 hover:scale-105"
                style={{
                  background: "linear-gradient(135deg, #00d4ff, #0057ff)",
                  color: "#04080f",
                  clipPath: "polygon(10px 0%, 100% 0%, calc(100% - 10px) 100%, 0% 100%)",
                }}
              >
                LANCER LE DASHBOARD
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4 sm:gap-6">
              {[
                { value: "15", label: "Modules" },
                { value: "6", label: "Stratégies" },
                { value: "24/7", label: "Surveillance" },
              ].map((s) => (
                <div key={s.label} className="border-l-2 border-primary/40 pl-4">
                  <div className="font-['Rajdhani'] font-700 text-2xl text-primary">{s.value}</div>
                  <div className="font-['Inter'] text-xs text-muted-foreground tracking-wider">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right — feature card */}
          <div className="relative">
            <div
              className="relative border border-primary/20 p-6"
              style={{
                background: "rgba(11,18,32,0.8)",
                backdropFilter: "blur(20px)",
                clipPath: "polygon(0 0, calc(100% - 20px) 0, 100% 20px, 100% 100%, 20px 100%, 0 calc(100% - 20px))",
              }}
            >
              <div className="font-['JetBrains_Mono'] text-xs text-muted-foreground tracking-widest mb-4">COMMENT ÇA MARCHE</div>
              <div className="space-y-4">
                {steps.map((step) => (
                  <div key={step.num} className="flex gap-4">
                    <div className="font-['Rajdhani'] font-700 text-lg text-primary shrink-0 w-8">{step.num}</div>
                    <div>
                      <div className="font-['Rajdhani'] font-700 text-sm text-foreground">{step.title}</div>
                      <div className="font-['Inter'] text-xs text-muted-foreground mt-0.5">{step.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="absolute -top-px -left-px w-6 h-6 border-t-2 border-l-2 border-primary" />
            <div className="absolute -bottom-px -right-px w-6 h-6 border-b-2 border-r-2 border-primary" />
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-muted-foreground/50">
          <span className="font-['JetBrains_Mono'] text-xs tracking-widest">SCROLL</span>
          <div className="w-4 h-6 border border-muted-foreground/30 rounded-full flex justify-center pt-1.5">
            <div className="w-1 h-1.5 bg-primary rounded-full animate-bounce" />
          </div>
        </div>
      </section>

      {/* ── BENEFITS ── */}
      <section className="relative py-24 overflow-hidden" style={{ background: "rgba(4,8,15,0.7)" }}>
        <GlowOrb x="50%" y="50%" size="800px" color="#0057ff" opacity={0.04} />
        <div className="relative z-10 max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">POURQUOI AEGIS</div>
            <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-5xl text-foreground">
              Conçu pour la <span style={{ color: "#00d4ff" }}>robustesse</span>
            </h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {benefits.map((b) => (
              <div
                key={b.title}
                className="relative p-6 border border-border transition-all duration-300 hover:border-primary/30"
                style={{ background: "rgba(11,18,32,0.7)" }}
              >
                <div className="w-12 h-12 flex items-center justify-center mb-4" style={{ background: `${b.color}15`, color: b.color, border: `1px solid ${b.color}25` }}>
                  {b.icon}
                </div>
                <h3 className="font-['Rajdhani'] font-700 text-lg text-foreground mb-2">{b.title}</h3>
                <p className="font-['Inter'] text-sm text-muted-foreground leading-relaxed">{b.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section className="relative py-24 overflow-hidden">
        <GlowOrb x="80%" y="40%" size="600px" color="#8b5cf6" opacity={0.05} />
        <div className="relative z-10 max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <div className="font-['JetBrains_Mono'] text-xs text-primary tracking-widest mb-4">FONCTIONNALITÉS</div>
            <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-5xl text-foreground">
              Tout ce qu'il faut, <span style={{ color: "#00d4ff" }}>rien de plus</span>
            </h2>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {features.map((f) => (
              <div
                key={f.title}
                className="p-5 border border-border transition-all duration-300 hover:border-primary/20 hover:bg-primary/5"
                style={{ background: "rgba(11,18,32,0.5)" }}
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="text-primary">{f.icon}</div>
                  <div className="font-['Rajdhani'] font-700 text-sm text-foreground">{f.title}</div>
                </div>
                <p className="font-['Inter'] text-xs text-muted-foreground leading-relaxed">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="relative py-24 overflow-hidden" style={{ background: "rgba(4,8,15,0.9)" }}>
        <GlowOrb x="50%" y="50%" size="600px" color="#0057ff" opacity={0.1} />
        <div className="relative z-10 max-w-3xl mx-auto px-6 text-center">
          <h2 className="font-['Rajdhani'] font-700 text-3xl sm:text-5xl text-foreground mb-6">
            Prêt à observer le système <span style={{ color: "#00d4ff" }}>en action</span> ?
          </h2>
          <p className="font-['Inter'] text-sm text-muted-foreground mb-10 max-w-lg mx-auto">
            Aucun compte requis. Aucun argent réel. Juste un dashboard live avec des données de marché en temps réel et des décisions IA.
          </p>
          <button
            onClick={onEnter}
            className="inline-flex items-center gap-2 px-8 py-4 font-['Rajdhani'] font-600 tracking-wider text-base transition-all duration-200 hover:scale-105"
            style={{
              background: "linear-gradient(135deg, #00d4ff, #0057ff)",
              color: "#04080f",
              clipPath: "polygon(12px 0%, 100% 0%, calc(100% - 12px) 100%, 0% 100%)",
            }}
          >
            ACCÉDER AU DASHBOARD
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="relative border-t border-border py-8">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="relative w-6 h-6">
              <div className="absolute inset-0 rounded border border-primary/60" style={{ transform: "rotate(45deg)" }} />
              <Activity className="absolute inset-0 m-auto w-3 h-3 text-primary" />
            </div>
            <span className="font-['Rajdhani'] font-700 text-sm tracking-[0.12em] text-foreground">
              AEGIS <span className="text-primary">AI QUANT</span>
            </span>
          </div>
          <div className="font-['JetBrains_Mono'] text-xs text-muted-foreground/50">
            © 2026 AEGIS AI QUANT V1 — CONFIDENTIEL
          </div>
        </div>
      </footer>
    </div>
  );
}
