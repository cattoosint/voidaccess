"use client";

import { useEffect, useState } from "react";

const FACTS = [
  // OSINT tradecraft
  "OSINT analysts use passive DNS reanalysis to uncover previously hidden infrastructure changes without alerting targets.",
  "Threat actors on dark web forums often reuse operational handles across platforms — a single handle can link dozens of personas.",
  "Bitcoin transaction graph analysis can de-anonymize wallets with as few as three confirmed co-spend events.",
  "The average dwell time of an APT inside a compromised network before detection is 197 days.",
  "Domain generation algorithms (DGAs) can produce thousands of C2 candidates per day, but all share a statistical fingerprint.",
  "Silk Road's downfall began when an admin posted on Stack Overflow using their real identity months before launch.",
  "Most ransomware groups use affiliate programs — the core developers write the code, affiliates deploy it for a revenue split.",
  "Monero's ring signature size determines the anonymity set — most legitimate transactions use 16 decoys by default.",
  "A single RDP brute-force success sells for $10–$50 on dark web access brokers, scaled by domain privilege.",
  "Telegram is the most common exfiltration channel for initial access brokers, replacing older IRC and forum models.",
  // Threat intelligence
  "MITRE ATT&CK catalogues over 400 unique adversary techniques organized across 14 tactical phases.",
  "Nation-state APTs frequently timestamp malware compilations to match business hours in their home timezone — a classic OPSEC failure.",
  "The average ransomware demand in 2023 was $1.54M — but the median payment was significantly lower due to negotiation.",
  "Cobalt Strike's watermark system allows defenders to attribute payloads to specific licensed customers when leaked.",
  "LockBit's affiliate panel included a real-time chat feature for negotiating ransoms directly with victims.",
  "Exploit brokers like Zerodium pay up to $2.5M for full iOS zero-click chains — the most expensive class of vulnerability.",
  "The Conti group's internal Jabber logs, leaked in 2022, revealed a structured corporate hierarchy with HR, R&D, and management.",
  "Most cybercriminal groups operate on a 9-to-5 schedule aligned with Moscow Standard Time, including scheduled lunch breaks.",
  "RedLine Stealer is the most prevalent infostealer by volume — its logs are the dominant product on Genesis Market.",
  "Initial access brokers typically wait 60–90 days before selling access to allow full enumeration of the network's value.",
  // Dark web mechanics
  "V3 onion addresses are 56 characters long and use ed25519 keys — V2 addresses were deprecated in 2021.",
  "Tor's hidden service protocol routes traffic through 6 relays — 3 for the client and 3 for the server — via a rendezvous point.",
  "The vast majority of .onion addresses are never indexed — discovery relies on referrals, paste sites, or dedicated link lists.",
  "Most dark web marketplaces implement a 2-of-3 multisig escrow to prevent exit scams from administrators.",
  "Exit node operators on Tor can observe plaintext traffic for non-HTTPS connections — a known deanonymization vector.",
  "The Tor network has approximately 7,000 relays but only ~1,500 are exit nodes, creating a bandwidth bottleneck.",
  "Many .onion sites implement proof-of-work puzzles to defend against DDoS attacks while preserving anonymity.",
  // Crypto & financial crime
  "Chain analysis firms estimate that only 0.24% of crypto transactions in 2023 were associated with illicit activity.",
  "Tornado Cash handled over $7B in transactions before OFAC sanctions — roughly 25% of funds had traceable criminal origins.",
  "Hydra Market processed over $5.2B in Bitcoin before its 2022 takedown — the largest dark web market seizure in history.",
  "UTXO consolidation is a common de-anonymization vector — when wallets merge inputs, they reveal common ownership.",
  "Privacy coins like Zcash have optional shielded transactions — but most Zcash transactions are transparent by default.",
  // Technical tradecraft
  "Living-off-the-land (LotL) attacks use legitimate system binaries like PowerShell and WMI to avoid EDR detection.",
  "The average time from public CVE disclosure to active exploitation in the wild is now under 15 days.",
  "Phishing-as-a-Service kits like EvilGinx use reverse proxies to steal session cookies, bypassing MFA entirely.",
  "Supply chain attacks cost on average 4x more to remediate than standard breaches due to their downstream blast radius.",
  "Adversary simulation teams use purple teaming — real-time collaboration between red and blue teams — to accelerate detection tuning.",
];

interface Props {
  query: string;
}

export function InvestigationLoadingScreen({ query }: Props) {
  const [factIndex, setFactIndex] = useState(() => Math.floor(Math.random() * FACTS.length));
  const [visible, setVisible] = useState(true);
  const [dots, setDots] = useState(".");
  const [scanLine, setScanLine] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  // Rotate facts every 7 seconds with fade
  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setFactIndex(i => (i + 1) % FACTS.length);
        setVisible(true);
      }, 400);
    }, 7000);
    return () => clearInterval(interval);
  }, []);

  // Animate dots
  useEffect(() => {
    const interval = setInterval(() => {
      setDots(d => (d.length >= 3 ? "." : d + "."));
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // Animate scan line (0–100)
  useEffect(() => {
    const interval = setInterval(() => {
      setScanLine(s => (s >= 100 ? 0 : s + 0.5));
    }, 16);
    return () => clearInterval(interval);
  }, []);

  // Track elapsed time
  useEffect(() => {
    const interval = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(interval);
  }, []);

  const elapsedLabel = elapsed < 60
    ? `${elapsed}s`
    : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--bg-void)] overflow-hidden">
      {/* Grid background */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `
            linear-gradient(to right, var(--text-primary) 1px, transparent 1px),
            linear-gradient(to bottom, var(--text-primary) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
        }}
      />

      {/* Scanning line */}
      <div
        className="pointer-events-none absolute left-0 right-0 h-[1px] transition-none"
        style={{
          top: `${scanLine}%`,
          background: "linear-gradient(to right, transparent, var(--accent), transparent)",
          opacity: 0.35,
          boxShadow: "0 0 12px 2px rgba(88,166,255,0.3)",
        }}
      />

      {/* Radial atmosphere */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(88,166,255,0.04) 0%, transparent 70%)",
        }}
      />

      {/* Header bar */}
      <div className="flex h-[56px] shrink-0 items-center justify-between border-b border-[var(--border-dim)] px-6">
        <div className="flex items-center gap-2 font-heading">
          <span className="text-[var(--accent)]">●</span>
          <span className="text-[15px] font-bold tracking-tight text-[var(--text-primary)]">voidaccess</span>
        </div>
        <div className="flex items-center gap-2.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--warning)] animate-pulse" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
            Analyzing Environment{dots}
          </span>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col items-center justify-center gap-12 px-6">

        {/* Central spinner + query */}
        <div className="flex flex-col items-center gap-6 text-center">
          {/* Animated rings */}
          <div className="relative flex h-24 w-24 items-center justify-center">
            <div className="absolute inset-0 rounded-full border border-[var(--accent-border)] animate-[spin_8s_linear_infinite]" />
            <div className="absolute inset-2 rounded-full border border-[var(--border-subtle)] animate-[spin_5s_linear_infinite_reverse]" />
            <div className="absolute inset-4 rounded-full border-[1.5px] border-[var(--accent)] opacity-60 animate-[spin_3s_linear_infinite]" />
            <div className="h-3 w-3 rounded-full bg-[var(--accent)] shadow-[0_0_16px_4px_rgba(88,166,255,0.5)]" />
          </div>

          <div className="flex flex-col items-center gap-2">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-[var(--text-muted)]">
              Active Investigation
            </p>
            <h2 className="font-heading text-2xl font-bold tracking-tight text-[var(--text-primary)] max-w-md">
              {query}
            </h2>
          </div>

          {/* Step indicators */}
          <div className="flex items-center gap-3">
            {["Search", "Scrape", "Extract", "Graph", "Summarize"].map((step, i) => (
              <div key={step} className="flex items-center gap-3">
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className="h-1.5 w-1.5 rounded-full"
                    style={{
                      background: "var(--accent)",
                      animation: `pulse-glow ${1 + i * 0.3}s ease-in-out infinite alternate`,
                    }}
                  />
                  <span className="font-mono text-[9px] uppercase tracking-widest text-[var(--text-muted)]">
                    {step}
                  </span>
                </div>
                {i < 4 && (
                  <div className="mb-4 h-px w-8 bg-[var(--border-dim)]" />
                )}
              </div>
            ))}
          </div>

          {/* Elapsed */}
          <p className="font-mono text-[10px] text-[var(--text-muted)] tracking-widest">
            ELAPSED: {elapsedLabel}
          </p>
        </div>

        {/* Fact rotator */}
        <div
          className="mx-auto w-full max-w-2xl rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6"
          style={{ minHeight: "120px" }}
        >
          <div className="mb-3 flex items-center gap-2">
            <span className="font-mono text-[9px] font-bold uppercase tracking-[0.25em] text-[var(--accent)]">
              Intelligence Briefing
            </span>
            <div className="flex-1 h-px bg-[var(--border-dim)]" />
            <span className="font-mono text-[9px] text-[var(--text-muted)]">
              {factIndex + 1} / {FACTS.length}
            </span>
          </div>

          <div
            style={{
              opacity: visible ? 1 : 0,
              transform: visible ? "translateY(0)" : "translateY(4px)",
              transition: "opacity 0.4s ease, transform 0.4s ease",
            }}
          >
            <p className="text-[13px] font-medium leading-relaxed text-[var(--text-secondary)]">
              {FACTS[factIndex]}
            </p>
          </div>

          {/* Progress bar for fact timer */}
          <div className="mt-4 h-[2px] w-full overflow-hidden rounded-full bg-[var(--border-dim)]">
            <div
              className="h-full rounded-full bg-[var(--accent)] opacity-50"
              style={{
                animation: "fact-progress 7s linear infinite",
              }}
            />
          </div>
        </div>
      </div>

      {/* Footer hint */}
      <div className="flex h-12 shrink-0 items-center justify-center border-t border-[var(--border-dim)]">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
          Fanning out across Tor network · Extracting entities · Building relationship graph
        </p>
      </div>

      <style>{`
        @keyframes fact-progress {
          from { width: 0% }
          to   { width: 100% }
        }
        @keyframes pulse-glow {
          from { opacity: 0.3; box-shadow: 0 0 4px 1px rgba(88,166,255,0.3); }
          to   { opacity: 1;   box-shadow: 0 0 10px 3px rgba(88,166,255,0.7); }
        }
      `}</style>
    </div>
  );
}
