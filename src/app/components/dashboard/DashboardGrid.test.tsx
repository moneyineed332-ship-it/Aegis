import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AlertWebSocketProvider } from "../AlertWebSocketProvider";
import DashboardGrid from "./DashboardGrid";

const renderGrid = (data: Record<string, unknown> | null = null) =>
  render(
    <AlertWebSocketProvider>
      <DashboardGrid data={data as never} activeSection="overview" onNavigate={vi.fn()} />
    </AlertWebSocketProvider>
  );

describe("DashboardGrid", () => {
  it("renders grid container", () => {
    const { container } = renderGrid();
    expect(container.querySelector(".grid")).toBeInTheDocument();
  });

  it("renders market regime card", () => {
    renderGrid();
    expect(screen.getByText("RÉGIME DE MARCHÉ")).toBeInTheDocument();
  });

  it("renders risk assessment card", () => {
    renderGrid();
    expect(screen.getByText("ÉVALUATION DES RISQUES")).toBeInTheDocument();
  });

  it("renders strategies available card", () => {
    renderGrid();
    expect(screen.getByText("STRATÉGIES DISPONIBLES")).toBeInTheDocument();
  });

  it("renders backtests card", () => {
    renderGrid();
    expect(screen.getByText("DERNIERS BACKTESTS")).toBeInTheDocument();
  });

  it("renders alerts card", () => {
    renderGrid();
    expect(screen.getByText("SYSTÈME D'ALERTES")).toBeInTheDocument();
  });

  it("renders journal card", () => {
    renderGrid();
    expect(screen.getByText("JOURNAL DE DÉCISIONS")).toBeInTheDocument();
  });

  it("renders memory card", () => {
    renderGrid();
    expect(screen.getByText("MÉMOIRE ÉPISODIQUE")).toBeInTheDocument();
  });

  it("renders data quality card", () => {
    renderGrid();
    expect(screen.getByText("QUALITÉ DES DONNÉES")).toBeInTheDocument();
  });

  it("calls onNavigate when regime card clicked", () => {
    const onNavigate = vi.fn();
    render(
      <AlertWebSocketProvider>
        <DashboardGrid data={null} activeSection="overview" onNavigate={onNavigate} />
      </AlertWebSocketProvider>
    );
    screen.getByText("RÉGIME DE MARCHÉ").click();
    expect(onNavigate).toHaveBeenCalledWith("regime");
  });

  it("shows empty states when data is null", () => {
    renderGrid();
    const emptyStates = screen.getAllByText(/Aucune donnée|Aucun backtest|Aucune décision/);
    expect(emptyStates.length).toBeGreaterThan(0);
  });

  it("shows ws status", () => {
    renderGrid();
    expect(screen.getByText(/WebSocket/)).toBeInTheDocument();
  });
});
