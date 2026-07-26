import type { UiMessage } from "../types";

interface StatusMessageProps {
  message: UiMessage | null;
  compact?: boolean;
}

export function StatusMessage({ message, compact = false }: StatusMessageProps) {
  if (!message) return null;
  return (
    <div
      className={`status-message status-${message.kind}${compact ? " is-compact" : ""}`}
      role={message.kind === "error" ? "alert" : "status"}
    >
      {message.text}
    </div>
  );
}
