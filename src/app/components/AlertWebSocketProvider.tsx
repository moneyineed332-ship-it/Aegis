import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import { fetchWsTicket, getAdminToken } from "../../lib/api";

interface AlertMessage {
  type: string;
  severity?: string;
  message?: string;
  timestamp?: string;
  [key: string]: unknown;
}

interface WebSocketContextValue {
  connected: boolean;
  lastAlert: AlertMessage | null;
  subscribe: (callback: (alert: AlertMessage) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue>({
  connected: false,
  lastAlert: null,
  subscribe: () => () => {},
});

export function useAlertWebSocket() {
  return useContext(WebSocketContext);
}

export function AlertWebSocketProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [lastAlert, setLastAlert] = useState<AlertMessage | null>(null);
  const subscribersRef = useRef<Set<(alert: AlertMessage) => void>>(new Set());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const retryCountRef = useRef(0);
  const mountedRef = useRef(true);

  const subscribe = useCallback((callback: (alert: AlertMessage) => void) => {
    subscribersRef.current.add(callback);
    return () => { subscribersRef.current.delete(callback); };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const maxRetries = 10;

    const connect = async () => {
      if (!mountedRef.current || retryCountRef.current >= maxRetries) return;
      try {
        // The configured URL is already validated in api.ts, which throws in
        // dev when it points at a remote host. The fallback is kept for the
        // case where the variable is absent entirely, which only affects the
        // socket and not the REST calls.
        const baseUrl = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/^http/, "ws");

        // A one-shot ticket, not the admin token. The WebSocket URL is the one
        // place a credential cannot travel in a header, and the URL is what the
        // reverse proxy records; a ticket that expires in seconds and is spent
        // on first use keeps the long-lived token out of that log.
        if (!getAdminToken()) {
          const unauthenticated = new WebSocket(`${baseUrl}/ws/alerts`);
          wsRef.current = unauthenticated;
          unauthenticated.onclose = () => {
            if (mountedRef.current) setConnected(false);
          };
          return;
        }

        const ticket = await fetchWsTicket();
        if (!ticket) {
          if (mountedRef.current) setConnected(false);
          return;
        }
        if (!mountedRef.current) return;
        const ws = new WebSocket(`${baseUrl}/ws/alerts?ticket=${encodeURIComponent(ticket)}`);
        wsRef.current = ws;

        ws.onopen = () => {
          retryCountRef.current = 0;
          if (mountedRef.current) setConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as AlertMessage;
            if (data.type === "pong") return;
            if (mountedRef.current) {
              setLastAlert(data);
              subscribersRef.current.forEach((cb) => cb(data));
            }
          } catch { /* ignore malformed messages */ }
        };

        ws.onclose = () => {
          if (mountedRef.current) setConnected(false);
          retryCountRef.current++;
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
          if (mountedRef.current) {
            // Each attempt mints its own ticket, since the previous one was
            // consumed by the connection it was made for.
            reconnectTimerRef.current = setTimeout(() => void connect(), delay);
          }
        };

        ws.onerror = () => ws.close();
      } catch {
        if (mountedRef.current) {
          reconnectTimerRef.current = setTimeout(() => void connect(), 5000);
        }
      }
    };

    void connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, []);

  return (
    <WebSocketContext.Provider value={{ connected, lastAlert, subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
}
