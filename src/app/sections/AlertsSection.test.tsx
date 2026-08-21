import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import AlertsSection from "./AlertsSection";

vi.mock("../../lib/api", () => ({
  getAlertHistory: vi.fn().mockResolvedValue([
    { id: 1, alert_type: "max_drawdown", severity: "warning", message: "Drawdown -8%", timestamp: "2026-01-15T10:00:00Z" },
  ]),
  getAlertThresholds: vi.fn().mockResolvedValue({
    max_drawdown_pct: 15,
    var_95_pct: 5,
    rsi_overbought: 75,
  }),
  checkAlerts: vi.fn().mockResolvedValue({ alerts: [] }),
}));

vi.mock("../components/AlertWebSocketProvider", () => ({
  useAlertWebSocket: () => ({
    connected: false,
    subscribe: vi.fn(() => vi.fn()),
  }),
}));

const renderWithToast = (ui: React.ReactElement) =>
  render(<ToastProvider>{ui}</ToastProvider>);

describe("AlertsSection", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders monitoring header", async () => {
    renderWithToast(<AlertsSection />);
    await waitFor(() => {
      expect(screen.getByText(/Monitoring/)).toBeInTheDocument();
    });
  });

  it("renders alert history", async () => {
    renderWithToast(<AlertsSection />);
    await waitFor(() => {
      expect(screen.getByText(/Drawdown -8%/)).toBeInTheDocument();
    });
  });

  it("renders WS status", async () => {
    renderWithToast(<AlertsSection />);
    await waitFor(() => {
      expect(screen.getByText(/WS OFF/)).toBeInTheDocument();
    });
  });
});
