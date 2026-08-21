import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";

const mockData = {
  mode: "paper" as const,
  capital: 20,
  current_equity: 21,
  realized_pnl: 1,
  exposure: 5,
  max_exposure: 2000,
  positions: [],
  equity_curve: [],
  recent_backtests: [],
  data_quality: { valid: true, candle_count: 500, gap_count: 0, invalid_candle_count: 0 },
  market_analysis: null,
  risk: null,
  stress_test: null,
  correlation: null,
  concentration: null,
  supervisor: { status: "healthy", kill_switch_active: false },
  alerts: [],
  coach: { reviewed_backtests: 0, recommendations: [] },
  strategy_registry: [],
  recent_decisions: [],
  fear_greed: [],
  funding_rates: [],
  open_interest: [],
  memory: { total_episodes: 0, strategies_used: [], avg_result: null, best_fingerprint: null },
  journal: null,
};

const renderSidebar = (props = {}) => {
  const defaultProps = {
    data: mockData,
    activeSection: "overview",
    onNavigate: vi.fn(),
    collapsed: false,
    onToggle: vi.fn(),
    mobileOpen: false,
    onMobileClose: vi.fn(),
  };
  return render(
    <MemoryRouter>
      <Sidebar {...defaultProps} {...props} />
    </MemoryRouter>
  );
};

describe("Sidebar", () => {
  it("renders AEGIS logo", () => {
    renderSidebar();
    expect(screen.getByText("AEGIS")).toBeInTheDocument();
    expect(screen.getByText("AI QUANT")).toBeInTheDocument();
  });

  it("renders navigation items", () => {
    renderSidebar();
    expect(screen.getByText("Vue d'ensemble")).toBeInTheDocument();
    expect(screen.getByText("Portefeuille")).toBeInTheDocument();
    expect(screen.getByText("Risques")).toBeInTheDocument();
    expect(screen.getByText("Analyste IA")).toBeInTheDocument();
  });

  it("highlights active section", () => {
    renderSidebar({ activeSection: "risk" });
    const riskBtn = screen.getByText("Risques").closest("button");
    expect(riskBtn).toHaveAttribute("aria-current", "page");
  });

  it("calls onNavigate when item clicked", () => {
    const onNavigate = vi.fn();
    renderSidebar({ onNavigate });
    fireEvent.click(screen.getByText("Portefeuille"));
    expect(onNavigate).toHaveBeenCalledWith("portfolio");
  });

  it("shows crypto prices section", () => {
    renderSidebar();
    expect(screen.getByText("PRIX CRYPTO")).toBeInTheDocument();
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("ETH")).toBeInTheDocument();
    expect(screen.getByText("SOL")).toBeInTheDocument();
  });

  it("shows system status", () => {
    renderSidebar();
    expect(screen.getByText("SYSTÈME ACTIF")).toBeInTheDocument();
  });

  it("shows emergency status when kill switch active", () => {
    const emergencyData = {
      ...mockData,
      supervisor: { status: "stopped", kill_switch_active: true },
    };
    renderSidebar({ data: emergencyData });
    expect(screen.getByText("ARRÊT D'URGENCE")).toBeInTheDocument();
  });

  it("calls onToggle when collapse button clicked", () => {
    const onToggle = vi.fn();
    renderSidebar({ onToggle });
    const toggleBtn = screen.getByLabelText("Collapse sidebar");
    fireEvent.click(toggleBtn);
    expect(onToggle).toHaveBeenCalled();
  });

  it("renders collapsed state", () => {
    renderSidebar({ collapsed: true });
    expect(screen.queryByText("Vue d'ensemble")).not.toBeInTheDocument();
  });
});
