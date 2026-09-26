import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import { getAdminToken } from "../../lib/api";

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

    const connect = () => {
      if (!mountedRef.current || retryCountRef.current >= maxRetries) return;
      try {
        const baseUrl = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/^http/, "ws");
        const token = getAdminToken();
        const wsUrl = token ? `${baseUrl}/ws/alerts?token=${encodeURIComponent(token)}` : `${baseUrl}/ws/alerts`;
        const ws = new WebSocket(wsUrl);
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
            reconnectTimerRef.current = setTimeout(connect, delay);
          }
        };

        ws.onerror = () => ws.close();
      } catch {
        if (mountedRef.current) {
          reconnectTimerRef.current = setTimeout(connect, 5000);
        }
      }
    };

    connect();

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
