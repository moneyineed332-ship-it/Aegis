import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import EngineSection from "./EngineSection";

vi.mock("../../lib/api", () => ({
  getEngineStatus: vi.fn().mockResolvedValue({
    status: "running",
    cycle_count: 42,
    mode: "paper",
    started_at: "2026-07-15T10:00:00",
    stats: { signals_generated: 15, trades_executed: 3, errors: 1 },
    scheduler: { tasks: { fetch_prices: { last_run: "2026-07-15T10:05:00" } } },
  }),
  getEngineLogs: vi.fn().mockResolvedValue([]),
  getEngineSignals: vi.fn().mockResolvedValue([]),
  getFocusStatus: vi.fn().mockResolvedValue({
    focused_mode: true,
    strategy: "donchian_breakout_long_flat",
    strategy_name: "Donchian Breakout",
    symbols: ["PAXGUSDT", "BTCUSDT", "ETHUSDT"],
    max_positions: 3,
    donchian_parameters: { breakout_period: 20, exit_period: 10 },
    mode: "paper",
    tradable_strategies: ["donchian_breakout_long_flat"],
  }),
  getOMSStatus: vi.fn().mockResolvedValue({ positions_count: 2, total_exposure: 500, max_exposure: 2000, recent_orders: 5 }),
  getOMSMode: vi.fn().mockResolvedValue({ mode: "paper", exchange: "paper" }),
  startEngine: vi.fn().mockResolvedValue({}),
  stopEngine: vi.fn().mockResolvedValue({}),
  setOMSMode: vi.fn().mockResolvedValue({}),
}));

const renderWithToast = (ui: React.ReactElement) =>
  render(<ToastProvider>{ui}</ToastProvider>);

describe("EngineSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders engine status after load", async () => {
    renderWithToast(<EngineSection />);
    await waitFor(() => {
      expect(screen.getByText("EN MARCHE")).toBeInTheDocument();
    });
  });

  it("renders mode badge", async () => {
    renderWithToast(<EngineSection />);
    await waitFor(() => {
      expect(screen.getByText("MODE: PAPER")).toBeInTheDocument();
    });
  });

  it("renders stats cards", async () => {
    renderWithToast(<EngineSection />);
    await waitFor(() => {
      expect(screen.getByText("Cycles")).toBeInTheDocument();
      expect(screen.getByText("42")).toBeInTheDocument();
    });
  });

  it("renders start/stop button based on status", async () => {
    renderWithToast(<EngineSection />);
    await waitFor(() => {
      expect(screen.getByText("ARRETER")).toBeInTheDocument();
    });
  });

  it("renders OMS section", async () => {
    renderWithToast(<EngineSection />);
    await waitFor(() => {
      expect(screen.getByText("Mode d'Execution")).toBeInTheDocument();
    });
  });

  it("renders started_at timestamp", async () => {
    renderWithToast(<EngineSection />);
    await waitFor(() => {
      expect(screen.getByText(/Demarre le/)).toBeInTheDocument();
    });
  });

  it("renders focused mode panel", async () => {
    renderWithToast(<EngineSection />);
    await waitFor(() => {
      expect(screen.getByText("Mode Focus — Strategie Unique")).toBeInTheDocument();
      expect(screen.getByText("Donchian Breakout")).toBeInTheDocument();
      expect(screen.getByText("PAXGUSDT · BTCUSDT · ETHUSDT")).toBeInTheDocument();
      expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
    });
  });
});
