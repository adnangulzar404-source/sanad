import { useEffect, useState } from "react";
import { ProvenancePanel } from "./components/ProvenancePanel";
import { Ask } from "./screens/Ask";
import { Claims } from "./screens/Claims";
import { Verify } from "./screens/Verify";

/** Geometric Rub el Hizb — two overlapping squares (axis-aligned + 45°
 *  rotated) forming the traditional 8-pointed Islamic star, with a small
 *  centre circle. Drawn as SVG so it never depends on font rendering. */
function RubElHizb({ size, color, opacity, style }: {
  size: number; color: string; opacity: number; style?: React.CSSProperties;
}) {
  // 8-pointed star polygon: outer R=45, inner r=19, 16 alternating vertices.
  const pts =
    "50,5 57.3,32.4 81.8,18.2 67.6,42.7 95,50 67.6,57.3 " +
    "81.8,81.8 57.3,67.6 50,95 42.7,67.6 18.2,81.8 32.4,57.3 " +
    "5,50 32.4,42.7 18.2,18.2 42.7,32.4";
  return (
    <svg aria-hidden width={size} height={size} viewBox="0 0 100 100"
         style={{ color, opacity, display: "block", ...style }}>
      <polygon points={pts} fill="currentColor" />
      <circle cx="50" cy="50" r="9" fill="currentColor" />
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
        {/* Large primary: slow full rotation, gold, off-center right */}
        <RubElHizb size={340} color="var(--gold)" opacity={0.09}
          style={{ position: "absolute", top: "6%", right: "-4%",
                   animation: "bgRotate 180s linear infinite",
                   transformOrigin: "center center" }} />

        {/* Medium: drifts slowly, verdigris, lower-left */}
        <RubElHizb size={190} color="var(--verdigris)" opacity={0.06}
          style={{ position: "absolute", bottom: "10%", left: "-2%",
                   animation: "bgDrift 140s ease-in-out infinite" }} />

        {/* Small: reverse drift, gold, upper-centre */}
        <RubElHizb size={88} color="var(--gold)" opacity={0.055}
          style={{ position: "absolute", top: "2%", left: "32%",
                   animation: "bgDrift 100s ease-in-out infinite reverse" }} />
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
