import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import LearningSection from "./LearningSection";

vi.mock("../../lib/api", () => ({
  getLearningSummary: vi.fn().mockResolvedValue({
    strategies_tracked: 4,
    total_trades: 25,
    overall_win_rate: 0.64,
    total_realized_pnl: 230.50,
    strategies: [
      { strategy: "SMA Crossover", score: 85, trades: 12, win_rate: 0.75, avg_pnl_pct: 3.1, regime_scores: {} },
      { strategy: "Grid", score: 60, trades: 8, win_rate: 0.625, avg_pnl_pct: 1.5, regime_scores: {} },
    ],
  }),
  getStrategyStats: vi.fn().mockResolvedValue([
    { strategy_id: "SMA_Crossover", score: 85, total_trades: 12, win_rate: 0.75, profit_factor: 2.1, avg_pnl_pct: 3.1, total_pnl: 37.20 },
    { strategy_id: "Grid", score: 60, total_trades: 8, win_rate: 0.625, profit_factor: 1.4, avg_pnl_pct: 1.5, total_pnl: 12.00 },
  ]),
  getTradeOutcomes: vi.fn().mockResolvedValue([]),
}));

const renderWithToast = (ui: React.ReactElement) =>
  render(<ToastProvider>{ui}</ToastProvider>);

describe("LearningSection", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows loading state initially", async () => {
    renderWithToast(<LearningSection />);
    expect(screen.getByText("Chargement...")).toBeInTheDocument();
    await act(async () => {});
  });

  it("renders learning header after load", async () => {
    renderWithToast(<LearningSection />);
    await waitFor(() => {
      expect(screen.getByText("Apprentissage")).toBeInTheDocument();
    });
  });

  it("renders total trades", async () => {
    renderWithToast(<LearningSection />);
    await waitFor(() => {
      expect(screen.getByText("Total trades")).toBeInTheDocument();
      expect(screen.getByText("25")).toBeInTheDocument();
    });
  });

  it("renders win rate", async () => {
    renderWithToast(<LearningSection />);
    await waitFor(() => {
      expect(screen.getByText("Win rate global")).toBeInTheDocument();
      expect(screen.getByText("64.0%")).toBeInTheDocument();
    });
  });

  it("renders strategies tracked", async () => {
    renderWithToast(<LearningSection />);
    await waitFor(() => {
      expect(screen.getByText("Strategies suivies")).toBeInTheDocument();
      expect(screen.getByText("4")).toBeInTheDocument();
    });
  });

  it("renders strategy table", async () => {
    renderWithToast(<LearningSection />);
    await waitFor(() => {
      expect(screen.getByText("SMA_Crossover")).toBeInTheDocument();
      expect(screen.getByText("Grid")).toBeInTheDocument();
    });
  });
});
