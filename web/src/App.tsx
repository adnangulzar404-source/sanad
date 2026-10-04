import { useEffect, useState } from "react";
import { ProvenancePanel } from "./components/ProvenancePanel";
import { Ask } from "./screens/Ask";
import { Claims } from "./screens/Claims";
import { Verify } from "./screens/Verify";

/** Geometric Rub el Hizb — two congruent squares (one axis-aligned, one
 *  rotated 45°) with fill-rule="evenodd": outer teeth (inside one square only)
 *  are filled; inner octagon (inside both squares) is hollow; centre dot on top.
 *  Sharp 90° outer points, hollow ring interior — matches the traditional shape. */
function RubElHizb({ size, color, opacity, style }: {
  size: number; color: string; opacity: number; style?: React.CSSProperties;
}) {
  const star =
    "M17,17 L83,17 L83,83 L17,83 Z " +
    "M50,3  L97,50 L50,97 L3,50  Z";
  return (
    <svg aria-hidden width={size} height={size} viewBox="0 0 100 100"
         style={{ color, opacity, display: "block", ...style }}>
      <path d={star} fillRule="evenodd" fill="currentColor" />
      <circle cx="50" cy="50" r="7" fill="currentColor" />
    </svg>
  );
}

type Tab = "ask" | "verify" | "claims";

const PROVENANCE_HASH = "#provenance";

/** Removes the fragment from the URL without leaving a bare trailing "#" and
 * without pushing a history entry or firing our own "hashchange" — the panel
 * open/close state already lives in React state, not in history. */
function clearProvenanceHash() {
  const { pathname, search } = window.location;
  window.history.replaceState(null, "", pathname + search);
}

export default function App() {
  // `IsnadTrace` links to "#provenance" so a reader can jump straight to a
  // card's source, and so `<deployment>/#provenance` is a citable URL to the
  // corpus manifest on its own. Both require the panel to open in response
  // to the hash, not only via the button below.
  const [showProvenance, setShowProvenance] = useState(
    () => window.location.hash === PROVENANCE_HASH
  );
  // Ask is the landing tab: it is the primary experience. Verify is one click
  // away. Tab state is local -- no router dependency.
  const [tab, setTab] = useState<Tab>("ask");

  useEffect(() => {
    const openOnHash = () => {
      if (window.location.hash === PROVENANCE_HASH) setShowProvenance(true);
    };
    window.addEventListener("hashchange", openOnHash);
    return () => window.removeEventListener("hashchange", openOnHash);
  }, []);

  const close = () => {
    setShowProvenance(false);
    // Without this, the hash is still "#provenance" after closing. A second
    // click on the same link then changes nothing -- the hash was already
    // that value, so "hashchange" never fires -- and the link is dead again,
    // just one click later than before this fix.
    clearProvenanceHash();
  };

  const tabStyle = (active: boolean) => ({
    font: "inherit", padding: "0.5rem 1.1rem", cursor: "pointer",
    background: active ? "color-mix(in srgb, var(--verdigris) 8%, var(--page))" : "none",
    border: "none",
    borderBlockEnd: active ? "2px solid var(--verdigris)" : "2px solid transparent",
    color: active ? "var(--verdigris)" : "var(--ink-60)",
    fontWeight: active ? 600 : 400,
    borderRadius: "2px 2px 0 0",
    transition: "color 0.15s, border-color 0.15s, background 0.15s",
  }) as const;

  return (
    <>
      {/* Fixed background layer: slowly rotating/drifting ۞ symbols create
          atmosphere without competing with content. aria-hidden + z-index:-1
          keep them invisible to AT and behind every interactive element. */}
      <div aria-hidden="true" style={{
        position: "fixed", inset: 0, zIndex: -1,
        overflow: "hidden", pointerEvents: "none",
      }}>
        {/* Top-right — large, gold, primary rotation */}
        <RubElHizb size={300} color="var(--gold)" opacity={0.11}
          style={{ position: "absolute", top: "4%", right: "-3%",
                   animation: "bgRotate 45s linear infinite",
                   transformOrigin: "center center" }} />

        {/* Bottom-left — medium, verdigris, counter-rotation */}
        <RubElHizb size={200} color="var(--verdigris)" opacity={0.08}
          style={{ position: "absolute", bottom: "6%", left: "-3%",
                   animation: "bgRotate 60s linear infinite reverse",
                   transformOrigin: "center center" }} />

        {/* Top-left — small, gold, slow rotation */}
        <RubElHizb size={110} color="var(--gold)" opacity={0.07}
          style={{ position: "absolute", top: "3%", left: "2%",
                   animation: "bgRotate 80s linear infinite",
                   transformOrigin: "center center" }} />

        {/* Bottom-right — medium-small, verdigris, medium rotation */}
        <RubElHizb size={150} color="var(--verdigris)" opacity={0.07}
          style={{ position: "absolute", bottom: "4%", right: "2%",
                   animation: "bgRotate 55s linear infinite reverse",
                   transformOrigin: "center center" }} />
      </div>

      {/* Brand header: Arabic name + Rub el Hizb (۞, U+06DE — the octagonal
          star marker used in Qur'an text layout) as geometric decoration. */}
      <header style={{
        maxWidth: "72rem", margin: "0 auto",
        padding: "1.25rem 1.5rem 0",
        display: "flex", alignItems: "baseline", gap: "0.75rem",
      }}>
        <RubElHizb size={24} color="var(--gold)" opacity={1} />
        <span style={{
          fontFamily: "var(--naskh)", fontSize: "var(--step-2)",
          color: "var(--ink)", direction: "rtl", lineHeight: 1,
        }}>سند</span>
        <span aria-hidden style={{ color: "var(--ink-30)" }}>·</span>
        <span style={{
          fontFamily: "var(--serif)", fontSize: "var(--step--1)",
          color: "var(--ink-60)", letterSpacing: "0.04em", textTransform: "uppercase",
        }}>Sanad</span>
      </header>

      <nav aria-label="mode" role="tablist" style={{
        display: "flex", gap: "0.25rem", maxWidth: "72rem",
        margin: "0 auto", padding: "0.75rem 1.5rem 0",
        borderBlockEnd: "var(--rule)",
      }}>
        <button role="tab" id="tab-ask" aria-controls="mode-panel"
                aria-selected={tab === "ask"} onClick={() => setTab("ask")}
                style={tabStyle(tab === "ask")}>Ask</button>
        <button role="tab" id="tab-verify" aria-controls="mode-panel"
                aria-selected={tab === "verify"} onClick={() => setTab("verify")}
                style={tabStyle(tab === "verify")}>Verify</button>
        <button role="tab" id="tab-claims" aria-controls="mode-panel"
                aria-selected={tab === "claims"} onClick={() => setTab("claims")}
                style={tabStyle(tab === "claims")}>Claims</button>
      </nav>

      <div role="tabpanel" id="mode-panel"
           aria-labelledby={
             tab === "verify" ? "tab-verify" : tab === "claims" ? "tab-claims" : "tab-ask"
           }>
        {tab === "verify" ? <Verify /> : tab === "claims" ? <Claims /> : <Ask />}
      </div>
      <div style={{ maxWidth: "72rem", margin: "0 auto", padding: "0 1.5rem 4rem" }}>
        {showProvenance ? (
          <ProvenancePanel onClose={close} />
        ) : (
          <button onClick={() => setShowProvenance(true)} className="data"
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer",
                           color: "var(--ink)", textDecoration: "underline" }}>
            what this corpus is, and where it came from
          </button>
        )}
      </div>
    </>
  );
}
