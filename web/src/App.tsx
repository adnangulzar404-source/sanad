import { useState } from "react";
import { ProvenancePanel } from "./components/ProvenancePanel";
import { Verify } from "./screens/Verify";

export default function App() {
  const [showProvenance, setShowProvenance] = useState(false);
  return (
    <>
      <Verify />
      <div style={{ maxWidth: "72rem", margin: "0 auto", padding: "0 1.5rem 4rem" }}>
        {showProvenance ? (
          <ProvenancePanel onClose={() => setShowProvenance(false)} />
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
