import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import JournalSection from "./JournalSection";

vi.mock("../../lib/api", () => ({
  getJournalAnalysis: vi.fn().mockResolvedValue({
    total_decisions: 12,
    accuracy: 0.67,
    avg_pnl: 2.5,
    total_pnl: 30,
    by_action: {
      buy: { count: 8, accuracy: 0.75, avg_pnl: 3.1 },
      sell: { count: 4, accuracy: 0.5, avg_pnl: 1.3 },
    },
    outcomes: [
      { decision_id: 1, action: "buy", symbol: "BTCUSDT", strategy: "smc_ict", regime: "trending_bull", confidence: 0.8, reason: "BOS", order_id: "1", decision_time: "2026-01-15T10:00:00Z", entry_price: 64000, current_price: 64500, pnl_since_decision: 0.0078, outcome: "correct_entry" },
    ],
    feedback: {
      message: "Based on 12 decisions",
      grade: "B — Decent, room for improvement",
      strengths: ["Strong strategy selection when entering"],
      weaknesses: ["Entering positions at wrong times"],
    },
  }),
  exportDashboardCSV: vi.fn().mockResolvedValue(new Blob(["csv"])),
  exportDashboardJSON: vi.fn().mockResolvedValue(new Blob(["json"])),
}));

const renderWithToast = (ui: React.ReactElement) =>
  render(<ToastProvider>{ui}</ToastProvider>);

describe("JournalSection", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders journal header after load", async () => {
    renderWithToast(<JournalSection />);
    await waitFor(() => {
      expect(screen.getByText(/Journal de Décisions/)).toBeInTheDocument();
    });
  });

  it("renders total decisions count", async () => {
    renderWithToast(<JournalSection />);
    await waitFor(() => {
      expect(screen.getByText(/12 décisions/)).toBeInTheDocument();
    });
  });

  it("renders accuracy percentage", async () => {
    renderWithToast(<JournalSection />);
    await waitFor(() => {
      expect(screen.getByText(/67%/)).toBeInTheDocument();
    });
  });

  it("renders export buttons", async () => {
    renderWithToast(<JournalSection />);
    await waitFor(() => {
      expect(screen.getByText(/CSV/)).toBeInTheDocument();
      expect(screen.getByText(/JSON/)).toBeInTheDocument();
    });
  });

  it("renders feedback grade", async () => {
    renderWithToast(<JournalSection />);
    await waitFor(() => {
      expect(screen.getByText(/Decent/)).toBeInTheDocument();
    });
  });

  it("renders by-action breakdown", async () => {
    renderWithToast(<JournalSection />);
    await waitFor(() => {
      expect(screen.getAllByText("ACHAT").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("VENTE").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders decision history table", async () => {
    renderWithToast(<JournalSection />);
    await waitFor(() => {
      expect(screen.getByText(/HISTORIQUE DES DÉCISIONS/)).toBeInTheDocument();
      expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
    });
  });
});
