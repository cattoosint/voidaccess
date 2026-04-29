"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import louvain from "graphology-communities-louvain";
import Sigma from "sigma";
import {
  CATEGORY_META,
  graphNodeTypeToCategory,
  type EntityCategoryKey,
  type GraphNodeJSON,
  type InvestigationGraphResponse,
} from "@/lib/types/investigation";

// ─── Palette ───────────────────────────────────────────────────────────────────

const CAT_COLOR: Record<EntityCategoryKey, string> = {
  THREAT_ACTOR: "#ff6b6b",
  WALLET:       "#58a6ff",
  MALWARE:      "#f0a050",
  FORUM:        "#79b8ff",
  C2_SERVER:    "#c678dd",
  CVE:          "#e5c07b",
  PASTE_URL:    "#56b6c2",
  ONION_URL:    "#88aaff",
  EMAIL:        "#d4a96a",
  PGP_KEY:      "#73d397",
  OTHER:        "#4a5260",
};

const EDGE_DEFAULT = "rgba(90,110,140,0.12)";
const EDGE_ACTIVE  = "#58a6ff";
const NODE_DIM     = "#181d26";

// ─── Smart label truncation ────────────────────────────────────────────────────

function smartLabel(raw: string): string {
  const s = raw.trim();
  // Onion URL → first 10 chars + …onion
  if (s.toLowerCase().includes(".onion")) {
    const m = s.match(/([a-z2-7]{8,})/i);
    return m ? m[1].slice(0, 10) + "….onion" : s.slice(0, 14) + "….onion";
  }
  // OTX / external threat intel URL
  if (s.toLowerCase().includes("otx.alienvault") || s.toLowerCase().includes("otx.")) {
    const part = s.split("/").filter(Boolean).pop() ?? s;
    return "OTX · " + part.slice(0, 18);
  }
  // Any HTTP URL → just the hostname
  if (s.startsWith("http")) {
    try {
      const u = new URL(s.toLowerCase());
      return u.hostname.replace(/^www\./, "").slice(0, 22);
    } catch { /* fall through */ }
  }
  return s.length > 30 ? s.slice(0, 28) + "…" : s;
}

// ─── Graph builder ─────────────────────────────────────────────────────────────

function buildGraph(data: InvestigationGraphResponse, strongOnly: boolean): Graph {
  const g = new Graph({ multi: true, type: "directed" });

  for (const n of data.nodes) {
    if (g.hasNode(n.id)) continue;
    const cat = graphNodeTypeToCategory(String(n.type ?? ""));
    g.addNode(n.id, {
      label:      smartLabel(n.id),   // truncated from the start
      size:       5,
      color:      CAT_COLOR[cat],
      origColor:  CAT_COLOR[cat],
      vaCategory: cat,
      community:  "0",
      raw:        n as GraphNodeJSON,
    });
  }

  let ei = 0;
  for (const e of data.edges) {
    if (strongOnly && e.type === "CO_INVESTIGATION") continue;
    if (!g.hasNode(e.source) || !g.hasNode(e.target)) continue;
    g.addEdgeWithKey(`e${ei++}`, e.source, e.target, {
      size:  0.6,
      color: EDGE_DEFAULT,
    });
  }

  // Size by degree — log scale 4 → 22
  g.forEachNode((n) => {
    const sz = Math.max(4, Math.min(22, 4 + Math.log1p(g.degree(n)) * 4));
    g.setNodeAttribute(n, "size",     sz);
    g.setNodeAttribute(n, "origSize", sz);
  });

  // Community detection first
  try { louvain.assign(g, { nodeCommunityAttribute: "community" }); } catch { /* ok */ }

  // Pre-position nodes by community sector so FA2 starts well-separated
  const commSet: Record<string, boolean> = {};
  g.forEachNode((n) => { commSet[g.getNodeAttribute(n, "community") as string] = true; });
  const allComms = Object.keys(commSet);
  const numComms = Math.max(1, allComms.length);
  const RING = 180;

  g.forEachNode((n) => {
    const c     = g.getNodeAttribute(n, "community") as string;
    const idx   = allComms.indexOf(c);
    const angle = (idx / numComms) * 2 * Math.PI - Math.PI / 2;
    g.setNodeAttribute(n, "x", Math.cos(angle) * RING + (Math.random() - 0.5) * 40);
    g.setNodeAttribute(n, "y", Math.sin(angle) * RING + (Math.random() - 0.5) * 40);
  });

  try {
    forceAtlas2.assign(g, {
      iterations: 300,
      settings: {
        scalingRatio:                   16,
        strongGravityMode:              true,
        gravity:                        0.04,
        linLogMode:                     true,
        barnesHutOptimize:              true,
        barnesHutTheta:                 0.6,
        adjustSizes:                    false,
        outboundAttractionDistribution: false,
        edgeWeightInfluence:            0,
        slowDown:                       5,
      },
    });
  } catch (e) { console.warn("FA2 failed", e); }

  return g;
}

// ─── Cluster data ──────────────────────────────────────────────────────────────

interface Cluster {
  id:        string;
  label:     string;
  cx:        number;
  cy:        number;
  labelGX:   number;  // label anchor in graph space
  labelGY:   number;
  radius:    number;
  color:     string;
  nodeCount: number;
  members:   string[];
}

function buildClusters(g: Graph): Cluster[] {
  const buckets: Record<string, string[]> = {};
  g.forEachNode((n) => {
    const c = (g.getNodeAttribute(n, "community") as string) ?? "0";
    (buckets[c] ??= []).push(n);
  });

  // Graph centroid for outward push
  let gcx = 0, gcy = 0, total = 0;
  g.forEachNode((n) => {
    gcx += g.getNodeAttribute(n, "x") as number;
    gcy += g.getNodeAttribute(n, "y") as number;
    total++;
  });
  if (total > 0) { gcx /= total; gcy /= total; }

  const clusters: Cluster[] = [];

  for (const [cid, members] of Object.entries(buckets)) {
    // Only label meaningful clusters
    if (members.length < 3) continue;

    let cx = 0, cy = 0;
    for (const n of members) {
      cx += g.getNodeAttribute(n, "x") as number;
      cy += g.getNodeAttribute(n, "y") as number;
    }
    cx /= members.length;
    cy /= members.length;

    let radius = 0;
    for (const n of members) {
      const dx = (g.getNodeAttribute(n, "x") as number) - cx;
      const dy = (g.getNodeAttribute(n, "y") as number) - cy;
      radius = Math.max(radius, Math.sqrt(dx * dx + dy * dy));
    }
    radius = Math.max(radius, 12);

    const catCount: Record<string, number> = {};
    let topNode = members[0], topDeg = -1;
    for (const n of members) {
      const cat = g.getNodeAttribute(n, "vaCategory") as EntityCategoryKey;
      catCount[cat] = (catCount[cat] ?? 0) + 1;
      const d = g.degree(n);
      if (d > topDeg) { topDeg = d; topNode = n; }
    }
    const domCat  = Object.entries(catCount).sort((a, b) => b[1] - a[1])[0][0] as EntityCategoryKey;
    const color   = CAT_COLOR[domCat] ?? "#58a6ff";
    const numCats = Object.keys(catCount).length;
    const hubRaw  = (g.getNodeAttribute(topNode, "label") as string ?? topNode);
    const label   = numCats === 1
      ? `${CATEGORY_META[domCat]?.short ?? domCat} · ${hubRaw}`
      : hubRaw;

    // Direction from graph center through cluster centroid
    const dirX   = cx - gcx, dirY = cy - gcy;
    const dirLen = Math.sqrt(dirX * dirX + dirY * dirY) || 1;
    const nx = dirX / dirLen, ny = dirY / dirLen;

    // Push label well beyond cluster edge
    const PUSH = radius * 2.8 + 90;
    clusters.push({
      id: cid, label, cx, cy,
      labelGX: cx + nx * PUSH,
      labelGY: cy + ny * PUSH,
      radius, color, nodeCount: members.length, members,
    });
  }

  return clusters;
}

// ─── Screen-space label positions + collision avoidance ────────────────────────

interface LabelPos {
  id:        string;
  label:     string;
  color:     string;
  nodeCount: number;
  opacity:   number;
  anchorX:   number;
  anchorY:   number;
  labelX:    number;
  labelY:    number;
  members:   string[];
}

const PILL_W = 185, PILL_H = 26;

function resolveCollisions(labels: LabelPos[], cw: number, ch: number): void {
  const MW = PILL_W + 12, MH = PILL_H + 10;
  for (let iter = 0; iter < 60; iter++) {
    let moved = false;
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        const a = labels[i], b = labels[j];
        const dx = b.labelX - a.labelX;
        const dy = b.labelY - a.labelY;
        const ox = MW - Math.abs(dx);
        const oy = MH - Math.abs(dy);
        if (ox > 0 && oy > 0) {
          const sx = (dx >= 0 ? 1 : -1);
          const sy = (dy >= 0 ? 1 : -1);
          if (ox < oy) {
            a.labelX -= sx * (ox / 2 + 1);
            b.labelX += sx * (ox / 2 + 1);
          } else {
            a.labelY -= sy * (oy / 2 + 1);
            b.labelY += sy * (oy / 2 + 1);
          }
          moved = true;
        }
      }
    }
    // Re-clamp after each iteration
    for (const p of labels) {
      p.labelX = Math.max(PILL_W / 2 + 6, Math.min(cw - PILL_W / 2 - 6, p.labelX));
      p.labelY = Math.max(PILL_H / 2 + 6, Math.min(ch - PILL_H / 2 - 6, p.labelY));
    }
    if (!moved) break;
  }
}

function calcLabelPositions(
  sigma: Sigma,
  clusters: Cluster[],
  cw: number,
  ch: number,
): LabelPos[] {
  const ratio   = sigma.getCamera().ratio;
  // Fully visible ratio range 0.25–1.8; fade at extremes
  const opacity = ratio < 0.08 ? 0
    : ratio < 0.25 ? (ratio - 0.08) / 0.17
    : ratio > 2.2  ? Math.max(0, 1 - (ratio - 2.2) / 1.2)
    : 1;

  const positions: LabelPos[] = clusters.map((cl) => {
    const anchor = sigma.graphToViewport({ x: cl.cx,     y: cl.cy });
    const raw    = sigma.graphToViewport({ x: cl.labelGX, y: cl.labelGY });
    return {
      id:        cl.id,
      label:     cl.label,
      color:     cl.color,
      nodeCount: cl.nodeCount,
      opacity,
      anchorX:   anchor.x,
      anchorY:   anchor.y,
      labelX:    Math.max(PILL_W / 2 + 6, Math.min(cw - PILL_W / 2 - 6, raw.x)),
      labelY:    Math.max(PILL_H / 2 + 6, Math.min(ch - PILL_H / 2 - 6, raw.y)),
      members:   cl.members,
    };
  });

  // Sort largest clusters first (they get priority in collision resolution)
  positions.sort((a, b) => b.nodeCount - a.nodeCount);
  resolveCollisions(positions, cw, ch);
  return positions;
}

// ─── Component ─────────────────────────────────────────────────────────────────

export type GraphVisualizationProps = {
  data:             InvestigationGraphResponse | null;
  loading:          boolean;
  error:            string | null;
  selectedNodeId:   string | null;
  hiddenCategories: Set<EntityCategoryKey>;
  strongEdgesOnly:  boolean;
  onNodeClick:      (nodeId: string, payload: GraphNodeJSON | null) => void;
  focusNodeId:      string | null;
  onFocusHandled:   () => void;
};

export function GraphVisualization({
  data,
  loading,
  error,
  selectedNodeId,
  hiddenCategories,
  strongEdgesOnly,
  onNodeClick,
  focusNodeId,
  onFocusHandled,
}: GraphVisualizationProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef     = useRef<Sigma | null>(null);
  const graphRef     = useRef<Graph | null>(null);
  const clustersRef  = useRef<Cluster[]>([]);
  const onClickRef   = useRef(onNodeClick);
  onClickRef.current = onNodeClick;

  // Refs for use inside sigma reducers (avoid stale closures)
  const selNodeRef   = useRef(selectedNodeId);
  const hidCatsRef   = useRef(hiddenCategories);
  const selCommRef   = useRef<string | null>(null);
  selNodeRef.current = selectedNodeId;
  hidCatsRef.current = hiddenCategories;

  const [selectedComm,   setSelectedComm]   = useState<string | null>(null);
  const [labelPositions, setLabelPositions] = useState<LabelPos[]>([]);

  useEffect(() => { selCommRef.current = selectedComm; }, [selectedComm]);

  const rebuildKey = useMemo(() => {
    if (!data) return "empty";
    return `${data.nodes.length}-${data.edges.length}-${strongEdgesOnly}`;
  }, [data, strongEdgesOnly]);

  function refreshLabels() {
    const sigma = sigmaRef.current;
    const el    = containerRef.current;
    if (!sigma || !el || !clustersRef.current.length) return;
    setLabelPositions(calcLabelPositions(sigma, clustersRef.current, el.offsetWidth, el.offsetHeight));
  }

  // ── Build sigma ───────────────────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !data || data.nodes.length === 0) return;

    sigmaRef.current?.kill();
    setLabelPositions([]);

    const g = buildGraph(data, strongEdgesOnly);
    graphRef.current    = g;
    clustersRef.current = buildClusters(g);

    const sigma = new Sigma(g, el, {
      renderLabels:   true,
      labelFont:      "'IBM Plex Mono', monospace",
      labelSize:      11,
      labelWeight:    "600",
      labelColor:     { color: "rgba(235,242,252,0.96)" },
      defaultNodeColor: "#4a5260",
      defaultEdgeColor: EDGE_DEFAULT,
      stagePadding:   90,
      // High threshold = only render labels for hub nodes when zoomed out
      // They appear naturally as you zoom in (rendered size = nodeSize / cameraRatio)
      labelRenderedSizeThreshold: 20,

      nodeReducer: (node, attrs) => {
        const res  = { ...attrs };
        const cat  = g.getNodeAttribute(node, "vaCategory") as EntityCategoryKey;
        const comm = g.getNodeAttribute(node, "community")  as string;

        if (hidCatsRef.current.has(cat)) { res.hidden = true; return res; }

        const sn = selNodeRef.current;
        const sc = selCommRef.current;

        if (sn) {
          if (node === sn) {
            res.size   = (attrs.origSize as number) * 2.2;
            res.color  = "#ffffff";
            res.zIndex = 10;
          } else if (g.areNeighbors(node, sn)) {
            res.size   = (attrs.origSize as number) * 1.5;
            res.zIndex = 5;
          } else {
            res.color  = NODE_DIM;
            res.size   = (attrs.origSize as number) * 0.45;
            res.label  = "";
          }
        } else if (sc) {
          if (comm !== sc) {
            res.color  = NODE_DIM;
            res.size   = (attrs.origSize as number) * 0.4;
            res.label  = "";
          } else {
            res.size   = (attrs.origSize as number) * 1.2;
            res.zIndex = 3;
          }
        }
        return res;
      },

      edgeReducer: (edge, attrs) => {
        const res = { ...attrs };
        const sn  = selNodeRef.current;
        const sc  = selCommRef.current;

        if (sn) {
          if (g.hasExtremity(edge, sn)) {
            res.color = EDGE_ACTIVE; res.size = 2; res.zIndex = 5;
          } else {
            res.color = "rgba(0,0,0,0)"; res.size = 0;
          }
        } else if (sc) {
          const srcComm = g.getNodeAttribute(g.source(edge), "community");
          const tgtComm = g.getNodeAttribute(g.target(edge), "community");
          if (srcComm === sc && tgtComm === sc) {
            res.color = EDGE_ACTIVE; res.size = 1.2;
          } else {
            res.color = "rgba(0,0,0,0)"; res.size = 0;
          }
        }
        return res;
      },
    });

    sigmaRef.current = sigma;

    sigma.on("clickNode", (ev) => {
      const raw = g.getNodeAttribute(ev.node, "raw") as GraphNodeJSON | null;
      onClickRef.current(ev.node, raw);
    });
    sigma.on("clickStage", () => {
      setSelectedComm(null);
      selCommRef.current = null;
      sigma.refresh();
    });
    sigma.on("enterNode", (ev) => {
      g.setNodeAttribute(ev.node, "forceLabel", true);
      el.style.cursor = "pointer";
      sigma.refresh();
    });
    sigma.on("leaveNode", (ev) => {
      g.setNodeAttribute(ev.node, "forceLabel", false);
      el.style.cursor = "default";
      sigma.refresh();
    });

    sigma.on("afterRender",        refreshLabels);
    sigma.getCamera().on("updated", refreshLabels);
    setTimeout(refreshLabels, 100);

    return () => {
      sigma.kill();
      sigmaRef.current = null;
      graphRef.current = null;
      setLabelPositions([]);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rebuildKey]);

  useEffect(() => { sigmaRef.current?.refresh(); }, [selectedNodeId, hiddenCategories, selectedComm]);

  useEffect(() => {
    if (!focusNodeId || !sigmaRef.current || !graphRef.current) return;
    const sigma = sigmaRef.current;
    if (!graphRef.current.hasNode(focusNodeId)) { onFocusHandled(); return; }
    const pos = sigma.getNodeDisplayData(focusNodeId);
    if (pos) sigma.getCamera().animate({ x: pos.x, y: pos.y, ratio: 0.1 }, { duration: 650 });
    onFocusHandled();
  }, [focusNodeId, onFocusHandled]);

  function handleClusterClick(lp: LabelPos) {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    if (selectedComm === lp.id) {
      setSelectedComm(null);
      selCommRef.current = null;
      sigma.refresh();
      return;
    }
    setSelectedComm(lp.id);
    selCommRef.current = lp.id;

    let sx = 0, sy = 0, cnt = 0;
    for (const n of lp.members) {
      const d = sigma.getNodeDisplayData(n);
      if (d && !d.hidden) { sx += d.x; sy += d.y; cnt++; }
    }
    if (cnt > 0) sigma.getCamera().animate({ x: sx / cnt, y: sy / cnt, ratio: 0.22 }, { duration: 650 });
    sigma.refresh();
  }

  // ── States ────────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-8 bg-[var(--bg-void)]">
        <p className="font-mono text-[13px] text-[var(--danger)]">Intelligence feed error: {error}</p>
      </div>
    );
  }
  if (loading && (!data || data.nodes.length === 0)) {
    return (
      <div className="flex h-full items-center justify-center bg-[var(--bg-void)]">
        <div className="flex flex-col items-center gap-4">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
          <p className="font-mono text-[11px] uppercase tracking-widest text-[var(--text-muted)]">Mapping Node Set</p>
        </div>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="relative h-full w-full bg-[var(--bg-void)] overflow-hidden">

      <div ref={containerRef} className="absolute inset-0" />

      {/* Vignette */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(ellipse 80% 80% at 50% 50%, transparent 45%, rgba(5,8,13,0.8) 100%)" }}
      />

      {/* SVG leader lines */}
      <svg
        className="pointer-events-none absolute inset-0"
        style={{ width: "100%", height: "100%", overflow: "visible" }}
      >
        {labelPositions.map((lp) => {
          const active = selectedComm === lp.id;
          const dx = lp.labelX - lp.anchorX;
          const dy = lp.labelY - lp.anchorY;
          const len = Math.sqrt(dx * dx + dy * dy) || 1;
          // Stop line a few px short of label center so it ends at pill edge
          const ex = lp.labelX - (dx / len) * (PILL_W / 2 + 2);
          const ey = lp.labelY - (dy / len) * (PILL_H / 2 + 2);

          return (
            <g key={lp.id} style={{ opacity: lp.opacity * (active ? 1 : 0.5) }}>
              {/* Glow blur */}
              <line x1={lp.anchorX} y1={lp.anchorY} x2={ex} y2={ey}
                stroke={lp.color} strokeWidth={4} strokeOpacity={0.1} />
              {/* Main line */}
              <line x1={lp.anchorX} y1={lp.anchorY} x2={ex} y2={ey}
                stroke={lp.color}
                strokeWidth={active ? 1.2 : 0.7}
                strokeOpacity={active ? 0.75 : 0.3}
                strokeDasharray={active ? "none" : "5 4"} />
              {/* Anchor dot */}
              <circle cx={lp.anchorX} cy={lp.anchorY} r={3} fill={lp.color} fillOpacity={active ? 0.8 : 0.5} />
            </g>
          );
        })}
      </svg>

      {/* Cluster pill labels */}
      {labelPositions.map((lp) => {
        const active = selectedComm === lp.id;
        return (
          <button
            key={lp.id}
            onClick={() => handleClusterClick(lp)}
            className="absolute"
            style={{
              left:          lp.labelX,
              top:           lp.labelY,
              transform:     "translate(-50%, -50%)",
              opacity:       lp.opacity,
              transition:    "opacity 0.2s ease",
              cursor:        "pointer",
              pointerEvents: lp.opacity > 0.1 ? "auto" : "none",
              zIndex:        active ? 20 : 10,
            }}
          >
            <div
              className="flex items-center gap-1.5 rounded-full transition-all duration-200"
              style={{
                padding:        "4px 10px 4px 7px",
                background:     active ? `${lp.color}20` : "rgba(7,11,17,0.88)",
                border:         `1px solid ${lp.color}${active ? "88" : "40"}`,
                backdropFilter: "blur(8px)",
                boxShadow:      active
                  ? `0 0 18px ${lp.color}44, inset 0 0 8px ${lp.color}11`
                  : "0 2px 12px rgba(0,0,0,0.5)",
                whiteSpace: "nowrap",
              }}
            >
              {/* Color dot */}
              <span
                className="flex-shrink-0 rounded-full"
                style={{
                  width:     7, height: 7,
                  background: lp.color,
                  boxShadow:  active ? `0 0 6px ${lp.color}` : "none",
                }}
              />
              {/* Label */}
              <span
                style={{
                  fontFamily:    "'IBM Plex Mono', monospace",
                  fontSize:      "9.5px",
                  fontWeight:    700,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color:         active ? lp.color : `${lp.color}cc`,
                  maxWidth:      148,
                  overflow:      "hidden",
                  textOverflow:  "ellipsis",
                }}
              >
                {lp.label}
              </span>
              {/* Count badge */}
              <span
                style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize:   "8px",
                  color:      active ? lp.color : `${lp.color}bb`,
                  background: active ? `${lp.color}22` : "transparent",
                  padding:    active ? "0 4px" : "0",
                  borderRadius: 99,
                  marginLeft: 2,
                }}
              >
                {lp.nodeCount}
              </span>
            </div>
          </button>
        );
      })}

      {/* Navigation Controls */}
      <div className="absolute bottom-4 left-4 flex flex-col gap-1.5 z-20">
        <button
          title="Fit graph in view"
          onClick={() => {
            const sigma = sigmaRef.current;
            if (!sigma) return;
            sigma.getCamera().animate({ x: 0, y: 0, ratio: 1, angle: 0 }, { duration: 400 });
          }}
          className="flex h-7 w-7 items-center justify-center rounded border border-white/10 bg-[rgba(7,11,17,0.82)] text-[rgba(200,220,240,0.85)] backdrop-blur-sm hover:border-white/20 hover:text-white transition-all"
          style={{ fontFamily: "monospace", fontSize: 12 }}
        >
          ⊙
        </button>
        <button
          title="Zoom in"
          onClick={() => {
            const cam = sigmaRef.current?.getCamera();
            if (cam) cam.animate({ ratio: cam.ratio * 0.6 }, { duration: 300 });
          }}
          className="flex h-7 w-7 items-center justify-center rounded border border-white/10 bg-[rgba(7,11,17,0.82)] text-[rgba(200,220,240,0.85)] backdrop-blur-sm hover:border-white/20 hover:text-white transition-all"
          style={{ fontFamily: "monospace", fontSize: 16 }}
        >
          +
        </button>
        <button
          title="Zoom out"
          onClick={() => {
            const cam = sigmaRef.current?.getCamera();
            if (cam) cam.animate({ ratio: cam.ratio * 1.6 }, { duration: 300 });
          }}
          className="flex h-7 w-7 items-center justify-center rounded border border-white/10 bg-[rgba(7,11,17,0.82)] text-[rgba(200,220,240,0.85)] backdrop-blur-sm hover:border-white/20 hover:text-white transition-all"
          style={{ fontFamily: "monospace", fontSize: 16 }}
        >
          −
        </button>
      </div>

      {/* Pan/zoom hint — shown only when graph is ready */}
      {labelPositions.length > 0 && (
        <div className="pointer-events-none absolute top-4 left-1/2 -translate-x-1/2">
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "rgba(165,185,210,0.45)" }}>
            drag to pan · scroll to zoom · click cluster to filter
          </span>
        </div>
      )}

      {/* Legend */}
      <div className="pointer-events-none absolute bottom-4 right-4 flex flex-col gap-[5px]">
        {(Object.entries(CAT_COLOR) as [EntityCategoryKey, string][])
          .filter(([cat]) => !hiddenCategories.has(cat))
          .filter(([cat]) => {
            const g = graphRef.current;
            return g ? g.someNode((_, a) => (a.vaCategory as EntityCategoryKey) === cat) : false;
          })
          .map(([cat, color]) => (
            <div key={cat} className="flex items-center gap-1.5">
              <span className="rounded-full" style={{ width: 5, height: 5, background: color, display: "inline-block" }} />
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 8, letterSpacing: "0.1em", textTransform: "uppercase", color: "rgba(165,185,210,0.82)" }}>
                {CATEGORY_META[cat]?.short ?? cat}
              </span>
            </div>
          ))}
      </div>

      {/* Clear filter hint */}
      {selectedComm && (
        <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2">
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, letterSpacing: "0.15em", textTransform: "uppercase", color: "rgba(165,185,210,0.72)" }}>
            click canvas to clear filter
          </span>
        </div>
      )}
    </div>
  );
}
