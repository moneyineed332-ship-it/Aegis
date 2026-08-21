import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle, XCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let toastId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const remove = useCallback((id: number) => {
    timers.current.delete(id);
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const add = useCallback(
    (type: ToastType, message: string) => {
      const id = ++toastId;
      setToasts((prev) => [...prev.slice(-4), { id, type, message }]);
      const timer = setTimeout(() => remove(id), 4000);
      timers.current.set(id, timer);
    },
    [remove],
  );

  useEffect(() => {
    return () => {
      timers.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const ctx = useMemo(() => ({
    success: (msg: string) => add("success", msg),
    error: (msg: string) => add("error", msg),
    info: (msg: string) => add("info", msg),
  }), [add]);

  const icon = (type: ToastType) => {
    switch (type) {
      case "success": return <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />;
      case "error": return <XCircle className="w-4 h-4 text-red-400 shrink-0" />;
      case "info": return <Info className="w-4 h-4 text-primary shrink-0" />;
    }
  };

  const border = (type: ToastType) => {
    switch (type) {
      case "success": return "border-emerald-400/30";
      case "error": return "border-red-400/30";
      case "info": return "border-primary/30";
    }
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-2.5 px-3.5 py-2.5 rounded-xl border bg-[#0a1020]/95 backdrop-blur-md shadow-lg animate-[slideInRight_0.3s_ease-out] max-w-xs ${border(t.type)}`}
          >
            {icon(t.type)}
            <span className="font-['Inter'] text-[12px] text-foreground flex-1 leading-snug">{t.message}</span>
            <button onClick={() => remove(t.id)} aria-label="Fermer la notification" className="p-0.5 text-muted-foreground hover:text-foreground transition-colors shrink-0">
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
