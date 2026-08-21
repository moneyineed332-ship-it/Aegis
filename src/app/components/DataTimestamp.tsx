import { Clock } from "lucide-react";

export function DataTimestamp({ lastUpdated }: { lastUpdated: Date | null }) {
  if (!lastUpdated) return null;
  const time = lastUpdated.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return (
    <span className="inline-flex items-center gap-1 font-['JetBrains_Mono'] text-[12px] text-muted-foreground/60">
      <Clock className="w-3 h-3" />
      {time}
    </span>
  );
}
