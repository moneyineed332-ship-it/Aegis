import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import React from "react";
import { ToastProvider, useToast } from "./Toast";

function TestComponent() {
  const toast = useToast();
  return (
    <div>
      <button onClick={() => toast.success("It worked!")}>Success</button>
      <button onClick={() => toast.error("Failed!")}>Error</button>
      <button onClick={() => toast.info("FYI")}>Info</button>
    </div>
  );
}

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("throws when useToast used outside provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    let captured: Error | null = null;
    // An error boundary consumes the error so React does not also report it
    // as an unhandled rejection, which would fail the whole run.
    class Catcher extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
      state = { failed: false };
      static getDerivedStateFromError() { return { failed: true }; }
      componentDidCatch(error: Error) { captured = error; }
      render() { return this.state.failed ? null : this.props.children; }
    }
    function Bad() {
      useToast();
      return null;
    }
    render(<Catcher><Bad /></Catcher>);
    expect(captured).toBeInstanceOf(Error);
    expect((captured as unknown as Error).message).toBe("useToast must be used within ToastProvider");
    spy.mockRestore();
  });

  it("shows success toast", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );
    act(() => { screen.getByText("Success").click(); });
    expect(screen.getByText("It worked!")).toBeInTheDocument();
  });

  it("shows error toast", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );
    act(() => { screen.getByText("Error").click(); });
    expect(screen.getByText("Failed!")).toBeInTheDocument();
  });

  it("shows info toast", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );
    act(() => { screen.getByText("Info").click(); });
    expect(screen.getByText("FYI")).toBeInTheDocument();
  });

  it("auto-removes toast after 4 seconds", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );
    act(() => { screen.getByText("Success").click(); });
    expect(screen.getByText("It worked!")).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(4000); });
    expect(screen.queryByText("It worked!")).not.toBeInTheDocument();
  });

  it("manually removes toast via close button", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );
    act(() => { screen.getByText("Success").click(); });
    act(() => { screen.getByLabelText("Fermer la notification").click(); });
    expect(screen.queryByText("It worked!")).not.toBeInTheDocument();
  });

  it("limits toasts to 5", async () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );
    for (let i = 0; i < 7; i++) {
      act(() => { screen.getByText("Success").click(); });
    }
    const toasts = screen.getAllByText("It worked!");
    expect(toasts.length).toBeLessThanOrEqual(5);
  });
});
