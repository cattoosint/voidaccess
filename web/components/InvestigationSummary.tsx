"use client";

import Link from "next/link";
import { InvestigationSummary as Inv } from "@/lib/types/investigation";

interface Props {
  investigation: Inv;
  investigationParamId: string;
  entityCount: number;
  relationshipCount: number;
  pagesCrawled: number;
  lastUpdatedLabel: string;
}

function parseModelDisplayName(modelId: string): string {
  let name = modelId.replace(/^openrouter\//, "");
  const lastSlash = name.lastIndexOf("/");
  if (lastSlash !== -1) name = name.slice(lastSlash + 1);
  name = name.replace(/-openrouter$/, "");
  return name.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function StatusBadge({ status }: { status: string }) {
  const isProcessing = status === "processing" || status === "pending";
  const isFailed = status === "failed";
  const isNoResults = status === "completed_no_results";
  const isComplete = status === "completed";

  const baseDot = "h-1.5 w-1.5 rounded-full";
  const baseLabel = "font-mono text-[10px] font-bold uppercase tracking-wider";

  if (isProcessing) {
    return (
      <div className="flex items-center gap-2.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-1">
        <span className={`${baseDot} bg-[var(--warning)] animate-pulse`} />
        <span className={`${baseLabel} text-[var(--text-secondary)]`}>Running</span>
      </div>
    );
  }

  if (isFailed) {
    return (
      <div className="flex items-center gap-2.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-1">
        <span className={`${baseDot} bg-[var(--danger)]`} />
        <span className={`${baseLabel} text-[var(--danger)]`}>Failed</span>
      </div>
    );
  }

  if (isNoResults) {
    return (
      <div className="flex items-center gap-2.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-1">
        <span className={`${baseDot} bg-[var(--neutral)]`} />
        <span className={`${baseLabel} text-[var(--text-muted)]`}>No results</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-1">
      <span className={`${baseDot} bg-[var(--success)] shadow-[0_0_8px_var(--success)]`} />
      <span className={`${baseLabel} text-[var(--text-secondary)]`}>Complete</span>
    </div>
  );
}

export function InvestigationSummary({
  investigation,
  entityCount,
  relationshipCount,
  pagesCrawled,
  lastUpdatedLabel,
}: Props) {
  return (
    <header className="flex h-[56px] shrink-0 items-center justify-between border-b border-[var(--border-dim)] bg-[var(--bg-void)]/60 px-6 backdrop-blur-xl">
      <div className="flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 font-heading transition-opacity hover:opacity-80">
          <span className="text-[var(--accent)]" aria-hidden>●</span>
          <span className="text-[15px] font-bold tracking-tight text-[var(--text-primary)]">voidaccess</span>
        </Link>

        <div className="h-4 w-px bg-[var(--border-dim)]" />

        <div className="flex items-center gap-5 font-mono text-[11px] font-medium tracking-tight">
          <div className="flex items-center gap-1.5 text-ellipsis overflow-hidden max-w-[200px]">
            <span className="text-[var(--text-muted)]">ID:</span>
            <span className="text-[var(--text-secondary)] uppercase">{String(investigation.id).slice(0, 8)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--text-primary)]">{entityCount}</span>
            <span className="text-[var(--text-muted)] uppercase">Entities</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--text-primary)]">{relationshipCount}</span>
            <span className="text-[var(--text-muted)] uppercase">Edges</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--text-primary)]">{pagesCrawled}</span>
            <span className="text-[var(--text-muted)] uppercase">Pages</span>
          </div>
          {investigation.model_used && (
            <div className="hidden md:flex items-center gap-1.5 rounded border border-[var(--border-dim)] bg-[var(--bg-overlay)] px-2 py-0.5">
              <span className="text-[var(--text-muted)] uppercase">Model:</span>
              <span className="text-[var(--text-secondary)]" title={investigation.model_used}>
                {parseModelDisplayName(investigation.model_used)}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <StatusBadge status={investigation.status} />

        <div className="h-4 w-px bg-[var(--border-dim)]" />

        <button className="flex h-8 items-center gap-2 rounded border border-[var(--border-dim)] bg-[var(--bg-raised)] px-3 text-[11px] font-semibold text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-overlay)]">
          Export Archive
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none" className="opacity-50">
            <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </header>
  );
}

