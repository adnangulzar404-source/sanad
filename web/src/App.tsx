import { useEffect, useState } from "react";
import { ProvenancePanel } from "./components/ProvenancePanel";
import { Ask } from "./screens/Ask";
import { Verify } from "./screens/Verify";

type Tab = "verify" | "ask";

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
  // Verify is the landing tab: it is the established primary and needs no API
  // key. Ask is one click away. Tab state is local -- no router dependency.
  const [tab, setTab] = useState<Tab>("verify");

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
    font: "inherit", padding: "0.5rem 1rem", cursor: "pointer",
    background: "none", border: "none",
    borderBlockEnd: active ? "2px solid var(--ink)" : "2px solid transparent",
    color: active ? "var(--ink)" : "var(--ink-60)",
    fontWeight: active ? 600 : 400,
  }) as const;

  return (
    <>
      <nav aria-label="mode" role="tablist" style={{
        display: "flex", gap: "0.5rem", maxWidth: "72rem",
        margin: "0 auto", padding: "1rem 1.5rem 0",
      }}>
        <button role="tab" id="tab-verify" aria-controls="mode-panel"
                aria-selected={tab === "verify"} onClick={() => setTab("verify")}
                style={tabStyle(tab === "verify")}>Verify</button>
        <button role="tab" id="tab-ask" aria-controls="mode-panel"
                aria-selected={tab === "ask"} onClick={() => setTab("ask")}
                style={tabStyle(tab === "ask")}>Ask</button>
      </nav>

      <div role="tabpanel" id="mode-panel"
           aria-labelledby={tab === "verify" ? "tab-verify" : "tab-ask"}>
        {tab === "verify" ? <Verify /> : <Ask />}
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
