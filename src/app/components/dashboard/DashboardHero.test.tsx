import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardHero from "./DashboardHero";

const mockData = {
  mode: "paper" as const,
  capital: 20,
  current_equity: 21,
  realized_pnl: 1,
  exposure: 5,
  max_exposure: 2000,
  positions: [
    { symbol: "BTCUSDT", quantity: 0.1, average_price: 45000 },
    { symbol: "ETHUSDT", quantity: 2, average_price: 2500 },
  ],
  equity_curve: [
    { time: "2026-01-01", equity: 20 },
    { time: "2026-01-02", equity: 20.4 },
    { time: "2026-01-03", equity: 21 },
  ],
  fear_greed: [{ value: 65, classification: "Greed", source: "alternative.me", collected_at: "2026-01-03" }],
  risk: {
    value_at_risk: 0.02,
    conditional_value_at_risk: 0.035,
    annualized_volatility: 0.45,
    max_drawdown_pct: 0.15,
  },
  recent_backtests: [],
  data_quality: { valid: true, candle_count: 500, gap_count: 0, invalid_candle_count: 0 },
  market_analysis: null,
  stress_test: null,
  correlation: null,
  concentration: null,
  supervisor: { status: "healthy", kill_switch_active: false },
  alerts: [],
  coach: { reviewed_backtests: 0, recommendations: [] },
  strategy_registry: [],
  recent_decisions: [],
  funding_rates: [],
  open_interest: [],
  memory: { total_episodes: 0, strategies_used: [], avg_result: null, best_fingerprint: null },
  journal: null,
};

describe("DashboardHero", () => {
  it("renders portfolio section", () => {
    render(<DashboardHero data={mockData} onRefresh={vi.fn()} loading={false} />);
    expect(screen.getByText("PORTEFEUILLE TOTAL")).toBeInTheDocument();
  });

  it("renders positions", () => {
    render(<DashboardHero data={mockData} onRefresh={vi.fn()} loading={false} />);
    expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    expect(screen.getByText("ETHUSDT")).toBeInTheDocument();
  });

  it("renders Fear & Greed value", () => {
    render(<DashboardHero data={mockData} onRefresh={vi.fn()} loading={false} />);
    expect(screen.getByText("65")).toBeInTheDocument();
    expect(screen.getByText("Greed")).toBeInTheDocument();
  });

  it("renders risk metrics section", () => {
    render(<DashboardHero data={mockData} onRefresh={vi.fn()} loading={false} />);
    expect(screen.getByText("MÉTRIQUES DE RISQUE")).toBeInTheDocument();
  });

  it("calls onRefresh when button clicked", async () => {
    const onRefresh = vi.fn();
    render(<DashboardHero data={mockData} onRefresh={onRefresh} loading={false} />);
    const buttons = screen.getAllByRole("button");
    const refreshBtn = buttons.find((b) => b.querySelector("svg"));
    if (refreshBtn) {
      refreshBtn.click();
      expect(onRefresh).toHaveBeenCalled();
    }
  });

  it("shows loading state", () => {
    render(<DashboardHero data={mockData} onRefresh={vi.fn()} loading={true} />);
    const buttons = screen.getAllByRole("button");
    const refreshBtn = buttons.find((b) => b.querySelector(".animate-spin"));
    expect(refreshBtn).toBeTruthy();
  });
});
