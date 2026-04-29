"use client";

import { useMemo, useState } from "react";
import {
  CATEGORY_META,
  EntityCategoryKey,
  InvestigationEntity,
} from "@/lib/types/investigation";
import { getMitreUrl, getCveUrl } from "@/lib/utils/entityLinks";
import { getEntityTypeConfig } from "@/lib/utils/entityTypes";

interface Props {
  entities: InvestigationEntity[];
  selectedIds: Set<string>;
  onToggle: (id: string, next: boolean) => void;
  onEntityActivate: (e: InvestigationEntity) => void;
  loading: boolean;
  investigationParamId: string;
  minConfidence?: number;
  onMinConfidenceChange?: (value: number) => void;
}

const CONFIDENCE_OPTIONS = [
  { label: "All confidence levels", value: 0 },
  { label: ">= 0.95 (verified)", value: 0.95 },
  { label: ">= 0.85 (high)", value: 0.85 },
  { label: ">= 0.75 (medium)", value: 0.75 },
  { label: ">= 0.50 (low)", value: 0.5 },
];

export function EntitySidebar({
  entities,
  selectedIds,
  onToggle,
  onEntityActivate,
  loading,
  minConfidence = 0.75,
  onMinConfidenceChange,
}: Props) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const s = search.toLowerCase().trim();
    let result = entities;
    if (s) {
      result = result.filter(
        (e) =>
          e.value.toLowerCase().includes(s) ||
          (e.category as string).toLowerCase().includes(s)
      );
    }
    return result;
  }, [entities, search]);

  const grouped = useMemo(() => {
    const map: Partial<Record<EntityCategoryKey, InvestigationEntity[]>> = {};
    filtered.forEach((e) => {
      const cat = e.category as EntityCategoryKey;
      if (!map[cat]) map[cat] = [];
      map[cat]!.push(e);
    });
    return Object.entries(map).sort((a, b) => b[1].length - a[1].length) as [
      EntityCategoryKey,
      InvestigationEntity[],
    ][];
  }, [filtered]);

  return (
    <div className="flex h-full flex-col font-sans">
      {/* Search Header */}
      <div className="p-4 border-b border-[var(--border-dim)] bg-[var(--bg-surface)] space-y-3">
        <div className="relative group">
          <svg
            className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)] group-focus-within:text-[var(--accent)] transition-colors"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Search investigation..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-[var(--border-subtle)] bg-[var(--bg-void)] py-1.5 pl-9 pr-3 text-[12px] text-[var(--text-primary)] outline-none transition-all placeholder:text-[var(--text-muted)] focus:border-[var(--accent-border)] focus:ring-1 focus:ring-[var(--accent-dim)]"
          />
        </div>
        <select
          value={minConfidence}
          onChange={(e) => onMinConfidenceChange?.(parseFloat(e.target.value))}
          className="w-full rounded-md border border-[var(--border-subtle)] bg-[var(--bg-void)] py-1.5 px-2 text-[11px] text-[var(--text-secondary)] outline-none transition-all focus:border-[var(--accent-border)] cursor-pointer"
        >
          {CONFIDENCE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <div className="text-[10px] font-mono text-[var(--text-muted)] text-center">
          {filtered.length} entities at this confidence level
        </div>
      </div>

      {/* Entity Lists */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-2 custom-scrollbar bg-[var(--bg-surface)]">
        {loading && grouped.length === 0 ? (
          <div className="flex flex-col gap-3 p-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 w-full animate-pulse rounded bg-[var(--bg-raised)]" />
            ))}
          </div>
        ) : grouped.length === 0 ? (
          <div className="flex h-32 flex-col items-center justify-center text-center p-4">
            <span className="text-[18px] text-[var(--text-muted)] opacity-20">◆</span>
            <p className="mt-2 text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-widest">
              No matching intelligence
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {grouped.map(([cat, items]) => {
              const meta = CATEGORY_META[cat] || CATEGORY_META.OTHER;
              return (
                <section key={cat} className="space-y-1">
                  <header className="sticky top-0 z-10 flex items-center justify-between bg-[var(--bg-surface)] px-2 py-1">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-3 w-1 rounded-full"
                        style={{ backgroundColor: meta.color }}
                      />
                      <span className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--text-secondary)]">
                        {meta.label}
                      </span>
                    </div>
                    <span className="font-mono text-[9px] text-[var(--text-muted)]">
                      {items.length}
                    </span>
                  </header>

                  <div className="space-y-0.5">
                    {items.map((e) => {
                      const selected = selectedIds.has(e.id);
                      const typeConfig = getEntityTypeConfig(e.entity_type);
                      const isMitresTech = e.entity_type === "MITRE_TECHNIQUE";
                      const isCve = e.entity_type === "CVE";
                      const isOnion = e.entity_type === "ONION_URL";

                      const renderValue = () => {
                        if (isMitresTech) {
                          return (
                            <a
                              href={getMitreUrl(e.value)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="truncate font-mono text-[12px] font-semibold tracking-tighter text-[var(--accent)] hover:underline"
                              onClick={(ev) => ev.stopPropagation()}
                            >
                              {e.value}
                              <svg className="ml-1 inline h-2.5 w-2.5" viewBox="0 0 16 16" fill="none">
                                <path d="M12 2h4v4M14 2L8 8M6 14H2v-4M2 14l6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            </a>
                          );
                        }
                        if (isCve) {
                          return (
                            <a
                              href={getCveUrl(e.value)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="truncate font-mono text-[12px] font-semibold tracking-tighter text-[var(--accent)] hover:underline"
                              onClick={(ev) => ev.stopPropagation()}
                            >
                              {e.value}
                              <svg className="ml-1 inline h-2.5 w-2.5" viewBox="0 0 16 16" fill="none">
                                <path d="M12 2h4v4M14 2L8 8M6 14H2v-4M2 14l6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            </a>
                          );
                        }
                        return (
                          <span className={`truncate font-mono text-[12px] font-semibold tracking-tighter ${
                            selected ? "text-[var(--accent)]" : "text-[var(--text-primary)]"
                          }`}>
                            {e.value}
                          </span>
                        );
                      };

                      return (
                        <div
                          key={e.id}
                          className={`group relative flex cursor-pointer items-center justify-between rounded-md border py-2 px-3 transition-all ${
                            selected
                              ? "border-[var(--accent-border)] bg-[var(--accent-dim)]"
                              : "border-transparent hover:bg-[var(--bg-raised)] hover:border-[var(--border-dim)]"
                          }`}
                          onClick={() => onEntityActivate(e)}
                        >
                          <div className="flex min-w-0 flex-col gap-0.5">
                            <div className="flex items-center gap-2">
                              {renderValue()}
                              <span
                                className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                                style={{
                                  backgroundColor: typeConfig.color,
                                  color: typeConfig.textColor,
                                }}
                              >
                                {typeConfig.label}
                              </span>
                            </div>
                            {e.context?.[0] && (
                              <span className="truncate text-[10px] text-[var(--text-muted)] leading-tight opacity-70">
                                {e.context[0]}
                              </span>
                            )}
                          </div>

                          <button
                            onClick={(ev) => {
                              ev.stopPropagation();
                              onToggle(e.id, !selected);
                            }}
                            className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
                              selected
                                ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--text-inverse)]"
                                : "border-[var(--border-subtle)] opacity-0 group-hover:opacity-100 hover:border-[var(--accent)]"
                            }`}
                          >
                            {selected && (
                              <svg viewBox="0 0 16 16" fill="white" className="h-2.5 w-2.5">
                                <path d="M13.5 4.5l-7.5 7.5-3.5-3.5" stroke="white" strokeWidth="2" fill="none" />
                              </svg>
                            )}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

