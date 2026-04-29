"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/auth";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  free_tier: boolean;
  recommended: boolean;
  context_window?: number | null;
}

interface ProviderInfo {
  name: string;
  key_name: string;
  configured: boolean;
  models: ModelInfo[];
}

interface ModelListResponse {
  providers: ProviderInfo[];
  custom_model_allowed: boolean;
}

interface ValidateResult {
  valid: boolean;
  model_id: string;
  provider?: string;
  message: string;
  error?: string;
  suggestion?: string;
}

// ---------------------------------------------------------------------------
// Client-side cache (localStorage with 5-min TTL)
// ---------------------------------------------------------------------------

const CACHE_KEY = "va_model_list_cache";
const CACHE_TTL_MS = 5 * 60 * 1000;

function getCachedModelList(): ModelListResponse | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const { ts, data } = JSON.parse(raw);
    if (Date.now() - ts > CACHE_TTL_MS) return null;
    return data as ModelListResponse;
  } catch {
    return null;
  }
}

function setCachedModelList(data: ModelListResponse) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data }));
  } catch {
    // ignore quota errors
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseModelDisplayName(modelId: string): string {
  // Strip "openrouter/" prefix
  let name = modelId.replace(/^openrouter\//, "");
  // Strip provider prefix before last "/"
  const lastSlash = name.lastIndexOf("/");
  if (lastSlash !== -1) name = name.slice(lastSlash + 1);
  // Strip trailing "-openrouter"
  name = name.replace(/-openrouter$/, "");
  // Replace dashes/underscores with spaces and title-case
  return name.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatContextWindow(ctx?: number | null): string {
  if (!ctx) return "";
  if (ctx >= 1_000_000) return `${(ctx / 1_000_000).toFixed(1)}M ctx`;
  if (ctx >= 1_000) return `${Math.round(ctx / 1000)}K ctx`;
  return `${ctx} ctx`;
}

// ---------------------------------------------------------------------------
// Component props
// ---------------------------------------------------------------------------

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
}

// ---------------------------------------------------------------------------
// ModelSelector component
// ---------------------------------------------------------------------------

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [modelList, setModelList] = useState<ModelListResponse | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<"browse" | "custom">("browse");
  const [search, setSearch] = useState("");

  const [customInput, setCustomInput] = useState("");
  const [validating, setValidating] = useState(false);
  const [validateResult, setValidateResult] = useState<ValidateResult | null>(null);
  const validateTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  // ── Fetch model list ──────────────────────────────────────────────────────

  const fetchModelList = useCallback(async (force = false) => {
    if (!force) {
      const cached = getCachedModelList();
      if (cached) { setModelList(cached); return; }
    }
    setLoadingList(true);
    setListError(null);
    try {
      const token = getToken();
      const res = await fetch("/api/settings/models", {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`Failed to load models (${res.status})`);
      const data: ModelListResponse = await res.json();
      setModelList(data);
      setCachedModelList(data);
    } catch (e) {
      setListError(e instanceof Error ? e.message : "Failed to load models");
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => { void fetchModelList(); }, [fetchModelList]);

  // ── Close on outside click ────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // ── Focus search on open ──────────────────────────────────────────────────

  useEffect(() => {
    if (isOpen && mode === "browse") {
      setTimeout(() => searchRef.current?.focus(), 50);
    }
  }, [isOpen, mode]);

  // ── Debounced validation ──────────────────────────────────────────────────

  const triggerValidation = useCallback((id: string) => {
    if (validateTimer.current) clearTimeout(validateTimer.current);
    if (!id.trim()) { setValidateResult(null); return; }
    validateTimer.current = setTimeout(async () => {
      setValidating(true);
      setValidateResult(null);
      try {
        const token = getToken();
        const res = await fetch("/api/settings/models/validate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ model_id: id.trim() }),
        });
        const data: ValidateResult = await res.json();
        setValidateResult(data);
      } catch {
        setValidateResult({ valid: false, model_id: id, message: "Validation request failed" });
      } finally {
        setValidating(false);
      }
    }, 800);
  }, []);

  const handleCustomInput = (v: string) => {
    setCustomInput(v);
    triggerValidation(v);
    if (v.trim()) onChange(v.trim());
  };

  // ── Flat filterable model list for browse mode ────────────────────────────

  const allModels: (ModelInfo & { providerName: string })[] = [];
  if (modelList) {
    for (const p of modelList.providers) {
      if (!p.configured || p.models.length === 0) continue;
      for (const m of p.models) {
        allModels.push({ ...m, providerName: p.name });
      }
    }
  }

  const filtered = search.trim()
    ? allModels.filter((m) =>
        m.name.toLowerCase().includes(search.toLowerCase()) ||
        m.id.toLowerCase().includes(search.toLowerCase()) ||
        m.provider.toLowerCase().includes(search.toLowerCase())
      )
    : allModels;

  // Group by provider (preserve order)
  const grouped: { provider: string; models: typeof filtered }[] = [];
  for (const m of filtered) {
    const last = grouped[grouped.length - 1];
    if (last && last.provider === m.providerName) {
      last.models.push(m);
    } else {
      grouped.push({ provider: m.providerName, models: [m] });
    }
  }

  // ── Keyboard navigation ───────────────────────────────────────────────────

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) return;
    if (e.key === "Escape") { setIsOpen(false); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIndex((i) => Math.min(i + 1, filtered.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIndex((i) => Math.max(i - 1, 0));
    }
    if (e.key === "Enter" && focusedIndex >= 0 && filtered[focusedIndex]) {
      onChange(filtered[focusedIndex].id);
      setIsOpen(false);
    }
  };

  // ── Derived display name ──────────────────────────────────────────────────

  const displayName = (() => {
    if (!value) return "Select model";
    const found = allModels.find((m) => m.id === value);
    return found ? found.name : parseModelDisplayName(value);
  })();

  // ── Check if no keys configured at all ───────────────────────────────────

  const noKeysConfigured =
    modelList !== null && modelList.providers.every((p) => !p.configured);

  // ── Mode C: No key banner ─────────────────────────────────────────────────

  if (noKeysConfigured && !loadingList) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-[var(--warning)]/40 bg-[var(--warning)]/10 px-3 py-2 text-[11px]">
        <span className="text-[var(--warning)]">⚠</span>
        <span className="text-[var(--text-secondary)]">
          No LLM provider configured.{" "}
          <Link href="/settings" className="text-[var(--accent)] hover:underline">
            Add an API key in Settings →
          </Link>
        </span>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div ref={containerRef} className="relative" onKeyDown={handleKeyDown}>
      {/* Trigger button */}
      <button
        id="model-selector-trigger"
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-center gap-2 rounded-md border border-[var(--border-dim)] bg-[var(--bg-overlay)] px-2.5 py-1 font-mono text-[11px] text-[var(--text-secondary)] outline-none transition-colors hover:border-[var(--border-subtle)] hover:text-[var(--text-primary)] focus:border-[var(--accent-border)]"
      >
        <span className="max-w-[130px] truncate">{displayName}</span>
        <svg
          width="10"
          height="10"
          viewBox="0 0 16 16"
          fill="none"
          className={`shrink-0 opacity-50 transition-transform ${isOpen ? "rotate-180" : ""}`}
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div
          className="absolute bottom-full left-0 z-50 mb-2 w-[380px] overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-2xl"
          style={{ maxHeight: "min(480px, 80vh)" }}
          role="dialog"
          aria-label="Model picker"
        >
          {/* Tabs */}
          <div className="flex border-b border-[var(--border-dim)] bg-[var(--bg-void)]/60">
            <button
              type="button"
              onClick={() => setMode("browse")}
              className={`flex-1 px-4 py-2.5 font-mono text-[11px] font-semibold transition-colors ${
                mode === "browse"
                  ? "text-[var(--accent)] border-b border-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              Browse Models
            </button>
            <button
              type="button"
              onClick={() => setMode("custom")}
              className={`flex-1 px-4 py-2.5 font-mono text-[11px] font-semibold transition-colors ${
                mode === "custom"
                  ? "text-[var(--accent)] border-b border-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              }`}
            >
              Enter Model ID
            </button>
          </div>

          {/* ── Mode A: Browse ── */}
          {mode === "browse" && (
            <>
              {/* Search */}
              <div className="border-b border-[var(--border-dim)] px-3 py-2">
                <div className="flex items-center gap-2">
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" className="shrink-0 text-[var(--text-muted)]">
                    <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5" />
                    <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                  <input
                    ref={searchRef}
                    type="text"
                    value={search}
                    onChange={(e) => { setSearch(e.target.value); setFocusedIndex(-1); }}
                    placeholder="Search models..."
                    className="w-full bg-transparent font-mono text-[11px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
                  />
                  {search && (
                    <button
                      type="button"
                      onClick={() => setSearch("")}
                      className="shrink-0 text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>

              {/* List */}
              <div
                ref={listRef}
                className="overflow-y-auto"
                style={{ maxHeight: "340px" }}
                role="listbox"
              >
                {loadingList && (
                  <div className="flex items-center justify-center gap-2 py-8 text-[11px] text-[var(--text-muted)]">
                    <span className="h-3 w-3 animate-spin rounded-full border border-[var(--accent)] border-t-transparent" />
                    Loading models...
                  </div>
                )}

                {listError && (
                  <div className="px-4 py-6 text-center text-[11px] text-[var(--warning)]">
                    {listError}
                    <button
                      type="button"
                      onClick={() => void fetchModelList(true)}
                      className="ml-2 underline hover:text-[var(--text-primary)]"
                    >
                      Retry
                    </button>
                  </div>
                )}

                {!loadingList && !listError && grouped.length === 0 && (
                  <div className="px-4 py-6 text-center text-[11px] text-[var(--text-muted)]">
                    {search ? "No models match your search." : "No models available."}
                  </div>
                )}

                {!loadingList && !listError && grouped.map((group) => (
                  <div key={group.provider}>
                    {/* Provider header */}
                    <div className="sticky top-0 bg-[var(--bg-surface)]/95 px-3 py-1.5 backdrop-blur-sm">
                      <span className="font-mono text-[9px] font-bold uppercase tracking-[0.15em] text-[var(--text-muted)]">
                        {group.provider}
                      </span>
                    </div>

                    {/* Models */}
                    {group.models.map((m, idx) => {
                      const globalIdx = filtered.findIndex((f) => f.id === m.id);
                      const isFocused = globalIdx === focusedIndex;
                      const isSelected = m.id === value;
                      return (
                        <button
                          key={m.id}
                          type="button"
                          role="option"
                          aria-selected={isSelected}
                          onClick={() => { onChange(m.id); setIsOpen(false); }}
                          onMouseEnter={() => setFocusedIndex(globalIdx)}
                          className={`flex w-full items-center justify-between px-3 py-2 text-left transition-colors ${
                            isFocused
                              ? "bg-[var(--accent-dim)]"
                              : isSelected
                              ? "bg-[var(--bg-raised)]"
                              : "hover:bg-[var(--bg-raised)]"
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            {isSelected && (
                              <span className="shrink-0 text-[var(--accent)] text-[10px]">✓</span>
                            )}
                            <span className={`truncate font-mono text-[11px] ${isSelected ? "text-[var(--accent)]" : "text-[var(--text-primary)]"}`}>
                              {m.name}
                            </span>
                            {m.free_tier && (
                              <span className="shrink-0 rounded bg-[var(--success)]/15 px-1 py-0.5 font-mono text-[8px] font-bold uppercase tracking-wider text-[var(--success)]">
                                Free
                              </span>
                            )}
                            {m.recommended && !m.free_tier && (
                              <span className="shrink-0 rounded bg-[var(--accent)]/15 px-1 py-0.5 font-mono text-[8px] font-bold uppercase tracking-wider text-[var(--accent)]">
                                ★
                              </span>
                            )}
                          </div>
                          {m.context_window && (
                            <span className="shrink-0 font-mono text-[9px] text-[var(--text-muted)]">
                              {formatContextWindow(m.context_window)}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))}

                {/* Unconfigured providers */}
                {!loadingList && !listError && modelList && (
                  <div>
                    {modelList.providers.filter((p) => !p.configured).map((p) => (
                      <div key={p.name} className="border-t border-[var(--border-dim)] px-3 py-2">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-[var(--text-muted)]">
                            {p.name}
                          </span>
                          <Link
                            href="/settings"
                            onClick={() => setIsOpen(false)}
                            className="font-mono text-[9px] text-[var(--accent)] hover:underline"
                          >
                            Add API key →
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* ── Mode B: Custom ID ── */}
          {mode === "custom" && (
            <div className="p-4">
              <p className="mb-3 font-mono text-[10px] leading-relaxed text-[var(--text-muted)]">
                Enter any model ID directly. Validation is advisory — you can still submit without a valid result.
              </p>

              <input
                type="text"
                value={customInput}
                onChange={(e) => handleCustomInput(e.target.value)}
                placeholder="e.g. openrouter/meta-llama/llama-3.3-70b-instruct"
                autoFocus
                className="w-full rounded-md border border-[var(--border-dim)] bg-[var(--bg-overlay)] px-3 py-2 font-mono text-[11px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus:border-[var(--accent-border)]"
              />

              {/* Validation state */}
              <div className="mt-2 min-h-[28px]">
                {validating && (
                  <div className="flex items-center gap-2 font-mono text-[10px] text-[var(--text-muted)]">
                    <span className="h-2.5 w-2.5 animate-spin rounded-full border border-[var(--text-muted)] border-t-transparent" />
                    Checking model...
                  </div>
                )}
                {!validating && validateResult && (
                  <div
                    className={`flex flex-col gap-0.5 font-mono text-[10px] ${
                      validateResult.valid ? "text-[var(--success)]" : "text-[var(--danger)]"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>{validateResult.valid ? "✓" : "✗"}</span>
                      <span>{validateResult.message}</span>
                    </div>
                    {validateResult.suggestion && (
                      <p className="pl-4 text-[var(--text-muted)]">{validateResult.suggestion}</p>
                    )}
                  </div>
                )}
              </div>

              <button
                type="button"
                disabled={!customInput.trim()}
                onClick={() => {
                  if (customInput.trim()) {
                    onChange(customInput.trim());
                    setIsOpen(false);
                  }
                }}
                className="mt-3 w-full rounded-md bg-[var(--accent)] px-3 py-1.5 font-mono text-[11px] font-semibold text-[var(--text-inverse)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
              >
                Use This Model
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
