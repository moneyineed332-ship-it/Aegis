import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import RiskSection from "./RiskSection";

vi.mock("../../lib/api", () => ({
  getDashboard: vi.fn().mockResolvedValue({
    risk: {
      value_at_risk: 59.82,
      conditional_value_at_risk: 102.72,
      max_drawdown_pct: -5.85,
      volatility: 0.0048,
      annualized_volatility: 0.4488,
      observations: 499,
      confidence: 0.95,
      interval: "1h",
    },
    stress_test: {
      capital: 20,
      current_price: 65000,
      position_value: 5,
      scenarios: [
        { name: "Crash -20%", portfolio_impact: 4 },
        { name: "Flash Crash -10%", portfolio_impact: 2 },
      ],
      worst_day_return: -4.82,
      worst_week_return: -5.61,
      worst_month_return: -4,
      avg_daily_volatility: 0.3,
    },
    correlation: null,
    concentration: {
      herfindahl: 0.52,
      max_concentration: 60.05,
      position_count: 2,
      positions: [],
      total_exposure: 625,
    },
  }),
}));

const renderWithToast = (ui: React.ReactElement) =>
  render(<ToastProvider>{ui}</ToastProvider>);

describe("RiskSection", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows loading state initially", async () => {
    const { container } = renderWithToast(<RiskSection />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    await act(async () => {});
  });

  it("renders risk amounts in currency, not as inflated percentages", async () => {
    renderWithToast(<RiskSection />);
    await waitFor(() => {
      // value_at_risk (59.82) and CVaR (102.72) are currency amounts.
      expect(screen.getByText("$59,82")).toBeInTheDocument();
      expect(screen.getByText("$102,72")).toBeInTheDocument();
    });
    // The old bug multiplied the amount by 100 and appended "%".
    expect(screen.queryByText("5 982,00%")).not.toBeInTheDocument();
  });

  it("does not re-multiply max_drawdown_pct which is already a percentage", async () => {
    renderWithToast(<RiskSection />);
    await waitFor(() => {
      expect(screen.getByText("-5.85%")).toBeInTheDocument();
    });
    expect(screen.queryByText("-585.00%")).not.toBeInTheDocument();
  });

  it("renders stress test scenarios", async () => {
    renderWithToast(<RiskSection />);
    await waitFor(() => {
      expect(screen.getByText("Crash -20%")).toBeInTheDocument();
    });
  });

  it("renders correlation section", async () => {
    renderWithToast(<RiskSection />);
    await waitFor(() => {
      expect(screen.getByText(/CORRÉLATION/)).toBeInTheDocument();
    });
  });

  it("renders concentration section", async () => {
    renderWithToast(<RiskSection />);
    await waitFor(() => {
      expect(screen.getByText(/Concentration/i)).toBeInTheDocument();
    });
  });
});
