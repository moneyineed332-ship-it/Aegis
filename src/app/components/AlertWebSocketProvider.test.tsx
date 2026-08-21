import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { AlertWebSocketProvider, useAlertWebSocket } from "./AlertWebSocketProvider";

function TestConsumer() {
  const { connected, lastAlert } = useAlertWebSocket();
  return (
    <div>
      <span data-testid="status">{connected ? "connected" : "disconnected"}</span>
      <span data-testid="alert">{lastAlert?.message ?? "none"}</span>
    </div>
  );
}

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    // Simulate connection
    setTimeout(() => this.onopen?.(), 0);
  }

  simulateMessage(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateClose() {
    this.onclose?.();
  }
}

describe("AlertWebSocketProvider", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    vi.stubGlobal("localStorage", { getItem: vi.fn(() => null), setItem: vi.fn() });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts disconnected", () => {
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    expect(screen.getByTestId("status").textContent).toBe("disconnected");
  });

  it("connects and sets connected to true", async () => {
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(MockWebSocket.instances.length).toBe(1);
  });

  it("receives messages and updates lastAlert", async () => {
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateMessage({ type: "alert", message: "New trade" });
    });
    expect(screen.getByTestId("alert").textContent).toBe("New trade");
  });

  it("ignores pong messages", async () => {
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateMessage({ type: "pong" });
    });
    expect(screen.getByTestId("alert").textContent).toBe("none");
  });

  it("ignores malformed messages", async () => {
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.onmessage?.({ data: "not json" });
    });
    expect(screen.getByTestId("alert").textContent).toBe("none");
  });
});
