import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import PositionMonitorSection from "./PositionMonitorSection";

vi.mock("../../lib/api", () => ({
  getPositionMonitor: vi.fn().mockResolvedValue({
    portfolio: {
      equity: 10500,
      total_pnl: 500,
      total_pnl_pct: 5.0,
      total_unrealized_pnl: 300,
      total_unrealized_pnl_pct: 3.0,
      exposure_pct: 42.9,
      position_count: 2,
      positions: [
        { symbol: "BTCUSDT", side: "long", quantity: 0.1, entry_price: 45000, current_price: 48000, notional: 4800, unrealized_pnl: 300, unrealized_pnl_pct: 6.67, exposure_pct: 42.9 },
        { symbol: "ETHUSDT", side: "long", quantity: 2, entry_price: 2500, current_price: 2600, notional: 5200, unrealized_pnl: 200, unrealized_pnl_pct: 4.0, exposure_pct: 50.0 },
      ],
    },
    alerts: [
      { symbol: "BTCUSDT", severity: "info", message: "Position healthy", unrealized_pnl_pct: 6.0 },
    ],
  }),
}));

const renderWithToast = (ui: React.ReactElement) =>
  render(<ToastProvider>{ui}</ToastProvider>);

describe("PositionMonitorSection", () => {
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading state initially", async () => {
    renderWithToast(<PositionMonitorSection />);
    expect(screen.getByText("Chargement...")).toBeInTheDocument();
    await act(async () => {});
  });

  it("renders section title after load", async () => {
    renderWithToast(<PositionMonitorSection />);
    await waitFor(() => {
      expect(screen.getByText("Monitor de Positions")).toBeInTheDocument();
    });
  });

  it("renders equity", async () => {
    renderWithToast(<PositionMonitorSection />);
    await waitFor(() => {
      expect(screen.getByText("Equity")).toBeInTheDocument();
    });
  });

  it("renders position count", async () => {
    renderWithToast(<PositionMonitorSection />);
    await waitFor(() => {
      expect(screen.getByText("Positions")).toBeInTheDocument();
    });
  });

  it("renders position symbols", async () => {
    renderWithToast(<PositionMonitorSection />);
    await waitFor(() => {
      expect(screen.getByText("BTCUSDT")).toBeInTheDocument();
      expect(screen.getByText("ETHUSDT")).toBeInTheDocument();
    });
  });
});
