"use client";

import { useEffect, useRef, useState } from "react";

interface ProgressData {
  step: number;
  step_label: string;
  progress: number;
  status: string;
  entity_count: number;
  page_count: number;
  done?: boolean;
}

interface Props {
  investigationId: string;
  onComplete?: () => void;
}

export function InvestigationProgress({ investigationId, onComplete }: Props) {
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const isDoneRef = useRef(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(
      `/api/investigations/${investigationId}/progress`,
      { withCredentials: true }
    );
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data: ProgressData = JSON.parse(e.data);
        setProgress(data);
        setConnectionError(false);
        if (data.done) {
          isDoneRef.current = true;
          es.close();
          onComplete?.();
        }
      } catch {
        // ignore malformed messages
      }
    };

    es.onerror = () => {
      if (!isDoneRef.current) {
        setConnectionError(true);
      }
      es.close();
    };

    return () => {
      es.close();
    };
  }, [investigationId, onComplete]);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const elapsedLabel = elapsed < 60
    ? `${elapsed}s`
    : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;

  const pct = progress?.progress ?? 0;
  const label = progress?.step_label ?? "Initializing...";
  const entities = progress?.entity_count ?? 0;
  const pages = progress?.page_count ?? 0;

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--border-dim)] bg-[var(--bg-surface)] p-6">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-[var(--accent)]">
            Pipeline Progress
          </span>
          <span className="text-[13px] font-medium text-[var(--text-primary)]">
            {label}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] text-[var(--text-muted)]">
            ELAPSED: {elapsedLabel}
          </span>
          {connectionError && (
            <span className="font-mono text-[10px] text-[var(--danger)]">
              CONNECTION ERROR
            </span>
          )}
        </div>
      </div>

      <div className="relative h-2 w-full overflow-hidden rounded-full bg-[var(--border-dim)]">
        <div
          className="absolute left-0 top-0 h-full rounded-full bg-[var(--accent)] transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] text-[var(--text-muted)]">
          {pct}%
        </span>
        <span className="font-mono text-[10px] text-[var(--text-muted)]">
          {entities} entities found · {pages} pages scraped
        </span>
      </div>

      {progress?.status && (
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider ${
              progress.status === "completed"
                ? "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]"
                : progress.status === "failed"
                ? "border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]"
                : "border-[var(--warning)]/30 bg-[var(--warning)]/10 text-[var(--warning)]"
            }`}
          >
            <span
              className={`h-1 w-1 rounded-full ${
                progress.status === "completed"
                  ? "bg-[var(--success)]"
                  : progress.status === "failed"
                  ? "bg-[var(--danger)]"
                  : "bg-[var(--warning)] animate-pulse"
              }`}
            />
            {progress.status}
          </span>
        </div>
      )}
    </div>
  );
}