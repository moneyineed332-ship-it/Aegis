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
    // The operator is logged in: the socket is authenticated with a single-use
    // ticket, so receiving alerts depends on that path succeeding.
    vi.stubGlobal("localStorage", { getItem: vi.fn(() => "test-token"), setItem: vi.fn() });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => ({ ticket: "wst1_test" }) })),
    );
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

  it("connects with a single-use ticket, never the admin token", async () => {
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    const url = MockWebSocket.instances[0].url;
    // The reverse proxy records the URL, so the admin token must not be in it.
    expect(url).toContain("ticket=");
    expect(url).not.toContain("test-token");
    expect(url).not.toContain("token=");
  });

  it("does not subscribe to alerts when the ticket cannot be minted", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, json: async () => ({}) })));
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(screen.getByTestId("status").textContent).toBe("disconnected");
    expect(screen.getByTestId("alert").textContent).toBe("none");
  });

  it("does not put the admin token in the URL when logged out", async () => {
    vi.stubGlobal("localStorage", { getItem: vi.fn(() => null), setItem: vi.fn() });
    render(
      <AlertWebSocketProvider>
        <TestConsumer />
      </AlertWebSocketProvider>
    );
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(MockWebSocket.instances[0].url).not.toContain("token=");
  });
});
