import { type ButtonHTMLAttributes, type ReactNode } from "react";

// --- Card ---
interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
}

export function Card({ children, className = "", onClick, hoverable = false }: CardProps) {
  return (
    <div
      className={`rounded-2xl border border-border p-4 transition-all duration-300 ${
        hoverable ? "hover:border-primary/20 cursor-pointer group" : ""
      } ${className}`}
      style={{ background: "var(--card)" }}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}
    >
      {children}
    </div>
  );
}

// --- CardHeader ---
interface CardHeaderProps {
  title: string;
  icon?: ReactNode;
  color?: string;
  action?: ReactNode;
}

export function CardHeader({ title, icon, color = "var(--primary)", action }: CardHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        {icon && (
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: `color-mix(in srgb, ${color} 10%, transparent)` }}
          >
            <div style={{ color }}>{icon}</div>
          </div>
        )}
        <span className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground tracking-wider">{title}</span>
      </div>
      {action}
    </div>
  );
}

// --- Button ---
type ButtonVariant = "primary" | "secondary" | "danger" | "success" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  loading?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground hover:bg-primary/90 border-primary",
  secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80 border-border",
  danger: "bg-destructive/10 text-destructive hover:bg-destructive/20 border-destructive/30",
  success: "bg-success/10 text-success hover:bg-success/20 border-success/30",
  ghost: "bg-transparent text-muted-foreground hover:text-foreground hover:bg-white/[0.03] border-transparent",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2 py-1 text-[12px] gap-1",
  md: "px-3 py-1.5 text-[12px] gap-1.5",
  lg: "px-4 py-2 text-[12px] gap-2",
};

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  loading,
  children,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center font-['JetBrains_Mono'] font-medium rounded-lg border transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}

// --- Badge ---
type BadgeVariant = "default" | "success" | "danger" | "warning" | "info";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const badgeStyles: Record<BadgeVariant, string> = {
  default: "bg-secondary text-secondary-foreground border-border",
  success: "bg-success/10 text-success border-success/20",
  danger: "bg-destructive/10 text-destructive border-destructive/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  info: "bg-primary/10 text-primary border-primary/20",
};

export function Badge({ children, variant = "default", className = "" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md font-['JetBrains_Mono'] text-[12px] border ${badgeStyles[variant]} ${className}`}>
      {children}
    </span>
  );
}

// --- Stat ---
interface StatProps {
  label: string;
  value: string | number;
  change?: number;
  className?: string;
}

export function Stat({ label, value, change, className = "" }: StatProps) {
  return (
    <div className={`rounded-xl p-3 border border-border ${className}`} style={{ background: "rgba(0,212,255,0.03)" }}>
      <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground/60 tracking-wider mb-1">{label}</div>
      <div className="font-['Rajdhani'] font-bold text-lg text-foreground">{value}</div>
      {change !== undefined && (
        <div className={`font-['JetBrains_Mono'] text-[12px] ${change >= 0 ? "text-success" : "text-destructive"}`}>
          {change >= 0 ? "+" : ""}{change.toFixed(2)}%
        </div>
      )}
    </div>
  );
}

// --- EmptyState ---
interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
}

export function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      {icon && <div className="text-muted-foreground/30 mb-3">{icon}</div>}
      <div className="font-['Inter'] text-[12px] text-muted-foreground">{title}</div>
      {description && (
        <div className="font-['JetBrains_Mono'] text-[12px] text-muted-foreground/50 mt-1">{description}</div>
      )}
    </div>
  );
}

// --- GlowOrb ---
interface GlowOrbProps {
  x: string;
  y: string;
  size: string;
  color: string;
  opacity: number;
}

export function GlowOrb({ x, y, size, color, opacity }: GlowOrbProps) {
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

// --- GridLines ---
export function GridLines() {
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

// --- Skeleton ---
export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-lg bg-primary/5 ${className}`} />
  );
}

// --- SkeletonCard ---
export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="rounded-2xl border border-border p-4 space-y-3" style={{ background: "var(--card)" }}>
      <Skeleton className="h-4 w-1/3" />
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-full" />
        ))}
      </div>
    </div>
  );
}
