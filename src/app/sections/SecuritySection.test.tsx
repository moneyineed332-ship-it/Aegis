import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { ToastProvider } from "../components/Toast";
import SecuritySection from "./SecuritySection";

vi.mock("../../lib/api", () => ({
  getSecuritySummary: vi.fn().mockResolvedValue({
    total_events: 150,
    auth_failures: 3,
    admin_actions: 12,
    risk_breaches: 1,
    recent_events: [
      { id: 1, event_type: "admin_login", severity: "info", message: "Admin login", details_json: "{}", created_at: "2026-07-15T10:00:00" },
      { id: 2, event_type: "risk_breach", severity: "warning", message: "Max drawdown hit", details_json: "{}", created_at: "2026-07-15T09:30:00" },
    ],
  }),
}));

const renderWithToast = (ui: React.ReactElement) =>
  render(<ToastProvider>{ui}</ToastProvider>);

describe("SecuritySection", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows loading state initially", async () => {
    renderWithToast(<SecuritySection />);
    expect(screen.getByText("Chargement...")).toBeInTheDocument();
    await act(async () => {});
  });

  it("renders security stats after load", async () => {
    renderWithToast(<SecuritySection />);
    await waitFor(() => {
      expect(screen.getByText("Evenements totaux")).toBeInTheDocument();
      expect(screen.getByText("150")).toBeInTheDocument();
    });
  });

  it("renders auth failures stat", async () => {
    renderWithToast(<SecuritySection />);
    await waitFor(() => {
      expect(screen.getByText("Echecs auth")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
    });
  });

  it("renders admin actions stat", async () => {
    renderWithToast(<SecuritySection />);
    await waitFor(() => {
      expect(screen.getByText("Actions admin")).toBeInTheDocument();
      expect(screen.getByText("12")).toBeInTheDocument();
    });
  });

  it("renders risk breaches stat", async () => {
    renderWithToast(<SecuritySection />);
    await waitFor(() => {
      expect(screen.getByText("Breaches risque")).toBeInTheDocument();
      expect(screen.getByText("1")).toBeInTheDocument();
    });
  });

  it("renders recent events", async () => {
    renderWithToast(<SecuritySection />);
    await waitFor(() => {
      expect(screen.getByText("admin_login")).toBeInTheDocument();
      expect(screen.getByText("risk_breach")).toBeInTheDocument();
    });
  });
});
